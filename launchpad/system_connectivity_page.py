"""System Connectivity report — Call Home / DNS / SNMP / NTP / Firmware live scan page."""

SYSTEM_CONNECTIVITY_PATH = "/system-connectivity"

SYSTEM_CONNECTIVITY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad System Connectivity</title>
  <style>
    :root {
      --bg: #0b0f14;
      --panel: #121821;
      --text: #e8edf5;
      --muted: #8b98ab;
      --accent: #ff6b00;
      --accent2: #ff8533;
      --border: #2a3444;
      --card: #151c27;
      --danger: #fecaca;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Segoe UI, Inter, Arial, sans-serif;
      background: radial-gradient(circle at top, #172033 0%, var(--bg) 45%);
      color: var(--text);
    }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 28px 20px 48px; }
    .hero {
      background: linear-gradient(135deg, #1a2230 0%, #101722 100%);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 24px 28px;
      margin-bottom: 18px;
    }
    .hero h1 { margin: 0 0 8px; color: var(--accent); font-size: 1.85rem; }
    .hero p { margin: 0; color: var(--muted); line-height: 1.45; }
    .hero-actions {
      display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 16px;
    }
    .btn, a.btn, button.btn {
      background: var(--accent); color: #111; border: none; border-radius: 10px;
      height: 34px; padding: 0 14px; font: inherit; font-weight: 600; cursor: pointer;
      display: inline-flex; align-items: center; text-decoration: none;
    }
    a.btn.secondary, button.btn.secondary {
      background: #0f141d; color: var(--text); border: 1px solid var(--border);
    }
    button.btn:disabled { opacity: .55; cursor: not-allowed; }
    .tabs {
      display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px;
    }
    .tab-btn {
      background: #0f141d; color: var(--muted); border: 1px solid var(--border);
      border-radius: 10px; height: 34px; padding: 0 14px; font: inherit; font-weight: 600;
      cursor: pointer;
    }
    .tab-btn.active {
      background: var(--accent); color: #111; border-color: var(--accent);
    }
    .section {
      background: var(--card); border: 1px solid var(--border); border-radius: 16px;
      padding: 18px 20px; margin-bottom: 16px;
    }
    .section[hidden] { display: none; }
    .section h2 { margin: 0 0 12px; font-size: 1.1rem; color: var(--accent2); }
    .hint { color: var(--muted); font-size: 0.88rem; margin: 0 0 12px; line-height: 1.45; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th, td { padding: 8px 10px; border-bottom: 1px solid var(--border); text-align: left; }
    th { color: var(--muted); font-weight: 600; }
    .empty { color: var(--muted); font-style: italic; }
    .status { color: var(--muted); font-size: 0.9rem; margin-top: 8px; }
    .errors { color: var(--danger); font-size: 0.88rem; margin-top: 8px; white-space: pre-wrap; }
    .footer { color: var(--muted); font-size: 0.82rem; margin-top: 20px; }
    select {
      background: #0f141d; color: var(--text); border: 1px solid var(--border);
      border-radius: 10px; height: 34px; padding: 0 10px; font: inherit;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>System Connectivity</h1>
      <p>Live Call Home, DNS, SNMP, NTP, and Firmware checks on monitored FlashSystem, HPE, and DS8884 arrays. Unlock LaunchPad, pick a site (or None for all), then Refresh live.</p>
      <div class="hero-actions">
        <label>Site <select id="sc-site-select"><option value="">None</option></select></label>
        <button type="button" class="btn" id="sc-refresh-btn">Refresh live</button>
        <button type="button" class="btn secondary" id="sc-export-xlsx-btn" disabled>Export Excel</button>
        <button type="button" class="btn secondary" id="sc-export-csv-btn" disabled>Export CSV</button>
        <a class="btn secondary" href="/">Health Dashboard</a>
        <a class="btn secondary" href="/capacity-report">Capacity</a>
        <a class="btn secondary" href="/host-volume-health">Hosts & Volumes</a>
        <a class="btn secondary" href="/volume-find">Host / Volume Find</a>
        <a class="btn secondary" href="/fc-consistgrp">FlashCopy CGs</a>
      </div>
      <div class="status" id="sc-status">Load cards, then Refresh live.</div>
      <div class="errors" id="sc-errors"></div>
    </div>

    <div class="tabs" role="tablist" aria-label="Connectivity topics">
      <button type="button" class="tab-btn active" data-tab="call_home">Call Home</button>
      <button type="button" class="tab-btn" data-tab="dns">DNS</button>
      <button type="button" class="tab-btn" data-tab="snmp">SNMP</button>
      <button type="button" class="tab-btn" data-tab="ntp">NTP</button>
      <button type="button" class="tab-btn" data-tab="firmware">Firmware</button>
    </div>

    <div class="section" id="sc-panel-call_home" data-panel="call_home">
      <h2>Call Home</h2>
      <p class="hint">HPE Call Home requires Service Processor access — not collected from array SSH in v1. DS8884 Call Home/NTP may require HMC.</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Site</th><th>Card</th><th>Host</th><th>Vendor</th><th>Profile</th>
              <th>Configured</th><th>Status</th><th>Details</th><th>Error</th>
            </tr>
          </thead>
          <tbody id="sc-call_home-body">
            <tr><td colspan="9" class="empty">No data yet — click Refresh live.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="section" id="sc-panel-dns" data-panel="dns" hidden>
      <h2>DNS</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Site</th><th>Card</th><th>Host</th><th>Vendor</th><th>Profile</th>
              <th>Configured</th><th>Status</th><th>Details</th><th>Error</th>
            </tr>
          </thead>
          <tbody id="sc-dns-body">
            <tr><td colspan="9" class="empty">No data yet — click Refresh live.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="section" id="sc-panel-snmp" data-panel="snmp" hidden>
      <h2>SNMP</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Site</th><th>Card</th><th>Host</th><th>Vendor</th><th>Profile</th>
              <th>Configured</th><th>Status</th><th>Details</th><th>Error</th>
            </tr>
          </thead>
          <tbody id="sc-snmp-body">
            <tr><td colspan="9" class="empty">No data yet — click Refresh live.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="section" id="sc-panel-ntp" data-panel="ntp" hidden>
      <h2>NTP</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Site</th><th>Card</th><th>Host</th><th>Vendor</th><th>Profile</th>
              <th>Configured</th><th>Status</th><th>Details</th><th>Error</th>
            </tr>
          </thead>
          <tbody id="sc-ntp-body">
            <tr><td colspan="9" class="empty">No data yet — click Refresh live.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="section" id="sc-panel-firmware" data-panel="firmware" hidden>
      <h2>Firmware</h2>
      <p class="hint">Versions behind uses the Admin Firmware catalog for this device profile. If Current is not in the catalog, behind shows unknown.</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Site</th><th>Card</th><th>Host</th><th>Vendor</th><th>Profile</th>
              <th>Current</th><th>Latest</th><th>Versions behind</th>
              <th>Configured</th><th>Status</th><th>Details</th><th>Error</th>
            </tr>
          </thead>
          <tbody id="sc-firmware-body">
            <tr><td colspan="12" class="empty">No data yet — click Refresh live.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="footer">LaunchPad {{APP_VERSION}}</div>
  </div>
  <script>
    const TOPICS = ["call_home", "dns", "snmp", "ntp", "firmware"];
    const TOPIC_LABELS = {
      call_home: "Call Home",
      dns: "DNS",
      snmp: "SNMP",
      ntp: "NTP",
      firmware: "Firmware",
    };
    const siteSelectEl = document.getElementById("sc-site-select");
    const refreshBtn = document.getElementById("sc-refresh-btn");
    const exportXlsxBtn = document.getElementById("sc-export-xlsx-btn");
    const exportCsvBtn = document.getElementById("sc-export-csv-btn");
    const statusEl = document.getElementById("sc-status");
    const errorsEl = document.getElementById("sc-errors");
    const bodies = {
      call_home: document.getElementById("sc-call_home-body"),
      dns: document.getElementById("sc-dns-body"),
      snmp: document.getElementById("sc-snmp-body"),
      ntp: document.getElementById("sc-ntp-body"),
      firmware: document.getElementById("sc-firmware-body"),
    };
    const tabButtons = Array.from(document.querySelectorAll(".tab-btn[data-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-panel]"));
    let refreshSucceeded = false;

    function escapeHtml(value) {
      return String(value == null ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function setActiveTab(tab) {
      tabButtons.forEach((btn) => {
        btn.classList.toggle("active", btn.getAttribute("data-tab") === tab);
      });
      panels.forEach((panel) => {
        panel.hidden = panel.getAttribute("data-panel") !== tab;
      });
    }

    async function loadSiteOptions() {
      try {
        const res = await fetch("/api/cards");
        if (!res.ok) return;
        const cards = await res.json();
        const sorted = (Array.isArray(cards) ? cards : []).slice().sort((a, b) => {
          return String(a.name || "").localeCompare(String(b.name || ""));
        });
        siteSelectEl.innerHTML = '<option value="">None</option>' + sorted.map((card) => (
          '<option value="' + escapeHtml(card.id) + '">' + escapeHtml(card.name || card.id) + "</option>"
        )).join("");
      } catch (_err) {
        /* ignore */
      }
    }

    function emptyMessage(topic) {
      return "No " + (TOPIC_LABELS[topic] || topic) + " rows found.";
    }

    function topicColspan(topic) {
      return topic === "firmware" ? 12 : 9;
    }

    function renderTopic(topic, rows) {
      const bodyEl = bodies[topic];
      if (!bodyEl) return;
      const colspan = topicColspan(topic);
      if (!rows.length) {
        bodyEl.innerHTML = '<tr><td colspan="' + colspan + '" class="empty">' + emptyMessage(topic) + "</td></tr>";
        return;
      }
      bodyEl.innerHTML = rows.map((row) => {
        let cells =
          "<td>" + escapeHtml(row.site || "") + "</td>"
          + "<td>" + escapeHtml(row.card_name || "") + "</td>"
          + "<td>" + escapeHtml(row.host || "") + "</td>"
          + "<td>" + escapeHtml(row.vendor || "") + "</td>"
          + "<td>" + escapeHtml(row.profile || "") + "</td>";
        if (topic === "firmware") {
          cells +=
            "<td>" + escapeHtml(row.current || "") + "</td>"
            + "<td>" + escapeHtml(row.latest || "") + "</td>"
            + "<td>" + escapeHtml(row.versions_behind || "") + "</td>";
        }
        cells +=
          "<td>" + escapeHtml(row.configured || "") + "</td>"
          + "<td>" + escapeHtml(row.status || "") + "</td>"
          + "<td>" + escapeHtml(row.details || "") + "</td>"
          + "<td>" + escapeHtml(row.error || "") + "</td>";
        return "<tr>" + cells + "</tr>";
      }).join("");
    }

    function clearTopics() {
      TOPICS.forEach((topic) => {
        const colspan = topicColspan(topic);
        bodies[topic].innerHTML =
          '<tr><td colspan="' + colspan + '" class="empty">No data yet — click Refresh live.</td></tr>';
      });
    }

    function renderErrors(errors) {
      if (!errors || !errors.length) {
        errorsEl.textContent = "";
        return;
      }
      errorsEl.textContent = errors.map((entry) => (
        (entry.card_name || entry.card_id || "Site") + ": " + (entry.error || "error")
      )).join("\\n");
    }

    function setExportEnabled(enabled) {
      exportXlsxBtn.disabled = !enabled;
      exportCsvBtn.disabled = !enabled;
    }

    async function refreshLive() {
      refreshBtn.disabled = true;
      statusEl.textContent = "Scanning live…";
      errorsEl.textContent = "";
      const cardId = siteSelectEl.value || "";
      const url = "/api/system-connectivity/live" + (cardId ? ("?card_id=" + encodeURIComponent(cardId)) : "");
      try {
        const res = await fetch(url);
        const data = await res.json().catch(() => ({}));
        if (res.status === 403) {
          statusEl.textContent = data.error || "Unlock LaunchPad to refresh live.";
          return;
        }
        if (!res.ok) {
          statusEl.textContent = data.error || ("Refresh failed (" + res.status + ")");
          return;
        }
        TOPICS.forEach((topic) => renderTopic(topic, data[topic] || []));
        renderErrors(data.errors || []);
        const counts = TOPICS.map((topic) => (data[topic] || []).length);
        const total = counts.reduce((sum, n) => sum + n, 0);
        const errCount = (data.errors || []).length;
        statusEl.textContent = "Found " + total + " connectivity row(s)."
          + (errCount ? (" " + errCount + " site error(s).") : "");
        refreshSucceeded = true;
        setExportEnabled(true);
      } catch (err) {
        statusEl.textContent = String(err && err.message ? err.message : err);
      } finally {
        refreshBtn.disabled = false;
      }
    }

    function exportUrl(format) {
      const cardId = siteSelectEl.value || "";
      let url = "/api/system-connectivity/export?format=" + encodeURIComponent(format) + "&open=1";
      if (cardId) {
        url += "&card_id=" + encodeURIComponent(cardId);
      }
      return url;
    }

    async function exportReport(format) {
      const btn = format === "xlsx" ? exportXlsxBtn : exportCsvBtn;
      btn.disabled = true;
      statusEl.textContent = format === "xlsx" ? "Exporting Excel…" : "Exporting CSV…";
      try {
        const res = await fetch(exportUrl(format));
        if (res.status === 404) {
          const data = await res.json().catch(() => ({}));
          statusEl.textContent = data.error || "Refresh live before exporting.";
          return;
        }
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          statusEl.textContent = data.error || ("Export failed (" + res.status + ")");
          return;
        }
        const blob = await res.blob();
        const disposition = res.headers.get("Content-Disposition") || "";
        const match = disposition.match(/filename=\"?([^\";]+)\"?/i);
        const filename = match ? match[1] : ("System_Connectivity." + (format === "xlsx" ? "xlsx" : "zip"));
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
        URL.revokeObjectURL(link.href);
        statusEl.textContent = "Export saved.";
      } catch (err) {
        statusEl.textContent = String(err && err.message ? err.message : err);
      } finally {
        btn.disabled = !refreshSucceeded;
      }
    }

    tabButtons.forEach((btn) => {
      btn.addEventListener("click", () => setActiveTab(btn.getAttribute("data-tab")));
    });
    refreshBtn.addEventListener("click", refreshLive);
    exportXlsxBtn.addEventListener("click", () => exportReport("xlsx"));
    exportCsvBtn.addEventListener("click", () => exportReport("csv"));
    siteSelectEl.addEventListener("change", () => {
      clearTopics();
      errorsEl.textContent = "";
      refreshSucceeded = false;
      setExportEnabled(false);
      statusEl.textContent = "Site changed — click Refresh to scan again.";
    });
    setActiveTab("call_home");
    loadSiteOptions();
  </script>
</body>
</html>"""
