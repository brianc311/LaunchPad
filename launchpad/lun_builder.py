"""Editable LUN build planning page."""

from html import escape

from launchpad.lun_builder_data import LUN_BUILDER_PROFILES

LUN_BUILDER_PATH = "/lun-builder"

_PROFILE_OPTIONS = "".join(
    f'<option value="{escape(key)}">{escape(label)}</option>'
    for key, label in LUN_BUILDER_PROFILES
)

LUN_BUILDER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad LUN Builder</title>
  <style>
    :root { --bg:#0b0f14; --panel:#121821; --text:#e8edf5; --muted:#8b98ab; --accent:#ff6b00; --accent2:#ff8533; --border:#2a3444; --card:#151c27; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; color:var(--text); font-family:Segoe UI,Inter,Arial,sans-serif; background:radial-gradient(circle at top,#172033 0%,var(--bg) 45%); }
    .wrap { max-width:1400px; margin:0 auto; padding:28px 20px 48px; }
    .hero, .section { margin-bottom:18px; padding:20px; border:1px solid var(--border); border-radius:16px; background:var(--card); }
    .hero { background:linear-gradient(135deg,#1a2230 0%,#101722 100%); }
    h1 { margin:0 0 8px; color:var(--accent); font-size:1.85rem; }
    h2 { margin:0; color:var(--accent2); font-size:1.05rem; }
    .lede, .status, .hint, .footer { color:var(--muted); }
    .picker, .actions, .section-head { display:flex; flex-wrap:wrap; align-items:center; gap:10px; }
    .picker, .actions { margin-top:16px; }
    .section-head { justify-content:space-between; margin-bottom:12px; }
    button, .btn { min-height:34px; padding:0 14px; border:0; border-radius:10px; background:var(--accent); color:#111; font:inherit; font-weight:600; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; justify-content:center; }
    button.secondary, .btn.secondary { color:var(--text); background:#0f141d; border:1px solid var(--border); }
    button.danger { color:#fff; background:#b91c1c; }
    button:disabled { cursor:not-allowed; opacity:.55; }
    label { display:flex; flex-direction:column; gap:6px; color:var(--muted); font-size:.85rem; font-weight:600; }
    select, input, textarea { width:100%; padding:8px 9px; color:var(--text); background:#0f141d; border:1px solid var(--border); border-radius:8px; font:inherit; }
    .picker select { width:auto; min-width:240px; }
    textarea { min-height:70px; resize:vertical; }
    .summary { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }
    .notes { grid-column:1 / -1; }
    .table-wrap { overflow-x:auto; }
    table { width:100%; min-width:980px; border-collapse:collapse; }
    th, td { padding:7px; text-align:left; vertical-align:top; border:1px solid var(--border); }
    th { color:var(--muted); background:#0f141d; font-size:.76rem; text-transform:uppercase; }
    td input, td select { min-width:100px; }
    .remove { min-height:30px; padding:0 10px; color:#fecaca; background:#32151a; border:1px solid #7f1d1d; }
    .empty { padding:14px; color:var(--muted); }
    .modal-backdrop { position:fixed; inset:0; z-index:10; display:grid; place-items:center; padding:20px; background:rgba(0,0,0,.72); }
    .modal-backdrop[hidden] { display:none !important; }
    .modal { width:min(850px,100%); max-height:85vh; overflow:auto; padding:20px; border:1px solid var(--border); border-radius:14px; background:var(--panel); }
    .modal-head { display:flex; align-items:center; justify-content:space-between; gap:12px; }
    .wizard-backdrop { position:fixed; inset:0; z-index:20; display:grid; place-items:center; padding:20px; background:rgba(0,0,0,.72); }
    .wizard-backdrop[hidden] { display:none !important; }
    .wizard { width:min(560px,100%); padding:24px; border:1px solid var(--border); border-radius:16px; background:var(--panel); box-shadow:0 24px 80px rgba(0,0,0,.45); }
    .wizard-step { color:var(--accent2); font-size:.8rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
    .wizard h2 { margin-top:10px; font-size:1.35rem; }
    .wizard-copy { min-height:72px; color:var(--text); line-height:1.5; }
    .wizard-actions { display:flex; justify-content:space-between; gap:10px; margin-top:20px; }
    .footer { margin-top:20px; font-size:.85rem; }
    @media (max-width:720px) { .summary { grid-template-columns:1fr; } .notes { grid-column:auto; } .picker select { width:100%; } }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <h1>LUN Builder</h1>
      <p class="lede">Plan hosts and repeatable LUN batches, preview sanitized CLI, and run supported storage creates after confirmation.</p>
      <div class="picker">
        <label for="build-picker">Build <select id="build-picker" aria-label="LUN build"></select></label>
        <button type="button" class="secondary" id="new-btn">New</button>
        <span class="status" id="status" aria-live="polite"></span>
      </div>
      <div class="actions">
        <button type="button" id="save-btn">Save</button>
        <button type="button" class="secondary" id="save-new-btn">Save as new</button>
        <button type="button" class="danger" id="delete-btn">Delete</button>
        <button type="button" class="secondary" id="export-excel-btn">Export Excel</button>
        <button type="button" class="secondary" id="export-csv-btn">Export CSV</button>
        <label for="import-mode">Import mode <select id="import-mode"><option value="merge">Merge</option><option value="replace">Replace</option></select></label>
        <input id="import-file" type="file" accept=".xlsx,.csv,.zip" hidden>
        <button type="button" class="secondary" id="import-btn">Import</button>
        <button type="button" class="secondary" id="pull-fc-btn">Pull from FC WWPN</button>
        <button type="button" class="secondary" id="preview-btn">Preview / Dry-run</button>
        <button type="button" class="danger" id="run-btn">Run Create</button>
        <a class="btn secondary" href="/">Health Dashboard</a>
      </div>
    </section>
    <section class="section">
      <div class="summary">
        <label>Name <input id="build-name" placeholder="Build name"></label>
        <label>Location <input id="build-location" placeholder="Site location"></label>
        <label class="notes">Notes <textarea id="build-notes" placeholder="Planning notes"></textarea></label>
      </div>
    </section>
    <section class="section">
      <div class="section-head"><h2>Hosts</h2><button type="button" class="secondary" id="add-host-btn">Add host</button></div>
      <div class="table-wrap"><table><thead><tr><th>LPAR name</th><th>Slot</th><th>State</th><th>Required</th><th>Type</th><th>WWPN 1</th><th>WWPN 2</th><th>Notes</th><th></th></tr></thead><tbody id="hosts-body"></tbody></table></div>
    </section>
    <section class="section">
      <div class="section-head"><h2>LUN specs</h2><button type="button" class="secondary" id="add-lun-btn">Add LUN spec</button></div>
      <p class="hint">Each row can expand into one or more LUNs during preview.</p>
      <div class="table-wrap"><table><thead><tr><th>Purpose</th><th>Count</th><th>Size</th><th>Shared</th><th>Storage profile</th><th>Pool / CPG</th><th>Host names</th><th>SCSI / LUN ID</th><th>Card hint</th><th>Cluster</th><th></th></tr></thead><tbody id="luns-body"></tbody></table></div>
    </section>
    <p class="footer">LaunchPad LUN Builder v{{APP_VERSION}}</p>
  </main>
  <div class="modal-backdrop" id="result-modal" hidden>
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div class="modal-head"><h2 id="modal-title">LUN Builder</h2><button type="button" class="secondary" id="modal-close">Close</button></div>
      <p id="modal-content"></p>
    </section>
  </div>
  <div class="wizard-backdrop" id="first-time-wizard" hidden>
    <section class="wizard" role="dialog" aria-modal="true" aria-label="LUN Builder first-time wizard" aria-labelledby="wizard-title">
      <div class="wizard-step" id="wizard-step">Step 1 of 4</div>
      <h2 id="wizard-title">Set the site</h2>
      <p class="wizard-copy" id="wizard-copy"></p>
      <div class="wizard-actions">
        <button type="button" class="secondary" id="wizard-skip">Skip wizard</button>
        <div class="actions">
          <button type="button" class="secondary" id="wizard-back">Back</button>
          <button type="button" id="wizard-next">Next</button>
        </div>
      </div>
    </section>
  </div>
  <script>
    const STORAGE_KEY = "launchpad.lunBuilds";
    const WIZARD_STORAGE_KEY = "launchpad.lunBuilder.wizardDone";
    const PROFILE_OPTIONS = `{{PROFILE_OPTIONS}}`;
    const picker = document.getElementById("build-picker");
    const statusEl = document.getElementById("status");
    const hostsBody = document.getElementById("hosts-body");
    const lunsBody = document.getElementById("luns-body");
    const modal = document.getElementById("result-modal");
    const wizard = document.getElementById("first-time-wizard");
    const wizardSteps = [
      { title:"Set the site", copy:"Name the build and enter its site location. These fields stay attached to the same in-memory build as you continue." },
      { title:"Add hosts", copy:"Add each host, its slot and WWPN details in the Hosts table." },
      { title:"Define LUN batches", copy:"Add repeatable LUN specs, including count, size, profile, pool, and target hosts." },
      { title:"Review safely", copy:"Save, then use Preview / Dry-run to review sanitized CLI. Run Create remains gated until a valid preview succeeds." },
    ];
    let builds = [];
    let currentId = "";
    let persisted = false;
    let previewRequestId = 0;
    let wizardStep = 0;
    window.__lastLunPreviewOk = false;
    window.__lastLunHasRunnableSteps = false;

    function invalidatePreview() {
      previewRequestId += 1;
      window.__lastLunPreviewOk = false;
      window.__lastLunHasRunnableSteps = false;
    }
    function renderWizard() {
      const step = wizardSteps[wizardStep];
      document.getElementById("wizard-step").textContent = `Step ${wizardStep + 1} of ${wizardSteps.length}`;
      document.getElementById("wizard-title").textContent = step.title;
      document.getElementById("wizard-copy").textContent = step.copy;
      document.getElementById("wizard-back").disabled = wizardStep === 0;
      document.getElementById("wizard-next").textContent = wizardStep === wizardSteps.length - 1 ? "Finish" : "Next";
    }
    function finishWizard() {
      try { localStorage.setItem(WIZARD_STORAGE_KEY, "true"); } catch (_err) { /* memory-only fallback */ }
      wizard.hidden = true;
    }
    function showWizardOnFirstVisit() {
      let wizardDone = false;
      try { wizardDone = localStorage.getItem(WIZARD_STORAGE_KEY) === "true"; } catch (_err) { /* show wizard */ }
      if (!wizardDone) { wizardStep = 0; renderWizard(); wizard.hidden = false; }
    }
    function esc(value) { return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;"); }
    function emptyBuild() { return { id:"", name:"", location:"", notes:"", hosts:[], luns:[] }; }
    function activeBuild() { return builds.find((build) => String(build.id) === currentId) || emptyBuild(); }
    function loadLocal() { try { const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); return Array.isArray(value) ? value : []; } catch (_err) { return []; } }
    function saveLocal() { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(builds)); } catch (_err) { /* memory-only fallback */ } }
    function input(key, value, index, kind, type="text") { return `<input type="${type}" data-kind="${kind}" data-index="${index}" data-key="${key}" value="${esc(value)}">`; }
    function render() {
      const build = activeBuild();
      picker.innerHTML = builds.length ? builds.map((item) => `<option value="${esc(item.id)}">${esc(item.name || item.id)}</option>`).join("") : '<option value="">New build</option>';
      picker.value = currentId;
      document.getElementById("build-name").value = build.name || "";
      document.getElementById("build-location").value = build.location || "";
      document.getElementById("build-notes").value = build.notes || "";
      hostsBody.innerHTML = (build.hosts || []).length ? build.hosts.map((host, index) => `<tr>
        <td>${input("lpar_name", host.lpar_name, index, "hosts")}</td><td>${input("slot", host.slot, index, "hosts")}</td>
        <td>${input("state", host.state, index, "hosts")}</td><td><input type="checkbox" data-kind="hosts" data-index="${index}" data-key="required" ${host.required ? "checked" : ""}></td>
        <td>${input("type", host.type, index, "hosts")}</td><td>${input("wwpn1", host.wwpn1, index, "hosts")}</td>
        <td>${input("wwpn2", host.wwpn2, index, "hosts")}</td><td>${input("notes", host.notes, index, "hosts")}</td>
        <td><button type="button" class="remove" data-remove="hosts" data-index="${index}">Remove</button></td></tr>`).join("") : '<tr><td colspan="9" class="empty">No hosts yet.</td></tr>';
      lunsBody.innerHTML = (build.luns || []).length ? build.luns.map((lun, index) => `<tr>
        <td>${input("purpose", lun.purpose, index, "luns")}</td><td>${input("count", lun.count || 1, index, "luns", "number")}</td>
        <td>${input("size", lun.size, index, "luns")}</td><td><input type="checkbox" data-kind="luns" data-index="${index}" data-key="shared" ${lun.shared ? "checked" : ""}></td>
        <td><select data-kind="luns" data-index="${index}" data-key="storage_profile"><option value="">Select profile</option>${PROFILE_OPTIONS}</select></td>
        <td>${input("pool_or_cpg", lun.pool_or_cpg, index, "luns")}</td><td>${input("host_names", (lun.host_names || []).join(", "), index, "luns")}</td>
        <td>${input("scsi_or_lun_id", lun.scsi_or_lun_id, index, "luns")}</td><td>${input("card_hint", lun.card_hint, index, "luns")}</td>
        <td>${input("cluster", lun.cluster, index, "luns")}</td><td><button type="button" class="remove" data-remove="luns" data-index="${index}">Remove</button></td></tr>`).join("") : '<tr><td colspan="11" class="empty">No LUN specs yet.</td></tr>';
      (build.luns || []).forEach((lun, index) => { const select = lunsBody.querySelector(`select[data-index="${index}"]`); if (select) select.value = lun.storage_profile || ""; });
      document.getElementById("delete-btn").disabled = !currentId;
      document.getElementById("export-excel-btn").disabled = !currentId;
      document.getElementById("export-csv-btn").disabled = !currentId;
      document.getElementById("run-btn").disabled = !window.__lastLunPreviewOk || !window.__lastLunHasRunnableSteps;
    }
    function readSummary(build) {
      build.name = document.getElementById("build-name").value.trim();
      build.location = document.getElementById("build-location").value.trim();
      build.notes = document.getElementById("build-notes").value.trim();
    }
    function makeId(name) {
      const base = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "build";
      let id = base; let suffix = 2;
      while (builds.some((build) => build.id === id)) id = `${base}-${suffix++}`;
      return id;
    }
    function addRow(kind) {
      const build = activeBuild();
      build[kind].push(kind === "hosts"
        ? { lpar_name:"", slot:"", state:"", required:false, type:"", wwpn1:"", wwpn2:"", notes:"" }
        : { purpose:"", count:1, size:"", shared:false, storage_profile:"", pool_or_cpg:"", host_names:[], scsi_or_lun_id:"", card_hint:"", cluster:"" });
      invalidatePreview();
      render();
    }
    function updateField(event) {
      const target = event.target;
      const item = (activeBuild()[target.dataset.kind] || [])[Number(target.dataset.index)];
      if (!item || !target.dataset.key) return;
      const value = target.type === "checkbox" ? target.checked : target.value;
      item[target.dataset.key] = target.dataset.key === "host_names" ? String(value).split(",").map((name) => name.trim()).filter(Boolean) : value;
      invalidatePreview();
      document.getElementById("run-btn").disabled = true;
    }
    async function save(saveAsNew) {
      let build = activeBuild();
      readSummary(build);
      if (!build.name) { statusEl.textContent = "Enter a build name before saving."; return; }
      if (!build.id || saveAsNew) {
        build = JSON.parse(JSON.stringify(build));
        build.id = makeId(build.name);
        builds.push(build);
        currentId = build.id;
        invalidatePreview();
      }
      build.updated_at = new Date().toISOString();
      saveLocal(); render();
      if (!persisted) { statusEl.textContent = "Saved in this browser only — unlock LaunchPad to persist."; return; }
      try {
        const response = await fetch("/api/lun-builds", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ build }) });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        builds = (await response.json()).builds; saveLocal(); render(); statusEl.textContent = "Saved.";
      } catch (error) { persisted = false; statusEl.textContent = `Saved locally only: ${error.message || error}`; }
    }
    async function removeBuild() {
      if (!currentId || !window.confirm("Delete this LUN build?")) return;
      const deleting = currentId;
      builds = builds.filter((build) => build.id !== deleting);
      currentId = builds[0]?.id || "";
      invalidatePreview();
      saveLocal(); render();
      if (!persisted) { statusEl.textContent = "Deleted from this browser only."; return; }
      try {
        const response = await fetch("/api/lun-builds", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ delete_id:deleting }) });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        builds = (await response.json()).builds; saveLocal(); render(); statusEl.textContent = "Deleted.";
      } catch (error) { statusEl.textContent = `Deleted locally only: ${error.message || error}`; }
    }
    function showModal(title, message) { document.getElementById("modal-title").textContent = title; document.getElementById("modal-content").textContent = message; modal.hidden = false; }
    async function persistCurrentBuildBeforeOps() {
      if (!currentId) { statusEl.textContent = "Save the build before previewing or creating."; return false; }
      if (!persisted) { statusEl.textContent = "Unlock LaunchPad before previewing or creating."; return false; }
      const build = activeBuild();
      readSummary(build);
      build.updated_at = new Date().toISOString();
      try {
        const response = await fetch("/api/lun-builds", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ build }) });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
        builds = data.builds; saveLocal(); render();
        return true;
      } catch (error) {
        statusEl.textContent = `Save failed: ${error.message || error}`;
        return false;
      }
    }
    async function postLunOperation(path, payload) {
      const response = await fetch(path, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload) });
      const data = await response.json();
      if (!response.ok && !Array.isArray(data.warnings)) throw new Error(data.error || `HTTP ${response.status}`);
      return data;
    }
    function formatLunResult(data, includeOutput=false) {
      const warnings = Array.isArray(data.warnings) ? data.warnings : [];
      const entries = includeOutput ? (Array.isArray(data.log) ? data.log : []) : (Array.isArray(data.steps) ? data.steps : []);
      const lines = [];
      if (data.plan_only) lines.push("Plan-only build: CLI is shown for review; Run Create remains disabled.");
      warnings.forEach((warning) => lines.push(`WARNING: ${warning}`));
      entries.forEach((entry) => {
        const state = entry.status || (entry.skip ? "skipped" : entry.live === false ? "plan-only" : "ready");
        lines.push(`[${state}] ${entry.label || entry.kind || "Step"}`);
        if (entry.cmd) lines.push(entry.cmd);
        if (includeOutput && entry.output) lines.push(entry.output);
        if (includeOutput && entry.error) lines.push(`ERROR: ${entry.error}`);
      });
      return lines.join("\\n") || "No steps were returned.";
    }
    async function previewLuns() {
      if (!(await persistCurrentBuildBeforeOps())) return;
      const requestId = ++previewRequestId;
      window.__lastLunPreviewOk = false;
      window.__lastLunHasRunnableSteps = false;
      render();
      statusEl.textContent = "Preparing LUN preview...";
      try {
        const data = await postLunOperation("/api/lun-builds/preview", { build_id:currentId });
        if (requestId !== previewRequestId) return;
        window.__lastLunPreviewOk = Boolean(data.ok);
        window.__lastLunHasRunnableSteps = Boolean(data.runnable);
        render();
        showModal("Preview / Dry-run", formatLunResult(data));
        statusEl.textContent = data.ok
          ? (data.plan_only ? "Plan-only preview succeeded; Run Create remains disabled." : "Preview succeeded; Run Create is enabled for this session.")
          : "Preview found blocking warnings; Run Create remains disabled.";
      } catch (error) {
        if (requestId !== previewRequestId) return;
        invalidatePreview(); render();
        statusEl.textContent = `Preview failed: ${error.message || error}`;
      }
    }
    async function runLunCreate() {
      if (!window.__lastLunPreviewOk || !window.__lastLunHasRunnableSteps) return;
      if (!window.confirm("This will create and map LUNs on the resolved storage cards. Existing hosts must already exist. Continue?")) return;
      statusEl.textContent = "Running LUN create...";
      try {
        const data = await postLunOperation("/api/lun-builds/create", { build_id:currentId, confirm:true });
        showModal("Run Create", formatLunResult(data, true));
        statusEl.textContent = data.ok ? "LUN create completed." : "LUN create stopped after a failure.";
      } catch (error) {
        statusEl.textContent = `LUN create failed: ${error.message || error}`;
      } finally {
        invalidatePreview(); render();
      }
    }
    function exportBuild(format) {
      if (!currentId) { statusEl.textContent = "Save the build before exporting."; return; }
      const suffix = format === "xlsx" ? "&format=xlsx" : "&format=csv";
      window.location.assign(`/api/lun-builds-export?id=${encodeURIComponent(currentId)}${suffix}`);
    }
    function importMessage(prefix, warnings) {
      const items = Array.isArray(warnings) ? warnings.filter(Boolean) : [];
      statusEl.textContent = items.length ? `${prefix} ${items.length} warning(s).` : prefix;
      if (items.length) showModal("Import warnings", items.join("\\n"));
    }
    async function importBuild(file) {
      if (!currentId) { statusEl.textContent = "Save the build before importing."; return; }
      if (!persisted) { statusEl.textContent = "Unlock LaunchPad before importing."; return; }
      const mode = document.getElementById("import-mode").value;
      if (mode === "replace" && !window.confirm("Replace all hosts and LUN specs in this build?")) return;
      statusEl.textContent = `Importing ${file.name}...`;
      try {
        const contentBase64 = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result || "").split(",", 2)[1] || "");
          reader.onerror = () => reject(reader.error || new Error("Could not read file."));
          reader.readAsDataURL(file);
        });
        const response = await fetch("/api/lun-builds/import", {
          method:"POST",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify({ filename:file.name, content_base64:contentBase64, mode, build_id:currentId }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
        builds = data.builds; saveLocal(); invalidatePreview(); render();
        importMessage("Import complete. Review and save any further edits; no create was run.", data.warnings);
      } catch (error) {
        statusEl.textContent = `Import failed: ${error.message || error}`;
      } finally {
        document.getElementById("import-file").value = "";
      }
    }
    async function pullFcHosts() {
      if (!currentId) { statusEl.textContent = "Save the build before pulling FC hosts."; return; }
      if (!persisted) { statusEl.textContent = "Unlock LaunchPad before pulling FC hosts."; return; }
      const cardName = window.prompt("Storage card name (leave blank for all FC WWPN cards):", "");
      if (cardName === null) return;
      statusEl.textContent = "Pulling hosts from FC WWPN...";
      try {
        const response = await fetch("/api/lun-builds/pull-fc", {
          method:"POST",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify({ build_id:currentId, card_name:cardName.trim() || undefined }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
        builds = data.builds; saveLocal(); invalidatePreview(); render();
        importMessage(`Pulled ${data.pulled || 0} FC host(s). No create was run.`, data.warnings);
      } catch (error) {
        statusEl.textContent = `FC WWPN pull failed: ${error.message || error}`;
      }
    }
    async function load() {
      const local = loadLocal(); builds = local; currentId = builds[0]?.id || ""; render();
      try {
        const response = await fetch("/api/lun-builds");
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json(); persisted = Boolean(data.persisted);
        if (Array.isArray(data.builds) && data.builds.length) builds = data.builds;
        currentId = builds[0]?.id || ""; saveLocal();
        statusEl.textContent = persisted ? "Loaded from LaunchPad." : "Browser-only until LaunchPad is unlocked.";
      } catch (_error) { persisted = false; statusEl.textContent = "Browser-only until LaunchPad is unlocked."; }
      render();
    }
    picker.addEventListener("change", () => { currentId = picker.value; invalidatePreview(); render(); });
    document.getElementById("new-btn").addEventListener("click", () => { builds.push(emptyBuild()); currentId = ""; invalidatePreview(); render(); });
    document.getElementById("save-btn").addEventListener("click", () => save(false));
    document.getElementById("save-new-btn").addEventListener("click", () => save(true));
    document.getElementById("delete-btn").addEventListener("click", removeBuild);
    document.getElementById("export-excel-btn").addEventListener("click", () => exportBuild("xlsx"));
    document.getElementById("export-csv-btn").addEventListener("click", () => exportBuild("csv"));
    document.getElementById("import-btn").addEventListener("click", () => document.getElementById("import-file").click());
    document.getElementById("import-file").addEventListener("change", (event) => { const file = event.target.files?.[0]; if (file) importBuild(file); });
    document.getElementById("pull-fc-btn").addEventListener("click", pullFcHosts);
    document.getElementById("add-host-btn").addEventListener("click", () => addRow("hosts"));
    document.getElementById("add-lun-btn").addEventListener("click", () => addRow("luns"));
    [hostsBody, lunsBody].forEach((body) => {
      body.addEventListener("input", updateField); body.addEventListener("change", updateField);
      body.addEventListener("click", (event) => { const button = event.target.closest("[data-remove]"); if (!button) return; activeBuild()[button.dataset.remove].splice(Number(button.dataset.index), 1); invalidatePreview(); render(); });
    });
    ["build-name", "build-location", "build-notes"].forEach((id) => document.getElementById(id).addEventListener("input", () => { invalidatePreview(); document.getElementById("run-btn").disabled = true; }));
    document.getElementById("preview-btn").addEventListener("click", previewLuns);
    document.getElementById("run-btn").addEventListener("click", runLunCreate);
    document.getElementById("modal-close").addEventListener("click", () => { modal.hidden = true; });
    modal.addEventListener("click", (event) => { if (event.target === modal) modal.hidden = true; });
    document.getElementById("wizard-skip").addEventListener("click", finishWizard);
    document.getElementById("wizard-back").addEventListener("click", () => { if (wizardStep > 0) { wizardStep -= 1; renderWizard(); } });
    document.getElementById("wizard-next").addEventListener("click", () => {
      if (wizardStep === wizardSteps.length - 1) { finishWizard(); return; }
      wizardStep += 1; renderWizard();
    });
    showWizardOnFirstVisit();
    load();
  </script>
</body>
</html>
""".replace("{{PROFILE_OPTIONS}}", _PROFILE_OPTIONS)
