"""Snapshot schedule page — frequency scaled by pool free headroom."""

SNAPSHOT_SCHEDULE_PATH = "/snapshot-schedule"

SNAPSHOT_SCHEDULE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Snapshot Schedule — IBM FlashSystem / Storwize</title>
  <style>
    :root {
      --bg: #0b0f14;
      --panel: #121821;
      --text: #e8edf5;
      --muted: #8b98ab;
      --accent: #ff6b00;
      --accent2: #ff8533;
      --ok: #4ade80;
      --ok-dim: rgba(74, 222, 128, 0.15);
      --warn: #f59e0b;
      --border: #2a3444;
      --card: #151c27;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Segoe UI, Inter, Arial, sans-serif;
      background: radial-gradient(circle at top, #172033 0%, var(--bg) 45%);
      color: var(--text);
      min-height: 100vh;
    }
    a:not(.btn) {
      color: #9ec1ff;
      text-decoration: underline;
      text-underline-offset: 2px;
    }
    a:not(.btn):hover { color: #c5d9ff; }
    .wrap { max-width: 1120px; margin: 0 auto; padding: 28px 20px 48px; }
    .hero {
      background: linear-gradient(135deg, #1a2230 0%, #101722 100%);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 24px 28px;
      margin-bottom: 28px;
      box-shadow: 0 0 40px rgba(255, 107, 0, 0.08);
    }
    .hero h1 {
      margin: 0 0 10px;
      font-size: 1.75rem;
      font-weight: 700;
      color: var(--text);
    }
    .hero .lede {
      margin: 0 0 18px;
      color: var(--muted);
      line-height: 1.5;
      max-width: 62rem;
      font-size: 0.95rem;
    }
    .hero-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-bottom: 18px;
    }
    .btn, a.btn {
      background: var(--accent);
      color: #111;
      border: none;
      border-radius: 10px;
      height: 34px;
      padding: 0 14px;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      text-decoration: none;
    }
    a.btn.secondary, button.btn.secondary {
      background: #0f141d;
      color: var(--text);
      border: 1px solid var(--border);
    }
    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 14px 20px;
      align-items: center;
    }
    .badges { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 12px;
      border-radius: 999px;
      font-size: 0.85rem;
      font-weight: 600;
      border: 1px solid transparent;
    }
    .badge.flagged {
      background: rgba(255, 107, 0, 0.15);
      color: var(--accent2);
      border-color: rgba(255, 107, 0, 0.45);
    }
    .badge.scheduled {
      background: var(--ok-dim);
      color: var(--ok);
      border-color: rgba(74, 222, 128, 0.4);
    }
    .threshold-block {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
      flex: 1;
      min-width: 260px;
    }
    .threshold-block label {
      color: var(--muted);
      font-size: 0.9rem;
      white-space: nowrap;
    }
    .threshold-block input[type="range"] {
      flex: 1;
      min-width: 140px;
      accent-color: var(--accent);
      max-width: 280px;
    }
    .threshold-value {
      color: var(--accent);
      font-weight: 700;
      font-size: 1.05rem;
      min-width: 3ch;
    }
    .today-label {
      color: var(--muted);
      font-size: 0.9rem;
      margin-left: auto;
    }
    .site-filters {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 16px;
      align-items: center;
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--border);
    }
    .site-filters .filter-label {
      color: var(--muted);
      font-size: 0.85rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    .site-filters label.filter-check {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--text);
      font-size: 0.92rem;
      cursor: pointer;
      user-select: none;
      background: #0f141d;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 6px 12px;
    }
    .site-filters label.filter-check input {
      width: 15px;
      height: 15px;
      accent-color: var(--accent);
      cursor: pointer;
    }
    .site-filters .filter-hint {
      color: var(--muted);
      font-size: 0.82rem;
    }
    .section { margin-bottom: 28px; }
    .section-title {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      margin: 0 0 14px;
    }
    .section-title.warn { color: var(--accent2); }
    .section-title.ok { color: var(--ok); }
    .section-title.cal { color: var(--text); }
    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      flex-shrink: 0;
    }
    .dot.warn { background: var(--accent); }
    .dot.ok { background: var(--ok); }
    .dot.cal { background: #60a5fa; }
    .empty {
      color: var(--muted);
      font-size: 0.95rem;
      padding: 14px 16px;
      border: 1px dashed var(--border);
      border-radius: 12px;
      background: rgba(15, 20, 29, 0.4);
    }
    .card {
      display: grid;
      grid-template-columns: 36px minmax(160px, 1.1fr) minmax(140px, 1.2fr) auto auto minmax(160px, 220px);
      gap: 12px 16px;
      align-items: start;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px 16px;
      margin-bottom: 10px;
    }
    .card.cal-collapsed {
      grid-template-columns: 36px minmax(160px, 1.1fr) minmax(140px, 1.2fr) auto auto auto;
    }
    .card-notes {
      grid-column: 1 / -1;
      margin-top: 2px;
    }
    .card-notes label {
      display: block;
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 6px;
    }
    .card-notes textarea {
      width: 100%;
      min-height: 64px;
      resize: vertical;
      font: inherit;
      font-size: 0.88rem;
      color: var(--text);
      background: #0f141d;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 8px 10px;
      line-height: 1.4;
    }
    .card-notes textarea:focus {
      outline: none;
      border-color: rgba(255, 107, 0, 0.55);
    }
    .card-notes .notes-hint {
      margin: 4px 0 0;
      font-size: 0.72rem;
      color: var(--muted);
    }
    .badge-custom { background: #1d4ed8; color: #fff; }
    .badge-hold { background: #c2410c; color: #fff; }
    .mode-toggle { display: inline-flex; gap: 4px; margin-right: 10px; }
    .mode-toggle button {
      background: #0f141d;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 4px 8px;
      font: inherit;
      font-size: 0.75rem;
      cursor: pointer;
    }
    .mode-toggle button.active { background: #2563eb; color: #fff; }
    .schedule-controls {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-top: 8px;
    }
    .hold-toggle {
      display: inline-flex;
      gap: 5px;
      align-items: center;
      font-size: 0.78rem;
      color: var(--text);
      cursor: pointer;
    }
    .sched-edit { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; align-items: end; }
    .sched-edit label { display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: var(--muted); }
    .sched-edit input {
      background: #0f172a;
      border: 1px solid #334155;
      color: #e2e8f0;
      border-radius: 6px;
      padding: 4px 6px;
      font: inherit;
      font-size: 0.82rem;
    }
    .sched-edit button {
      background: #0f141d;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 5px 8px;
      font: inherit;
      font-size: 0.78rem;
      cursor: pointer;
    }
    .oneoff-list { margin: 6px 0 0; padding-left: 18px; font-size: 12px; }
    .oneoff-list li { display: flex; gap: 8px; align-items: center; }
    .oneoff-list button {
      background: transparent;
      color: #fca5a5;
      border: 0;
      padding: 0;
      cursor: pointer;
      font: inherit;
      font-size: 0.75rem;
    }
    .schedule-error {
      display: block;
      min-height: 1.1em;
      margin-top: 5px;
      color: #fca5a5;
      font-size: 0.76rem;
    }
    .cal-col { min-width: 0; }
    .cal-toggle {
      background: #0f141d;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      height: 30px;
      padding: 0 10px;
      font: inherit;
      font-size: 0.78rem;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
    }
    .cal-toggle:hover { border-color: var(--accent); color: var(--accent2); }
    .mini-cal-wrap.hidden { display: none; }
    .section-tools {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: -6px 0 12px;
    }
    .card.flagged {
      border-color: rgba(255, 107, 0, 0.35);
      background: linear-gradient(90deg, rgba(255, 107, 0, 0.07), var(--card) 40%);
    }
    .card.pending {
      border-style: dashed;
      opacity: 0.95;
    }
    .idx {
      color: var(--muted);
      font-weight: 600;
      font-size: 0.95rem;
      padding-top: 4px;
    }
    .name {
      font-weight: 700;
      font-size: 1.05rem;
      margin: 0 0 4px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .color-swatch {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      flex-shrink: 0;
      box-shadow: 0 0 0 1px rgba(255,255,255,0.12);
    }
    .meta { color: var(--muted); font-size: 0.82rem; margin: 0; line-height: 1.35; }
    .usage-label {
      color: var(--muted);
      font-size: 0.82rem;
      margin: 0 0 6px;
    }
    .bar {
      height: 8px;
      border-radius: 999px;
      background: #0f141d;
      border: 1px solid var(--border);
      overflow: hidden;
    }
    .bar .fill {
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, #22c55e, #4ade80);
    }
    .bar .fill.hot {
      background: linear-gradient(90deg, #f59e0b, #ff6b00);
    }
    .free {
      font-weight: 700;
      font-size: 1.1rem;
      white-space: nowrap;
      text-align: right;
      padding-top: 4px;
    }
    .sched {
      text-align: right;
      min-width: 110px;
      padding-top: 4px;
    }
    .freq {
      font-weight: 700;
      font-size: 0.82rem;
      letter-spacing: 0.04em;
      color: var(--ok);
      margin: 0 0 4px;
    }
    .freq.hold { color: var(--accent2); }
    .next {
      color: var(--muted);
      font-size: 0.78rem;
      margin: 0;
    }
    .status { color: var(--muted); font-size: 0.9rem; margin-left: 6px; }
    .footer {
      color: var(--muted);
      font-size: 0.85rem;
      margin-top: 24px;
    }

    /* Overall + card calendars */
    .calendar-panel {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 18px 20px 20px;
      margin-bottom: 8px;
    }
    .cal-toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      margin-bottom: 14px;
    }
    .cal-toolbar h3 {
      margin: 0;
      flex: 1;
      font-size: 1.15rem;
    }
    .cal-nav { display: flex; gap: 8px; align-items: center; }
    .cal-nav button {
      background: #0f141d;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      height: 32px;
      min-width: 36px;
      cursor: pointer;
      font-weight: 700;
    }
    .cal-grid {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 6px;
    }
    .cal-dow {
      text-align: center;
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      padding: 4px 0 8px;
    }
    .cal-cell {
      min-height: 78px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: #0f141d;
      padding: 6px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .cal-cell.other { opacity: 0.35; }
    .cal-cell.completed {
      background: #16a34a;
      border-color: #15803d;
    }
    .cal-cell.completed .cal-daynum { color: #ecfdf5; }
    .cal-cell.today {
      border-color: rgba(96, 165, 250, 0.7);
      box-shadow: inset 0 0 0 1px rgba(96, 165, 250, 0.25);
    }
    .cal-daynum {
      font-size: 0.78rem;
      font-weight: 700;
      color: var(--muted);
    }
    .cal-cell.today .cal-daynum { color: #93c5fd; }
    .cal-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 3px;
      align-content: flex-start;
    }
    .cal-chip {
      font-size: 0.62rem;
      font-weight: 700;
      padding: 2px 5px;
      border-radius: 999px;
      color: #0b0f14;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      line-height: 1.3;
    }
    .cal-chip.more {
      background: #334155;
      color: #e2e8f0;
    }
    .cal-chip.oneoff {
      outline: 2px solid #38bdf8;
      outline-offset: 1px;
    }
    .cal-legend {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 14px;
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px solid var(--border);
    }
    .cal-legend-item {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.78rem;
      color: var(--muted);
    }
    .cal-legend-swatch {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      flex-shrink: 0;
    }
    .cal-hint {
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 0.8rem;
    }

    .mini-cal {
      border: 1px solid var(--border);
      border-radius: 10px;
      background: #0f141d;
      padding: 8px;
    }
    .mini-cal-title {
      font-size: 0.72rem;
      font-weight: 700;
      color: var(--muted);
      text-align: center;
      margin: 0 0 6px;
      letter-spacing: 0.03em;
      text-transform: uppercase;
    }
    .mini-grid {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 2px;
    }
    .mini-dow {
      text-align: center;
      font-size: 0.58rem;
      color: var(--muted);
      font-weight: 700;
      padding-bottom: 2px;
    }
    .mini-day {
      aspect-ratio: 1;
      border-radius: 5px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.62rem;
      color: var(--muted);
      border: 1px solid transparent;
    }
    .mini-day.other { opacity: 0.25; }
    .mini-day.today {
      border-color: rgba(96, 165, 250, 0.55);
      color: #93c5fd;
    }
    .mini-day.snap {
      color: #0b0f14;
      font-weight: 700;
      cursor: pointer;
    }
    .mini-day.snap:hover {
      filter: brightness(1.08);
    }
    .mini-day.completed {
      background: #16a34a !important;
      color: #ecfdf5;
      font-weight: 700;
      cursor: pointer;
      border-color: #15803d;
    }
    .mini-day.oneoff {
      outline: 2px solid #38bdf8;
      outline-offset: -2px;
    }
    .mini-day.hold-mark {
      background: rgba(255, 107, 0, 0.2);
      color: var(--accent2);
      border-color: rgba(255, 107, 0, 0.35);
    }
    .mini-caption {
      margin: 6px 0 0;
      font-size: 0.68rem;
      color: var(--muted);
      text-align: center;
      line-height: 1.3;
    }

    @media (max-width: 980px) {
      .card, .card.cal-collapsed {
        grid-template-columns: 28px 1fr;
        gap: 8px 12px;
      }
      .usage, .free, .sched, .cal-col { grid-column: 2; }
      .free, .sched { text-align: left; }
      .today-label { margin-left: 0; width: 100%; }
      .cal-cell { min-height: 64px; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>Snapshot Schedule — IBM FlashSystem / Storwize</h1>
      <p class="lede">
        Snapshot frequency scaled to free headroom — fuller systems get snapshotted less often,
        preserving capacity on systems that need room to grow.
        Systems at/above the threshold are held back until capacity is expanded.
        Use the overall calendar for every site, and each card’s calendar for that site alone.
      </p>
      <div class="hero-actions">
        <button type="button" id="refresh-btn" class="btn">Refresh Data</button>
        <button type="button" id="excel-btn" class="btn secondary">Export Excel</button>
        <a class="btn secondary" href="/capacity">Capacity Report</a>
        <a class="btn secondary" href="/fc-wwpn">FC WWPN</a>
        <a class="btn secondary" href="/fc-consistgrp">FlashCopy CGs</a>
        <a class="btn secondary" href="/">Health Dashboard</a>
        <span id="status" class="status"></span>
      </div>
      <div class="controls">
        <div class="badges">
          <span class="badge flagged" id="flagged-badge">0 Flagged</span>
          <span class="badge scheduled" id="scheduled-badge">0 scheduled</span>
        </div>
        <div class="threshold-block">
          <label for="threshold">Enough-space threshold (% used)</label>
          <input type="range" id="threshold" min="50" max="95" step="1" value="80">
          <span class="threshold-value" id="threshold-value">80%</span>
        </div>
        <span class="today-label" id="today-label"></span>
      </div>
      <div class="site-filters" id="site-filters">
        <span class="filter-label">Include in list / Excel</span>
        <label class="filter-check" for="filter-wag1">
          <input type="checkbox" id="filter-wag1" checked>
          WAG1
        </label>
        <label class="filter-check" for="filter-wag2">
          <input type="checkbox" id="filter-wag2" checked>
          WAG2
        </label>
        <label class="filter-check" for="filter-other">
          <input type="checkbox" id="filter-other" checked>
          Other sites
        </label>
        <span class="filter-hint">Uncheck a group to hide it from the schedule and export.</span>
      </div>
    </section>

    <section class="section">
      <h2 class="section-title cal">
        <span class="dot cal"></span>
        Overall snapshot calendar
      </h2>
      <div class="calendar-panel">
        <div class="cal-toolbar">
          <h3 id="cal-month-label">Month</h3>
          <div class="cal-nav">
            <button type="button" id="cal-prev" aria-label="Previous month">‹</button>
            <button type="button" id="cal-today" class="btn secondary" style="height:32px;padding:0 12px;">Today</button>
            <button type="button" id="cal-next" aria-label="Next month">›</button>
          </div>
        </div>
        <div class="cal-grid" id="overall-calendar"></div>
        <div class="cal-legend" id="cal-legend"></div>
        <p class="cal-hint">
          Color dots mark planned snapshot days. Solid green = completed / done (click a site calendar day to toggle).
          Orange = held back (flagged). Green → amber = scheduled,
          warmer colors mean fuller capacity / less frequent snapshots.
        </p>
      </div>
    </section>

    <section class="section">
      <h2 class="section-title warn">
        <span class="dot warn"></span>
        Insufficient headroom — expand before snapshotting
      </h2>
      <div class="section-tools">
        <button type="button" class="cal-toggle" id="collapse-all-cals">Collapse card calendars</button>
        <button type="button" class="cal-toggle" id="expand-all-cals">Expand card calendars</button>
      </div>
      <div id="flagged-list"></div>
    </section>

    <section class="section">
      <h2 class="section-title ok">
        <span class="dot ok"></span>
        Snapshot schedule — enough space
      </h2>
      <div id="scheduled-list"></div>
    </section>

    <section class="section" id="pending-section" style="display:none">
      <h2 class="section-title" style="color:var(--muted)">
        <span class="dot" style="background:var(--muted)"></span>
        Awaiting capacity data
      </h2>
      <div id="pending-list"></div>
    </section>

    <p class="footer">
      LaunchPad Snapshot Schedule v{{APP_VERSION}} ·
      Uses live pool capacity from monitored sites. Calendars show planned snapshot days for this month —
      LaunchPad does not create the snapshots automatically.
    </p>
  </div>
  <script>
    const CAPACITY_UNIT_MODE = "{{CAPACITY_UNIT_MODE}}";
    const THRESHOLD_KEY = "launchpad.snapshotSchedule.threshold";
    const NOTES_KEY = "launchpad.snapshotSchedule.notes";
    const CAL_COLLAPSED_KEY = "launchpad.snapshotSchedule.calCollapsed";
    const OVERRIDES_KEY = "launchpad.snapshotSchedule.overrides";
    const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const SITE_PALETTE = [
      "#4ade80", "#60a5fa", "#a78bfa", "#f472b6", "#34d399",
      "#fbbf24", "#38bdf8", "#fb923c", "#c084fc", "#2dd4bf",
      "#86efac", "#93c5fd",
    ];
    const statusEl = document.getElementById("status");
    const flaggedListEl = document.getElementById("flagged-list");
    const scheduledListEl = document.getElementById("scheduled-list");
    const pendingListEl = document.getElementById("pending-list");
    const pendingSectionEl = document.getElementById("pending-section");
    const flaggedBadge = document.getElementById("flagged-badge");
    const scheduledBadge = document.getElementById("scheduled-badge");
    const thresholdInput = document.getElementById("threshold");
    const thresholdValue = document.getElementById("threshold-value");
    const todayLabel = document.getElementById("today-label");
    const refreshBtn = document.getElementById("refresh-btn");
    const excelBtn = document.getElementById("excel-btn");
    const filterWag1 = document.getElementById("filter-wag1");
    const filterWag2 = document.getElementById("filter-wag2");
    const filterOther = document.getElementById("filter-other");
    const overallCalendarEl = document.getElementById("overall-calendar");
    const calLegendEl = document.getElementById("cal-legend");
    const calMonthLabel = document.getElementById("cal-month-label");
    let cardsCache = [];
    let viewMonth = null; // Date at 1st of month
    let lastRows = [];
    let notesByCard = {};
    let calCollapsedByCard = {};
    let notesPersistedInDb = false;
    let noteSaveTimers = {};
    let overridesCache = {};
    const overridesPersistTimers = {};
    let overridesDbAvailable = false;
    const FILTER_KEY = "launchpad.snapshotSchedule.siteFilters";

    function loadSiteFilters() {
      try {
        const raw = localStorage.getItem(FILTER_KEY);
        if (!raw) return;
        const data = JSON.parse(raw);
        if (typeof data.wag1 === "boolean") filterWag1.checked = data.wag1;
        if (typeof data.wag2 === "boolean") filterWag2.checked = data.wag2;
        if (typeof data.other === "boolean") filterOther.checked = data.other;
      } catch (_err) {
        /* ignore */
      }
    }

    function saveSiteFilters() {
      try {
        localStorage.setItem(
          FILTER_KEY,
          JSON.stringify({
            wag1: filterWag1.checked,
            wag2: filterWag2.checked,
            other: filterOther.checked,
          })
        );
      } catch (_err) {
        /* ignore */
      }
    }

    function selectedSiteGroups() {
      const groups = [];
      if (filterWag1.checked) groups.push("wag1");
      if (filterWag2.checked) groups.push("wag2");
      if (filterOther.checked) groups.push("other");
      return groups;
    }

    function siteGroup(card) {
      const hay = [
        card.name,
        card.category,
        card.host,
        card.model,
        card.device_profile,
      ]
        .map((part) => String(part || "").toLowerCase())
        .join(" ");
      if (hay.includes("wag1")) return "wag1";
      if (hay.includes("wag2")) return "wag2";
      return "other";
    }

    function cardPassesSiteFilter(card) {
      const allowed = new Set(selectedSiteGroups());
      if (!allowed.size) return false;
      return allowed.has(siteGroup(card));
    }

    function exportFileLabel() {
      const groups = selectedSiteGroups();
      if (groups.length === 3) return "All";
      if (!groups.length) return "None";
      return groups.map((g) => (g === "other" ? "Other" : g.toUpperCase())).join("_");
    }

    try {
      notesByCard = JSON.parse(localStorage.getItem(NOTES_KEY) || "{}") || {};
    } catch (_err) {
      notesByCard = {};
    }
    try {
      calCollapsedByCard = JSON.parse(localStorage.getItem(CAL_COLLAPSED_KEY) || "{}") || {};
    } catch (_err) {
      calCollapsedByCard = {};
    }

    function loadOverridesLocal() {
      try {
        overridesCache = JSON.parse(localStorage.getItem(OVERRIDES_KEY) || "{}") || {};
      } catch (_err) {
        overridesCache = {};
      }
    }

    function saveOverridesLocal() {
      try {
        localStorage.setItem(OVERRIDES_KEY, JSON.stringify(overridesCache));
      } catch (_err) {
        /* keep in memory */
      }
    }

    async function loadOverridesFromDb() {
      try {
        const res = await fetch("/api/snapshot-schedule-overrides");
        if (!res.ok) throw new Error("unavailable");
        const data = await res.json();
        overridesDbAvailable = Boolean(data.persisted);
        const remote =
          data.overrides && typeof data.overrides === "object" ? data.overrides : {};
        overridesCache = { ...overridesCache, ...remote };
        saveOverridesLocal();
        if (
          overridesDbAvailable &&
          Object.keys(overridesCache).length &&
          Object.keys(remote).length === 0
        ) {
          await fetch("/api/snapshot-schedule-overrides", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ overrides: overridesCache }),
          });
        }
      } catch (_err) {
        overridesDbAvailable = false;
      }
    }

    function persistOverride(cardId) {
      saveOverridesLocal();
      if (!overridesDbAvailable) return;
      const timerKey = String(cardId);
      clearTimeout(overridesPersistTimers[timerKey]);
      overridesPersistTimers[timerKey] = setTimeout(async () => {
        delete overridesPersistTimers[timerKey];
        try {
          await fetch("/api/snapshot-schedule-overrides", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              card_id: cardId,
              override: overridesCache[timerKey] || {
                mode: "auto",
                held: false,
                interval_days: 7,
                start_date: "",
                time: "02:00",
                one_offs: [],
                completed_dates: [],
              },
            }),
          });
        } catch (_err) {
          /* keep local cache */
        }
      }, 400);
    }

    function getOverride(cardId) {
      return overridesCache[String(cardId)] || null;
    }

    function ensureOverride(cardId) {
      const key = String(cardId);
      if (!overridesCache[key]) {
        overridesCache[key] = {
          mode: "auto",
          held: false,
          interval_days: 7,
          start_date: "",
          time: "02:00",
          one_offs: [],
          completed_dates: [],
        };
      }
      if (!Array.isArray(overridesCache[key].completed_dates)) {
        overridesCache[key].completed_dates = [];
      }
      return overridesCache[key];
    }

    function saveNotesLocal() {
      try {
        localStorage.setItem(NOTES_KEY, JSON.stringify(notesByCard));
      } catch (_err) {
        /* ignore */
      }
    }

    async function loadNotesFromDb() {
      try {
        const res = await fetch("/api/snapshot-notes");
        if (!res.ok) return;
        const data = await res.json();
        const remote = data.notes || {};
        notesPersistedInDb = true;
        // Prefer DB notes; keep any local-only keys as a one-time merge.
        const merged = { ...notesByCard, ...remote };
        notesByCard = merged;
        saveNotesLocal();
        if (Object.keys(notesByCard).length && Object.keys(remote).length === 0) {
          await fetch("/api/snapshot-notes", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ notes: notesByCard }),
          });
        }
      } catch (_err) {
        notesPersistedInDb = false;
      }
    }

    function persistNoteToDb(cardId) {
      if (!notesPersistedInDb) {
        saveNotesLocal();
        return;
      }
      if (noteSaveTimers[cardId]) clearTimeout(noteSaveTimers[cardId]);
      noteSaveTimers[cardId] = setTimeout(async () => {
        try {
          await fetch("/api/snapshot-notes", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              card_id: cardId,
              note: notesByCard[cardId] || "",
            }),
          });
          saveNotesLocal();
        } catch (_err) {
          saveNotesLocal();
        }
      }, 400);
    }

    function saveCalCollapsed() {
      try {
        localStorage.setItem(CAL_COLLAPSED_KEY, JSON.stringify(calCollapsedByCard));
      } catch (_err) {
        /* ignore */
      }
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function formatBytes(value) {
      if (!value || value <= 0) return "0 B";
      const si = CAPACITY_UNIT_MODE === "si";
      const units = si
        ? ["B", "KB", "MB", "GB", "TB", "PB"]
        : ["B", "KiB", "MiB", "GiB", "TiB", "PiB"];
      const step = si ? 1000 : 1024;
      let size = value;
      let unit = 0;
      while (size >= step && unit < units.length - 1) {
        size /= step;
        unit += 1;
      }
      return unit === 0 ? `${Math.round(size)} ${units[unit]}` : `${size.toFixed(1)} ${units[unit]}`;
    }

    function formatDate(d) {
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    }

    function startOfDay(date) {
      const d = new Date(date.getTime());
      d.setHours(0, 0, 0, 0);
      return d;
    }

    function addDays(date, days) {
      const d = new Date(date.getTime());
      d.setDate(d.getDate() + days);
      return d;
    }

    function dateKey(d) {
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      return `${y}-${m}-${day}`;
    }

    function sameDay(a, b) {
      return dateKey(a) === dateKey(b);
    }

    function intervalDays(usedPct, threshold) {
      const t = Math.max(0, Math.min(1, usedPct / threshold));
      return Math.max(2, Math.round(2 + t * 19));
    }

    function formatFrequency(days) {
      if (days === 7) return "WEEKLY";
      if (days === 14) return "BIWEEKLY";
      return `EVERY ${days} DAYS`;
    }

    function barTone(usedPct, threshold) {
      return usedPct >= threshold * 0.9 ? "hot" : "";
    }

    /** Color by headroom: greener when emptier, warmer when fuller / held. */
    function scheduleColor(row, colorIndex) {
      if (row.held) return "#ff6b00";
      const threshold = Number(thresholdInput.value) || 80;
      const ratio = Math.max(0, Math.min(1, row.usedPct / threshold));
      if (ratio < 0.5) return SITE_PALETTE[colorIndex % SITE_PALETTE.length];
      if (ratio < 0.75) return "#fbbf24";
      if (ratio < 0.9) return "#fb923c";
      return "#f97316";
    }

    function parseSizeBytes(label) {
      const text = String(label || "").trim();
      const match = text.match(/^(\\d+(?:\\.\\d+)?)\\s*([TGMK])B?/i);
      if (!match) return 0;
      const amount = Number(match[1]);
      const unit = match[2].toUpperCase();
      const mult = { K: 1024, M: 1024 ** 2, G: 1024 ** 3, T: 1024 ** 4 };
      return Math.round(amount * (mult[unit] || 1));
    }

    function capacityFromCommands(card) {
      const results = Array.isArray(card.command_results) ? card.command_results : [];
      for (const item of results) {
        if (item.error) continue;
        const label = String(item.label || "").toLowerCase();
        const command = String(item.command || "").toLowerCase();
        const isRoot =
          label.includes("capacity - root disk") ||
          command.includes("df -h /") ||
          label.includes("capacity - all filesystems");
        if (!isRoot) continue;
        const text = String(item.output || "").trim();
        if (!text) continue;
        const sized = text.match(
          /(\\d+(?:\\.\\d+)?)\\s*%\\s*used\\s*\\(([^/]+?)\\s*\\/\\s*([^)]+)\\)/i
        );
        if (sized) {
          const usedPct = Number(sized[1]) || 0;
          const used = parseSizeBytes(sized[2]);
          const total = parseSizeBytes(sized[3]);
          const freeBytes = total > used ? total - used : 0;
          return { usedPct, freeBytes, poolName: "Root disk" };
        }
        const pctOnly = text.match(/(\\d+(?:\\.\\d+)?)\\s*%\\s*(?:used)?\\b/i);
        if (pctOnly) {
          return {
            usedPct: Number(pctOnly[1]) || 0,
            freeBytes: 0,
            poolName: "Root disk",
          };
        }
        const dfLine = text.match(
          /\\S+\\s+(\\d+(?:\\.\\d+)?[TGMK]i?B?)\\s+(\\d+(?:\\.\\d+)?[TGMK]i?B?)\\s+(\\d+(?:\\.\\d+)?[TGMK]i?B?)\\s+(\\d+(?:\\.\\d+)?)%\\s+\\//i
        );
        if (dfLine) {
          const total = parseSizeBytes(dfLine[1]);
          const used = parseSizeBytes(dfLine[2]);
          const freeBytes = parseSizeBytes(dfLine[3]);
          return {
            usedPct: Number(dfLine[4]) || 0,
            freeBytes: freeBytes || Math.max(0, total - used),
            poolName: "Root disk",
          };
        }
      }
      return null;
    }

    function pickCapacity(card) {
      const pools = Array.isArray(card.pools) ? card.pools.slice() : [];
      if (pools.length) {
        pools.sort((a, b) => (Number(b.used_pct) || 0) - (Number(a.used_pct) || 0));
        const pool = pools[0];
        return {
          usedPct: Number(pool.used_pct) || 0,
          freeBytes: Number(pool.free_bytes) || 0,
          poolName: pool.name || "Pool",
        };
      }
      const cap = card.capacity_summary;
      if (cap && (cap.total_bytes || cap.used_pct != null)) {
        return {
          usedPct: Number(cap.used_pct) || 0,
          freeBytes: Number(cap.free_bytes) || 0,
          poolName: cap.name || "System",
        };
      }
      return capacityFromCommands(card);
    }

    function isStorageLike(card) {
      const profile = String(card.device_profile || "").toLowerCase();
      if (
        profile.includes("flashsystem") ||
        profile.includes("storwize") ||
        profile.includes("svc") ||
        profile.startsWith("ibm_") ||
        profile.includes("linux") ||
        profile.includes("vultr")
      ) {
        return true;
      }
      return Boolean(pickCapacity(card));
    }

    function firstSnapshotDate(today, index, days) {
      return addDays(today, 1 + (index % Math.max(1, days || 1)));
    }

    function buildRows(threshold) {
      const today = startOfDay(new Date());
      const rows = [];
      for (const card of cardsCache) {
        if (!cardPassesSiteFilter(card)) continue;
        if (!isStorageLike(card)) continue;
        const cap = pickCapacity(card);
        if (!cap) {
          const ov = getOverride(card.id);
          const mode = ov && ov.mode === "custom" ? "custom" : "auto";
          const manualHeld = Boolean(ov && ov.held);
          rows.push({
            card,
            usedPct: 0,
            freeBytes: 0,
            poolName: "—",
            held: manualHeld,
            days:
              mode === "custom" && ov
                ? Math.max(2, Number(ov.interval_days) || 7)
                : null,
            frequency: "NO CAPACITY DATA",
            noData: true,
            color: "#6b7280",
            colorIndex: 0,
            startDate:
              mode === "custom" && ov ? parseDateKey(ov.start_date) : null,
            siteGroup: siteGroup(card),
            mode,
            timeOfDay: (ov && ov.time) || "",
            oneOffs: (ov && Array.isArray(ov.one_offs) ? ov.one_offs : []),
            manualHeld,
          });
          continue;
        }
        const usedPct = cap.usedPct;
        let held = usedPct >= threshold;
        let days = held ? null : intervalDays(usedPct, threshold);
        const ov = getOverride(card.id);
        let mode = "auto";
        let manualHeld = false;
        if (ov) {
          mode = ov.mode === "custom" ? "custom" : "auto";
          manualHeld = Boolean(ov.held);
          if (manualHeld) {
            held = true;
            days = null;
          } else if (mode === "custom") {
            held = false;
            days = Math.max(2, Number(ov.interval_days) || 7);
          }
        }
        rows.push({
          card,
          usedPct,
          freeBytes: cap.freeBytes,
          poolName: cap.poolName,
          held,
          days,
          frequency: held ? "HOLD — EXPAND FIRST" : formatFrequency(days),
          noData: false,
          siteGroup: siteGroup(card),
          mode,
          timeOfDay: (ov && ov.time) || "",
          oneOffs: (ov && Array.isArray(ov.one_offs) ? ov.one_offs : []),
          manualHeld,
        });
      }
      const ready = rows.filter((row) => !row.noData);
      ready.sort((a, b) => a.usedPct - b.usedPct);
      ready.forEach((row, i) => {
        row.colorIndex = i;
        row.color = scheduleColor(row, i);
        row.startDate = row.held ? null : firstSnapshotDate(today, i + 1, row.days);
        const ov = getOverride(row.card.id);
        if (ov && !row.manualHeld && row.mode === "custom" && ov.start_date) {
          const parts = String(ov.start_date).split("-").map(Number);
          if (parts.length === 3 && parts.every((n) => Number.isFinite(n))) {
            row.startDate = startOfDay(new Date(parts[0], parts[1] - 1, parts[2]));
          }
        }
        row.frequency = row.held
          ? "HOLD — EXPAND FIRST"
          : row.mode === "custom"
            ? formatFrequency(row.days)
            : row.frequency;
      });
      return rows;
    }

    function snapshotDatesInRange(startDate, interval, rangeStart, rangeEnd) {
      const dates = [];
      if (!startDate || !interval) return dates;
      let d = startOfDay(startDate);
      // Walk back to ensure we catch earlier occurrences in the visible range
      while (d > rangeStart) {
        d = addDays(d, -interval);
      }
      while (d < rangeStart) {
        d = addDays(d, interval);
      }
      while (d <= rangeEnd) {
        dates.push(new Date(d.getTime()));
        d = addDays(d, interval);
      }
      return dates;
    }

    function parseDateKey(value) {
      const parts = String(value || "").split("-").map(Number);
      if (parts.length !== 3 || !parts.every((n) => Number.isFinite(n))) return null;
      const date = startOfDay(new Date(parts[0], parts[1] - 1, parts[2]));
      return date.getFullYear() === parts[0] &&
        date.getMonth() === parts[1] - 1 &&
        date.getDate() === parts[2]
        ? date
        : null;
    }

    function scheduleEventsInRange(row, rangeStart, rangeEnd) {
      if (row.held || !row.startDate || !row.days) return [];
      const byDate = {};
      for (const date of snapshotDatesInRange(row.startDate, row.days, rangeStart, rangeEnd)) {
        byDate[dateKey(date)] = {
          date,
          time: row.mode === "custom" ? row.timeOfDay : "",
          kind: "recurring",
          label: "",
        };
      }
      if (row.mode === "custom") {
        for (const oneOff of row.oneOffs || []) {
          const date = parseDateKey(oneOff.date);
          if (!date || date < rangeStart || date > rangeEnd) continue;
          byDate[dateKey(date)] = {
            date,
            time: String(oneOff.time || ""),
            kind: "oneoff",
            label: String(oneOff.label || ""),
          };
        }
      }
      return Object.values(byDate);
    }

    function eventTooltip(row, event) {
      const details = [row.card.name, row.frequency];
      if (event.time) details.push(event.time);
      if (event.kind === "oneoff") details.push(event.label ? `One-off: ${event.label}` : "One-off");
      return details.join(" · ");
    }

    function subtitle(card) {
      const parts = [
        card.category || "",
        card.model || card.device_profile || "",
        card.host || "",
      ].filter(Boolean);
      return parts.join(" · ");
    }

    function shortName(name) {
      const s = String(name || "");
      return s.length > 10 ? `${s.slice(0, 9)}…` : s;
    }

    function monthBounds(monthDate) {
      const y = monthDate.getFullYear();
      const m = monthDate.getMonth();
      const first = new Date(y, m, 1);
      const last = new Date(y, m + 1, 0);
      const gridStart = addDays(first, -first.getDay());
      const gridEnd = addDays(last, 6 - last.getDay());
      return { first, last, gridStart, gridEnd };
    }

    function renderMiniCalendar(row, monthDate, today) {
      const { first, last, gridStart, gridEnd } = monthBounds(monthDate);
      const events = scheduleEventsInRange(row, gridStart, gridEnd);
      const eventsByDate = Object.fromEntries(events.map((event) => [dateKey(event.date), event]));
      const cardId = String(row.card.id);
      const completedSet = new Set(
        ((getOverride(cardId) || {}).completed_dates || []).map(String)
      );
      const monthLabel = monthDate.toLocaleDateString("en-US", { month: "short", year: "numeric" });
      let cells = DOW.map((d) => `<div class="mini-dow">${d[0]}</div>`).join("");
      let cursor = new Date(gridStart.getTime());
      while (cursor <= gridEnd) {
        const key = dateKey(cursor);
        const other = cursor.getMonth() !== first.getMonth();
        const isToday = sameDay(cursor, today);
        let cls = "mini-day";
        if (other) cls += " other";
        if (isToday) cls += " today";
        let style = "";
        let toggleAttrs = "";
        if (row.held) {
          if (!other && cursor.getDate() === today.getDate() && sameDay(cursor, today)) {
            cls += " hold-mark";
          }
        } else if (eventsByDate[key]) {
          const event = eventsByDate[key];
          const isCompleted = completedSet.has(key);
          cls += isCompleted ? " completed" : " snap";
          if (event.kind === "oneoff") cls += " oneoff";
          if (!isCompleted) style = ` style="background:${row.color};"`;
          toggleAttrs = ` data-card-id="${escapeHtml(cardId)}" data-date="${escapeHtml(key)}" role="button" tabindex="0"`;
        }
        const event = eventsByDate[key];
        let titleText = event ? eventTooltip(row, event) : "";
        if (event && completedSet.has(key)) titleText = `${titleText} · completed`;
        const title = titleText ? ` title="${escapeHtml(titleText)}"` : "";
        cells += `<div class="${cls}"${style}${toggleAttrs}${title}>${cursor.getDate()}</div>`;
        cursor = addDays(cursor, 1);
      }
      const caption = row.held
        ? "No snapshots while flagged"
        : `${row.frequency.toLowerCase()}${row.timeOfDay ? ` · ${row.timeOfDay}` : ""} · ${events.length} day(s) this month`;
      return `
        <div class="mini-cal">
          <p class="mini-cal-title">${escapeHtml(monthLabel)}</p>
          <div class="mini-grid">${cells}</div>
          <p class="mini-caption">${escapeHtml(caption)}</p>
        </div>
      `;
    }

    function renderOverallCalendar(rows, monthDate, today) {
      const { first, last, gridStart, gridEnd } = monthBounds(monthDate);
      calMonthLabel.textContent = monthDate.toLocaleDateString("en-US", {
        month: "long",
        year: "numeric",
      });

      const byDay = {};
      for (const row of rows) {
        if (row.held || !row.startDate || !row.days) continue;
        for (const event of scheduleEventsInRange(row, gridStart, gridEnd)) {
          const key = dateKey(event.date);
          if (!byDay[key]) byDay[key] = [];
          byDay[key].push({ row, event });
        }
      }

      let html = DOW.map((d) => `<div class="cal-dow">${d}</div>`).join("");
      let cursor = new Date(gridStart.getTime());
      while (cursor <= gridEnd) {
        const key = dateKey(cursor);
        const other = cursor.getMonth() !== first.getMonth();
        const isToday = sameDay(cursor, today);
        const events = byDay[key] || [];
        const anyCompleted = events.some(({ row }) => {
          const dates = ((getOverride(row.card.id) || {}).completed_dates || []).map(String);
          return dates.includes(key);
        });
        const shown = events.slice(0, 3);
        const extra = events.length - shown.length;
        const chips = shown
          .map(
            ({ row, event }) =>
              `<span class="cal-chip${event.kind === "oneoff" ? " oneoff" : ""}" style="background:${row.color};" title="${escapeHtml(eventTooltip(row, event))}">${escapeHtml(shortName(row.card.name))}${event.time ? ` ${escapeHtml(event.time)}` : ""}</span>`
          )
          .join("");
        const moreChip = extra > 0 ? `<span class="cal-chip more">+${extra}</span>` : "";
        html += `
          <div class="cal-cell${other ? " other" : ""}${isToday ? " today" : ""}${anyCompleted ? " completed" : ""}">
            <div class="cal-daynum">${cursor.getDate()}</div>
            <div class="cal-chips">${chips}${moreChip}</div>
          </div>
        `;
        cursor = addDays(cursor, 1);
      }
      overallCalendarEl.innerHTML = html;

      const legendRows = rows.slice();
      calLegendEl.innerHTML = legendRows.length
        ? legendRows
            .map((row) => {
              const label = row.held
                ? `${row.card.name} (held)`
                : `${row.card.name} · ${row.frequency.toLowerCase()}`;
              return `
                <span class="cal-legend-item">
                  <span class="cal-legend-swatch" style="background:${row.color};"></span>
                  ${escapeHtml(label)}
                </span>
              `;
            })
            .join("")
        : '<span class="cal-legend-item">No scheduled sites yet</span>';
    }

    function renderCard(row, index, today) {
      const held = row.held;
      const noData = Boolean(row.noData);
      const pct = row.usedPct;
      const fillClass = noData ? "ok" : barTone(pct, Number(thresholdInput.value));
      const nextText = noData
        ? "click Refresh Data"
        : held
          ? "waiting on capacity"
          : `starts ${formatDate(row.startDate)}`;
      const month = viewMonth || new Date(today.getFullYear(), today.getMonth(), 1);
      const cardId = String(row.card.id);
      const collapsed = Object.prototype.hasOwnProperty.call(calCollapsedByCard, cardId)
        ? Boolean(calCollapsedByCard[cardId])
        : true;
      const note = notesByCard[cardId] || "";
      const override = getOverride(cardId);
      const mode = row.mode || (override && override.mode === "custom" ? "custom" : "auto");
      const manualHeld = Boolean(row.manualHeld || (override && override.held));
      const customBadges = [
        mode === "custom" ? '<span class="badge badge-custom">CUSTOM</span>' : "",
        held ? '<span class="badge badge-hold">HOLD</span>' : "",
      ].join("");
      const customFields = mode === "custom" && !held
        ? `
          <div class="sched-edit" data-custom-edit="${escapeHtml(cardId)}">
            <label>Interval days
              <input class="custom-interval" data-card-id="${escapeHtml(cardId)}" type="number" min="2" step="1" value="${escapeHtml((override && override.interval_days) || row.days || 7)}">
            </label>
            <label>Start date
              <input class="custom-start-date" data-card-id="${escapeHtml(cardId)}" type="date" value="${escapeHtml((override && override.start_date) || dateKey(row.startDate))}">
            </label>
            <label>Time
              <input class="custom-time" data-card-id="${escapeHtml(cardId)}" type="time" value="${escapeHtml((override && override.time) || "02:00")}">
            </label>
          </div>
          <div class="sched-edit" data-oneoff-edit="${escapeHtml(cardId)}">
            <label>One-off date
              <input class="oneoff-date" data-card-id="${escapeHtml(cardId)}" type="date">
            </label>
            <label>Time
              <input class="oneoff-time" data-card-id="${escapeHtml(cardId)}" type="time" value="02:00">
            </label>
            <label>Label (optional)
              <input class="oneoff-label" data-card-id="${escapeHtml(cardId)}" type="text" maxlength="120" placeholder="Change window">
            </label>
            <button type="button" class="add-oneoff" data-card-id="${escapeHtml(cardId)}">Add one-off</button>
          </div>
          <ul class="oneoff-list">
            ${(row.oneOffs || []).map((oneOff, oneOffIndex) => `
              <li>
                <span>${escapeHtml(oneOff.date)} ${escapeHtml(oneOff.time || "")}${oneOff.label ? ` · ${escapeHtml(oneOff.label)}` : ""}</span>
                <button type="button" class="remove-oneoff" data-card-id="${escapeHtml(cardId)}" data-oneoff-index="${oneOffIndex}">Remove</button>
              </li>
            `).join("")}
          </ul>
        `
        : "";
      const toggleLabel = collapsed ? "Show calendar" : "Hide calendar";
      const usageLabel = noData
        ? (row.card.error
            ? `Refresh error: ${escapeHtml(String(row.card.error))}`
            : "Capacity not loaded yet — keep LaunchPad unlocked and click Refresh Data")
        : `${pct.toFixed(1)}% used · pool: ${escapeHtml(row.poolName)}`;
      const freeLabel = noData ? "—" : `${formatBytes(row.freeBytes)} free`;
      return `
        <article class="card${held ? " flagged" : ""}${collapsed ? " cal-collapsed" : ""}${noData ? " pending" : ""}" data-card-id="${escapeHtml(cardId)}">
          <div class="idx">${index}</div>
          <div>
            <p class="name">
              <span class="color-swatch" style="background:${row.color};"></span>
              ${escapeHtml(row.card.name)}
              ${customBadges}
            </p>
            <p class="meta">${escapeHtml(subtitle(row.card))}</p>
          </div>
          <div class="usage">
            <p class="usage-label">${usageLabel}</p>
            <div class="bar"><div class="fill ${fillClass}" style="width:${noData ? 0 : Math.min(100, pct).toFixed(1)}%;"></div></div>
          </div>
          <div class="free">${escapeHtml(freeLabel)}</div>
          <div class="sched">
            <p class="freq${held || noData ? " hold" : ""}">${escapeHtml(row.frequency)}</p>
            <p class="next">${escapeHtml(nextText)}</p>
          </div>
          <div class="cal-col">
            <button type="button" class="cal-toggle card-cal-toggle" data-card-id="${escapeHtml(cardId)}" aria-expanded="${collapsed ? "false" : "true"}">${toggleLabel}</button>
            <div class="mini-cal-wrap${collapsed ? " hidden" : ""}" data-cal-for="${escapeHtml(cardId)}">
              ${noData ? '<p class="mini-caption">Calendar available after capacity loads</p>' : renderMiniCalendar(row, month, today)}
            </div>
          </div>
          <div class="card-notes">
            <div class="schedule-controls">
              <div class="mode-toggle" role="group" aria-label="Schedule mode for ${escapeHtml(row.card.name)}">
                <button type="button" class="set-mode${mode === "auto" ? " active" : ""}" data-card-id="${escapeHtml(cardId)}" data-mode="auto">Auto</button>
                <button type="button" class="set-mode${mode === "custom" ? " active" : ""}" data-card-id="${escapeHtml(cardId)}" data-mode="custom">Custom</button>
              </div>
              <label class="hold-toggle">
                <input type="checkbox" class="set-hold" data-card-id="${escapeHtml(cardId)}"${manualHeld ? " checked" : ""}>
                Hold schedule
              </label>
            </div>
            ${customFields}
            <span class="schedule-error" id="schedule-error-${escapeHtml(cardId)}" aria-live="polite"></span>
            <label for="note-${escapeHtml(cardId)}">Comments / notes</label>
            <textarea
              id="note-${escapeHtml(cardId)}"
              class="card-note"
              data-card-id="${escapeHtml(cardId)}"
              placeholder="Add notes for this site (snapshot window, contact, change ticket…)"
              rows="3"
            >${escapeHtml(note)}</textarea>
            <p class="notes-hint" id="notes-hint-${escapeHtml(cardId)}">
              ${notesPersistedInDb
                ? "Saved in LaunchPad database (and this browser)."
                : "Saved in this browser only — unlock LaunchPad to store in the database."}
            </p>
          </div>
        </article>
      `;
    }

    function setScheduleError(cardId, message) {
      const errorEl = document.getElementById(`schedule-error-${cardId}`);
      if (errorEl) errorEl.textContent = message;
    }

    function validDate(value) {
      return Boolean(parseDateKey(value));
    }

    function validTime(value) {
      const match = String(value || "").match(/^\\d{1,2}:\\d{2}$/);
      if (!match) return false;
      const [hours, minutes] = value.split(":").map(Number);
      return hours >= 0 && hours <= 23 && minutes >= 0 && minutes <= 59;
    }

    function setMode(cardId, mode) {
      const override = ensureOverride(cardId);
      override.mode = mode === "custom" ? "custom" : "auto";
      if (override.mode === "custom") {
        if (!override.time) override.time = "02:00";
        if (!override.interval_days) override.interval_days = 7;
        if (!override.start_date) {
          const date = new Date();
          date.setDate(date.getDate() + 1);
          override.start_date = dateKey(startOfDay(date));
        }
      }
      persistOverride(cardId);
      render();
    }

    function setHeld(cardId, held) {
      const override = ensureOverride(cardId);
      override.held = Boolean(held);
      persistOverride(cardId);
      render();
    }

    function toggleCompletedDate(cardId, dateStr) {
      const key = String(dateStr || "");
      if (!validDate(key)) return;
      const override = ensureOverride(cardId);
      const dates = Array.isArray(override.completed_dates)
        ? override.completed_dates.map(String)
        : [];
      const idx = dates.indexOf(key);
      if (idx >= 0) dates.splice(idx, 1);
      else dates.push(key);
      dates.sort();
      override.completed_dates = dates;
      persistOverride(cardId);
      render();
    }

    function pruneCompletedForRows(rows) {
      const today = startOfDay(new Date());
      const rangeStart = addDays(today, -400);
      const rangeEnd = addDays(today, 800);
      for (const row of rows) {
        if (row.held || row.noData) continue;
        const cardId = String(row.card.id);
        const ov = getOverride(cardId);
        if (!ov || !Array.isArray(ov.completed_dates) || !ov.completed_dates.length) continue;
        const planned = new Set(
          scheduleEventsInRange(row, rangeStart, rangeEnd).map((event) => dateKey(event.date))
        );
        const next = ov.completed_dates.map(String).filter((d) => planned.has(d)).sort();
        const prev = ov.completed_dates.map(String).slice().sort();
        if (next.join(",") !== prev.join(",")) {
          ov.completed_dates = next;
          persistOverride(cardId);
        }
      }
    }

    function updateCustomSchedule(cardId) {
      const cardEl = document.querySelector(`.card[data-card-id="${cardId}"]`);
      if (!cardEl) return;
      const intervalValue = cardEl.querySelector(".custom-interval")?.value;
      const startDate = cardEl.querySelector(".custom-start-date")?.value;
      const time = cardEl.querySelector(".custom-time")?.value;
      const intervalDays = Number(intervalValue);
      if (!Number.isInteger(intervalDays) || intervalDays < 2) {
        setScheduleError(cardId, "Interval must be a whole number of at least 2 days.");
        return;
      }
      if (!validDate(startDate)) {
        setScheduleError(cardId, "Enter a valid start date.");
        return;
      }
      if (!validTime(time)) {
        setScheduleError(cardId, "Enter a valid time in 24-hour HH:MM format.");
        return;
      }
      const override = ensureOverride(cardId);
      override.interval_days = intervalDays;
      override.start_date = startDate;
      override.time = time;
      setScheduleError(cardId, "");
      persistOverride(cardId);
      render();
    }

    function addOneOff(cardId) {
      const cardEl = document.querySelector(`.card[data-card-id="${cardId}"]`);
      if (!cardEl) return;
      const date = cardEl.querySelector(".oneoff-date")?.value;
      const time = cardEl.querySelector(".oneoff-time")?.value;
      const label = cardEl.querySelector(".oneoff-label")?.value.trim() || "";
      if (!validDate(date)) {
        setScheduleError(cardId, "Enter a valid one-off date.");
        return;
      }
      if (!validTime(time)) {
        setScheduleError(cardId, "Enter a valid one-off time in 24-hour HH:MM format.");
        return;
      }
      const override = ensureOverride(cardId);
      override.one_offs = Array.isArray(override.one_offs) ? override.one_offs : [];
      override.one_offs.push({ date, time, label });
      setScheduleError(cardId, "");
      persistOverride(cardId);
      render();
    }

    function removeOneOff(cardId, index) {
      const override = ensureOverride(cardId);
      const oneOffs = Array.isArray(override.one_offs) ? override.one_offs : [];
      if (!Number.isInteger(index) || index < 0 || index >= oneOffs.length) return;
      oneOffs.splice(index, 1);
      persistOverride(cardId);
      render();
    }

    function bindCardInteractions() {
      document.querySelectorAll(".card-cal-toggle").forEach((btn) => {
        btn.addEventListener("click", () => {
          const cardId = btn.getAttribute("data-card-id");
          const cardEl = document.querySelector(`.card[data-card-id="${cardId}"]`);
          const wrap = document.querySelector(`.mini-cal-wrap[data-cal-for="${cardId}"]`);
          if (!cardEl || !wrap) return;
          const nextCollapsed = !wrap.classList.contains("hidden");
          wrap.classList.toggle("hidden", nextCollapsed);
          cardEl.classList.toggle("cal-collapsed", nextCollapsed);
          btn.textContent = nextCollapsed ? "Show calendar" : "Hide calendar";
          btn.setAttribute("aria-expanded", nextCollapsed ? "false" : "true");
          calCollapsedByCard[cardId] = nextCollapsed;
          saveCalCollapsed();
        });
      });
      document.querySelectorAll("textarea.card-note").forEach((area) => {
        area.addEventListener("input", () => {
          const cardId = area.getAttribute("data-card-id");
          notesByCard[cardId] = area.value;
          persistNoteToDb(cardId);
        });
      });
      document.querySelectorAll(".set-mode").forEach((button) => {
        button.addEventListener("click", () => {
          setMode(button.getAttribute("data-card-id"), button.getAttribute("data-mode"));
        });
      });
      document.querySelectorAll(".set-hold").forEach((input) => {
        input.addEventListener("change", () => {
          setHeld(input.getAttribute("data-card-id"), input.checked);
        });
      });
      document.querySelectorAll(".custom-interval, .custom-start-date, .custom-time").forEach((input) => {
        input.addEventListener("change", () => {
          updateCustomSchedule(input.getAttribute("data-card-id"));
        });
      });
      document.querySelectorAll(".add-oneoff").forEach((button) => {
        button.addEventListener("click", () => addOneOff(button.getAttribute("data-card-id")));
      });
      document.querySelectorAll(".remove-oneoff").forEach((button) => {
        button.addEventListener("click", () => {
          removeOneOff(
            button.getAttribute("data-card-id"),
            Number(button.getAttribute("data-oneoff-index"))
          );
        });
      });
      document.querySelectorAll(".mini-day[data-date][data-card-id]").forEach((dayEl) => {
        const activate = () => {
          toggleCompletedDate(dayEl.getAttribute("data-card-id"), dayEl.getAttribute("data-date"));
        };
        dayEl.addEventListener("click", activate);
        dayEl.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            activate();
          }
        });
      });
    }

    function setAllCardCalendarsCollapsed(collapsed) {
      document.querySelectorAll(".card[data-card-id]").forEach((cardEl) => {
        const cardId = cardEl.getAttribute("data-card-id");
        const wrap = cardEl.querySelector(`.mini-cal-wrap[data-cal-for="${cardId}"]`);
        const btn = cardEl.querySelector(".card-cal-toggle");
        if (!wrap || !btn) return;
        wrap.classList.toggle("hidden", collapsed);
        cardEl.classList.toggle("cal-collapsed", collapsed);
        btn.textContent = collapsed ? "Show calendar" : "Hide calendar";
        btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
        calCollapsedByCard[cardId] = collapsed;
      });
      saveCalCollapsed();
    }

    function render() {
      const threshold = Number(thresholdInput.value) || 80;
      thresholdValue.textContent = `${threshold}%`;
      const today = startOfDay(new Date());
      todayLabel.textContent = `today: ${formatDate(today)}`;
      if (!viewMonth) {
        viewMonth = new Date(today.getFullYear(), today.getMonth(), 1);
      }

      const rows = buildRows(threshold);
      lastRows = rows;
      pruneCompletedForRows(rows);
      const flagged = rows.filter((r) => r.held && !r.noData);
      const scheduled = rows.filter((r) => !r.held && !r.noData);
      const pending = rows.filter((r) => r.noData);

      flaggedBadge.textContent = `${flagged.length} Flagged`;
      scheduledBadge.textContent = `${scheduled.length} scheduled`;

      renderOverallCalendar(
        rows.filter((r) => !r.noData),
        viewMonth,
        today
      );

      if (!cardsCache.length) {
        flaggedListEl.innerHTML =
          '<p class="empty">No sites loaded. Keep LaunchPad unlocked, then refresh.</p>';
        scheduledListEl.innerHTML = "";
        pendingSectionEl.style.display = "none";
        pendingListEl.innerHTML = "";
        return;
      }

      flaggedListEl.innerHTML = flagged.length
        ? flagged.map((row, i) => renderCard(row, i + 1, today)).join("")
        : '<p class="empty">No systems at or above this threshold — nothing held back.</p>';

      scheduledListEl.innerHTML = scheduled.length
        ? scheduled.map((row, i) => renderCard(row, i + 1, today)).join("")
        : '<p class="empty">No systems below this threshold with pool capacity data.</p>';

      if (pending.length) {
        pendingSectionEl.style.display = "";
        pendingListEl.innerHTML = pending
          .map((row, i) => renderCard(row, i + 1, today))
          .join("");
      } else {
        pendingSectionEl.style.display = "none";
        pendingListEl.innerHTML = "";
      }

      bindCardInteractions();
    }

    async function downloadExcel() {
      const threshold = Number(thresholdInput.value) || 80;
      const groups = selectedSiteGroups();
      if (!groups.length) {
        statusEl.textContent = "Select at least one group (WAG1, WAG2, or Other) before exporting.";
        return;
      }
      const rows = buildRows(threshold);
      excelBtn.disabled = true;
      statusEl.textContent = "Building Excel workbook…";
      try {
        const params = new URLSearchParams({
          threshold: String(threshold),
          groups: groups.join(","),
        });
        const res = await fetch(`/api/snapshot-schedule-export?${params.toString()}`);
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
        a.download = `Snapshot_Schedule_${exportFileLabel()}_${stamp}.xlsx`;
        a.click();
        URL.revokeObjectURL(url);
        statusEl.textContent = `Exported ${rows.length} card(s) to Excel (${exportFileLabel()}).`;
      } catch (err) {
        statusEl.textContent = `Excel export failed: ${err.message || err}`;
      } finally {
        excelBtn.disabled = false;
      }
    }

    async function loadCards() {
      statusEl.textContent = "Loading…";
      try {
        try {
          await fetch("/api/sync", { method: "POST" });
        } catch (_err) {
          /* best-effort */
        }
        await loadNotesFromDb();
        await loadOverridesFromDb();
        const res = await fetch("/api/cards");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        cardsCache = await res.json();
        statusEl.textContent = `${cardsCache.length} site(s) loaded`;
        render();
      } catch (err) {
        statusEl.textContent = err.message || String(err);
        flaggedListEl.innerHTML =
          '<p class="empty">Could not load sites. Keep LaunchPad running and unlocked, then refresh.</p>';
      }
    }

    async function refreshMonitored() {
      refreshBtn.disabled = true;
      statusEl.textContent = "Refreshing sites…";
      try {
        try {
          await fetch("/api/sync", { method: "POST" });
        } catch (_err) {
          /* best-effort */
        }
        const listRes = await fetch("/api/cards");
        if (!listRes.ok) throw new Error(`HTTP ${listRes.status}`);
        cardsCache = await listRes.json();
        if (!cardsCache.length) {
          statusEl.textContent = "No sites loaded. Keep LaunchPad unlocked and open Capacity Report once.";
          render();
          return;
        }

        let monitorStates = {};
        try {
          const mon = await fetch("/api/monitor");
          if (mon.ok) {
            const data = await mon.json();
            monitorStates = data.states || {};
          }
        } catch (_err) {
          /* ignore */
        }

        let targets = cardsCache.filter((c) => monitorStates[String(c.id)]);
        if (!targets.length) {
          targets = cardsCache.slice();
          statusEl.textContent = `Refreshing all ${targets.length} site(s)…`;
        }

        let done = 0;
        let failed = 0;
        for (const card of targets) {
          statusEl.textContent = `Refreshing ${done + 1}/${targets.length}: ${card.name}…`;
          try {
            const res = await fetch(`/api/refresh/${card.id}`, { method: "POST" });
            const payload = await res.json().catch(() => ({}));
            if (!res.ok) {
              failed += 1;
              card.error = payload.error || `HTTP ${res.status}`;
            } else {
              const idx = cardsCache.findIndex((entry) => entry.id === payload.id);
              if (idx >= 0) cardsCache[idx] = payload;
              else cardsCache.push(payload);
            }
          } catch (_err) {
            failed += 1;
          }
          done += 1;
          render();
        }
        await loadNotesFromDb();
        await loadOverridesFromDb();
        statusEl.textContent =
          `Refreshed ${done} site(s)` + (failed ? ` (${failed} failed)` : "");
        render();
      } catch (err) {
        statusEl.textContent = `Refresh failed: ${err.message || err}`;
      } finally {
        refreshBtn.disabled = false;
      }
    }

    try {
      const saved = localStorage.getItem(THRESHOLD_KEY);
      if (saved) thresholdInput.value = String(Math.max(50, Math.min(95, Number(saved) || 80)));
    } catch (_err) {
      /* ignore */
    }
    loadSiteFilters();
    loadOverridesLocal();

    thresholdInput.addEventListener("input", () => {
      try {
        localStorage.setItem(THRESHOLD_KEY, thresholdInput.value);
      } catch (_err) {
        /* ignore */
      }
      render();
    });
    [filterWag1, filterWag2, filterOther].forEach((input) => {
      input.addEventListener("change", () => {
        saveSiteFilters();
        render();
      });
    });
    document.getElementById("cal-prev").addEventListener("click", () => {
      viewMonth = new Date(viewMonth.getFullYear(), viewMonth.getMonth() - 1, 1);
      render();
    });
    document.getElementById("cal-next").addEventListener("click", () => {
      viewMonth = new Date(viewMonth.getFullYear(), viewMonth.getMonth() + 1, 1);
      render();
    });
    document.getElementById("cal-today").addEventListener("click", () => {
      const t = new Date();
      viewMonth = new Date(t.getFullYear(), t.getMonth(), 1);
      render();
    });
    refreshBtn.addEventListener("click", refreshMonitored);
    excelBtn.addEventListener("click", downloadExcel);
    document.getElementById("collapse-all-cals").addEventListener("click", () => {
      setAllCardCalendarsCollapsed(true);
    });
    document.getElementById("expand-all-cals").addEventListener("click", () => {
      setAllCardCalendarsCollapsed(false);
    });
    loadCards();
  </script>
</body>
</html>
"""
