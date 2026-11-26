import json
import os
import re
import threading
import time
from typing import Any

from flagsmith import Flagsmith
from flagsmith.models import DefaultFlag

from app.db import get_conn, log_anomaly

PII_KEYS = {
    "email",
    "e_mail",
    "phone",
    "phone_number",
    "mobile",
    "ip",
    "ip_address",
    "ssn",
    "password",
    "credit_card",
    "address",
    "full_name",
}

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9\-\s\(\)]{8,18}$")
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class LivePolicyController:
    def __init__(self) -> None:
        self.server_key = os.getenv("FLAGSMITH_SERVER_KEY", "")
        self.core_url = os.getenv("FLAGSMITH_CORE_URL", "http://localhost:8000").rstrip("/")
        self.refresh_interval = int(os.getenv("REFRESH_INTERVAL_SECONDS", "15"))
        self._client: Flagsmith | None = None
        self._strict_block_cached = False
        self._last_check = 0.0
        self._lock = threading.Lock()
        self._init_client()

    def _default_handler(self, feature_name: str) -> DefaultFlag:
        return DefaultFlag(enabled=False, value=None)

    def _init_client(self) -> None:
        if self.server_key and not self.server_key.startswith("ser.replace"):
            try:
                self._client = Flagsmith(
                    environment_key=self.server_key,
                    api_url=f"{self.core_url}/api/v1/",
                    environment_refresh_interval_seconds=self.refresh_interval,
                    default_flag_handler=self._default_handler,
                )
            except Exception:
                self._client = None

    def is_strict_pii_block_enabled(self) -> bool:
        now = time.time()
        with self._lock:
            if self._client is None:
                self._init_client()
            if self._client is not None and (now - self._last_check) >= 2.0:
                try:
                    flags = self._client.get_environment_flags()
                    self._strict_block_cached = bool(flags.is_feature_enabled("strict_pii_block_mode"))
                    self._last_check = now
                except Exception:
                    pass
            return self._strict_block_cached


def scrub_pii(payload: Any, parent_key: str = "") -> tuple[Any, list[str]]:
    redacted_fields: list[str] = []

    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for k, v in payload.items():
            key_lower = str(k).lower()
            if key_lower in PII_KEYS and v not in (None, "", "[REDACTED]"):
                cleaned[k] = "[REDACTED]"
                redacted_fields.append(str(k))
            else:
                sub_val, sub_fields = scrub_pii(v, key_lower)
                cleaned[k] = sub_val
                redacted_fields.extend(sub_fields)
        return cleaned, list(dict.fromkeys(redacted_fields))

    if isinstance(payload, list):
        cleaned_list = []
        for item in payload:
            sub_val, sub_fields = scrub_pii(item, parent_key)
            cleaned_list.append(sub_val)
            redacted_fields.extend(sub_fields)
        return cleaned_list, list(dict.fromkeys(redacted_fields))

    if isinstance(payload, str) and payload != "[REDACTED]":
        if EMAIL_RE.match(payload.strip()) or (
            parent_key not in {"id", "identifier", "value", "feature"}
            and PHONE_RE.match(payload.strip())
        ):
            return "[REDACTED]", [parent_key or "string_pattern"]

    return payload, []


def inspect_request_anomalies(
    db_path: str, port: int, path: str, headers: dict[str, str], body_json: Any
) -> None:
    env_key = headers.get("x-environment-key", "")
    if "/api/v1/" in path and not path.startswith("/api/audit") and not env_key:
        log_anomaly(
            db_path,
            "MISSING_ENV_KEY",
            "HIGH",
            port,
            f"Missing X-Environment-Key header on {path}",
        )

    if isinstance(body_json, dict):
        identifier = body_json.get("identifier")
        if "/identities" in path:
            if not identifier or str(identifier).strip().lower() in {"null", "none", "anonymous", ""}:
                log_anomaly(
                    db_path,
                    "UNSTABLE_EXPERIMENT_ID",
                    "CRITICAL",
                    port,
                    f"Null/anonymous identity on {path} - breaks deterministic multivariate bucketing",
                )
            elif UUID_RE.match(str(identifier)):
                conn = get_conn(db_path)
                recent_uuids = conn.execute(
                    """
                    SELECT COUNT(*) AS c FROM wire_logs
                    WHERE path LIKE '%/identities%' AND ts > ? AND payload_preview LIKE '%-%-%-%-%'
                    """,
                    (time.time() - 30.0,),
                ).fetchone()["c"]
                conn.close()
                if recent_uuids >= 5:
                    log_anomaly(
                        db_path,
                        "UNSTABLE_EXPERIMENT_ID",
                        "CRITICAL",
                        port,
                        f"Ephemeral UUID churn detected ({identifier}) - unstable experiment bucketing",
                    )

        if "/analytics/flags" in path:
            for k, v in body_json.items():
                if isinstance(v, (int, float)) and v < 0:
                    log_anomaly(
                        db_path,
                        "NEGATIVE_ANALYTICS_COUNT",
                        "HIGH",
                        port,
                        f"Negative evaluation count ({k}={v}) rejected from telemetry stream",
                    )

        if "/events" in path or "/traits" in path:
            ident = body_json.get("identifier")
            event_name = str(body_json.get("event_name") or body_json.get("trait_key") or "")
            if not ident or str(ident).strip().lower() in {"null", "none", ""}:
                log_anomaly(
                    db_path,
                    "ORPHANED_OR_FLAT_CONVERSION",
                    "CRITICAL",
                    port,
                    f"Orphaned conversion/trait ({event_name}) with missing/null identifier",
                )
            else:
                conn = get_conn(db_path)
                row = conn.execute(
                    "SELECT * FROM experiment_sessions WHERE identifier = ?",
                    (str(ident),),
                ).fetchone()
                if row is None:
                    log_anomaly(
                        db_path,
                        "ORPHANED_OR_FLAT_CONVERSION",
                        "HIGH",
                        port,
                        f"Conversion '{event_name}' fired for '{ident}' with zero prior flag exposure",
                    )
                else:
                    conn.execute(
                        "UPDATE experiment_sessions SET conversions = conversions + 1 WHERE identifier = ?",
                        (str(ident),),
                    )
                    conn.commit()
                conn.close()


