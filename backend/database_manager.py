"""
Single-user database connection manager.
Supports: local SQLite / MySQL / PostgreSQL, and SSH-tunnelled MySQL / PostgreSQL.
Only one active connection at a time.
"""
import sqlite3
import threading
import logging
import tempfile
import os
from typing import Optional, List, Dict, Any

_logger = logging.getLogger(__name__)
_lock = threading.Lock()

_active_conn = None   # raw DB connection
_active_tunnel = None  # SSHTunnelForwarder or None
_active_db_type: Optional[str] = None  # "sqlite" | "mysql" | "postgres"
_active_meta: Optional[Dict] = None    # display info
_ssh_key_tmp: Optional[str] = None     # temp file path for SSH key

# SSH reconnect context — kept alive so switch_database can reuse the tunnel
_ssh_reconnect: Optional[Dict] = None  # {local_port, db_user, db_password, ssh_host}


# ─────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────

def _close_existing():
    global _active_conn, _active_tunnel, _active_db_type, _active_meta, _ssh_key_tmp, _ssh_reconnect
    _ssh_reconnect = None
    if _active_conn:
        try:
            _active_conn.close()
        except Exception:
            pass
        _active_conn = None
    if _active_tunnel:
        try:
            _active_tunnel.stop()
        except Exception:
            pass
        _active_tunnel = None
    if _ssh_key_tmp and os.path.exists(_ssh_key_tmp):
        try:
            os.unlink(_ssh_key_tmp)
        except Exception:
            pass
        _ssh_key_tmp = None
    _active_db_type = None
    _active_meta = None


def _cursor():
    if _active_conn is None:
        raise RuntimeError("未连接数据库")
    return _active_conn.cursor()


def _make_sqlite_conn(path: str):
    return sqlite3.connect(path, check_same_thread=False)


def _make_mysql_conn(host: str, port: int, database: str, user: str, password: str):
    import pymysql
    return pymysql.connect(
        host=host, port=port, database=database,
        user=user, password=password,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.Cursor,
        connect_timeout=10,
    )


def _make_postgres_conn(host: str, port: int, database: str, user: str, password: str):
    import psycopg2
    return psycopg2.connect(
        host=host, port=port, dbname=database,
        user=user, password=password,
        connect_timeout=10,
    )


# ─────────────────────────────────────────────────────────────────────
# Public API – connect
# ─────────────────────────────────────────────────────────────────────

def connect_local(
    db_type: str,
    path: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict:
    global _active_conn, _active_db_type, _active_meta

    with _lock:
        _close_existing()

        if db_type == "sqlite":
            if not path:
                raise ValueError("SQLite 连接需要文件路径")
            _active_conn = _make_sqlite_conn(path)
            display = os.path.basename(path) or path
        elif db_type == "mysql":
            _active_conn = _make_mysql_conn(
                host or "127.0.0.1", port or 3306,
                database or "", user or "", password or "",
            )
            display = f"{host}:{port or 3306}/{database}"
        elif db_type == "postgres":
            _active_conn = _make_postgres_conn(
                host or "127.0.0.1", port or 5432,
                database or "", user or "", password or "",
            )
            display = f"{host}:{port or 5432}/{database}"
        else:
            raise ValueError(f"不支持的数据库类型: {db_type}")

        _active_db_type = db_type
        _active_meta = {
            "db_type": db_type,
            "display_name": display,
            "connection_type": "local",
        }
        _logger.info("Local DB connected: %s", display)
        return dict(_active_meta)


def connect_ssh(
    ssh_host: str,
    ssh_port: int = 22,
    ssh_user: str = "",
    ssh_password: Optional[str] = None,
    ssh_key: Optional[str] = None,
    db_type: str = "mysql",
    db_host: str = "127.0.0.1",
    db_port: Optional[int] = None,
    database: Optional[str] = None,
    db_user: Optional[str] = None,
    db_password: Optional[str] = None,
) -> Dict:
    global _active_conn, _active_tunnel, _active_db_type, _active_meta, _ssh_key_tmp
    from sshtunnel import SSHTunnelForwarder

    default_db_port = 3306 if db_type == "mysql" else 5432
    remote_db_port = db_port or default_db_port

    with _lock:
        _close_existing()

        tunnel_kwargs: Dict[str, Any] = dict(
            ssh_address_or_host=(ssh_host, ssh_port),
            ssh_username=ssh_user,
            remote_bind_address=(db_host, remote_db_port),
        )
        if ssh_password:
            tunnel_kwargs["ssh_password"] = ssh_password
        if ssh_key:
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False)
            tmp.write(ssh_key)
            tmp.close()
            os.chmod(tmp.name, 0o600)
            tunnel_kwargs["ssh_pkey"] = tmp.name
            _ssh_key_tmp = tmp.name

        tunnel = SSHTunnelForwarder(**tunnel_kwargs)
        tunnel.start()
        local_port = tunnel.local_bind_port
        _logger.info("SSH tunnel up: localhost:%d → %s:%d", local_port, db_host, remote_db_port)

        # MySQL can connect without selecting a database.
        # PostgreSQL requires a database; fall back to "postgres" system db.
        initial_db = database or ("" if db_type == "mysql" else "postgres")

        try:
            if db_type == "mysql":
                conn = _make_mysql_conn("127.0.0.1", local_port, initial_db, db_user or "", db_password or "")
            elif db_type == "postgres":
                conn = _make_postgres_conn("127.0.0.1", local_port, initial_db, db_user or "", db_password or "")
            else:
                tunnel.stop()
                raise ValueError(f"SSH 不支持此数据库类型: {db_type}")
        except Exception:
            tunnel.stop()
            raise

        _active_conn = conn
        _active_tunnel = tunnel
        _active_db_type = db_type
        _ssh_reconnect = {
            "local_port": local_port,
            "db_user": db_user or "",
            "db_password": db_password or "",
            "ssh_host": ssh_host,
        }
        display = f"{ssh_host} → {database}" if database else ssh_host
        _active_meta = {
            "db_type": db_type,
            "display_name": display,
            "connection_type": "ssh",
            "current_database": database or None,
        }
        _logger.info("SSH DB connected: %s", _active_meta["display_name"])
        return dict(_active_meta)


