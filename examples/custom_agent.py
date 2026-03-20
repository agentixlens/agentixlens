"""
examples/custom_agent.py
─────────────────────────
Full example: a custom research agent using AgentixLens @trace,
@trace_llm, and @trace_tool decorators.

Run:
    python examples/custom_agent.py

Requirements: none beyond agentixlens itself.
(Uses mock LLM/tool responses so no API key needed.)
"""

import asyncio
from agentixlens import lens, trace, trace_llm, trace_tool, current_span


# ── Initialize AgentixLens ────────────────────────────────────
lens.init(
    project="research-agent",
    endpoint="http://localhost:4317",  # self-hosted backend
    debug=True,                        # print trace summary to console
    local=True,                        # store locally (no network needed for demo)
)


# ── Mock LLM call (swap with real SDK in production) ──────────

class MockLLMResponse:
    """Simulates an OpenAI-compatible response object."""
    class Usage:
        prompt_tokens = 280
        completion_tokens = 145
        total_tokens = 425
    usage = Usage()
    class Choice:
        class Message:
            content = "I'll search for recent AI papers and summarize the key findings."
        message = Message()
        finish_reason = "stop"
    choices = [Choice()]


@trace_llm(model="claude-3-5-sonnet", provider="anthropic")
async def call_llm(messages: list, system: str = "") -> MockLLMResponse:
    """Wrapping an LLM call — AgentixLens captures tokens & cost."""
    await asyncio.sleep(0.05)  # simulate network latency
    return MockLLMResponse()


# ── Tool definitions ──────────────────────────────────────────

@trace_tool("web_search")
async def web_search(query: str) -> list:
    """Simulated web search tool."""
    await asyncio.sleep(0.03)
    return [
        {"title": "Attention Is All You Need", "url": "https://arxiv.org/abs/1706.03762"},
        {"title": "GPT-4 Technical Report", "url": "https://arxiv.org/abs/2303.08774"},
    ]


@trace_tool("summarize_page")
async def summarize_page(url: str) -> str:
    """Simulated page summarizer."""
    await asyncio.sleep(0.02)
    return f"Summary of {url}: groundbreaking research in transformer architectures."


# ── Main agent entrypoint ─────────────────────────────────────

@trace("research-agent", tags={"env": "dev", "version": "1.0"})
async def run_research_agent(query: str) -> str:
    """
    A research agent that:
    1. Plans with an LLM
    2. Searches the web
    3. Summarizes each result
    4. Synthesizes a final answer
    """

    # Add runtime metadata to the root span
    span = current_span()
    if span:
        span.set_attribute("query_length", len(query))
        span.set_attribute("user_tier", "pro")

    # Step 1: Plan
    plan_response = await call_llm(
        messages=[{"role": "user", "content": f"Plan a research strategy for: {query}"}],
        system="You are a research planning assistant.",
    )

    # Step 2: Search
    results = await web_search(query=query)

    # Step 3: Summarize each result
    summaries = []
    for result in results:
        summary = await summarize_page(url=result["url"])
        summaries.append(summary)

    # Step 4: Synthesize
    synthesis_response = await call_llm(
        messages=[
            {"role": "user", "content": f"Synthesize these research findings: {summaries}"}
        ]
    )

    final_answer = synthesis_response.choices[0].message.content
    return f"Research complete. Found {len(results)} sources. {final_answer}"


# ── Run it ────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  AgentixLens — Research Agent Demo")
    print("=" * 60)

    result = await run_research_agent("Latest breakthroughs in AI reasoning")
    print(f"\n✓ Agent result: {result}")

    print("\n📂 Traces stored at: ~/.agentixlens/traces.db")
    print("🔭 Open AgentixLens dashboard to explore the trace.")


if __name__ == "__main__":
    asyncio.run(main())
