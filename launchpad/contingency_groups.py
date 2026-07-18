"""Editable contingency host, volume, and map reference library page."""

CONTINGENCY_GROUPS_PATH = "/contingency-groups"

CONTINGENCY_GROUPS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Contingency Groups</title>
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
    select, input, textarea { width:100%; color:var(--text); background:#0f141d; border:1px solid var(--border); border-radius:8px; padding:8px 9px; font:inherit; }
    select { width:auto; min-width:240px; }
    input:focus, textarea:focus, select:focus { outline:none; border-color:var(--accent); }
    textarea { min-height:74px; resize:vertical; }
    .summary { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }
    label { display:flex; flex-direction:column; gap:6px; color:var(--muted); font-size:.85rem; font-weight:600; }
    .notes { grid-column:1 / -1; }
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
    .modal { width:min(900px,100%); max-height:85vh; overflow:auto; padding:20px; border:1px solid var(--border); border-radius:14px; background:var(--panel); box-shadow:0 20px 70px rgba(0,0,0,.45); }
    .modal-head { display:flex; align-items:center; justify-content:space-between; gap:12px; }
    .modal h2 { margin-bottom:8px; }
    .modal pre { margin:0; padding:12px; overflow:auto; border:1px solid var(--border); border-radius:8px; background:#0b0f14; color:#d8e3f2; white-space:pre-wrap; }
    .step-list { margin:8px 0 16px; padding-left:24px; }
    .skipped { color:var(--muted); text-decoration:line-through; }
    .warning { margin:8px 0; padding:9px 10px; border-left:3px solid var(--danger); background:#32151a; color:#fecaca; }
    .footer { margin:20px 0 0; font-size:.85rem; }
    @media (max-width:720px) { .summary { grid-template-columns:1fr; } select { width:100%; } .notes { grid-column:auto; } }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <h1>Contingency Groups</h1>
      <p class="lede">Maintain a planning reference for contingency hosts, volumes, and mappings. By default these entries are planning-only; Run Create (after Preview) can create _snap volumes and start FlashCopy on the linked array.</p>
      <div class="picker">
        <label for="group-picker">Group
          <select id="group-picker" aria-label="Contingency group"></select>
        </label>
        <button type="button" class="secondary" id="new-group-btn">New group</button>
        <span class="status" id="status" aria-live="polite"></span>
      </div>
      <div class="actions">
        <button type="button" id="save-btn">Save</button>
        <button type="button" id="save-new-btn" class="secondary">Save as new</button>
        <button type="button" id="delete-btn" class="danger">Delete</button>
        <button type="button" id="export-btn" class="secondary">Export Excel</button>
        <button type="button" id="export-all-btn" class="secondary">Export All Excel</button>
        <button type="button" id="fc-wwpn-btn" class="secondary">Open in FC WWPN</button>
        <button type="button" id="generate-snaps-btn" class="secondary">Generate _snap rows</button>
        <button type="button" id="snap-preview-btn" class="secondary">Preview / Dry-run</button>
        <button type="button" id="snap-create-btn" class="danger">Run Create</button>
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
    <p class="footer">LaunchPad Contingency Groups v{{APP_VERSION}} · _snap creation is operator-initiated and only runs after confirmation.</p>
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
    let groups = [];
    let currentId = "";
    let persisted = false;
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
      return { id: "", name: "", location: "", storage_hint: "", notes: "", hosts: [], volumes: [], maps: [] };
    }
    function activeGroup() {
      return groups.find((group) => String(group.id) === currentId) || emptyGroup();
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
    function render() {
      const group = activeGroup();
      document.getElementById("group-name").value = group.name || "";
      document.getElementById("group-location").value = group.location || "";
      document.getElementById("group-storage-hint").value = group.storage_hint || "";
      document.getElementById("group-notes").value = group.notes || "";
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
      if (!window.confirm("Delete this contingency group?")) return;
      groups = groups.filter((group) => group.id !== deletingId);
      currentId = groups[0] ? groups[0].id : "";
      saveLocal();
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
    function formatResolvedCard(card, fallbackHint) {
      if (card && (card.name || card.host)) {
        const name = card.name || fallbackHint || "Resolved card";
        const host = card.host ? ` (${card.host})` : "";
        return `${name}${host}`;
      }
      return fallbackHint || "Not specified";
    }
    async function generateSnapRows() {
      if (!currentId) return;
      if (!(await persistCurrentGroupBeforeSnapOps())) return;
      statusEl.textContent = "Generating _snap rows…";
      try {
        const data = await postSnap("/api/contingency-groups/generate-snaps", { group_id: currentId });
        if (!data.ok || !data.group) {
          statusEl.textContent = (data.warnings || [data.error || "Unable to generate _snap rows."]).join(" ");
          return;
        }
        const index = groups.findIndex((group) => String(group.id) === currentId);
        if (index >= 0) groups[index] = data.group;
        saveLocal();
        window.__lastSnapPreviewOk = false;
        statusEl.textContent = "Generated _snap rows and saved in LaunchPad.";
        render();
      } catch (error) { statusEl.textContent = `Unable to generate _snap rows: ${error.message || error}`; }
    }
    async function previewSnaps() {
      if (!currentId) return;
      if (!(await persistCurrentGroupBeforeSnapOps())) return;
      statusEl.textContent = "Preparing _snap preview…";
      try {
        const data = await postSnap("/api/contingency-groups/snap-preview", { group_id: currentId });
        const warnings = Array.isArray(data.warnings) ? data.warnings : [];
        const blocking = !data.ok || warnings.length > 0;
        window.__lastSnapPreviewOk = !blocking;
        const group = activeGroup();
        const steps = Array.isArray(data.steps) ? data.steps : [];
        const stepHtml = steps.length
          ? `<ol class="step-list">${steps.map((step) => `<li class="${step.skip ? "skipped" : ""}"><strong>${escapeHtml(step.purpose || step.kind || "Step")}</strong>${step.skip ? ` — skipped: ${escapeHtml(step.reason || "already exists")}` : ""}<pre>${escapeHtml(step.cmd || "")}</pre></li>`).join("")}</ol>`
          : "<p class='hint'>No create steps were returned.</p>";
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
        const data = await postSnap("/api/contingency-groups/snap-create", { group_id: currentId, confirm: true });
        const log = Array.isArray(data.log) ? data.log : [];
        const logHtml = log.length
          ? `<ol class="step-list">${log.map((entry) => `<li><strong>${escapeHtml(entry.step || entry.kind || "Step")}</strong> — ${entry.ok ? "ok" : "failed"}<pre>${escapeHtml(entry.cmd || "")}${entry.output ? `\n${escapeHtml(entry.output)}` : ""}</pre></li>`).join("")}</ol>`
          : "<p class='hint'>No command log was returned.</p>";
        showSnapModal(data.ok ? "Create log" : "Create blocked or failed", `${snapWarnings(data.warnings)}${logHtml}`);
        statusEl.textContent = data.ok ? "Create completed; see the log for details." : "Create did not complete; see the log and warnings.";
      } catch (error) { statusEl.textContent = `Unable to run _snap create: ${error.message || error}`; }
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
    picker.addEventListener("change", () => { currentId = picker.value; window.__lastSnapPreviewOk = false; render(); });
    document.getElementById("new-group-btn").addEventListener("click", () => { groups.push(emptyGroup()); currentId = ""; window.__lastSnapPreviewOk = false; render(); });
    document.getElementById("add-host-btn").addEventListener("click", () => addRow("hosts"));
    document.getElementById("add-volume-btn").addEventListener("click", () => addRow("volumes"));
    document.getElementById("add-map-btn").addEventListener("click", () => addRow("maps"));
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
    document.getElementById("save-btn").addEventListener("click", () => persistGroup(false));
    document.getElementById("save-new-btn").addEventListener("click", () => persistGroup(true));
    document.getElementById("delete-btn").addEventListener("click", deleteGroup);
    document.getElementById("generate-snaps-btn").addEventListener("click", generateSnapRows);
    document.getElementById("snap-preview-btn").addEventListener("click", previewSnaps);
    document.getElementById("snap-create-btn").addEventListener("click", runSnapCreate);
    document.getElementById("snap-modal-close").addEventListener("click", closeSnapModal);
    snapModalBackdrop.addEventListener("click", (event) => { if (event.target === snapModalBackdrop) closeSnapModal(); });
    document.getElementById("export-btn").addEventListener("click", () => {
      if (!currentId) { statusEl.textContent = "Select a group to export."; return; }
      window.location.assign(`/api/contingency-groups-export?id=${encodeURIComponent(currentId)}`);
    });
    document.getElementById("export-all-btn").addEventListener("click", () => {
      window.location.assign("/api/contingency-groups-export");
    });
    document.getElementById("fc-wwpn-btn").addEventListener("click", () => {
      if (currentId) window.location.assign(`/fc-wwpn?group=${encodeURIComponent(currentId)}`);
    });
    loadGroups();
  </script>
</body>
</html>
"""
