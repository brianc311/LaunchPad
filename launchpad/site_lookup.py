"""Browser UI for cached and live Spectrum Virtualize site inventory."""

SITE_LOOKUP_PATH = "/site-lookup"

SITE_LOOKUP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Site Lookup</title>
  <style>
    :root { --bg:#0b0f14; --panel:#121821; --card:#151c27; --text:#e8edf5; --muted:#8b98ab; --accent:#ff6b00; --accent2:#ff8533; --ok:#4ade80; --bad:#ef4444; --border:#2a3444; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; color:var(--text); font-family:Segoe UI,Inter,Arial,sans-serif; background:radial-gradient(circle at top,#172033 0%,var(--bg) 45%); }
    .wrap { max-width:1180px; margin:0 auto; padding:28px 20px 48px; }
    .hero,.panel { background:linear-gradient(135deg,#1a2230,#101722); border:1px solid var(--border); border-radius:18px; }
    .hero { padding:24px 28px; margin-bottom:20px; }
    h1 { margin:0 0 8px; color:var(--accent); font-size:1.9rem; }
    h2 { margin:0; color:var(--accent2); font-size:1.3rem; }
    p { line-height:1.45; } .sub,.status,.footer { color:var(--muted); }
    .actions,.nameplate,.tabs,.stats { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
    .actions { margin-top:16px; } .nameplate { margin-bottom:16px; align-items:baseline; }
    .meta { color:var(--muted); font-size:.9rem; } .badge { border:1px solid var(--border); color:var(--accent2); border-radius:999px; padding:3px 9px; font-size:.78rem; }
    .btn,button,select,input { font:inherit; }
    .btn,button.btn { height:35px; padding:0 14px; border:0; border-radius:10px; background:var(--accent); color:#111; cursor:pointer; font-weight:700; text-decoration:none; display:inline-flex; align-items:center; }
    .btn.secondary { background:#0f141d; color:var(--text); border:1px solid var(--border); }
    .btn:disabled { cursor:wait; opacity:.6; }
    select,input { min-height:35px; color:var(--text); background:#0f141d; border:1px solid var(--border); border-radius:10px; padding:0 10px; }
    #siteSelect { min-width:min(460px,100%); flex:1; }
    .panel { padding:20px 22px; margin-bottom:16px; } .hub-panel { max-width:700px; }
    .stats { margin:0 0 16px; }
    .stat { min-width:130px; flex:1; background:var(--card); border:1px solid var(--border); border-radius:12px; padding:12px 14px; }
    .stat b { display:block; font-size:1.55rem; color:var(--accent2); } .stat span { color:var(--muted); font-size:.82rem; }
    .tabs { margin:12px 0; border-bottom:1px solid var(--border); padding-bottom:12px; }
    .tab { background:#0f141d; color:var(--text); border:1px solid var(--border); }
    .tab.active { color:var(--accent2); border-color:var(--accent); }
    .table-wrap { overflow:auto; border:1px solid var(--border); border-radius:12px; }
    table { width:100%; border-collapse:collapse; font-size:.88rem; }
    th,td { padding:9px 11px; border-bottom:1px solid var(--border); text-align:left; vertical-align:top; white-space:nowrap; }
    th { position:sticky; top:0; background:#0f141d; color:var(--muted); z-index:1; }
    tr:nth-child(even) td { background:rgba(255,255,255,.02); }
    tr:last-child td { border-bottom:0; } .empty,.error { padding:18px; border:1px dashed var(--border); border-radius:12px; color:var(--muted); }
    .error { border-color:var(--bad); color:#fecaca; margin-bottom:14px; } .hidden { display:none; }
    @media (max-width:600px) { .wrap { padding:16px 12px 32px; } .hero,.panel { padding:18px; } #siteSelect { min-width:100%; } }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <h1>Site Lookup</h1>
      <p id="heroText">Browse cached storage inventory or refresh a site over SSH.</p>
      <div class="actions">
        <a class="btn secondary" href="/site-lookup">Site Lookup</a>
        <a class="btn secondary" href="/">Health</a>
        <a class="btn secondary" href="/capacity">Capacity</a>
        <a class="btn secondary" href="/fc-wwpn">FC WWPN</a>
      </div>
    </section>
    <div id="error" class="error hidden" role="alert"></div>
    <section id="hub" class="panel hub-panel">
      <h2>Open a storage site</h2>
      <p class="sub">FlashSystem, Storwize, and SVC sites open in a new browser tab.</p>
      <div class="actions">
        <select id="siteSelect" aria-label="Storage site"><option>Loading sites…</option></select>
        <button id="openBtn" class="btn" type="button">Open</button>
      </div>
      <p id="hubStatus" class="status"></p>
    </section>
    <section id="detail" class="hidden">
      <div class="panel">
        <div class="nameplate">
          <h2 id="siteName">Loading site…</h2>
          <span id="model" class="badge"></span>
          <span id="siteMeta" class="meta"></span>
        </div>
        <div id="stats" class="stats"></div>
        <div class="actions">
          <input id="q" type="search" placeholder="Filter hosts or volumes" aria-label="Filter hosts or volumes">
          <button id="refreshBtn" class="btn" type="button">Refresh</button>
          <span id="detailStatus" class="status"></span>
        </div>
      </div>
      <div class="panel">
        <div class="tabs" role="tablist">
          <button class="tab active" type="button" data-tab="hosts">Hosts</button>
          <button class="tab" type="button" data-tab="volumes">Volumes</button>
          <button class="tab" type="button" data-tab="mappings">Mappings</button>
          <button class="tab" type="button" data-tab="consistency_groups">Consistency groups</button>
        </div>
        <div id="table"></div>
      </div>
    </section>
    <p class="footer">LaunchPad Site Lookup v{{APP_VERSION}} · Cached inventory loads first; Refresh queries the selected site.</p>
  </main>
  <script>
    const query = new URLSearchParams(window.location.search);
    const cardId = query.get("card");
    const hub = document.getElementById("hub");
    const detail = document.getElementById("detail");
    const errorEl = document.getElementById("error");
    const siteSelect = document.getElementById("siteSelect");
    const openBtn = document.getElementById("openBtn");
    const hubStatus = document.getElementById("hubStatus");
    const detailStatus = document.getElementById("detailStatus");
    const refreshBtn = document.getElementById("refreshBtn");
    const tableEl = document.getElementById("table");
    const searchEl = document.getElementById("q");
    let state = null;
    let activeTab = "hosts";

    function escapeHtml(value) {
      return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }
    function showError(message) {
      errorEl.textContent = message;
      errorEl.classList.toggle("hidden", !message);
    }
    function rowsFor(tab) { return Array.isArray(state && state[tab]) ? state[tab] : []; }
    function filteredRows(tab) {
      const needle = searchEl.value.trim().toLocaleLowerCase();
      const rows = rowsFor(tab);
      if (!needle || tab === "consistency_groups") return rows;
      return rows.filter((row) => {
        const host = String(row.name || row.host || "").toLocaleLowerCase();
        const volume = String(row.name || row.volume || "").toLocaleLowerCase();
        return host.includes(needle) || volume.includes(needle);
      });
    }
    function tableHeaders(tab) {
      if (tab === "hosts") return [["name","Host"],["status","Status"],["type","Type"],["ports","Ports"],["protocol","Protocol"]];
      if (tab === "volumes") return [["name","Volume"],["capacity","Capacity"],["pool","Pool"],["status","Status"],["uid","UID"]];
      if (tab === "mappings") return [["host","Host"],["volume","Volume"],["scsi_id","SCSI / LUN ID"],["io_group","I/O group"]];
      return [["id","ID"],["name","Name"],["status","Status"],["type","Type"],["location","Location"],["volume_count","Volumes"],["host_count","Hosts"],["map_count","Mappings"]];
    }
    function filterRows() {
      const headers = tableHeaders(activeTab);
      const rows = filteredRows(activeTab);
      if (!rows.length) {
        tableEl.innerHTML = `<p class="empty">${searchEl.value ? "No matching rows." : "No inventory rows returned."}</p>`;
        return;
      }
      tableEl.innerHTML = `<div class="table-wrap"><table><thead><tr>${headers.map(([, label]) => `<th>${label}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${headers.map(([key]) => `<td>${escapeHtml(row[key])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    }
    function render() {
      const card = state.card || {};
      document.getElementById("siteName").textContent = card.name || "Storage site";
      document.getElementById("model").textContent = card.model || card.device_profile || "Spectrum Virtualize";
      document.getElementById("siteMeta").textContent = [card.host, card.serial ? `Serial ${card.serial}` : ""].filter(Boolean).join(" · ");
      const labels = [["hosts","Hosts"],["volumes","Volumes"],["mappings","Mappings"],["cgs","Consistency groups"]];
      document.getElementById("stats").innerHTML = labels.map(([key,label]) => `<div class="stat"><b>${Number(state.stats && state.stats[key] || 0)}</b><span>${label}</span></div>`).join("");
      detailStatus.textContent = `${state.source || "cache"}${state.refreshed_at ? ` · Refreshed ${state.refreshed_at}` : " · Cached inventory"}`;
      filterRows();
    }
    async function loadHub() {
      hub.classList.remove("hidden");
      try {
        const res = await fetch("/api/site-lookup/cards");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const cards = await res.json();
        if (!cards.length) {
          siteSelect.innerHTML = "<option value=''>No FlashSystem / SVC sites registered</option>";
          openBtn.disabled = true;
          return;
        }
        siteSelect.innerHTML = cards.map((card) => `<option value="${escapeHtml(card.id)}">${escapeHtml(card.name)}${card.host ? ` · ${escapeHtml(card.host)}` : ""}${card.model ? ` · ${escapeHtml(card.model)}` : ""}</option>`).join("");
        hubStatus.textContent = `${cards.length} site(s) available`;
      } catch (err) {
        siteSelect.innerHTML = "<option value=''>Could not load sites</option>";
        openBtn.disabled = true;
        showError(`Could not load storage sites: ${err.message || err}`);
      }
    }
    async function loadDetail() {
      hub.classList.add("hidden");
      detail.classList.remove("hidden");
      try {
        const res = await fetch(`/api/site-lookup/detail?card=${encodeURIComponent(cardId)}`);
        const payload = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(payload.error || `HTTP ${res.status}`);
        state = payload;
        render();
      } catch (err) {
        showError(`Could not load this site: ${err.message || err}`);
        tableEl.innerHTML = '<p class="empty"><a href="/site-lookup">Return to Site Lookup</a> and choose a registered FlashSystem / SVC site.</p>';
      }
    }
    async function refresh() {
      if (!state) return;
      refreshBtn.disabled = true;
      showError("");
      detailStatus.textContent = "Refreshing inventory over SSH…";
      try {
        const res = await fetch("/api/site-lookup/refresh", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({card_id:Number(cardId)}) });
        const payload = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(payload.error || `HTTP ${res.status}`);
        state = payload;
        render();
      } catch (err) {
        showError(`Refresh failed; cached inventory is still displayed. ${err.message || err}`);
        detailStatus.textContent = "Refresh failed";
      } finally {
        refreshBtn.disabled = false;
      }
    }
    openBtn.addEventListener("click", () => {
      if (siteSelect.value) window.open(`/site-lookup?card=${encodeURIComponent(siteSelect.value)}`, "_blank");
    });
    refreshBtn.addEventListener("click", refresh);
    searchEl.addEventListener("input", filterRows);
    document.querySelectorAll(".tab").forEach((button) => button.addEventListener("click", () => {
      activeTab = button.dataset.tab;
      document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab === button));
      filterRows();
    }));
    if (cardId) loadDetail(); else loadHub();
  </script>
</body>
</html>
"""
