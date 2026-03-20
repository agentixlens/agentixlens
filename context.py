"""
Context management for AgentixLens.
Maintains current trace/span in both thread-local and async-local contexts.
"""

import threading
from contextvars import ContextVar
from typing import Optional
from .models import Trace, Span

# Async-safe context vars (work in both sync and async code)
_current_trace: ContextVar[Optional[Trace]] = ContextVar("_current_trace", default=None)
_current_span:  ContextVar[Optional[Span]]  = ContextVar("_current_span",  default=None)

# Thread-local fallback for pure sync usage
_thread_local = threading.local()


def set_current_trace(trace: Optional[Trace]) -> None:
    _current_trace.set(trace)
    _thread_local.trace = trace


def get_current_trace() -> Optional[Trace]:
    t = _current_trace.get()
    if t is None:
        t = getattr(_thread_local, "trace", None)
    return t


def set_current_span(span: Optional[Span]) -> None:
    _current_span.set(span)
    _thread_local.span = span


def current_span() -> Optional[Span]:
    """
    Returns the currently active span, if any.
    Useful for adding attributes mid-function:

        from agentixlens import current_span
        current_span().set_attribute("user_id", user.id)
    """
    s = _current_span.get()
    if s is None:
        s = getattr(_thread_local, "span", None)
    return s