# ─────────────────────────────────────────────────────────────────────
# Public API – query
# ─────────────────────────────────────────────────────────────────────

def get_status() -> Optional[Dict]:
    return dict(_active_meta) if _active_meta else None


def get_tables() -> List[str]:
    cur = _cursor()
    if _active_db_type == "sqlite":
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [r[0] for r in cur.fetchall()]
    elif _active_db_type == "mysql":
        cur.execute("SHOW TABLES")
        return [r[0] for r in cur.fetchall()]
    elif _active_db_type == "postgres":
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        )
        return [r[0] for r in cur.fetchall()]
    return []


def get_columns(table: str) -> List[Dict]:
    cur = _cursor()
    if _active_db_type == "sqlite":
        cur.execute(f"PRAGMA table_info(\"{table}\")")
        return [
            {"name": r[1], "type": r[2] or "TEXT", "notnull": bool(r[3]), "pk": bool(r[5])}
            for r in cur.fetchall()
        ]
    elif _active_db_type == "mysql":
        cur.execute(f"DESCRIBE `{table}`")
        return [
            {"name": r[0], "type": r[1], "notnull": r[2] == "NO", "pk": r[3] == "PRI"}
            for r in cur.fetchall()
        ]
    elif _active_db_type == "postgres":
        cur.execute(
            """
            SELECT c.column_name, c.data_type, c.is_nullable,
                   CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_name = %s
            ) pk ON pk.column_name = c.column_name
            WHERE c.table_name = %s AND c.table_schema = 'public'
            ORDER BY c.ordinal_position
            """,
            (table, table),
        )
        return [
            {"name": r[0], "type": r[1], "notnull": r[2] == "NO", "pk": bool(r[3])}
            for r in cur.fetchall()
        ]
    return []


def get_table_comments() -> Dict[str, str]:
    """Return {table_name: comment} for all tables that have a comment."""
    cur = _cursor()
    if _active_db_type == "mysql":
        # Prefer explicit db name over DATABASE() which can return NULL after USE
        db_name = (_active_meta or {}).get("current_database") or None
        if not db_name:
            cur.execute("SELECT DATABASE()")
            row = cur.fetchone()
            db_name = row[0] if row else None
        if not db_name:
            _logger.warning("get_table_comments: no current database selected")
            return {}
        cur.execute(
            "SELECT TABLE_NAME, TABLE_COMMENT "
            "FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_COMMENT != '' AND TABLE_COMMENT IS NOT NULL",
            (db_name,)
        )
        return {r[0]: r[1] for r in cur.fetchall()}
    elif _active_db_type == "postgres":
        cur.execute(
            """
            SELECT c.relname, obj_description(c.oid, 'pg_class')
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
              AND obj_description(c.oid, 'pg_class') IS NOT NULL
            """
        )
        return {r[0]: r[1] for r in cur.fetchall()}
    return {}


