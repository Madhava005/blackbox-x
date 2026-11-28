import argparse
from concurrent.futures import ThreadPoolExecutor
import os
import time
import uuid

import httpx
from dotenv import load_dotenv


load_dotenv()

CORE_PROXY = f"http://localhost:{os.getenv('PROXY_CORE_PORT', '9000')}"
ANALYTICS_PROXY = f"http://localhost:{os.getenv('PROXY_ANALYTICS_PORT', '9080')}"
CLIENT_KEY = os.getenv("FLAGSMITH_CLIENT_KEY", "")


def _headers(include_key: bool = True) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if include_key and CLIENT_KEY:
        headers["X-Environment-Key"] = CLIENT_KEY
    return headers


def run_stage_1_healthy_baseline(client: httpx.Client, multiplier: int = 1) -> None:
    print(f"\n[Stage 1] Healthy Baseline Traffic ({multiplier}x scale: Flags, Identities & Analytics)")
    for _ in range(multiplier):
        r_flags = client.get(f"{CORE_PROXY}/api/v1/flags/", headers=_headers())
    print(f"  -> GET /api/v1/flags/ (x{multiplier}) [{r_flags.status_code}]")

    for idx in range(1, (4 * multiplier) + 1):
        ident = f"cust_healthy_{idx:03d}"
        r_id = client.post(
            f"{CORE_PROXY}/api/v1/identities/",
            headers=_headers(),
            json={
                "identifier": ident,
                "traits": [
                    {"trait_key": "tier", "trait_value": "pro" if idx % 2 == 0 else "free"},
                    {"trait_key": "region", "trait_value": "ap-south-1"},
                ],
            },
        )
        if idx <= 4 or idx % 20 == 0:
            print(f"  -> POST /api/v1/identities/ ({ident}) [{r_id.status_code}]")

    for _ in range(multiplier):
        r_ana = client.post(
            f"{ANALYTICS_PROXY}/api/v1/analytics/flags/",
            headers=_headers(),
            json={"checkout_flow_v2": 18, "button_color": 18},
        )
    print(f"  -> POST :9080/api/v1/analytics/flags/ (x{multiplier}) [{r_ana.status_code}]")


def run_stage_2_pii_leak_test(client: httpx.Client, multiplier: int = 1) -> None:
    print(f"\n[Stage 2] PII Leak & Query Scrubbing Verification ({multiplier}x scale)")
    for idx in range(1, multiplier + 1):
        r_post = client.post(
            f"{CORE_PROXY}/api/v1/identities/",
            headers=_headers(),
            json={
                "identifier": f"cust_pii_{idx:03d}",
                "traits": [
                    {"trait_key": "email", "trait_value": f"leak.user{idx}@example.com"},
                    {"trait_key": "phone", "trait_value": "+1-415-890-4321"},
                    {"trait_key": "plan", "trait_value": "enterprise"},
                ],
                "meta": {"ip": "203.0.113.77"},
            },
        )
    redacted_hdr = r_post.headers.get("x-blackbox-pii-redacted", "none")
    print(f"  -> POST /api/v1/identities/ (nested PII x{multiplier}) [{r_post.status_code}] | redacted={redacted_hdr}")

    for idx in range(1, multiplier + 1):
        r_get = client.get(
            f"{CORE_PROXY}/api/v1/identities/",
            params={"identifier": f"query.leak{idx}@example.com"},
            headers=_headers(),
        )
    q_redacted_hdr = r_get.headers.get("x-blackbox-pii-redacted", "none")
    print(f"  -> GET /api/v1/identities/?identifier=<email> (x{multiplier}) [{r_get.status_code}] | redacted={q_redacted_hdr}")


