"""All-sites capacity report page (print-friendly)."""

CAPACITY_REPORT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Capacity Report</title>
  <style>
    :root {
      --bg: #0b0f14;
      --panel: #121821;
      --text: #e8edf5;
      --muted: #8b98ab;
      --accent: #ff6b00;
      --accent2: #ff8533;
      --warn: #f59e0b;
      --bad: #ef4444;
      --border: #2a3444;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Segoe UI, Inter, Arial, sans-serif;
      background: radial-gradient(circle at top, #172033 0%, var(--bg) 45%);
      color: var(--text);
      min-height: 100vh;
    }
    .wrap { max-width: 900px; margin: 0 auto; padding: 28px 20px 48px; }
    .hero {
      background: linear-gradient(135deg, #1a2230 0%, #101722 100%);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 24px 28px;
      margin-bottom: 24px;
    }
    .hero h1 { margin: 0 0 6px; color: var(--accent); font-size: 2rem; }
    .hero p { margin: 0; color: var(--muted); }
    a:not(.btn) {
      color: #9ec1ff;
      text-decoration: underline;
      text-underline-offset: 2px;
    }
    a:not(.btn):hover { color: #c5d9ff; }
    .report-hero-header { margin-bottom: 4px; }
    .report-title-input,
    .report-subtitle-input,
    .site-name-input {
      font: inherit;
      color: inherit;
      background: transparent;
      border: 1px dashed transparent;
      border-radius: 8px;
      width: 100%;
      padding: 4px 8px;
      margin: 0 0 4px;
    }
    .report-title-input {
      color: var(--accent);
      font-size: 2rem;
      font-weight: 700;
    }
    .report-subtitle-input {
      color: var(--muted);
      font-size: 1rem;
    }
    .site-name-input {
      color: var(--accent2);
      font-size: 1.45rem;
      font-weight: 700;
      margin-bottom: 4px;
    }
    .report-title-input:hover,
    .report-subtitle-input:hover,
    .site-name-input:hover,
    .report-title-input:focus,
    .report-subtitle-input:focus,
    .site-name-input:focus {
      border-color: var(--border);
      outline: none;
      background: rgba(15, 20, 29, 0.55);
    }
    .rename-hint {
      color: var(--muted);
      font-size: 0.78rem;
      margin: 0 0 8px;
    }
    body.hide-report-title-print .report-hero-header {
      display: none;
    }
    .hero-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      margin-top: 16px;
    }
    .refresh-status { color: var(--muted); font-size: 0.9rem; }
    #cap-progress-wrap { margin-top: 12px; max-width: 420px; }
    #cap-progress-wrap[hidden] { display: none; }
    .cap-progress-track {
      height: 8px; border-radius: 999px; background: #0f141d; border: 1px solid var(--border);
      overflow: hidden;
    }
    #cap-progress-bar { height: 100%; width: 0; background: var(--accent); }
    .print-meta { color: var(--muted); font-size: 0.88rem; margin-top: 10px; }
    button, a.btn {
      font: inherit;
      border-radius: 10px;
      height: 36px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      text-decoration: none;
      padding: 0 16px;
      font-weight: 600;
    }
    button {
      background: var(--accent);
      color: #111;
      border: none;
    }
    button:hover { background: var(--accent2); }
    button:disabled { opacity: 0.55; cursor: wait; }
    button.secondary, a.btn.secondary {
      background: #0f141d;
      color: var(--text);
      border: 1px solid var(--border);
    }
    button.secondary:hover, a.btn.secondary:hover {
      border-color: var(--accent);
      color: var(--accent2);
    }
    .site-block {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 22px 24px 24px;
      margin-bottom: 24px;
    }
    .site-block.fail { border-color: rgba(239, 68, 68, 0.45); }
    .site-block.loading { opacity: 0.72; }
    .site-block.monitor-off { opacity: 0.6; }
    .site-block.monitor-off .capacity-section,
    .site-block.monitor-off .capacity-pools-wrap,
    .site-block.monitor-off .table-wrap,
    .site-block.monitor-off .metric,
    .site-block.monitor-off .cmd-summary,
    .site-block.monitor-off .raw-output {
      filter: grayscale(0.7);
    }
    .monitor-toggle {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.85rem;
      color: var(--muted);
      cursor: pointer;
      user-select: none;
      margin-top: 8px;
      margin-right: 14px;
    }
    .monitor-toggle input { width: 15px; height: 15px; accent-color: var(--accent); cursor: pointer; }
    .monitor-toggle.on { color: #4ade80; }
    .dell-include-toggle.on { color: var(--accent); }
    .paused-note {
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 0.82rem;
      font-style: italic;
    }
    .site-head {
      margin-bottom: 16px;
      padding-bottom: 14px;
      border-bottom: 1px solid var(--border);
    }
    .site-head h2 {
      margin: 0 0 4px;
      color: var(--accent2);
      font-size: 1.45rem;
    }
    .site-head .host { color: var(--muted); font-size: 0.92rem; margin: 0; }
    .site-head .updated { color: var(--muted); font-size: 0.82rem; margin: 8px 0 0; }
    .cmd-summary {
      margin: 0 0 10px;
      color: #4ade80;
      font-weight: 600;
      font-size: 0.95rem;
    }
    .metric { margin-top: 8px; }
    .metric-head {
      display: flex;
      justify-content: space-between;
      margin-bottom: 6px;
      font-size: 0.9rem;
    }
    .bar {
      height: 10px;
      background: #0b0f14;
      border-radius: 999px;
      overflow: hidden;
      border: 1px solid var(--border);
    }
    .fill { height: 100%; border-radius: 999px; background: var(--accent); }
    .sub { color: var(--muted); font-size: 0.82rem; margin-top: 6px; }
    .capacity-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin: 16px 0 0;
    }
    .card {
      background: #0f141d;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
    }
    .card h3 { margin: 0 0 10px; font-size: 0.95rem; color: var(--accent2); }
    .stat { font-size: 1.75rem; font-weight: 700; margin-bottom: 4px; }
    .stat-label { color: var(--muted); font-size: 0.85rem; }
    .table-wrap {
      overflow-x: auto;
      margin-top: 14px;
      border: 1px solid var(--border);
      border-radius: 10px;
    }
    .data-table {
      width: 100%;
      border-collapse: collapse;
      font-family: Consolas, monospace;
      font-size: 0.76rem;
    }
    .data-table th,
    .data-table td {
      border-bottom: 1px solid var(--border);
      padding: 7px 10px;
      text-align: left;
      vertical-align: top;
    }
    .data-table th {
      color: var(--muted);
      font-weight: 500;
    }
    .kv-table th {
      width: 220px;
    }
    .data-table.df-table {
      table-layout: auto;
      min-width: 520px;
    }
    .data-table.df-table th,
    .data-table.df-table td {
      white-space: nowrap;
      min-width: 4.5rem;
      width: auto;
    }
    .data-table.df-table th:first-child,
    .data-table.df-table td:first-child {
      min-width: 8rem;
    }
    .data-table td { color: #d7e0ef; word-break: break-word; }
    .error {
      background: rgba(239, 68, 68, 0.12);
      border: 1px solid rgba(239, 68, 68, 0.35);
      color: #fecaca;
      border-radius: 10px;
      padding: 12px 14px;
      font-size: 0.9rem;
      white-space: pre-wrap;
    }
    .fleet-capacity-alert {
      border-radius: 14px;
      padding: 16px 18px;
      margin-bottom: 20px;
      border: 2px solid rgba(239, 68, 68, 0.55);
      background: rgba(239, 68, 68, 0.16);
      color: #fecaca;
    }
    .fleet-capacity-alert.warn {
      border-color: rgba(245, 158, 11, 0.55);
      background: rgba(245, 158, 11, 0.14);
      color: #fde68a;
    }
    .fleet-capacity-alert .alert-title {
      margin: 0 0 8px;
      font-size: 1.15rem;
      font-weight: 800;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    .fleet-capacity-alert ul {
      margin: 0;
      padding-left: 1.2rem;
    }
    .fleet-capacity-alert li { margin: 4px 0; }
    .capacity-alert {
      border-radius: 12px;
      padding: 14px 16px;
      margin: 0 0 16px;
      border: 2px solid rgba(239, 68, 68, 0.55);
      background: rgba(239, 68, 68, 0.14);
      color: #fecaca;
    }
    .capacity-alert.warn {
      border-color: rgba(245, 158, 11, 0.55);
      background: rgba(245, 158, 11, 0.12);
      color: #fde68a;
    }
    .capacity-alert-label {
      display: inline-block;
      margin: 0 0 8px;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 0.85rem;
      font-weight: 800;
      letter-spacing: 0.06em;
      background: rgba(239, 68, 68, 0.35);
      color: #fff;
    }
    .capacity-alert.warn .capacity-alert-label {
      background: rgba(245, 158, 11, 0.4);
      color: #111;
    }
    .capacity-alert ul {
      margin: 0;
      padding-left: 1.15rem;
    }
    .capacity-alert li { margin: 3px 0; font-size: 0.92rem; }
    .site-block.capacity-critical {
      border-color: rgba(239, 68, 68, 0.65);
      box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.25);
    }
    .site-block.capacity-warn {
      border-color: rgba(245, 158, 11, 0.55);
    }
    .empty { color: var(--muted); padding: 32px; text-align: center; }
    .footer { margin-top: 8px; color: var(--muted); font-size: 0.85rem; }
    .toggle-row {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 0 14px;
      height: 36px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: #0f141d;
      color: var(--text);
      font-size: 0.9rem;
      cursor: pointer;
      user-select: none;
    }
    .toggle-row input {
      width: 16px;
      height: 16px;
      accent-color: var(--accent);
      cursor: pointer;
    }
    .options-menu {
      position: relative;
      display: inline-flex;
      align-items: center;
    }
    .options-menu-panel {
      position: absolute;
      top: calc(100% + 6px);
      left: 0;
      z-index: 40;
      min-width: 280px;
      max-width: min(420px, 92vw);
      padding: 10px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: #121821;
      box-shadow: 0 12px 28px rgba(0, 0, 0, 0.45);
      display: none;
      flex-direction: column;
      gap: 8px;
    }
    .options-menu.open .options-menu-panel { display: flex; }
    .options-menu-panel .toggle-row {
      width: 100%;
      justify-content: flex-start;
      height: auto;
      min-height: 36px;
      padding: 8px 12px;
    }
    #options-menu-btn[aria-expanded="true"] {
      border-color: var(--accent);
      color: var(--accent2);
    }
    body.hide-capacity-details .capacity-detail-section {
      display: none;
    }
    body.hide-raw-capacity .capacity-raw-wrap {
      display: none;
    }
    .capacity-pools-wrap {
      margin-top: 8px;
      display: none;
    }
    body.show-pools-ibm .site-block[data-pool-family="ibm"] .capacity-pools-wrap,
    body.show-pools-hpe .site-block[data-pool-family="hpe"] .capacity-pools-wrap,
    body.show-pools-dell .site-block[data-pool-family="dell"] .capacity-pools-wrap {
      display: block;
    }
    .capacity-pool-block {
      margin-top: 20px;
      padding-top: 18px;
      border-top: 1px solid var(--border);
    }
    @media print {
      body {
        background: #fff;
        color: #111;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }
      .wrap { max-width: none; padding: 0; }
      .no-print { display: none !important; }
      .hero {
        background: none;
        border: none;
        border-bottom: 2px solid #ff6b00;
        border-radius: 0;
        padding: 0 0 12px;
        margin-bottom: 20px;
      }
      .hero h1 { color: #111; font-size: 1.6rem; }
      .hero p, .print-meta { color: #444; }
      .report-title-input {
        color: #111;
        font-size: 1.6rem;
        border: none;
        background: transparent;
        padding: 0;
      }
      .report-subtitle-input {
        color: #444;
        border: none;
        background: transparent;
        padding: 0;
      }
      .site-name-input {
        color: #111;
        border: none;
        background: transparent;
        padding: 0;
      }
      .rename-hint { display: none; }
      .site-block {
        background: #fff;
        border: 1px solid #ccc;
        border-radius: 8px;
        page-break-inside: avoid;
        break-inside: avoid;
        margin-bottom: 18px;
      }
      body.one-site-per-page .site-block:not(:last-child) {
        page-break-after: always;
        break-after: page;
      }
      .site-head h2 { color: #111; }
      .site-head .host, .site-head .updated { color: #555; }
      .cmd-summary { color: #166534; }
      .card {
        background: #f8fafc;
        border-color: #ddd;
      }
      .card h3 { color: #c2410c; }
      .stat { color: #111; }
      .stat-label, .sub { color: #555; }
      .bar { background: #eee; border-color: #ccc; }
      .data-table th { color: #555; }
      .data-table td { color: #111; }
      .footer { display: none; }
    }
  </style>
</head>
<body class="one-site-per-page">
  <div class="wrap">
    <section class="hero">
      <div class="report-hero-header">
        <input
          type="text"
          id="report-title-input"
          class="report-title-input"
          value="LaunchPad Capacity Report"
          aria-label="Report title"
        >
        <input
          type="text"
          id="report-subtitle-input"
          class="report-subtitle-input"
          value="All monitored storage sites — capacity stats stacked for review and PDF export."
          aria-label="Report subtitle"
        >
      </div>
      <p class="rename-hint no-print">Click the report title, subtitle, or any site name below to rename for this report and printout.</p>
      <div class="hero-actions no-print">
        <div class="options-menu" id="options-menu">
          <button type="button" id="options-menu-btn" class="secondary" aria-expanded="false" aria-controls="options-menu-panel" title="Choose one or more display and monitoring options.">View options</button>
          <div id="options-menu-panel" class="options-menu-panel" role="group" aria-label="View options">
            <label class="toggle-row" for="monitor-all-toggle" title="Connect over SSH only for sites you turn on.">
              <input type="checkbox" id="monitor-all-toggle">
              All monitoring on
            </label>
            <label class="toggle-row" for="show-details-toggle">
              <input type="checkbox" id="show-details-toggle" checked>
              Show system details
            </label>
            <label class="toggle-row" for="one-page-toggle">
              <input type="checkbox" id="one-page-toggle" checked>
              One site per page
            </label>
            <label class="toggle-row" for="show-pools-ibm-toggle" title="Show IBM mdiskgrp / pool blocks on this page and print.">
              <input type="checkbox" id="show-pools-ibm-toggle">
              Show IBM pools
            </label>
            <label class="toggle-row" for="show-pools-hpe-toggle" title="Show HPE CPG / pool blocks on this page and print.">
              <input type="checkbox" id="show-pools-hpe-toggle">
              Show HPE CPGs / pools
            </label>
            <label class="toggle-row" for="show-pools-dell-toggle" title="Show Dell pool blocks on this page and print.">
              <input type="checkbox" id="show-pools-dell-toggle">
              Show Dell pools
            </label>
            <label class="toggle-row" for="show-raw-toggle">
              <input type="checkbox" id="show-raw-toggle">
              Show raw capacity
            </label>
            <label class="toggle-row" for="show-title-toggle">
              <input type="checkbox" id="show-title-toggle" checked>
              Show report title on print
            </label>
            <label class="toggle-row" for="include-off-toggle" title="When unchecked, sites with Monitor off are hidden on this page and omitted from Excel. Does not add no-capacity sites to Dell Report — use the Dell Report checkbox on each site card for that.">
              <input type="checkbox" id="include-off-toggle">
              Include monitoring-off sites
            </label>
          </div>
        </div>
        <button type="button" id="print-btn">Print / Save PDF</button>
        <button type="button" id="refresh-all-btn">Refresh On Sites</button>
        <button type="button" id="excel-btn" class="secondary">Export Excel</button>
        <button type="button" id="dell-report-btn" class="secondary" style="display:none">Dell Report</button>
        <label class="toggle-row" id="dell-include-noss-wrap" for="dell-include-noss-toggle" style="display:none" title="When checked, every IBM/HPE site without live capacity / with SSH failure is included on Dell Report (blank capacity cells). Uncheck to clear those includes.">
          <input type="checkbox" id="dell-include-noss-toggle">
          Include no-SSH on Dell Report
        </label>
        <label>Site <select id="capacity-site-select"><option value="">All servers</option></select></label>
        <a class="btn secondary" href="/fc-wwpn">FC WWPN</a>
        <a class="btn secondary" href="/volume-find">Host / Volume Find</a>
        <a class="btn secondary" href="/host-volume-health">Hosts & Volumes</a>
        <a class="btn secondary" href="/system-connectivity">System Connectivity</a>
        <a class="btn secondary" href="/snapshot-schedule">Snapshot Schedule</a>
        <a class="btn secondary" href="/fc-consistgrp">FlashCopy CGs</a>
        <a class="btn secondary" href="/">Health Dashboard</a>
        <span id="refresh-status" class="refresh-status"></span>
      </div>
      <div id="cap-progress-wrap" hidden>
        <div class="cap-progress-track"><div id="cap-progress-bar"></div></div>
      </div>
      <p id="print-meta" class="print-meta"></p>
    </section>
    <div id="fleet-alerts"></div>
    <div id="sites"></div>
    <p class="footer no-print">
      LaunchPad Capacity v{{APP_VERSION}} · Keep LaunchPad running and unlocked while refreshing.
      Use <strong>Print / Save PDF</strong> and choose &ldquo;Save as PDF&rdquo; in the print dialog.
    </p>
  </div>
  <script>
    const sitesEl = document.getElementById("sites");
    const fleetAlertsEl = document.getElementById("fleet-alerts");
    const refreshStatusEl = document.getElementById("refresh-status");
    const progressWrap = document.getElementById("cap-progress-wrap");
    const progressBar = document.getElementById("cap-progress-bar");
    let progressActive = false;

    function hideProgress() {
      progressActive = false;
      if (progressWrap) progressWrap.hidden = true;
      if (progressBar) progressBar.style.width = "0%";
    }

    function applyProgress(done, total, current) {
      if (!progressActive) {
        return;
      }
      if (progressWrap) progressWrap.hidden = false;
      const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
      if (progressBar) progressBar.style.width = pct + "%";
      let label = done + " / " + total + " arrays";
      const name = String(current || "").trim();
      if (name) {
        label += " · " + name;
      }
      if (refreshStatusEl) refreshStatusEl.textContent = label;
    }

    const refreshAllBtn = document.getElementById("refresh-all-btn");
    const monitorAllToggle = document.getElementById("monitor-all-toggle");
    const printBtn = document.getElementById("print-btn");
    const printMetaEl = document.getElementById("print-meta");
    const showDetailsToggle = document.getElementById("show-details-toggle");
    const onePageToggle = document.getElementById("one-page-toggle");
    const showPoolsIbmToggle = document.getElementById("show-pools-ibm-toggle");
    const showPoolsHpeToggle = document.getElementById("show-pools-hpe-toggle");
    const showPoolsDellToggle = document.getElementById("show-pools-dell-toggle");
    const showRawToggle = document.getElementById("show-raw-toggle");
    const showTitleToggle = document.getElementById("show-title-toggle");
    const includeOffToggle = document.getElementById("include-off-toggle");
    const capacitySiteSelectEl = document.getElementById("capacity-site-select");
    const excelBtn = document.getElementById("excel-btn");
    const dellReportBtn = document.getElementById("dell-report-btn");
    const dellIncludeNoSshToggle = document.getElementById("dell-include-noss-toggle");
    const dellIncludeNoSshWrap = document.getElementById("dell-include-noss-wrap");
    const optionsMenu = document.getElementById("options-menu");
    const optionsMenuBtn = document.getElementById("options-menu-btn");
    const optionsMenuPanel = document.getElementById("options-menu-panel");
    const reportTitleInput = document.getElementById("report-title-input");
    const reportSubtitleInput = document.getElementById("report-subtitle-input");
    const DETAILS_PREF_KEY = "launchpad.capacityReport.showDetails";
    const ONE_PAGE_PREF_KEY = "launchpad.capacityReport.oneSitePerPage";
    const POOLS_IBM_PREF_KEY = "launchpad.capacityReport.showPoolsIbm";
    const POOLS_HPE_PREF_KEY = "launchpad.capacityReport.showPoolsHpe";
    const POOLS_DELL_PREF_KEY = "launchpad.capacityReport.showPoolsDell";
    const RAW_PREF_KEY = "launchpad.capacityReport.showRaw";
    const TITLE_PREF_KEY = "launchpad.capacityReport.title";
    const SUBTITLE_PREF_KEY = "launchpad.capacityReport.subtitle";
    const SHOW_TITLE_PRINT_KEY = "launchpad.capacityReport.showTitlePrint";
    const SITE_NAMES_PREF_KEY = "launchpad.capacityReport.siteNames";
    const DEFAULT_TITLE = "LaunchPad Capacity Report";
    const DEFAULT_SUBTITLE =
      "All monitored storage sites — capacity stats stacked for review and PDF export.";
    let refreshAllRunning = false;
    let cardsCache = [];
    let siteNameOverrides = {};
    let monitorServerState = {};
    let dellIncludeIds = new Set();

    function isDellReportFamily(card) {
      const family = (card.dell_report_family || "").toLowerCase();
      if (family === "ibm" || family === "hp") return true;
      const p = (card.device_profile || "").toLowerCase();
      return /flashsystem|storwize|svc|xiv|ds8|ibm_|hpe|3par|primera|^hp_/.test(p);
    }

    function isDellIncludeOn(cardId) {
      return dellIncludeIds.has(String(cardId));
    }

    async function loadDellIncludeState() {
      try {
        const res = await fetch("/api/dell-report-settings");
        const data = await res.json();
        dellIncludeIds = new Set(
          (data.include_card_ids || []).map((id) => String(id))
        );
      } catch (_err) {
        dellIncludeIds = new Set();
      }
    }

    async function persistDellInclude(cardId, on) {
      const key = String(cardId);
      if (on) dellIncludeIds.add(key);
      else dellIncludeIds.delete(key);
      const res = await fetch("/api/dell-report-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ card_id: cardId, include: on }),
      });
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          const err = await res.json();
          if (err && err.error) detail = err.error;
        } catch (_err) {
          /* ignore */
        }
        if (on) dellIncludeIds.delete(key);
        else dellIncludeIds.add(key);
        throw new Error(detail);
      }
      const data = await res.json();
      dellIncludeIds = new Set(
        (data.include_card_ids || []).map((id) => String(id))
      );
    }

    function setDellInclude(cardId, on) {
      void persistDellInclude(cardId, on)
        .then(() => {
          const section = document.querySelector(`.site-block[data-id="${cardId}"]`);
          if (!section) return;
          const toggle = section.querySelector(".dell-include-toggle");
          const input = section.querySelector(".dell-include-switch");
          if (toggle) toggle.classList.toggle("on", isDellIncludeOn(cardId));
          if (input) input.checked = isDellIncludeOn(cardId);
          syncNoSshDellToggle();
        })
        .catch((err) => {
          if (refreshStatusEl) {
            refreshStatusEl.textContent = `Dell Report include failed: ${err.message || err}`;
          }
          const section = document.querySelector(`.site-block[data-id="${cardId}"]`);
          const input = section && section.querySelector(".dell-include-switch");
          if (input) input.checked = isDellIncludeOn(cardId);
          syncNoSshDellToggle();
        });
    }

    function noSshDellCandidates(cards) {
      return (cards || []).filter((card) => {
        if (!isDellReportFamily(card)) return false;
        const hasCapacity = Boolean(card.capacity_popup_html);
        const hasSummary =
          card.capacity_summary && Number(card.capacity_summary.total_bytes || 0) > 0;
        const hasRaw =
          card.raw_capacity_summary &&
          Number(card.raw_capacity_summary.total_bytes || 0) > 0;
        return Boolean(card.error) || !(hasCapacity || hasSummary || hasRaw);
      });
    }

    async function setNoSshDellInclude(on) {
      if (!dellIncludeNoSshToggle) return;
      const candidates = noSshDellCandidates(cardsCache);
      if (!candidates.length) {
        dellIncludeNoSshToggle.checked = false;
        if (refreshStatusEl) {
          refreshStatusEl.textContent =
            "No IBM/HPE sites without capacity found for Dell Report include.";
        }
        return;
      }
      dellIncludeNoSshToggle.disabled = true;
      if (refreshStatusEl) {
        refreshStatusEl.textContent = on
          ? `Adding ${candidates.length} no-SSH site(s) to Dell Report…`
          : `Clearing Dell Report include on ${candidates.length} no-SSH site(s)…`;
      }
      let ok = 0;
      let failed = 0;
      for (const card of candidates) {
        try {
          await persistDellInclude(card.id, on);
          ok += 1;
        } catch (_err) {
          failed += 1;
        }
      }
      renderAll(cardsCache);
      syncNoSshDellToggle();
      if (refreshStatusEl) {
        refreshStatusEl.textContent = on
          ? `Dell Report include: ${ok} site(s) checked` +
            (failed ? `, ${failed} failed` : "") +
            ". Click Dell Report to export (capacity blank for those rows)."
          : `Dell Report include cleared on ${ok} no-SSH site(s)` +
            (failed ? `, ${failed} failed` : "") +
            ".";
      }
      dellIncludeNoSshToggle.disabled = false;
    }

    function syncNoSshDellToggle() {
      if (!dellIncludeNoSshToggle) return;
      const candidates = noSshDellCandidates(cardsCache);
      if (!candidates.length) {
        dellIncludeNoSshToggle.checked = false;
        return;
      }
      dellIncludeNoSshToggle.checked = candidates.every((card) =>
        isDellIncludeOn(card.id)
      );
    }

    function updateViewOptionsButton() {
      if (!optionsMenuBtn || !optionsMenuPanel) return;
      const boxes = optionsMenuPanel.querySelectorAll('input[type="checkbox"]');
      const onCount = Array.from(boxes).filter((box) => box.checked).length;
      optionsMenuBtn.textContent =
        onCount > 0 ? `View options (${onCount})` : "View options";
    }

    function setOptionsMenuOpen(open) {
      if (!optionsMenu || !optionsMenuBtn) return;
      optionsMenu.classList.toggle("open", open);
      optionsMenuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    }

    function isMonitorOn(cardId) {
      const key = String(cardId);
      if (Object.prototype.hasOwnProperty.call(monitorServerState, key)) {
        return Boolean(monitorServerState[key]);
      }
      return false;
    }

    async function persistMonitor(cardId, on, syncServer = true) {
      monitorServerState[String(cardId)] = on;
      if (!syncServer) return;
      try {
        await fetch("/api/monitor", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ card_id: cardId, enabled: on }),
        });
      } catch (_err) {
        /* best effort */
      }
    }

    async function loadMonitorState() {
      try {
        const res = await fetch("/api/monitor");
        if (!res.ok) return;
        const data = await res.json();
        monitorServerState = data.states || {};
      } catch (_err) {
        /* best effort */
      }
    }

    function updateMasterMonitorToggle() {
      if (!monitorAllToggle) return;
      const ids = cardsCache.map((card) => card.id);
      monitorAllToggle.checked = ids.length > 0 && ids.every((id) => isMonitorOn(id));
    }

    function applyMonitorVisual(cardId) {
      const section = document.querySelector(`.site-block[data-id="${cardId}"]`);
      if (!section) return;
      const on = isMonitorOn(cardId);
      section.classList.toggle("monitor-off", !on);
      const toggle = section.querySelector(".monitor-toggle");
      if (toggle) toggle.classList.toggle("on", on);
      const input = section.querySelector(".monitor-switch");
      if (input) input.checked = on;
      const note = section.querySelector(".paused-note");
      if (note) note.style.display = on ? "none" : "";
    }

    function setMonitor(cardId, on, { refresh = true } = {}) {
      void persistMonitor(cardId, on).then(() => {
        applyMonitorVisual(cardId);
        renderAll(cardsCache);
        if (on && refresh) refreshCard(cardId).then(updateSiteBlock).catch(() => {});
        updateMasterMonitorToggle();
      });
    }

    async function setAllMonitoring(on) {
      const ids = cardsCache.map((card) => card.id).sort((a, b) => a - b);
      try {
        await fetch("/api/monitor", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ all: true, enabled: on }),
        });
        await loadMonitorState();
      } catch (_err) {
        /* best effort */
      }
      ids.forEach((id) => {
        void persistMonitor(id, on, false);
        applyMonitorVisual(id);
      });
      updateMasterMonitorToggle();
      renderAll(cardsCache);
      if (!on) {
        if (refreshStatusEl) refreshStatusEl.textContent = "All monitoring off.";
        return;
      }
      if (ids.length) refreshAllSequential();
    }

    function updateSiteBlock(card) {
      const section = document.querySelector(`.site-block[data-id="${card.id}"]`);
      if (!section) return;
      const wrapper = document.createElement("div");
      wrapper.innerHTML = renderSite(card);
      section.replaceWith(wrapper.firstElementChild);
      wireSiteNameInputs();
      const monitorSwitch = document.querySelector(`.site-block[data-id="${card.id}"] .monitor-switch`);
      if (monitorSwitch) {
        monitorSwitch.onchange = () => setMonitor(card.id, monitorSwitch.checked);
      }
      applyMonitorVisual(card.id);
    }

    function readJsonStorage(key, fallback) {
      try {
        const raw = localStorage.getItem(key);
        return raw ? JSON.parse(raw) : fallback;
      } catch (_err) {
        return fallback;
      }
    }

    function loadSiteNameOverrides() {
      siteNameOverrides = readJsonStorage(SITE_NAMES_PREF_KEY, {});
      if (!siteNameOverrides || typeof siteNameOverrides !== "object") {
        siteNameOverrides = {};
      }
    }

    function saveSiteNameOverride(cardId, name) {
      const trimmed = String(name || "").trim();
      const key = String(cardId);
      if (trimmed) {
        siteNameOverrides[key] = trimmed;
      } else {
        delete siteNameOverrides[key];
      }
      try {
        localStorage.setItem(SITE_NAMES_PREF_KEY, JSON.stringify(siteNameOverrides));
      } catch (_err) {
        /* ignore storage errors */
      }
    }

    function siteDisplayName(card) {
      const override = siteNameOverrides[String(card.id)];
      return override || card.name || "Site";
    }

    function applyReportTitlePrint(showTitle) {
      document.body.classList.toggle("hide-report-title-print", !showTitle);
      if (showTitleToggle) {
        showTitleToggle.checked = showTitle;
      }
      try {
        localStorage.setItem(SHOW_TITLE_PRINT_KEY, showTitle ? "1" : "0");
      } catch (_err) {
        /* ignore storage errors */
      }
    }

    function syncDocumentTitle() {
      const title = reportTitleInput ? reportTitleInput.value.trim() : DEFAULT_TITLE;
      document.title = title || DEFAULT_TITLE;
    }

    function initReportHeader() {
      let title = DEFAULT_TITLE;
      let subtitle = DEFAULT_SUBTITLE;
      let showTitlePrint = true;
      try {
        title = localStorage.getItem(TITLE_PREF_KEY) || DEFAULT_TITLE;
        subtitle = localStorage.getItem(SUBTITLE_PREF_KEY) || DEFAULT_SUBTITLE;
        if (localStorage.getItem(SHOW_TITLE_PRINT_KEY) === "0") showTitlePrint = false;
      } catch (_err) {
        /* ignore storage errors */
      }
      if (reportTitleInput) {
        reportTitleInput.value = title;
        reportTitleInput.addEventListener("input", () => {
          syncDocumentTitle();
          try {
            localStorage.setItem(TITLE_PREF_KEY, reportTitleInput.value);
          } catch (_err) {
            /* ignore storage errors */
          }
        });
      }
      if (reportSubtitleInput) {
        reportSubtitleInput.value = subtitle;
        reportSubtitleInput.addEventListener("input", () => {
          try {
            localStorage.setItem(SUBTITLE_PREF_KEY, reportSubtitleInput.value);
          } catch (_err) {
            /* ignore storage errors */
          }
        });
      }
      applyReportTitlePrint(showTitlePrint);
      if (showTitleToggle) {
        showTitleToggle.addEventListener("change", () => {
          applyReportTitlePrint(showTitleToggle.checked);
        });
      }
      syncDocumentTitle();
    }

    function wireSiteNameInputs() {
      document.querySelectorAll(".site-name-input").forEach((input) => {
        input.addEventListener("change", () => {
          saveSiteNameOverride(input.dataset.cardId, input.value);
        });
        input.addEventListener("keydown", (event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            input.blur();
          }
        });
      });
    }

    function applyDetailsVisibility(showDetails) {
      document.body.classList.toggle("hide-capacity-details", !showDetails);
      if (showDetailsToggle) {
        showDetailsToggle.checked = showDetails;
      }
      try {
        localStorage.setItem(DETAILS_PREF_KEY, showDetails ? "1" : "0");
      } catch (_err) {
        /* ignore storage errors */
      }
    }

    function applyPageLayout(oneSitePerPage) {
      document.body.classList.toggle("one-site-per-page", oneSitePerPage);
      if (onePageToggle) {
        onePageToggle.checked = oneSitePerPage;
      }
      try {
        localStorage.setItem(ONE_PAGE_PREF_KEY, oneSitePerPage ? "1" : "0");
      } catch (_err) {
        /* ignore storage errors */
      }
    }

    function applyVendorPoolVisibility() {
      const ibm = showPoolsIbmToggle ? showPoolsIbmToggle.checked : false;
      const hpe = showPoolsHpeToggle ? showPoolsHpeToggle.checked : false;
      const dell = showPoolsDellToggle ? showPoolsDellToggle.checked : false;
      document.body.classList.toggle("show-pools-ibm", ibm);
      document.body.classList.toggle("show-pools-hpe", hpe);
      document.body.classList.toggle("show-pools-dell", dell);
      try {
        localStorage.setItem(POOLS_IBM_PREF_KEY, ibm ? "1" : "0");
        localStorage.setItem(POOLS_HPE_PREF_KEY, hpe ? "1" : "0");
        localStorage.setItem(POOLS_DELL_PREF_KEY, dell ? "1" : "0");
      } catch (_err) {
        /* ignore storage errors */
      }
      updateViewOptionsButton();
    }

    function applyRawCapacityVisibility(showRaw) {
      document.body.classList.toggle("hide-raw-capacity", !showRaw);
      if (showRawToggle) {
        showRawToggle.checked = showRaw;
      }
      try {
        localStorage.setItem(RAW_PREF_KEY, showRaw ? "1" : "0");
      } catch (_err) {
        /* ignore storage errors */
      }
    }

    function initDetailsToggle() {
      let showDetails = true;
      try {
        const saved = localStorage.getItem(DETAILS_PREF_KEY);
        if (saved === "0") showDetails = false;
      } catch (_err) {
        /* ignore storage errors */
      }
      applyDetailsVisibility(showDetails);
      if (showDetailsToggle) {
        showDetailsToggle.addEventListener("change", () => {
          applyDetailsVisibility(showDetailsToggle.checked);
        });
      }
    }

    function initPageLayoutToggle() {
      let oneSitePerPage = true;
      try {
        const saved = localStorage.getItem(ONE_PAGE_PREF_KEY);
        if (saved === "0") oneSitePerPage = false;
      } catch (_err) {
        /* ignore storage errors */
      }
      applyPageLayout(oneSitePerPage);
      if (onePageToggle) {
        onePageToggle.addEventListener("change", () => {
          applyPageLayout(onePageToggle.checked);
        });
      }
    }

    function initVendorPoolToggles() {
      const load = (key) => {
        try {
          return localStorage.getItem(key) === "1";
        } catch (_err) {
          return false;
        }
      };
      if (showPoolsIbmToggle) showPoolsIbmToggle.checked = load(POOLS_IBM_PREF_KEY);
      if (showPoolsHpeToggle) showPoolsHpeToggle.checked = load(POOLS_HPE_PREF_KEY);
      if (showPoolsDellToggle) showPoolsDellToggle.checked = load(POOLS_DELL_PREF_KEY);
      applyVendorPoolVisibility();
      [showPoolsIbmToggle, showPoolsHpeToggle, showPoolsDellToggle].forEach((el) => {
        if (el) el.addEventListener("change", applyVendorPoolVisibility);
      });
    }

    function initRawCapacityToggle() {
      let showRaw = false;
      try {
        const saved = localStorage.getItem(RAW_PREF_KEY);
        if (saved === "1") showRaw = true;
      } catch (_err) {
        /* ignore storage errors */
      }
      applyRawCapacityVisibility(showRaw);
      if (showRawToggle) {
        showRawToggle.addEventListener("change", () => {
          applyRawCapacityVisibility(showRawToggle.checked);
        });
      }
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function hostLabel(card) {
      const port = card.port ? `:${card.port}` : "";
      return `${card.host || ""}${port}`;
    }

    function siteOptionLabel(card) {
      return `${card.name} (${card.host || ""})`;
    }

    function selectedCapacitySiteId() {
      if (!capacitySiteSelectEl) return null;
      const raw = capacitySiteSelectEl.value;
      if (!raw) return null;
      const id = parseInt(raw, 10);
      return Number.isFinite(id) ? id : null;
    }

    function populateCapacitySiteSelect(cards) {
      if (!capacitySiteSelectEl) return;
      const previous = capacitySiteSelectEl.value;
      const sorted = [...cards].sort((a, b) =>
        (a.name || "").localeCompare(b.name || "", undefined, { sensitivity: "base" })
      );
      capacitySiteSelectEl.innerHTML =
        '<option value="">All servers</option>' +
        sorted
          .map(
            (card) =>
              `<option value="${card.id}">${escapeHtml(siteOptionLabel(card))}</option>`
          )
          .join("");
      if (previous && sorted.some((card) => String(card.id) === previous)) {
        capacitySiteSelectEl.value = previous;
      } else {
        capacitySiteSelectEl.value = "";
      }
    }

    function applyCapacitySiteFilter() {
      const siteId = selectedCapacitySiteId();
      document.querySelectorAll(".site-block").forEach((section) => {
        const id = parseInt(section.dataset.id, 10);
        const visible = siteId == null || id === siteId;
        section.style.display = visible ? "" : "none";
      });
    }

    function capacityIssues(card) {
      if (!isMonitorOn(card.id)) return [];
      return (card.health_issues || []).filter((issue) => {
        const cat = String(issue.category || "").toLowerCase();
        if (cat === "capacity") return true;
        const msg = String(issue.message || "");
        return /%\\s*(full|capacity)/i.test(msg) || /running at\\s+\\d/i.test(msg);
      });
    }

    function capacityAlertBanner(card) {
      const issues = capacityIssues(card);
      if (!issues.length) return "";
      const hasCritical = issues.some((issue) => issue.severity === "critical");
      const sev = hasCritical ? "critical" : "warn";
      const label = hasCritical ? "CRITICAL" : "WARNING";
      const items = issues
        .map((issue) => `<li>${escapeHtml(issue.message || "")}</li>`)
        .join("");
      return `
        <div class="capacity-alert ${sev}" role="alert">
          <div class="capacity-alert-label">${label}</div>
          <ul>${items}</ul>
        </div>`;
    }

    function renderFleetCapacityAlerts(cards) {
      if (!fleetAlertsEl) return;
      const rows = [];
      cards.forEach((card) => {
        const issues = capacityIssues(card);
        if (!issues.length) return;
        const hasCritical = issues.some((issue) => issue.severity === "critical");
        const top = issues[0];
        rows.push({
          name: siteDisplayName(card),
          severity: hasCritical ? "critical" : "warn",
          message: top.message || "",
          count: issues.length,
        });
      });
      if (!rows.length) {
        fleetAlertsEl.innerHTML = "";
        return;
      }
      const hasCritical = rows.some((row) => row.severity === "critical");
      const sev = hasCritical ? "critical" : "warn";
      const title = hasCritical
        ? `Critical capacity on ${rows.filter((r) => r.severity === "critical").length} site(s)`
        : `Capacity warning on ${rows.length} site(s)`;
      const items = rows
        .map((row) => {
          const extra = row.count > 1 ? ` (+${row.count - 1} more)` : "";
          return `<li><strong>${escapeHtml(row.name)}</strong> — ${escapeHtml(row.message)}${extra}</li>`;
        })
        .join("");
      fleetAlertsEl.innerHTML = `
        <div class="fleet-capacity-alert ${sev}" role="alert">
          <p class="alert-title">${escapeHtml(title)}</p>
          <ul>${items}</ul>
        </div>`;
    }

    function renderSite(card) {
      const updated = card.updated_at
        ? `Last updated: ${card.updated_at}`
        : "Not refreshed yet";
      const monitorOn = isMonitorOn(card.id);
      const poolFamily = String(card.pool_family || "").toLowerCase();
      const dellFamily = isDellReportFamily(card);
      const dellIncludeOn = isDellIncludeOn(card.id);
      const offClass = monitorOn ? "" : " monitor-off";
      const issues = capacityIssues(card);
      const hasCritical = issues.some((issue) => issue.severity === "critical");
      const alertClass = !issues.length
        ? ""
        : hasCritical
          ? " capacity-critical"
          : " capacity-warn";
      let body = "";
      if (card.error && !card.capacity_popup_html) {
        body = `<div class="error">${escapeHtml(card.error)}</div>`;
      } else if (card.capacity_popup_html) {
        body = capacityAlertBanner(card) + card.capacity_popup_html;
      } else {
        body =
          capacityAlertBanner(card) +
          '<div class="error">No capacity data for this site. ' +
          "Turn on Monitor and refresh, or check SSH credentials in Admin." +
          (dellFamily
            ? " Or check <strong>Dell Report</strong> on this card to list it on the Dell workbook with blank capacity."
            : "") +
          "</div>";
      }
      const dellToggle = dellFamily
        ? `<label class="monitor-toggle dell-include-toggle no-print${dellIncludeOn ? " on" : ""}" title="Include on Dell Report even when SSH/capacity fails (capacity cells blank).">
              <input type="checkbox" class="dell-include-switch" data-id="${card.id}"${dellIncludeOn ? " checked" : ""}>
              Dell Report
            </label>`
        : "";
      return `
        <section class="site-block${card.error && !card.capacity_popup_html ? " fail" : ""}${offClass}${alertClass}" data-id="${card.id}" data-pool-family="${escapeHtml(poolFamily)}">
          <div class="site-head">
            <input
              type="text"
              class="site-name-input"
              data-card-id="${card.id}"
              value="${escapeHtml(siteDisplayName(card))}"
              aria-label="Site name"
            >
            <p class="host">${escapeHtml(hostLabel(card))}</p>
            <label class="monitor-toggle no-print${monitorOn ? " on" : ""}">
              <input type="checkbox" class="monitor-switch" data-id="${card.id}"${monitorOn ? " checked" : ""}>
              Monitor
            </label>
            ${dellToggle}
            <p class="paused-note no-print"${monitorOn ? ' style="display:none"' : ""}>Monitoring off — showing last snapshot. Turn on Monitor to connect over SSH.</p>
            <p class="updated">${escapeHtml(updated)}</p>
          </div>
          ${body}
        </section>`;
    }

    function visibleCards(cards) {
      if (includeOffToggle && includeOffToggle.checked) {
        return cards;
      }
      return cards.filter((c) => isMonitorOn(c.id));
    }

    function renderAll(cards) {
      if (!cards.length) {
        if (fleetAlertsEl) fleetAlertsEl.innerHTML = "";
        sitesEl.innerHTML =
          '<div class="empty">No servers yet. Keep LaunchPad running and unlocked, then use ' +
          "<strong>Capacity Report</strong> or <strong>Health Dashboard</strong> in LaunchPad.</div>";
        if (refreshStatusEl) {
          refreshStatusEl.textContent =
            "No servers — keep LaunchPad unlocked and open Capacity Report from LaunchPad";
        }
        return;
      }
      const visible = visibleCards(cards);
      if (!visible.length) {
        if (fleetAlertsEl) fleetAlertsEl.innerHTML = "";
        sitesEl.innerHTML =
          '<div class="empty">All sites have Monitor off. Check ' +
          '<strong>Include monitoring-off sites</strong> to view them.</div>';
        updateMasterMonitorToggle();
        if (refreshStatusEl) {
          refreshStatusEl.textContent = `0 of ${cards.length} monitored site(s) shown`;
        }
        updatePrintMeta(cards);
        return;
      }
      const sorted = [...visible].sort((a, b) =>
        (a.name || "").localeCompare(b.name || "", undefined, { sensitivity: "base" })
      );
      renderFleetCapacityAlerts(sorted);
      sitesEl.innerHTML = sorted.map(renderSite).join("");
      wireSiteNameInputs();
      document.querySelectorAll(".monitor-switch").forEach((input) => {
        const cardId = parseInt(input.dataset.id, 10);
        input.onchange = () => setMonitor(cardId, input.checked);
      });
      document.querySelectorAll(".dell-include-switch").forEach((input) => {
        const cardId = parseInt(input.dataset.id, 10);
        input.onchange = () => setDellInclude(cardId, input.checked);
      });
      sorted.forEach((card) => applyMonitorVisual(card.id));
      updateMasterMonitorToggle();
      populateCapacitySiteSelect(visible);
      applyCapacitySiteFilter();
      if (refreshStatusEl) {
        const siteId = selectedCapacitySiteId();
        const shownCount = siteId == null
          ? visible.length
          : visible.filter((card) => card.id === siteId).length;
        const includeOff = includeOffToggle && includeOffToggle.checked;
        refreshStatusEl.textContent = includeOff
          ? `${shownCount} of ${cards.length} site(s) shown`
          : `${shownCount} monitored site(s) shown (${cards.length} total)`;
      }
      updatePrintMeta(cards);
    }

    async function downloadExcel() {
      if (!excelBtn) return;
      excelBtn.disabled = true;
      if (refreshStatusEl) refreshStatusEl.textContent = "Building Excel workbook…";
      try {
        const includeOff = includeOffToggle ? includeOffToggle.checked : false;
        const showRaw = showRawToggle ? showRawToggle.checked : false;
        const siteId = selectedCapacitySiteId();
        let exportUrl =
          `/api/capacity-export?include_off=${includeOff ? 1 : 0}` +
          `&include_pools=1` +
          `&show_raw=${showRaw ? 1 : 0}&open=1`;
        if (siteId != null) {
          exportUrl += `&card_id=${siteId}`;
        }
        const res = await fetch(exportUrl);
        if (!res.ok) {
          let detail = `HTTP ${res.status}`;
          try {
            const err = await res.json();
            if (err && err.error) detail = err.error;
          } catch (_err) {
            /* ignore */
          }
          throw new Error(detail);
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        const stamp = new Date().toISOString().slice(0, 16).replace(/[:-]/g, "");
        a.href = url;
        a.download = `Storage_Capacity_Report_${stamp}.xlsx`;
        a.click();
        URL.revokeObjectURL(url);
        if (refreshStatusEl) {
          refreshStatusEl.textContent = "Excel (.xlsx) downloaded and opened in Excel.";
        }
      } catch (err) {
        if (refreshStatusEl) {
          refreshStatusEl.textContent = `Excel export failed: ${err.message || err}`;
        }
      } finally {
        excelBtn.disabled = false;
      }
    }

    async function downloadDellReport() {
      if (!dellReportBtn) return;
      dellReportBtn.disabled = true;
      if (refreshStatusEl) refreshStatusEl.textContent = "Building Dell Report workbook…";
      try {
        const includeOff = includeOffToggle ? includeOffToggle.checked : false;
        const showRaw = showRawToggle ? showRawToggle.checked : false;
        const siteId = selectedCapacitySiteId();
        let exportUrl =
          `/api/dell-report-export?include_off=${includeOff ? 1 : 0}` +
          `&include_pools=1` +
          `&show_raw=${showRaw ? 1 : 0}&open=1`;
        if (siteId != null) {
          exportUrl += `&card_id=${siteId}`;
        }
        const res = await fetch(exportUrl);
        if (!res.ok) {
          let detail = `HTTP ${res.status}`;
          try {
            const err = await res.json();
            if (err && err.error) detail = err.error;
          } catch (_err) {
            /* ignore */
          }
          throw new Error(detail);
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        const stamp = new Date().toISOString().slice(0, 16).replace(/[:-]/g, "");
        a.href = url;
        a.download = `Dell_Capacity_Report_${stamp}.xlsx`;
        a.click();
        URL.revokeObjectURL(url);
        if (refreshStatusEl) {
          refreshStatusEl.textContent = "Dell Report (.xlsx) downloaded and opened in Excel.";
        }
      } catch (err) {
        if (refreshStatusEl) {
          refreshStatusEl.textContent = `Dell Report export failed: ${err.message || err}`;
        }
      } finally {
        dellReportBtn.disabled = false;
      }
    }

    async function initDellReportButton() {
      if (!dellReportBtn) return;
      try {
        const res = await fetch("/api/dell-report-settings");
        const settings = await res.json();
        const show = settings && settings.enabled;
        dellReportBtn.style.display = show ? "" : "none";
        if (dellIncludeNoSshWrap) {
          dellIncludeNoSshWrap.style.display = show ? "" : "none";
        }
      } catch (_err) {
        dellReportBtn.style.display = "none";
        if (dellIncludeNoSshWrap) dellIncludeNoSshWrap.style.display = "none";
      }
    }

    async function refreshCard(cardId) {
      const section = document.querySelector(`.site-block[data-id="${cardId}"]`);
      if (section) section.classList.add("loading");
      try {
        const res = await fetch(
          `/api/refresh/${cardId}?focus=capacity&include_pools=1`,
          { method: "POST" }
        );
        const card = await res.json();
        if (!res.ok) throw new Error(card.error || "Refresh failed");
        return card;
      } finally {
        if (section) section.classList.remove("loading");
      }
    }

    async function refreshAllSequential() {
      if (refreshAllRunning) return;
      refreshAllRunning = true;
      if (refreshAllBtn) refreshAllBtn.disabled = true;
      try {
        const res = await fetch("/api/cards");
        const all = (await res.json()).sort((a, b) => a.id - b.id);
        const cards = all.filter((card) => isMonitorOn(card.id));
        if (!cards.length) {
          if (refreshStatusEl) {
            refreshStatusEl.textContent = all.length
              ? "No sites are on. Turn on Monitor or use All monitoring on."
              : "No servers to refresh.";
          }
          return;
        }
        const updated = [...all];
        progressActive = true;
        applyProgress(0, cards.length, cards[0] ? cards[0].name : "");
        for (let index = 0; index < cards.length; index += 1) {
          const card = cards[index];
          applyProgress(index, cards.length, card.name);
          try {
            const refreshed = await refreshCard(card.id);
            const cacheIndex = updated.findIndex((entry) => entry.id === card.id);
            if (cacheIndex >= 0) updated[cacheIndex] = refreshed;
          } catch (err) {
            const cacheIndex = updated.findIndex((entry) => entry.id === card.id);
            if (cacheIndex >= 0) {
              updated[cacheIndex] = { ...card, error: err.message || String(err) };
            }
          }
        }
        renderAll(updated);
        cardsCache = updated;
        hideProgress();
        if (refreshStatusEl) refreshStatusEl.textContent = "Refresh complete.";
        updatePrintMeta(updated);
      } finally {
        refreshAllRunning = false;
        if (refreshAllBtn) refreshAllBtn.disabled = false;
        hideProgress();
      }
    }

    function updatePrintMeta(cards) {
      const stamp = new Date().toLocaleString();
      const visible = visibleCards(cards);
      const withCapacity = visible.filter((c) => c.capacity_popup_html).length;
      const includeOff = includeOffToggle && includeOffToggle.checked;
      if (includeOff) {
        printMetaEl.textContent =
          `Report generated ${stamp} — ${withCapacity} of ${visible.length} site(s) with capacity data.`;
      } else {
        printMetaEl.textContent =
          `Report generated ${stamp} — ${withCapacity} of ${visible.length} monitored site(s) with capacity data` +
          (cards.length !== visible.length ? ` (${cards.length} total in LaunchPad).` : ".");
      }
    }

    async function loadCards() {
      let showLoadBar = false;
      try {
        const exportBusy =
          (excelBtn && excelBtn.disabled) || (dellReportBtn && dellReportBtn.disabled);
        showLoadBar =
          !refreshAllRunning && !exportBusy && !cardsCache.length;
        if (showLoadBar) {
          progressActive = true;
          if (progressWrap) progressWrap.hidden = false;
          if (progressBar) progressBar.style.width = "0%";
          if (refreshStatusEl) refreshStatusEl.textContent = "Loading servers…";
        } else if (refreshStatusEl && !refreshAllRunning && !exportBusy) {
          refreshStatusEl.textContent = "Loading servers from LaunchPad...";
        }
        if (sitesEl && !cardsCache.length) {
          sitesEl.innerHTML = '<div class="empty">Loading servers from LaunchPad...</div>';
        }
        try {
          await fetch("/api/sync", { method: "POST" });
        } catch (_syncErr) {
          // Sync is best-effort; /api/cards also syncs when LaunchPad is unlocked.
        }
        await loadMonitorState();
        await loadDellIncludeState();
        const res = await fetch("/api/cards");
        if (!res.ok) {
          throw new Error(`Health server returned ${res.status}`);
        }
        const cards = await res.json();
        cardsCache = Array.isArray(cards) ? cards : [];
        renderAll(cardsCache);
        syncNoSshDellToggle();
        updateViewOptionsButton();
        updatePrintMeta(cardsCache);
        if (showLoadBar) hideProgress();
      } catch (err) {
        sitesEl.innerHTML =
          `<div class="error">${escapeHtml(err.message || err)}. Keep LaunchPad running and unlocked, then use <strong>Capacity Report</strong> in the app.</div>`;
        if (showLoadBar) hideProgress();
        if (refreshStatusEl) {
          refreshStatusEl.textContent = "Could not load servers";
        }
      }
    }

    if (printBtn) {
      printBtn.onclick = () => window.print();
    }
    if (refreshAllBtn) {
      refreshAllBtn.onclick = () => refreshAllSequential();
    }
    if (monitorAllToggle) {
      monitorAllToggle.addEventListener("change", () => {
        setAllMonitoring(monitorAllToggle.checked);
      });
    }
    if (includeOffToggle) {
      includeOffToggle.addEventListener("change", () => {
        renderAll(cardsCache);
      });
    }
    if (capacitySiteSelectEl) {
      capacitySiteSelectEl.addEventListener("change", () => {
        applyCapacitySiteFilter();
        if (refreshStatusEl && cardsCache.length) {
          const visible = includeOffToggle && includeOffToggle.checked
            ? cardsCache
            : cardsCache.filter((c) => isMonitorOn(c.id));
          const siteId = selectedCapacitySiteId();
          const shownCount = siteId == null
            ? visible.length
            : visible.filter((card) => card.id === siteId).length;
          refreshStatusEl.textContent = `${shownCount} of ${cardsCache.length} site(s) shown`;
        }
      });
    }
    if (excelBtn) {
      excelBtn.addEventListener("click", downloadExcel);
    }
    if (dellReportBtn) {
      dellReportBtn.addEventListener("click", downloadDellReport);
    }
    if (dellIncludeNoSshToggle) {
      dellIncludeNoSshToggle.addEventListener("change", () => {
        void setNoSshDellInclude(dellIncludeNoSshToggle.checked);
      });
    }
    if (optionsMenuBtn && optionsMenu) {
      optionsMenuBtn.addEventListener("click", (event) => {
        event.stopPropagation();
        setOptionsMenuOpen(!optionsMenu.classList.contains("open"));
      });
      if (optionsMenuPanel) {
        optionsMenuPanel.addEventListener("click", (event) => {
          event.stopPropagation();
        });
        optionsMenuPanel.addEventListener("change", () => {
          updateViewOptionsButton();
        });
      }
      document.addEventListener("click", () => {
        setOptionsMenuOpen(false);
      });
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") setOptionsMenuOpen(false);
      });
    }

    initDetailsToggle();
    initPageLayoutToggle();
    initVendorPoolToggles();
    initRawCapacityToggle();
    loadSiteNameOverrides();
    initReportHeader();
    initDellReportButton();
    updateViewOptionsButton();
    loadCards();
    setInterval(loadCards, 15000);
  </script>
</body>
</html>"""

CAPACITY_REPORT_PATH = "/capacity"
