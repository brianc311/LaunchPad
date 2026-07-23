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
    @media print {
      body { background: #fff; color: #111; }
      .hero, .site { border-color: #ccc; background: #fff; box-shadow: none; }
      .hero h1, .site-head h2 { color: #c2410c; }
      .no-print, .modal-backdrop { display: none !important; }
      th { background: #eee; color: #333; }
      th, td { border-color: #bbb; }
      .site { page-break-inside: avoid; }
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
        <a class="btn secondary" href="/contingency-groups">Contingency Groups</a>
        <a class="btn secondary" href="/">Health Dashboard</a>
        <label for="site-select" class="status">Site</label>
        <select id="site-select" class="group-filter" aria-label="Site">
          <option value="">None</option>
        </select>
        <span id="status" class="status"></span>
      </div>
    </section>
    <div id="sites"></div>
    <p class="footer">LaunchPad FC WWPN v{{APP_VERSION}} · Keep LaunchPad running while refreshing.</p>
  </div>

  <div class="modal-backdrop" id="modal" role="dialog" aria-modal="true">
    <div class="modal">
      <button type="button" class="btn secondary modal-close" id="modal-close">Close</button>
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
    const modal = document.getElementById("modal");
    const modalTitle = document.getElementById("modal-title");
    const modalSub = document.getElementById("modal-sub");
    const modalBody = document.getElementById("modal-body");
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

    function updateSiteOptions() {
      const svcCards = cardsCache.filter(isSvcLike).slice().sort((a, b) =>
        String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" })
      );
      const selected = svcCards.some((card) => String(card.id) === String(activeSiteId))
        ? String(activeSiteId) : "";
      activeSiteId = selected;
      siteSelect.innerHTML = '<option value="">None</option>' + svcCards.map((card) =>
        `<option value="${escapeHtml(card.id)}">${escapeHtml(card.name || card.id)}</option>`
      ).join("");
      siteSelect.value = selected;
    }

    function portTable(ports) {
      if (!ports.length) return '<p class="empty">No FC ports / WWPNs returned.</p>';
      const rows = ports.map((p) => `
        <tr>
          <td>${escapeHtml(p.port_id || p.fc_io_port_id || "")}</td>
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
      const all = cardsCache.filter(isSvcLike);
      updateSiteOptions();
      const cards = filterCardsBySite(all, activeSiteId);
      if (!all.length) {
        sitesEl.innerHTML = '<p class="empty">No storage sites with FC data. Register IBM FlashSystem/Storwize/SVC cards, load presets, monitor, and refresh.</p>';
        return;
      }
      if (activeSiteId && !cards.length) {
        sitesEl.innerHTML = '<p class="empty">Selected site not found in the loaded card list.</p>';
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
      modal.classList.add("open");
    }

    function closeModal() {
      modal.classList.remove("open");
      activeCard = null;
    }

    async function downloadExcel() {
      excelBtn.disabled = true;
      statusEl.textContent = "Building Excel workbook…";
      try {
        const params = new URLSearchParams({ open: "1" });
        if (activeSiteId) params.set("card_id", activeSiteId);
        const res = await fetch(`/api/fc-wwpn-export?${params.toString()}`);
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
    modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });
    refreshBtn.addEventListener("click", refreshMonitored);
    printBtn.addEventListener("click", () => window.print());
    excelBtn.addEventListener("click", downloadExcel);
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