def run_stage_3_broken_experiments(client: httpx.Client, multiplier: int = 1) -> None:
    print(f"\n[Stage 3] Broken Experiment & Telemetry Anomaly Simulation ({multiplier}x scale)")
    for _ in range(multiplier):
        r_nokey = client.get(f"{CORE_PROXY}/api/v1/flags/", headers=_headers(include_key=False))
    print(f"  -> GET /api/v1/flags/ (missing X-Environment-Key x{multiplier}) [{r_nokey.status_code}]")

    for i in range(3 * multiplier):
        ephemeral_id = f"anon_{uuid.uuid4()}"
        r_churn = client.post(
            f"{CORE_PROXY}/api/v1/identities/",
            headers=_headers(),
            json={"identifier": ephemeral_id, "traits": []},
        )
        if i < 3 or (i + 1) % 20 == 0:
            print(f"  -> POST /api/v1/identities/ (ephemeral UUID {ephemeral_id[:16]}...) [{r_churn.status_code}]")

    for _ in range(multiplier):
        r_neg = client.post(
            f"{ANALYTICS_PROXY}/api/v1/analytics/flags/",
            headers=_headers(),
            json={"checkout_flow_v2": -5},
        )
    print(f"  -> POST :9080/api/v1/analytics/flags/ (negative count x{multiplier}) [{r_neg.status_code}]")

    for idx in range(1, multiplier + 1):
        r_orphan = client.post(
            f"{CORE_PROXY}/api/v1/identities/",
            headers=_headers(),
            json={
                "identifier": f"ghost_buyer_{idx:03d}",
                "traits": [{"trait_key": "conversion", "trait_value": 1}],
            },
        )
    print(f"  -> POST /api/v1/identities/ (orphaned conversion x{multiplier}) [{r_orphan.status_code}]")


def run_stage_4_schema_drift(client: httpx.Client, multiplier: int = 1) -> None:
    print(f"\n[Stage 4] Remote Config Schema-Drift Mutation Injection ({multiplier}x scale)")
    r_base = client.get(f"{CORE_PROXY}/api/v1/flags/", headers=_headers())
    print(f"  -> GET /api/v1/flags/ (baseline check) [{r_base.status_code}]")

    mutated_snapshot = [
        {
            "feature": {"name": "checkout_flow_v2"},
            "enabled": True,
            "feature_state_value": {"variant": "v2_experiment", "rollout_pct": 100},
        },
        {
            "feature": {"name": "button_color"},
            "enabled": True,
            "feature_state_value": 16711680,
        },
    ]
    for idx in range(1, multiplier + 1):
        r_mut = client.post(
            f"{CORE_PROXY}/api/simulate/telemetry",
            headers=_headers(),
            json={"path": "/api/v1/flags/", "identifier": f"cust_drift_{idx:03d}", "flags": mutated_snapshot},
        )
    print(f"  -> POST /api/simulate/telemetry (str -> dict/int drift x{multiplier}) [{r_mut.status_code}]")

    restored_snapshot = [
        {"feature": {"name": "checkout_flow_v2"}, "enabled": True, "feature_state_value": "control"},
        {"feature": {"name": "button_color"}, "enabled": True, "feature_state_value": "#00FF00"},
    ]
    r_rest = client.post(
        f"{CORE_PROXY}/api/simulate/telemetry",
        headers=_headers(),
        json={"path": "/api/v1/flags/", "identifier": None, "flags": restored_snapshot},
    )
    print(f"  -> POST /api/simulate/telemetry (baseline schema restored) [{r_rest.status_code}]")


def main() -> None:
    parser = argparse.ArgumentParser(description="BlackBox X Traffic Simulator")
    parser.add_argument(
        "--stage",
        choices=["1", "2", "3", "4", "all"],
        default="all",
        help="Traffic stage to execute",
    )
    parser.add_argument(
        "--multiplier",
        type=int,
        default=20,
        help="Traffic volume multiplier (default: 20x)",
    )
    args = parser.parse_args()

    t0 = time.perf_counter()
    limits = httpx.Limits(max_connections=32, max_keepalive_connections=16)
    with httpx.Client(timeout=15.0, limits=limits) as client:
        if args.stage == "all":
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [
                    pool.submit(run_stage_1_healthy_baseline, client, args.multiplier),
                    pool.submit(run_stage_2_pii_leak_test, client, args.multiplier),
                    pool.submit(run_stage_3_broken_experiments, client, args.multiplier),
                    pool.submit(run_stage_4_schema_drift, client, args.multiplier),
                ]
                for fut in futures:
                    fut.result()
        else:
            if args.stage == "1":
                run_stage_1_healthy_baseline(client, args.multiplier)
            elif args.stage == "2":
                run_stage_2_pii_leak_test(client, args.multiplier)
            elif args.stage == "3":
                run_stage_3_broken_experiments(client, args.multiplier)
            elif args.stage == "4":
                run_stage_4_schema_drift(client, args.multiplier)

    elapsed = time.perf_counter() - t0
    print(f"\n[Done] Completed {args.multiplier}x traffic wave in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
