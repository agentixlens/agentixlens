"""
db/database.py — async SQLite via aiosqlite
"""

import os
import aiosqlite

DB_PATH = os.environ.get("AGENTIXLENS_DB", os.path.expanduser("~/.agentixlens/server.db"))


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                trace_id      TEXT PRIMARY KEY,
                project       TEXT NOT NULL,
                agent_name    TEXT NOT NULL,
                status        TEXT NOT NULL,
                start_time    REAL NOT NULL,
                end_time      REAL,
                duration_ms   REAL,
                total_tokens  INTEGER DEFAULT 0,
                cost_usd      REAL    DEFAULT 0.0,
                llm_calls     INTEGER DEFAULT 0,
                tool_calls    INTEGER DEFAULT 0,
                payload       TEXT NOT NULL,
                sdk_version   TEXT,
                created_at    REAL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS spans (
                span_id     TEXT PRIMARY KEY,
                trace_id    TEXT NOT NULL,
                parent_id   TEXT,
                name        TEXT NOT NULL,
                kind        TEXT NOT NULL,
                status      TEXT NOT NULL,
                start_time  REAL NOT NULL,
                end_time    REAL,
                duration_ms REAL,
                error       TEXT,
                payload     TEXT NOT NULL,
                FOREIGN KEY (trace_id) REFERENCES traces(trace_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                project     TEXT NOT NULL,
                name        TEXT NOT NULL,
                condition   TEXT NOT NULL,
                threshold   REAL NOT NULL,
                enabled     INTEGER DEFAULT 1,
                created_at  REAL
            )
        """)
        # Indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_traces_project    ON traces(project)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_traces_status     ON traces(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_traces_start      ON traces(start_time)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_spans_trace       ON spans(trace_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_spans_kind        ON spans(kind)")
        await db.commit()


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()
