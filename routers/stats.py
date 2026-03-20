"""
routers/stats.py — /v1/stats, /v1/timeseries, /v1/latency
Powers the metrics cards and charts in the dashboard.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
import aiosqlite
import time

from db.database import get_db
from models.schemas import StatsResponse, TimeseriesPoint, LatencyPercentiles

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    project: Optional[str] = Query(None),
    since:   Optional[float] = Query(None, description="Unix timestamp — only count runs after this"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Aggregate metrics for the dashboard summary cards."""
    where  = "WHERE 1=1"
    params = []
    if project:
        where += " AND project=?"; params.append(project)
    if since:
        where += " AND start_time>=?"; params.append(since)

    async with db.execute(f"""
        SELECT
            COUNT(*)                                              AS total_runs,
            SUM(CASE WHEN status='ok'    THEN 1 ELSE 0 END)      AS ok_count,
            SUM(CASE WHEN status='error' THEN 1 ELSE 0 END)      AS error_count,
            AVG(duration_ms)                                      AS avg_latency_ms,
            SUM(total_tokens)                                     AS total_tokens,
            SUM(cost_usd)                                         AS total_cost_usd,
            SUM(llm_calls)                                        AS total_llm_calls,
            SUM(tool_calls)                                       AS total_tool_calls
        FROM traces {where}
    """, params) as cur:
        row = await cur.fetchone()

    total = row["total_runs"] or 1
    return StatsResponse(
        total_runs      = row["total_runs"] or 0,
        ok_count        = row["ok_count"] or 0,
        error_count     = row["error_count"] or 0,
        success_rate    = round((row["ok_count"] or 0) / total * 100, 2),
        avg_latency_ms  = round(row["avg_latency_ms"], 2) if row["avg_latency_ms"] else None,
        total_tokens    = row["total_tokens"] or 0,
        total_cost_usd  = round(row["total_cost_usd"] or 0, 6),
        total_llm_calls = row["total_llm_calls"] or 0,
        total_tool_calls= row["total_tool_calls"] or 0,
    )


@router.get("/timeseries")
async def get_timeseries(
    project:  Optional[str]   = Query(None),
    interval: str             = Query("hour", regex="^(minute|hour|day)$"),
    since:    Optional[float] = Query(None),
    db: aiosqlite.Connection  = Depends(get_db),
):
    """
    Bucketed run counts + avg latency for the time-series chart.
    interval: minute | hour | day
    """
    bucket_size = {"minute": 60, "hour": 3600, "day": 86400}[interval]
    since = since or (time.time() - bucket_size * 48)  # default: last 48 buckets

    where  = "WHERE start_time >= ?"
    params = [since]
    if project:
        where += " AND project=?"; params.append(project)

    async with db.execute(f"""
        SELECT
            CAST(start_time / {bucket_size} AS INTEGER) * {bucket_size}  AS bucket,
            COUNT(*)                                                        AS runs,
            SUM(CASE WHEN status='error' THEN 1 ELSE 0 END)                AS errors,
            AVG(duration_ms)                                                AS avg_latency_ms,
            SUM(cost_usd)                                                   AS total_cost_usd
        FROM traces {where}
        GROUP BY bucket
        ORDER BY bucket
    """, params) as cur:
        rows = await cur.fetchall()

    import datetime
    result = []
    for r in rows:
        dt = datetime.datetime.utcfromtimestamp(r["bucket"])
        result.append({
            "bucket":         dt.isoformat() + "Z",
            "runs":           r["runs"],
            "errors":         r["errors"] or 0,
            "avg_latency_ms": round(r["avg_latency_ms"] or 0, 2),
            "total_cost_usd": round(r["total_cost_usd"] or 0, 6),
        })
    return result


@router.get("/latency/percentiles", response_model=LatencyPercentiles)
async def get_latency_percentiles(
    project: Optional[str] = Query(None),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Return p50/p95/p99 latency for the latency heatmap panel."""
    where  = "WHERE duration_ms IS NOT NULL"
    params = []
    if project:
        where += " AND project=?"; params.append(project)

    async with db.execute(
        f"SELECT duration_ms FROM traces {where} ORDER BY duration_ms", params
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        return LatencyPercentiles(p50=0, p95=0, p99=0, min=0, max=0)

    vals = [r["duration_ms"] for r in rows]
    n    = len(vals)

    def pct(p):
        idx = max(0, int(n * p / 100) - 1)
        return round(vals[idx], 2)

    return LatencyPercentiles(
        p50=pct(50), p95=pct(95), p99=pct(99),
        min=round(vals[0], 2), max=round(vals[-1], 2),
    )


@router.get("/cost/by-model")
async def get_cost_by_model(
    project: Optional[str] = Query(None),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Cost breakdown by LLM model — for the cost breakdown chart."""
    where  = "WHERE kind='llm'"
    params = []
    if project:
        where += " AND trace_id IN (SELECT trace_id FROM traces WHERE project=?)"
        params.append(project)

    async with db.execute(f"""
        SELECT
            json_extract(payload, '$.llm_meta.model') AS model,
            SUM(json_extract(payload, '$.llm_meta.cost_usd'))         AS total_cost,
            SUM(json_extract(payload, '$.llm_meta.total_tokens'))      AS total_tokens,
            COUNT(*)                                                    AS call_count
        FROM spans {where}
        GROUP BY model
        ORDER BY total_cost DESC
    """, params) as cur:
        rows = await cur.fetchall()

    return [
        {
            "model":        r["model"] or "unknown",
            "total_cost":   round(r["total_cost"] or 0, 6),
            "total_tokens": r["total_tokens"] or 0,
            "call_count":   r["call_count"],
        }
        for r in rows
    ]
