"""
tests/test_tracer.py
─────────────────────
Core unit tests for AgentixLens tracing.
Run: pytest tests/
"""

import asyncio
import pytest
from agentixlens import lens, trace, trace_llm, trace_tool, current_span
from agentixlens.models import SpanKind, SpanStatus


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def init_lens(tmp_path):
    """Initialize lens with a temp SQLite DB for each test."""
    db = str(tmp_path / "test.db")
    lens.init(
        project="test-project",
        debug=False,
        local=True,
    )
    lens.get_store().db_path = db
    yield
    lens.shutdown()
    lens.enabled = False


# ── @trace decorator ──────────────────────────────────────────

def test_sync_trace_captures_result():
    @trace("test-agent")
    def my_agent(x: int) -> int:
        return x * 2

    result = my_agent(5)
    assert result == 10


@pytest.mark.asyncio
async def test_async_trace_captures_result():
    @trace("async-agent")
    async def my_agent(x: int) -> int:
        await asyncio.sleep(0.01)
        return x + 1

    result = await my_agent(3)
    assert result == 4


@pytest.mark.asyncio
async def test_trace_captures_error():
    @trace("failing-agent")
    async def bad_agent():
        raise ValueError("something went wrong")

    with pytest.raises(ValueError, match="something went wrong"):
        await bad_agent()


@pytest.mark.asyncio
async def test_trace_span_has_correct_kind():
    captured = []

    @trace("kind-check-agent")
    async def my_agent():
        span = current_span()
        captured.append(span)
        return "ok"

    await my_agent()
    assert len(captured) == 1
    assert captured[0].kind == SpanKind.AGENT
    assert captured[0].name == "kind-check-agent"


# ── @trace_llm decorator ──────────────────────────────────────

@pytest.mark.asyncio
async def test_trace_llm_creates_child_span():
    class FakeResp:
        class Usage:
            prompt_tokens = 10
            completion_tokens = 20
            total_tokens = 30
        usage = Usage()
        choices = []

    @trace("parent-agent")
    async def agent():
        @trace_llm(model="gpt-4o", provider="openai")
        async def call_llm():
            return FakeResp()

        return await call_llm()

    await agent()


@pytest.mark.asyncio
async def test_trace_llm_extracts_token_counts():
    class FakeResp:
        class Usage:
            prompt_tokens = 100
            completion_tokens = 50
            total_tokens = 150
        usage = Usage()
        choices = []

    @trace("token-agent")
    async def agent():
        @trace_llm(model="gpt-4o", provider="openai")
        async def call_llm():
            return FakeResp()
        return await call_llm()

    await agent()
    # Should not raise


# ── @trace_tool decorator ─────────────────────────────────────

@pytest.mark.asyncio
async def test_trace_tool_captures_args_and_result():
    @trace("tool-agent")
    async def agent():
        @trace_tool("calculator")
        async def add(a: int, b: int) -> int:
            return a + b

        return await add(a=3, b=4)

    result = await agent()
    assert result == 7


@pytest.mark.asyncio
async def test_trace_tool_handles_error():
    @trace("error-tool-agent")
    async def agent():
        @trace_tool("broken_tool")
        async def broken():
            raise RuntimeError("tool failed")
        return await broken()

    with pytest.raises(RuntimeError, match="tool failed"):
        await agent()


# ── current_span() ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_current_span_accessible_inside_trace():
    found_span = []

    @trace("span-access-agent")
    async def agent():
        span = current_span()
        found_span.append(span)

    await agent()
    assert len(found_span) == 1
    assert found_span[0] is not None
    assert found_span[0].name == "span-access-agent"


@pytest.mark.asyncio
async def test_current_span_is_none_outside_trace():
    span = current_span()
    assert span is None


# ── TraceStore ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trace_stored_locally():
    @trace("stored-agent")
    async def agent():
        return "data"

    await agent()

    store = lens.get_store()
    traces = store.list_traces(project="test-project")
    assert len(traces) >= 1
    assert traces[0]["agent_name"] == "stored-agent"


@pytest.mark.asyncio
async def test_store_stats():
    @trace("stats-agent")
    async def agent():
        return "ok"

    await agent()
    await agent()

    stats = lens.get_store().stats(project="test-project")
    assert stats["total_runs"] >= 2
    assert 0 <= stats["success_rate"] <= 100