def inspect_response_telemetry(
    db_path: str, port: int, path: str, identifier: str | None, resp_json: Any
) -> None:
    flags_list: list[dict[str, Any]] = []
    if isinstance(resp_json, list):
        flags_list = [item for item in resp_json if isinstance(item, dict)]
    elif isinstance(resp_json, dict) and isinstance(resp_json.get("flags"), list):
        flags_list = [item for item in resp_json["flags"] if isinstance(item, dict)]

    if not flags_list:
        return

    now = time.time()
    conn = get_conn(db_path)
    for item in flags_list:
        feat = item.get("feature", {})
        fname = feat.get("name") if isinstance(feat, dict) else None
        if not fname:
            continue
        val = item.get("feature_state_value")
        val_type = type(val).__name__

        baseline = conn.execute(
            "SELECT * FROM schema_baselines WHERE feature_name = ?", (fname,)
        ).fetchone()
        if baseline is None:
            conn.execute(
                "INSERT INTO schema_baselines (feature_name, expected_type, last_value, updated_ts) VALUES (?, ?, ?, ?)",
                (fname, val_type, json.dumps(val), now),
            )
        elif baseline["expected_type"] != val_type:
            log_anomaly(
                db_path,
                "SCHEMA_DRIFT_DETECTED",
                "CRITICAL",
                port,
                f"Feature '{fname}' mutated type from {baseline['expected_type']} ({baseline['last_value']}) -> {val_type} ({json.dumps(val)})",
            )
            conn.execute(
                "UPDATE schema_baselines SET expected_type = ?, last_value = ?, updated_ts = ? WHERE feature_name = ?",
                (val_type, json.dumps(val), now, fname),
            )

        if identifier and fname == "checkout_flow_v2" and val is not None:
            var_str = str(val)
            existing = conn.execute(
                "SELECT * FROM experiment_sessions WHERE identifier = ? AND feature_name = ?",
                (identifier, fname),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO experiment_sessions
                    (identifier, feature_name, variation, first_seen, last_seen, exposures, conversions)
                    VALUES (?, ?, ?, ?, ?, 1, 0)
                    """,
                    (identifier, fname, var_str, now, now),
                )
            else:
                if existing["variation"] != var_str:
                    log_anomaly(
                        db_path,
                        "LATE_MULTIVARIATE_MUTATION",
                        "CRITICAL",
                        port,
                        f"Session '{identifier}' mutated mid-experiment on '{fname}': {existing['variation']} -> {var_str}",
                    )
                conn.execute(
                    "UPDATE experiment_sessions SET exposures = exposures + 1, last_seen = ?, variation = ? WHERE identifier = ? AND feature_name = ?",
                    (now, var_str, identifier, fname),
                )

    totals = conn.execute(
        """
        SELECT variation, COUNT(*) AS cnt FROM experiment_sessions
        WHERE feature_name = 'checkout_flow_v2' GROUP BY variation
        """
    ).fetchall()
    if len(totals) == 1 and totals[0]["cnt"] >= 8:
        only_var = totals[0]["variation"]
        cnt = totals[0]["cnt"]
        already = conn.execute(
            "SELECT COUNT(*) AS c FROM anomalies WHERE code = 'ONE_SIDED_EXPOSURE_SKEW' AND ts > ?",
            (now - 60.0,),
        ).fetchone()["c"]
        if already == 0:
            log_anomaly(
                db_path,
                "ONE_SIDED_EXPOSURE_SKEW",
                "HIGH",
                port,
                f"100% exposure skew ({cnt} sessions in '{only_var}', 0 in alternate variation) on checkout_flow_v2",
            )

    conn.commit()
    conn.close()
