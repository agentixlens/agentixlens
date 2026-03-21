"""
routers/ingest.py — POST /v1/ingest
Receives trace batches from the AgentixLens Python SDK.
"""

import json
import time
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
import aiosqlite

from db.database import get_db
from models.schemas import IngestRequest, IngestResponse

router = APIRouter()
logger = logging.getLogger("agentixlens.ingest")


@router.post("/ingest", response_model=IngestResponse)
async def ingest_traces(
    body: IngestRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Receive a batch of traces from the AgentixLens SDK.
    Saves traces and all their child spans to SQLite.
    """
    accepted = 0
    rejected = 0

    for trace in body.traces:
        try:
            # Upsert trace row
            await db.execute("""
                INSERT OR REPLACE INTO traces
                (trace_id, project, agent_name, status, start_time, end_time,
                 duration_ms, total_tokens, cost_usd, llm_calls, tool_calls,
                 payload, sdk_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trace.trace_id,
                trace.project,
                trace.agent_name,
                trace.status,
                trace.start_time,
                trace.end_time,
                trace.duration_ms,
                trace.total_tokens,
                trace.total_cost_usd,
                trace.llm_calls,
                trace.tool_calls,
                trace.model_dump_json(),
                body.sdk_version,
                time.time(),
            ))

            # Upsert each span
            for span in trace.spans:
                await db.execute("""
                    INSERT OR REPLACE INTO spans
                    (span_id, trace_id, parent_id, name, kind, status,
                     start_time, end_time, duration_ms, error, payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    span.span_id,
                    span.trace_id,
                    span.parent_id,
                    span.name,
                    span.kind,
                    span.status,
                    span.start_time,
                    span.end_time,
                    span.duration_ms,
                    span.error,
                    json.dumps(span.model_dump()),
                ))

            accepted += 1

        except Exception as e:
            logger.error(f"Failed to ingest trace {trace.trace_id}: {e}")
            rejected += 1

    await db.commit()
    logger.info(f"Ingested {accepted} trace(s), rejected {rejected}")
    return IngestResponse(accepted=accepted, rejected=rejected)
