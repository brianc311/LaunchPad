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
    }
    .monitor-toggle input { width: 15px; height: 15px; accent-color: var(--accent); cursor: pointer; }
    .monitor-toggle.on { color: #4ade80; }
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
    body.hide-capacity-details .capacity-detail-section {
      display: none;
    }
    body.hide-pool-storage .capacity-pools-wrap {
      display: none;
    }
    .capacity-pools-wrap {
      margin-top: 8px;
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
        <button type="button" id="print-btn">Print / Save PDF</button>
        <button type="button" id="refresh-all-btn">Refresh On Sites</button>
        <a class="btn secondary" href="/fc-wwpn">FC WWPN</a>
        <a class="btn secondary" href="/site-lookup">Site Lookup</a>
        <a class="btn secondary" href="/snapshot-schedule">Snapshot Schedule</a>
        <a class="btn secondary" href="/">Health Dashboard</a>
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
        <label class="toggle-row" for="show-pools-toggle">
          <input type="checkbox" id="show-pools-toggle" checked>
          Show pool storage
        </label>
        <label class="toggle-row" for="show-title-toggle">
          <input type="checkbox" id="show-title-toggle" checked>
          Show report title on print
        </label>
        <span id="refresh-status" class="refresh-status"></span>
      </div>
      <p id="print-meta" class="print-meta"></p>
    </section>
    <div id="sites"></div>
    <p class="footer no-print">
      LaunchPad Capacity v{{APP_VERSION}} · Keep LaunchPad running and unlocked while refreshing.
      Use <strong>Print / Save PDF</strong> and choose &ldquo;Save as PDF&rdquo; in the print dialog.
    </p>
  </div>
  <script>
    const sitesEl = document.getElementById("sites");
    const refreshStatusEl = document.getElementById("refresh-status");
    const refreshAllBtn = document.getElementById("refresh-all-btn");
    const monitorAllToggle = document.getElementById("monitor-all-toggle");
    const printBtn = document.getElementById("print-btn");
    const printMetaEl = document.getElementById("print-meta");
    const showDetailsToggle = document.getElementById("show-details-toggle");
    const onePageToggle = document.getElementById("one-page-toggle");
    const showPoolsToggle = document.getElementById("show-pools-toggle");
    const showTitleToggle = document.getElementById("show-title-toggle");
    const reportTitleInput = document.getElementById("report-title-input");
    const reportSubtitleInput = document.getElementById("report-subtitle-input");
    const DETAILS_PREF_KEY = "launchpad.capacityReport.showDetails";
    const ONE_PAGE_PREF_KEY = "launchpad.capacityReport.oneSitePerPage";
    const POOLS_PREF_KEY = "launchpad.capacityReport.showPools";
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

    function applyPoolStorageVisibility(showPools) {
      document.body.classList.toggle("hide-pool-storage", !showPools);
      if (showPoolsToggle) {
        showPoolsToggle.checked = showPools;
      }
      try {
        localStorage.setItem(POOLS_PREF_KEY, showPools ? "1" : "0");
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

    function initPoolStorageToggle() {
      let showPools = true;
      try {
        const saved = localStorage.getItem(POOLS_PREF_KEY);
        if (saved === "0") showPools = false;
      } catch (_err) {
        /* ignore storage errors */
      }
      applyPoolStorageVisibility(showPools);
      if (showPoolsToggle) {
        showPoolsToggle.addEventListener("change", () => {
          applyPoolStorageVisibility(showPoolsToggle.checked);
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

    function renderSite(card) {
      const updated = card.updated_at
        ? `Last updated: ${card.updated_at}`
        : "Not refreshed yet";
      const monitorOn = isMonitorOn(card.id);
      const offClass = monitorOn ? "" : " monitor-off";
      let body = "";
      if (card.error && !card.capacity_popup_html) {
        body = `<div class="error">${escapeHtml(card.error)}</div>`;
      } else if (card.capacity_popup_html) {
        body = card.capacity_popup_html;
      } else {
        body =
          '<div class="error">No capacity data for this site. ' +
          "Turn on Monitor and refresh, or check SSH credentials in Admin.</div>";
      }
      return `
        <section class="site-block${card.error && !card.capacity_popup_html ? " fail" : ""}${offClass}" data-id="${card.id}">
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
            <p class="paused-note no-print"${monitorOn ? ' style="display:none"' : ""}>Monitoring off — showing last snapshot. Turn on Monitor to connect over SSH.</p>
            <p class="updated">${escapeHtml(updated)}</p>
          </div>
          ${body}
        </section>`;
    }

    function renderAll(cards) {
      if (!cards.length) {
        sitesEl.innerHTML =
          '<div class="empty">No servers yet. Keep LaunchPad running and unlocked, then use ' +
          "<strong>Capacity Report</strong> or <strong>Health Dashboard</strong> in LaunchPad.</div>";
        return;
      }
      const sorted = [...cards].sort((a, b) =>
        (a.name || "").localeCompare(b.name || "", undefined, { sensitivity: "base" })
      );
      sitesEl.innerHTML = sorted.map(renderSite).join("");
      wireSiteNameInputs();
      document.querySelectorAll(".monitor-switch").forEach((input) => {
        const cardId = parseInt(input.dataset.id, 10);
        input.onchange = () => setMonitor(cardId, input.checked);
      });
      sorted.forEach((card) => applyMonitorVisual(card.id));
      updateMasterMonitorToggle();
    }

    async function refreshCard(cardId) {
      const section = document.querySelector(`.site-block[data-id="${cardId}"]`);
      if (section) section.classList.add("loading");
      try {
        const res = await fetch(`/api/refresh/${cardId}`, { method: "POST" });
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
        for (let index = 0; index < cards.length; index += 1) {
          const card = cards[index];
          if (refreshStatusEl) {
            refreshStatusEl.textContent =
              `Refreshing ${card.name} (${index + 1}/${cards.length})...`;
          }
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
        if (refreshStatusEl) refreshStatusEl.textContent = "Refresh complete.";
        updatePrintMeta(updated);
      } finally {
        refreshAllRunning = false;
        if (refreshAllBtn) refreshAllBtn.disabled = false;
      }
    }

    function updatePrintMeta(cards) {
      const stamp = new Date().toLocaleString();
      const withCapacity = cards.filter((c) => c.capacity_popup_html).length;
      printMetaEl.textContent =
        `Report generated ${stamp} — ${withCapacity} of ${cards.length} site(s) with capacity data.`;
    }

    async function loadCards() {
      try {
        if (refreshStatusEl && !refreshAllRunning) {
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
        const res = await fetch("/api/cards");
        if (!res.ok) {
          throw new Error(`Health server returned ${res.status}`);
        }
        const cards = await res.json();
        cardsCache = Array.isArray(cards) ? cards : [];
        renderAll(cardsCache);
        updatePrintMeta(cardsCache);
        if (refreshStatusEl && !refreshAllRunning) {
          refreshStatusEl.textContent = cardsCache.length
            ? `${cardsCache.length} site(s) loaded`
            : "No servers — keep LaunchPad unlocked and open Capacity Report from LaunchPad";
        }
      } catch (err) {
        sitesEl.innerHTML =
          `<div class="error">${escapeHtml(err.message || err)}. Keep LaunchPad running and unlocked, then use <strong>Capacity Report</strong> in the app.</div>`;
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

    initDetailsToggle();
    initPageLayoutToggle();
    initPoolStorageToggle();
    loadSiteNameOverrides();
    initReportHeader();
    loadCards();
    setInterval(loadCards, 15000);
  </script>
</body>
</html>"""

CAPACITY_REPORT_PATH = "/capacity"
