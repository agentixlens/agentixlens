"""
models/schemas.py — Pydantic request/response schemas
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


# ── Ingest (SDK → Backend) ────────────────────────────────────

class LLMMetaSchema(BaseModel):
    model: str = ""
    provider: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    temperature: Optional[float] = None
    finish_reason: Optional[str] = None


class ToolMetaSchema(BaseModel):
    tool_name: str = ""
    tool_version: Optional[str] = None
    args: Dict[str, Any] = Field(default_factory=dict)


class SpanSchema(BaseModel):
    span_id: str
    trace_id: str
    parent_id: Optional[str] = None
    name: str
    kind: str
    status: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    events: List[Dict] = Field(default_factory=list)
    error: Optional[str] = None
    error_type: Optional[str] = None
    llm_meta: Optional[LLMMetaSchema] = None
    tool_meta: Optional[ToolMetaSchema] = None


class TraceSchema(BaseModel):
    trace_id: str
    project: str
    agent_name: str
    run_label: Optional[str] = None
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    llm_calls: int = 0
    tool_calls: int = 0
    tags: Dict[str, str] = Field(default_factory=dict)
    spans: List[SpanSchema] = Field(default_factory=list)


class IngestRequest(BaseModel):
    traces: List[TraceSchema]
    sdk_version: str = "unknown"


class IngestResponse(BaseModel):
    accepted: int
    rejected: int
    message: str = "ok"


# ── Query responses (Backend → Dashboard) ─────────────────────

class TraceListItem(BaseModel):
    trace_id: str
    project: str
    agent_name: str
    status: str
    duration_ms: Optional[float]
    total_tokens: int
    cost_usd: float
    llm_calls: int
    tool_calls: int
    start_time: float
    end_time: Optional[float]


class TraceDetail(TraceListItem):
    spans: List[SpanSchema]
    tags: Dict[str, str]


class StatsResponse(BaseModel):
    total_runs: int
    ok_count: int
    error_count: int
    success_rate: float
    avg_latency_ms: Optional[float]
    total_tokens: int
    total_cost_usd: float
    total_llm_calls: int
    total_tool_calls: int


class TimeseriesPoint(BaseModel):
    bucket: str          # ISO timestamp bucket
    runs: int
    errors: int
    avg_latency_ms: float
    total_cost_usd: float


class LatencyPercentiles(BaseModel):
    p50: float
    p95: float
    p99: float
    min: float
    max: float


class AlertSchema(BaseModel):
    id: Optional[int] = None
    project: str
    name: str
    condition: str       # "latency_gt" | "cost_gt" | "error_rate_gt"
    threshold: float
    enabled: bool = True
