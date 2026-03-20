"""
TraceExporter — ships completed traces to the AgentixLens backend
(or stores locally if network is unavailable).
"""

import json
import logging
import queue
import threading
import time
import urllib.request
import urllib.error
from typing import Optional
from .models import Trace
from .store import TraceStore

logger = logging.getLogger("agentixlens")

_BATCH_SIZE = 20
_FLUSH_INTERVAL = 5.0  # seconds


class TraceExporter:
    """
    Background-thread exporter: batches completed traces and POSTs
    them to the AgentixLens ingest endpoint.

    Falls back to local-only (SQLite) when the network is unavailable.
    Retries pending traces on reconnect automatically.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: Optional[str],
        local_only: bool,
        store: TraceStore,
    ):
        self.endpoint = endpoint.rstrip("/") + "/v1/ingest"
        self.api_key = api_key
        self.local_only = local_only
        self.store = store

        self._queue: queue.Queue = queue.Queue(maxsize=5_000)
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True, name="agentixlens-exporter")
        self._worker.start()

    # ── Public API ──────────────────────────────────────────

    def export(self, trace: Trace):
        """Enqueue a trace for async export. Non-blocking."""
        # Always save locally first
        self.store.save(trace)
        if not self.local_only:
            try:
                self._queue.put_nowait(trace.to_dict())
            except queue.Full:
                logger.warning("[AgentixLens] export queue full, trace dropped from network export")

    def flush(self, timeout: float = 10.0):
        """Block until the queue is empty or timeout is reached."""
        deadline = time.time() + timeout
        while not self._queue.empty() and time.time() < deadline:
            time.sleep(0.1)

    def shutdown(self):
        """Signal the background worker to stop and wait for it."""
        self._stop_event.set()
        self._worker.join(timeout=15)

    # ── Background worker ────────────────────────────────────

    def _run(self):
        batch = []
        last_flush = time.time()

        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.5)
                batch.append(item)
            except queue.Empty:
                pass

            should_flush = (
                len(batch) >= _BATCH_SIZE or
                (batch and time.time() - last_flush >= _FLUSH_INTERVAL)
            )

            if should_flush:
                self._send_batch(batch)
                batch = []
                last_flush = time.time()

        # Drain remaining on shutdown
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if batch:
            self._send_batch(batch)

    def _send_batch(self, batch: list):
        if not batch:
            return

        payload = json.dumps({
            "traces": batch,
            "sdk_version": "0.1.0",
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "agentixlens-python/0.1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            req = urllib.request.Request(
                self.endpoint,
                data=payload,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 202):
                    for t in batch:
                        self.store.mark_exported(t["trace_id"])
                    logger.debug(f"[AgentixLens] exported {len(batch)} trace(s)")
                else:
                    logger.warning(f"[AgentixLens] backend returned {resp.status}")

        except urllib.error.URLError as e:
            logger.warning(f"[AgentixLens] network error, traces saved locally: {e.reason}")
        except Exception as e:
            logger.error(f"[AgentixLens] unexpected export error: {e}")

    def retry_pending(self):
        """
        Retry any locally-stored traces that weren't exported yet.
        Call this on reconnect or app restart.
        """
        pending = self.store.get_unexported(limit=200)
        if pending:
            logger.info(f"[AgentixLens] retrying {len(pending)} pending trace(s)")
            self._send_batch(pending)
