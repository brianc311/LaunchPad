"""Storage Inventory report — live fleet inventory page."""

STORAGE_INVENTORY_PATH = "/storage-inventory"

STORAGE_INVENTORY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Storage Inventory</title>
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
      --issue-bg: #3d2024;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Segoe UI, Inter, Arial, sans-serif;
      background: radial-gradient(circle at top, #172033 0%, var(--bg) 45%);
      color: var(--text);
    }
    .wrap { max-width: 1400px; margin: 0 auto; padding: 28px 20px 48px; }
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
    .si-age-toggle { display: inline-flex; gap: 6px; }
    button.btn.secondary.si-age-btn.is-on {
      background: var(--accent); color: #111; border-color: var(--accent);
    }
    .site-issues th:nth-child(1),
    .site-issues td:nth-child(1),
    .site-issues th:nth-child(2),
    .site-issues td:nth-child(2) {
      min-width: 8rem;
      white-space: nowrap;
    }
    #si-progress-wrap { margin-top: 12px; max-width: 420px; }
    #si-progress-wrap[hidden] { display: none; }
    .si-progress-track {
      height: 8px; border-radius: 999px; background: #0f141d; border: 1px solid var(--border);
      overflow: hidden;
    }
    #si-progress-bar { height: 100%; width: 0; background: var(--accent); }
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
    .summary-grid {
      display: flex; flex-wrap: wrap; gap: 24px; margin-bottom: 4px;
    }
    .summary-item { font-size: 0.95rem; }
    .summary-item strong { color: var(--accent2); }
    a:not(.btn) {
      color: #9ec1ff;
      text-decoration: underline;
      text-underline-offset: 2px;
    }
    a:not(.btn):hover { color: #c5d9ff; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th, td { padding: 8px 10px; border-bottom: 1px solid var(--border); text-align: left; }
    th { color: var(--muted); font-weight: 600; }
    tr.row-issue td { background: var(--issue-bg); }
    .empty { color: var(--muted); font-style: italic; }
    .status { color: var(--muted); font-size: 0.9rem; margin-top: 8px; }
    .errors { color: var(--danger); font-size: 0.88rem; margin-top: 8px; white-space: pre-wrap; }
    .footer { color: var(--muted); font-size: 0.82rem; margin-top: 20px; }
    #si-sites { display: flex; flex-direction: column; gap: 10px; }
    .site-card {
      border: 1px solid var(--border);
      border-radius: 12px;
      border-left: 6px solid var(--border);
      background: var(--card);
    }
    .site-card.site-red { border-left-color: #e85d5d; background: #2a1618; }
    .site-card.site-orange { border-left-color: #e8a23c; background: #221c10; }
    .site-card.site-green { border-left-color: #3cb371; background: #14241a; }
    .site-card > summary.site-head {
      cursor: pointer;
      list-style: none;
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      padding: 12px 16px;
      font-weight: 600;
    }
    .site-card > summary.site-head::-webkit-details-marker { display: none; }
    .site-meta { color: var(--muted); font-weight: 500; font-size: 0.9rem; }
    .site-body { padding: 0 12px 12px; }
    .site-issues {
      margin-top: 10px;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 8px 12px;
    }
    .site-issues > summary { cursor: pointer; color: var(--accent2); font-weight: 600; }
    select {
      background: #0f141d; color: var(--text); border: 1px solid var(--border);
      border-radius: 10px; height: 34px; padding: 0 10px; font: inherit;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>Storage Inventory</h1>
      <p>Live fleet inventory (Phone Home, Data Protection, SMTP, Issues) for monitored FlashSystem, HPE, and DS8884 arrays. Unlock LaunchPad to Refresh live; cached results load automatically.</p>
      <div class="hero-actions">
        <label>Site <select id="siteFilter"><option value="">All Arrays</option></select></label>
        <div class="si-age-toggle" id="si-age-toggle" role="group" aria-label="Issue age">
          <button type="button" class="btn secondary si-age-btn is-on" id="si-age-recent" data-age="recent">Recent</button>
          <button type="button" class="btn secondary si-age-btn" id="si-age-older" data-age="older">Older</button>
          <button type="button" class="btn secondary si-age-btn" id="si-age-all" data-age="all">All</button>
        </div>
        <button type="button" class="btn" id="si-refresh-btn">Refresh live</button>
        <button type="button" class="btn secondary" id="si-export-btn" disabled>Export Excel</button>
        <a class="btn secondary" href="/">Home</a>
        <a class="btn secondary" href="/system-connectivity">System Connectivity</a>
        <a class="btn secondary" href="/host-volume-health">Hosts &amp; Volumes</a>
      </div>
      <div id="si-progress-wrap" hidden>
        <div class="si-progress-track"><div id="si-progress-bar"></div></div>
      </div>
      <div class="status" id="si-status">Loading cache…</div>
      <div class="errors" id="si-errors"></div>
    </div>

    <div class="section">
      <div class="summary-grid">
        <div class="summary-item"><strong>Total Devices:</strong> <span id="si-total-devices">0</span></div>
        <div class="summary-item"><strong>Devices with Issues:</strong> <span id="si-devices-with-issues">0</span></div>
      </div>
    </div>

    <div class="section">
      <h2>Inventory</h2>
      <div id="si-sites">
        <p class="empty">No data yet — click Refresh live.</p>
      </div>
    </div>

    <div class="footer">LaunchPad {{APP_VERSION}}</div>
  </div>
  <script>
    const siteFilterEl = document.getElementById("siteFilter");
    const refreshBtn = document.getElementById("si-refresh-btn");
    const exportBtn = document.getElementById("si-export-btn");
    const statusEl = document.getElementById("si-status");
    const errorsEl = document.getElementById("si-errors");
    const totalDevicesEl = document.getElementById("si-total-devices");
    const devicesWithIssuesEl = document.getElementById("si-devices-with-issues");
    const sitesEl = document.getElementById("si-sites");
    const BLANK_SITE_LABEL = "(no site)";
    let allRows = [];
    let knownSites = [];
    let hasCache = false;
    let ageMode = "recent";

    function escapeHtml(value) {
      return String(value == null ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function isIpv4(ip) {
      const parts = String(ip || "").trim().split(".");
      if (parts.length !== 4) {
        return false;
      }
      return parts.every((part) => {
        if (!/^[0-9]{1,3}$/.test(part)) {
          return false;
        }
        const n = Number(part);
        return n >= 0 && n <= 255;
      });
    }

    function ipLink(ip) {
      const trimmed = String(ip == null ? "" : ip).trim();
      if (!trimmed) {
        return "";
      }
      if (!isIpv4(trimmed)) {
        return escapeHtml(trimmed);
      }
      return '<a href="https://' + escapeHtml(trimmed) + '" target="_blank" rel="noopener">'
        + escapeHtml(trimmed) + "</a>";
    }

    function volumeProtectionDisplay(row) {
      const text = String(row.volume_protection || "").trim();
      return text || "unknown";
    }

    function notesFor(row) {
      if (ageMode === "older") {
        return String(row.issues_older || "");
      }
      if (ageMode === "all") {
        return String(row.issues || "");
      }
      if (row.issues_recent != null && row.issues_recent !== undefined) {
        return String(row.issues_recent || "");
      }
      return String(row.issues || "");
    }

    function rowHasIssues(row) {
      return Boolean(notesFor(row).trim());
    }

    function siteLabel(row) {
      const text = String(row.site || "").trim();
      return text || BLANK_SITE_LABEL;
    }

    function rowHasUnknown(row) {
      const fields = [row.phone_home, row.data_protection, row.smtp, volumeProtectionDisplay(row)];
      return fields.some((value) => String(value || "").trim().toLowerCase() === "unknown");
    }

    function siteStatus(rows) {
      if (rows.some(rowHasIssues)) {
        return "red";
      }
      if (rows.some(rowHasUnknown)) {
        return "orange";
      }
      return "green";
    }

    function groupRowsBySite(rows) {
      const buckets = {};
      rows.forEach((row) => {
        const label = siteLabel(row);
        if (!buckets[label]) {
          buckets[label] = [];
        }
        buckets[label].push(row);
      });
      return Object.keys(buckets).sort((a, b) => a.localeCompare(b)).map((name) => [name, buckets[name]]);
    }

    function renderDeviceRows(rows) {
      return rows.map((row) => (
        "<tr>"
        + "<td>" + escapeHtml(row.host || "") + "</td>"
        + "<td>" + ipLink(row.ip) + "</td>"
        + "<td>" + escapeHtml(row.model || "") + "</td>"
        + "<td>" + escapeHtml(row.serial || "") + "</td>"
        + "<td>" + escapeHtml(row.location || "") + "</td>"
        + "<td>" + escapeHtml(row.phone_home || "") + "</td>"
        + "<td>" + escapeHtml(row.data_protection || "") + "</td>"
        + "<td>" + escapeHtml(volumeProtectionDisplay(row)) + "</td>"
        + "<td>" + escapeHtml(row.smtp || "") + "</td>"
        + "</tr>"
      )).join("");
    }

    function renderIssuesBlock(rows) {
      const issueRows = rows.filter(rowHasIssues);
      if (!issueRows.length) {
        return "";
      }
      const body = issueRows.map((row) => (
        "<tr>"
        + "<td>" + escapeHtml(row.host || "") + "</td>"
        + "<td>" + ipLink(row.ip) + "</td>"
        + "<td>" + escapeHtml(notesFor(row)) + "</td>"
        + "</tr>"
      )).join("");
      return (
        '<details class="site-issues">'
        + "<summary>Issues / Notes (" + issueRows.length + ")</summary>"
        + '<div class="table-wrap"><table>'
        + "<thead><tr><th>Host</th><th>IP Address</th><th>Issues / Notes</th></tr></thead>"
        + "<tbody>" + body + "</tbody>"
        + "</table></div>"
        + "</details>"
      );
    }

    function renderSites(rows) {
      if (!rows.length) {
        sitesEl.innerHTML = '<p class="empty">No inventory rows found.</p>';
        return;
      }
      sitesEl.innerHTML = groupRowsBySite(rows).map(([name, siteRows]) => {
        const status = siteStatus(siteRows);
        const issueCount = siteRows.filter(rowHasIssues).length;
        let meta = siteRows.length + " device" + (siteRows.length === 1 ? "" : "s");
        if (issueCount) {
          meta += " · " + issueCount + " with issues";
        }
        return (
          '<details class="site-card site-' + status + '">'
          + '<summary class="site-head"><span>' + escapeHtml(name) + "</span>"
          + '<span class="site-meta">' + escapeHtml(meta) + "</span></summary>"
          + '<div class="site-body"><div class="table-wrap"><table>'
          + "<thead><tr>"
          + "<th>Host</th><th>IP Address</th><th>Model</th><th>Serial Number (SN)</th>"
          + "<th>Location</th><th>Phone Home</th><th>Data Protection</th><th>Volume Protection</th><th>SMTP IP(s)</th>"
          + "</tr></thead>"
          + "<tbody>" + renderDeviceRows(siteRows) + "</tbody>"
          + "</table></div>"
          + renderIssuesBlock(siteRows)
          + "</div></details>"
        );
      }).join("");
    }

    function filteredRows() {
      const site = siteFilterEl.value || "";
      if (!site) {
        return allRows.slice();
      }
      return allRows.filter((row) => String(row.site || "") === site);
    }

    function updateSiteFilterOptions() {
      const fromRows = allRows.map((row) => String(row.site || "").trim()).filter(Boolean);
      const sites = Array.from(new Set(knownSites.concat(fromRows))).sort((a, b) => a.localeCompare(b));
      const current = siteFilterEl.value || "";
      siteFilterEl.innerHTML = '<option value="">All Arrays</option>' + sites.map((site) => (
        '<option value="' + escapeHtml(site) + '">' + escapeHtml(site) + "</option>"
      )).join("");
      if (current && sites.includes(current)) {
        siteFilterEl.value = current;
      }
    }

    function updateSummary(rows) {
      const total = rows.length;
      const withIssues = rows.filter((row) => rowHasIssues(row)).length;
      totalDevicesEl.textContent = String(total);
      devicesWithIssuesEl.textContent = String(withIssues);
    }

    function renderErrors(errors) {
      if (!errors || !errors.length) {
        errorsEl.textContent = "";
        return;
      }
      errorsEl.textContent = errors.map((entry) => (
        (entry.card_name || entry.card_id || entry.site || "Site") + ": " + (entry.error || "error")
      )).join("\\n");
    }

    function renderAll() {
      const rows = filteredRows();
      renderSites(rows);
      updateSummary(rows);
    }

    function setExportEnabled(enabled) {
      exportBtn.disabled = !enabled;
    }

    function applyPayload(data) {
      allRows = Array.isArray(data.rows) ? data.rows : [];
      updateSiteFilterOptions();
      renderAll();
      renderErrors(data.errors || []);
      hasCache = allRows.length > 0;
      setExportEnabled(hasCache);
      const generated = String(data.generated_at || "").trim();
      const errCount = (data.errors || []).length;
      let statusText = "Showing " + allRows.length + " device(s).";
      if (generated) {
        statusText += " Cache from " + generated + ".";
      }
      if (errCount) {
        statusText += " " + errCount + " site error(s).";
      }
      statusEl.textContent = statusText;
    }

    async function loadCache() {
      statusEl.textContent = "Loading cache…";
      try {
        const res = await fetch("/api/storage-inventory/cache");
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          statusEl.textContent = data.error || ("Cache load failed (" + res.status + ")");
          return;
        }
        applyPayload(data);
        if (!allRows.length) {
          statusEl.textContent =
            "No FlashSystem / 3PAR inventory yet — unlock LaunchPad and click Refresh live.";
        }
      } catch (err) {
        statusEl.textContent = String(err && err.message ? err.message : err);
      }
    }

    const progressWrap = document.getElementById("si-progress-wrap");
    const progressBar = document.getElementById("si-progress-bar");
    document.getElementById("si-age-toggle").addEventListener("click", (event) => {
      const btn = event.target.closest("[data-age]");
      if (!btn) {
        return;
      }
      ageMode = btn.getAttribute("data-age") || "recent";
      document.querySelectorAll(".si-age-btn").forEach((el) => {
        if (el.getAttribute("data-age") === ageMode) {
          el.classList.add("is-on");
        } else {
          el.classList.remove("is-on");
        }
      });
      renderAll();
    });

    let progressTimer = null;
    let progressActive = false;

    function hideProgress() {
      progressActive = false;
      if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
      }
      progressWrap.hidden = true;
      progressBar.style.width = "0%";
    }

    function applyProgress(data) {
      if (!progressActive) {
        return;
      }
      const total = Number(data && data.total) || 0;
      const done = Number(data && data.done) || 0;
      const current = String((data && data.current) || "").trim();
      progressWrap.hidden = false;
      const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
      progressBar.style.width = pct + "%";
      let label = "Scanning live…";
      if (total > 0) {
        label = done + " / " + total + " arrays";
        if (current) {
          label += " · " + current;
        }
      }
      statusEl.textContent = label;
    }

    async function pollProgress() {
      try {
        const res = await fetch("/api/storage-inventory/progress");
        if (!progressActive) {
          return;
        }
        const data = await res.json().catch(() => ({}));
        if (!progressActive) {
          return;
        }
        applyProgress(data);
      } catch (_err) {
        /* ignore poll errors while live request is in flight */
      }
    }

    async function refreshLive() {
      refreshBtn.disabled = true;
      errorsEl.textContent = "";
      progressActive = true;
      applyProgress({done:0,total:0,current:""});
      progressTimer = setInterval(pollProgress, 400);
      pollProgress();
      try {
        const res = await fetch("/api/storage-inventory/live");
        const data = await res.json().catch(() => ({}));
        if (res.status === 403) {
          hideProgress();
          statusEl.textContent = data.error || "Unlock LaunchPad to refresh live.";
          return;
        }
        if (!res.ok) {
          statusEl.textContent = data.error || ("Refresh failed (" + res.status + ")");
          return;
        }
        applyPayload(data);
        if (!allRows.length) {
          statusEl.textContent =
            "No FlashSystem, 3PAR, or DS8884 SSH cards found. Set Device Profile on those array cards in Admin, then Refresh live.";
        }
      } catch (err) {
        statusEl.textContent = String(err && err.message ? err.message : err);
      } finally {
        hideProgress();
        refreshBtn.disabled = false;
      }
    }

    async function exportExcel() {
      exportBtn.disabled = true;
      statusEl.textContent = "Exporting Excel…";
      try {
        const res = await fetch("/api/storage-inventory/export?format=xlsx&open=1");
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
        const filename = match ? match[1] : "Storage_Inventory.xlsx";
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
        URL.revokeObjectURL(link.href);
        statusEl.textContent = "Export saved.";
      } catch (err) {
        statusEl.textContent = String(err && err.message ? err.message : err);
      } finally {
        exportBtn.disabled = !hasCache;
      }
    }

    async function loadSiteOptions() {
      try {
        const res = await fetch("/api/cards");
        if (!res.ok) return;
        const cards = await res.json();
        knownSites = (Array.isArray(cards) ? cards : [])
          .map((card) => String(card.name || "").trim())
          .filter(Boolean);
        knownSites.sort((a, b) => a.localeCompare(b));
        updateSiteFilterOptions();
      } catch (_err) {
        /* ignore */
      }
    }

    siteFilterEl.addEventListener("change", renderAll);
    refreshBtn.addEventListener("click", refreshLive);
    exportBtn.addEventListener("click", exportExcel);
    loadSiteOptions();
    loadCache();
  </script>
</body>
</html>"""
