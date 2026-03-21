"""
Data models for AgentixLens traces and spans.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class SpanKind(str, Enum):
    AGENT   = "agent"     # Top-level agent execution
    LLM     = "llm"       # A call to a language model
    TOOL    = "tool"      # A tool / function call
    CHAIN   = "chain"     # A sub-chain or pipeline step
    MEMORY  = "memory"    # Memory read/write
    EMBED   = "embedding" # Embedding generation
    CUSTOM  = "custom"    # User-defined span


class SpanStatus(str, Enum):
    OK      = "ok"
    ERROR   = "error"
    TIMEOUT = "timeout"


@dataclass
class LLMMeta:
    """Metadata specific to LLM calls."""
    model: str = ""
    provider: str = ""                  # openai, anthropic, google, local…
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0               # estimated cost
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    finish_reason: Optional[str] = None


@dataclass
class ToolMeta:
    """Metadata specific to tool calls."""
    tool_name: str = ""
    tool_version: Optional[str] = None
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """
    A single unit of work in an agent's execution.
    Analogous to an OpenTelemetry Span.
    """
    span_id:    str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    trace_id:   str = ""
    parent_id:  Optional[str] = None
    name:       str = ""
    kind:       SpanKind = SpanKind.CUSTOM
    status:     SpanStatus = SpanStatus.OK

    start_time: float = field(default_factory=time.time)
    end_time:   Optional[float] = None

    inputs:     Dict[str, Any] = field(default_factory=dict)
    outputs:    Dict[str, Any] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)
    events:     List[Dict]     = field(default_factory=list)

    error:      Optional[str] = None
    error_type: Optional[str] = None

    llm_meta:   Optional[LLMMeta]  = None
    tool_meta:  Optional[ToolMeta] = None

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time is not None:
            return round((self.end_time - self.start_time) * 1000, 2)
        return None

    def end(self, status: SpanStatus = SpanStatus.OK):
        self.end_time = time.time()
        self.status = status

    def add_event(self, name: str, attributes: Dict[str, Any] = None):
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id":        self.span_id,
            "trace_id":       self.trace_id,
            "parent_id":      self.parent_id,
            "name":           self.name,
            "kind":           self.kind.value,
            "status":         self.status.value,
            "start_time":     self.start_time,
            "end_time":       self.end_time,
            "duration_ms":    self.duration_ms,
            "inputs":         self.inputs,
            "outputs":        self.outputs,
            "attributes":     self.attributes,
            "events":         self.events,
            "error":          self.error,
            "error_type":     self.error_type,
            "llm_meta":       vars(self.llm_meta) if self.llm_meta else None,
            "tool_meta":      vars(self.tool_meta) if self.tool_meta else None,
        }


@dataclass
class Trace:
    """
    A complete trace — the full execution of one agent run.
    Contains one root span (the agent) and N child spans.
    """
    trace_id:   str = field(default_factory=lambda: "ax_" + uuid.uuid4().hex[:10])
    project:    str = ""
    agent_name: str = ""
    run_label:  Optional[str] = None

    start_time: float = field(default_factory=time.time)
    end_time:   Optional[float] = None
    status:     SpanStatus = SpanStatus.OK

    spans:      List[Span] = field(default_factory=list)
    tags:       Dict[str, str] = field(default_factory=dict)

    # Aggregated metrics (filled on close)
    total_tokens:   int   = 0
    total_cost_usd: float = 0.0
    llm_calls:      int   = 0
    tool_calls:     int   = 0

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time:
            return round((self.end_time - self.start_time) * 1000, 2)
        return None

    def add_span(self, span: Span):
        span.trace_id = self.trace_id
        self.spans.append(span)

    def close(self):
        self.end_time = time.time()
        # Aggregate LLM metrics
        for span in self.spans:
            if span.llm_meta:
                self.total_tokens   += span.llm_meta.total_tokens
                self.total_cost_usd += span.llm_meta.cost_usd
                self.llm_calls      += 1
            if span.kind == SpanKind.TOOL:
                self.tool_calls += 1
        # Propagate error status
        errors = [s for s in self.spans if s.status == SpanStatus.ERROR]
        if errors:
            self.status = SpanStatus.ERROR

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id":       self.trace_id,
            "project":        self.project,
            "agent_name":     self.agent_name,
            "run_label":      self.run_label,
            "start_time":     self.start_time,
            "end_time":       self.end_time,
            "duration_ms":    self.duration_ms,
            "status":         self.status.value,
            "total_tokens":   self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "llm_calls":      self.llm_calls,
            "tool_calls":     self.tool_calls,
            "tags":           self.tags,
            "spans":          [s.to_dict() for s in self.spans],
        }
