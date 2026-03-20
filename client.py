"""
LensClient — Initializes AgentixLens and manages trace export.
"""

import os
import uuid
import asyncio
import threading
import logging
from typing import Optional
from .exporter import TraceExporter
from .store import TraceStore

logger = logging.getLogger("agentixlens")


class LensClient:
    """
    Global singleton client for AgentixLens.

    Usage:
        from agentixlens import lens
        lens.init(project="my-agent", endpoint="http://localhost:4317")
    """

    def __init__(self):
        self.project: Optional[str] = None
        self.endpoint: Optional[str] = None
        self.api_key: Optional[str] = None
        self.enabled: bool = False
        self.debug: bool = False
        self._exporter: Optional[TraceExporter] = None
        self._store: Optional[TraceStore] = None
        self._lock = threading.Lock()

    def init(
        self,
        project: str,
        endpoint: str = "http://localhost:4317",
        api_key: Optional[str] = None,
        debug: bool = False,
        local: bool = False,
    ) -> "LensClient":
        """
        Initialize AgentixLens.

        Args:
            project:  Your project/agent name shown in the dashboard.
            endpoint: AgentixLens backend URL (default: localhost for self-hosted).
            api_key:  API key for cloud tier (optional for self-hosted).
            debug:    Print trace info to console as well.
            local:    Store traces locally in SQLite only (no network export).

        Returns:
            self — chainable
        """
        with self._lock:
            self.project = project
            self.endpoint = os.environ.get("AGENTIXLENS_ENDPOINT", endpoint)
            self.api_key = api_key or os.environ.get("AGENTIXLENS_API_KEY")
            self.debug = debug
            self.enabled = True

            self._store = TraceStore(project=project)
            self._exporter = TraceExporter(
                endpoint=self.endpoint,
                api_key=self.api_key,
                local_only=local,
                store=self._store,
            )

        if debug:
            logging.basicConfig(level=logging.DEBUG)
            logger.debug(f"[AgentixLens] initialized project='{project}' endpoint='{self.endpoint}'")
        else:
            logging.basicConfig(level=logging.INFO)

        return self

    def flush(self):
        """Force-flush any buffered spans to the backend."""
        if self._exporter:
            self._exporter.flush()

    def shutdown(self):
        """Gracefully shut down — flush and close connections."""
        if self._exporter:
            self._exporter.flush()
            self._exporter.shutdown()
        self.enabled = False

    def get_store(self) -> Optional["TraceStore"]:
        return self._store

    def get_exporter(self) -> Optional["TraceExporter"]:
        return self._exporter

    def is_ready(self) -> bool:
        return self.enabled and self._exporter is not None

    def __repr__(self):
        return f"<LensClient project={self.project!r} enabled={self.enabled}>"
