"""Host / Volume Find page — search volume and host names across monitored arrays."""

VOLUME_FIND_PATH = "/volume-find"

VOLUME_FIND_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Host / Volume Find</title>
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
    .wrap { max-width: 1100px; margin: 0 auto; padding: 28px 20px 48px; }
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
    .find-type-toggle {
      display: inline-flex; border: 1px solid var(--border); border-radius: 10px; overflow: hidden;
    }
    .find-type-option {
      position: relative; display: inline-flex; align-items: center; margin: 0; cursor: pointer;
    }
    .find-type-option input {
      position: absolute; opacity: 0; width: 0; height: 0; pointer-events: none;
    }
    .find-type-option span {
      display: inline-flex; align-items: center; height: 34px; padding: 0 14px;
      font: inherit; font-weight: 600; color: var(--muted); background: #0f141d;
    }
    .find-type-option input:checked + span {
      background: var(--accent); color: #111;
    }
    #volume-search {
      width: min(420px, 100%); background: #0f141d; color: var(--text);
      border: 1px solid var(--border); border-radius: 10px; height: 34px;
      padding: 0 12px; font: inherit;
    }
    .status { color: var(--muted); font-size: 0.9rem; }
    .section {
      background: var(--card); border: 1px solid var(--border); border-radius: 16px;
      padding: 18px 20px; margin-bottom: 16px;
    }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th, td {
      border: 1px solid var(--border); padding: 8px 10px; text-align: left; vertical-align: top;
    }
    th {
      color: var(--muted); background: #0f141d; font-size: 0.76rem;
      text-transform: uppercase; letter-spacing: 0.03em;
    }
    .empty { padding: 14px 0; color: var(--muted); }
    .errors {
      margin: 0 0 12px; padding: 10px 12px; border-radius: 10px;
      background: #32151a; border: 1px solid #7f1d1d; color: var(--danger);
      white-space: pre-wrap; font-size: 0.88rem;
    }
    .errors:empty, .errors[hidden] { display: none; }
    .footer { margin-top: 18px; color: var(--muted); font-size: 0.85rem; }
    .site-ip-cell { white-space: nowrap; }
    .site-ip-link { color: var(--accent2); }
    .site-ip-empty { color: var(--muted); }
    .site-ip-input {
      width: min(180px, 100%); background: #0f141d; color: var(--text);
      border: 1px solid var(--border); border-radius: 8px; height: 28px;
      padding: 0 8px; font: inherit;
    }
    button.btn.site-ip-edit, button.btn.site-ip-save, button.btn.site-ip-cancel {
      height: 28px; padding: 0 10px; font-size: 0.8rem; margin-left: 6px;
    }
    #vf-progress-wrap { margin-top: 12px; max-width: 420px; }
    #vf-progress-wrap[hidden] { display: none; }
    .vf-progress-track {
      height: 8px; border-radius: 999px; background: #0f141d; border: 1px solid var(--border);
      overflow: hidden;
    }
    #vf-progress-bar { height: 100%; width: 0; background: var(--accent); }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <h1>Host / Volume Find</h1>
      <p>
        Search volume or host names across monitor-on IBM FlashSystem / Storwize / SVC and HPE 3PAR / Primera SSH cards.
        Find uses cached health command output; Search live runs SSH queries after LaunchPad is unlocked.
      </p>
      <div class="hero-actions">
        <div class="find-type-toggle" role="radiogroup" aria-label="Search type">
          <label class="find-type-option">
            <input type="radio" name="find-type" value="volume" checked>
            <span>Volume</span>
          </label>
          <label class="find-type-option">
            <input type="radio" name="find-type" value="host" id="find-type-host">
            <span>Host</span>
          </label>
        </div>
        <input type="search" id="volume-search" placeholder="Search volume name…" aria-label="Search volumes">
        <button type="button" id="volume-find-btn" class="btn">Find</button>
        <button type="button" id="volume-live-btn" class="btn secondary">Search live</button>
        <a class="btn secondary" href="/fc-wwpn">FC WWPN</a>
        <a class="btn secondary" href="/capacity">Capacity Report</a>
        <a class="btn secondary" href="/host-volume-health">Hosts & Volumes</a>
        <a class="btn secondary" href="/system-connectivity">System Connectivity</a>
        <a class="btn secondary" href="/">Health Dashboard</a>
        <span id="status" class="status" aria-live="polite"></span>
      </div>
      <div id="vf-progress-wrap" hidden>
        <div class="vf-progress-track"><div id="vf-progress-bar"></div></div>
      </div>
    </section>

    <section class="section">
      <div id="errors" class="errors" hidden></div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr id="results-head-row">
              <th>Card</th>
              <th>Site IP</th>
              <th>Vendor</th>
              <th>Volume</th>
              <th>Pool / CPG</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody id="results-body">
            <tr><td colspan="6" class="empty">Enter a volume name fragment and click Find.</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <p class="footer">LaunchPad Host / Volume Find v{{APP_VERSION}} · Keep LaunchPad running while searching live.</p>
  </main>

  <script>
    const searchEl = document.getElementById("volume-search");
    const findBtn = document.getElementById("volume-find-btn");
    const liveBtn = document.getElementById("volume-live-btn");
    const statusEl = document.getElementById("status");
    const errorsEl = document.getElementById("errors");
    const bodyEl = document.getElementById("results-body");
    const headRowEl = document.getElementById("results-head-row");
    const progressWrap = document.getElementById("vf-progress-wrap");
    const progressBar = document.getElementById("vf-progress-bar");
    let lastMatches = [];
    let lastFindType = "volume";
    let progressTimer = null;
    let progressActive = false;

    function getFindType() {
      return document.querySelector('input[name="find-type"]:checked')?.value || "volume";
    }

    function updateSearchPlaceholder() {
      const findType = getFindType();
      searchEl.placeholder = findType === "host"
        ? "Search host name…"
        : "Search volume name…";
      searchEl.setAttribute(
        "aria-label",
        findType === "host" ? "Search hosts" : "Search volumes"
      );
    }

    function emptyPromptMessage(findType) {
      return findType === "host"
        ? "Enter a host name fragment and click Find."
        : "Enter a volume name fragment and click Find.";
    }

    function renderTableHead(findType) {
      if (findType === "host") {
        headRowEl.innerHTML = (
          "<th>Card</th><th>Site IP</th><th>Vendor</th><th>Host</th><th>WWPNs</th><th>Source</th>"
        );
      } else {
        headRowEl.innerHTML = (
          "<th>Card</th><th>Site IP</th><th>Vendor</th><th>Volume</th>"
          + "<th>Pool / CPG</th><th>Source</th>"
        );
      }
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function normalizeSiteHost(raw) {
      let host = String(raw || "").trim();
      const lower = host.toLowerCase();
      if (lower.startsWith("https://")) host = host.slice(8);
      else if (lower.startsWith("http://")) host = host.slice(7);
      return host.replace(/\\/+$/, "").trim();
    }

    function siteIpHref(host) {
      const normalized = normalizeSiteHost(host);
      if (!normalized) return "";
      return "https://" + normalized;
    }

    function setBusy(busy) {
      findBtn.disabled = busy;
      liveBtn.disabled = busy;
    }

    function renderErrors(errors) {
      if (!errors || !errors.length) {
        errorsEl.hidden = true;
        errorsEl.textContent = "";
        return;
      }
      errorsEl.hidden = false;
      errorsEl.textContent = errors.map((e) => {
        const name = e.card_name || e.card_id || "card";
        return name + ": " + (e.error || "error");
      }).join("\\n");
    }

    function renderSiteIpCell(cardId, host) {
      const href = siteIpHref(host);
      const display = href
        ? ('<a class="site-ip-link" href="' + escapeHtml(href)
          + '" target="_blank" rel="noopener">' + escapeHtml(href) + "</a>")
        : '<span class="site-ip-empty">—</span>';
      return (
        '<td class="site-ip-cell" data-card-id="' + escapeHtml(cardId)
        + '" data-host="' + escapeHtml(host || "") + '">'
        + '<span class="site-ip-view">'
        + display
        + ' <button type="button" class="btn secondary site-ip-edit">Edit</button>'
        + "</span></td>"
      );
    }

    function enterSiteIpEdit(cell) {
      const cardId = cell.getAttribute("data-card-id") || "";
      const host = cell.getAttribute("data-host") || "";
      cell.innerHTML = (
        '<span class="site-ip-edit-form">'
        + '<input type="text" class="site-ip-input" value="' + escapeHtml(host)
        + '" aria-label="Site IP host">'
        + ' <button type="button" class="btn site-ip-save">Save</button>'
        + ' <button type="button" class="btn secondary site-ip-cancel">Cancel</button>'
        + "</span>"
      );
      const input = cell.querySelector(".site-ip-input");
      if (input) {
        input.focus();
        input.select();
      }
      cell.dataset.cardId = cardId;
    }

    function cancelSiteIpEdit(cell) {
      const cardId = cell.getAttribute("data-card-id") || "";
      const host = cell.getAttribute("data-host") || "";
      cell.outerHTML = renderSiteIpCell(cardId, host);
    }

    function applyHostToMatches(cardId, host) {
      lastMatches.forEach((m) => {
        if (String(m.card_id) === String(cardId)) m.host = host;
      });
      renderMatches(lastMatches, lastFindType);
    }

    async function saveSiteIp(cell) {
      const cardId = cell.getAttribute("data-card-id");
      const input = cell.querySelector(".site-ip-input");
      const host = normalizeSiteHost(input ? input.value : "");
      if (!host) {
        statusEl.textContent = "Host cannot be empty.";
        return;
      }
      statusEl.textContent = "Saving Site IP…";
      try {
        const res = await fetch("/api/volume-find/card-host", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ card_id: Number(cardId), host: host }),
        });
        const data = await res.json().catch(() => ({}));
        if (res.status === 403) {
          statusEl.textContent = data.error || "Unlock LaunchPad to save Site IP.";
          return;
        }
        if (!res.ok) {
          statusEl.textContent = data.error || ("Save failed (" + res.status + ")");
          return;
        }
        const saved = data.host || host;
        applyHostToMatches(cardId, saved);
        statusEl.textContent = "Site IP saved.";
      } catch (err) {
        statusEl.textContent = String(err && err.message ? err.message : err);
      }
    }

    function renderMatches(matches, findType) {
      lastFindType = findType || getFindType();
      lastMatches = matches || [];
      renderTableHead(lastFindType);
      if (!lastMatches.length) {
        bodyEl.innerHTML = '<tr><td colspan="6" class="empty">No matches.</td></tr>';
        return;
      }
      if (lastFindType === "host") {
        bodyEl.innerHTML = lastMatches.map((m) => (
          "<tr>"
          + "<td>" + escapeHtml(m.card_name || m.card_id || "") + "</td>"
          + renderSiteIpCell(m.card_id, m.host || "")
          + "<td>" + escapeHtml(m.vendor || "") + "</td>"
          + "<td>" + escapeHtml(m.host_name || "") + "</td>"
          + "<td>" + escapeHtml(m.wwpns || "") + "</td>"
          + "<td>" + escapeHtml(m.source || "") + "</td>"
          + "</tr>"
        )).join("");
        return;
      }
      bodyEl.innerHTML = lastMatches.map((m) => (
        "<tr>"
        + "<td>" + escapeHtml(m.card_name || m.card_id || "") + "</td>"
        + renderSiteIpCell(m.card_id, m.host || "")
        + "<td>" + escapeHtml(m.vendor || "") + "</td>"
        + "<td>" + escapeHtml(m.volume || "") + "</td>"
        + "<td>" + escapeHtml(m.pool_or_cpg || "") + "</td>"
        + "<td>" + escapeHtml(m.source || "") + "</td>"
        + "</tr>"
      )).join("");
    }

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
      if (total > 0) {
        let label = done + " / " + total + " arrays";
        if (current) {
          label += " · " + current;
        }
        statusEl.textContent = label;
      }
    }

    async function pollProgress() {
      try {
        const res = await fetch("/api/volume-find/progress");
        if (!progressActive) {
          return;
        }
        const data = await res.json().catch(() => ({}));
        if (!progressActive) {
          return;
        }
        applyProgress(data);
      } catch (_err) {
        /* ignore poll errors while search request is in flight */
      }
    }

    async function runSearch(mode) {
      const findType = getFindType();
      const q = (searchEl.value || "").trim();
      if (!q) {
        statusEl.textContent = "Enter a search term.";
        renderErrors([]);
        bodyEl.innerHTML = (
          '<tr><td colspan="6" class="empty">' + emptyPromptMessage(findType) + "</td></tr>"
        );
        renderTableHead(findType);
        return;
      }
      setBusy(true);
      statusEl.textContent = mode === "live" ? "Searching live…" : "Searching cache…";
      renderErrors([]);
      progressActive = true;
      applyProgress({done:0,total:0,current:""});
      progressTimer = setInterval(pollProgress, 400);
      pollProgress();
      try {
        const url = "/api/volume-find?q=" + encodeURIComponent(q)
          + "&mode=" + mode + "&type=" + encodeURIComponent(findType);
        const res = await fetch(url);
        const data = await res.json().catch(() => ({}));
        if (res.status === 403) {
          hideProgress();
          statusEl.textContent = data.error || "Unlock LaunchPad to search live.";
          return;
        }
        if (!res.ok) {
          const msg = data.error || ("Request failed (" + res.status + ")");
          statusEl.textContent = msg;
          renderErrors([{ card_name: "API", error: msg }]);
          renderTableHead(findType);
          bodyEl.innerHTML = '<tr><td colspan="6" class="empty">No matches.</td></tr>';
          return;
        }
        const matches = data.matches || [];
        const errors = data.errors || [];
        renderMatches(matches, findType);
        renderErrors(errors);
        if (matches.length) {
          const label = mode === "live" ? "live" : "cache";
          statusEl.textContent = matches.length + " " + label + " match"
            + (matches.length === 1 ? "" : "es")
            + (errors.length ? " · " + errors.length + " error" + (errors.length === 1 ? "" : "s") : "");
        } else if (mode === "cache") {
          statusEl.textContent = "No cache matches — try Search live";
        } else {
          statusEl.textContent = errors.length
            ? ("No live matches · " + errors.length + " error" + (errors.length === 1 ? "" : "s"))
            : "No live matches.";
        }
      } catch (err) {
        statusEl.textContent = String(err && err.message ? err.message : err);
        renderErrors([{ card_name: "Network", error: String(err) }]);
        renderTableHead(findType);
        bodyEl.innerHTML = '<tr><td colspan="6" class="empty">No matches.</td></tr>';
      } finally {
        hideProgress();
        setBusy(false);
      }
    }

    bodyEl.addEventListener("click", (ev) => {
      const target = ev.target;
      if (!(target instanceof Element)) return;
      const cell = target.closest(".site-ip-cell");
      if (!cell) return;
      if (target.classList.contains("site-ip-edit")) {
        enterSiteIpEdit(cell);
      } else if (target.classList.contains("site-ip-save")) {
        saveSiteIp(cell);
      } else if (target.classList.contains("site-ip-cancel")) {
        cancelSiteIpEdit(cell);
      }
    });

    document.querySelectorAll('input[name="find-type"]').forEach((el) => {
      el.addEventListener("change", () => {
        updateSearchPlaceholder();
        lastMatches = [];
        statusEl.textContent = "";
        renderErrors([]);
        const findType = getFindType();
        renderTableHead(findType);
        bodyEl.innerHTML = (
          '<tr><td colspan="6" class="empty">' + emptyPromptMessage(findType) + "</td></tr>"
        );
      });
    });

    findBtn.addEventListener("click", () => runSearch("cache"));
    liveBtn.addEventListener("click", () => runSearch("live"));
    searchEl.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") {
        ev.preventDefault();
        runSearch("cache");
      }
    });
  </script>
</body>
</html>
"""
