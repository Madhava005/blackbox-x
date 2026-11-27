from fastapi.testclient import TestClient
from app.proxy import build_proxy_app


def test_dashboard_endpoint_renders_controls():
    app = build_proxy_app("http://127.0.0.1:8000", 9000, "core")
    client = TestClient(app)
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "BlackBox X" in res.text
    assert "Live Polling: ON (5s)" in res.text
    assert "Recent Intercepted Wire Traffic" in res.text
    assert "/api/audit/export" in res.text
