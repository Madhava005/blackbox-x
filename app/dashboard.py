DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>BlackBox X — Flagsmith Governance & Telemetry</title>
  <style>
    :root {
      --bg: #0d1117;
      --panel: #161b22;
      --border: #30363d;
      --text: #e6edf3;
      --muted: #8b949e;
      --accent: #58a6ff;
      --crit: #f85149;
      --warn: #d29922;
      --ok: #3fb950;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
      background: var(--bg);
      color: var(--text);
      padding: 24px;
      line-height: 1.5;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--border);
      padding-bottom: 16px;
      margin-bottom: 24px;
    }
    h1 { font-size: 1.35rem; color: var(--accent); }
    .badge {
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 600;
      background: rgba(63, 185, 80, 0.15);
      color: var(--ok);
      border: 1px solid rgba(63, 185, 80, 0.4);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 28px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
    }
    .card .label { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; }
    .card .value { font-size: 1.8rem; font-weight: 700; margin-top: 6px; }
    section {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 22px;
    }
    h2 { font-size: 1rem; margin-bottom: 12px; color: var(--text); }
    table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--border); }
    th { color: var(--muted); font-weight: 600; }
    .sev-CRITICAL { color: var(--crit); font-weight: 700; }
    .sev-WARN { color: var(--warn); font-weight: 700; }
    .sev-INFO { color: var(--accent); font-weight: 700; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>BlackBox X — Flagsmith Governance & Telemetry</h1>
      <div style="color: var(--muted); font-size: 0.82rem;">Dual-Port Intercept (:9000 Core / :9080 Analytics)</div>
    </div>
    <span class="badge" id="strict-badge">Loading Policy...</span>
  </header>

  <div class="grid">
    <div class="card"><div class="label">Wire Requests</div><div class="value" id="cnt-wire">-</div></div>
    <div class="card"><div class="label">Anomalies</div><div class="value" style="color: var(--crit);" id="cnt-anom">-</div></div>
    <div class="card"><div class="label">Experiment Sessions</div><div class="value" style="color: var(--ok);" id="cnt-sess">-</div></div>
    <div class="card"><div class="label">Tracked Schemas</div><div class="value" style="color: var(--warn);" id="cnt-schema">-</div></div>
  </div>

  <section>
    <h2>Detected Anomalies & Drift Alerts</h2>
    <table>
      <thead><tr><th>Time</th><th>Severity</th><th>Code</th><th>Port</th><th>Detail</th></tr></thead>
      <tbody id="anom-body"></tbody>
    </table>
  </section>

  <section>
    <h2>Feature Schema Baselines</h2>
    <table>
      <thead><tr><th>Feature</th><th>Expected Type</th><th>Last Value</th><th>Updated</th></tr></thead>
      <tbody id="schema-body"></tbody>
    </table>
  </section>

  <script>
    function fmtTime(ts) {
      if (!ts) return "-";
      return new Date(ts * 1000).toLocaleTimeString();
    }
    async function loadAudit() {
      const res = await fetch("/api/audit/export?limit=25");
      const data = await res.json();
      document.getElementById("cnt-wire").textContent = data.counts.wire_logs;
      document.getElementById("cnt-anom").textContent = data.counts.anomalies;
      document.getElementById("cnt-sess").textContent = data.counts.experiment_sessions;
      document.getElementById("cnt-schema").textContent = data.counts.schema_baselines;
      document.getElementById("strict-badge").textContent =
        data.strict_pii_block_mode ? "STRICT PII BLOCK: ON" : "PII REDACTION: ACTIVE";

      const anomBody = document.getElementById("anom-body");
      anomBody.innerHTML = data.anomalies.slice(0, 12).map(a => `
        <tr>
          <td>${fmtTime(a.ts)}</td>
          <td class="sev-${a.severity}">${a.severity}</td>
          <td><strong>${a.code}</strong></td>
          <td>${a.port}</td>
          <td>${a.detail}</td>
        </tr>
      `).join("");

      const schemaBody = document.getElementById("schema-body");
      schemaBody.innerHTML = data.schema_baselines.map(s => `
        <tr>
          <td><strong>${s.feature_name}</strong></td>
          <td>${s.expected_type}</td>
          <td><code>${s.last_value}</code></td>
          <td>${fmtTime(s.updated_ts)}</td>
        </tr>
      `).join("");
    }
    loadAudit();
  </script>
</body>
</html>
"""
