import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import parse_qsl

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from app.dashboard import DASHBOARD_HTML

from app.db import get_conn, init_db, log_wire_event
from app.governance import (
    LivePolicyController,
    inspect_request_anomalies,
    inspect_response_telemetry,
    scrub_pii,
    scrub_query_params,
)

load_dotenv()

CORE_UPSTREAM = os.getenv("FLAGSMITH_CORE_URL", "http://localhost:8000").rstrip("/")
ANALYTICS_UPSTREAM = os.getenv("FLAGSMITH_ANALYTICS_URL", "http://localhost:8080").rstrip("/")
CORE_PORT = int(os.getenv("PROXY_CORE_PORT", "9000"))
ANALYTICS_PORT = int(os.getenv("PROXY_ANALYTICS_PORT", "9080"))
DB_PATH = os.getenv("DB_PATH", "data/blackbox.db")

POLICY = LivePolicyController()

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
    "content-encoding",
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
            "strict_pii_block_mode": POLICY.is_strict_pii_block_enabled(),
        }

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard_view() -> HTMLResponse:
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/api/audit/export")
    async def audit_export(limit: int = 50) -> JSONResponse:
        conn = get_conn(DB_PATH)
        logs = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM wire_logs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        ]
        anomalies = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM anomalies ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        ]
        sessions = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM experiment_sessions ORDER BY last_seen DESC LIMIT ?", (limit,)
            ).fetchall()
        ]
        schemas = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM schema_baselines ORDER BY feature_name ASC"
            ).fetchall()
        ]
        conn.close()
        return JSONResponse(
            {
                "exported_at": time.time(),
                "strict_pii_block_mode": POLICY.is_strict_pii_block_enabled(),
                "counts": {
                    "wire_logs": len(logs),
                    "anomalies": len(anomalies),
                    "experiment_sessions": len(sessions),
                    "schema_baselines": len(schemas),
                },
                "wire_logs": logs,
                "anomalies": anomalies,
                "experiment_sessions": sessions,
                "schema_baselines": schemas,
            }
        )

    @app.post("/api/simulate/telemetry")
    async def simulate_telemetry(request: Request) -> JSONResponse:
        body = await request.json()
        inspect_response_telemetry(
            DB_PATH,
            listen_port,
            body.get("path", "/api/v1/flags/"),
            body.get("identifier"),
            body.get("flags", []),
        )
        return JSONResponse({"status": "recorded"})

    @app.api_route(
        "/{full_path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    async def forward(request: Request, full_path: str) -> Response:
        start = time.perf_counter()
        raw_body = await request.body()
        cleaned_query, query_redacted = scrub_query_params(request.url.query)
        req_path = f"/{full_path}"
        if cleaned_query:
            req_path = f"{req_path}?{cleaned_query}"

        headers_lower = {k.lower(): v for k, v in request.headers.items()}
        fwd_headers = {
            k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP_HEADERS
        }

        parsed_body: Any = None
        redacted_fields: list[str] = list(query_redacted)
        outbound_body = raw_body
        identifier: str | None = dict(parse_qsl(cleaned_query)).get("identifier")

        if raw_body:
            try:
                parsed_body = json.loads(raw_body.decode("utf-8"))
                if isinstance(parsed_body, dict) and parsed_body.get("identifier") is not None:
                    identifier = str(parsed_body.get("identifier"))

                cleaned_body, body_redacted = scrub_pii(parsed_body)
                if body_redacted:
                    redacted_fields = list(dict.fromkeys(redacted_fields + body_redacted))
                    if POLICY.is_strict_pii_block_enabled():
                        latency_ms = (time.perf_counter() - start) * 1000.0
                        log_wire_event(
                            db_path=DB_PATH,
                            port=listen_port,
                            method=request.method,
                            path=req_path,
                            status_code=403,
                            latency_ms=latency_ms,
                            pii_redacted=True,
                            quarantined=True,
                            redacted_fields=redacted_fields,
                            payload_preview=json.dumps(cleaned_body)[:1000],
                        )
                        return JSONResponse(
                            status_code=403,
                            content={
                                "error": "strict_pii_block_mode_enforced",
                                "message": "Payload quarantined by BlackBox X governance policy",
                                "blocked_fields": redacted_fields,
                            },
                            headers={"x-blackbox-quarantined": "true"},
                        )

                    outbound_body = json.dumps(cleaned_body).encode("utf-8")
                    fwd_headers["content-type"] = "application/json"
                    parsed_body = cleaned_body
            except Exception:
                pass

        inspect_request_anomalies(DB_PATH, listen_port, req_path, headers_lower, parsed_body)

        try:
            upstream_resp = await app.state.http.request(
                method=request.method,
                url=req_path,
                headers=fwd_headers,
                content=outbound_body,
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

        if resp_bytes:
            try:
                resp_json = json.loads(resp_bytes.decode("utf-8"))
                inspect_response_telemetry(DB_PATH, listen_port, req_path, identifier, resp_json)
            except Exception:
                pass

        if redacted_fields:
            resp_headers["x-blackbox-pii-redacted"] = ",".join(redacted_fields)

        latency_ms = (time.perf_counter() - start) * 1000.0
        log_wire_event(
            db_path=DB_PATH,
            port=listen_port,
            method=request.method,
            path=req_path,
            status_code=status_code,
            latency_ms=latency_ms,
            pii_redacted=bool(redacted_fields),
            quarantined=False,
            redacted_fields=redacted_fields,
            payload_preview=outbound_body.decode("utf-8", errors="ignore")[:1000],
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
