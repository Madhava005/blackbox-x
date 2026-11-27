import os
import tempfile

import httpx
from fastapi.testclient import TestClient

import app.proxy as proxy_mod
import app.simulate as sim_mod
from app.db import get_conn, init_db


def test_stage_4_logs_schema_drift_and_restores_baseline(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        init_db(db_path)
        monkeypatch.setattr(proxy_mod, "DB_PATH", db_path)
        conn = get_conn(db_path)
        conn.execute(
            "INSERT INTO schema_baselines (feature_name, expected_type, last_value, updated_ts) VALUES (?, ?, ?, ?)",
            ("checkout_flow_v2", "str", '"control"', 1.0),
        )
        conn.execute(
            "INSERT INTO schema_baselines (feature_name, expected_type, last_value, updated_ts) VALUES (?, ?, ?, ?)",
            ("button_color", "str", '"#00FF00"', 1.0),
        )
        conn.commit()
        conn.close()

        app = proxy_mod.build_proxy_app("http://upstream.local", 9000, "core")
        tc = TestClient(app)

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and request.url.path == "/api/v1/flags/":
                return httpx.Response(200, json=[])
            resp = tc.request(request.method, request.url.path, content=request.content)
            return httpx.Response(resp.status_code, json=resp.json())

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            sim_mod.run_stage_4_schema_drift(client)

        conn = get_conn(db_path)
        drifts = conn.execute(
            "SELECT * FROM anomalies WHERE code = 'SCHEMA_DRIFT_DETECTED'"
        ).fetchall()
        baseline = conn.execute(
            "SELECT expected_type FROM schema_baselines WHERE feature_name = 'checkout_flow_v2'"
        ).fetchone()
        conn.close()

        assert len(drifts) >= 2
        assert baseline["expected_type"] == "str"
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
