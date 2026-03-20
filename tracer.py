"""
AgentixLens Tracers
-------------------
Decorators and context managers that wrap agent functions,
LLM calls, and tool calls to capture telemetry automatically.
"""

import time
import asyncio
import inspect
import logging
import functools
import traceback
from typing import Any, Callable, Dict, Optional, Type, Union

from .models import Span, Trace, SpanKind, SpanStatus, LLMMeta, ToolMeta
from .context import (
    get_current_trace, set_current_trace,
    current_span, set_current_span,
)

logger = logging.getLogger("agentixlens")


# ─────────────────────────────────────────────
# Cost estimation table (per 1M tokens, USD)
# Add/update as models change — no API needed.
# ─────────────────────────────────────────────
_COST_TABLE: Dict[str, Dict[str, float]] = {
    # model_name → {input: $/1M, output: $/1M}
    "gpt-4o":                   {"input": 5.00,  "output": 15.00},
    "gpt-4o-mini":              {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":              {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo":            {"input": 0.50,  "output": 1.50},
    "claude-3-5-sonnet":        {"input": 3.00,  "output": 15.00},
    "claude-3-opus":            {"input": 15.00, "output": 75.00},
    "claude-3-haiku":           {"input": 0.25,  "output": 1.25},
    "claude-sonnet-4":          {"input": 3.00,  "output": 15.00},
    "gemini-1.5-pro":           {"input": 3.50,  "output": 10.50},
    "gemini-1.5-flash":         {"input": 0.075, "output": 0.30},
    "llama-3.1-70b":            {"input": 0.00,  "output": 0.00},  # local/free
    "mistral-large":            {"input": 4.00,  "output": 12.00},
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost from token counts using the static price table."""
    key = next((k for k in _COST_TABLE if k in model.lower()), None)
    if not key:
        return 0.0
    prices = _COST_TABLE[key]
    return (
        (prompt_tokens    / 1_000_000) * prices["input"] +
        (completion_tokens / 1_000_000) * prices["output"]
    )


def _safe_serialize(obj: Any) -> Any:
    """Best-effort serialization of inputs/outputs for storage."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    try:
        return str(obj)[:2000]  # cap huge objects
    except Exception:
        return "<unserializable>"


# ─────────────────────────────────────────────
# @trace  — wraps an entire agent function
# ─────────────────────────────────────────────

def trace(
    name: Optional[str] = None,
    *,
    kind: SpanKind = SpanKind.AGENT,
    tags: Optional[Dict[str, str]] = None,
    capture_input: bool = True,
    capture_output: bool = True,
):
    """
    Decorator to trace an entire agent function.

    Usage:
        @trace("research-agent")
        async def run_agent(query: str) -> str:
            ...

        @trace("data-pipeline", tags={"env": "prod"})
        def sync_pipeline(data):
            ...
    """
    def decorator(fn: Callable) -> Callable:
        agent_name = name or fn.__name__

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            return await _run_traced(
                fn, args, kwargs,
                agent_name=agent_name, kind=kind,
                tags=tags or {},
                capture_input=capture_input,
                capture_output=capture_output,
                is_async=True,
            )

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            return asyncio.get_event_loop().run_until_complete(
                _run_traced(
                    fn, args, kwargs,
                    agent_name=agent_name, kind=kind,
                    tags=tags or {},
                    capture_input=capture_input,
                    capture_output=capture_output,
                    is_async=False,
                )
            ) if asyncio.get_event_loop().is_running() else _run_traced_sync(
                fn, args, kwargs,
                agent_name=agent_name, kind=kind,
                tags=tags or {},
                capture_input=capture_input,
                capture_output=capture_output,
            )

        if inspect.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    # Allow @trace without parentheses: @trace
    if callable(name):
        fn, name = name, None
        return decorator(fn)

    return decorator


async def _run_traced(fn, args, kwargs, *, agent_name, kind, tags,
                      capture_input, capture_output, is_async):
    from agentixlens import lens  # local import avoids circular

    # Create trace + root span
    trace_obj = Trace(
        project=lens.project or "default",
        agent_name=agent_name,
        tags=tags,
    )
    root_span = Span(
        name=agent_name,
        kind=kind,
        trace_id=trace_obj.trace_id,
    )

    if capture_input:
        root_span.inputs = _safe_serialize({"args": args, "kwargs": kwargs})

    trace_obj.add_span(root_span)
    set_current_trace(trace_obj)
    set_current_span(root_span)

    try:
        if is_async:
            result = await fn(*args, **kwargs)
        else:
            result = fn(*args, **kwargs)

        if capture_output:
            root_span.outputs = {"result": _safe_serialize(result)}

        root_span.end(SpanStatus.OK)
        return result

    except Exception as exc:
        root_span.status = SpanStatus.ERROR
        root_span.error = str(exc)
        root_span.error_type = type(exc).__name__
        root_span.end_time = time.time()
        root_span.add_event("exception", {
            "message": str(exc),
            "stacktrace": traceback.format_exc(),
        })
        raise

    finally:
        trace_obj.close()
        set_current_span(None)
        set_current_trace(None)

        # Export
        if lens.is_ready():
            try:
                lens.get_exporter().export(trace_obj)
            except Exception as e:
                logger.warning(f"[AgentixLens] export failed: {e}")

        if lens.debug:
            _print_trace_summary(trace_obj)


def _run_traced_sync(fn, args, kwargs, *, agent_name, kind, tags,
                     capture_input, capture_output):
    """Pure sync version for environments without an event loop."""
    from agentixlens import lens

    trace_obj = Trace(
        project=lens.project or "default",
        agent_name=agent_name,
        tags=tags,
    )
    root_span = Span(name=agent_name, kind=kind, trace_id=trace_obj.trace_id)

    if capture_input:
        root_span.inputs = _safe_serialize({"args": args, "kwargs": kwargs})

    trace_obj.add_span(root_span)
    set_current_trace(trace_obj)
    set_current_span(root_span)

    try:
        result = fn(*args, **kwargs)
        if capture_output:
            root_span.outputs = {"result": _safe_serialize(result)}
        root_span.end(SpanStatus.OK)
        return result
    except Exception as exc:
        root_span.status = SpanStatus.ERROR
        root_span.error = str(exc)
        root_span.error_type = type(exc).__name__
        root_span.end_time = time.time()
        raise
    finally:
        trace_obj.close()
        set_current_span(None)
        set_current_trace(None)
        if lens.is_ready():
            try:
                lens.get_exporter().export(trace_obj)
            except Exception as e:
                logger.warning(f"[AgentixLens] export failed: {e}")
        if lens.debug:
            _print_trace_summary(trace_obj)


# ─────────────────────────────────────────────
# @trace_llm  — wraps a single LLM call
# ─────────────────────────────────────────────

def trace_llm(
    model: str,
    *,
    provider: str = "",
    capture_prompts: bool = True,
):
    """
    Decorator to trace a single LLM API call.

    Usage:
        @trace_llm(model="claude-3-5-sonnet", provider="anthropic")
        async def call_claude(messages):
            response = await anthropic_client.messages.create(...)
            return response
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            return await _run_llm_span(fn, args, kwargs,
                                       model=model, provider=provider,
                                       capture_prompts=capture_prompts,
                                       is_async=True)

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            return _run_llm_span_sync(fn, args, kwargs,
                                      model=model, provider=provider,
                                      capture_prompts=capture_prompts)

        return async_wrapper if inspect.iscoroutinefunction(fn) else sync_wrapper

    return decorator


async def _run_llm_span(fn, args, kwargs, *, model, provider, capture_prompts, is_async):
    parent_span = current_span()
    parent_trace = get_current_trace()

    span = Span(
        name=f"llm:{model}",
        kind=SpanKind.LLM,
        parent_id=parent_span.span_id if parent_span else None,
        trace_id=parent_trace.trace_id if parent_trace else "",
    )

    if capture_prompts and kwargs.get("messages"):
        span.inputs = {"messages": _safe_serialize(kwargs["messages"])}

    set_current_span(span)

    try:
        result = await fn(*args, **kwargs) if is_async else fn(*args, **kwargs)

        # Try to extract token info from common response shapes
        meta = _extract_llm_meta(result, model=model, provider=provider)
        span.llm_meta = meta
        span.outputs = {"content": _safe_serialize(_extract_content(result))}
        span.end(SpanStatus.OK)
        return result

    except Exception as exc:
        span.status = SpanStatus.ERROR
        span.error = str(exc)
        span.end_time = time.time()
        raise
    finally:
        set_current_span(parent_span)
        if parent_trace:
            parent_trace.add_span(span)


def _run_llm_span_sync(fn, args, kwargs, *, model, provider, capture_prompts):
    parent_span = current_span()
    parent_trace = get_current_trace()

    span = Span(
        name=f"llm:{model}",
        kind=SpanKind.LLM,
        parent_id=parent_span.span_id if parent_span else None,
        trace_id=parent_trace.trace_id if parent_trace else "",
    )

    set_current_span(span)
    try:
        result = fn(*args, **kwargs)
        meta = _extract_llm_meta(result, model=model, provider=provider)
        span.llm_meta = meta
        span.end(SpanStatus.OK)
        return result
    except Exception as exc:
        span.status = SpanStatus.ERROR
        span.error = str(exc)
        span.end_time = time.time()
        raise
    finally:
        set_current_span(parent_span)
        if parent_trace:
            parent_trace.add_span(span)


def _extract_llm_meta(response: Any, *, model: str, provider: str) -> LLMMeta:
    """Parse token counts from common SDK response shapes (OpenAI, Anthropic, etc.)."""
    prompt_tokens = 0
    completion_tokens = 0
    finish_reason = None

    try:
        # OpenAI / OpenAI-compatible
        if hasattr(response, "usage"):
            usage = response.usage
            prompt_tokens     = getattr(usage, "prompt_tokens", 0) or getattr(usage, "input_tokens", 0)
            completion_tokens = getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0)
        # Anthropic SDK
        if hasattr(response, "stop_reason"):
            finish_reason = response.stop_reason
        elif hasattr(response, "choices"):
            finish_reason = response.choices[0].finish_reason if response.choices else None
    except Exception:
        pass

    cost = _estimate_cost(model, prompt_tokens, completion_tokens)

    return LLMMeta(
        model=model,
        provider=provider,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        cost_usd=cost,
        finish_reason=finish_reason,
    )


def _extract_content(response: Any) -> Any:
    """Extract text content from common SDK response shapes."""
    try:
        # Anthropic
        if hasattr(response, "content") and isinstance(response.content, list):
            return response.content[0].text if response.content else ""
        # OpenAI
        if hasattr(response, "choices"):
            return response.choices[0].message.content if response.choices else ""
    except Exception:
        pass
    return str(response)[:500]


# ─────────────────────────────────────────────
# @trace_tool  — wraps a tool/function call
# ─────────────────────────────────────────────

def trace_tool(
    name: Optional[str] = None,
    *,
    version: Optional[str] = None,
    capture_args: bool = True,
    capture_result: bool = True,
):
    """
    Decorator to trace a tool call within an agent.

    Usage:
        @trace_tool("web_search")
        async def search(query: str) -> list:
            ...
    """
    def decorator(fn: Callable) -> Callable:
        tool_name = name or fn.__name__

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            return await _run_tool_span(fn, args, kwargs,
                                        tool_name=tool_name, version=version,
                                        capture_args=capture_args,
                                        capture_result=capture_result,
                                        is_async=True)

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            return _run_tool_span_sync(fn, args, kwargs,
                                       tool_name=tool_name, version=version,
                                       capture_args=capture_args,
                                       capture_result=capture_result)

        return async_wrapper if inspect.iscoroutinefunction(fn) else sync_wrapper

    if callable(name):
        fn, name = name, None
        return decorator(fn)

    return decorator


async def _run_tool_span(fn, args, kwargs, *, tool_name, version,
                         capture_args, capture_result, is_async):
    parent_span = current_span()
    parent_trace = get_current_trace()

    span = Span(
        name=f"tool:{tool_name}",
        kind=SpanKind.TOOL,
        parent_id=parent_span.span_id if parent_span else None,
        trace_id=parent_trace.trace_id if parent_trace else "",
        tool_meta=ToolMeta(tool_name=tool_name, tool_version=version),
    )

    if capture_args:
        span.inputs = _safe_serialize({"args": args, "kwargs": kwargs})
        if span.tool_meta:
            span.tool_meta.args = kwargs

    set_current_span(span)
    try:
        result = await fn(*args, **kwargs) if is_async else fn(*args, **kwargs)
        if capture_result:
            span.outputs = {"result": _safe_serialize(result)}
        span.end(SpanStatus.OK)
        return result
    except Exception as exc:
        span.status = SpanStatus.ERROR
        span.error = str(exc)
        span.end_time = time.time()
        raise
    finally:
        set_current_span(parent_span)
        if parent_trace:
            parent_trace.add_span(span)


def _run_tool_span_sync(fn, args, kwargs, *, tool_name, version,
                        capture_args, capture_result):
    parent_span = current_span()
    parent_trace = get_current_trace()

    span = Span(
        name=f"tool:{tool_name}",
        kind=SpanKind.TOOL,
        parent_id=parent_span.span_id if parent_span else None,
        trace_id=parent_trace.trace_id if parent_trace else "",
        tool_meta=ToolMeta(tool_name=tool_name, tool_version=version),
    )
    set_current_span(span)
    try:
        result = fn(*args, **kwargs)
        if capture_result:
            span.outputs = {"result": _safe_serialize(result)}
        span.end(SpanStatus.OK)
        return result
    except Exception as exc:
        span.status = SpanStatus.ERROR
        span.error = str(exc)
        span.end_time = time.time()
        raise
    finally:
        set_current_span(parent_span)
        if parent_trace:
            parent_trace.add_span(span)


# ─────────────────────────────────────────────
# Debug printer
# ─────────────────────────────────────────────

def _print_trace_summary(trace_obj: Trace):
    print(f"\n{'─'*60}")
    print(f"[AgentixLens] Trace: {trace_obj.trace_id}")
    print(f"  Agent   : {trace_obj.agent_name}")
    print(f"  Status  : {trace_obj.status.value}")
    print(f"  Duration: {trace_obj.duration_ms}ms")
    print(f"  LLM calls: {trace_obj.llm_calls}  |  Tool calls: {trace_obj.tool_calls}")
    print(f"  Tokens: {trace_obj.total_tokens}  |  Cost: ${trace_obj.total_cost_usd:.6f}")
    for span in trace_obj.spans:
        status_icon = "✓" if span.status == SpanStatus.OK else "✗"
        print(f"  {status_icon} [{span.kind.value:8}] {span.name:<35} {span.duration_ms}ms")
    print(f"{'─'*60}\n")
