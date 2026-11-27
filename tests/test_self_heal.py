import json
from fastapi.testclient import TestClient

from app.db import init_db
from app.governance import inspect_response_telemetry
from app.proxy import POLICY, build_proxy_app


def test_self_healing_restores_last_known_good_value(tmp_path):
    db_file = str(tmp_path / "heal.db")
    init_db(db_file)

    # 1. Baseline healthy string flag
    healthy = [{"feature": {"name": "checkout_banner"}, "feature_state_value": "v1_promo"}]
    healed_1 = inspect_response_telemetry(db_file, 9000, "/api/v1/flags/", "u1", healthy, self_heal=True)
    assert healed_1 == []

    # 2. Upstream mutates flag type from str -> dict (would normally crash client SDK)
    mutated = [{"feature": {"name": "checkout_banner"}, "feature_state_value": {"broken": 123}}]
    healed_2 = inspect_response_telemetry(db_file, 9000, "/api/v1/flags/", "u1", mutated, self_heal=True)
    assert healed_2 == ["checkout_banner"]
    assert mutated[0]["feature_state_value"] == "v1_promo"


def test_self_heal_policy_toggle_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "toggle.db"))
    app = build_proxy_app("http://localhost:8000", 9000, "core")
    with TestClient(app) as client:
        res_off = client.post("/api/policy/self-heal", json={"enabled": False})
        assert res_off.status_code == 200
        assert res_off.json()["self_heal_enabled"] is False
        assert POLICY.is_self_heal_enabled() is False

        res_on = client.post("/api/policy/self-heal", json={"enabled": True})
        assert res_on.status_code == 200
        assert res_on.json()["self_heal_enabled"] is True
        assert POLICY.is_self_heal_enabled() is True
