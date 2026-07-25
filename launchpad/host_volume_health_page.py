"""Hosts & Volumes Health report — live offline/degraded scan."""

HOST_VOLUME_HEALTH_PATH = "/host-volume-health"

HOST_VOLUME_HEALTH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Hosts & Volumes Health</title>
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
    .section {
      background: var(--card); border: 1px solid var(--border); border-radius: 16px;
      padding: 18px 20px; margin-bottom: 16px;
    }
    .section h2 { margin: 0 0 12px; font-size: 1.1rem; color: var(--accent2); }
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
      <h1>Hosts & Volumes Health</h1>
      <p>Live offline and degraded hosts and volumes on monitored IBM and HPE arrays. Unlock LaunchPad, pick a site (or None for all), then Refresh live.</p>
      <div class="hero-actions">
        <label>Site <select id="hv-site-select"><option value="">None</option></select></label>
        <button type="button" class="btn" id="hv-refresh-btn">Refresh live</button>
        <button type="button" class="btn secondary" id="hv-export-xlsx-btn" disabled>Export Excel</button>
        <button type="button" class="btn secondary" id="hv-export-csv-btn" disabled>Export CSV</button>
        <a class="btn secondary" href="/">Health Dashboard</a>
        <a class="btn secondary" href="/capacity-report">Capacity</a>
        <a class="btn secondary" href="/volume-find">Host / Volume Find</a>
        <a class="btn secondary" href="/fc-consistgrp">FlashCopy CGs</a>
      </div>
      <div class="status" id="hv-status">Load cards, then Refresh live.</div>
      <div class="errors" id="hv-errors"></div>
    </div>

    <div class="section">
      <h2>Hosts</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Card</th><th>Site IP</th><th>Vendor</th><th>Host name</th><th>Status</th>
            </tr>
          </thead>
          <tbody id="hv-hosts-body">
            <tr><td colspan="5" class="empty">No data yet — click Refresh live.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="section">
      <h2>Volumes</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Card</th><th>Site IP</th><th>Vendor</th><th>Volume</th><th>Pool/CPG</th><th>Status</th>
            </tr>
          </thead>
          <tbody id="hv-volumes-body">
            <tr><td colspan="6" class="empty">No data yet — click Refresh live.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="footer">LaunchPad {{APP_VERSION}}</div>
  </div>
  <script>
    const siteSelectEl = document.getElementById("hv-site-select");
    const refreshBtn = document.getElementById("hv-refresh-btn");
    const exportXlsxBtn = document.getElementById("hv-export-xlsx-btn");
    const exportCsvBtn = document.getElementById("hv-export-csv-btn");
    const statusEl = document.getElementById("hv-status");
    const errorsEl = document.getElementById("hv-errors");
    const hostsBodyEl = document.getElementById("hv-hosts-body");
    const volumesBodyEl = document.getElementById("hv-volumes-body");

    function escapeHtml(value) {
      return String(value == null ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
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

    function renderHosts(hosts) {
      if (!hosts.length) {
        hostsBodyEl.innerHTML = '<tr><td colspan="5" class="empty">No offline or degraded hosts found.</td></tr>';
        return;
      }
      hostsBodyEl.innerHTML = hosts.map((row) => (
        "<tr>"
        + "<td>" + escapeHtml(row.card_name || "") + "</td>"
        + "<td>" + escapeHtml(row.host || "") + "</td>"
        + "<td>" + escapeHtml(row.vendor || "") + "</td>"
        + "<td>" + escapeHtml(row.host_name || "") + "</td>"
        + "<td>" + escapeHtml(row.status || "") + "</td>"
        + "</tr>"
      )).join("");
    }

    function renderVolumes(volumes) {
      if (!volumes.length) {
        volumesBodyEl.innerHTML = '<tr><td colspan="6" class="empty">No offline or degraded volumes found.</td></tr>';
        return;
      }
      volumesBodyEl.innerHTML = volumes.map((row) => (
        "<tr>"
        + "<td>" + escapeHtml(row.card_name || "") + "</td>"
        + "<td>" + escapeHtml(row.host || "") + "</td>"
        + "<td>" + escapeHtml(row.vendor || "") + "</td>"
        + "<td>" + escapeHtml(row.volume_name || "") + "</td>"
        + "<td>" + escapeHtml(row.pool_or_cpg || "") + "</td>"
        + "<td>" + escapeHtml(row.status || "") + "</td>"
        + "</tr>"
      )).join("");
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

    async function refreshLive() {
      refreshBtn.disabled = true;
      statusEl.textContent = "Scanning live…";
      errorsEl.textContent = "";
      const cardId = siteSelectEl.value || "";
      const url = "/api/host-volume-health/live" + (cardId ? ("?card_id=" + encodeURIComponent(cardId)) : "");
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
        renderHosts(data.hosts || []);
        renderVolumes(data.volumes || []);
        renderErrors(data.errors || []);
        const hostCount = (data.hosts || []).length;
        const volCount = (data.volumes || []).length;
        const errCount = (data.errors || []).length;
        statusEl.textContent = "Found " + hostCount + " host(s) and " + volCount + " volume(s)."
          + (errCount ? (" " + errCount + " site error(s).") : "");
        const hasRows = hostCount + volCount > 0;
        exportXlsxBtn.disabled = !hasRows;
        exportCsvBtn.disabled = !hasRows;
      } catch (err) {
        statusEl.textContent = String(err && err.message ? err.message : err);
      } finally {
        refreshBtn.disabled = false;
      }
    }

    function exportUrl(format) {
      const cardId = siteSelectEl.value || "";
      let url = "/api/host-volume-health/export?format=" + encodeURIComponent(format) + "&open=1";
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
        const filename = match ? match[1] : ("Host_Volume_Health." + (format === "xlsx" ? "xlsx" : "zip"));
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
        URL.revokeObjectURL(link.href);
        statusEl.textContent = "Export saved.";
      } catch (err) {
        statusEl.textContent = String(err && err.message ? err.message : err);
      } finally {
        btn.disabled = false;
      }
    }

    refreshBtn.addEventListener("click", refreshLive);
    exportXlsxBtn.addEventListener("click", () => exportReport("xlsx"));
    exportCsvBtn.addEventListener("click", () => exportReport("csv"));
    siteSelectEl.addEventListener("change", () => {
      renderHosts([]);
      renderVolumes([]);
      errorsEl.textContent = "";
      exportXlsxBtn.disabled = true;
      exportCsvBtn.disabled = true;
      statusEl.textContent = "Site changed — click Refresh to scan again.";
    });
    loadSiteOptions();
  </script>
</body>
</html>"""
