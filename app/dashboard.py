DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>BlackBox X — Flagsmith Governance & Telemetry</title>
  <style>
    :root {
      --bg: #07090d;
      --panel: #0e1218;
      --panel-alt: #141a23;
      --border: #212836;
      --border-hi: #334155;
      --text: #f1f5f9;
      --muted: #8b9bb4;
      --accent: #6366f1;
      --accent-soft: rgba(99, 102, 241, 0.14);
      --crit: #f43f5e;
      --crit-soft: rgba(244, 63, 94, 0.14);
      --warn: #f59e0b;
      --warn-soft: rgba(245, 158, 11, 0.14);
      --ok: #10b981;
      --ok-soft: rgba(16, 185, 129, 0.14);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 18px 22px;
      line-height: 1.45;
    }
    code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }

    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 14px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px 18px;
      margin-bottom: 16px;
    }
    .brand { display: flex; align-items: center; gap: 12px; }
    .logo {
      width: 34px; height: 34px; border-radius: 8px;
      background: linear-gradient(135deg, #6366f1, #8b5cf6);
      display: grid; place-items: center;
      font-weight: 800; font-size: 0.9rem; color: #fff;
      box-shadow: 0 0 20px rgba(99, 102, 241, 0.35);
    }
    h1 { font-size: 1.08rem; font-weight: 700; letter-spacing: -0.01em; }
    .sub { font-size: 0.76rem; color: var(--muted); display: flex; align-items: center; gap: 8px; margin-top: 2px; }
    .dot-live {
      width: 7px; height: 7px; border-radius: 50%; background: var(--ok);
      box-shadow: 0 0 8px var(--ok); display: inline-block;
    }

    .controls { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .switch-box {
      display: flex; align-items: center; gap: 10px;
      background: var(--panel-alt);
      border: 1px solid var(--border);
      border-radius: 9px;
      padding: 6px 12px;
    }
    .switch-label { font-size: 0.75rem; font-weight: 600; color: var(--muted); }
    .switch-state { font-size: 0.75rem; font-weight: 700; min-width: 92px; }
    .toggle {
      position: relative; width: 40px; height: 22px; cursor: pointer;
    }
    .toggle input { opacity: 0; width: 0; height: 0; }
    .slider {
      position: absolute; inset: 0; border-radius: 999px;
      background: #283244; transition: 0.2s;
    }
    .slider:before {
      content: ""; position: absolute; height: 16px; width: 16px;
      left: 3px; bottom: 3px; border-radius: 50%;
      background: #fff; transition: 0.2s;
    }
    input:checked + .slider.crit { background: var(--crit); }
    input:checked + .slider.ok { background: var(--ok); }
    input:checked + .slider:before { transform: translateX(18px); }

    .btn {
      background: var(--panel-alt);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 7px;
      padding: 6px 11px;
      font-size: 0.76rem;
      font-weight: 600;
      cursor: pointer;
      transition: border-color 0.15s, background 0.15s;
    }
    .btn:hover { border-color: var(--border-hi); }
    .btn.active {
      background: var(--accent-soft);
      border-color: var(--accent);
      color: #a5b4fc;
    }

    .kpis {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin-bottom: 16px;
    }
    @media (max-width: 860px) { .kpis { grid-template-columns: repeat(2, 1fr); } }
    .kpi {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 13px 16px;
    }
    .kpi-top { display: flex; justify-content: space-between; align-items: center; }
    .kpi-label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); font-weight: 600; }
    .kpi-tag { font-size: 0.68rem; padding: 2px 7px; border-radius: 5px; font-weight: 600; }
    .kpi-val { font-size: 1.75rem; font-weight: 700; margin-top: 4px; letter-spacing: -0.02em; }

    .split {
      display: grid;
      grid-template-columns: 1fr 1.15fr;
      gap: 14px;
      margin-bottom: 14px;
    }
    @media (max-width: 1020px) { .split { grid-template-columns: 1fr; } }

    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 11px;
      padding: 14px 16px;
      display: flex;
      flex-direction: column;
    }
    .panel-head {
      display: flex; justify-content: space-between; align-items: center;
      gap: 8px; flex-wrap: wrap;
      padding-bottom: 10px; margin-bottom: 8px;
      border-bottom: 1px solid var(--border);
    }
    .panel-title { font-size: 0.88rem; font-weight: 700; }
    .table-wrap { max-height: 295px; overflow-y: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 0.79rem; }
    th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--border); }
    th { color: var(--muted); font-weight: 600; font-size: 0.72rem; text-transform: uppercase; position: sticky; top: 0; background: var(--panel); }
    tbody tr { cursor: pointer; transition: background 0.12s; }
    tbody tr:hover { background: var(--panel-alt); }

    .sev-CRITICAL { color: var(--crit); font-weight: 700; }
    .sev-HIGH, .sev-WARN { color: var(--warn); font-weight: 700; }
    .sev-INFO { color: #38bdf8; font-weight: 700; }

    .pill {
      display: inline-block; border-radius: 4px; padding: 1px 6px;
      font-size: 0.7rem; font-weight: 600; margin-right: 4px;
    }
    .pill-redact { background: var(--crit-soft); color: #fda4af; border: 1px solid rgba(244, 63, 94, 0.35); }
    .pill-port { background: var(--accent-soft); color: #a5b4fc; }
    .st-ok { color: var(--ok); font-weight: 700; }
    .st-err { color: var(--crit); font-weight: 700; }

    .bottom-grid {
      display: grid;
      grid-template-columns: 0.9fr 1.1fr;
      gap: 14px;
    }
    @media (max-width: 1020px) { .bottom-grid { grid-template-columns: 1fr; } }
    pre.inspector {
      background: #05070a;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 0.76rem;
      color: #cbd5e1;
      max-height: 150px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="logo">BX</div>
      <div>
        <h1>BlackBox X — Flagsmith Governance & Telemetry</h1>
        <div class="sub">
          <span class="dot-live" id="live-dot"></span>
          <span>Dual-Port Wire Intercept (:9000 Core / :9080 Analytics)</span>
          <span>•</span>
          <span id="last-sync" class="mono">Syncing...</span>
        </div>
      </div>
    </div>

    <div class="controls">
      <div class="switch-box" title="Toggle between automatic PII redaction and strict HTTP 403 payload quarantine">
        <span class="switch-label">PII FIREWALL</span>
        <label class="toggle">
          <input type="checkbox" id="strict-toggle" onchange="toggleStrictPii(this.checked)" />
          <span class="slider crit"></span>
        </label>
        <span class="switch-state mono" id="strict-label" style="color: var(--ok);">REDACT MODE</span>
      </div>

      <div class="switch-box" title="Automatically restore last-known-good flag values when upstream mutates schema types">
        <span class="switch-label">SCHEMA HEALER</span>
        <label class="toggle">
          <input type="checkbox" id="heal-toggle" checked onchange="toggleSelfHeal(this.checked)" />
          <span class="slider ok"></span>
        </label>
        <span class="switch-state mono" id="heal-label" style="color: var(--ok);">HEAL ON</span>
      </div>

      <div class="switch-box">
        <span class="switch-label">AUTO-POLL (5s)</span>
        <label class="toggle">
          <input type="checkbox" id="poll-toggle" checked onchange="togglePolling(this.checked)" />
          <span class="slider ok"></span>
        </label>
      </div>

      <button class="btn" onclick="loadAudit()">Refresh</button>
    </div>
  </header>

  <div class="kpis">
    <div class="kpi">
      <div class="kpi-top"><span class="kpi-label">Wire Requests</span><span class="kpi-tag mono" style="background: var(--accent-soft); color: #a5b4fc;">:9000/:9080</span></div>
      <div class="kpi-val" id="cnt-wire">-</div>
    </div>
    <div class="kpi">
      <div class="kpi-top"><span class="kpi-label">Anomalies Caught</span><span class="kpi-tag" style="background: var(--crit-soft); color: #fda4af;">GUARD</span></div>
      <div class="kpi-val" style="color: var(--crit);" id="cnt-anom">-</div>
    </div>
    <div class="kpi">
      <div class="kpi-top"><span class="kpi-label">Experiment Sessions</span><span class="kpi-tag" style="background: var(--ok-soft); color: #6ee7b7;">ACTIVE</span></div>
      <div class="kpi-val" style="color: var(--ok);" id="cnt-sess">-</div>
    </div>
    <div class="kpi">
      <div class="kpi-top"><span class="kpi-label">Tracked Schemas</span><span class="kpi-tag" style="background: var(--warn-soft); color: #fcd34d;">DRIFT LOCK</span></div>
      <div class="kpi-val" style="color: var(--warn);" id="cnt-schema">-</div>
    </div>
  </div>

  <div class="split">
    <section class="panel">
      <div class="panel-head">
        <span class="panel-title">Detected Anomalies & Drift Alerts</span>
        <div class="controls" id="sev-filters">
          <button class="btn active" data-sev="ALL" onclick="setSeverity('ALL')">ALL</button>
          <button class="btn" data-sev="CRITICAL" onclick="setSeverity('CRITICAL')">CRITICAL</button>
          <button class="btn" data-sev="HIGH" onclick="setSeverity('HIGH')">HIGH</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Time</th><th>Severity</th><th>Code</th><th>Detail</th></tr></thead>
          <tbody id="anom-body"></tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <span class="panel-title">Live Wire Stream</span>
        <div class="controls" id="port-filters">
          <button class="btn active" data-port="ALL" onclick="setPort('ALL')">ALL PORTS</button>
          <button class="btn" data-port="9000" onclick="setPort('9000')">:9000 CORE</button>
          <button class="btn" data-port="9080" onclick="setPort('9080')">:9080 ANALYTICS</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Time</th><th>Port</th><th>Route</th><th>Status</th><th>Redacted PII</th></tr></thead>
          <tbody id="wire-body"></tbody>
        </table>
      </div>
    </section>
  </div>

  <div class="bottom-grid">
    <section class="panel">
      <div class="panel-head">
        <span class="panel-title">Feature Schema Baselines</span>
        <span style="font-size: 0.72rem; color: var(--muted);">Type-Drift Enforcement</span>
      </div>
      <div class="table-wrap" style="max-height: 150px;">
        <table>
          <thead><tr><th>Feature</th><th>Type</th><th>Last Value</th></tr></thead>
          <tbody id="schema-body"></tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <span class="panel-title">Wire Payload Inspector</span>
        <span style="font-size: 0.72rem; color: var(--muted);" id="insp-meta">Click any wire row to inspect scrubbed payload</span>
      </div>
      <pre class="inspector mono" id="insp-box">{ "hint": "Select a row in Live Wire Stream to inspect sanitized JSON payload & latency." }</pre>
    </section>
  </div>

  <script>
    let currentSeverity = "ALL";
    let currentPort = "ALL";
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

    function setPort(port) {
      currentPort = port;
      document.querySelectorAll("#port-filters .btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.port === port);
      });
      if (cachedData) renderTables(cachedData);
    }

    function togglePolling(enabled) {
      pollingEnabled = enabled;
      document.getElementById("live-dot").style.background = enabled ? "var(--ok)" : "var(--muted)";
      document.getElementById("live-dot").style.boxShadow = enabled ? "0 0 8px var(--ok)" : "none";
    }

    function updateStrictUI(enabled) {
      const toggle = document.getElementById("strict-toggle");
      const label = document.getElementById("strict-label");
      toggle.checked = Boolean(enabled);
      if (enabled) {
        label.textContent = "403 STRICT BLOCK";
        label.style.color = "var(--crit)";
      } else {
        label.textContent = "REDACT MODE";
        label.style.color = "var(--ok)";
      }
    }

    async function toggleStrictPii(enabled) {
      try {
        const res = await fetch("/api/policy/strict-pii", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled }),
        });
        const data = await res.json();
        updateStrictUI(data.strict_pii_block_mode);
      } catch (e) {
        updateStrictUI(!enabled);
      }
    }

    function updateHealUI(enabled) {
      const toggle = document.getElementById("heal-toggle");
      const label = document.getElementById("heal-label");
      toggle.checked = Boolean(enabled);
      if (enabled) {
        label.textContent = "HEAL ON";
        label.style.color = "var(--ok)";
      } else {
        label.textContent = "PASS-THRU";
        label.style.color = "var(--warn)";
      }
    }

    async function toggleSelfHeal(enabled) {
      try {
        const res = await fetch("/api/policy/self-heal", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled }),
        });
        const data = await res.json();
        updateHealUI(data.self_heal_enabled);
      } catch (e) {
        updateHealUI(!enabled);
      }
    }

    function inspectWire(idx) {
      if (!cachedData || !cachedData.wire_logs) return;
      const filtered = cachedData.wire_logs.filter(w =>
        currentPort === "ALL" ? true : String(w.port) === currentPort
      );
      const item = filtered[idx];
      if (!item) return;
      document.getElementById("insp-meta").textContent =
        `${item.method} ${item.path} • HTTP ${item.status_code} • ${Number(item.latency_ms || 0).toFixed(1)} ms`;
      let pretty = item.payload_preview || "(empty body)";
      try {
        pretty = JSON.stringify(JSON.parse(pretty), null, 2);
      } catch (e) {}
      document.getElementById("insp-box").textContent = pretty;
    }

    function renderTables(data) {
      const filteredAnoms = (data.anomalies || []).filter(a =>
        currentSeverity === "ALL" ? true : a.severity === currentSeverity
      );
      document.getElementById("anom-body").innerHTML = filteredAnoms.slice(0, 20).map(a => `
        <tr>
          <td class="mono">${fmtTime(a.ts)}</td>
          <td class="sev-${escapeHtml(a.severity)}">${escapeHtml(a.severity)}</td>
          <td class="mono"><strong>${escapeHtml(a.code)}</strong></td>
          <td>${escapeHtml(a.detail)}</td>
        </tr>
      `).join("") || '<tr><td colspan="4" style="color: var(--muted);">No anomalies matching filter.</td></tr>';

      const filteredWire = (data.wire_logs || []).filter(w =>
        currentPort === "ALL" ? true : String(w.port) === currentPort
      );
      document.getElementById("wire-body").innerHTML = filteredWire.slice(0, 20).map((w, idx) => {
        let fields = [];
        try {
          fields = typeof w.redacted_fields === "string"
            ? JSON.parse(w.redacted_fields || "[]")
            : (w.redacted_fields || []);
        } catch (e) { fields = []; }
        const badges = fields.length
          ? fields.map(f => `<span class="pill pill-redact">${escapeHtml(f)}</span>`).join("")
          : '<span style="color: var(--muted);">clean</span>';
        const stCls = w.status_code >= 400 ? "st-err" : "st-ok";
        return `
          <tr onclick="inspectWire(${idx})">
            <td class="mono">${fmtTime(w.ts)}</td>
            <td><span class="pill pill-port mono">:${escapeHtml(w.port)}</span></td>
            <td class="mono"><strong>${escapeHtml(w.method)}</strong> ${escapeHtml(w.path)}</td>
            <td class="${stCls} mono">${escapeHtml(w.status_code)}</td>
            <td>${badges}</td>
          </tr>
        `;
      }).join("") || '<tr><td colspan="5" style="color: var(--muted);">No wire traffic logged yet.</td></tr>';

      document.getElementById("schema-body").innerHTML = (data.schema_baselines || []).map(s => `
        <tr>
          <td class="mono"><strong>${escapeHtml(s.feature_name)}</strong></td>
          <td class="mono">${escapeHtml(s.expected_type)}</td>
          <td class="mono">${escapeHtml(s.last_value)}</td>
        </tr>
      `).join("") || '<tr><td colspan="3" style="color: var(--muted);">No schema baselines recorded yet.</td></tr>';
    }

    async function loadAudit() {
      try {
        const res = await fetch("/api/audit/export?limit=40");
        const data = await res.json();
        cachedData = data;
        document.getElementById("cnt-wire").textContent = data.counts.wire_logs;
        document.getElementById("cnt-anom").textContent = data.counts.anomalies;
        document.getElementById("cnt-sess").textContent = data.counts.experiment_sessions;
        document.getElementById("cnt-schema").textContent = data.counts.schema_baselines;
        updateStrictUI(data.strict_pii_block_mode);
        updateHealUI(data.self_heal_enabled);
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
