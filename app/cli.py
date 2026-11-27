import argparse
import os
from datetime import datetime

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

load_dotenv()

CORE_PROXY = os.getenv("BLACKBOX_CORE_URL", "http://localhost:9000")
console = Console()


def _fmt_ts(ts: float | None) -> str:
    if not ts:
        return "-"
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


def render_audit(data: dict) -> None:
    counts = data.get("counts", {})
    strict_mode = data.get("strict_pii_block_mode", False)

    summary = (
        f"[bold cyan]Wire Logs:[/bold cyan] {counts.get('wire_logs', 0)}   "
        f"[bold red]Anomalies:[/bold red] {counts.get('anomalies', 0)}   "
        f"[bold green]Sessions:[/bold green] {counts.get('experiment_sessions', 0)}   "
        f"[bold yellow]Schemas:[/bold yellow] {counts.get('schema_baselines', 0)}   "
        f"[bold magenta]Strict PII Block:[/bold magenta] {strict_mode}"
    )
    console.print(Panel(summary, title="BlackBox X — Flagsmith Governance & Telemetry Audit", border_style="cyan"))

    anom_table = Table(title="Detected Anomalies & Drift Alerts", show_lines=False)
    anom_table.add_column("Time", style="dim", width=10)
    anom_table.add_column("Severity", width=10)
    anom_table.add_column("Code", style="bold")
    anom_table.add_column("Port", width=6)
    anom_table.add_column("Detail")

    for row in data.get("anomalies", [])[:15]:
        sev = row.get("severity", "INFO")
        sev_style = "bold red" if sev == "CRITICAL" else "bold yellow" if sev == "WARN" else "cyan"
        anom_table.add_row(
            _fmt_ts(row.get("ts")),
            f"[{sev_style}]{sev}[/{sev_style}]",
            str(row.get("code", "")),
            str(row.get("port", "")),
            str(row.get("detail", "")),
        )
    console.print(anom_table)

    schema_table = Table(title="Tracked Feature Schema Baselines", show_lines=False)
    schema_table.add_column("Feature Name", style="bold cyan")
    schema_table.add_column("Expected Type", style="green")
    schema_table.add_column("Last Value")
    schema_table.add_column("Updated", style="dim", width=10)

    for row in data.get("schema_baselines", []):
        schema_table.add_row(
            str(row.get("feature_name", "")),
            str(row.get("expected_type", "")),
            str(row.get("last_value", "")),
            _fmt_ts(row.get("updated_ts")),
        )
    console.print(schema_table)

    wire_table = Table(title="Recent Wire Traffic", show_lines=False)
    wire_table.add_column("Time", style="dim", width=10)
    wire_table.add_column("Port", width=6)
    wire_table.add_column("Method", width=7)
    wire_table.add_column("Path")
    wire_table.add_column("Status", width=7)
    wire_table.add_column("PII Redacted", style="yellow")

    for row in data.get("wire_logs", [])[:12]:
        wire_table.add_row(
            _fmt_ts(row.get("ts")),
            str(row.get("port", "")),
            str(row.get("method", "")),
            str(row.get("path", "")),
            str(row.get("status_code", "")),
            str(row.get("redacted_fields") or "-"),
        )
    console.print(wire_table)


def verify_stack() -> None:
    with httpx.Client(timeout=10.0) as client:
        h = client.get(f"{CORE_PROXY}/health")
        h.raise_for_status()
        health = h.json()
        exp = client.get(f"{CORE_PROXY}/api/audit/export", params={"limit": 50})
        exp.raise_for_status()
        data = exp.json()
        counts = data.get("counts", {})
        healed = sum(1 for a in data.get("anomalies", []) if a.get("code") == "SCHEMA_DRIFT_HEALED")
        console.print(
            Panel(
                f"[bold green]PASS[/bold green] — Proxy healthy on :{health.get('listen_port')} | "
                f"Self-Heal: [bold cyan]{health.get('self_heal_enabled')}[/bold cyan] | "
                f"Wire Logs: {counts.get('wire_logs', 0)} | "
                f"Anomalies: {counts.get('anomalies', 0)} (Healed: {healed})",
                title="BlackBox X — Judge Verification Check",
                border_style="green",
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="BlackBox X Terminal Audit CLI")
    parser.add_argument("--limit", type=int, default=25, help="Max records to fetch from /api/audit/export")
    parser.add_argument("--verify", action="store_true", help="Run 1-command health & governance verification")
    args = parser.parse_args()

    if args.verify:
        verify_stack()
        return

    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{CORE_PROXY}/api/audit/export", params={"limit": args.limit})
        resp.raise_for_status()
        render_audit(resp.json())


if __name__ == "__main__":
    main()
