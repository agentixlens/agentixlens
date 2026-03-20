# 🔭 AgentixLens

**AI Agent Observability — trace, monitor, and debug your AI agents in real-time.**

[![PyPI version](https://badge.fury.io/py/agentixlens.svg)](https://badge.fury.io/py/agentixlens)
[![License: MIT](https://img.shields.io/badge/License-MIT-cyan.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)

[Website](https://agentixlens.com) · [Docs](https://docs.agentixlens.com) · [Dashboard](https://app.agentixlens.com)

---

## What is AgentixLens?

AgentixLens gives you a transparent window into every decision your AI agents make.

- **Visual Trace Explorer** — see every LLM call, tool use, and decision branch
- **Cost & Token Tracking** — per-run, per-model, per-tool granularity
- **Latency Heatmaps** — find bottlenecks before users do
- **Failure Capture & Replay** — reproduce any failed run with full context
- **Zero paid dependencies** — works with any LLM, model-agnostic, open-source SDK

---

## Install

```bash
pip install agentixlens
```

With LangChain support:
```bash
pip install agentixlens[langchain]
```

---

## Quickstart

### Custom agent (2 lines)

```python
from agentixlens import lens, trace

lens.init(project="my-agent")

@trace("research-agent")
async def run_agent(query: str) -> str:
    # your existing agent code — unchanged
    plan   = await llm.call(query)
    result = await tool_search(plan)
    answer = await llm.summarize(result)
    return answer
```

### Trace individual LLM calls

```python
from agentixlens import trace_llm

@trace_llm(model="claude-3-5-sonnet", provider="anthropic")
async def call_claude(messages: list):
    return await anthropic_client.messages.create(
        model="claude-3-5-sonnet-20241022",
        messages=messages,
        max_tokens=1000,
    )
```

### Trace tool calls

```python
from agentixlens import trace_tool

@trace_tool("web_search")
async def search(query: str) -> list:
    return await my_search_api(query)
```

### Add metadata mid-function

```python
from agentixlens import current_span

@trace("my-agent")
async def agent(user_id: str):
    current_span().set_attribute("user_id", user_id)
    current_span().set_attribute("tier", "pro")
    ...
```

---

## LangChain Integration

Zero changes to your existing LangChain code:

```python
from agentixlens import lens
from agentixlens.integrations.langchain import AgentixLensCallback

lens.init(project="langchain-agent")

llm   = ChatOpenAI(callbacks=[AgentixLensCallback()])
chain = LLMChain(llm=llm, prompt=..., callbacks=[AgentixLensCallback()])
```

---

## Supported Frameworks

| Framework   | Support       |
|-------------|---------------|
| Custom      | ✅ Native      |
| LangChain   | ✅ Callback    |
| AutoGen     | 🔜 v0.2        |
| CrewAI      | 🔜 v0.2        |
| LlamaIndex  | 🔜 v0.2        |

---

## Supported Models (cost estimation)

Works with **any** LLM. Built-in cost estimation for:

- OpenAI: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo
- Anthropic: claude-3-5-sonnet, claude-3-opus, claude-3-haiku
- Google: gemini-1.5-pro, gemini-1.5-flash
- Local: llama-3.1, mistral (cost = $0)

---

## Self-Hosting

Run the AgentixLens backend locally:

```bash
docker run -p 4317:4317 -p 3000:3000 agentixlens/server
```

Then open `http://localhost:3000` for the dashboard.

---

## Configuration

```python
lens.init(
    project   = "my-agent",           # shown in dashboard
    endpoint  = "http://localhost:4317",  # backend URL
    api_key   = "ax_...",             # cloud tier only
    debug     = True,                 # print trace to console
    local     = True,                 # SQLite only, no network
)
```

Or via environment variables:
```bash
AGENTIXLENS_ENDPOINT=http://localhost:4317
AGENTIXLENS_API_KEY=ax_your_key
```

Traces are always saved locally at `~/.agentixlens/traces.db` — 
even if the network is unavailable, nothing is lost.

---

## License

MIT © 2025 AgentixLens
