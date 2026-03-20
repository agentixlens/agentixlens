"""
routers/traces.py — GET /v1/traces  &  GET /v1/traces/{trace_id}
"""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
import aiosqlite

from db.database import get_db
from models.schemas import TraceListItem, TraceDetail, SpanSchema

router = APIRouter()


@router.get("/traces", response_model=List[TraceListItem])
async def list_traces(
    project:    Optional[str] = Query(None),
    status:     Optional[str] = Query(None),
    agent_name: Optional[str] = Query(None),
    limit:      int = Query(50, ge=1, le=500),
    offset:     int = Query(0, ge=0),
    db: aiosqlite.Connection = Depends(get_db),
):
    """List traces with optional filters. Powers the main trace table."""
    sql    = "SELECT * FROM traces WHERE 1=1"
    params = []

    if project:
        sql += " AND project = ?"; params.append(project)
    if status:
        sql += " AND status = ?";  params.append(status)
    if agent_name:
        sql += " AND agent_name LIKE ?"; params.append(f"%{agent_name}%")

    sql += " ORDER BY start_time DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    async with db.execute(sql, params) as cur:
        rows = await cur.fetchall()

    return [
        TraceListItem(
            trace_id   = r["trace_id"],
            project    = r["project"],
            agent_name = r["agent_name"],
            status     = r["status"],
            duration_ms= r["duration_ms"],
            total_tokens= r["total_tokens"],
            cost_usd   = r["cost_usd"],
            llm_calls  = r["llm_calls"],
            tool_calls = r["tool_calls"],
            start_time = r["start_time"],
            end_time   = r["end_time"],
        )
        for r in rows
    ]


@router.get("/traces/{trace_id}", response_model=TraceDetail)
async def get_trace(
    trace_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get full trace with all spans. Powers the trace detail / waterfall view."""
    async with db.execute(
        "SELECT * FROM traces WHERE trace_id = ?", (trace_id,)
    ) as cur:
        row = await cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")

    # Load spans
    async with db.execute(
        "SELECT payload FROM spans WHERE trace_id = ? ORDER BY start_time", (trace_id,)
    ) as cur:
        span_rows = await cur.fetchall()

    spans = [SpanSchema(**json.loads(r["payload"])) for r in span_rows]

    # Reconstruct full trace from payload (has tags etc.)
    payload = json.loads(row["payload"])

    return TraceDetail(
        trace_id    = row["trace_id"],
        project     = row["project"],
        agent_name  = row["agent_name"],
        status      = row["status"],
        duration_ms = row["duration_ms"],
        total_tokens= row["total_tokens"],
        cost_usd    = row["cost_usd"],
        llm_calls   = row["llm_calls"],
        tool_calls  = row["tool_calls"],
        start_time  = row["start_time"],
        end_time    = row["end_time"],
        tags        = payload.get("tags", {}),
        spans       = spans,
    )


@router.get("/projects")
async def list_projects(db: aiosqlite.Connection = Depends(get_db)):
    """List all distinct projects that have sent traces."""
    async with db.execute(
        "SELECT DISTINCT project, COUNT(*) as run_count FROM traces GROUP BY project ORDER BY run_count DESC"
    ) as cur:
        rows = await cur.fetchall()
    return [{"project": r["project"], "run_count": r["run_count"]} for r in rows]
