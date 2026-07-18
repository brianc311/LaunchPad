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
    .footer { margin:20px 0 0; font-size:.85rem; }
    @media (max-width:720px) { .summary { grid-template-columns:1fr; } select { width:100%; } .notes { grid-column:auto; } }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <h1>Contingency Groups</h1>
      <p class="lede">Maintain a planning reference for contingency hosts, volumes, and mappings. These entries are never applied to a storage array.</p>
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
    <p class="footer">LaunchPad Contingency Groups v{{APP_VERSION}} · Reference library only — LaunchPad does not modify the array.</p>
  </main>
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
      body.innerHTML = items.map((item, index) => `<tr>${columns.map((column) => {
        const value = column.key === "wwpns" ? (item.wwpns || []).join(String.fromCharCode(10)) : item[column.key] || "";
        const control = column.multiline
          ? `<textarea data-kind="${kind}" data-index="${index}" data-key="${column.key}" placeholder="${column.placeholder || ""}">${escapeHtml(value)}</textarea>`
          : `<input data-kind="${kind}" data-index="${index}" data-key="${column.key}" type="${column.type || "text"}" value="${escapeAttr(value)}">`;
        return `<td>${control}</td>`;
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
        volumes: { name: "", capacity: "", pool: "", uid: "", protocol: "SCSI" },
        maps: { volume: "", host: "", scsi_id: "" },
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
    picker.addEventListener("change", () => { currentId = picker.value; render(); });
    document.getElementById("new-group-btn").addEventListener("click", () => { groups.push(emptyGroup()); currentId = ""; render(); });
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