def get_columns_with_comments(table: str) -> List[Dict]:
    """Like get_columns but also includes column-level comments (MySQL/PG)."""
    cur = _cursor()
    if _active_db_type == "sqlite":
        cur.execute(f'PRAGMA table_info("{table}")')
        return [
            {"name": r[1], "type": r[2] or "TEXT", "notnull": bool(r[3]),
             "pk": bool(r[5]), "comment": ""}
            for r in cur.fetchall()
        ]
    elif _active_db_type == "mysql":
        db_name = (_active_meta or {}).get("current_database") or None
        if not db_name:
            cur.execute("SELECT DATABASE()")
            row = cur.fetchone()
            db_name = row[0] if row else None
        cur.execute(
            "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_COMMENT "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION",
            (db_name, table),
        )
        return [
            {"name": r[0], "type": r[1], "notnull": r[2] == "NO",
             "pk": r[3] == "PRI", "comment": r[4] or ""}
            for r in cur.fetchall()
        ]
    elif _active_db_type == "postgres":
        cur.execute(
            """
            SELECT c.column_name, c.data_type, c.is_nullable,
                   CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END,
                   pgd.description
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_name = %s
            ) pk ON pk.column_name = c.column_name
            LEFT JOIN pg_catalog.pg_statio_all_tables st
              ON st.relname = c.table_name
            LEFT JOIN pg_catalog.pg_description pgd
              ON pgd.objoid = st.relid
             AND pgd.objsubid = c.ordinal_position
            WHERE c.table_name = %s AND c.table_schema = 'public'
            ORDER BY c.ordinal_position
            """,
            (table, table),
        )
        return [
            {"name": r[0], "type": r[1], "notnull": r[2] == "NO",
             "pk": bool(r[3]), "comment": r[4] or ""}
            for r in cur.fetchall()
        ]
    return []


def execute_query(sql: str, limit: int = 500) -> Dict:
    cur = _cursor()
    cur.execute(sql)
    if cur.description:
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchmany(limit)
        row_data = [[str(v) if v is not None else None for v in row] for row in rows]
        return {
            "columns": columns,
            "rows": row_data,
            "row_count": len(row_data),
            "truncated": len(row_data) == limit,
        }
    # DML (INSERT / UPDATE / DELETE)
    try:
        _active_conn.commit()
    except Exception:
        pass
    return {
        "columns": [],
        "rows": [],
        "row_count": 0,
        "affected": getattr(cur, "rowcount", 0),
        "truncated": False,
    }


def list_databases() -> List[str]:
    cur = _cursor()
    if _active_db_type == "mysql":
        cur.execute("SHOW DATABASES")
        skip = {"information_schema", "performance_schema", "sys", "mysql"}
        return [r[0] for r in cur.fetchall() if r[0] not in skip]
    elif _active_db_type == "postgres":
        cur.execute(
            "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname"
        )
        return [r[0] for r in cur.fetchall()]
    raise RuntimeError("当前连接类型不支持列出数据库")


def switch_database(db_name: str) -> Dict:
    """Switch to a different database on the existing connection."""
    global _active_conn, _active_meta

    if not _active_conn:
        raise RuntimeError("未连接数据库")

    with _lock:
        if _active_db_type == "mysql":
            # MySQL supports USE statement — no reconnect needed
            cur = _active_conn.cursor()
            cur.execute(f"USE `{db_name}`")
        elif _active_db_type == "postgres":
            # PostgreSQL requires a new connection per database
            if not _ssh_reconnect:
                raise RuntimeError("PostgreSQL 切换数据库需要 SSH 连接信息，请重新连接")
            if _active_conn:
                try:
                    _active_conn.close()
                except Exception:
                    pass
                _active_conn = None
            lp = _ssh_reconnect["local_port"]
            _active_conn = _make_postgres_conn(
                "127.0.0.1", lp, db_name,
                _ssh_reconnect["db_user"], _ssh_reconnect["db_password"],
            )
        else:
            raise RuntimeError("当前连接类型不支持切换数据库")

        ssh_host = (_ssh_reconnect or {}).get("ssh_host", _active_meta.get("display_name", ""))
        _active_meta = {
            **(_active_meta or {}),
            "display_name": f"{ssh_host} → {db_name}",
            "current_database": db_name,
        }
        _logger.info("Switched to database: %s", db_name)
        return dict(_active_meta)


def disconnect():
    with _lock:
        _close_existing()
    _logger.info("DB disconnected")
