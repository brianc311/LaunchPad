"""Fibre Channel WWPN inventory and host/LUN mapping report page."""

FC_WWPN_REPORT_PATH = "/fc-wwpn"

FC_WWPN_REPORT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad FC WWPN Report</title>
  <style>
    :root {
      --bg: #0b0f14;
      --panel: #121821;
      --text: #e8edf5;
      --muted: #8b98ab;
      --accent: #ff6b00;
      --accent2: #ff8533;
      --ok: #4ade80;
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
    .wrap { max-width: 1180px; margin: 0 auto; padding: 28px 20px 48px; }
    .hero {
      background: linear-gradient(135deg, #1a2230 0%, #101722 100%);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 24px 28px;
      margin-bottom: 24px;
    }
    .hero h1 { margin: 0 0 8px; color: var(--accent); font-size: 1.85rem; }
    .hero p { margin: 0; color: var(--muted); line-height: 1.45; }
    a:not(.btn) {
      color: #9ec1ff;
      text-decoration: underline;
      text-underline-offset: 2px;
    }
    a:not(.btn):hover { color: #c5d9ff; }
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
    .status { color: var(--muted); font-size: 0.9rem; }
    .group-filter {
      background: #0f141d; color: var(--text); border: 1px solid var(--border);
      border-radius: 10px; height: 34px; padding: 0 10px; font: inherit;
    }
    .site-filters {
      display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center;
      margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border);
    }
    .site-filters .filter-label {
      color: var(--muted); font-size: 0.85rem; font-weight: 700;
      letter-spacing: 0.04em; text-transform: uppercase;
    }
    .site-filters label.filter-check {
      display: inline-flex; align-items: center; gap: 8px;
      color: var(--text); font-size: 0.92rem; cursor: pointer; user-select: none;
      background: #0f141d; border: 1px solid var(--border); border-radius: 999px;
      padding: 6px 12px;
    }
    .site-filters label.filter-check input {
      width: 15px; height: 15px; accent-color: var(--accent); cursor: pointer;
    }
    .site-filters .filter-hint { color: var(--muted); font-size: 0.82rem; }
    #fc-search {
      width: min(420px, 100%); background: #0f141d; color: var(--text);
      border: 1px solid var(--border); border-radius: 10px; height: 34px;
      padding: 0 12px; font: inherit;
    }
    .site {
      background: var(--card); border: 1px solid var(--border); border-radius: 16px;
      padding: 18px 20px; margin-bottom: 16px; break-inside: avoid;
    }
    .site-head {
      display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: baseline;
      margin-bottom: 12px;
    }
    .site-head h2 { margin: 0; font-size: 1.25rem; color: var(--accent2); }
    .site-head .meta { color: var(--muted); font-size: 0.88rem; }
    .site-actions { margin-left: auto; display: flex; gap: 8px; flex-wrap: wrap; }
    .node-block { margin: 14px 0 8px; }
    .node-title {
      font-size: 0.8rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
      color: var(--ok); margin: 0 0 8px;
    }
    table {
      width: 100%; border-collapse: collapse; font-size: 0.86rem; margin-bottom: 8px;
    }
    th, td {
      border: 1px solid var(--border); padding: 7px 9px; text-align: left; vertical-align: top;
    }
    th { background: #0f141d; color: var(--muted); font-weight: 700; }
    td.mono { font-family: Consolas, monospace; letter-spacing: 0.02em; }
    td.cell-clamp {
      cursor: pointer;
      max-width: 22rem;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      word-break: normal;
    }
    td.cell-clamp.is-expanded {
      white-space: normal;
      word-break: break-all;
      overflow: visible;
      text-overflow: unset;
      max-width: none;
    }
    .empty {
      color: var(--muted); border: 1px dashed var(--border); border-radius: 12px;
      padding: 14px 16px; background: rgba(15,20,29,0.45);
    }
    .footer { color: var(--muted); font-size: 0.85rem; margin-top: 20px; }
    .modal-backdrop {
      position: fixed; inset: 0; background: rgba(0,0,0,0.65); display: none;
      align-items: center; justify-content: center; z-index: 50; padding: 20px;
    }
    .modal-backdrop.open { display: flex; }
    .modal {
      background: #121821; border: 1px solid var(--border); border-radius: 16px;
      width: min(980px, 100%); max-height: min(85vh, 900px); overflow: auto;
      padding: 20px 22px;
    }
    .modal h3 { margin: 0 0 6px; color: var(--accent); }
    .modal .sub { color: var(--muted); margin: 0 0 14px; font-size: 0.9rem; }
    .modal-close { float: right; }
    .tabs { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
    .tab {
      background: #0f141d; border: 1px solid var(--border); color: var(--text);
      border-radius: 8px; height: 30px; padding: 0 12px; cursor: pointer; font-weight: 600;
    }
    .tab.active { border-color: var(--accent); color: var(--accent2); }
    #modal-print { display: none; }
    @media print {
      body { background: #fff; color: #111; }
      .hero, .site { border-color: #ccc; background: #fff; box-shadow: none; }
      .hero h1, .site-head h2 { color: #c2410c; }
      .no-print, .modal-backdrop { display: none !important; }
      th { background: #eee; color: #333; }
      th, td { border-color: #bbb; }
      .site { page-break-inside: avoid; }
      body.printing-modal-mappings .hero,
      body.printing-modal-mappings #sites,
      body.printing-modal-mappings .footer { display: none !important; }
      body.printing-modal-mappings #modal-print { display: block !important; }
      body.printing-modal-mappings #modal-print h4 { margin: 16px 0 8px; color: #c2410c; }
      td.cell-clamp, td.cell-clamp.is-expanded {
        white-space: normal;
        word-break: break-all;
        overflow: visible;
        text-overflow: unset;
        max-width: none;
      }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>FC WWPN Report</h1>
      <p>
        Fibre Channel port WWPNs by canister/node, with host and LUN mappings.
        Refresh monitored IBM FlashSystem / Storwize / SVC sites after loading the latest device presets
        (includes <code>lsportfc</code>, <code>lshost</code>, <code>lshostvdiskmap</code>, <code>lsfabric</code>).
      </p>
      <div class="hero-actions no-print">
        <button type="button" id="refresh-btn" class="btn">Refresh On Sites</button>
        <button type="button" id="print-btn" class="btn secondary">Print / Save PDF</button>
        <button type="button" id="excel-btn" class="btn secondary">Export Excel</button>
        <a class="btn secondary" href="/capacity">Capacity Report</a>
        <a class="btn secondary" href="/volume-find">Host / Volume Find</a>
        <a class="btn secondary" href="/host-volume-health">Hosts & Volumes</a>
        <a class="btn secondary" href="/system-connectivity">System Connectivity</a>
        <a class="btn secondary" href="/contingency-groups">Consistency Groups</a>
        <a class="btn secondary" href="/fc-consistgrp">FlashCopy CGs</a>
        <a class="btn secondary" href="/">Health Dashboard</a>
        <input type="search" id="fc-search" placeholder="Search WWPN, remote WWPN, host, or volume…" aria-label="Search FC inventory">
        <button type="button" id="fc-search-btn" class="btn secondary">Find</button>
        <label for="site-select" class="status">Site</label>
        <select id="site-select" class="group-filter" aria-label="Site">
          <option value="">All servers</option>
        </select>
        <span id="status" class="status"></span>
      </div>
      <div class="site-filters no-print" id="site-filters">
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
        <span class="filter-hint">Uncheck a group to hide it from the report and export.</span>
      </div>
    </section>
    <div id="sites"></div>
    <p class="footer">LaunchPad FC WWPN v{{APP_VERSION}} · Keep LaunchPad running while refreshing.</p>
  </div>

  <div id="modal-print"></div>

  <div class="modal-backdrop" id="modal" role="dialog" aria-modal="true">
    <div class="modal">
      <div class="modal-actions no-print" style="float:right;display:flex;gap:8px;flex-wrap:wrap;">
        <button type="button" class="btn secondary" id="modal-export-excel-btn">Export Excel</button>
        <button type="button" class="btn secondary" id="modal-export-csv-btn">Export CSV</button>
        <button type="button" class="btn secondary" id="modal-print-btn">Print / Save PDF</button>
        <button type="button" class="btn secondary modal-close" id="modal-close">Close</button>
      </div>
      <h3 id="modal-title">Mappings</h3>
      <p class="sub" id="modal-sub"></p>
      <div class="tabs no-print">
        <button type="button" class="tab active" data-tab="hosts">Hosts &amp; WWPNs</button>
        <button type="button" class="tab" data-tab="maps">LUN Mappings</button>
        <button type="button" class="tab" data-tab="fabric">Fabric Logins</button>
      </div>
      <div id="modal-body"></div>
    </div>
  </div>

  <script>
    const sitesEl = document.getElementById("sites");
    const statusEl = document.getElementById("status");
    const refreshBtn = document.getElementById("refresh-btn");
    const printBtn = document.getElementById("print-btn");
    const excelBtn = document.getElementById("excel-btn");
    const siteSelect = document.getElementById("site-select");
    const searchInput = document.getElementById("fc-search");
    const searchBtn = document.getElementById("fc-search-btn");
    const filterWag1 = document.getElementById("filter-wag1");
    const filterWag2 = document.getElementById("filter-wag2");
    const filterOther = document.getElementById("filter-other");
    const modal = document.getElementById("modal");
    const modalTitle = document.getElementById("modal-title");
    const modalSub = document.getElementById("modal-sub");
    const modalBody = document.getElementById("modal-body");
    const modalExportExcelBtn = document.getElementById("modal-export-excel-btn");
    const modalExportCsvBtn = document.getElementById("modal-export-csv-btn");
    const modalPrintBtn = document.getElementById("modal-print-btn");
    const modalPrintEl = document.getElementById("modal-print");
    let cardsCache = [];
    let activeCard = null;
    let activeTab = "hosts";
    let activeSiteId = new URLSearchParams(window.location.search).get("site") || "";

    function escapeHtml(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function formatFcPortLabel(raw) {
      const text = String(raw || "").trim();
      if (!text) return "";
      if (/^\\d+$/.test(text)) return "fc" + text;
      const m = /^fc(\\d+)$/i.exec(text);
      if (m) return "fc" + m[1];
      return text;
    }

    function cellNeedsClamp(td) {
      const text = (td.textContent || "").trim();
      if (!text) return false;
      if (text.includes("\\n") || text.includes(";")) return true;
      return td.scrollWidth > td.clientWidth + 1 || td.scrollHeight > td.clientHeight + 1;
    }

    function collapseAllClampedCells(root) {
      const scope = root || document.getElementById("sites");
      if (!scope) return;
      scope.querySelectorAll("td.cell-clamp.is-expanded").forEach((td) => {
        td.classList.remove("is-expanded");
        td.setAttribute("aria-expanded", "false");
      });
    }

    function applyCellClamps(root) {
      const scope = root || document.getElementById("sites");
      if (!scope) return;
      scope.querySelectorAll("td").forEach((td) => {
        td.classList.remove("cell-clamp", "is-expanded");
        td.removeAttribute("aria-expanded");
        td.removeAttribute("title");
        if (!cellNeedsClamp(td)) return;
        td.classList.add("cell-clamp");
        td.setAttribute("aria-expanded", "false");
        td.title = "Click to expand";
      });
    }

    function expandClampedCellsMatching(query, root) {
      const scope = root || document.getElementById("sites");
      if (!scope) return;
      const raw = String(query || "").trim();
      if (!raw) return;
      const qText = raw.toLowerCase();
      const qWwpn = normalizeWwpn(raw);
      let first = null;
      scope.querySelectorAll("td.cell-clamp").forEach((td) => {
        const text = td.textContent || "";
        const hit = fieldMatchesText(text, qText) || fieldMatchesWwpn(text, qWwpn);
        if (!hit) return;
        td.classList.add("is-expanded");
        td.setAttribute("aria-expanded", "true");
        td.title = "Click to collapse";
        if (!first) first = td;
      });
      if (first && typeof first.scrollIntoView === "function") {
        first.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    }

    function isSvcLike(card) {
      const p = String(card.device_profile || "").toLowerCase();
      if (p.includes("ds8884") || p.includes("xiv") || p.includes("ds8")) {
        return Boolean(card.fc_available);
      }
      return (
        p.includes("flashsystem") ||
        p.includes("storwize") ||
        p.includes("svc") ||
        Boolean(card.fc_available)
      );
    }

    function filterCardsBySite(cards, siteId) {
      const id = String(siteId || "").trim();
      if (!id) return cards;
      return cards.filter((card) => String(card.id) === id);
    }

    // Keep siteGroup in sync with launchpad.snapshot_schedule_export.site_group
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

    function includedGroups() {
      const groups = new Set();
      if (filterWag1.checked) groups.add("wag1");
      if (filterWag2.checked) groups.add("wag2");
      if (filterOther.checked) groups.add("other");
      return groups;
    }

    function normalizeWwpn(value) {
      return String(value || "").replace(/[\\s:]/g, "").toUpperCase();
    }

    function wwpnFieldTokens(field) {
      const text = String(field || "").trim();
      if (!text) return [];
      return text
        .split(/[;,]+/)
        .map((part) => part.trim())
        .filter(Boolean)
        .map(normalizeWwpn);
    }

    function fieldMatchesText(field, qText) {
      if (!qText) return false;
      const text = String(field || "").trim();
      if (!text) return false;
      return text.toLowerCase().includes(qText);
    }

    function fieldMatchesWwpn(field, qWwpn) {
      if (!qWwpn) return false;
      return wwpnFieldTokens(field).some((token) => token.includes(qWwpn));
    }

    // Keep cardMatchesQuery in sync with launchpad.fc_wwpn_search.card_matches_fc_query
    function cardMatchesQuery(card, query) {
      const raw = String(query || "").trim();
      if (!raw) return true;
      const qText = raw.toLowerCase();
      const qWwpn = normalizeWwpn(raw);

      const textFields = [];
      const wwpnFields = [];

      for (const port of card.fc_ports || []) {
        wwpnFields.push(port.wwpn);
        wwpnFields.push(port.remote_wwpns);
      }
      for (const node of card.fc_ports_by_node || []) {
        for (const port of node.ports || []) {
          wwpnFields.push(port.wwpn);
          wwpnFields.push(port.remote_wwpns);
        }
      }
      for (const host of card.fc_hosts || []) {
        textFields.push(host.host_name || host.name);
        wwpnFields.push(host.wwpns);
        wwpnFields.push(host.wwpn);
        wwpnFields.push(host.host_wwpns);
      }
      for (const mapping of card.fc_mappings || []) {
        textFields.push(mapping.vdisk_name || mapping.volume);
        textFields.push(mapping.host_name || mapping.host);
        wwpnFields.push(mapping.host_wwpns);
      }
      for (const login of card.fc_fabric || []) {
        textFields.push(login.host_name);
        wwpnFields.push(login.local_wwpn);
        wwpnFields.push(login.remote_wwpn);
      }

      if (textFields.some((field) => fieldMatchesText(field, qText))) return true;
      if (wwpnFields.some((field) => fieldMatchesWwpn(field, qWwpn))) return true;
      return false;
    }

    function runFcSearch() {
      const q = (searchInput.value || "").trim();
      if (!q) {
        collapseAllClampedCells();
        statusEl.textContent = "Search cleared.";
        return;
      }
      let matches = cardsCache.filter(isSvcLike).filter((c) => cardMatchesQuery(c, q));
      const finish = (list, serverMatches) => {
        if (!list.length) {
          if (serverMatches && serverMatches.length) {
            const first = serverMatches[0];
            activeSiteId = String(first.id);
            updateSiteOptions();
            render();
            applyCellClamps();
            expandClampedCellsMatching(q);
            const extra = serverMatches.length - 1;
            statusEl.textContent = extra
              ? `Found on ${first.name} (also on ${extra} other site(s))`
              : `Found on ${first.name}`;
            return;
          }
          activeSiteId = "";
          updateSiteOptions();
          render();
          applyCellClamps();
          statusEl.textContent = `WWPN not found — can't locate site`;
          return;
        }
        list = list.slice().sort((a, b) =>
          String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" })
        );
        activeSiteId = String(list[0].id);
        updateSiteOptions();
        render();
        applyCellClamps();
        expandClampedCellsMatching(q);
        const extra = list.length - 1;
        statusEl.textContent = extra
          ? `Found on ${list[0].name} (also on ${extra} other site(s))`
          : `Found on ${list[0].name}`;
      };
      if (matches.length) {
        finish(matches);
        return;
      }
      fetch(`/api/fc-wwpn-find?q=${encodeURIComponent(q)}`)
        .then((r) => r.json())
        .then((payload) => {
          const ids = new Set((payload.matches || []).map((m) => String(m.id)));
          finish(
            cardsCache.filter((c) => ids.has(String(c.id))),
            payload.matches || [],
          );
        })
        .catch((err) => {
          statusEl.textContent = `Search failed: ${err.message || err}`;
        });
    }

    function updateSiteOptions() {
      const allowed = includedGroups();
      const svcCards = cardsCache
        .filter(isSvcLike)
        .filter((card) => allowed.has(siteGroup(card)))
        .slice()
        .sort((a, b) =>
          String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" })
        );
      const selected = svcCards.some((card) => String(card.id) === String(activeSiteId))
        ? String(activeSiteId) : "";
      activeSiteId = selected;
      siteSelect.innerHTML = '<option value="">All servers</option>' + svcCards.map((card) =>
        `<option value="${escapeHtml(card.id)}">${escapeHtml(card.name || card.id)}</option>`
      ).join("");
      siteSelect.value = selected;
    }

    function portTable(ports) {
      if (!ports.length) return '<p class="empty">No FC ports / WWPNs returned.</p>';
      const rows = ports.map((p) => `
        <tr>
          <td>${escapeHtml(formatFcPortLabel(p.port_id || p.fc_io_port_id || ""))}</td>
          <td class="mono">${escapeHtml(p.wwpn || "")}</td>
          <td>${escapeHtml(p.status || "")}</td>
          <td>${escapeHtml(p.speed || "")}</td>
          <td>${escapeHtml(p.attachment || p.type || "")}</td>
          <td>${escapeHtml(p.logged_in_count || "0")}</td>
          <td class="mono">${escapeHtml(p.remote_wwpns || "")}</td>
        </tr>
      `).join("");
      return `
        <table>
          <thead>
            <tr>
              <th>Port</th><th>WWPN</th><th>Status</th><th>Speed</th>
              <th>Attachment</th><th>Logins</th><th>Remote WWPNs</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    }

    function renderSite(card) {
      const groups = Array.isArray(card.fc_ports_by_node) ? card.fc_ports_by_node : [];
      const portCount = (card.fc_ports || []).length;
      const mapCount = (card.fc_mappings || []).length;
      const hostCount = (card.fc_hosts || []).length;
      let body = "";
      if (card.error && !portCount) {
        body = `<div class="empty">${escapeHtml(card.error)}</div>`;
      } else if (!portCount && !mapCount && !hostCount) {
        const fcErrors = (card.command_results || [])
          .filter((item) => {
            const hay = `${item.label || ""} ${item.command || ""}`.toLowerCase();
            return (
              hay.includes("fc -") ||
              hay.includes("lsportfc") ||
              hay.includes("lshost") ||
              hay.includes("lsfabric")
            );
          })
          .filter((item) => item.error || !(item.output || "").trim())
          .slice(0, 4)
          .map((item) => {
            const detail = item.error || "empty output";
            return `${item.label || item.command}: ${detail}`;
          });
        const hint = fcErrors.length
          ? `<div class="empty">FC commands ran but returned no usable data:<br>${fcErrors.map(escapeHtml).join("<br>")}<br>Confirm the SSH user can run <code>lsportfc</code> / <code>lshostvdiskmap</code>, then Refresh again.</div>`
          : `<div class="empty">No FC data yet. Click <strong>Refresh On Sites</strong> (FlashSystem / Storwize / SVC). FC commands are added automatically for those profiles.</div>`;
        body = hint;
      } else if (groups.length) {
        body = groups.map((g) => `
          <div class="node-block">
            <p class="node-title">Canister / Node · ${escapeHtml(g.node_name)}</p>
            ${portTable(g.ports || [])}
          </div>
        `).join("");
      } else {
        body = portTable(card.fc_ports || []);
      }
      return `
        <section class="site" data-id="${card.id}">
          <div class="site-head">
            <h2>${escapeHtml(card.name)}</h2>
            <span class="meta">${escapeHtml(card.category || "")} · ${escapeHtml(card.model || card.device_profile || "")} · ${escapeHtml(card.host || "")}</span>
            <span class="meta">${portCount} WWPN(s) · ${hostCount} host(s) · ${mapCount} LUN map(s)</span>
            <div class="site-actions no-print">
              <button type="button" class="btn secondary map-btn" data-id="${card.id}">Hosts &amp; LUN Mappings</button>
            </div>
          </div>
          ${body}
        </section>
      `;
    }

    function render() {
      const allowed = includedGroups();
      const all = cardsCache
        .filter(isSvcLike)
        .filter((card) => allowed.has(siteGroup(card)));
      updateSiteOptions();
      const cards = filterCardsBySite(all, activeSiteId);
      if (!all.length) {
        sitesEl.innerHTML = '<p class="empty">No storage sites with FC data. Register IBM FlashSystem/Storwize/SVC cards, load presets, monitor, and refresh.</p>';
        applyCellClamps();
        return;
      }
      if (activeSiteId && !cards.length) {
        sitesEl.innerHTML = '<p class="empty">Selected site not found in the loaded card list.</p>';
        applyCellClamps();
        return;
      }
      sitesEl.innerHTML = cards.map(renderSite).join("");
      sitesEl.querySelectorAll(".map-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          const id = Number(btn.getAttribute("data-id"));
          openModal(cards.find((c) => c.id === id));
        });
      });
      if (activeSiteId) {
        statusEl.textContent = `Showing ${cards.length} of ${all.length} site(s)`;
      }
      applyCellClamps();
    }

    function tableFromRows(headers, rows) {
      if (!rows.length) return '<p class="empty">No rows.</p>';
      const head = headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("");
      const body = rows.map((row) =>
        `<tr>${row.map((cell, i) => `<td class="${i === 1 || String(headers[i]).toLowerCase().includes('wwpn') ? 'mono' : ''}">${escapeHtml(cell)}</td>`).join("")}</tr>`
      ).join("");
      return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
    }

    function renderModalBody() {
      if (!activeCard) return;
      if (activeTab === "hosts") {
        const rows = (activeCard.fc_hosts || []).map((h) => [
          h.host_id, h.host_name, h.status, h.protocol, h.wwpn_count, h.wwpns,
        ]);
        modalBody.innerHTML = tableFromRows(
          ["ID", "Host", "Status", "Protocol", "WWPN count", "Host WWPNs"],
          rows
        );
      } else if (activeTab === "maps") {
        const rows = (activeCard.fc_mappings || []).map((m) => [
          m.host_name, m.vdisk_name, m.scsi_id, m.vdisk_id, m.host_wwpns,
        ]);
        modalBody.innerHTML = tableFromRows(
          ["Host", "Volume / VDisk", "SCSI / LUN ID", "VDisk ID", "Host WWPNs"],
          rows
        );
      } else {
        const rows = (activeCard.fc_fabric || []).map((f) => [
          f.node_name, f.local_wwpn, f.remote_wwpn, f.host_name, f.state, f.local_port,
        ]);
        modalBody.innerHTML = tableFromRows(
          ["Node", "Local WWPN", "Remote WWPN", "Host", "State", "Local port"],
          rows
        );
      }
    }

    function setModalExportEnabled(enabled) {
      modalExportExcelBtn.disabled = !enabled;
      modalExportCsvBtn.disabled = !enabled;
      modalPrintBtn.disabled = !enabled;
    }

    async function downloadModalMappings(format) {
      if (!activeCard || activeCard.id == null) return;
      const btn = format === "csv" ? modalExportCsvBtn : modalExportExcelBtn;
      btn.disabled = true;
      statusEl.textContent = format === "csv"
        ? "Building mappings CSV ZIP…"
        : "Building mappings Excel…";
      try {
        const params = new URLSearchParams({ open: format === "xlsx" ? "1" : "0" });
        params.set("card_id", String(activeCard.id));
        params.set("format", format);
        const res = await fetch(`/api/fc-wwpn-mappings-export?${params.toString()}`);
        if (!res.ok) {
          let detail = `HTTP ${res.status}`;
          try {
            const err = await res.json();
            if (err && err.error) detail = err.error;
          } catch (_err) { /* ignore */ }
          throw new Error(detail);
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        const stamp = new Date().toISOString().slice(0, 16).replace(/[:-]/g, "");
        const safe = String(activeCard.name || activeCard.id).replace(/[^\\w\\-]+/g, "_");
        a.href = url;
        a.download = format === "csv"
          ? `FC_Mappings_${safe}_${stamp}.zip`
          : `FC_Mappings_${safe}_${stamp}.xlsx`;
        a.click();
        URL.revokeObjectURL(url);
        statusEl.textContent = format === "csv"
          ? "Mappings CSV ZIP downloaded (hosts / lun_mappings / fabric_logins)."
          : "Mappings Excel downloaded (Hosts / LUN Mappings / Fabric Logins).";
      } catch (err) {
        statusEl.textContent = `Mappings export failed: ${err.message || err}`;
      } finally {
        setModalExportEnabled(Boolean(activeCard));
      }
    }

    function printModalMappings() {
      if (!activeCard) return;
      const hostRows = (activeCard.fc_hosts || []).map((h) => [
        h.host_id, h.host_name, h.status, h.protocol, h.wwpn_count, h.wwpns,
      ]);
      const mapRows = (activeCard.fc_mappings || []).map((m) => [
        m.host_name, m.vdisk_name, m.scsi_id, m.vdisk_id, m.host_wwpns,
      ]);
      const fabricRows = (activeCard.fc_fabric || []).map((f) => [
        f.node_name, f.local_wwpn, f.remote_wwpn, f.host_name, f.state, f.local_port,
      ]);
      modalPrintEl.innerHTML = `
        <h3>${escapeHtml(activeCard.name)} — Hosts &amp; LUN Mappings</h3>
        <h4>Hosts & WWPNs</h4>
        ${tableFromRows(["ID", "Host", "Status", "Protocol", "WWPN count", "Host WWPNs"], hostRows)}
        <h4>LUN Mappings</h4>
        ${tableFromRows(["Host", "Volume / VDisk", "SCSI / LUN ID", "VDisk ID", "Host WWPNs"], mapRows)}
        <h4>Fabric Logins</h4>
        ${tableFromRows(["Node", "Local WWPN", "Remote WWPN", "Host", "State", "Local port"], fabricRows)}
      `;
      document.body.classList.add("printing-modal-mappings");
      let cleaned = false;
      const cleanup = () => {
        if (cleaned) return;
        cleaned = true;
        document.body.classList.remove("printing-modal-mappings");
        window.removeEventListener("afterprint", cleanup);
      };
      window.addEventListener("afterprint", cleanup);
      setTimeout(cleanup, 2000);
      window.print();
    }

    function openModal(card) {
      if (!card) return;
      activeCard = card;
      activeTab = "hosts";
      modalTitle.textContent = `${card.name} — Hosts & LUN Mappings`;
      modalSub.textContent = `${(card.fc_hosts || []).length} hosts · ${(card.fc_mappings || []).length} LUN maps · ${(card.fc_fabric || []).length} fabric logins`;
      modal.querySelectorAll(".tab").forEach((t) => {
        t.classList.toggle("active", t.getAttribute("data-tab") === activeTab);
      });
      renderModalBody();
      setModalExportEnabled(true);
      modal.classList.add("open");
    }

    function closeModal() {
      modal.classList.remove("open");
      modalPrintEl.innerHTML = "";
      activeCard = null;
      setModalExportEnabled(false);
    }

    async function downloadExcel() {
      const groups = [...includedGroups()];
      if (!groups.length) {
        statusEl.textContent = "Select at least one group (WAG1, WAG2, or Other) before exporting.";
        return;
      }
      excelBtn.disabled = true;
      statusEl.textContent = "Building Excel workbook…";
      try {
        let exportUrl = `/api/fc-wwpn-export?open=1&groups=${encodeURIComponent(groups.join(","))}`;
        if (activeSiteId) exportUrl += `&card_id=${encodeURIComponent(activeSiteId)}`;
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
        a.download = `FC_WWPN_Report_${stamp}.xlsx`;
        a.click();
        URL.revokeObjectURL(url);
        statusEl.textContent =
          "Excel (.xlsx) downloaded and opened in Excel (Ports / Hosts / LUN Mappings sheets).";
      } catch (err) {
        statusEl.textContent = `Excel export failed: ${err.message || err}`;
      } finally {
        excelBtn.disabled = false;
      }
    }

    async function loadCards() {
      statusEl.textContent = "Loading…";
      try {
        try { await fetch("/api/sync", { method: "POST" }); } catch (_e) {}
        const res = await fetch("/api/cards");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        cardsCache = await res.json();
        statusEl.textContent = `${cardsCache.length} site(s) loaded`;
        render();
      } catch (err) {
        statusEl.textContent = err.message || String(err);
        sitesEl.innerHTML = '<p class="empty">Could not load sites. Keep LaunchPad unlocked and try again.</p>';
      }
    }

    async function refreshMonitored() {
      refreshBtn.disabled = true;
      try {
        try { await fetch("/api/sync", { method: "POST" }); } catch (_e) {}
        const listRes = await fetch("/api/cards");
        if (!listRes.ok) throw new Error(`HTTP ${listRes.status}`);
        cardsCache = await listRes.json();

        let states = {};
        try {
          const mon = await fetch("/api/monitor");
          if (mon.ok) states = (await mon.json()).states || {};
        } catch (_e) {}

        let targets = cardsCache.filter((c) => isSvcLike(c) && states[String(c.id)]);
        if (!targets.length) {
          targets = cardsCache.filter(isSvcLike);
        }
        if (!targets.length) {
          statusEl.textContent = "No FlashSystem / Storwize / SVC sites to refresh.";
          render();
          return;
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
          } catch (_e) {
            failed += 1;
          }
          done += 1;
          render();
        }
        statusEl.textContent =
          `Refreshed ${done} site(s)` + (failed ? ` (${failed} failed)` : "");
        render();
      } catch (err) {
        statusEl.textContent = err.message || String(err);
      } finally {
        refreshBtn.disabled = false;
      }
    }

    modal.querySelectorAll(".tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        activeTab = tab.getAttribute("data-tab");
        modal.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
        renderModalBody();
      });
    });
    document.getElementById("modal-close").addEventListener("click", closeModal);
    modalExportExcelBtn.addEventListener("click", () => downloadModalMappings("xlsx"));
    modalExportCsvBtn.addEventListener("click", () => downloadModalMappings("csv"));
    modalPrintBtn.addEventListener("click", printModalMappings);
    setModalExportEnabled(false);
    modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });
    refreshBtn.addEventListener("click", refreshMonitored);
    printBtn.addEventListener("click", () => window.print());
    excelBtn.addEventListener("click", downloadExcel);
    searchBtn.addEventListener("click", runFcSearch);
    searchInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") runFcSearch();
    });
    filterWag1.addEventListener("change", render);
    filterWag2.addEventListener("change", render);
    filterOther.addEventListener("change", render);
    sitesEl.addEventListener("click", (event) => {
      const td = event.target.closest("td.cell-clamp");
      if (!td || !sitesEl.contains(td)) return;
      const open = !td.classList.contains("is-expanded");
      td.classList.toggle("is-expanded", open);
      td.setAttribute("aria-expanded", open ? "true" : "false");
      td.title = open ? "Click to collapse" : "Click to expand";
    });
    siteSelect.addEventListener("change", () => {
      activeSiteId = siteSelect.value;
      const url = new URL(window.location.href);
      if (activeSiteId) url.searchParams.set("site", activeSiteId);
      else url.searchParams.delete("site");
      url.searchParams.delete("group");
      window.history.replaceState({}, "", url);
      render();
    });
    loadCards();
  </script>
</body>
</html>
"""
