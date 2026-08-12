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
    a:not(.btn) {
      color: #9ec1ff;
      text-decoration: underline;
      text-underline-offset: 2px;
    }
    a:not(.btn):hover { color: #c5d9ff; }
    .picker, .actions, .section-head { display:flex; flex-wrap:wrap; align-items:center; gap:10px; }
    .picker, .actions { margin-top:16px; }
    .section-head { justify-content:space-between; margin-bottom:12px; }
    details.section > summary.section-head { cursor:pointer; list-style:none; margin-bottom:0; }
    details.section[open] > summary.section-head { margin-bottom:12px; }
    details.section > summary.section-head::-webkit-details-marker { display:none; }
    details.section > summary.section-head h2::before { content:"\\25B8  "; color:var(--muted); }
    details.section[open] > summary.section-head h2::before { content:"\\25BE  "; }
    .template-banner { margin:12px 0 0; padding:10px 12px; color:#fed7aa; background:#431407; border:1px solid #9a3412; border-radius:10px; }
    .template-banner[hidden] { display:none; }
    button, .btn { min-height:34px; padding:0 14px; border:0; border-radius:10px; background:var(--accent); color:#111; font:inherit; font-weight:600; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; justify-content:center; }
    button.secondary, .btn.secondary { color:var(--text); background:#0f141d; border:1px solid var(--border); }
    button.danger { color:#fff; background:#b91c1c; }
    button:disabled { cursor:not-allowed; opacity:.55; }
    label { display:flex; flex-direction:column; gap:6px; color:var(--muted); font-size:.85rem; font-weight:600; }
    select, input, textarea { width:100%; padding:8px 9px; color:var(--text); background:#0f141d; border:1px solid var(--border); border-radius:8px; font:inherit; }
    .picker select { width:auto; min-width:240px; }
    #lun-search {
      width:min(420px, 100%); height:34px; padding:0 12px; border-radius:10px;
    }
    textarea { min-height:70px; resize:vertical; }
    .summary { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }
    .notes { grid-column:1 / -1; }
    .defaults-hint { grid-column:1 / -1; margin:0; color:var(--muted); font-size:.85rem; }
    .table-wrap { overflow-x:auto; }
    table { width:100%; min-width:980px; border-collapse:collapse; }
    th, td { padding:7px; text-align:left; vertical-align:top; border:1px solid var(--border); }
    th { color:var(--muted); background:#0f141d; font-size:.76rem; text-transform:uppercase; }
    td input, td select { min-width:100px; }
    .lun-table { min-width:1840px; }
    .lun-table td input, .lun-table td select { min-width:0; width:100%; }
    .lun-table th:nth-child(1) { min-width:52px; }    /* Done */
    .lun-table th:nth-child(2) { min-width:150px; }   /* Purpose */
    .lun-table th:nth-child(3) { min-width:70px; }    /* Count */
    .lun-table th:nth-child(4) { min-width:220px; }   /* Volume names */
    .lun-table th:nth-child(5) { min-width:140px; }   /* Size */
    .size-cell { display:flex; gap:6px; align-items:center; }
    .size-cell input { flex:1; min-width:4rem; }
    .size-cell select { width:4.5rem; flex:0 0 4.5rem; }
    .lun-table th:nth-child(6) { min-width:64px; }    /* Shared */
    .lun-table th:nth-child(7) { min-width:210px; }   /* Storage profile */
    .lun-table th:nth-child(8) { min-width:130px; }   /* Pool / CPG */
    .lun-table th:nth-child(9) { min-width:260px; }   /* Host names */
    .lun-table th:nth-child(10) { min-width:110px; }  /* SCSI / LUN ID */
    .lun-table th:nth-child(11) { min-width:170px; }  /* Card hint */
    .lun-table th:nth-child(12) { min-width:100px; }  /* Cluster */
    .volume-names { color:var(--accent2); font-size:.82rem; line-height:1.35; word-break:break-word; }
    .plan-table { min-width:1150px; }
    .plan-table th:nth-child(1) { min-width:52px; }   /* Done */
    .plan-table th:nth-child(2) { min-width:220px; }  /* Volume name */
    .host-table { min-width:1340px; }
    .host-table td input { min-width:0; width:100%; }
    .host-table th:nth-child(1) { min-width:52px; }   /* Done */
    .host-table th:nth-child(2) { min-width:150px; }  /* LPAR name */
    .host-table th:nth-child(3) { min-width:70px; }   /* Slot */
    .host-table th:nth-child(4) { min-width:90px; }   /* State */
    .host-table th:nth-child(7), .host-table th:nth-child(8) { min-width:180px; } /* WWPNs */
    .host-table th:nth-child(9) { min-width:200px; }  /* Notes */
    .remove { min-height:30px; padding:0 10px; color:#fecaca; background:#32151a; border:1px solid #7f1d1d; }
    .empty { padding:14px; color:var(--muted); }
    .plan-summary { margin:0 0 10px; padding:8px 12px; border-radius:8px; background:#0f2540; border:1px solid #1e3a5f; font-size:13px; line-height:1.6; }
    .plan-summary strong { color:#7dd3fc; }
    .plan-breakdown { color:var(--muted); font-size:12px; }
    .done-cell { width:44px; text-align:center; vertical-align:middle; }
    .done-cell input[type="checkbox"] { width:18px; height:18px; min-width:18px; cursor:pointer; accent-color:#22c55e; }
    tr.row-done td { background:#14532d; }
    tr.row-done input, tr.row-done select { background:#166534; border-color:#22c55e; }
    tr.row-done .volume-names { color:#bbf7d0; }
    .modal-backdrop { position:fixed; inset:0; z-index:10; display:grid; place-items:center; padding:20px; background:rgba(0,0,0,.72); }
    .modal-backdrop[hidden] { display:none !important; }
    .modal { width:min(850px,100%); max-height:85vh; overflow:auto; padding:20px; border:1px solid var(--border); border-radius:14px; background:var(--panel); }
    .modal-head { display:flex; align-items:center; justify-content:space-between; gap:12px; }
    .wizard-backdrop { position:fixed; inset:0; z-index:20; display:grid; place-items:center; padding:20px; background:rgba(0,0,0,.72); }
    .wizard-backdrop[hidden] { display:none !important; }
    .wizard { width:min(560px,100%); padding:24px; border:1px solid var(--border); border-radius:16px; background:var(--panel); box-shadow:0 24px 80px rgba(0,0,0,.45); }
    .wizard-step { color:var(--accent2); font-size:.8rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
    .cli-panel { margin-top:18px; border:1px solid var(--border); border-radius:12px; background:#0f141d; }
    .cli-panel > summary { cursor:pointer; list-style:none; padding:12px 14px; color:var(--accent2); font-weight:700; }
    .cli-panel > summary::-webkit-details-marker { display:none; }
    .cli-panel > summary::before { content:"▸ "; }
    .cli-panel[open] > summary::before { content:"▾ "; }
    .cli-panel pre { margin:0; padding:0 14px 14px; overflow:auto; color:#d8e3f2; white-space:pre-wrap; font-family:Consolas,monospace; font-size:.85rem; }
    .cli-panel .cli-empty { padding:0 14px 14px; color:var(--muted); }
    #cli-checklist-wrap { padding:0 14px 14px; }
    .cli-toolbar { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-bottom:10px; }
    .cli-warnings { margin:0 0 10px; color:#fed7aa; white-space:pre-wrap; font-size:.85rem; }
    .cli-warnings:empty { display:none; }
    .cli-table { min-width:760px; }
    .cli-table th:nth-child(1) { min-width:52px; }   /* Done */
    .cli-table th:nth-child(2) { min-width:180px; }  /* Volume */
    .cli-table th:nth-child(4) { min-width:90px; }   /* Copy */
    .cli-table td pre { margin:0; overflow:auto; white-space:pre-wrap; color:#d8e3f2; font-family:Consolas,monospace; font-size:.85rem; }
    .cli-table tr.row-done td { background:#14532d; }
    .cli-table tr.row-done td pre { color:#bbf7d0; }
    .wizard h2 { margin-top:10px; font-size:1.35rem; }
    .wizard-copy { min-height:72px; color:var(--text); line-height:1.5; }
    .wizard-actions { display:flex; justify-content:space-between; gap:10px; margin-top:20px; }
    .footer { margin-top:20px; font-size:.85rem; }
    .view-mode { display:flex; flex-wrap:wrap; align-items:center; gap:6px; }
    .view-mode button { min-height:30px; padding:0 12px; font-size:.85rem; }
    .view-mode button.active { background:var(--accent2); color:#111; }
    .inventory-banner { margin:12px 0 0; padding:10px 12px; color:#bae6fd; background:#0c4a6e; border:1px solid #0369a1; border-radius:10px; }
    .inventory-banner[hidden] { display:none; }
    .read-only-cell { color:var(--text); }
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
        <span class="view-mode" role="group" aria-label="View mode">
          <button type="button" class="secondary active" id="view-mode-plan">Plan</button>
          <button type="button" class="secondary" id="view-mode-inventory">Inventory</button>
        </span>
        <button type="button" class="secondary" id="new-btn">New</button>
        <input type="search" id="lun-search" placeholder="Search volume, purpose, or host…" aria-label="Search LUN build">
        <button type="button" class="secondary" id="lun-search-btn">Find</button>
        <span class="status" id="status" aria-live="polite"></span>
      </div>
      <p class="template-banner" id="template-banner" hidden>Template — use Save as new to keep an editable copy.</p>
      <p class="inventory-banner" id="inventory-banner" hidden>Offline copy · last updated</p>
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
        <button type="button" class="secondary" id="sync-inventory-btn">Sync Inventory</button>
        <button type="button" class="secondary" id="preview-btn">Preview / Dry-run</button>
        <button type="button" class="danger" id="run-btn">Run Create</button>
        <a class="btn secondary" href="/">Health Dashboard</a>
      </div>
    </section>
    <details class="section" id="section-details" open>
      <summary class="section-head"><h2>Build details</h2></summary>
      <div class="summary">
        <label>Name <input id="build-name" placeholder="Build name"></label>
        <label>Location <input id="build-location" placeholder="Site location"></label>
        <label>Storage profile
          <select id="default-storage-profile"><option value="">Select profile</option>{{PROFILE_OPTIONS}}</select>
        </label>
        <label>Pool / CPG <input id="default-pool-or-cpg" placeholder="Apply to all LUN rows"></label>
        <label>Card hint <select id="default-card-hint" title="LaunchPad SSH Health Card name used for Preview/Run"><option value="">Select Health Card</option></select></label>
        <p class="defaults-hint">Storage profile, Pool/CPG, and Card hint above fill every LUN row. Card hint is the LaunchPad SSH Health Card name (or unique part of it) for the target array — not the pool name. You can still edit individual rows.</p>
        <label class="notes">Notes <textarea id="build-notes" placeholder="Planning notes"></textarea></label>
      </div>
    </details>
    <details class="section" id="section-hosts" open>
      <summary class="section-head"><h2 id="hosts-heading">Hosts (0/0 done)</h2><button type="button" class="secondary" id="add-host-btn">Add host</button></summary>
      <div class="table-wrap"><table class="host-table"><thead><tr><th>Done</th><th>LPAR name</th><th>Slot</th><th>State</th><th>Required</th><th>Type</th><th>WWPN 1</th><th>WWPN 2</th><th>Notes</th><th></th></tr></thead><tbody id="hosts-body"></tbody></table></div>
    </details>
    <details class="section" id="section-luns" open>
      <summary class="section-head"><h2 id="luns-heading">LUN specs (0/0 done)</h2><button type="button" class="secondary" id="add-lun-btn">Add LUN spec</button></summary>
      <p class="hint">Each row expands into named volumes (shown in Volume names and LUN Plan). Edit Purpose/Count/Hosts here; names update automatically.</p>
      <div class="table-wrap"><table class="lun-table"><thead><tr id="luns-head-row"><th>Done</th><th>Purpose</th><th>Count</th><th>Volume names</th><th>Size</th><th>Shared</th><th>Storage profile</th><th>Pool / CPG</th><th>Host names</th><th>SCSI / LUN ID</th><th>Card hint</th><th>Cluster</th><th></th></tr></thead><tbody id="luns-body"></tbody></table></div>
    </details>
    <details class="section" id="section-plan" open>
      <summary class="section-head"><h2>LUN Plan</h2></summary>
      <p class="hint">Expanded volumes that Preview, Run, and Excel export will use — one row per volume.</p>
      <p class="plan-summary" id="plan-summary"></p>
      <div class="table-wrap"><table class="plan-table"><thead><tr><th>Done</th><th>Volume name</th><th>Source batch</th><th>Size</th><th>Shared</th><th>Pool / CPG</th><th>Host Name Mappings</th><th>Card hint</th><th>Cluster</th></tr></thead><tbody id="plan-body"></tbody></table></div>
    </details>
    <section class="section">
      <details class="cli-panel" id="cli-panel">
        <summary>Command checklist (Preview)</summary>
        <p class="cli-empty" id="cli-empty">Run Preview / Dry-run to fill this checklist.</p>
        <div id="cli-checklist-wrap" hidden>
          <div class="cli-toolbar">
            <button type="button" class="secondary" id="copy-all-remaining-btn">Copy All Remaining</button>
            <span class="status" id="cli-copy-status" aria-live="polite"></span>
          </div>
          <div id="cli-warnings" class="cli-warnings"></div>
          <div class="table-wrap">
            <table class="cli-table">
              <thead>
                <tr>
                  <th>Done</th>
                  <th>Volume</th>
                  <th>Commands</th>
                  <th></th>
                </tr>
              </thead>
              <tbody id="cli-checklist"></tbody>
            </table>
          </div>
        </div>
        <pre id="cli-commands" hidden></pre>
      </details>
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
    const templateBanner = document.getElementById("template-banner");
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
    let templates = [];
    let currentId = "";
    let lunSearchQuery = "";
    let persisted = false;
    let previewRequestId = 0;
    let wizardStep = 0;
    let cliChecklistGroups = [];
    let viewMode = "plan";
    let offlineSnapshots = {};
    let offlineSnapshotFull = {};
    let healthCards = {};
    const INVENTORY_BANNER_ONLINE = "Online · last updated";
    const INVENTORY_BANNER_OFFLINE = "Offline copy · last updated";
    const INVENTORY_BADGE_LABEL = "Inventory · Updated";
    window.__lastLunPreviewOk = false;
    window.__lastLunHasRunnableSteps = false;

    function invalidatePreview() {
      previewRequestId += 1;
      window.__lastLunPreviewOk = false;
      window.__lastLunHasRunnableSteps = false;
      clearCliChecklist();
    }
    function commandGroupSignature(volumeName, commands) {
      const name = String(volumeName || "").trim();
      const cmds = (commands || []).map((cmd) => String(cmd || "").trim()).filter(Boolean);
      return name + ((name || cmds.length) ? "\\n" : "") + cmds.join("\\n");
    }
    function groupLunStepsByVolume(steps) {
      const groups = [];
      for (const step of steps || []) {
        const volumeName = String(step.volume_name || "").trim();
        const cmd = String(step.cmd || "").trim();
        const solo = !volumeName;
        let group;
        if (!solo && groups.length && groups[groups.length - 1].volume_name === volumeName) {
          group = groups[groups.length - 1];
        } else {
          group = { volume_name: volumeName, commands: [], steps: [], signature: "" };
          groups.push(group);
        }
        group.steps.push(step);
        if (cmd) group.commands.push(cmd);
        group.signature = commandGroupSignature(group.volume_name, group.commands);
      }
      return groups;
    }
    function buildCommandDone(build) {
      if (!build.command_done || typeof build.command_done !== "object") build.command_done = {};
      return build.command_done;
    }
    async function copyText(text, statusMessage) {
      try {
        await navigator.clipboard.writeText(text);
        document.getElementById("cli-copy-status").textContent = statusMessage;
      } catch (_err) {
        document.getElementById("cli-copy-status").textContent = "Copy failed — select commands manually.";
      }
    }
    function updateCopyAllRemainingState() {
      const copyAllBtn = document.getElementById("copy-all-remaining-btn");
      if (!copyAllBtn) return;
      const commandDone = buildCommandDone(activeBuild());
      const hasRemaining = cliChecklistGroups.some((group) => group.commands.length && !commandDone[group.signature]);
      copyAllBtn.disabled = !hasRemaining;
    }
    function clearCliChecklist() {
      const empty = document.getElementById("cli-empty");
      const wrap = document.getElementById("cli-checklist-wrap");
      const body = document.getElementById("cli-checklist");
      const warningsEl = document.getElementById("cli-warnings");
      const status = document.getElementById("cli-copy-status");
      const panel = document.getElementById("cli-panel");
      if (!empty || !wrap || !body || !warningsEl || !panel) return;
      cliChecklistGroups = [];
      empty.hidden = false;
      wrap.hidden = true;
      body.innerHTML = "";
      warningsEl.innerHTML = "";
      if (status) status.textContent = "";
      panel.open = false;
      updateCopyAllRemainingState();
    }
    function fillCliChecklist(data) {
      const empty = document.getElementById("cli-empty");
      const wrap = document.getElementById("cli-checklist-wrap");
      const body = document.getElementById("cli-checklist");
      const warningsEl = document.getElementById("cli-warnings");
      if (!empty || !wrap || !body || !warningsEl) return;
      const warnings = (Array.isArray(data?.warnings) ? data.warnings : []).filter(Boolean);
      const rawSteps = Array.isArray(data?.steps) && data.steps.length
        ? data.steps
        : (Array.isArray(data?.log) ? data.log : []);
      const groups = groupLunStepsByVolume(rawSteps);
      if (!warnings.length && !groups.length) { clearCliChecklist(); return; }
      cliChecklistGroups = groups;
      empty.hidden = true;
      wrap.hidden = false;
      warningsEl.innerHTML = warnings.map((warning) => `<div>WARNING: ${esc(warning)}</div>`).join("");
      const commandDone = buildCommandDone(activeBuild());
      body.innerHTML = groups.length
        ? groups.map((group, index) => {
            const done = Boolean(commandDone[group.signature]);
            const hasCommands = group.commands.length > 0;
            return `<tr class="${done ? "row-done" : ""}">
              <td class="done-cell"><input type="checkbox" data-cli-done-index="${index}" title="Mark commands done" ${done ? "checked" : ""}></td>
              <td>${esc(group.volume_name || "—")}</td>
              <td><pre>${esc(group.commands.join("\\n"))}</pre></td>
              <td><button type="button" class="secondary" data-cli-copy-index="${index}" ${hasCommands ? "" : "disabled"}>Copy</button></td>
            </tr>`;
          }).join("")
        : '<tr><td colspan="4" class="empty">No commands to show.</td></tr>';
      updateCopyAllRemainingState();
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
    const SITE_HOST_RE = /^([A-Za-z]{3,4})([A-Za-z]{2,}\\d+.*)$/;
    function inferSitePrefix(hostNames) {
      for (const host of hostNames || []) {
        const match = String(host || "").match(SITE_HOST_RE);
        if (match) return match[1].toLowerCase();
      }
      return "";
    }
    function volumeNameBase(lun, purpose) {
      if (Boolean(lun.exact_name)) return null;
      const hostNames = Array.isArray(lun.host_names) ? lun.host_names.filter(Boolean) : [];
      let prefix = String(lun.name_prefix || "").trim().replace(/_+$/, "");
      if (!prefix) prefix = inferSitePrefix(hostNames);
      const cluster = String(lun.cluster || "").trim().toLowerCase();
      const shared = Boolean(lun.shared);
      let head = "";
      if (!shared && hostNames.length === 1) {
        const host = String(hostNames[0]);
        if (prefix && host.toLowerCase().startsWith(prefix.toLowerCase())) {
          const short = host.slice(prefix.length).replace(/^[_-]+/, "");
          head = short ? `${prefix}${short}` : host;
        } else if (prefix) {
          head = `${prefix}${host}`;
        } else {
          head = host;
        }
      } else if (cluster) {
        head = prefix ? `${prefix}${cluster}` : cluster;
      } else if (prefix) {
        head = prefix;
      } else {
        return null;
      }
      return `${head}_${purpose}`;
    }
    function expandLunBatch(lun) {
      const purpose = String(lun.purpose || "").trim();
      let count = Number(lun.count);
      if (!Number.isFinite(count) || count < 1) count = 1;
      const base = volumeNameBase(lun, purpose);
      const names = [];
      for (let index = 0; index < count; index += 1) {
        if (base) names.push(count === 1 ? base : `${base}_${index + 1}`);
        else names.push(count === 1 ? purpose : `${purpose}_${index + 1}`);
      }
      return names;
    }
    // Keep host/lun/build match helpers in sync with launchpad.lun_builder_search
    function normalizeSearchQuery(value) {
      return String(value || "").trim().toLowerCase();
    }
    function fieldMatchesText(field, q) {
      if (!q) return false;
      const text = String(field || "").trim().toLowerCase();
      return Boolean(text) && text.includes(q);
    }
    function hostRowMatches(host, query) {
      const q = normalizeSearchQuery(query);
      if (!q) return true;
      return fieldMatchesText(host?.lpar_name, q);
    }
    function lunRowMatches(lun, query) {
      const q = normalizeSearchQuery(query);
      if (!q) return true;
      if (fieldMatchesText(lun?.purpose, q)) return true;
      for (const name of lun?.host_names || []) {
        if (fieldMatchesText(name, q)) return true;
      }
      for (const name of expandLunBatch(lun || {})) {
        if (fieldMatchesText(name, q)) return true;
      }
      return false;
    }
    function buildMatches(build, query) {
      const q = normalizeSearchQuery(query);
      if (!q) return true;
      if ((build?.hosts || []).some((host) => host && hostRowMatches(host, query))) return true;
      if ((build?.luns || []).some((lun) => lun && lunRowMatches(lun, query))) return true;
      return false;
    }
    function applyLunSearchFilter(build) {
      if (!lunSearchQuery) return;
      hostsBody.querySelectorAll("tr").forEach((tr) => {
        const indexAttr = tr.querySelector("[data-index]")?.dataset?.index;
        if (indexAttr === undefined) return;
        const host = (build.hosts || [])[Number(indexAttr)];
        if (!host || !hostRowMatches(host, lunSearchQuery)) tr.style.display = "none";
      });
      lunsBody.querySelectorAll("tr").forEach((tr) => {
        const indexAttr = tr.querySelector("[data-index]")?.dataset?.index;
        if (indexAttr === undefined) return;
        const lun = (build.luns || [])[Number(indexAttr)];
        if (!lun || !lunRowMatches(lun, lunSearchQuery)) tr.style.display = "none";
      });
    }
    function runLunSearch() {
      const searchInput = document.getElementById("lun-search");
      const raw = (searchInput?.value || "").trim();
      lunSearchQuery = raw;
      if (!raw) {
        render();
        statusEl.textContent = "Search cleared.";
        return;
      }
      if (buildMatches(activeBuild(), raw)) {
        render();
        statusEl.textContent = "Showing matching rows";
        return;
      }
      const catalog = [...templates, ...builds];
      const matches = catalog
        .filter((item) => item && buildMatches(item, raw))
        .slice()
        .sort((a, b) =>
          String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" })
        );
      if (!matches.length) {
        lunSearchQuery = "";
        render();
        statusEl.textContent = "No matching hosts, volumes, or purposes";
        return;
      }
      const first = matches[0];
      currentId = String(first.id || "");
      invalidatePreview();
      render();
      const extra = matches.length - 1;
      statusEl.textContent = extra
        ? `Found in ${first.name || first.id} (also in ${extra} other build(s))`
        : `Found in ${first.name || first.id}`;
    }
    function normalizeHostName(value) {
      return String(value || "").trim().toLowerCase();
    }
    function syncCompletionFromPlan(build) {
      const planDone = build.plan_done && typeof build.plan_done === "object"
        ? build.plan_done
        : {};
      const luns = Array.isArray(build.luns) ? build.luns : [];
      const hosts = Array.isArray(build.hosts) ? build.hosts : [];
      const volumeNamesByLun = luns.map((lun) => expandLunBatch(lun));

      luns.forEach((lun, index) => {
        lun.done = volumeNamesByLun[index].every((name) => Boolean(planDone[name]));
      });

      hosts.forEach((host) => {
        const hostName = normalizeHostName(host.lpar_name);
        if (!hostName) return;
        const mappedNames = [];
        luns.forEach((lun, index) => {
          const hostNames = Array.isArray(lun.host_names) ? lun.host_names : [];
          if (hostNames.some((name) => normalizeHostName(name) === hostName)) {
            mappedNames.push(...volumeNamesByLun[index]);
          }
        });
        if (mappedNames.length) {
          host.done = mappedNames.every((name) => Boolean(planDone[name]));
        }
      });
    }
    function emptyBuild() {
      return {
        id:"", name:"", location:"", notes:"", hosts:[], luns:[], is_template:false,
        default_storage_profile:"", default_pool_or_cpg:"", default_card_hint:"",
        plan_done:{}, command_done:{},
      };
    }
    function normalizeSiteName(value) {
      return String(value || "").trim().toLowerCase();
    }
    function buildSiteNames(build) {
      return [build?.name, build?.default_card_hint, build?.location]
        .map((value) => normalizeSiteName(value))
        .filter(Boolean);
    }
    function snapshotMatchesBuild(snapshot, build) {
      const site = normalizeSiteName(snapshot?.site_name);
      if (!site) return false;
      return buildSiteNames(build).includes(site);
    }
    function findSnapshotForBuild(build) {
      for (const row of Object.values(offlineSnapshots)) {
        if (snapshotMatchesBuild(row, build)) return row;
      }
      return null;
    }
    function findSnapshotForSelection() {
      if (String(currentId || "").startsWith("inventory:")) {
        const cardId = currentId.slice("inventory:".length);
        return offlineSnapshots[cardId] || null;
      }
      return findSnapshotForBuild(activeBuild());
    }
    function isInventoryOnlySelection() {
      return String(currentId || "").startsWith("inventory:");
    }
    function formatInventoryTimestamp(iso) {
      if (!iso) return "unknown";
      const date = new Date(iso);
      if (Number.isNaN(date.getTime())) return iso;
      return date.toLocaleString();
    }
    function cardIsOffline(card) {
      if (!card) return true;
      if (card.error) return true;
      const results = card.command_results;
      return !Array.isArray(results) || !results.length;
    }
    async function ensureFullSnapshot(cardId) {
      const key = String(cardId);
      if (offlineSnapshotFull[key]) return offlineSnapshotFull[key];
      try {
        const response = await fetch(`/api/lun-offline-inventory?card_id=${encodeURIComponent(key)}`);
        const data = await response.json().catch(() => ({}));
        if (data.ok && data.snapshot) {
          offlineSnapshotFull[key] = data.snapshot;
          return data.snapshot;
        }
      } catch (_err) { /* keep summary-only view */ }
      return null;
    }
    async function loadOfflineInventory() {
      try {
        const response = await fetch("/api/lun-offline-inventory");
        const data = await response.json().catch(() => ({}));
        offlineSnapshots = {};
        for (const row of (data.snapshots || [])) {
          offlineSnapshots[String(row.card_id)] = row;
        }
      } catch (_err) {
        offlineSnapshots = {};
      }
    }
    async function loadHealthCards() {
      try {
        const response = await fetch("/api/cards");
        const cards = await response.json().catch(() => []);
        healthCards = {};
        for (const card of (Array.isArray(cards) ? cards : [])) {
          healthCards[String(card.id)] = card;
        }
      } catch (_err) {
        healthCards = {};
      }
    }
    function sshCardNames() {
      return Object.values(healthCards)
        .filter((card) => !card.card_type || card.card_type === "ssh")
        .map((card) => String(card.name || "").trim())
        .filter(Boolean)
        .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
    }
    function fillCardHintOptions(selectedHint) {
      const select = document.getElementById("default-card-hint");
      if (!select) return;
      const current = String(selectedHint || "").trim();
      const names = sshCardNames();
      const extras = current && !names.includes(current) ? [current] : [];
      const values = ["", ...extras, ...names];
      select.innerHTML = values.map((name) => {
        const label = name || "Select Health Card";
        return `<option value="${esc(name)}">${esc(label)}</option>`;
      }).join("");
      select.value = current;
    }
    function inventoryBannerText(snapshot) {
      if (!snapshot) return "";
      const card = healthCards[String(snapshot.card_id)];
      const prefix = cardIsOffline(card) ? INVENTORY_BANNER_OFFLINE : INVENTORY_BANNER_ONLINE;
      return `${prefix} ${formatInventoryTimestamp(snapshot.updated_at)}`;
    }
    function updateInventoryBanner(snapshot) {
      const banner = document.getElementById("inventory-banner");
      if (!banner) return;
      if (viewMode !== "inventory" || !snapshot) {
        banner.hidden = true;
        return;
      }
      banner.hidden = false;
      banner.textContent = inventoryBannerText(snapshot);
    }
    function inventoryBadgeText(snapshot) {
      if (!snapshot?.updated_at) return "";
      return `${INVENTORY_BADGE_LABEL} ${formatInventoryTimestamp(snapshot.updated_at)}`;
    }
    function buildInventoryPickerOptions() {
      const catalog = [...templates, ...builds];
      const matchedSites = new Set();
      for (const item of catalog) {
        for (const name of buildSiteNames(item)) matchedSites.add(name);
      }
      const options = [];
      for (const row of Object.values(offlineSnapshots)) {
        const site = normalizeSiteName(row.site_name);
        if (!site || matchedSites.has(site)) continue;
        options.push({
          id: `inventory:${row.card_id}`,
          label: `${row.site_name} (inventory only)`,
        });
      }
      return options.sort((a, b) =>
        a.label.localeCompare(b.label, undefined, { sensitivity: "base" })
      );
    }
    function planEditsBlocked() {
      return viewMode === "inventory";
    }
    function updatePlanEditControls(inInventoryMode) {
      const blocked = inInventoryMode;
      [
        "save-btn", "save-new-btn", "delete-btn", "export-excel-btn", "export-csv-btn",
        "import-btn", "pull-fc-btn", "sync-inventory-btn", "preview-btn", "run-btn",
        "add-host-btn", "add-lun-btn", "new-btn", "import-mode",
      ].forEach((id) => {
        const element = document.getElementById(id);
        if (element) element.disabled = blocked;
      });
      ["build-name", "build-location", "build-notes", "default-storage-profile", "default-pool-or-cpg", "default-card-hint"].forEach((id) => {
        const element = document.getElementById(id);
        if (element) element.disabled = blocked;
      });
      document.getElementById("section-details").open = !blocked;
    }
    function renderInventoryTables(snapshot) {
      const full = offlineSnapshotFull[String(snapshot?.card_id)] || snapshot || {};
      const hosts = Array.isArray(full.hosts) ? full.hosts : [];
      const volumes = Array.isArray(full.volumes) ? full.volumes : [];
      hostsBody.innerHTML = hosts.length
        ? hosts.map((host) => `<tr>
            <td class="read-only-cell">—</td>
            <td class="read-only-cell">${esc(host.lpar_name || "")}</td>
            <td class="read-only-cell">${esc(host.slot || "")}</td>
            <td class="read-only-cell">${esc(host.state || "")}</td>
            <td class="read-only-cell">${host.required ? "Yes" : "No"}</td>
            <td class="read-only-cell">${esc(host.type || "")}</td>
            <td class="read-only-cell">${esc(host.wwpn1 || "")}</td>
            <td class="read-only-cell">${esc(host.wwpn2 || "")}</td>
            <td class="read-only-cell">${esc(host.notes || "")}</td>
            <td></td>
          </tr>`).join("")
        : '<tr><td colspan="10" class="empty">No inventory hosts.</td></tr>';
      const lunsHead = document.getElementById("luns-head-row");
      if (lunsHead) {
        lunsHead.innerHTML = "<th>Name</th><th>Pool / CPG</th><th>Capacity</th><th>Status</th>";
      }
      lunsBody.innerHTML = volumes.length
        ? volumes.map((volume) => `<tr>
            <td class="read-only-cell">${esc(volume.name || "")}</td>
            <td class="read-only-cell">${esc(volume.pool || "")}</td>
            <td class="read-only-cell">${esc(volume.capacity || "")}</td>
            <td class="read-only-cell">${esc(volume.status || "")}</td>
          </tr>`).join("")
        : '<tr><td colspan="4" class="empty">No inventory volumes.</td></tr>';
      const hostsHeading = document.getElementById("hosts-heading");
      const lunsHeading = document.getElementById("luns-heading");
      if (hostsHeading) hostsHeading.textContent = `Hosts (inventory ${hosts.length})`;
      if (lunsHeading) lunsHeading.textContent = `Volumes (inventory ${volumes.length})`;
      const planBody = document.getElementById("plan-body");
      const planSummary = document.getElementById("plan-summary");
      if (planBody) planBody.innerHTML = '<tr><td colspan="9" class="empty">Inventory view shows hosts and volumes only.</td></tr>';
      if (planSummary) planSummary.textContent = "";
    }
    function restorePlanTableHeaders() {
      const lunsHead = document.getElementById("luns-head-row");
      if (lunsHead) {
        lunsHead.innerHTML = "<th>Done</th><th>Purpose</th><th>Count</th><th>Volume names</th><th>Size</th><th>Shared</th><th>Storage profile</th><th>Pool / CPG</th><th>Host names</th><th>SCSI / LUN ID</th><th>Card hint</th><th>Cluster</th><th></th>";
      }
    }
    async function refreshInventoryView() {
      if (viewMode === "inventory") {
        const snapshot = findSnapshotForSelection();
        if (snapshot) await ensureFullSnapshot(snapshot.card_id);
      }
      render();
    }
    async function setViewMode(mode) {
      viewMode = mode;
      document.getElementById("view-mode-plan").classList.toggle("active", mode === "plan");
      document.getElementById("view-mode-inventory").classList.toggle("active", mode === "inventory");
      await refreshInventoryView();
    }
    function activeBuild() {
      return builds.find((build) => String(build.id) === currentId)
        || templates.find((template) => String(template.id) === currentId)
        || emptyBuild();
    }
    function loadLocal() { try { const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); return Array.isArray(value) ? value : []; } catch (_err) { return []; } }
    function saveLocal() { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(builds)); } catch (_err) { /* memory-only fallback */ } }
    let completionSaveTimer = null;
    function scheduleCompletionSave(build) {
      if (completionSaveTimer) clearTimeout(completionSaveTimer);
      completionSaveTimer = setTimeout(async () => {
        completionSaveTimer = null;
        if (!persisted || !build || !build.id || build.is_template) return;
        build.updated_at = new Date().toISOString();
        try {
          const response = await fetch("/api/lun-builds", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ build }),
          });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          builds = (await response.json()).builds;
          saveLocal();
          statusEl.textContent = "Completion saved.";
        } catch (error) {
          statusEl.textContent = `Completion saved locally only: ${error.message || error}`;
        }
      }, 400);
    }
    function persistCompletionState() {
      const build = activeBuild();
      saveLocal();
      if (!persisted || !build.id || build.is_template) {
        statusEl.textContent = "Completion saved locally only.";
        return;
      }
      scheduleCompletionSave(build);
    }
    function input(key, value, index, kind, type="text") { return `<input type="${type}" data-kind="${kind}" data-index="${index}" data-key="${key}" value="${esc(value)}">`; }
    function splitLunSizeForUi(size) {
      const text = String(size || "").trim();
      if (!text) return { amount: "", unit: "GB" };
      const match = text.match(/^(-?\\d+(?:\\.\\d+)?)\\s*(GB|TB|MB|KB|PB|B)?$/i);
      if (!match) return { amount: text, unit: "GB" };
      const amount = match[1];
      const suffix = String(match[2] || "").toUpperCase();
      if (suffix === "GB" || suffix === "TB") return { amount, unit: suffix };
      return { amount, unit: "GB" };
    }
    function joinLunSize(amount, unit) {
      const text = String(amount || "").trim();
      if (!text) return "";
      const match = text.match(/^(-?\\d+(?:\\.\\d+)?)\\s*(GB|TB|MB|KB|PB|B)?$/i);
      if (match) {
        const suffix = String(match[2] || "").toUpperCase();
        if (suffix === "GB" || suffix === "TB") return `${match[1]}${suffix}`;
      }
      let normalized = String(unit || "").trim().toUpperCase();
      if (normalized !== "GB" && normalized !== "TB") normalized = "GB";
      if (match) return `${match[1]}${normalized}`;
      return `${text}${normalized}`;
    }
    function sizeCell(lun, index) {
      const parts = splitLunSizeForUi(lun.size);
      const gbSelected = parts.unit === "GB" ? " selected" : "";
      const tbSelected = parts.unit === "TB" ? " selected" : "";
      return `<td class="size-cell"><input type="text" data-kind="luns" data-index="${index}" data-key="size_amount" value="${esc(parts.amount)}"><select data-kind="luns" data-index="${index}" data-key="size_unit"><option value="GB"${gbSelected}>GB</option><option value="TB"${tbSelected}>TB</option></select></td>`;
    }
    function render() {
      const build = activeBuild();
      const inventoryMode = viewMode === "inventory";
      const snapshot = findSnapshotForSelection();
      const templateOptions = templates.map((item) => {
        const snap = findSnapshotForBuild(item);
        const badge = snap ? ` — ${inventoryBadgeText(snap)}` : "";
        return `<option value="${esc(item.id)}">${esc(item.name || item.id)}${esc(badge)}</option>`;
      }).join("");
      const buildOptions = builds.length
        ? builds.map((item) => {
            const snap = findSnapshotForBuild(item);
            const badge = snap ? ` — ${inventoryBadgeText(snap)}` : "";
            return `<option value="${esc(item.id)}">${esc(item.name || item.id)}${esc(badge)}</option>`;
          }).join("")
        : '<option value="">New build</option>';
      const inventoryOptions = buildInventoryPickerOptions()
        .map((item) => `<option value="${esc(item.id)}">${esc(item.label)}</option>`)
        .join("");
      const inventoryGroup = inventoryOptions
        ? `<optgroup label="Inventory only">${inventoryOptions}</optgroup>`
        : "";
      picker.innerHTML = `<optgroup label="Templates">${templateOptions}</optgroup><optgroup label="Saved builds">${buildOptions}</optgroup>${inventoryGroup}`;
      picker.value = currentId;
      templateBanner.hidden = !build.is_template || inventoryMode;
      updateInventoryBanner(snapshot);
      updatePlanEditControls(inventoryMode);
      document.getElementById("view-mode-plan").classList.toggle("active", viewMode === "plan");
      document.getElementById("view-mode-inventory").classList.toggle("active", viewMode === "inventory");
      if (inventoryMode) {
        renderInventoryTables(snapshot);
        document.getElementById("delete-btn").disabled = true;
        document.getElementById("export-excel-btn").disabled = true;
        document.getElementById("export-csv-btn").disabled = true;
        document.getElementById("run-btn").disabled = true;
        if (snapshot && !isInventoryOnlySelection() && statusEl.textContent && !statusEl.textContent.includes(INVENTORY_BADGE_LABEL)) {
          statusEl.textContent = `${statusEl.textContent} ${inventoryBadgeText(snapshot)}`.trim();
        }
        return;
      }
      restorePlanTableHeaders();
      document.getElementById("build-name").value = build.name || "";
      document.getElementById("build-location").value = build.location || "";
      document.getElementById("build-notes").value = build.notes || "";
      document.getElementById("default-storage-profile").value = build.default_storage_profile || "";
      document.getElementById("default-pool-or-cpg").value = build.default_pool_or_cpg || "";
      fillCardHintOptions(build.default_card_hint || "");
      hostsBody.innerHTML = (build.hosts || []).length ? build.hosts.map((host, index) => `<tr class="${host.done ? "row-done" : ""}">
        <td class="done-cell"><input type="checkbox" data-kind="hosts" data-index="${index}" data-key="done" title="Mark row done" ${host.done ? "checked" : ""}></td>
        <td>${input("lpar_name", host.lpar_name, index, "hosts")}</td><td>${input("slot", host.slot, index, "hosts")}</td>
        <td>${input("state", host.state, index, "hosts")}</td><td><input type="checkbox" data-kind="hosts" data-index="${index}" data-key="required" ${host.required ? "checked" : ""}></td>
        <td>${input("type", host.type, index, "hosts")}</td><td>${input("wwpn1", host.wwpn1, index, "hosts")}</td>
        <td>${input("wwpn2", host.wwpn2, index, "hosts")}</td><td>${input("notes", host.notes, index, "hosts")}</td>
        <td><button type="button" class="remove" data-remove="hosts" data-index="${index}">Remove</button></td></tr>`).join("") : '<tr><td colspan="10" class="empty">No hosts yet.</td></tr>';
      lunsBody.innerHTML = (build.luns || []).length ? build.luns.map((lun, index) => {
        const volumeNames = expandLunBatch(lun);
        return `<tr class="${lun.done ? "row-done" : ""}">
        <td class="done-cell"><input type="checkbox" data-kind="luns" data-index="${index}" data-key="done" title="Mark row done" ${lun.done ? "checked" : ""}></td>
        <td>${input("purpose", lun.purpose, index, "luns")}</td><td>${input("count", lun.count || 1, index, "luns", "number")}</td>
        <td class="volume-names">${esc(volumeNames.join(", "))}</td>
        ${sizeCell(lun, index)}<td><input type="checkbox" data-kind="luns" data-index="${index}" data-key="shared" ${lun.shared ? "checked" : ""}></td>
        <td><select data-kind="luns" data-index="${index}" data-key="storage_profile"><option value="">Select profile</option>${PROFILE_OPTIONS}</select></td>
        <td>${input("pool_or_cpg", lun.pool_or_cpg, index, "luns")}</td><td>${input("host_names", (lun.host_names || []).join(", "), index, "luns")}</td>
        <td>${input("scsi_or_lun_id", lun.scsi_or_lun_id, index, "luns")}</td><td>${input("card_hint", lun.card_hint, index, "luns")}</td>
        <td>${input("cluster", lun.cluster, index, "luns")}</td><td><button type="button" class="remove" data-remove="luns" data-index="${index}">Remove</button></td></tr>`;
      }).join("") : '<tr><td colspan="13" class="empty">No LUN specs yet.</td></tr>';
      (build.luns || []).forEach((lun, index) => {
        const profileSelect = lunsBody.querySelector(`select[data-key="storage_profile"][data-index="${index}"]`);
        if (profileSelect) profileSelect.value = lun.storage_profile || "";
      });
      applyLunSearchFilter(build);
      renderPlanTable(build);
      updateSectionHeadings(build);
      document.getElementById("delete-btn").disabled = !currentId || Boolean(build.is_template);
      document.getElementById("export-excel-btn").disabled = !currentId || Boolean(build.is_template);
      document.getElementById("export-csv-btn").disabled = !currentId || Boolean(build.is_template);
      document.getElementById("run-btn").disabled = !window.__lastLunPreviewOk || !window.__lastLunHasRunnableSteps;
      if (snapshot && !inventoryMode) {
        const badge = inventoryBadgeText(snapshot);
        if (badge && statusEl.textContent && !statusEl.textContent.includes(INVENTORY_BADGE_LABEL)) {
          statusEl.textContent = `${statusEl.textContent} ${badge}`.trim();
        }
      }
    }
    function readSummary(build) {
      build.name = document.getElementById("build-name").value.trim();
      build.location = document.getElementById("build-location").value.trim();
      build.notes = document.getElementById("build-notes").value.trim();
      build.default_storage_profile = document.getElementById("default-storage-profile").value.trim();
      build.default_pool_or_cpg = document.getElementById("default-pool-or-cpg").value.trim();
      build.default_card_hint = document.getElementById("default-card-hint").value.trim();
    }
    function applyBuildDefaultsToLuns(build) {
      const profile = String(build.default_storage_profile || "").trim();
      const pool = String(build.default_pool_or_cpg || "").trim();
      const cardHint = String(build.default_card_hint || "").trim();
      (build.luns || []).forEach((lun) => {
        if (profile) lun.storage_profile = profile;
        if (pool) lun.pool_or_cpg = pool;
        if (cardHint) lun.card_hint = cardHint;
      });
    }
    function onBuildDefaultsChanged() {
      const build = activeBuild();
      readSummary(build);
      applyBuildDefaultsToLuns(build);
      invalidatePreview();
      render();
      statusEl.textContent = "Applied storage defaults to all LUN rows.";
    }
    function makeId(name) {
      const base = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "build";
      let id = base; let suffix = 2;
      while (builds.some((build) => build.id === id)) id = `${base}-${suffix++}`;
      return id;
    }
    function templateCopyName(name) {
      return String(name || "").replace(" (Template)", "").trim();
    }
    function addRow(kind) {
      if (planEditsBlocked()) return;
      const build = activeBuild();
      build[kind].push(kind === "hosts"
        ? { lpar_name:"", slot:"", state:"", required:false, type:"", wwpn1:"", wwpn2:"", notes:"", done:false }
        : {
            purpose:"", count:1, size:"", shared:false,
            storage_profile: build.default_storage_profile || "",
            pool_or_cpg: build.default_pool_or_cpg || "",
            host_names:[], scsi_or_lun_id:"",
            card_hint: build.default_card_hint || "",
            cluster:"", done:false,
          });
      readSummary(activeBuild());
      invalidatePreview();
      render();
    }
    function updateField(event) {
      if (planEditsBlocked()) return;
      const target = event.target;
      const item = (activeBuild()[target.dataset.kind] || [])[Number(target.dataset.index)];
      if (!item || !target.dataset.key) return;
      if (target.dataset.key === "size_amount" || target.dataset.key === "size_unit") {
        const row = target.closest("tr");
        const amountEl = row && row.querySelector('[data-key="size_amount"]');
        const unitEl = row && row.querySelector('[data-key="size_unit"]');
        let amount = amountEl ? amountEl.value : "";
        let unit = unitEl ? unitEl.value : "GB";
        const rawMatch = String(amount || "").trim().match(/^(-?\\d+(?:\\.\\d+)?)\\s*(GB|TB|MB|KB|PB|B)?$/i);
        if (rawMatch && rawMatch[2]) {
          const suf = String(rawMatch[2]).toUpperCase();
          if (suf !== "GB" && suf !== "TB") {
            amount = rawMatch[1];
          }
        }
        item.size = joinLunSize(amount, unit);
        const parts = splitLunSizeForUi(item.size);
        if (amountEl) amountEl.value = parts.amount;
        if (unitEl) unitEl.value = parts.unit;
        invalidatePreview();
        document.getElementById("run-btn").disabled = true;
        if (target.dataset.kind === "luns") refreshExpandedNames();
        return;
      }
      const value = target.type === "checkbox" ? target.checked : target.value;
      item[target.dataset.key] = target.dataset.key === "host_names" ? String(value).split(",").map((name) => name.trim()).filter(Boolean) : value;
      if (target.dataset.key === "done") {
        const row = target.closest("tr");
        if (row) row.classList.toggle("row-done", Boolean(value));
        updateSectionHeadings(activeBuild());
        persistCompletionState();
        return;
      }
      invalidatePreview();
      document.getElementById("run-btn").disabled = true;
      if (target.dataset.kind === "luns") refreshExpandedNames();
    }
    function refreshExpandedNames() {
      const build = activeBuild();
      (build.luns || []).forEach((lun, index) => {
        const cell = lunsBody.querySelector(`tr:nth-child(${index + 1}) td.volume-names`);
        if (cell) cell.textContent = expandLunBatch(lun).join(", ");
      });
      renderPlanTable(build);
    }
    function renderPlanTable(build) {
      const planBody = document.getElementById("plan-body");
      if (!planBody) return;
      const planDone = build.plan_done || {};
      const planRows = (build.luns || []).flatMap((lun) => {
        const names = expandLunBatch(lun);
        const hostCount = (lun.host_names || []).filter(Boolean).length;
        return names.map((name) => ({
          name,
          done: Boolean(planDone[name]),
          purpose: lun.purpose || "",
          size: lun.size || "",
          shared: Boolean(lun.shared),
          pool: lun.pool_or_cpg || "",
          hosts: (lun.host_names || []).join("; "),
          hostCount,
          card: lun.card_hint || "",
          cluster: lun.cluster || "",
        }));
      });
      planBody.innerHTML = planRows.length
        ? planRows.map((row) => `<tr class="${row.done ? "row-done" : ""}">
            <td class="done-cell"><input type="checkbox" data-plan-name="${esc(row.name)}" title="Mark volume done" ${row.done ? "checked" : ""}></td>
            <td>${esc(row.name)}</td><td>${esc(row.purpose)}</td><td>${esc(row.size)}</td>
            <td>${row.shared ? "Yes" : "No"}</td><td>${esc(row.pool)}</td>
            <td>${esc(row.hosts)}</td><td>${esc(row.card)}</td><td>${esc(row.cluster)}</td>
          </tr>`).join("")
        : '<tr><td colspan="9" class="empty">No expanded volumes yet.</td></tr>';
      renderPlanSummary(build, planRows);
    }
    function updateSectionHeadings(build) {
      const hosts = build.hosts || [];
      const luns = build.luns || [];
      const hostsDone = hosts.filter((host) => host.done).length;
      const lunsDone = luns.filter((lun) => lun.done).length;
      const hostsHeading = document.getElementById("hosts-heading");
      const lunsHeading = document.getElementById("luns-heading");
      if (hostsHeading) hostsHeading.textContent = `Hosts (${hostsDone}/${hosts.length} done)`;
      if (lunsHeading) lunsHeading.textContent = `LUN specs (${lunsDone}/${luns.length} done)`;
    }
    function renderPlanSummary(build, planRows) {
      const summaryEl = document.getElementById("plan-summary");
      if (!summaryEl) return;
      if (!planRows.length) { summaryEl.textContent = ""; return; }
      const hostTotal = (build.hosts || []).length;
      const volumeTotal = planRows.length;
      const mappingTotal = planRows.reduce((sum, row) => sum + row.hostCount, 0);
      const byPurpose = new Map();
      planRows.forEach((row) => {
        const key = row.purpose || "(unnamed)";
        byPurpose.set(key, (byPurpose.get(key) || 0) + 1);
      });
      const breakdown = [...byPurpose.entries()].map(([name, count]) => `${esc(name)}: ${count}`).join(" | ");
      summaryEl.innerHTML = `<strong>${hostTotal}</strong> hosts &middot; <strong>${volumeTotal}</strong> LUNs &middot; <strong>${mappingTotal}</strong> mappings` + (breakdown ? `<br><span class="plan-breakdown">${breakdown}</span>` : "");
    }
    async function save(saveAsNew) {
      if (planEditsBlocked()) return;
      let build = activeBuild();
      readSummary(build);
      if (!build.name) { statusEl.textContent = "Enter a build name before saving."; return; }
      if (!build.id || saveAsNew || build.is_template) {
        build = JSON.parse(JSON.stringify(build));
        if (build.is_template) build.name = templateCopyName(build.name);
        build.id = makeId(build.name);
        build.is_template = false;
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
      if (!currentId || activeBuild().is_template || !window.confirm("Delete this LUN build?")) return;
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
        const previewText = formatLunResult(data);
        fillCliChecklist(data);
        showModal("Preview / Dry-run", previewText);
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
      if (!(await persistCurrentBuildBeforeOps())) return;
      if (!window.confirm("This will create and map LUNs on the resolved storage cards. Existing hosts must already exist. Continue?")) return;
      statusEl.textContent = "Running LUN create...";
      try {
        const data = await postLunOperation("/api/lun-builds/create", { build_id:currentId, confirm:true });
        const resultText = formatLunResult(data, true);
        fillCliChecklist(data);
        showModal("Run Create", resultText);
        statusEl.textContent = data.ok ? "LUN create completed." : "LUN create stopped after a failure.";
      } catch (error) {
        statusEl.textContent = `LUN create failed: ${error.message || error}`;
      } finally {
        previewRequestId += 1;
        window.__lastLunPreviewOk = false;
        window.__lastLunHasRunnableSteps = false;
        render();
      }
    }
    function exportBuild(format) {
      if (!currentId) { statusEl.textContent = "Save the build before exporting."; return; }
      if (activeBuild().is_template) {
        statusEl.textContent = "Save as new before exporting a template.";
        return;
      }
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
    async function syncInventory() {
      if (!currentId) { statusEl.textContent = "Save the build before syncing inventory."; return; }
      if (!persisted) { statusEl.textContent = "Unlock LaunchPad before syncing inventory."; return; }
      const cardName = window.prompt("Storage card name (required):", activeBuild()?.default_card_hint || "");
      if (cardName === null) return;
      if (!cardName.trim()) { statusEl.textContent = "Card name is required for Sync Inventory."; return; }
      statusEl.textContent = "Syncing inventory via SSH...";
      try {
        const response = await fetch("/api/lun-builds/sync-inventory", {
          method:"POST",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify({ build_id:currentId, card_name:cardName.trim() }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
        builds = data.builds; saveLocal(); invalidatePreview(); render();
        const p = data.pulled || {};
        importMessage(
          `Synced hosts=${p.hosts||0} volumes=${p.volumes||0} maps=${p.maps||0} skipped_snaps=${p.skipped_snaps||0} live_snaps=${p.live_snaps||0}. CG upserted. No create was run.`,
          data.warnings
        );
      } catch (error) {
        statusEl.textContent = `Sync Inventory failed: ${error.message || error}`;
      }
    }
    async function load() {
      const local = loadLocal(); builds = local; currentId = builds[0]?.id || ""; render();
      try {
        const response = await fetch("/api/lun-builds");
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json(); persisted = Boolean(data.persisted);
        builds = Array.isArray(data.builds) ? data.builds : local;
        templates = Array.isArray(data.templates) ? data.templates : [];
        currentId = builds[0]?.id || templates[0]?.id || ""; saveLocal();
        statusEl.textContent = persisted ? "Loaded from LaunchPad." : "Browser-only until LaunchPad is unlocked.";
      } catch (_error) { persisted = false; statusEl.textContent = "Browser-only until LaunchPad is unlocked."; }
      await Promise.all([loadOfflineInventory(), loadHealthCards()]);
      render();
    }
    picker.addEventListener("change", async () => {
      currentId = picker.value;
      if (isInventoryOnlySelection()) viewMode = "inventory";
      invalidatePreview();
      await refreshInventoryView();
    });
    document.getElementById("new-btn").addEventListener("click", () => {
      if (planEditsBlocked()) return;
      builds.push(emptyBuild()); currentId = ""; invalidatePreview(); render();
    });
    document.getElementById("view-mode-plan").addEventListener("click", () => setViewMode("plan"));
    document.getElementById("view-mode-inventory").addEventListener("click", () => setViewMode("inventory"));
    document.getElementById("lun-search-btn").addEventListener("click", runLunSearch);
    document.getElementById("lun-search").addEventListener("keydown", (event) => {
      if (event.key === "Enter") runLunSearch();
    });
    document.getElementById("save-btn").addEventListener("click", () => save(false));
    document.getElementById("save-new-btn").addEventListener("click", () => save(true));
    document.getElementById("delete-btn").addEventListener("click", removeBuild);
    document.getElementById("export-excel-btn").addEventListener("click", () => exportBuild("xlsx"));
    document.getElementById("export-csv-btn").addEventListener("click", () => exportBuild("csv"));
    document.getElementById("import-btn").addEventListener("click", () => document.getElementById("import-file").click());
    document.getElementById("import-file").addEventListener("change", (event) => { const file = event.target.files?.[0]; if (file) importBuild(file); });
    document.getElementById("pull-fc-btn").addEventListener("click", pullFcHosts);
    document.getElementById("sync-inventory-btn").addEventListener("click", syncInventory);
    document.getElementById("add-host-btn").addEventListener("click", (event) => { event.preventDefault(); event.stopPropagation(); addRow("hosts"); });
    document.getElementById("add-lun-btn").addEventListener("click", (event) => { event.preventDefault(); event.stopPropagation(); addRow("luns"); });
    document.querySelectorAll("details.section").forEach((section) => {
      const key = `launchpad.lunBuilder.section.${section.id}`;
      try { const saved = localStorage.getItem(key); if (saved !== null) section.open = saved === "true"; } catch (_err) { /* default open */ }
      section.addEventListener("toggle", () => {
        try { localStorage.setItem(key, String(section.open)); } catch (_err) { /* memory-only */ }
      });
    });
    [hostsBody, lunsBody].forEach((body) => {
      body.addEventListener("input", updateField); body.addEventListener("change", updateField);
      body.addEventListener("click", (event) => { const button = event.target.closest("[data-remove]"); if (!button) return; activeBuild()[button.dataset.remove].splice(Number(button.dataset.index), 1); readSummary(activeBuild()); invalidatePreview(); render(); });
    });
    document.getElementById("plan-body").addEventListener("change", (event) => {
      const target = event.target;
      const name = target?.dataset?.planName;
      if (!name) return;
      const build = activeBuild();
      if (!build.plan_done || typeof build.plan_done !== "object") build.plan_done = {};
      if (target.checked) build.plan_done[name] = true;
      else delete build.plan_done[name];
      syncCompletionFromPlan(build);
      readSummary(activeBuild());
      render();
      persistCompletionState();
    });
    document.getElementById("cli-checklist").addEventListener("change", (event) => {
      const target = event.target;
      const indexAttr = target?.dataset?.cliDoneIndex;
      if (indexAttr === undefined) return;
      const group = cliChecklistGroups[Number(indexAttr)];
      if (!group) return;
      const commandDone = buildCommandDone(activeBuild());
      if (target.checked) commandDone[group.signature] = true;
      else delete commandDone[group.signature];
      const row = target.closest("tr");
      if (row) row.classList.toggle("row-done", target.checked);
      updateCopyAllRemainingState();
      persistCompletionState();
    });
    document.getElementById("cli-checklist").addEventListener("click", (event) => {
      const button = event.target.closest("[data-cli-copy-index]");
      if (!button) return;
      const group = cliChecklistGroups[Number(button.dataset.cliCopyIndex)];
      if (!group || !group.commands.length) return;
      copyText(group.commands.join("\\n"), `Copied commands for ${group.volume_name || "this group"}.`);
    });
    document.getElementById("copy-all-remaining-btn").addEventListener("click", () => {
      const commandDone = buildCommandDone(activeBuild());
      const remaining = cliChecklistGroups.filter((group) => group.commands.length && !commandDone[group.signature]);
      const text = remaining.flatMap((group) => group.commands).join("\\n");
      if (!text) return;
      copyText(text, `Copied commands for ${remaining.length} remaining volume(s).`);
    });
    ["build-name", "build-location", "build-notes"].forEach((id) => document.getElementById(id).addEventListener("input", () => {
      const build = activeBuild();
      readSummary(build);
      invalidatePreview();
      document.getElementById("run-btn").disabled = true;
    }));
    document.getElementById("default-storage-profile").addEventListener("change", onBuildDefaultsChanged);
    document.getElementById("default-pool-or-cpg").addEventListener("change", onBuildDefaultsChanged);
    document.getElementById("default-card-hint").addEventListener("change", onBuildDefaultsChanged);
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
