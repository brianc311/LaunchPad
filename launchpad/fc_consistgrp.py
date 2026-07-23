"""FlashCopy Consistency Groups page: array card picker + live CG/map management."""

FC_CONSISTGRP_PATH = "/fc-consistgrp"

FC_CONSISTGRP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad FlashCopy Consistency Groups</title>
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
    .actions, .picker, .section-head { display:flex; flex-wrap:wrap; align-items:center; gap:10px; }
    .actions { margin-top:16px; }
    .picker { margin-top:16px; }
    .section-head { justify-content:space-between; margin-bottom:12px; }
    button, .btn { min-height:34px; padding:0 14px; border:0; border-radius:10px; background:var(--accent); color:#111; font:inherit; font-weight:600; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; justify-content:center; }
    button.secondary, .btn.secondary { color:var(--text); background:#0f141d; border:1px solid var(--border); }
    button.danger { color:#fff; background:#b91c1c; }
    button:disabled { cursor:not-allowed; opacity:.6; }
    select, input, textarea { color:var(--text); background:#0f141d; border:1px solid var(--border); border-radius:8px; padding:6px 9px; font:inherit; }
    select { min-width:260px; }
    input:focus, textarea:focus, select:focus { outline:none; border-color:var(--accent); }
    label { display:flex; flex-direction:column; gap:6px; color:var(--muted); font-size:.85rem; font-weight:600; }
    label.inline { flex-direction:row; align-items:center; gap:8px; }
    .table-wrap { overflow-x:auto; }
    table { width:100%; min-width:600px; border-collapse:collapse; }
    th, td { padding:7px; text-align:left; vertical-align:top; border:1px solid var(--border); }
    th { color:var(--muted); background:#0f141d; font-size:.78rem; text-transform:uppercase; letter-spacing:.04em; }
    tr.selected-row td { background:rgba(255,107,0,.14); }
    .empty { padding:14px; border:1px dashed var(--border); border-radius:10px; color:var(--muted); }
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
    @media (max-width:720px) { select { width:100%; } }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <h1>FlashCopy Consistency Groups</h1>
      <p class="lede">View and manage array-level FlashCopy Consistency Groups (create, assign, remove, start, delete) with Preview &rarr; Confirm &rarr; Run safety.</p>
      <div class="picker">
        <label for="card-select">Array
          <select id="card-select" aria-label="Array"><option value="">Loading arrays&hellip;</option></select>
        </label>
        <button type="button" class="secondary" id="refresh-btn">Refresh</button>
        <span class="status" id="status" aria-live="polite"></span>
      </div>
      <div class="actions">
        <a class="btn secondary" href="/">Health Dashboard</a>
        <a class="btn secondary" href="/contingency-groups">Contingency Groups</a>
      </div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Consistency Groups</h2></div>
      <p class="hint" id="selected-group-hint">No group selected.</p>
      <div class="table-wrap"><table><thead><tr><th></th><th>Name</th><th>Status</th><th>Maps</th></tr></thead><tbody id="groups-body"></tbody></table></div>
      <div class="actions">
        <button type="button" id="start-group-btn">Start CG</button>
        <button type="button" class="danger" id="delete-group-btn">Delete CG</button>
      </div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Create consistency group</h2></div>
      <div class="actions">
        <label style="flex:1;min-width:220px;">Name <input id="create-group-name" type="text" placeholder="e.g. AWD1_AS400_CG"></label>
        <button type="button" id="create-group-btn">Create CG</button>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <h2>Member maps</h2>
        <button type="button" class="danger" id="remove-maps-btn">Remove from CG</button>
      </div>
      <p class="hint" id="member-maps-hint">Select a consistency group above to view its member maps.</p>
      <div class="table-wrap"><table><thead><tr><th></th><th>Map</th><th>Source</th><th>Target</th><th>Status</th><th>Progress</th></tr></thead><tbody id="member-maps-body"></tbody></table></div>
    </section>

    <section class="section">
      <div class="section-head">
        <h2>Stand-alone maps</h2>
        <button type="button" id="assign-maps-btn">Assign to selected CG</button>
      </div>
      <p class="hint">FlashCopy maps not currently in a consistency group. Select one or more, then assign to the CG selected above.</p>
      <div class="table-wrap"><table><thead><tr><th></th><th>Map</th><th>Source</th><th>Target</th><th>Status</th></tr></thead><tbody id="standalone-maps-body"></tbody></table></div>
    </section>

    <p class="footer">LaunchPad FlashCopy Consistency Groups v{{APP_VERSION}} &middot; mutations run only after Preview &rarr; Run confirmation.</p>
  </main>
  <div id="cg-modal-backdrop" class="modal-backdrop" hidden>
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="cg-modal-title">
      <div class="modal-head"><h2 id="cg-modal-title">Preview</h2><button type="button" class="secondary" id="cg-modal-close">Close</button></div>
      <div id="cg-modal-content"></div>
    </section>
  </div>
  <script>
    const cardSelect = document.getElementById("card-select");
    const refreshBtn = document.getElementById("refresh-btn");
    const statusEl = document.getElementById("status");
    const groupsBody = document.getElementById("groups-body");
    const selectedGroupHint = document.getElementById("selected-group-hint");
    const memberMapsBody = document.getElementById("member-maps-body");
    const memberMapsHint = document.getElementById("member-maps-hint");
    const standAloneMapsBody = document.getElementById("standalone-maps-body");
    const createGroupNameInput = document.getElementById("create-group-name");
    const createGroupBtn = document.getElementById("create-group-btn");
    const assignMapsBtn = document.getElementById("assign-maps-btn");
    const removeMapsBtn = document.getElementById("remove-maps-btn");
    const startGroupBtn = document.getElementById("start-group-btn");
    const deleteGroupBtn = document.getElementById("delete-group-btn");
    const modalBackdrop = document.getElementById("cg-modal-backdrop");
    const modalTitle = document.getElementById("cg-modal-title");
    const modalContent = document.getElementById("cg-modal-content");
    const modalCloseBtn = document.getElementById("cg-modal-close");

    let inventory = { groups: [], maps: [], stand_alone: [], card: null };
    let selectedGroupName = null;
    const selectedMemberMaps = new Set();
    const selectedStandAloneMaps = new Set();
    let pending = null;

    function escapeHtml(value) {
      return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
    }
    function escapeAttr(value) { return escapeHtml(value); }

    function currentCardId() {
      const value = cardSelect.value;
      return value ? Number(value) : null;
    }

    function closeModal() { modalBackdrop.hidden = true; }
    modalCloseBtn.addEventListener("click", closeModal);
    modalBackdrop.addEventListener("click", (event) => { if (event.target === modalBackdrop) closeModal(); });

    function warningsHtml(warnings) {
      return (warnings || []).map((warning) => `<p class="warning">${escapeHtml(warning)}</p>`).join("");
    }
    function stepListHtml(steps) {
      if (!steps || !steps.length) return "<p class='hint'>No steps were returned.</p>";
      return `<ol class="step-list">${steps.map((step) => `<li class="${step.skip ? "skipped" : ""}"><strong>${escapeHtml(step.purpose || step.kind || "Step")}</strong>${step.skip ? ` &mdash; skipped: ${escapeHtml(step.reason || "already satisfied")}` : ""}<pre>${escapeHtml(step.cmd || "")}</pre></li>`).join("")}</ol>`;
    }
    function logListHtml(log) {
      if (!log || !log.length) return "<p class='hint'>No log entries were returned.</p>";
      return `<ol class="step-list">${log.map((entry) => {
        const state = entry.skipped ? "skipped" : (entry.ok ? "ok" : "failed");
        const detail = [entry.output, entry.error].filter(Boolean).join(String.fromCharCode(10));
        return `<li class="${entry.skipped ? "skipped" : ""}"><strong>${escapeHtml(entry.purpose || entry.kind || "Step")}</strong> &mdash; ${state}<pre>${escapeHtml(entry.cmd || "")}${detail ? String.fromCharCode(10) + escapeHtml(detail) : ""}</pre></li>`;
      }).join("")}</ol>`;
    }

    function showModal(title, bodyHtml, runEnabled) {
      modalTitle.textContent = title;
      modalContent.innerHTML = `${bodyHtml}<div class="actions" style="margin-top:14px;">
        <button type="button" id="cg-modal-run" ${runEnabled ? "" : "disabled"}>Run</button>
        <button type="button" class="secondary" id="cg-modal-cancel">Cancel</button>
      </div>`;
      modalBackdrop.hidden = false;
      document.getElementById("cg-modal-run")?.addEventListener("click", runPending);
      document.getElementById("cg-modal-cancel")?.addEventListener("click", closeModal);
    }

    function showResultModal(title, bodyHtml) {
      modalTitle.textContent = title;
      modalContent.innerHTML = `${bodyHtml}<div class="actions" style="margin-top:14px;">
        <button type="button" class="secondary" id="cg-modal-done">Close</button>
      </div>`;
      document.getElementById("cg-modal-done")?.addEventListener("click", closeModal);
    }

    async function postJson(path, payload) {
      const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({ ok: false, warnings: [`HTTP ${res.status}`] }));
      if (!res.ok && !data.warnings) data.warnings = [data.error || `HTTP ${res.status}`];
      return data;
    }

    async function runAction(action, payload, label) {
      const cardId = currentCardId();
      if (cardId === null) { statusEl.textContent = "Select an array first."; return; }
      statusEl.textContent = `Preparing ${label} preview\u2026`;
      try {
        const data = await postJson("/api/fc-consistgrp/preview", { card_id: cardId, action, ...payload });
        const steps = Array.isArray(data.steps) ? data.steps : [];
        const warnings = Array.isArray(data.warnings) ? data.warnings : [];
        pending = data.ok ? { action, payload, cardId, label } : null;
        showModal(label, `${warningsHtml(warnings)}${stepListHtml(steps)}`, Boolean(data.ok));
        statusEl.textContent = data.ok ? "Preview succeeded; Run is enabled." : "Preview found blocking warnings; resolve before Run.";
      } catch (err) {
        pending = null;
        statusEl.textContent = `Unable to preview ${label}: ${err}`;
      }
    }

    async function runPending() {
      if (!pending) return;
      const { action, payload, cardId, label } = pending;
      statusEl.textContent = `Running ${label}\u2026`;
      try {
        const data = await postJson("/api/fc-consistgrp/run", { card_id: cardId, action, confirm: true, ...payload });
        const log = Array.isArray(data.log) ? data.log : [];
        showResultModal(data.ok ? "Run complete" : "Run blocked or failed", `${warningsHtml(data.warnings)}${logListHtml(log)}`);
        pending = null;
        if (data.ok) {
          statusEl.textContent = "Run completed; refreshing inventory\u2026";
          selectedMemberMaps.clear();
          selectedStandAloneMaps.clear();
          await loadInventory();
        } else {
          statusEl.textContent = "Run did not complete; see the log and warnings.";
        }
      } catch (err) {
        statusEl.textContent = `Unable to run ${label}: ${err}`;
      }
    }

    function renderGroups() {
      const groups = inventory.groups || [];
      groupsBody.innerHTML = groups.length
        ? groups.map((group) => {
            const name = String(group.name || "");
            const isSelected = name === selectedGroupName;
            return `<tr class="${isSelected ? "selected-row" : ""}">
              <td><input type="radio" name="selected-group" value="${escapeAttr(name)}" ${isSelected ? "checked" : ""} aria-label="Select ${escapeAttr(name)}"></td>
              <td>${escapeHtml(name)}</td>
              <td>${escapeHtml(group.status || "")}</td>
              <td>${escapeHtml(String(group.map_count ?? ""))}</td>
            </tr>`;
          }).join("")
        : '<tr><td colspan="4" class="empty">No consistency groups found. Use Create CG below.</td></tr>';
      selectedGroupHint.textContent = selectedGroupName ? `Selected: ${selectedGroupName}` : "No group selected.";
    }

    function renderMemberMaps() {
      const maps = selectedGroupName
        ? (inventory.maps || []).filter((mapping) => String(mapping.consistgrp || "").trim() === selectedGroupName)
        : [];
      memberMapsHint.textContent = selectedGroupName
        ? `${maps.length} map(s) in ${selectedGroupName}.`
        : "Select a consistency group above to view its member maps.";
      memberMapsBody.innerHTML = maps.length
        ? maps.map((mapping) => {
            const name = String(mapping.name || "");
            const checked = selectedMemberMaps.has(name);
            return `<tr>
              <td><input type="checkbox" data-member-map="${escapeAttr(name)}" ${checked ? "checked" : ""} aria-label="Select ${escapeAttr(name)}"></td>
              <td>${escapeHtml(name)}</td>
              <td>${escapeHtml(mapping.source || "")}</td>
              <td>${escapeHtml(mapping.target || "")}</td>
              <td>${escapeHtml(mapping.status || "")}</td>
              <td>${escapeHtml(String(mapping.progress ?? ""))}</td>
            </tr>`;
          }).join("")
        : `<tr><td colspan="6" class="empty">${selectedGroupName ? "No member maps in this group." : "Select a consistency group to view member maps."}</td></tr>`;
    }

    function renderStandAlone() {
      const maps = inventory.stand_alone || [];
      standAloneMapsBody.innerHTML = maps.length
        ? maps.map((mapping) => {
            const name = String(mapping.name || "");
            const checked = selectedStandAloneMaps.has(name);
            return `<tr>
              <td><input type="checkbox" data-standalone-map="${escapeAttr(name)}" ${checked ? "checked" : ""} aria-label="Select ${escapeAttr(name)}"></td>
              <td>${escapeHtml(name)}</td>
              <td>${escapeHtml(mapping.source || "")}</td>
              <td>${escapeHtml(mapping.target || "")}</td>
              <td>${escapeHtml(mapping.status || "")}</td>
            </tr>`;
          }).join("")
        : '<tr><td colspan="5" class="empty">No stand-alone FlashCopy maps found.</td></tr>';
    }

    function updateActionState() {
      const hasCard = currentCardId() !== null;
      createGroupBtn.disabled = !hasCard;
      assignMapsBtn.disabled = !hasCard || !selectedGroupName || selectedStandAloneMaps.size === 0;
      removeMapsBtn.disabled = !hasCard || selectedMemberMaps.size === 0;
      startGroupBtn.disabled = !hasCard || !selectedGroupName;
      deleteGroupBtn.disabled = !hasCard || !selectedGroupName;
    }

    function render() {
      renderGroups();
      renderMemberMaps();
      renderStandAlone();
      updateActionState();
    }

    async function loadInventory() {
      const cardId = currentCardId();
      if (cardId === null) {
        inventory = { groups: [], maps: [], stand_alone: [], card: null };
        statusEl.textContent = "Select an array to load inventory.";
        render();
        return;
      }
      statusEl.textContent = "Loading inventory\u2026";
      try {
        const res = await fetch(`/api/fc-consistgrp/inventory?card_id=${cardId}`);
        const data = await res.json();
        if (!data.ok) {
          inventory = { groups: [], maps: [], stand_alone: [], card: data.card || null };
          statusEl.textContent = (data.warnings || []).join(" ") || "Inventory load failed.";
          render();
          return;
        }
        inventory = data;
        if (selectedGroupName && !(data.groups || []).some((group) => String(group.name || "") === selectedGroupName)) {
          selectedGroupName = null;
          selectedMemberMaps.clear();
        }
        statusEl.textContent = `Loaded ${data.groups.length} group(s), ${data.maps.length} map(s) (${data.stand_alone.length} stand-alone).`;
        render();
      } catch (err) {
        statusEl.textContent = `Unable to load inventory: ${err}`;
      }
    }

    async function loadCards() {
      statusEl.textContent = "Loading arrays\u2026";
      try {
        const res = await fetch("/api/fc-consistgrp/cards");
        const data = await res.json();
        const cards = data.cards || [];
        const preselect = new URLSearchParams(window.location.search).get("card");
        cardSelect.innerHTML = "";
        if (!cards.length) {
          cardSelect.innerHTML = '<option value="">No Health Cards registered</option>';
          statusEl.textContent = "No Health Cards registered. Unlock LaunchPad and register an SSH card.";
          render();
          return;
        }
        cardSelect.innerHTML = '<option value="">Select an array&hellip;</option>' + cards.map(
          (card) => `<option value="${card.id}">${escapeHtml(card.name)} (${escapeHtml(card.host)})</option>`
        ).join("");
        if (preselect) {
          cardSelect.value = preselect;
          if (cardSelect.value === preselect) {
            await loadInventory();
            return;
          }
        }
        statusEl.textContent = "Select an array to load inventory.";
        render();
      } catch (err) {
        statusEl.textContent = `Unable to load arrays: ${err}`;
      }
    }

    cardSelect.addEventListener("change", () => {
      selectedGroupName = null;
      selectedMemberMaps.clear();
      selectedStandAloneMaps.clear();
      loadInventory();
    });
    refreshBtn.addEventListener("click", loadInventory);

    groupsBody.addEventListener("change", (event) => {
      const input = event.target.closest("input[name='selected-group']");
      if (!input) return;
      selectedGroupName = input.value || null;
      selectedMemberMaps.clear();
      render();
    });
    memberMapsBody.addEventListener("change", (event) => {
      const input = event.target.closest("input[data-member-map]");
      if (!input) return;
      const name = input.dataset.memberMap;
      if (input.checked) selectedMemberMaps.add(name); else selectedMemberMaps.delete(name);
      updateActionState();
    });
    standAloneMapsBody.addEventListener("change", (event) => {
      const input = event.target.closest("input[data-standalone-map]");
      if (!input) return;
      const name = input.dataset.standaloneMap;
      if (input.checked) selectedStandAloneMaps.add(name); else selectedStandAloneMaps.delete(name);
      updateActionState();
    });

    createGroupBtn.addEventListener("click", () => {
      const name = createGroupNameInput.value.trim();
      if (!name) { statusEl.textContent = "Enter a name for the new consistency group."; return; }
      runAction("create_group", { name }, `Create consistency group ${name}`);
    });
    assignMapsBtn.addEventListener("click", () => {
      if (!selectedGroupName) { statusEl.textContent = "Select a consistency group first."; return; }
      const mapNames = Array.from(selectedStandAloneMaps);
      if (!mapNames.length) { statusEl.textContent = "Select at least one stand-alone map to assign."; return; }
      runAction("assign_maps", { group_name: selectedGroupName, map_names: mapNames }, `Assign maps to ${selectedGroupName}`);
    });
    removeMapsBtn.addEventListener("click", () => {
      const mapNames = Array.from(selectedMemberMaps);
      if (!mapNames.length) { statusEl.textContent = "Select at least one member map to remove."; return; }
      runAction("remove_maps", { map_names: mapNames }, "Remove maps from consistency group");
    });
    startGroupBtn.addEventListener("click", () => {
      if (!selectedGroupName) { statusEl.textContent = "Select a consistency group first."; return; }
      runAction("start_group", { group_name: selectedGroupName }, `Start ${selectedGroupName}`);
    });
    deleteGroupBtn.addEventListener("click", () => {
      if (!selectedGroupName) { statusEl.textContent = "Select a consistency group first."; return; }
      if (!window.confirm(`Preview deleting consistency group ${selectedGroupName}?`)) return;
      runAction("delete_group", { group_name: selectedGroupName }, `Delete ${selectedGroupName}`);
    });

    render();
    loadCards();
  </script>
</body>
</html>"""
