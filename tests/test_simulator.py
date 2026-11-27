import os
import tempfile

import httpx

import app.simulate as sim_mod
from app.db import get_conn


def test_stage_4_logs_schema_drift_and_restores_baseline(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    def mock_flags(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"feature": {"name": "checkout_flow_v2"}, "enabled": True, "feature_state_value": "control"},
                {"feature": {"name": "button_color"}, "enabled": True, "feature_state_value": "#00FF00"},
            ],
        )

    try:
        monkeypatch.setattr(sim_mod, "DB_PATH", db_path)
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

        with httpx.Client(transport=httpx.MockTransport(mock_flags)) as client:
            sim_mod.run_stage_4_schema_drift(client)

        conn = get_conn(db_path)
        drifts = conn.execute(
            "SELECT * FROM anomalies WHERE category = 'SCHEMA_DRIFT_DETECTED'"
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
