"""
AgentixLens — AI Agent Observability SDK
https://agentixlens.com

Usage:
    from agentixlens import lens, trace

    lens.init(project="my-agent")

    @trace("my-agent")
    async def run_agent(query: str):
        ...
"""

from .client import LensClient
from .tracer import trace, trace_llm, trace_tool
from .context import current_span, get_current_trace

# Global singleton client
lens = LensClient()

__version__ = "0.1.0"
__all__ = ["lens", "trace", "trace_llm", "trace_tool", "current_span", "get_current_trace"]
