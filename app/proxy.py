import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Any

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response

from app.db import init_db, log_wire_event

load_dotenv()

CORE_UPSTREAM = os.getenv("FLAGSMITH_CORE_URL", "http://localhost:8000").rstrip("/")
ANALYTICS_UPSTREAM = os.getenv("FLAGSMITH_ANALYTICS_URL", "http://localhost:8080").rstrip("/")
CORE_PORT = int(os.getenv("PROXY_CORE_PORT", "9000"))
ANALYTICS_PORT = int(os.getenv("PROXY_ANALYTICS_PORT", "9080"))
DB_PATH = os.getenv("DB_PATH", "data/blackbox.db")

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


def build_proxy_app(upstream_url: str, listen_port: int, role: str) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(DB_PATH)
        app.state.http = httpx.AsyncClient(base_url=upstream_url, timeout=15.0)
        yield
        await app.state.http.aclose()

    app = FastAPI(title=f"BlackBox X Proxy ({role})", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "role": role,
            "listen_port": listen_port,
            "upstream": upstream_url,
            "db_path": DB_PATH,
        }

    @app.api_route(
        "/{full_path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    async def forward(request: Request, full_path: str) -> Response:
        start = time.perf_counter()
        raw_body = await request.body()
        req_path = f"/{full_path}"
        if request.url.query:
            req_path = f"{req_path}?{request.url.query}"

        fwd_headers = {
            k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP_HEADERS
        }

        try:
            upstream_resp = await app.state.http.request(
                method=request.method,
                url=req_path,
                headers=fwd_headers,
                content=raw_body,
            )
            resp_bytes = upstream_resp.content
            status_code = upstream_resp.status_code
            resp_headers = {
                k: v
                for k, v in upstream_resp.headers.items()
                if k.lower() not in HOP_BY_HOP_HEADERS
            }
        except Exception as exc:
            if role == "analytics" and "analytics" in req_path:
                resp_bytes = b""
                status_code = 200
                resp_headers = {"x-blackbox-analytics-fallback": "accepted"}
            else:
                resp_bytes = json.dumps({"error": "upstream_unreachable", "detail": str(exc)}).encode()
                status_code = 502
                resp_headers = {"content-type": "application/json"}

        latency_ms = (time.perf_counter() - start) * 1000.0
        log_wire_event(
            db_path=DB_PATH,
            port=listen_port,
            method=request.method,
            path=req_path,
            status_code=status_code,
            latency_ms=latency_ms,
            payload_preview=raw_body.decode("utf-8", errors="ignore")[:1000],
        )

        return Response(content=resp_bytes, status_code=status_code, headers=resp_headers)

    return app


async def serve_dual_ports() -> None:
    init_db(DB_PATH)
    core_app = build_proxy_app(CORE_UPSTREAM, CORE_PORT, "core")
    analytics_app = build_proxy_app(ANALYTICS_UPSTREAM, ANALYTICS_PORT, "analytics")

    cfg_core = uvicorn.Config(core_app, host="0.0.0.0", port=CORE_PORT, log_level="warning")
    cfg_analytics = uvicorn.Config(
        analytics_app, host="0.0.0.0", port=ANALYTICS_PORT, log_level="warning"
    )

    server_core = uvicorn.Server(cfg_core)
    server_analytics = uvicorn.Server(cfg_analytics)
    await asyncio.gather(server_core.serve(), server_analytics.serve())


if __name__ == "__main__":
    asyncio.run(serve_dual_ports())
