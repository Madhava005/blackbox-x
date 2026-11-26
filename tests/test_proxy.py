import json
import os
import tempfile

import httpx
from fastapi.testclient import TestClient

import app.proxy as proxy_mod
from app.db import get_conn


def test_proxy_redacts_pii_and_sets_header(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    captured_upstream = {}

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_upstream["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "flags": [
                    {
                        "feature": {"name": "checkout_flow_v2"},
                        "enabled": True,
                        "feature_state_value": "variant_a",
                    }
                ]
            },
        )

    try:
        monkeypatch.setattr(proxy_mod, "DB_PATH", db_path)
        app = proxy_mod.build_proxy_app("http://mock-flagsmith", 9000, "core")
        with TestClient(app) as client:
            app.state.http = httpx.AsyncClient(
                base_url="http://mock-flagsmith",
                transport=httpx.MockTransport(mock_handler),
            )
            resp = client.post(
                "/api/v1/identities/",
                headers={"X-Environment-Key": "ser.testkey123"},
                json={
                    "identifier": "user_501",
                    "traits": [{"trait_key": "email", "trait_value": "bob@example.com"}],
                },
            )

        assert resp.status_code == 200
        assert resp.headers.get("x-blackbox-pii-redacted") == "email"
        assert captured_upstream["body"]["traits"][0]["trait_value"] == "[REDACTED]"

        conn = get_conn(db_path)
        row = conn.execute("SELECT * FROM wire_logs ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row["pii_redacted"] == 1
        assert "bob@example.com" not in row["payload_preview"]
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_analytics_proxy_empty_body_fallback(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    def failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("upstream offline")

    try:
        monkeypatch.setattr(proxy_mod, "DB_PATH", db_path)
        app = proxy_mod.build_proxy_app("http://mock-analytics", 9080, "analytics")
        with TestClient(app) as client:
            app.state.http = httpx.AsyncClient(
                base_url="http://mock-analytics",
                transport=httpx.MockTransport(failing_handler),
            )
            resp = client.post(
                "/api/v1/analytics/flags/",
                headers={"X-Environment-Key": "ser.testkey123"},
                json={"checkout_flow_v2": 12},
            )

        assert resp.status_code == 200
        assert resp.content == b""
        assert resp.headers.get("x-blackbox-analytics-fallback") == "accepted"
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
