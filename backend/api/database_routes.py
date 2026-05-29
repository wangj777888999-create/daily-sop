from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging
import os

import database_manager as dm

router = APIRouter()
_logger = logging.getLogger(__name__)


class LocalConnectRequest(BaseModel):
    db_type: str                    # "sqlite" | "mysql" | "postgres"
    path: Optional[str] = None     # SQLite only
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None


class SSHConnectRequest(BaseModel):
    ssh_host: str
    ssh_port: int = 22
    ssh_user: str
    ssh_password: Optional[str] = None
    ssh_key: Optional[str] = None   # PEM content
    db_type: str = "mysql"
    db_host: str = "127.0.0.1"
    db_port: Optional[int] = None
    database: Optional[str] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None


class QueryRequest(BaseModel):
    sql: str
    limit: int = 20000


class SwitchDatabaseRequest(BaseModel):
    database: str


@router.post("/database/connect/local")
def connect_local(req: LocalConnectRequest):
    try:
        meta = dm.connect_local(
            req.db_type, req.path, req.host, req.port,
            req.database, req.user, req.password,
        )
        return {"ok": True, **meta}
    except Exception as e:
        _logger.exception("Local DB connect failed")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/database/connect/ssh")
def connect_ssh(req: SSHConnectRequest):
    try:
        meta = dm.connect_ssh(
            req.ssh_host, req.ssh_port, req.ssh_user,
            req.ssh_password, req.ssh_key,
            req.db_type, req.db_host, req.db_port,
            req.database, req.db_user, req.db_password,
        )
        return {"ok": True, **meta}
    except Exception as e:
        _logger.exception("SSH DB connect failed")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/database/status")
def get_status():
    status = dm.get_status()
    return status if status else {}


@router.get("/database/databases")
def list_databases():
    try:
        return dm.list_databases()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/database/switch")
def switch_database(req: SwitchDatabaseRequest):
    try:
        return dm.switch_database(req.database)
    except Exception as e:
        _logger.exception("Switch database failed")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/database/tables")
def get_tables():
    try:
        return dm.get_tables()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/database/columns/{table}")
def get_columns(table: str):
    try:
        return dm.get_columns(table)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/database/columns-full/{table}")
def get_columns_full(table: str):
    """Columns with comment field included."""
    try:
        return dm.get_columns_with_comments(table)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/database/table-comments")
def get_table_comments():
    """Return {table: comment} for all tables with a non-empty comment."""
    try:
        return dm.get_table_comments()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/database/query")
def execute_query(req: QueryRequest):
    try:
        return dm.execute_query(req.sql, req.limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/database/disconnect")
def disconnect():
    dm.disconnect()
    return {"ok": True}


class DescribeTableRequest(BaseModel):
    table_name: str
    columns: List[dict]   # [{name, type, pk}]


@router.post("/database/describe-table")
def describe_table(req: DescribeTableRequest):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="未配置 ANTHROPIC_API_KEY")
    try:
        import anthropic
        col_text = ", ".join(
            f"{c['name']}({c.get('type','?')})" for c in req.columns[:20]
        )
        prompt = (
            f"数据库表名：{req.table_name}\n"
            f"字段列表：{col_text}\n\n"
            "请用一句话（15字以内）描述这张表存储的是什么数据。"
            "直接输出描述内容，不要加任何前缀或标点之外的内容。"
        )
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=60,
            messages=[{"role": "user", "content": prompt}],
        )
        description = message.content[0].text.strip()
        return {"description": description}
    except Exception as e:
        _logger.exception("describe_table failed")
        raise HTTPException(status_code=500, detail=str(e))
