from fastapi.testclient import TestClient
from app.proxy import POLICY, build_proxy_app


def test_dashboard_endpoint_renders_controls():
    app = build_proxy_app("http://127.0.0.1:8000", 9000, "core")
    client = TestClient(app)
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "BlackBox X" in res.text
    assert "PII FIREWALL" in res.text
    assert "Live Wire Stream" in res.text
    assert "/api/policy/strict-pii" in res.text


def test_strict_pii_policy_toggle_and_403_block():
    POLICY._client = None
    app = build_proxy_app("http://127.0.0.1:8000", 9000, "core")
    client = TestClient(app)
    try:
        res_on = client.post("/api/policy/strict-pii", json={"enabled": True})
        assert res_on.status_code == 200
        assert res_on.json()["strict_pii_block_mode"] is True

        blocked = client.post(
            "/api/v1/identities/",
            json={"identifier": "alice", "traits": [{"trait_key": "email", "trait_value": "a@b.com"}]},
        )
        assert blocked.status_code == 403
        assert blocked.headers.get("x-blackbox-quarantined") == "true"
    finally:
        POLICY._manual_override = None
        POLICY._strict_block_cached = False
