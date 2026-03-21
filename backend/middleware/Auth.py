"""
middleware/auth.py — API Key authentication
Set AUTH_ENABLED=false to disable (local dev only).
"""

import os
import secrets
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

AUTH_ENABLED    = os.environ.get("AUTH_ENABLED", "true").lower() != "false"
API_SECRET_KEY  = os.environ.get("API_SECRET_KEY", "")
DASHBOARD_TOKEN = os.environ.get("DASHBOARD_TOKEN", "")

PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not AUTH_ENABLED:
            return await call_next(request)

        path = request.url.path

        if path in PUBLIC_PATHS or path.startswith("/assets"):
            return await call_next(request)

        if path in ("/dashboard", "/dashboard/") or path.startswith("/dashboard/"):
            return await call_next(request)

        # SDK ingest — requires Bearer API key
        if path == "/v1/ingest":
            if API_SECRET_KEY:
                auth_header = request.headers.get("Authorization", "")
                token = auth_header.removeprefix("Bearer ").strip()
                if not secrets.compare_digest(token, API_SECRET_KEY):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid API key."},
                    )
            return await call_next(request)

        # Dashboard API — requires dashboard token
        if DASHBOARD_TOKEN:
            token = (
                request.headers.get("X-Dashboard-Token", "")
                or request.query_params.get("token", "")
            )
            if not token or not secrets.compare_digest(token, DASHBOARD_TOKEN):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Dashboard token required."},
                )

        return await call_next(request)