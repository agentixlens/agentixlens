"""
AgentixLens × LangChain Integration
-------------------------------------
Auto-patches LangChain's callback system to capture traces
without any changes to your existing LangChain code.

Usage:
    from agentixlens import lens
    from agentixlens.integrations.langchain import AgentixLensCallback

    lens.init(project="my-langchain-agent")

    llm = ChatOpenAI(callbacks=[AgentixLensCallback()])
    # or globally:
    # from langchain.callbacks import set_global_handler
    # set_global_handler("agentixlens")
"""

import time
import logging
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from ..models import Span, Trace, SpanKind, SpanStatus, LLMMeta
from ..context import get_current_trace, set_current_trace, current_span, set_current_span

logger = logging.getLogger("agentixlens")


try:
    from langchain.callbacks.base import BaseCallbackHandler
    from langchain_core.outputs import LLMResult

    class AgentixLensCallback(BaseCallbackHandler):
        """
        LangChain callback handler that sends all LLM/chain/tool
        events to AgentixLens automatically.

        Attach to any LangChain component:
            llm = ChatOpenAI(callbacks=[AgentixLensCallback()])
            chain = LLMChain(..., callbacks=[AgentixLensCallback()])
        """

        def __init__(self, agent_name: str = "langchain-agent"):
            super().__init__()
            self.agent_name = agent_name
            self._spans: Dict[str, Span] = {}
            self._trace: Optional[Trace] = None

        # ── Chain events ──────────────────────────────────────

        def on_chain_start(self, serialized: Dict, inputs: Dict, *, run_id: UUID, **kw):
            from agentixlens import lens
            name = serialized.get("id", ["chain"])[-1]

            if self._trace is None:
                self._trace = Trace(
                    project=lens.project or "default",
                    agent_name=self.agent_name,
                )
                set_current_trace(self._trace)

            span = Span(
                name=f"chain:{name}",
                kind=SpanKind.CHAIN,
                trace_id=self._trace.trace_id,
                inputs={"inputs": str(inputs)[:500]},
            )
            self._trace.add_span(span)
            self._spans[str(run_id)] = span
            set_current_span(span)

        def on_chain_end(self, outputs: Dict, *, run_id: UUID, **kw):
            span = self._spans.pop(str(run_id), None)
            if span:
                span.outputs = {"outputs": str(outputs)[:500]}
                span.end(SpanStatus.OK)

        def on_chain_error(self, error: Exception, *, run_id: UUID, **kw):
            span = self._spans.pop(str(run_id), None)
            if span:
                span.error = str(error)
                span.end(SpanStatus.ERROR)

        # ── LLM events ────────────────────────────────────────

        def on_llm_start(self, serialized: Dict, prompts: List[str], *, run_id: UUID, **kw):
            model = serialized.get("kwargs", {}).get("model_name", "unknown")
            span = Span(
                name=f"llm:{model}",
                kind=SpanKind.LLM,
                trace_id=self._trace.trace_id if self._trace else "",
                inputs={"prompt": prompts[0][:1000] if prompts else ""},
            )
            if self._trace:
                self._trace.add_span(span)
            self._spans[str(run_id)] = span

        def on_llm_end(self, response: "LLMResult", *, run_id: UUID, **kw):
            span = self._spans.pop(str(run_id), None)
            if not span:
                return
            try:
                gen = response.generations[0][0] if response.generations else None
                output_text = gen.text if gen else ""
                span.outputs = {"text": output_text[:1000]}

                usage = getattr(response, "llm_output", {}) or {}
                token_usage = usage.get("token_usage", {})
                meta = LLMMeta(
                    model=span.name.replace("llm:", ""),
                    prompt_tokens=token_usage.get("prompt_tokens", 0),
                    completion_tokens=token_usage.get("completion_tokens", 0),
                    total_tokens=token_usage.get("total_tokens", 0),
                )
                span.llm_meta = meta
            except Exception as e:
                logger.debug(f"[AgentixLens] langchain on_llm_end parse error: {e}")
            span.end(SpanStatus.OK)

        def on_llm_error(self, error: Exception, *, run_id: UUID, **kw):
            span = self._spans.pop(str(run_id), None)
            if span:
                span.error = str(error)
                span.end(SpanStatus.ERROR)

        # ── Tool events ───────────────────────────────────────

        def on_tool_start(self, serialized: Dict, input_str: str, *, run_id: UUID, **kw):
            tool_name = serialized.get("name", "unknown_tool")
            span = Span(
                name=f"tool:{tool_name}",
                kind=SpanKind.TOOL,
                trace_id=self._trace.trace_id if self._trace else "",
                inputs={"input": input_str[:500]},
            )
            if self._trace:
                self._trace.add_span(span)
            self._spans[str(run_id)] = span

        def on_tool_end(self, output: str, *, run_id: UUID, **kw):
            span = self._spans.pop(str(run_id), None)
            if span:
                span.outputs = {"output": str(output)[:500]}
                span.end(SpanStatus.OK)

        def on_tool_error(self, error: Exception, *, run_id: UUID, **kw):
            span = self._spans.pop(str(run_id), None)
            if span:
                span.error = str(error)
                span.end(SpanStatus.ERROR)

        # ── Agent finish (flush trace) ─────────────────────────

        def on_agent_finish(self, finish, *, run_id: UUID, **kw):
            from agentixlens import lens
            if self._trace:
                self._trace.close()
                if lens.is_ready():
                    lens.get_exporter().export(self._trace)
                self._trace = None
                set_current_trace(None)

except ImportError:
    class AgentixLensCallback:  # type: ignore
        def __init__(self, *a, **kw):
            raise ImportError(
                "langchain is not installed. Run: pip install langchain langchain-core"
            )
