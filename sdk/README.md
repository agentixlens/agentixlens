
# 🔭 AgentixLens

**AI Agent Observability — trace, monitor, and debug your AI agents in real-time.**
[![PyPI version](https://badge.fury.io/py/agentixlens.svg)](https://pypi.org/project/agentixlens)
[![Downloads](https://static.pepy.tech/badge/agentixlens)](https://pepy.tech/project/agentixlens)
[![License: MIT](https://img.shields.io/badge/License-MIT-cyan.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com)

[🌐 Website](https://agentixlens.com) · [📊 Dashboard](https://agentixlens.com/dashboard) · [🐦 Twitter](https://x.com/agentixlens)

---

## What is AgentixLens?

AgentixLens gives you a transparent window into every decision your AI agents make.

- **Visual Trace Explorer** — every LLM call, tool use, and decision branch in a waterfall
- **Cost & Token Tracking** — per-run, per-model, per-tool granularity
- **Latency Heatmaps** — p50/p95/p99 across your entire agent fleet
- **Failure Capture & Replay** — reproduce any failed run with full context
- **Model-Agnostic** — works with any LLM, zero vendor lock-in

---

## Repo Structure

```
agentixlens/
├── index.html          # Landing page (deployed to Netlify)
├── dashboard.html      # Dashboard UI (deployed to Netlify)
├── netlify.toml        # Netlify config
├── backend/            # FastAPI backend (deploy to Railway/Render/Fly)
│   ├── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example    # Copy to .env and fill in values
│   ├── db/
│   ├── models/
│   ├── routers/
│   └── middleware/
└── sdk/                # Python SDK (publish to PyPI)
    ├── agentixlens/
    ├── examples/
    └── tests/
```

---

## Quick Start

### 1. Install the SDK

```bash
pip install agentixlens
```

### 2. Instrument your agent

```python
from agentixlens import lens, trace

lens.init(project="my-agent")

@trace("research-agent")
async def run_agent(query: str) -> str:
    # Your existing agent code — unchanged
    ...
```

### 3. Run the backend locally

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # Fill in your values
uvicorn main:app --reload --port 4317
```

### 4. Open the dashboard

Open `dashboard.html` in your browser — it connects to `http://localhost:4317` automatically.

---

## Deployment

### Frontend (Netlify) — free

1. Push this repo to GitHub
2. Connect to [Netlify](https://netlify.com) → **Import from Git**
3. Set **Publish directory** to `.` (root)
4. Set **Build command** to *(empty)*
5. Deploy — `index.html` and `dashboard.html` go live instantly

### Backend (Railway) — one click

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template)

Or manually:
```bash
cd backend
railway login
railway up
```

Set these environment variables on Railway:
```
ENV=production
AUTH_ENABLED=true
API_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">
DASHBOARD_TOKEN=<generate same way>
ALLOWED_ORIGINS=https://agentixlens.com
```

### Backend (Docker)

```bash
cd backend
docker build -t agentixlens-backend .
docker run -p 4317:4317 \
  -e API_SECRET_KEY=your-key \
  -e DASHBOARD_TOKEN=your-token \
  -v agentixlens-data:/data \
  agentixlens-backend
```

---

## SDK Reference

```python
from agentixlens import lens, trace, trace_llm, trace_tool, current_span

# Initialize
lens.init(
    project="my-agent",
    endpoint="https://your-backend.railway.app",
    api_key="ax_...",
    debug=True,
)

# Trace entire agent run
@trace("my-agent", tags={"env": "prod"})
async def run_agent(query: str): ...

# Trace individual LLM call
@trace_llm(model="claude-3-5-sonnet", provider="anthropic")
async def call_llm(messages): ...

# Trace tool calls
@trace_tool("web_search")
async def search(query: str): ...

# Add metadata from inside any function
current_span().set_attribute("user_id", user.id)
```

### LangChain Integration

```python
from agentixlens.integrations.langchain import AgentixLensCallback

llm = ChatOpenAI(callbacks=[AgentixLensCallback()])
```

---

## Environment Variables

See [`backend/.env.example`](backend/.env.example) for all options.

| Variable | Required | Description |
|---|---|---|
| `API_SECRET_KEY` | Yes (prod) | SDK authentication key |
| `DASHBOARD_TOKEN` | Yes (prod) | Dashboard UI access token |
| `ENV` | No | `development` or `production` |
| `AGENTIXLENS_DB` | No | SQLite path (default: `~/.agentixlens/server.db`) |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins |
| `AUTH_ENABLED` | No | Set `false` for local dev |

---

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Run tests: `cd sdk && pytest tests/ -v`
4. Commit and push
5. Open a Pull Request

---

## License

MIT © 2025 AgentixLens

---

*Built for developers who are tired of flying blind with AI agents.*
