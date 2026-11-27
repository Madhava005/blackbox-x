import argparse
import os
import time

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


def run_stage_1_healthy_baseline(client: httpx.Client) -> None:
    print("\n[Stage 1] Healthy Baseline Traffic (Flags, Identities & Analytics)")
    r_flags = client.get(f"{CORE_PROXY}/api/v1/flags/", headers=_headers())
    print(f"  -> GET /api/v1/flags/ [{r_flags.status_code}]")

    for idx in range(1, 5):
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
        print(f"  -> POST /api/v1/identities/ ({ident}) [{r_id.status_code}]")
        time.sleep(0.1)

    r_ana = client.post(
        f"{ANALYTICS_PROXY}/api/v1/analytics/flags/",
        headers=_headers(),
        json={"checkout_flow_v2": 18, "button_color": 18},
    )
    print(f"  -> POST :9080/api/v1/analytics/flags/ [{r_ana.status_code}]")


def main() -> None:
    parser = argparse.ArgumentParser(description="BlackBox X Traffic Simulator")
    parser.add_argument(
        "--stage",
        choices=["1", "all"],
        default="all",
        help="Traffic stage to execute",
    )
    args = parser.parse_args()

    with httpx.Client(timeout=10.0) as client:
        if args.stage in {"1", "all"}:
            run_stage_1_healthy_baseline(client)


if __name__ == "__main__":
    main()
