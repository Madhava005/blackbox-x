import json
import sqlite3
import threading
import time
from pathlib import Path

_LOCK = threading.Lock()


def get_conn(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db(db_path: str) -> None:
    with _LOCK:
        conn = get_conn(db_path)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS wire_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                port INTEGER NOT NULL,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                latency_ms REAL NOT NULL,
                pii_redacted INTEGER NOT NULL DEFAULT 0,
                quarantined INTEGER NOT NULL DEFAULT 0,
                redacted_fields TEXT,
                payload_preview TEXT
            );

            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                code TEXT NOT NULL,
                severity TEXT NOT NULL,
                port INTEGER NOT NULL,
                detail TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS schema_baselines (
                feature_name TEXT PRIMARY KEY,
                expected_type TEXT NOT NULL,
                last_value TEXT,
                updated_ts REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS experiment_sessions (
                identifier TEXT NOT NULL,
                feature_name TEXT NOT NULL,
                variation TEXT NOT NULL,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                exposures INTEGER NOT NULL DEFAULT 1,
                conversions INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (identifier, feature_name)
            );
            """
        )
        conn.commit()
        conn.close()


def log_wire_event(
    db_path: str,
    port: int,
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
    pii_redacted: bool = False,
    quarantined: bool = False,
    redacted_fields: list[str] | None = None,
    payload_preview: str = "",
) -> None:
    with _LOCK:
        conn = get_conn(db_path)
        conn.execute(
            """
            INSERT INTO wire_logs
            (ts, port, method, path, status_code, latency_ms, pii_redacted, quarantined, redacted_fields, payload_preview)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(),
                port,
                method,
                path,
                status_code,
                round(latency_ms, 2),
                1 if pii_redacted else 0,
                1 if quarantined else 0,
                json.dumps(redacted_fields or []),
                payload_preview[:1000],
            ),
        )
        conn.commit()
        conn.close()


def log_anomaly(db_path: str, code: str, severity: str, port: int, detail: str) -> None:
    with _LOCK:
        conn = get_conn(db_path)
        conn.execute(
            "INSERT INTO anomalies (ts, code, severity, port, detail) VALUES (?, ?, ?, ?, ?)",
            (time.time(), code, severity, port, detail),
        )
        conn.commit()
        conn.close()
