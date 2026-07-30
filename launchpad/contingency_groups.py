"""Editable contingency host, volume, and map reference library page."""

CONTINGENCY_GROUPS_PATH = "/contingency-groups"

CONTINGENCY_GROUPS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Consistency Groups</title>
  <style>
    :root { --bg:#0b0f14; --panel:#121821; --text:#e8edf5; --muted:#8b98ab; --accent:#ff6b00; --accent2:#ff8533; --ok:#4ade80; --border:#2a3444; --card:#151c27; --danger:#f87171; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; color:var(--text); font-family:Segoe UI,Inter,Arial,sans-serif; background:radial-gradient(circle at top,#172033 0%,var(--bg) 45%); }
    .wrap { max-width:1280px; margin:0 auto; padding:28px 20px 48px; }
    .hero, .section { background:var(--card); border:1px solid var(--border); border-radius:16px; padding:20px; margin-bottom:18px; }
    .hero { background:linear-gradient(135deg,#1a2230 0%,#101722 100%); }
    h1 { margin:0 0 8px; color:var(--accent); font-size:1.85rem; }
    h2 { margin:0; color:var(--accent2); font-size:1.05rem; }
    p { line-height:1.45; }
    .lede, .hint, .status, .footer { color:var(--muted); }
    a:not(.btn) {
      color: #9ec1ff;
      text-decoration: underline;
      text-underline-offset: 2px;
    }
    a:not(.btn):hover { color: #c5d9ff; }
    .actions, .picker, .section-head { display:flex; flex-wrap:wrap; align-items:center; gap:10px; }
    .actions { margin-top:16px; }
    .picker { margin-top:16px; }
    .section-head { justify-content:space-between; margin-bottom:12px; }
    button, .btn { min-height:34px; padding:0 14px; border:0; border-radius:10px; background:var(--accent); color:#111; font:inherit; font-weight:600; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; justify-content:center; }
    button.secondary, .btn.secondary { color:var(--text); background:#0f141d; border:1px solid var(--border); }
    button.danger { color:#fff; background:#b91c1c; }
    button:disabled { cursor:not-allowed; opacity:.6; }
    select, input, textarea { width:100%; color:var(--text); background:#0f141d; border:1px solid var(--border); border-radius:8px; padding:8px 9px; font:inherit; }
    select { width:auto; min-width:240px; }
    #cg-search {
      width:min(420px, 100%); height:34px; padding:0 12px; border-radius:10px;
    }
    input:focus, textarea:focus, select:focus { outline:none; border-color:var(--accent); }
    textarea { min-height:74px; resize:vertical; }
    .summary { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }
    label { display:flex; flex-direction:column; gap:6px; color:var(--muted); font-size:.85rem; font-weight:600; }
    .notes { grid-column:1 / -1; }
    .wizard-progress { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-bottom:18px; }
    .wizard-progress span { padding:10px; border:1px solid var(--border); border-radius:10px; color:var(--muted); text-align:center; font-weight:700; }
    .wizard-progress span.active { border-color:var(--accent); color:var(--text); background:#2d1b0e; }
    .wizard-step { min-height:110px; }
    .wizard-actions { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-top:16px; }
    #wizard-errors:empty { display:none; }
    .advanced-toggle { display:flex; justify-content:flex-end; margin-bottom:18px; }
    .table-wrap { overflow-x:auto; }
    table { width:100%; min-width:760px; border-collapse:collapse; }
    th, td { padding:7px; text-align:left; vertical-align:top; border:1px solid var(--border); }
    th { color:var(--muted); background:#0f141d; font-size:.78rem; text-transform:uppercase; letter-spacing:.04em; }
    td input, td textarea { min-width:100px; }
    td textarea { min-width:190px; min-height:62px; }
    .remove { min-height:30px; padding:0 10px; color:#fecaca; background:#32151a; border:1px solid #7f1d1d; }
    .empty { padding:14px; border:1px dashed var(--border); border-radius:10px; color:var(--muted); }
    .badge { display:inline-flex; margin:5px 0 0; padding:2px 6px; border:1px solid #7c3aed; border-radius:999px; color:#ddd6fe; background:#2e1065; font-size:.7rem; font-weight:700; letter-spacing:.06em; }
    .modal-backdrop { position:fixed; inset:0; z-index:10; display:grid; place-items:center; padding:20px; background:rgba(0,0,0,.72); }
    /* Author display:grid would otherwise override the HTML hidden attribute. */
    .modal-backdrop[hidden] { display:none !important; }
    .modal { width:min(900px,100%); max-height:85vh; overflow:auto; padding:20px; border:1px solid var(--border); border-radius:14px; background:var(--panel); box-shadow:0 20px 70px rgba(0,0,0,.45); }
    .modal-head { display:flex; align-items:center; justify-content:space-between; gap:12px; }
    .modal h2 { margin-bottom:8px; }
    .modal pre { margin:0; padding:12px; overflow:auto; border:1px solid var(--border); border-radius:8px; background:#0b0f14; color:#d8e3f2; white-space:pre-wrap; }
    .step-list { margin:8px 0 16px; padding-left:24px; }
    .skipped { color:var(--muted); text-decoration:line-through; }
    .warning { margin:8px 0; padding:9px 10px; border-left:3px solid var(--danger); background:#32151a; color:#fecaca; }
    .footer { margin:20px 0 0; font-size:.85rem; }
    .cli-panel { margin-top:18px; border:1px solid var(--border); border-radius:12px; background:#0f141d; }
    .cli-panel > summary { cursor:pointer; list-style:none; padding:12px 14px; color:var(--accent2); font-weight:700; }
    .cli-panel > summary::-webkit-details-marker { display:none; }
    .cli-panel > summary::before { content:"▸ "; }
    .cli-panel[open] > summary::before { content:"▾ "; }
    .cli-panel pre { margin:0; padding:0 14px 14px; overflow:auto; color:#d8e3f2; white-space:pre-wrap; font-family:Consolas,monospace; font-size:.85rem; }
    .cli-panel .cli-empty { padding:0 14px 14px; color:var(--muted); }
    @media (max-width:720px) { .summary { grid-template-columns:1fr; } select { width:100%; } .notes { grid-column:auto; } }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <h1>Consistency Groups</h1>
      <p class="lede">Maintain a planning reference for site hosts, volumes, and mappings. By default these entries are planning-only; Run Create (after Preview) can create _snap volumes and start FlashCopy on the linked array.</p>
      <div class="picker">
        <label for="group-picker">Group
          <select id="group-picker" aria-label="Consistency group"></select>
        </label>
        <button type="button" class="secondary" id="new-group-btn">New group</button>
        <input type="search" id="cg-search" placeholder="Search group, host, or volume…" aria-label="Search consistency groups">
        <button type="button" class="secondary" id="cg-search-btn">Find</button>
        <span class="status" id="status" aria-live="polite"></span>
      </div>
      <div class="actions">
        <button type="button" id="save-btn">Save</button>
        <button type="button" id="save-new-btn" class="secondary">Save as new</button>
        <button type="button" id="delete-btn" class="danger">Delete</button>
        <button type="button" id="export-btn" class="secondary">Export Excel</button>
        <button type="button" id="export-all-btn" class="secondary">Export All Excel</button>
        <button type="button" id="fc-wwpn-btn" class="secondary">Open in FC WWPN</button>
        <button type="button" id="sync-array-btn" class="secondary">Sync from array</button>
        <a class="btn secondary" href="/volume-find">Host / Volume Find</a>
        <a class="btn secondary" href="/fc-consistgrp">FlashCopy CGs</a>
        <a class="btn secondary" href="/snapcopy-summary">Snapcopy Summary</a>
        <a class="btn secondary" href="/">Health Dashboard</a>
      </div>
    </section>

    <section class="section">
      <div class="summary">
        <label>Name <input id="group-name" type="text" placeholder="e.g. Houston, TX"></label>
        <label>Location <input id="group-location" type="text" placeholder="Site location"></label>
        <label>Storage hint <input id="group-storage-hint" type="text" placeholder="Array or card name"></label>
        <label class="notes">Notes <textarea id="group-notes" placeholder="Planning notes, contacts, recovery details…"></textarea></label>
      </div>
    </section>

    <section class="section" id="wizard-panel">
      <div class="wizard-progress" aria-label="Wizard progress">
        <span data-wizard-progress="1">1 Source</span>
        <span data-wizard-progress="2">2 Target</span>
        <span data-wizard-progress="3">3 Create &amp; Map</span>
      </div>
      <div id="wizard-errors" aria-live="polite"></div>
      <section class="wizard-step" id="wizard-step-1">
        <div class="section-head"><h2>Source volumes</h2><button type="button" class="secondary" id="add-source-volume-btn">Add source volume</button></div>
        <p class="hint">Only source volumes are shown here. Use the Storage hint above to identify the source array or card.</p>
        <div class="table-wrap"><table><thead><tr><th>Name</th><th>Pool</th><th>Capacity</th><th></th></tr></thead><tbody id="wizard-source-volumes-body"></tbody></table></div>
        <h2>Source maps</h2>
        <p class="hint">Host mappings for the source volumes are listed for reference.</p>
        <div class="table-wrap"><table><thead><tr><th>Volume</th><th>Host</th><th>SCSI ID</th></tr></thead><tbody id="wizard-source-maps-body"></tbody></table></div>
      </section>
      <section class="wizard-step" id="wizard-step-2" hidden>
        <div class="section-head"><h2>Target volumes</h2><button type="button" id="generate-snaps-btn" class="secondary">Generate _snap rows</button></div>
        <p class="hint">Review each generated source and target pair. Target details remain editable before create.</p>
        <div class="table-wrap"><table><thead><tr><th>Source</th><th>Target</th><th>Pool</th><th>Capacity</th></tr></thead><tbody id="wizard-snap-pairs-body"></tbody></table></div>
      </section>
      <section class="wizard-step" id="wizard-step-3" hidden>
        <h2>Create &amp; Map</h2>
        <ol class="step-list">
          <li>Create target volumes</li>
          <li>Create FlashCopy (source → target)</li>
          <li>Start FlashCopy</li>
          <li>Map targets to hosts (same SCSI as source)</li>
        </ol>
        <p class="hint">Preview will mark each operation as create or skip if it already exists.</p>
        <p class="warning" id="wizard-storage-warning" hidden>Storage hint is required before Preview or Run Create.</p>
        <div class="table-wrap"><table><thead><tr><th>Source</th><th>Target</th><th>Hosts / SCSI</th><th>Action</th></tr></thead><tbody id="wizard-create-pairs-body"></tbody></table></div>
        <label class="hint">
          <input type="checkbox" id="snap-assign-cg-enabled">
          Assign new FlashCopy maps to CG
        </label>
        <label>CG name <input id="snap-assign-cg-name" type="text" placeholder="e.g. WIN_ESX_snap" disabled></label>
        <p class="hint">Optional. Creates the CG if missing, or assigns into it if it already exists. Fine-grained add/remove remains on <a href="/fc-consistgrp">FlashCopy CGs</a>.</p>
        <div class="actions">
          <button type="button" id="snap-preview-btn" class="secondary">Preview / Dry-run</button>
          <button type="button" id="snap-create-btn" class="danger">Run Create</button>
        </div>
      </section>
      <div class="wizard-actions">
        <button type="button" class="secondary" id="wizard-back-btn">Back</button>
        <button type="button" id="wizard-next-btn">Next</button>
      </div>
    </section>
    <div class="advanced-toggle"><button type="button" class="secondary" id="advanced-toggle-btn" aria-expanded="false">Advanced edit</button></div>
    <div id="advanced-panel" hidden>
      <section class="section">
        <div class="section-head"><h2>Hosts</h2><button type="button" class="secondary" id="add-host-btn">Add host</button></div>
        <div class="table-wrap"><table><thead><tr><th>Name</th><th>Status</th><th>Type</th><th>Ports</th><th>Protocol</th><th>WWPNs</th><th></th></tr></thead><tbody id="hosts-body"></tbody></table></div>
      </section>
      <section class="section">
        <div class="section-head"><h2>Volumes</h2><button type="button" class="secondary" id="add-volume-btn">Add volume</button></div>
        <div class="table-wrap"><table><thead><tr><th>Name</th><th>Capacity</th><th>Pool</th><th>UID</th><th>Protocol</th><th></th></tr></thead><tbody id="volumes-body"></tbody></table></div>
      </section>
      <section class="section">
        <div class="section-head"><h2>Maps</h2><button type="button" class="secondary" id="add-map-btn">Add map</button></div>
        <div class="table-wrap"><table><thead><tr><th>Volume</th><th>Host</th><th>SCSI ID</th><th></th></tr></thead><tbody id="maps-body"></tbody></table></div>
      </section>
    </div>
    <section class="section">
      <details class="cli-panel" id="cli-panel">
        <summary>CLI commands (Preview)</summary>
        <p class="cli-empty" id="cli-empty">Run Preview / Dry-run to fill this panel. It stays collapsed until you expand it.</p>
        <pre id="cli-commands" hidden></pre>
      </details>
    </section>
    <p class="footer">LaunchPad Consistency Groups v{{APP_VERSION}} · _snap creation is operator-initiated and only runs after confirmation.</p>
  </main>
  <div id="snap-modal-backdrop" class="modal-backdrop" hidden>
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="snap-modal-title">
      <div class="modal-head"><h2 id="snap-modal-title">_snap operation</h2><button type="button" class="secondary" id="snap-modal-close">Close</button></div>
      <div id="snap-modal-content"></div>
    </section>
  </div>
  <script>
    const STORAGE_KEY = "launchpad.contingencyGroups";
    const picker = document.getElementById("group-picker");
    const statusEl = document.getElementById("status");
    const hostsBody = document.getElementById("hosts-body");
    const volumesBody = document.getElementById("volumes-body");
    const mapsBody = document.getElementById("maps-body");
    const wizardSourceVolumesBody = document.getElementById("wizard-source-volumes-body");
    const wizardSourceMapsBody = document.getElementById("wizard-source-maps-body");
    const wizardSnapPairsBody = document.getElementById("wizard-snap-pairs-body");
    const wizardCreatePairsBody = document.getElementById("wizard-create-pairs-body");
    const wizardStorageWarning = document.getElementById("wizard-storage-warning");
    const wizardErrors = document.getElementById("wizard-errors");
    const wizardBackBtn = document.getElementById("wizard-back-btn");
    const wizardNextBtn = document.getElementById("wizard-next-btn");
    const advancedPanel = document.getElementById("advanced-panel");
    const advancedToggleBtn = document.getElementById("advanced-toggle-btn");
    const wizardLabels = ["1 Source", "2 Target", "3 Create & Map"];
    let groups = [];
    let currentId = "";
    let cgSearchQuery = "";
    let cgFilterContent = false;
    let persisted = false;
    let wizardStep = 1;
    let advancedOpen = false;
    window.__lastSnapPreviewOk = false;
    const snapModalBackdrop = document.getElementById("snap-modal-backdrop");
    const snapModalTitle = document.getElementById("snap-modal-title");
    const snapModalContent = document.getElementById("snap-modal-content");

    function escapeHtml(value) {
      return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
    }
    function escapeAttr(value) { return escapeHtml(value); }
    function parseWwpns(value) {
      return String(value || "").replaceAll(";", ",").replaceAll(String.fromCharCode(10), ",").split(",").map((item) => item.trim()).filter(Boolean);
    }
    function saveLocal() {
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(groups)); } catch (_err) { /* keep in memory */ }
    }
    function loadLocal() {
      try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
        return Array.isArray(saved) ? saved : [];
      } catch (_err) { return []; }
    }
    function emptyGroup() {
      return { id: "", name: "", location: "", storage_hint: "", notes: "", hosts: [], volumes: [], maps: [], snap_assign_cg_name: "", snap_assign_cg_enabled: false };
    }
    function activeGroup() {
      return groups.find((group) => String(group.id) === currentId) || emptyGroup();
    }
    // Keep identity/content match helpers in sync with launchpad.contingency_groups_search
    function normalizeSearchQuery(value) {
      return String(value || "").trim().toLowerCase();
    }
    function fieldMatchesText(field, q) {
      if (!q) return false;
      const text = String(field || "").trim().toLowerCase();
      return Boolean(text) && text.includes(q);
    }
    function wwpnMatches(field, q) {
      if (!q) return false;
      const qNorm = String(q).replace(/[\\s:]/g, "").toUpperCase();
      const parts = Array.isArray(field)
        ? field
        : String(field || "").split(/[;,\\s]+/);
      for (const part of parts) {
        const token = String(part || "").replace(/[\\s:]/g, "").toUpperCase();
        if (token && token.includes(qNorm)) return true;
      }
      return false;
    }
    function groupIdentityMatches(group, query) {
      const q = normalizeSearchQuery(query);
      if (!q) return true;
      return fieldMatchesText(group?.name, q) || fieldMatchesText(group?.location, q);
    }
    function hostRowMatches(host, query) {
      const q = normalizeSearchQuery(query);
      if (!q) return true;
      return fieldMatchesText(host?.name, q) || wwpnMatches(host?.wwpns, q);
    }
    function volumeRowMatches(volume, query) {
      const q = normalizeSearchQuery(query);
      if (!q) return true;
      return fieldMatchesText(volume?.name, q);
    }
    function mapRowMatches(mapping, query) {
      const q = normalizeSearchQuery(query);
      if (!q) return true;
      return fieldMatchesText(mapping?.volume, q) || fieldMatchesText(mapping?.host, q);
    }
    function groupContentMatches(group, query) {
      const q = normalizeSearchQuery(query);
      if (!q) return true;
      if ((group?.hosts || []).some((host) => host && hostRowMatches(host, query))) return true;
      if ((group?.volumes || []).some((volume) => volume && volumeRowMatches(volume, query))) return true;
      if ((group?.maps || []).some((mapping) => mapping && mapRowMatches(mapping, query))) return true;
      return false;
    }
    function findGroupsMatchingIdentity(query) {
      if (!String(query || "").trim()) return [];
      return groups
        .filter((group) => group && groupIdentityMatches(group, query))
        .slice()
        .sort((a, b) =>
          String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" })
        );
    }
    function findGroupsMatchingContent(query) {
      if (!String(query || "").trim()) return [];
      return groups
        .filter((group) => group && groupContentMatches(group, query))
        .slice()
        .sort((a, b) =>
          String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" })
        );
    }
    function applyCgSearchFilter(group) {
      if (!cgFilterContent || !cgSearchQuery) return;
      hostsBody.querySelectorAll("tr").forEach((tr) => {
        const indexAttr = tr.querySelector("[data-index]")?.dataset?.index;
        if (indexAttr === undefined) return;
        const host = (group.hosts || [])[Number(indexAttr)];
        if (!host || !hostRowMatches(host, cgSearchQuery)) tr.style.display = "none";
      });
      volumesBody.querySelectorAll("tr").forEach((tr) => {
        const indexAttr = tr.querySelector("[data-index]")?.dataset?.index;
        if (indexAttr === undefined) return;
        const volume = (group.volumes || [])[Number(indexAttr)];
        if (!volume || !volumeRowMatches(volume, cgSearchQuery)) tr.style.display = "none";
      });
      mapsBody.querySelectorAll("tr").forEach((tr) => {
        const indexAttr = tr.querySelector("[data-index]")?.dataset?.index;
        if (indexAttr === undefined) return;
        const mapping = (group.maps || [])[Number(indexAttr)];
        if (!mapping || !mapRowMatches(mapping, cgSearchQuery)) tr.style.display = "none";
      });
    }
    function selectMatchedGroup(group) {
      currentId = String(group.id || "");
      wizardStep = 1;
      showWizardErrors([]);
      window.__lastSnapPreviewOk = false;
      clearCliPanel();
    }
    function runCgSearch() {
      const searchInput = document.getElementById("cg-search");
      const raw = (searchInput?.value || "").trim();
      if (!raw) {
        cgSearchQuery = "";
        cgFilterContent = false;
        render();
        statusEl.textContent = "Search cleared.";
        return;
      }
      const identityMatches = findGroupsMatchingIdentity(raw);
      if (identityMatches.length) {
        const first = identityMatches[0];
        cgSearchQuery = raw;
        cgFilterContent = false;
        selectMatchedGroup(first);
        render();
        const extra = identityMatches.length - 1;
        statusEl.textContent = extra
          ? `Selected ${first.name || first.id} (also ${extra} other group(s))`
          : `Selected ${first.name || first.id}`;
        return;
      }
      const contentMatches = findGroupsMatchingContent(raw);
      if (contentMatches.length) {
        const first = contentMatches[0];
        cgSearchQuery = raw;
        cgFilterContent = true;
        selectMatchedGroup(first);
        render();
        const extra = contentMatches.length - 1;
        statusEl.textContent = extra
          ? `Found in ${first.name || first.id} (also in ${extra} other group(s))`
          : `Found in ${first.name || first.id}`;
        return;
      }
      cgSearchQuery = "";
      cgFilterContent = false;
      render();
      statusEl.textContent = "No matching groups, hosts, or volumes";
    }
    function updatePicker() {
      picker.innerHTML = groups.length
        ? groups.map((group) => `<option value="${escapeAttr(group.id)}">${escapeHtml(group.name || group.id)}</option>`).join("")
        : '<option value="">New group</option>';
      picker.value = currentId;
    }
    function renderRowInputs(items, columns, body, kind) {
      if (!items.length) {
        body.innerHTML = `<tr><td colspan="${columns.length + 1}" class="empty">No ${kind} yet. Use Add ${kind.slice(0, -1)}.</td></tr>`;
        return;
      }
      body.innerHTML = items.map((item, index) => `<tr>${columns.map((column, columnIndex) => {
        const value = column.key === "wwpns" ? (item.wwpns || []).join(String.fromCharCode(10)) : item[column.key] || "";
        const control = column.multiline
          ? `<textarea data-kind="${kind}" data-index="${index}" data-key="${column.key}" placeholder="${column.placeholder || ""}">${escapeHtml(value)}</textarea>`
          : `<input data-kind="${kind}" data-index="${index}" data-key="${column.key}" type="${column.type || "text"}" value="${escapeAttr(value)}">`;
        const isSnap = ["volumes", "maps"].includes(kind) && String(item.role || "").toLowerCase() === "snap";
        return `<td>${control}${columnIndex === 0 && isSnap ? '<span class="badge">SNAP</span>' : ""}</td>`;
      }).join("")}<td><button type="button" class="remove" data-remove-kind="${kind}" data-index="${index}">Remove</button></td></tr>`).join("");
    }
    function isSnapVolume(volume) {
      if (!volume || typeof volume !== "object") return false;
      const role = String(volume.role || "source").toLowerCase();
      return role === "snap" || String(volume.name || "").endsWith("_snap");
    }
    function sourceVolumeEntries(group) {
      return (group.volumes || []).map((volume, index) => ({ volume, index })).filter(({ volume }) => !isSnapVolume(volume));
    }
    function snapPairs(group) {
      const targets = (group.volumes || []).filter((volume) => isSnapVolume(volume));
      return sourceVolumeEntries(group).map(({ volume: source }) => {
        const sourceName = String(source.name || "");
        const target = targets.find((volume) => String(volume.source_volume || "") === sourceName)
          || targets.find((volume) => String(volume.name || "") === `${sourceName}_snap`);
        return { source, target };
      });
    }
    function validateWizardStep(group, step) {
      const warnings = [];
      const sources = sourceVolumeEntries(group).map(({ volume }) => volume);
      if (step === 1) {
        if (!sources.length) return ["At least one source volume is required"];
        sources.forEach((volume) => {
          const name = String(volume.name || "").trim();
          if (!name) warnings.push("Source volume name is required");
          if (!String(volume.pool || "").trim()) warnings.push(`Missing pool for source volume ${name || "(unnamed)"}`);
          if (!String(volume.capacity || "").trim()) warnings.push(`Missing or invalid size/capacity for source volume ${name || "(unnamed)"}`);
        });
      }
      if (step === 2) {
        const targets = (group.volumes || []).filter((volume) => isSnapVolume(volume));
        sources.forEach((source) => {
          const sourceName = String(source.name || "");
          const target = targets.find((volume) => String(volume.source_volume || "") === sourceName)
            || targets.find((volume) => String(volume.name || "") === `${sourceName}_snap`);
          if (!target || !isSnapVolume(target)) warnings.push(`Missing target volume for source ${sourceName}`);
        });
      }
      return warnings;
    }
    function showWizardErrors(warnings) {
      wizardErrors.innerHTML = (warnings || []).map((warning) => `<p class="warning">${escapeHtml(warning)}</p>`).join("");
    }
    function renderWizardSourceStep(group) {
      const sources = sourceVolumeEntries(group);
      wizardSourceVolumesBody.innerHTML = sources.length ? sources.map(({ volume, index }) => `<tr>
        <td><input data-wizard-volume-index="${index}" data-key="name" value="${escapeAttr(volume.name || "")}"></td>
        <td><input data-wizard-volume-index="${index}" data-key="pool" value="${escapeAttr(volume.pool || "")}"></td>
        <td><input data-wizard-volume-index="${index}" data-key="capacity" value="${escapeAttr(volume.capacity || "")}"></td>
        <td><button type="button" class="remove" data-remove-source-index="${index}">Remove</button></td>
      </tr>`).join("") : '<tr><td colspan="4" class="empty">No source volumes yet. Use Add source volume.</td></tr>';
      const sourceNames = new Set(sources.map(({ volume }) => String(volume.name || "")));
      const sourceMaps = (group.maps || []).filter((mapping) => mapping && String(mapping.role || "source").toLowerCase() !== "snap" && sourceNames.has(String(mapping.volume || "")));
      wizardSourceMapsBody.innerHTML = sourceMaps.length ? sourceMaps.map((mapping) => `<tr>
        <td>${escapeHtml(mapping.volume || "")}</td><td>${escapeHtml(mapping.host || "")}</td><td>${escapeHtml(mapping.scsi_id || "")}</td>
      </tr>`).join("") : '<tr><td colspan="3" class="empty">No source maps.</td></tr>';
    }
    function renderWizardTargetStep(group) {
      const pairs = snapPairs(group);
      wizardSnapPairsBody.innerHTML = pairs.length ? pairs.map(({ source, target }) => {
        if (!target) return `<tr><td>${escapeHtml(source.name || "")}</td><td colspan="3" class="empty">Target not generated.</td></tr>`;
        const index = (group.volumes || []).indexOf(target);
        return `<tr>
          <td>${escapeHtml(source.name || "")}</td>
          <td><input data-wizard-volume-index="${index}" data-key="name" value="${escapeAttr(target.name || "")}"></td>
          <td><input data-wizard-volume-index="${index}" data-key="pool" value="${escapeAttr(target.pool || "")}"></td>
          <td><input data-wizard-volume-index="${index}" data-key="capacity" value="${escapeAttr(target.capacity || "")}"></td>
        </tr>`;
      }).join("") : '<tr><td colspan="4" class="empty">No source and target pairs.</td></tr>';
    }
    function renderWizardCreateStep(group) {
      const pairs = snapPairs(group);
      wizardStorageWarning.hidden = Boolean(String(group.storage_hint || "").trim());
      wizardCreatePairsBody.innerHTML = pairs.length ? pairs.map(({ source, target }) => {
        const sourceName = String(source.name || "");
        const mappings = (group.maps || []).filter((mapping) =>
          mapping && String(mapping.role || "source").toLowerCase() !== "snap" && String(mapping.volume || "") === sourceName
        );
        const hostsAndScsi = mappings.length
          ? mappings.map((mapping) => `${escapeHtml(mapping.host || "(host missing)")} / SCSI ${escapeHtml(mapping.scsi_id || "(missing)")}`).join("<br>")
          : '<span class="hint">No source host maps.</span>';
        return `<tr>
          <td>${escapeHtml(sourceName)}</td>
          <td>${target ? escapeHtml(target.name || "") : '<span class="warning">Target not generated.</span>'}</td>
          <td>${hostsAndScsi}</td>
          <td class="hint">Preview to determine create or skip</td>
        </tr>`;
      }).join("") : '<tr><td colspan="4" class="empty">No source and target pairs.</td></tr>';
    }
    function renderWizard() {
      const group = activeGroup();
      wizardStep = Math.max(1, Math.min(3, wizardStep));
      renderWizardSourceStep(group);
      renderWizardTargetStep(group);
      renderWizardCreateStep(group);
      document.querySelectorAll("[data-wizard-progress]").forEach((item) => {
        const step = Number(item.dataset.wizardProgress);
        const active = step === wizardStep;
        item.setAttribute("aria-label", wizardLabels[step - 1]);
        item.classList.toggle("active", active);
        if (active) item.setAttribute("aria-current", "step");
        else item.removeAttribute("aria-current");
      });
      [1, 2, 3].forEach((step) => {
        document.getElementById(`wizard-step-${step}`).hidden = step !== wizardStep;
      });
      wizardBackBtn.disabled = wizardStep === 1;
      wizardNextBtn.hidden = wizardStep === 3;
      advancedPanel.hidden = !advancedOpen;
      advancedToggleBtn.textContent = advancedOpen ? "Hide advanced" : "Advanced edit";
      advancedToggleBtn.setAttribute("aria-expanded", String(advancedOpen));
    }
    function render() {
      const group = activeGroup();
      document.getElementById("group-name").value = group.name || "";
      document.getElementById("group-location").value = group.location || "";
      document.getElementById("group-storage-hint").value = group.storage_hint || "";
      document.getElementById("group-notes").value = group.notes || "";
      const assignEnabled = Boolean(group.snap_assign_cg_enabled);
      const assignEnabledEl = document.getElementById("snap-assign-cg-enabled");
      const assignNameEl = document.getElementById("snap-assign-cg-name");
      assignEnabledEl.checked = assignEnabled;
      assignNameEl.value = group.snap_assign_cg_name || "";
      assignNameEl.disabled = !assignEnabled;
      updatePicker();
      renderRowInputs(group.hosts || [], [
        { key: "name" }, { key: "status" }, { key: "host_type" }, { key: "port_count", type: "number" }, { key: "protocol" }, { key: "wwpns", multiline: true, placeholder: "One per line, comma, or semicolon separated" },
      ], hostsBody, "hosts");
      renderRowInputs(group.volumes || [], [
        { key: "name" }, { key: "capacity" }, { key: "pool" }, { key: "uid" }, { key: "protocol" },
      ], volumesBody, "volumes");
      renderRowInputs(group.maps || [], [
        { key: "volume" }, { key: "host" }, { key: "scsi_id" },
      ], mapsBody, "maps");
      document.getElementById("delete-btn").disabled = !currentId;
      document.getElementById("fc-wwpn-btn").disabled = !currentId;
      document.getElementById("generate-snaps-btn").disabled = !currentId;
      document.getElementById("snap-preview-btn").disabled = !currentId;
      document.getElementById("snap-create-btn").disabled = !currentId || !window.__lastSnapPreviewOk;
      renderWizard();
      applyCgSearchFilter(group);
    }
    function setFieldValue(event) {
      const input = event.target;
      const kind = input.dataset.kind;
      const index = Number(input.dataset.index);
      const key = input.dataset.key;
      if (!kind || !Number.isInteger(index) || !key) return;
      const group = activeGroup();
      const items = group[kind] || [];
      if (!items[index]) return;
      items[index][key] = key === "wwpns" ? parseWwpns(input.value) : input.value;
    }
    function readSummary(group) {
      group.name = document.getElementById("group-name").value.trim();
      group.location = document.getElementById("group-location").value.trim();
      group.storage_hint = document.getElementById("group-storage-hint").value.trim();
      group.notes = document.getElementById("group-notes").value.trim();
      group.snap_assign_cg_enabled = document.getElementById("snap-assign-cg-enabled").checked;
      group.snap_assign_cg_name = document.getElementById("snap-assign-cg-name").value.trim();
    }
    function createId() { return `group-${Date.now()}`; }
    function addRow(kind) {
      const group = activeGroup();
      const defaults = {
        hosts: { name: "", status: "Online", host_type: "Generic", port_count: "", protocol: "SCSI", wwpns: [] },
        volumes: { name: "", capacity: "", pool: "", uid: "", protocol: "SCSI", role: "source" },
        maps: { volume: "", host: "", scsi_id: "", role: "source" },
      };
      group[kind].push(defaults[kind]);
      render();
    }
    async function persistGroup(saveAsNew) {
      const group = activeGroup();
      readSummary(group);
      if (!group.name) { statusEl.textContent = "Enter a group name before saving."; return; }
      if (saveAsNew && group.id) {
        const copy = JSON.parse(JSON.stringify(group));
        copy.id = createId();
        groups.push(copy);
        currentId = copy.id;
      } else if (!group.id) {
        const copy = JSON.parse(JSON.stringify(group));
        copy.id = createId();
        groups.push(copy);
        currentId = copy.id;
      }
      const current = activeGroup();
      current.updated_at = new Date().toISOString();
      saveLocal();
      render();
      statusEl.textContent = persisted ? "Saving…" : "Saved in this browser only — unlock LaunchPad to persist.";
      if (!persisted) return;
      try {
        const response = await fetch("/api/contingency-groups", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ group: current }) });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        groups = Array.isArray(data.groups) ? data.groups : groups;
        saveLocal();
        statusEl.textContent = "Saved in LaunchPad and this browser.";
        render();
      } catch (error) {
        persisted = false;
        statusEl.textContent = `Saved locally only: ${error.message || error}`;
      }
    }
    async function deleteGroup() {
      if (!currentId) return;
      const deletingId = currentId;
      if (!window.confirm("Delete this consistency group?")) return;
      groups = groups.filter((group) => group.id !== deletingId);
      currentId = groups[0] ? groups[0].id : "";
      saveLocal();
      wizardStep = 1;
      showWizardErrors([]);
      render();
      if (!persisted) { statusEl.textContent = "Deleted from this browser only."; return; }
      try {
        const response = await fetch("/api/contingency-groups", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ delete_id: deletingId }) });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        groups = Array.isArray(data.groups) ? data.groups : groups;
        saveLocal();
        statusEl.textContent = "Deleted.";
        render();
      } catch (error) { statusEl.textContent = `Deleted locally only: ${error.message || error}`; }
    }
    function showSnapModal(title, content) {
      snapModalTitle.textContent = title;
      snapModalContent.innerHTML = content;
      snapModalBackdrop.hidden = false;
    }
    function closeSnapModal() { snapModalBackdrop.hidden = true; }
    function snapWarnings(warnings) {
      return (warnings || []).map((warning) => `<p class="warning">${escapeHtml(warning)}</p>`).join("");
    }
    async function postSnap(path, payload) {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({ ok: false, warnings: [`HTTP ${response.status}`] }));
      if (!response.ok && !data.warnings) data.warnings = [data.error || `HTTP ${response.status}`];
      return data;
    }
    async function persistCurrentGroupBeforeSnapOps() {
      if (!currentId) {
        statusEl.textContent = "Select or save a group before running _snap operations.";
        return false;
      }
      const group = activeGroup();
      readSummary(group);
      group.updated_at = new Date().toISOString();
      saveLocal();
      if (!persisted) {
        statusEl.textContent = "Unlock LaunchPad to save changes before _snap operations.";
        return false;
      }
      try {
        const response = await fetch("/api/contingency-groups", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ group }),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        groups = Array.isArray(data.groups) ? data.groups : groups;
        saveLocal();
        return true;
      } catch (error) {
        statusEl.textContent = `Unable to save before _snap operation: ${error.message || error}`;
        return false;
      }
    }
    function clearCliPanel() {
      const empty = document.getElementById("cli-empty");
      const commands = document.getElementById("cli-commands");
      const panel = document.getElementById("cli-panel");
      if (!empty || !commands || !panel) return;
      empty.hidden = false;
      commands.hidden = true;
      commands.textContent = "";
      panel.open = false;
    }
    function fillCliPanel(text) {
      const empty = document.getElementById("cli-empty");
      const commands = document.getElementById("cli-commands");
      if (!empty || !commands) return;
      const body = String(text || "").trim();
      if (!body) { clearCliPanel(); return; }
      empty.hidden = true;
      commands.hidden = false;
      commands.textContent = body;
    }
    function formatResolvedCard(card, fallbackHint) {
      if (card && (card.name || card.host)) {
        const name = card.name || fallbackHint || "Resolved card";
        const host = card.host ? ` (${card.host})` : "";
        return `${name}${host}`;
      }
      return fallbackHint || "Not specified";
    }
    async function generateSnapRows() {
      if (!currentId) return false;
      if (!(await persistCurrentGroupBeforeSnapOps())) return false;
      statusEl.textContent = "Generating _snap rows…";
      try {
        const data = await postSnap("/api/contingency-groups/generate-snaps", { group_id: currentId });
        if (!data.ok || !data.group) {
          statusEl.textContent = (data.warnings || [data.error || "Unable to generate _snap rows."]).join(" ");
          return false;
        }
        const index = groups.findIndex((group) => String(group.id) === currentId);
        if (index >= 0) groups[index] = data.group;
        saveLocal();
        window.__lastSnapPreviewOk = false;
        statusEl.textContent = "Generated _snap rows and saved in LaunchPad.";
        render();
        return true;
      } catch (error) {
        statusEl.textContent = `Unable to generate _snap rows: ${error.message || error}`;
        return false;
      }
    }
    async function previewSnaps() {
      if (!currentId) return;
      if (!(await persistCurrentGroupBeforeSnapOps())) return;
      statusEl.textContent = "Preparing _snap preview…";
      try {
        const data = await postSnap("/api/contingency-groups/snap-preview", {
          group_id: currentId,
          snap_assign_cg_enabled: document.getElementById("snap-assign-cg-enabled").checked,
          snap_assign_cg_name: document.getElementById("snap-assign-cg-name").value.trim(),
        });
        const warnings = Array.isArray(data.warnings) ? data.warnings : [];
        const blocking = !data.ok;
        window.__lastSnapPreviewOk = !blocking;
        const group = activeGroup();
        const steps = Array.isArray(data.steps) ? data.steps : [];
        const stepHtml = steps.length
          ? `<ol class="step-list">${steps.map((step) => `<li class="${step.skip ? "skipped" : ""}"><strong>${escapeHtml(step.purpose || step.kind || "Step")}</strong>${step.skip ? ` — skipped: ${escapeHtml(step.reason || "already exists")}` : ""}<pre>${escapeHtml(step.cmd || "")}</pre></li>`).join("")}</ol>`
          : "<p class='hint'>No create steps were returned.</p>";
        const cliText = steps.map((step) => {
          const label = step.purpose || step.kind || "Step";
          const state = step.skip ? "skipped" : "ready";
          return `[${state}] ${label}${step.cmd ? String.fromCharCode(10) + step.cmd : ""}`;
        }).join(String.fromCharCode(10));
        fillCliPanel(cliText || "No create steps were returned.");
        showSnapModal(
          "Preview / Dry-run",
          `<p class="hint">Target card: <strong>${escapeHtml(formatResolvedCard(data.card, group.storage_hint))}</strong></p>${snapWarnings(warnings)}${stepHtml}<button type="button" class="secondary" id="copy-snap-preview">Copy commands</button>`,
        );
        document.getElementById("copy-snap-preview")?.addEventListener("click", async () => {
          const commands = steps.map((step) => step.cmd || "").filter(Boolean).join(String.fromCharCode(10));
          await navigator.clipboard?.writeText(commands);
        });
        statusEl.textContent = blocking ? "Preview found blocking warnings; Run Create remains disabled." : "Preview succeeded; Run Create is enabled for this session.";
        render();
      } catch (error) {
        window.__lastSnapPreviewOk = false;
        statusEl.textContent = `Unable to preview _snap create: ${error.message || error}`;
        render();
      }
    }
    async function runSnapCreate() {
      if (!currentId || !window.__lastSnapPreviewOk) return;
      if (!(await persistCurrentGroupBeforeSnapOps())) return;
      const group = activeGroup();
      const card = group.storage_hint || "the resolved storage card";
      if (!window.confirm(`This will create volumes and start FlashCopy on ${card}. Continue?`)) return;
      statusEl.textContent = "Running _snap create…";
      try {
        const data = await postSnap("/api/contingency-groups/snap-create", {
          group_id: currentId,
          snap_assign_cg_enabled: document.getElementById("snap-assign-cg-enabled").checked,
          snap_assign_cg_name: document.getElementById("snap-assign-cg-name").value.trim(),
          confirm: true,
        });
        const log = Array.isArray(data.log) ? data.log : [];
        const logHtml = log.length
          ? `<ol class="step-list">${log.map((entry) => `<li><strong>${escapeHtml(entry.step || entry.kind || "Step")}</strong> — ${entry.ok ? "ok" : "failed"}<pre>${escapeHtml(entry.cmd || "")}${entry.output ? `\n${escapeHtml(entry.output)}` : ""}</pre></li>`).join("")}</ol>`
          : "<p class='hint'>No command log was returned.</p>";
        const cliText = log.map((entry) => {
          const label = entry.step || entry.kind || "Step";
          const state = entry.ok ? "ok" : "failed";
          return `[${state}] ${label}${entry.cmd ? String.fromCharCode(10) + entry.cmd : ""}${entry.output ? String.fromCharCode(10) + entry.output : ""}`;
        }).join(String.fromCharCode(10));
        fillCliPanel(cliText || "No command log was returned.");
        showSnapModal(data.ok ? "Create log" : "Create blocked or failed", `${snapWarnings(data.warnings)}${logHtml}`);
        statusEl.textContent = data.ok ? "Create completed; see the log for details." : "Create did not complete; see the log and warnings.";
      } catch (error) { statusEl.textContent = `Unable to run _snap create: ${error.message || error}`; }
    }
    async function syncFromArray() {
      if (!currentId) { statusEl.textContent = "Select a group to sync."; return; }
      if (!persisted) { statusEl.textContent = "Unlock LaunchPad before syncing from the array."; return; }
      const group = activeGroup();
      const cardName = window.prompt(
        "Storage card name (required):",
        (group.storage_hint || group.name || "").trim()
      );
      if (cardName === null) return;
      if (!cardName.trim()) { statusEl.textContent = "Card name is required for Sync from array."; return; }
      statusEl.textContent = "Syncing Consistency Group via SSH…";
      try {
        const response = await fetch("/api/contingency-groups/sync-inventory", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ group_id: currentId, card_name: cardName.trim() }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
        groups = Array.isArray(data.groups) ? data.groups : groups;
        saveLocal();
        render();
        const p = data.pulled || {};
        statusEl.textContent =
          `Synced hosts=${p.hosts||0} volumes=${p.volumes||0} maps=${p.maps||0}` +
          ` skipped_snaps=${p.skipped_snaps||0} live_snaps=${p.live_snaps||0}. CG updated.`;
      } catch (error) {
        statusEl.textContent = `Sync from array failed: ${error.message || error}`;
      }
    }
    async function loadGroups() {
      const localGroups = loadLocal();
      groups = localGroups;
      currentId = groups[0] ? String(groups[0].id) : "";
      render();
      statusEl.textContent = "Loading groups…";
      try {
        const response = await fetch("/api/contingency-groups");
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        persisted = Boolean(data.persisted);
        const remote = Array.isArray(data.groups) ? data.groups : [];
        if (remote.length) {
          const merged = new Map(remote.map((group) => [String(group.id || ""), group]));
          localGroups.filter((group) => group && group.id).forEach((group) => {
            merged.set(String(group.id), group);
          });
          groups = Array.from(merged.values());
        }
        if (persisted && localGroups.length) {
          await fetch("/api/contingency-groups", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ groups }) });
        }
        saveLocal();
        currentId = groups.some((group) => group.id === currentId) ? currentId : (groups[0] ? String(groups[0].id) : "");
        statusEl.textContent = persisted ? "Loaded from LaunchPad." : "Saved in this browser only — unlock LaunchPad to persist.";
      } catch (_error) {
        persisted = false;
        statusEl.textContent = groups.length ? "Loaded from this browser only." : "Create a group; it will save locally until LaunchPad is unlocked.";
      }
      render();
    }
    picker.addEventListener("change", () => { currentId = picker.value; wizardStep = 1; showWizardErrors([]); window.__lastSnapPreviewOk = false; clearCliPanel(); render(); });
    document.getElementById("new-group-btn").addEventListener("click", () => { groups.push(emptyGroup()); currentId = ""; wizardStep = 1; showWizardErrors([]); window.__lastSnapPreviewOk = false; clearCliPanel(); render(); });
    document.getElementById("cg-search-btn").addEventListener("click", runCgSearch);
    document.getElementById("cg-search").addEventListener("keydown", (event) => {
      if (event.key === "Enter") runCgSearch();
    });
    document.getElementById("add-host-btn").addEventListener("click", () => addRow("hosts"));
    document.getElementById("add-volume-btn").addEventListener("click", () => addRow("volumes"));
    document.getElementById("add-map-btn").addEventListener("click", () => addRow("maps"));
    document.getElementById("add-source-volume-btn").addEventListener("click", () => addRow("volumes"));
    [hostsBody, volumesBody, mapsBody].forEach((body) => {
      body.addEventListener("input", setFieldValue);
      body.addEventListener("click", (event) => {
        const button = event.target.closest("[data-remove-kind]");
        if (!button) return;
        const group = activeGroup();
        group[button.dataset.removeKind].splice(Number(button.dataset.index), 1);
        render();
      });
    });
    [wizardSourceVolumesBody, wizardSnapPairsBody].forEach((body) => {
      body.addEventListener("input", (event) => {
        const input = event.target;
        const index = Number(input.dataset.wizardVolumeIndex);
        const key = input.dataset.key;
        const volume = (activeGroup().volumes || [])[index];
        if (!Number.isInteger(index) || !key || !volume) return;
        volume[key] = input.value;
      });
    });
    wizardSourceVolumesBody.addEventListener("click", (event) => {
      const button = event.target.closest("[data-remove-source-index]");
      if (!button) return;
      activeGroup().volumes.splice(Number(button.dataset.removeSourceIndex), 1);
      render();
    });
    document.getElementById("save-btn").addEventListener("click", () => persistGroup(false));
    document.getElementById("save-new-btn").addEventListener("click", () => persistGroup(true));
    document.getElementById("delete-btn").addEventListener("click", deleteGroup);
    document.getElementById("generate-snaps-btn").addEventListener("click", generateSnapRows);
    document.getElementById("snap-preview-btn").addEventListener("click", previewSnaps);
    document.getElementById("snap-create-btn").addEventListener("click", runSnapCreate);
    document.getElementById("snap-assign-cg-enabled").addEventListener("change", (event) => {
      document.getElementById("snap-assign-cg-name").disabled = !event.target.checked;
      const group = activeGroup();
      group.snap_assign_cg_enabled = event.target.checked;
      group.snap_assign_cg_name = document.getElementById("snap-assign-cg-name").value.trim();
    });
    document.getElementById("snap-assign-cg-name").addEventListener("input", (event) => {
      activeGroup().snap_assign_cg_name = event.target.value.trim();
    });
    document.getElementById("snap-modal-close").addEventListener("click", closeSnapModal);
    snapModalBackdrop.addEventListener("click", (event) => { if (event.target === snapModalBackdrop) closeSnapModal(); });
    wizardBackBtn.addEventListener("click", () => {
      wizardStep = Math.max(1, wizardStep - 1);
      showWizardErrors([]);
      render();
    });
    wizardNextBtn.addEventListener("click", async () => {
      const group = activeGroup();
      readSummary(group);
      const warnings = validateWizardStep(group, wizardStep);
      showWizardErrors(warnings);
      if (warnings.length) return;
      if (wizardStep === 1 && !(await generateSnapRows())) return;
      wizardStep = Math.min(3, wizardStep + 1);
      render();
    });
    advancedToggleBtn.addEventListener("click", () => {
      advancedOpen = !advancedOpen;
      render();
    });
    document.getElementById("export-btn").addEventListener("click", () => {
      if (!currentId) { statusEl.textContent = "Select a group to export."; return; }
      window.location.assign(`/api/contingency-groups-export?id=${encodeURIComponent(currentId)}`);
    });
    document.getElementById("export-all-btn").addEventListener("click", () => {
      window.location.assign("/api/contingency-groups-export");
    });
    document.getElementById("fc-wwpn-btn").addEventListener("click", () => {
      window.location.assign("/fc-wwpn");
    });
    document.getElementById("sync-array-btn").addEventListener("click", syncFromArray);
    loadGroups();
  </script>
</body>
</html>
"""
