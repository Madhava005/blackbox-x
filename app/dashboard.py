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
      --panel-alt: #1c2128;
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
      flex-wrap: wrap;
      gap: 12px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 16px;
      margin-bottom: 24px;
    }
    h1 { font-size: 1.35rem; color: var(--accent); }
    .controls { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .badge {
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 600;
      background: rgba(63, 185, 80, 0.15);
      color: var(--ok);
      border: 1px solid rgba(63, 185, 80, 0.4);
    }
    .btn {
      background: var(--panel-alt);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 5px 11px;
      font-size: 0.78rem;
      cursor: pointer;
    }
    .btn:hover { border-color: var(--accent); }
    .btn.active {
      background: rgba(88, 166, 255, 0.18);
      border-color: var(--accent);
      color: var(--accent);
      font-weight: 600;
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
      overflow-x: auto;
    }
    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      flex-wrap: wrap;
      gap: 8px;
    }
    h2 { font-size: 1rem; color: var(--text); }
    table { width: 100%; border-collapse: collapse; font-size: 0.84rem; }
    th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--border); }
    th { color: var(--muted); font-weight: 600; }
    .sev-CRITICAL { color: var(--crit); font-weight: 700; }
    .sev-HIGH, .sev-WARN { color: var(--warn); font-weight: 700; }
    .sev-INFO { color: var(--accent); font-weight: 700; }
    .pill-redact {
      display: inline-block;
      background: rgba(248, 81, 73, 0.16);
      color: var(--crit);
      border: 1px solid rgba(248, 81, 73, 0.4);
      border-radius: 4px;
      padding: 1px 6px;
      font-size: 0.74rem;
      margin-right: 4px;
    }
    .status-ok { color: var(--ok); font-weight: 600; }
    .status-err { color: var(--crit); font-weight: 600; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>BlackBox X — Flagsmith Governance & Telemetry</h1>
      <div style="color: var(--muted); font-size: 0.82rem;">Dual-Port Intercept (:9000 Core / :9080 Analytics)</div>
    </div>
    <div class="controls">
      <span class="badge" id="strict-badge">Loading Policy...</span>
      <button class="btn active" id="poll-btn" onclick="togglePolling()">Live Polling: ON (5s)</button>
      <button class="btn" onclick="loadAudit()">Refresh Now</button>
    </div>
  </header>

  <div class="grid">
    <div class="card"><div class="label">Wire Requests</div><div class="value" id="cnt-wire">-</div></div>
    <div class="card"><div class="label">Anomalies</div><div class="value" style="color: var(--crit);" id="cnt-anom">-</div></div>
    <div class="card"><div class="label">Experiment Sessions</div><div class="value" style="color: var(--ok);" id="cnt-sess">-</div></div>
    <div class="card"><div class="label">Tracked Schemas</div><div class="value" style="color: var(--warn);" id="cnt-schema">-</div></div>
  </div>

  <section>
    <div class="section-head">
      <h2>Detected Anomalies & Drift Alerts</h2>
      <div class="controls" id="sev-filters">
        <button class="btn active" data-sev="ALL" onclick="setSeverity('ALL')">ALL</button>
        <button class="btn" data-sev="CRITICAL" onclick="setSeverity('CRITICAL')">CRITICAL</button>
        <button class="btn" data-sev="HIGH" onclick="setSeverity('HIGH')">HIGH</button>
      </div>
    </div>
    <table>
      <thead><tr><th>Time</th><th>Severity</th><th>Code</th><th>Port</th><th>Detail</th></tr></thead>
      <tbody id="anom-body"></tbody>
    </table>
  </section>

  <section>
    <div class="section-head">
      <h2>Feature Schema Baselines</h2>
    </div>
    <table>
      <thead><tr><th>Feature</th><th>Expected Type</th><th>Last Value</th><th>Updated</th></tr></thead>
      <tbody id="schema-body"></tbody>
    </table>
  </section>

  <section>
    <div class="section-head">
      <h2>Recent Intercepted Wire Traffic</h2>
      <span style="color: var(--muted); font-size: 0.78rem;" id="last-sync">Syncing...</span>
    </div>
    <table>
      <thead><tr><th>Time</th><th>Port</th><th>Method</th><th>Path</th><th>Status</th><th>Redacted Fields</th></tr></thead>
      <tbody id="wire-body"></tbody>
    </table>
  </section>

  <script>
    let currentSeverity = "ALL";
    let pollingEnabled = true;
    let cachedData = null;

    function fmtTime(ts) {
      if (!ts) return "-";
      return new Date(ts * 1000).toLocaleTimeString();
    }

    function escapeHtml(val) {
      return String(val ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }

    function setSeverity(sev) {
      currentSeverity = sev;
      document.querySelectorAll("#sev-filters .btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.sev === sev);
      });
      if (cachedData) renderTables(cachedData);
    }

    function togglePolling() {
      pollingEnabled = !pollingEnabled;
      const btn = document.getElementById("poll-btn");
      btn.textContent = pollingEnabled ? "Live Polling: ON (5s)" : "Live Polling: PAUSED";
      btn.classList.toggle("active", pollingEnabled);
    }

    function renderTables(data) {
      const filteredAnoms = (data.anomalies || []).filter(a =>
        currentSeverity === "ALL" ? true : a.severity === currentSeverity
      );
      const anomBody = document.getElementById("anom-body");
      anomBody.innerHTML = filteredAnoms.slice(0, 15).map(a => `
        <tr>
          <td>${fmtTime(a.ts)}</td>
          <td class="sev-${escapeHtml(a.severity)}">${escapeHtml(a.severity)}</td>
          <td><strong>${escapeHtml(a.code)}</strong></td>
          <td>${escapeHtml(a.port)}</td>
          <td>${escapeHtml(a.detail)}</td>
        </tr>
      `).join("") || '<tr><td colspan="5" style="color: var(--muted);">No anomalies matching filter.</td></tr>';

      const schemaBody = document.getElementById("schema-body");
      schemaBody.innerHTML = (data.schema_baselines || []).map(s => `
        <tr>
          <td><strong>${escapeHtml(s.feature_name)}</strong></td>
          <td>${escapeHtml(s.expected_type)}</td>
          <td><code>${escapeHtml(s.last_value)}</code></td>
          <td>${fmtTime(s.updated_ts)}</td>
        </tr>
      `).join("") || '<tr><td colspan="4" style="color: var(--muted);">No schema baselines recorded yet.</td></tr>';

      const wireBody = document.getElementById("wire-body");
      wireBody.innerHTML = (data.wire_logs || []).slice(0, 15).map(w => {
        let fields = [];
        try {
          fields = typeof w.redacted_fields === "string"
            ? JSON.parse(w.redacted_fields || "[]")
            : (w.redacted_fields || []);
        } catch (e) { fields = []; }
        const badges = fields.length
          ? fields.map(f => `<span class="pill-redact">${escapeHtml(f)}</span>`).join("")
          : '<span style="color: var(--muted);">clean</span>';
        const statusCls = w.status_code >= 400 ? "status-err" : "status-ok";
        return `
          <tr>
            <td>${fmtTime(w.ts)}</td>
            <td>${escapeHtml(w.port)}</td>
            <td><strong>${escapeHtml(w.method)}</strong></td>
            <td><code>${escapeHtml(w.path)}</code></td>
            <td class="${statusCls}">${escapeHtml(w.status_code)}</td>
            <td>${badges}</td>
          </tr>
        `;
      }).join("") || '<tr><td colspan="6" style="color: var(--muted);">No wire traffic logged yet.</td></tr>';
    }

    async function loadAudit() {
      try {
        const res = await fetch("/api/audit/export?limit=30");
        const data = await res.json();
        cachedData = data;
        document.getElementById("cnt-wire").textContent = data.counts.wire_logs;
        document.getElementById("cnt-anom").textContent = data.counts.anomalies;
        document.getElementById("cnt-sess").textContent = data.counts.experiment_sessions;
        document.getElementById("cnt-schema").textContent = data.counts.schema_baselines;
        document.getElementById("strict-badge").textContent =
          data.strict_pii_block_mode ? "STRICT PII BLOCK: ON" : "PII REDACTION: ACTIVE";
        document.getElementById("last-sync").textContent = "Updated " + new Date().toLocaleTimeString();
        renderTables(data);
      } catch (err) {
        document.getElementById("last-sync").textContent = "Sync error";
      }
    }

    loadAudit();
    setInterval(() => {
      if (pollingEnabled) loadAudit();
    }, 5000);
  </script>
</body>
</html>
"""
