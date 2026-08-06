"""Site Lookup browser page."""

SITE_LOOKUP_PATH = "/site-lookup"

SITE_LOOKUP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Site Lookup</title>
  <style>
    :root {
      --bg: #0f1115;
      --panel: #171a21;
      --panel2: #1e222b;
      --border: #2a2f3a;
      --text: #e8eaf0;
      --sub: #98a1b3;
      --accent: #4f8cff;
      --accent2: #3ad0a5;
      --warn: #e0a63b;
      --bad: #e05b5b;
      --ok: #3ad0a5;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      padding: 24px;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    }
    .wrap { max-width: 1150px; margin: 0 auto; }
    .title-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 18px;
    }
    h1 { margin: 0; font-size: 1.7rem; }
    .nav-link { color: var(--sub); font-size: .9rem; }
    .nav-link:hover { color: var(--text); }
    .searchbar {
      display: flex;
      gap: 10px;
      margin-bottom: 18px;
      position: relative;
    }
    .searchbar input, .row-filter {
      background: var(--panel);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 12px 14px;
      border-radius: 10px;
      font: inherit;
      outline: none;
    }
    .searchbar input { flex: 1; min-width: 0; }
    .searchbar input:focus, .row-filter:focus { border-color: var(--accent); }
    button {
      border: 0;
      border-radius: 10px;
      padding: 11px 17px;
      background: var(--accent);
      color: #fff;
      font: inherit;
      font-size: .9rem;
      font-weight: 650;
      cursor: pointer;
    }
    button.secondary { background: var(--panel2); border: 1px solid var(--border); }
    button:hover:not(:disabled) { filter: brightness(1.1); }
    button:disabled { opacity: .5; cursor: not-allowed; }
    .suggest {
      position: absolute;
      top: 50px;
      left: 0;
      right: 244px;
      z-index: 10;
      display: none;
      max-height: 280px;
      overflow-y: auto;
      background: var(--panel2);
      border: 1px solid var(--border);
      border-radius: 10px;
    }
    .suggest button {
      display: block;
      width: 100%;
      padding: 10px 14px;
      border: 0;
      border-radius: 0;
      background: transparent;
      color: var(--sub);
      text-align: left;
      font-weight: 400;
    }
    .suggest button:hover, .suggest button:focus { background: var(--panel); color: var(--text); }
    .empty { color: var(--sub); text-align: center; padding: 42px 20px; font-size: .95rem; }
    .banner {
      margin-bottom: 16px;
      padding: 12px 15px;
      border: 1px solid #6e2828;
      border-radius: 10px;
      background: #341919;
      color: #ffb2b2;
      white-space: pre-wrap;
    }
    .banner[hidden] { display: none; }
    .header-card {
      margin-bottom: 18px;
      padding: 20px 22px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 14px;
    }
    .header-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 12px;
    }
    .site-name { font-size: 1.35rem; font-weight: 700; }
    .site-sub { margin-top: 4px; color: var(--sub); font-size: .83rem; }
    .badge, .pill {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      font-size: .76rem;
      font-weight: 650;
    }
    .badge { padding: 5px 12px; background: #12321f; color: var(--ok); border: 1px solid #1e4f34; }
    .pill { padding: 3px 9px; background: #202b3c; color: #b9d1ff; }
    .pill.ok { background: #12321f; color: var(--ok); }
    .pill.warn { background: #3a2c11; color: var(--warn); }
    .pill.bad { background: #3a1414; color: var(--bad); }
    .stat-row { display: flex; gap: 26px; margin-top: 15px; flex-wrap: wrap; }
    .stat { color: var(--sub); font-size: .82rem; }
    .stat b { display: block; color: var(--text); font-size: .98rem; }
    .result-tools {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
      flex-wrap: wrap;
    }
    .status { color: var(--sub); font-size: .85rem; }
    .row-filter { width: min(360px, 100%); padding: 9px 12px; }
    .tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--border); margin-bottom: 18px; overflow-x: auto; }
    .tab {
      padding: 10px 16px;
      border: 0;
      border-bottom: 2px solid transparent;
      border-radius: 0;
      background: transparent;
      color: var(--sub);
      white-space: nowrap;
    }
    .tab.active { color: var(--text); border-color: var(--accent); }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: .84rem; }
    th {
      padding: 8px 10px;
      border-bottom: 1px solid var(--border);
      color: var(--sub);
      text-align: left;
      text-transform: uppercase;
      letter-spacing: .03em;
      font-size: .76rem;
    }
    td { padding: 9px 10px; border-bottom: 1px solid #1e222b; vertical-align: top; }
    tr:hover td { background: #1a1e26; }
    .mono { color: var(--sub); font-family: Consolas, monospace; font-size: .76rem; }
    .pool-card {
      margin-bottom: 14px;
      padding: 16px 18px;
      background: var(--panel2);
      border: 1px solid var(--border);
      border-radius: 12px;
    }
    .pool-top { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
    .pool-name { font-weight: 700; }
    .pool-bar { height: 8px; margin-bottom: 10px; overflow: hidden; border-radius: 999px; background: #11141a; }
    .pool-bar-fill { height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent2)); }
    .pool-stats { display: flex; gap: 22px; flex-wrap: wrap; color: var(--sub); font-size: .82rem; }
    .footer { margin-top: 24px; color: var(--sub); font-size: .8rem; }
    @media (max-width: 720px) {
      body { padding: 16px; }
      .searchbar { flex-wrap: wrap; }
      .searchbar input { flex-basis: 100%; }
      .searchbar button { flex: 1; }
      .suggest { top: 50px; right: 0; }
    }
  </style>
</head>
<body>
  <main class="wrap">
    <div class="title-row">
      <div>
        <h1>Site Lookup</h1>
        <div class="site-sub">Search a registered storage site, inspect cached inventory, or refresh it live.</div>
      </div>
      <a class="nav-link" href="/">Health Dashboard</a>
    </div>

    <div class="searchbar">
      <input id="site-query" type="search" placeholder="Enter card name, site IP, model, or card ID…" autocomplete="off" aria-label="Find a storage site">
      <div class="suggest" id="site-suggest" role="listbox"></div>
      <button type="button" id="lookup-btn">Look Up</button>
      <button type="button" class="secondary" id="refresh-btn" disabled>Live Refresh</button>
    </div>

    <div class="banner" id="error-banner" role="alert" hidden></div>
    <div id="result">
      <div class="empty">Loading registered storage sites…</div>
    </div>
    <div class="footer">LaunchPad {{APP_VERSION}}</div>
  </main>

  <script>
    const queryEl = document.getElementById("site-query");
    const suggestEl = document.getElementById("site-suggest");
    const lookupBtn = document.getElementById("lookup-btn");
    const refreshBtn = document.getElementById("refresh-btn");
    const errorEl = document.getElementById("error-banner");
    const resultEl = document.getElementById("result");

    let cards = [];
    let currentCard = null;
    let currentPayload = null;
    let activeTab = "hosts";
    let rowFilter = "";

    function escapeHtml(value) {
      return String(value == null ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function asRows(value) {
      return Array.isArray(value) ? value.filter((row) => row && typeof row === "object") : [];
    }

    function cardSearchText(card) {
      return [card.id, card.name, card.host, card.model, card.device_profile, card.serial_number]
        .map((value) => String(value || "").toLowerCase()).join(" ");
    }

    function filteredCards(value) {
      const needle = String(value || "").trim().toLowerCase();
      if (!needle) return cards.slice(0, 30);
      return cards.filter((card) => cardSearchText(card).includes(needle)).slice(0, 30);
    }

    function showSuggestions() {
      const matches = filteredCards(queryEl.value);
      if (!matches.length) {
        suggestEl.style.display = "none";
        suggestEl.innerHTML = "";
        return;
      }
      suggestEl.innerHTML = matches.map((card) => (
        '<button type="button" role="option" data-card-id="' + escapeHtml(card.id) + '">'
        + escapeHtml(card.name) + " — " + escapeHtml(card.host || card.model || ("Card " + card.id))
        + "</button>"
      )).join("");
      suggestEl.style.display = "block";
    }

    function hideSuggestions() {
      suggestEl.style.display = "none";
    }

    function setError(message) {
      errorEl.textContent = message || "";
      errorEl.hidden = !message;
    }

    function profileSupportsConsistencyGroups(card) {
      const profile = String(card && card.device_profile || "").toLowerCase();
      return profile.includes("flashsystem") || profile.includes("storwize") || profile.includes("svc");
    }

    function cachePayload(card) {
      const hosts = asRows(card.fc_hosts);
      const mappings = asRows(card.fc_mappings);
      const pools = asRows(card.pools);
      const volumeNames = new Map();
      mappings.forEach((mapping) => {
        const name = String(mapping.vdisk_name || mapping.volume_name || "").trim();
        if (name && !volumeNames.has(name)) {
          volumeNames.set(name, {
            name: name,
            uid: mapping.vdisk_UID || mapping.vdisk_uid || "",
            capacity: mapping.capacity || "",
            pool: mapping.pool || mapping.mdisk_grp_name || "",
            status: mapping.status || "",
          });
        }
      });
      return {
        card: {
          id: card.id,
          name: card.name,
          host: card.host || "",
          model: card.model || "",
          device_profile: card.device_profile || "",
          serial: card.serial_number || card.serial || "",
        },
        stats: {
          hosts: hosts.length,
          volumes: volumeNames.size,
          pools: pools.length,
          nodes: asRows(card.fc_ports_by_node).length,
          consistency_groups: 0,
        },
        hosts: hosts,
        volumes: Array.from(volumeNames.values()),
        mappings: mappings,
        consistency_groups: [],
        pools: pools,
        source: "cache",
        refreshed_at: card.updated_at || null,
        consistency_groups_available: profileSupportsConsistencyGroups(card),
        has_cache: hosts.length > 0 || mappings.length > 0 || pools.length > 0,
      };
    }

    function normalizePayload(payload) {
      const data = payload && typeof payload === "object" ? payload : {};
      return {
        card: data.card || {},
        stats: data.stats || {},
        hosts: asRows(data.hosts),
        volumes: asRows(data.volumes),
        mappings: asRows(data.mappings),
        consistency_groups: asRows(data.consistency_groups),
        pools: asRows(data.pools),
        source: data.source || "live",
        refreshed_at: data.refreshed_at || null,
        consistency_groups_available: profileSupportsConsistencyGroups(data.card || currentCard),
        has_cache: true,
      };
    }

    function valueText(value) {
      if (Array.isArray(value)) return value.map(valueText).join(" ");
      if (value && typeof value === "object") return Object.values(value).map(valueText).join(" ");
      return String(value == null ? "" : value);
    }

    function matchesFilter(row, related) {
      const needle = rowFilter.trim().toLowerCase();
      if (!needle) return true;
      return (valueText(row) + " " + valueText(related || [])).toLowerCase().includes(needle);
    }

    function rowStatus(status) {
      const text = String(status || "Unknown");
      const lower = text.toLowerCase();
      let css = "";
      if (lower.includes("online") || lower.includes("active") || lower === "ok") css = " ok";
      else if (lower.includes("degrad") || lower.includes("warning")) css = " warn";
      else if (lower.includes("offline") || lower.includes("error") || lower.includes("failed")) css = " bad";
      return '<span class="pill' + css + '">' + escapeHtml(text) + "</span>";
    }

    function emptyMessage(unavailable) {
      return '<div class="empty">' + (unavailable ? "Not available for this profile" : "No rows") + "</div>";
    }

    function renderHosts(data) {
      const rows = data.hosts.filter((host) => {
        const name = host.host_name || host.name || "";
        return matchesFilter(host, data.mappings.filter((mapping) => (
          String(mapping.host_name || mapping.name || "") === String(name)
        )));
      });
      if (!rows.length) return emptyMessage(false);
      return '<div class="table-wrap"><table><thead><tr>'
        + "<th>Host</th><th>Status</th><th>Type</th><th>Ports</th><th>Protocol</th>"
        + "</tr></thead><tbody>" + rows.map((host) => (
          "<tr><td>" + escapeHtml(host.host_name || host.name || "") + "</td>"
          + "<td>" + rowStatus(host.status || host.state) + "</td>"
          + "<td>" + escapeHtml(host.type || host.host_type || "—") + "</td>"
          + "<td>" + escapeHtml(host.port_count || host.ports || "—") + "</td>"
          + "<td>" + escapeHtml(host.protocol || "SCSI") + "</td></tr>"
        )).join("") + "</tbody></table></div>";
    }

    function renderVolumes(data) {
      const rows = data.volumes.filter((volume) => {
        const name = volume.name || volume.vdisk_name || "";
        return matchesFilter(volume, data.mappings.filter((mapping) => (
          String(mapping.vdisk_name || mapping.volume_name || "") === String(name)
        )));
      });
      if (!rows.length) return emptyMessage(false);
      return '<div class="table-wrap"><table><thead><tr>'
        + "<th>Volume</th><th>Status</th><th>Capacity</th><th>Pool</th><th>UID</th>"
        + "</tr></thead><tbody>" + rows.map((volume) => (
          "<tr><td>" + escapeHtml(volume.name || volume.vdisk_name || "") + "</td>"
          + "<td>" + rowStatus(volume.status || volume.state) + "</td>"
          + "<td>" + escapeHtml(volume.capacity || "—") + "</td>"
          + "<td>" + escapeHtml(volume.pool || volume.mdisk_grp_name || "—") + "</td>"
          + '<td class="mono">' + escapeHtml(volume.uid || volume.vdisk_UID || "—") + "</td></tr>"
        )).join("") + "</tbody></table></div>";
    }

    function renderConsistencyGroups(data) {
      if (!data.consistency_groups_available) return emptyMessage(true);
      const groups = data.consistency_groups.filter((group) => matchesFilter(group));
      const mappings = data.mappings.filter((mapping) => matchesFilter(mapping));
      if (!groups.length && !mappings.length) return emptyMessage(false);
      let html = "";
      if (groups.length) {
        html += '<div class="table-wrap"><table><thead><tr>'
          + "<th>Consistency Group</th><th>Status</th><th>Location</th><th>Volumes / Maps</th>"
          + "</tr></thead><tbody>" + groups.map((group) => (
            "<tr><td>" + escapeHtml(group.name || group.id || "") + "</td>"
            + "<td>" + rowStatus(group.status) + "</td>"
            + "<td>" + escapeHtml(group.location || "—") + "</td>"
            + "<td>" + escapeHtml(asRows(group.volumes).length + asRows(group.maps).length) + "</td></tr>"
          )).join("") + "</tbody></table></div>";
      }
      if (mappings.length) {
        html += '<div class="site-sub" style="margin:18px 0 8px">Host / volume mappings</div>'
          + '<div class="table-wrap"><table><thead><tr>'
          + "<th>Host</th><th>Volume</th><th>SCSI ID</th><th>I/O Group</th>"
          + "</tr></thead><tbody>" + mappings.map((mapping) => (
            "<tr><td>" + escapeHtml(mapping.host_name || "") + "</td>"
            + "<td>" + escapeHtml(mapping.vdisk_name || mapping.volume_name || "") + "</td>"
            + "<td>" + escapeHtml(mapping.scsi_id == null ? "—" : mapping.scsi_id) + "</td>"
            + "<td>" + escapeHtml(mapping.io_group_name || "—") + "</td></tr>"
          )).join("") + "</tbody></table></div>";
      }
      return html;
    }

    function numberValue(value) {
      const number = Number(value);
      return Number.isFinite(number) ? number : null;
    }

    function formatBytes(value) {
      const bytes = numberValue(value);
      if (bytes == null) return "—";
      if (bytes === 0) return "0 B";
      const units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"];
      const index = Math.min(Math.floor(Math.log(Math.abs(bytes)) / Math.log(1024)), units.length - 1);
      return (bytes / Math.pow(1024, index)).toFixed(index < 3 ? 0 : 2) + " " + units[index];
    }

    function renderPools(data) {
      const rows = data.pools.filter((pool) => matchesFilter(pool));
      if (!rows.length) return emptyMessage(false);
      return rows.map((pool) => {
        const pct = numberValue(pool.used_pct);
        const safePct = pct == null ? 0 : Math.max(0, Math.min(100, pct));
        return '<div class="pool-card"><div class="pool-top">'
          + '<div class="pool-name">' + escapeHtml(pool.name || "") + "</div>"
          + '<span class="badge">' + escapeHtml(pct == null ? "Capacity" : (pct.toFixed(1) + "% used")) + "</span>"
          + '</div><div class="pool-bar"><div class="pool-bar-fill" style="width:'
          + safePct + '%"></div></div><div class="pool-stats">'
          + "<span>Used <b>" + escapeHtml(formatBytes(pool.used_bytes)) + "</b></span>"
          + "<span>Free <b>" + escapeHtml(formatBytes(pool.free_bytes)) + "</b></span>"
          + "<span>Total <b>" + escapeHtml(formatBytes(pool.total_bytes)) + "</b></span>"
          + "</div></div>";
      }).join("");
    }

    function statusText(data) {
      if (data.refreshed_at) {
        const parsed = new Date(data.refreshed_at);
        const display = Number.isNaN(parsed.getTime()) ? data.refreshed_at : parsed.toLocaleString();
        return "Last updated: " + display + " · " + (data.source || "live");
      }
      return data.has_cache
        ? "Showing cached card data · use Live Refresh for full inventory."
        : "No cached inventory · use Live Refresh.";
    }

    function renderPayload() {
      if (!currentPayload) return;
      const data = currentPayload;
      const card = data.card || {};
      const stats = data.stats || {};
      const tabs = [
        ["hosts", "Hosts"],
        ["volumes", "Volumes"],
        ["consistency_groups", "Consistency Groups"],
        ["pools", "Pools"],
      ];
      let body = "";
      if (activeTab === "hosts") body = renderHosts(data);
      else if (activeTab === "volumes") body = renderVolumes(data);
      else if (activeTab === "consistency_groups") body = renderConsistencyGroups(data);
      else body = renderPools(data);
      resultEl.innerHTML = '<section class="header-card"><div class="header-top"><div>'
        + '<div class="site-name">' + escapeHtml(card.name || ("Card " + card.id)) + "</div>"
        + '<div class="site-sub">' + escapeHtml(card.model || card.device_profile || "Storage system")
        + (card.host ? (" · " + escapeHtml(card.host)) : "")
        + (card.serial ? (" · Serial " + escapeHtml(card.serial)) : "") + "</div></div>"
        + '<span class="badge">' + escapeHtml(data.source === "cache" ? "Cached" : "Live") + "</span></div>"
        + '<div class="stat-row"><div class="stat"><b>' + escapeHtml(stats.hosts == null ? data.hosts.length : stats.hosts) + "</b>Hosts</div>"
        + '<div class="stat"><b>' + escapeHtml(stats.volumes == null ? data.volumes.length : stats.volumes) + "</b>Volumes</div>"
        + '<div class="stat"><b>' + escapeHtml(stats.consistency_groups == null ? data.consistency_groups.length : stats.consistency_groups) + "</b>Consistency Groups</div>"
        + '<div class="stat"><b>' + escapeHtml(stats.pools == null ? data.pools.length : stats.pools) + "</b>Pools</div></div></section>"
        + '<div class="result-tools"><span class="status" id="lookup-status">' + escapeHtml(statusText(data)) + "</span>"
        + '<input class="row-filter" id="row-filter" type="search" value="' + escapeHtml(rowFilter)
        + '" placeholder="Filter host or volume names…" aria-label="Filter result rows"></div>'
        + '<div class="tabs" role="tablist">' + tabs.map((tab) => (
          '<button type="button" class="tab ' + (activeTab === tab[0] ? "active" : "")
          + '" data-tab="' + tab[0] + '" role="tab" aria-selected="' + (activeTab === tab[0]) + '">'
          + tab[1] + "</button>"
        )).join("") + '</div><section id="tab-body">' + body + "</section>";
      const filterEl = document.getElementById("row-filter");
      if (filterEl) {
        filterEl.addEventListener("input", () => {
          rowFilter = filterEl.value || "";
          const bodyEl = document.getElementById("tab-body");
          if (!bodyEl) return;
          if (activeTab === "hosts") bodyEl.innerHTML = renderHosts(currentPayload);
          else if (activeTab === "volumes") bodyEl.innerHTML = renderVolumes(currentPayload);
          else if (activeTab === "consistency_groups") bodyEl.innerHTML = renderConsistencyGroups(currentPayload);
          else bodyEl.innerHTML = renderPools(currentPayload);
        });
      }
    }

    function selectCard(card) {
      currentCard = card;
      currentPayload = cachePayload(card);
      activeTab = "hosts";
      rowFilter = "";
      queryEl.value = card.name || String(card.id);
      refreshBtn.disabled = false;
      hideSuggestions();
      setError("");
      renderPayload();
    }

    function lookup() {
      const raw = queryEl.value.trim().toLowerCase();
      const exact = cards.find((card) => (
        String(card.id).toLowerCase() === raw
        || String(card.name || "").toLowerCase() === raw
        || String(card.host || "").toLowerCase() === raw
      ));
      const card = exact || filteredCards(raw)[0];
      if (!card) {
        setError('No registered site matches "' + queryEl.value.trim() + '".');
        return;
      }
      selectCard(card);
    }

    async function liveRefresh() {
      if (!currentCard) return;
      refreshBtn.disabled = true;
      setError("");
      const statusEl = document.getElementById("lookup-status");
      if (statusEl) statusEl.textContent = "Refreshing live inventory…";
      try {
        const response = await fetch("/api/site-lookup/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ card_id: currentCard.id }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.error) {
          throw new Error(payload.error || ("Live Refresh failed (" + response.status + ")"));
        }
        currentPayload = normalizePayload(payload);
        renderPayload();
      } catch (error) {
        setError(String(error && error.message ? error.message : error));
        const preservedStatus = document.getElementById("lookup-status");
        if (preservedStatus) preservedStatus.textContent = "Live Refresh failed · showing previous data.";
      } finally {
        refreshBtn.disabled = false;
      }
    }

    async function loadCards() {
      try {
        const response = await fetch("/api/cards");
        const payload = await response.json().catch(() => []);
        if (!response.ok) throw new Error("Unable to load registered sites (" + response.status + ")");
        const rawCards = Array.isArray(payload) ? payload : asRows(payload.cards);
        cards = rawCards.filter((card) => card.id != null && String(card.name || "").trim());
        cards.sort((a, b) => String(a.name).localeCompare(String(b.name)));
        resultEl.innerHTML = cards.length
          ? '<div class="empty">Type a card name, site IP, model, or card ID above.</div>'
          : '<div class="empty">No registered storage sites are available.</div>';
      } catch (error) {
        resultEl.innerHTML = '<div class="empty">Unable to load registered storage sites.</div>';
        setError(String(error && error.message ? error.message : error));
      }
    }

    queryEl.addEventListener("input", showSuggestions);
    queryEl.addEventListener("focus", showSuggestions);
    queryEl.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        lookup();
      } else if (event.key === "Escape") {
        hideSuggestions();
      }
    });
    suggestEl.addEventListener("click", (event) => {
      const button = event.target.closest("[data-card-id]");
      if (!button) return;
      const card = cards.find((item) => String(item.id) === button.dataset.cardId);
      if (card) selectCard(card);
    });
    resultEl.addEventListener("click", (event) => {
      const button = event.target.closest("[data-tab]");
      if (!button || !currentPayload) return;
      activeTab = button.dataset.tab;
      renderPayload();
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".searchbar")) hideSuggestions();
    });
    lookupBtn.addEventListener("click", lookup);
    refreshBtn.addEventListener("click", liveRefresh);
    loadCards();
  </script>
</body>
</html>"""
