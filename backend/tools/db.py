import sqlite3
import os
from typing import List, Optional, Dict, Any
from datetime import date

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")
DB_PATH = os.path.join(DATA_DIR, "tools.db")


def _get_conn() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS daily_checkin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            check_date DATE NOT NULL,
            department TEXT NOT NULL,
            school_name TEXT NOT NULL,
            course_type TEXT,
            course_name TEXT NOT NULL,
            coach_name TEXT NOT NULL,
            course_date TEXT,
            start_time TEXT,
            end_time TEXT,
            sign_in_time TEXT,
            sign_out_time TEXT,
            sign_status TEXT NOT NULL,
            actual_count INTEGER DEFAULT 0,
            expected_count INTEGER DEFAULT 0,
            confirmed_revenue REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(check_date, course_name, coach_name, course_date, start_time)
        );

        CREATE TABLE IF NOT EXISTS checkin_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_date DATE NOT NULL,
            coach_file TEXT,
            finance_file TEXT,
            output_filename TEXT,
            record_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS monthly_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            analysis_type TEXT NOT NULL DEFAULT 'campus',
            filename TEXT,
            record_count INTEGER DEFAULT 0,
            department_count INTEGER DEFAULT 0,
            coach_count INTEGER DEFAULT 0,
            sheets TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_checkin_date_dept
            ON daily_checkin(check_date, department);
        CREATE INDEX IF NOT EXISTS idx_checkin_coach
            ON daily_checkin(coach_name, check_date);
        CREATE INDEX IF NOT EXISTS idx_monthly_year_month
            ON monthly_analyses(year, month, analysis_type);

        CREATE TABLE IF NOT EXISTS monthly_checkin_consolidation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            record_count INTEGER DEFAULT 0,
            filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month)
        );
    """)
    # Migration: add output_filename if missing
    try:
        conn.execute("ALTER TABLE checkin_batches ADD COLUMN output_filename TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def save_checkin_records(records: List[Dict[str, Any]], batch_info: Dict[str, Any]) -> int:
    conn = _get_conn()
    cur = conn.cursor()

    inserted = 0
    for r in records:
        try:
            cur.execute("""
                INSERT OR IGNORE INTO daily_checkin
                (check_date, department, school_name, course_type, course_name,
                 coach_name, course_date, start_time, end_time,
                 sign_in_time, sign_out_time, sign_status,
                 actual_count, expected_count, confirmed_revenue)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r.get("check_date"), r.get("department"), r.get("school_name"),
                r.get("course_type"), r.get("course_name"), r.get("coach_name"),
                r.get("course_date"), r.get("start_time"), r.get("end_time"),
                r.get("sign_in_time"), r.get("sign_out_time"), r.get("sign_status"),
                r.get("actual_count", 0), r.get("expected_count", 0), r.get("confirmed_revenue", 0),
            ))
            if cur.rowcount > 0:
                inserted += 1
        except sqlite3.IntegrityError:
            pass

    cur.execute("""
        INSERT INTO checkin_batches (batch_date, coach_file, finance_file, output_filename, record_count, status)
        VALUES (?, ?, ?, ?, ?, 'completed')
    """, (
        batch_info.get("batch_date", str(date.today())),
        batch_info.get("coach_file", ""),
        batch_info.get("finance_file", ""),
        batch_info.get("output_filename", ""),
        inserted,
    ))
    batch_id = cur.lastrowid

    conn.commit()
    conn.close()
    return batch_id


def get_checkin_by_month(year: int, month: int) -> List[Dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM daily_checkin
        WHERE strftime('%Y', check_date) = ? AND strftime('%m', check_date) = ?
        ORDER BY check_date, department, school_name, coach_name
    """, (str(year), f"{month:02d}")).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_available_months() -> List[str]:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT DISTINCT strftime('%Y-%m', check_date) as ym
        FROM daily_checkin ORDER BY ym DESC
    """).fetchall()
    conn.close()
    return [r["ym"] for r in rows]


def get_batches(limit: int = 50) -> List[Dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM checkin_batches ORDER BY created_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_batch(batch_id: int) -> Optional[Dict[str, Any]]:
    """Delete a batch and its associated checkin records. Returns the batch info for file cleanup."""
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    batch = conn.execute("SELECT * FROM checkin_batches WHERE id = ?", (batch_id,)).fetchone()
    if not batch:
        conn.close()
        return None

    batch_info = dict(batch)
    batch_date = batch_info["batch_date"]

    # Delete associated checkin records
    conn.execute("DELETE FROM daily_checkin WHERE check_date = ?", (batch_date,))
    # Delete the batch record
    conn.execute("DELETE FROM checkin_batches WHERE id = ?", (batch_id,))

    conn.commit()
    conn.close()
    return batch_info


# ──────────────────── Monthly Analysis ────────────────────

def save_monthly_analysis(info: Dict[str, Any]) -> int:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO monthly_analyses (year, month, analysis_type, filename, record_count, department_count, coach_count, sheets)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        info.get("year"), info.get("month"), info.get("analysis_type", "campus"),
        info.get("filename", ""), info.get("record_count", 0),
        info.get("department_count", 0), info.get("coach_count", 0),
        info.get("sheets", ""),
    ))
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_monthly_analyses(analysis_type: str = "campus", limit: int = 50) -> List[Dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM monthly_analyses WHERE analysis_type = ?
        ORDER BY created_at DESC LIMIT ?
    """, (analysis_type, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_monthly_analysis(analysis_id: int) -> Optional[Dict[str, Any]]:
    """Delete a monthly analysis record. Returns the record info for file cleanup."""
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM monthly_analyses WHERE id = ?", (analysis_id,)).fetchone()
    if not row:
        conn.close()
        return None

    info = dict(row)
    conn.execute("DELETE FROM monthly_analyses WHERE id = ?", (analysis_id,))
    conn.commit()
    conn.close()
    return info


# ──────────────────── Check-in Consolidation ────────────────────

def save_consolidation(year: int, month: int, record_count: int, filename: str, status: str = 'draft') -> int:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO monthly_checkin_consolidation (year, month, status, record_count, filename, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(year, month) DO UPDATE SET
            status = excluded.status,
            record_count = excluded.record_count,
            filename = excluded.filename,
            updated_at = CURRENT_TIMESTAMP
    """, (year, month, status, record_count, filename))
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_consolidation(year: int, month: int) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM monthly_checkin_consolidation WHERE year = ? AND month = ?",
        (year, month)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_consolidation_status(consolidation_id: int, status: str) -> bool:
    conn = _get_conn()
    cur = conn.execute(
        "UPDATE monthly_checkin_consolidation SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, consolidation_id)
    )
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def get_consolidations(limit: int = 50) -> List[Dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM monthly_checkin_consolidation
        ORDER BY year DESC, month DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_consolidation(consolidation_id: int) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM monthly_checkin_consolidation WHERE id = ?", (consolidation_id,)).fetchone()
    if not row:
        conn.close()
        return None
    info = dict(row)
    conn.execute("DELETE FROM monthly_checkin_consolidation WHERE id = ?", (consolidation_id,))
    conn.commit()
    conn.close()
    return info


# Auto-init on import
init_db()
