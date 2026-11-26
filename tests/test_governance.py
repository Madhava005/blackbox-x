import os
import tempfile

from app.db import get_conn, init_db
from app.governance import (
    inspect_request_anomalies,
    inspect_response_telemetry,
    scrub_pii,
)


def test_scrub_pii_nested_payload():
    payload = {
        "identifier": "user_101",
        "traits": [
            {"trait_key": "email", "trait_value": "alice@example.com"},
            {"trait_key": "phone", "trait_value": "+1-415-555-0199"},
            {"trait_key": "plan", "trait_value": "pro"},
        ],
        "meta": {"ip": "192.168.1.42"},
    }
    cleaned, redacted = scrub_pii(payload)
    assert cleaned["traits"][0]["trait_value"] == "[REDACTED]"
    assert cleaned["traits"][1]["trait_value"] == "[REDACTED]"
    assert cleaned["traits"][2]["trait_value"] == "pro"
    assert cleaned["meta"]["ip"] == "[REDACTED]"
    assert set(redacted) == {"email", "phone", "ip"}


def test_missing_environment_key_and_schema_drift():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        init_db(db_path)
        inspect_request_anomalies(db_path, 9000, "/api/v1/flags/", {}, None)

        baseline_flags = [
            {
                "feature": {"name": "checkout_flow_v2"},
                "enabled": True,
                "feature_state_value": "variant_a",
            }
        ]
        inspect_response_telemetry(db_path, 9000, "/api/v1/identities/", "user_1", baseline_flags)

        drifted_flags = [
            {
                "feature": {"name": "checkout_flow_v2"},
                "enabled": True,
                "feature_state_value": 42,
            }
        ]
        inspect_response_telemetry(db_path, 9000, "/api/v1/identities/", "user_2", drifted_flags)

        conn = get_conn(db_path)
        codes = [r["code"] for r in conn.execute("SELECT code FROM anomalies").fetchall()]
        conn.close()

        assert "MISSING_ENV_KEY" in codes
        assert "SCHEMA_DRIFT_DETECTED" in codes
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
