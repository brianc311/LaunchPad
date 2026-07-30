"""Snapcopy Summary — multi-site FlashCopy CG summary page."""

SNAPCOPY_SUMMARY_PATH = "/snapcopy-summary"

SNAPCOPY_SUMMARY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Snapcopy Summary</title>
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
    .wrap { max-width: 1280px; margin: 0 auto; padding: 28px 20px 48px; }
    .hero {
      background: linear-gradient(135deg, #1a2230 0%, #101722 100%);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 24px 28px;
      margin-bottom: 18px;
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
    button.btn:disabled { opacity: .55; cursor: not-allowed; }
    .section {
      background: var(--card); border: 1px solid var(--border); border-radius: 16px;
      padding: 18px 20px; margin-bottom: 16px;
    }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; min-width: 960px; }
    th, td { padding: 8px 10px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
    th { color: var(--muted); font-weight: 600; background: #0f141d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; }
    .empty { color: var(--muted); font-style: italic; }
    .status { color: var(--muted); font-size: 0.9rem; margin-top: 8px; }
    .footer { color: var(--muted); font-size: 0.82rem; margin-top: 20px; }
    select {
      background: #0f141d; color: var(--text); border: 1px solid var(--border);
      border-radius: 10px; height: 34px; padding: 0 10px; font: inherit; min-width: 200px;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>Snapcopy Summary</h1>
      <p>Live FlashCopy Consistency Groups across monitored sites (read-only). Unlock LaunchPad, turn on Monitor for sites in Health Dashboard, pick a site (or All sites), then Refresh. Select rows with checkboxes before Export Excel.</p>
      <div class="hero-actions">
        <label>Site <select id="snapcopy-site" aria-label="Snapcopy summary site filter"><option value="">All sites</option></select></label>
        <button type="button" class="btn" id="snapcopy-refresh">Refresh</button>
        <button type="button" class="btn secondary" id="snapcopy-export">Export Excel</button>
        <a class="btn secondary" href="/contingency-groups">Consistency Groups</a>
        <a class="btn secondary" href="/fc-consistgrp">FlashCopy CGs</a>
        <a class="btn secondary" href="/">Health Dashboard</a>
      </div>
      <div class="status" id="snapcopy-status">Load cards, then Refresh. Export requires at least one checked CG.</div>
    </div>

    <div class="section">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th><input type="checkbox" id="snapcopy-select-all" aria-label="Select all CGs"></th>
              <th>Site</th><th>Host</th><th>Name</th><th>Status</th><th>Flash time</th>
              <th>Progress</th><th>Maps</th><th>Host maps</th><th>Size</th><th>Policy</th><th>Snaps/week</th>
            </tr>
          </thead>
          <tbody id="snapcopy-body">
            <tr><td colspan="12" class="empty">Click Refresh (Unlock required).</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="footer">LaunchPad {{APP_VERSION}}</div>
  </div>
  <script>
    const siteSelectEl = document.getElementById("snapcopy-site");
    const refreshBtn = document.getElementById("snapcopy-refresh");
    const exportBtn = document.getElementById("snapcopy-export");
    const statusEl = document.getElementById("snapcopy-status");
    const bodyEl = document.getElementById("snapcopy-body");
    let snapcopyRows = [];
    let snapcopyLoaded = false;

    function escapeHtml(value) {
      return String(value == null ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }
    function escapeAttr(value) { return escapeHtml(value); }

    function hostLink(host) {
      const trimmed = String(host || "").trim();
      if (!trimmed) return "—";
      return '<a href="https://' + escapeAttr(trimmed) + '" target="_blank" rel="noopener">'
        + escapeHtml(trimmed) + "</a>";
    }

    function renderRows(rows) {
      const selectAll = document.getElementById("snapcopy-select-all");
      const list = Array.isArray(rows) ? rows : [];
      if (!list.length) {
        bodyEl.innerHTML = '<tr><td colspan="12" class="empty">No FlashCopy CGs found for the selected site(s).</td></tr>';
        if (selectAll) {
          selectAll.checked = false;
          selectAll.indeterminate = false;
          selectAll.disabled = true;
        }
        return;
      }
      bodyEl.innerHTML = list.map((row) => {
        const rowKey = row.row_key || "";
        const flashTime = row.flash_time || "—";
        const progress = row.progress_pct != null && row.progress_pct !== ""
          ? row.progress_pct + "%"
          : "—";
        const maps = row.fc_map_count ?? "";
        const hostMaps = row.host_map_count ?? "";
        const size = row.total_size || "—";
        const policy = row.policy || "—";
        const snaps = row.snaps_per_week ?? "—";
        return "<tr>"
          + '<td><input type="checkbox" class="snapcopy-row-cb" data-row-key="' + escapeAttr(rowKey)
          + '" aria-label="Select ' + escapeAttr(row.name || "") + '"></td>'
          + "<td>" + escapeHtml(row.site || "") + "</td>"
          + "<td>" + hostLink(row.host) + "</td>"
          + "<td>" + escapeHtml(row.name || "") + "</td>"
          + "<td>" + escapeHtml(row.status || "") + "</td>"
          + "<td>" + escapeHtml(String(flashTime)) + "</td>"
          + "<td>" + escapeHtml(String(progress)) + "</td>"
          + "<td>" + escapeHtml(String(maps)) + "</td>"
          + "<td>" + escapeHtml(String(hostMaps)) + "</td>"
          + "<td>" + escapeHtml(String(size)) + "</td>"
          + "<td>" + escapeHtml(String(policy)) + "</td>"
          + "<td>" + escapeHtml(String(snaps)) + "</td>"
          + "</tr>";
      }).join("");
      if (selectAll) {
        selectAll.disabled = false;
        selectAll.checked = false;
        selectAll.indeterminate = false;
      }
    }

    function syncSelectAll() {
      const selectAll = document.getElementById("snapcopy-select-all");
      const boxes = Array.from(document.querySelectorAll(".snapcopy-row-cb"));
      if (!selectAll || !boxes.length) {
        if (selectAll) {
          selectAll.checked = false;
          selectAll.indeterminate = false;
        }
        return;
      }
      const checked = boxes.filter((box) => box.checked).length;
      selectAll.checked = checked === boxes.length;
      selectAll.indeterminate = checked > 0 && checked < boxes.length;
    }

    function selectedRowKeys() {
      return Array.from(document.querySelectorAll(".snapcopy-row-cb:checked"))
        .map((box) => box.getAttribute("data-row-key") || "")
        .filter(Boolean);
    }

    async function loadSiteOptions() {
      try {
        const res = await fetch("/api/fc-consistgrp/cards");
        const data = await res.json();
        const cards = (data.cards || []).filter((card) => {
          const typeOk = String(card.card_type || "ssh").toLowerCase() === "ssh";
          return typeOk;
        });
        const sorted = cards.slice().sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")));
        siteSelectEl.innerHTML = '<option value="">All sites</option>' + sorted.map((card) => {
          const monitorOn = !!card.monitor_on;
          const label = (card.name || card.id) + (monitorOn ? "" : " (monitor off)");
          return '<option value="' + escapeAttr(card.id) + '">' + escapeHtml(label) + "</option>";
        }).join("");
      } catch (_err) {
        /* ignore */
      }
    }

    async function refreshSummary() {
      statusEl.textContent = "Loading FlashCopy CG summary…";
      const cardId = siteSelectEl && siteSelectEl.value ? siteSelectEl.value : "";
      const url = "/api/contingency-groups/fc-cg-summary/live"
        + (cardId ? ("?card_id=" + encodeURIComponent(cardId)) : "");
      try {
        const response = await fetch(url);
        const data = await response.json().catch(() => ({}));
        if (response.status === 403) {
          statusEl.textContent = data.error || "Unlock LaunchPad to refresh CG summary.";
          return false;
        }
        if (!response.ok) {
          statusEl.textContent = data.error || ("CG summary failed (HTTP " + response.status + ")");
          return false;
        }
        snapcopyRows = Array.isArray(data.rows) ? data.rows : [];
        snapcopyLoaded = true;
        renderRows(snapcopyRows);
        const errCount = (data.errors || []).length;
        const skipped = Array.isArray(data.skipped_monitor_off) ? data.skipped_monitor_off : [];
        const eligible = data.eligible != null ? Number(data.eligible) : null;
        if (!snapcopyRows.length && eligible === 0 && skipped.length) {
          statusEl.textContent = "No monitored sites to scan. Turn on Monitor in Health Dashboard for: "
            + skipped.join(", ") + ", then Refresh.";
          return true;
        }
        if (!snapcopyRows.length && eligible === 0) {
          statusEl.textContent = "No monitored FlashSystem/SVC sites. Turn on Monitor in Health Dashboard, then Refresh.";
          return true;
        }
        statusEl.textContent = "Loaded " + snapcopyRows.length + " CG(s)."
          + (errCount ? (" " + errCount + " site error(s).") : "")
          + (snapcopyRows.length ? " Select rows, then Export Excel." : "");
        return true;
      } catch (error) {
        statusEl.textContent = "CG summary failed: " + (error.message || error);
        return false;
      }
    }

    async function exportSelected() {
      const selected = selectedRowKeys();
      if (!selected.length) {
        statusEl.textContent = "Select at least one CG to export.";
        return;
      }
      if (!snapcopyLoaded) {
        statusEl.textContent = "Refresh CG summary before exporting.";
        return;
      }
      exportBtn.disabled = true;
      statusEl.textContent = "Exporting Excel…";
      try {
        const response = await fetch("/api/contingency-groups/fc-cg-summary/export-selected", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ selected, open: true }),
        });
        if (response.status === 404) {
          const data = await response.json().catch(() => ({}));
          statusEl.textContent = data.error || "Refresh CG summary before exporting.";
          return;
        }
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          statusEl.textContent = data.error || ("Export failed (HTTP " + response.status + ")");
          return;
        }
        const blob = await response.blob();
        const disposition = response.headers.get("Content-Disposition") || "";
        const match = disposition.match(/filename=\"?([^\";]+)\"?/i);
        const filename = match ? match[1] : "FC_CG_Summary_MultiSite.xlsx";
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
        URL.revokeObjectURL(link.href);
        statusEl.textContent = "Export saved.";
      } catch (error) {
        statusEl.textContent = "Export failed: " + (error.message || error);
      } finally {
        exportBtn.disabled = false;
      }
    }

    refreshBtn.addEventListener("click", refreshSummary);
    exportBtn.addEventListener("click", exportSelected);
    document.getElementById("snapcopy-select-all").addEventListener("change", (event) => {
      const checked = event.target.checked;
      document.querySelectorAll(".snapcopy-row-cb").forEach((box) => {
        box.checked = checked;
      });
      syncSelectAll();
    });
    bodyEl.addEventListener("change", (event) => {
      if (!event.target.closest(".snapcopy-row-cb")) return;
      syncSelectAll();
    });
    siteSelectEl.addEventListener("change", () => {
      snapcopyRows = [];
      snapcopyLoaded = false;
      renderRows([]);
      statusEl.textContent = "Site changed — click Refresh again.";
    });

    loadSiteOptions();
  </script>
</body>
</html>"""
