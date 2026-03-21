"""
TraceStore — local SQLite persistence for traces.
Allows offline mode and serves as a buffer before export.
"""

import json
import sqlite3
import logging
import threading
import os
from typing import List, Optional, Dict, Any
from .models import Trace

logger = logging.getLogger("agentixlens")

_DEFAULT_DB = os.path.expanduser("~/.agentixlens/traces.db")


class TraceStore:
    """
    Lightweight SQLite store for traces.
    Thread-safe via connection-per-thread pattern.
    """

    def __init__(self, project: str, db_path: str = _DEFAULT_DB):
        self.project = project
        self.db_path = db_path
        self._local = threading.local()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id      TEXT PRIMARY KEY,
                    project       TEXT,
                    agent_name    TEXT,
                    status        TEXT,
                    start_time    REAL,
                    end_time      REAL,
                    duration_ms   REAL,
                    total_tokens  INTEGER,
                    cost_usd      REAL,
                    llm_calls     INTEGER,
                    tool_calls    INTEGER,
                    payload       TEXT,
                    exported      INTEGER DEFAULT 0,
                    created_at    REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_project ON traces(project)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status  ON traces(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exported ON traces(exported)")
            conn.commit()

    def save(self, trace: Trace):
        """Persist a completed trace to SQLite."""
        try:
            with self._conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO traces
                    (trace_id, project, agent_name, status, start_time, end_time,
                     duration_ms, total_tokens, cost_usd, llm_calls, tool_calls,
                     payload, exported, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """, (
                    trace.trace_id,
                    trace.project,
                    trace.agent_name,
                    trace.status.value,
                    trace.start_time,
                    trace.end_time,
                    trace.duration_ms,
                    trace.total_tokens,
                    trace.total_cost_usd,
                    trace.llm_calls,
                    trace.tool_calls,
                    json.dumps(trace.to_dict()),
                    trace.start_time,
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"[TraceStore] save failed: {e}")

    def mark_exported(self, trace_id: str):
        with self._conn() as conn:
            conn.execute("UPDATE traces SET exported=1 WHERE trace_id=?", (trace_id,))
            conn.commit()

    def get_unexported(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return traces not yet sent to the backend (for retry on reconnect)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT payload FROM traces WHERE exported=0 ORDER BY start_time LIMIT ?",
                (limit,)
            ).fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT payload FROM traces WHERE trace_id=?", (trace_id,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def list_traces(
        self,
        project: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM traces WHERE 1=1"
        params = []
        if project:
            query += " AND project=?"; params.append(project)
        if status:
            query += " AND status=?";  params.append(status)
        query += " ORDER BY start_time DESC LIMIT ? OFFSET ?"
        params += [limit, offset]

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def stats(self, project: Optional[str] = None) -> Dict[str, Any]:
        """Aggregate stats for dashboard summary."""
        where = "WHERE project=?" if project else ""
        params = [project] if project else []
        with self._conn() as conn:
            row = conn.execute(f"""
                SELECT
                    COUNT(*)           AS total_runs,
                    AVG(duration_ms)   AS avg_latency_ms,
                    SUM(total_tokens)  AS total_tokens,
                    SUM(cost_usd)      AS total_cost,
                    SUM(CASE WHEN status='ok'    THEN 1 ELSE 0 END) AS ok_count,
                    SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) AS error_count
                FROM traces {where}
            """, params).fetchone()
        d = dict(row)
        total = d["total_runs"] or 1
        d["success_rate"] = round(d["ok_count"] / total * 100, 2)
        return d

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
