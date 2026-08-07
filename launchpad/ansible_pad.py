"""Browser page for exporting and running Ansible Pad packages."""

ANSIBLE_PAD_PATH = "/ansible-pad"

ANSIBLE_PAD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Ansible Pad</title>
  <style>
    :root { --bg:#0b0f14; --panel:#151c27; --panel-alt:#0f141d; --text:#e8edf5; --muted:#a9b6c8; --accent:#ff6b00; --border:#2a3444; --danger:#ef4444; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; color:var(--text); font-family:Segoe UI,Inter,Arial,sans-serif; background:radial-gradient(circle at top,#172033 0%,var(--bg) 45%); }
    main { max-width:1120px; margin:0 auto; padding:28px 20px 48px; }
    section { margin-bottom:18px; padding:20px; border:1px solid var(--border); border-radius:14px; background:var(--panel); }
    .hero { background:linear-gradient(135deg,#1a2230,#101722); }
    h1 { margin:0 0 8px; color:var(--accent); font-size:1.9rem; }
    h2 { margin:0 0 14px; color:#ff9a56; font-size:1.12rem; }
    p, .hint, .status { color:var(--muted); line-height:1.5; }
    .grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
    .wide { grid-column:1 / -1; }
    label { display:flex; flex-direction:column; gap:6px; color:var(--muted); font-size:.86rem; font-weight:600; }
    input, select { width:100%; padding:9px 10px; color:var(--text); background:var(--panel-alt); border:1px solid var(--border); border-radius:8px; font:inherit; }
    .actions, .checks { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:14px; }
    .checks label { flex-direction:row; align-items:center; cursor:pointer; }
    .checks input { width:auto; accent-color:var(--accent); }
    button, a.button { min-height:36px; padding:0 14px; border:0; border-radius:9px; background:var(--accent); color:#111; font:inherit; font-weight:700; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; }
    button.secondary, a.secondary { color:var(--text); background:var(--panel-alt); border:1px solid var(--border); }
    button:disabled { opacity:.6; cursor:wait; }
    pre { min-height:150px; max-height:420px; overflow:auto; margin:0; padding:13px; color:#d8e3f2; background:#080c11; border:1px solid var(--border); border-radius:9px; white-space:pre-wrap; word-break:break-word; font:13px/1.5 Consolas,monospace; }
    .warning { color:#fed7aa; }
    @media (max-width:700px) { .grid { grid-template-columns:1fr; } .wide { grid-column:auto; } }
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Ansible Pad</h1>
      <p>Generate and run Ansible packages through control host <strong>plp5-dz5-nw</strong>. Native LaunchPad Contingency Groups and FlashCopy CG actions remain available as the direct SSH path.</p>
      <a class="button secondary" href="/">Back to dashboard</a>
    </section>

    <section>
      <h2>Control host settings</h2>
      <form id="settings-form" class="grid">
        <label>Host<input id="host" name="host" required></label>
        <label>SSH user<input id="user" name="user" autocomplete="username"></label>
        <label>SSH key path<input id="key_path" name="key_path" placeholder="C:\\\\Keys\\\\ansible.pem"></label>
        <label>Key passphrase<input id="key_passphrase" name="key_passphrase" type="password" autocomplete="new-password"></label>
        <label>SSH password<input id="password" name="password" type="password" autocomplete="new-password"></label>
        <label>Remote package directory<input id="remote_dir" name="remote_dir" placeholder="/srv/launchpad/ansible-pad"></label>
        <label class="wide">Default existing playbook<input id="default_playbook" name="default_playbook" placeholder="/opt/runbooks/playbook.yml"></label>
      </form>
      <div class="actions"><button id="save-settings" type="button">Save settings</button></div>
      <p id="settings-status" class="status" role="status"></p>
    </section>

    <section>
      <h2>Package and run</h2>
      <p class="hint">Download creates a ZIP locally. Sync &amp; Run uploads the generated package before running it on the configured control host.</p>
      <div class="grid">
        <label>Generated package playbook
          <select id="sync-playbook">
            <option value="playbooks/start_fc_consistgrp.yml">Start FlashCopy consistency group</option>
            <option value="playbooks/snap_copy_stub.yml">Snap-copy stub</option>
          </select>
        </label>
        <label>Existing remote playbook<input id="existing-playbook" placeholder="/opt/runbooks/playbook.yml"></label>
      </div>
      <div class="checks">
        <label><input id="check-mode" type="checkbox" checked> Check mode / dry run</label>
        <label><input id="confirm-mutate" type="checkbox"> I confirm this mutating run</label>
      </div>
      <p class="warning">A non-check run changes arrays and requires the confirmation checkbox.</p>
      <div class="actions">
        <a class="button secondary" href="/api/ansible-pad/export.zip">Download ZIP</a>
        <button id="sync-run" type="button">Sync &amp; Run</button>
        <button id="run-existing" class="secondary" type="button">Run existing</button>
      </div>
    </section>

    <section>
      <h2>Run log</h2>
      <pre id="log" aria-live="polite">Ready. Check mode is on by default.</pre>
    </section>
  </main>
  <script>
    const fields = ["host", "user", "key_path", "key_passphrase", "password", "remote_dir", "default_playbook"];
    const log = document.getElementById("log");
    const settingsStatus = document.getElementById("settings-status");
    const formValue = (id) => document.getElementById(id).value.trim();
    const isCheck = () => document.getElementById("check-mode").checked;
    const isConfirmed = () => document.getElementById("confirm-mutate").checked;

    function writeLog(message) {
      log.textContent = message || "No output returned.";
    }

    async function requestJson(path, options = {}) {
      const response = await fetch(path, options);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
      return data;
    }

    async function loadSettings() {
      try {
        const settings = await requestJson("/api/ansible-pad/settings");
        fields.forEach((field) => {
          if (settings[field] && settings[field] !== "***") {
            document.getElementById(field).value = settings[field];
          }
        });
        document.getElementById("existing-playbook").value = settings.default_playbook || "";
        settingsStatus.textContent = `Loaded control host ${settings.host || "plp5-dz5-nw"}.`;
      } catch (error) {
        settingsStatus.textContent = `Could not load settings: ${error.message}`;
      }
    }

    async function saveSettings() {
      const payload = {};
      fields.forEach((field) => {
        const value = formValue(field);
        if (value || !["password", "key_passphrase"].includes(field)) payload[field] = value;
      });
      try {
        const settings = await requestJson("/api/ansible-pad/settings", {
          method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
        });
        settingsStatus.textContent = `Saved settings for ${settings.host}.`;
      } catch (error) {
        settingsStatus.textContent = `Could not save settings: ${error.message}`;
      }
    }

    async function run(path, playbook) {
      if (!playbook) {
        writeLog("A playbook path is required.");
        return;
      }
      const check = isCheck();
      const confirm = isConfirmed();
      if (!check && !confirm) {
        writeLog("Mutating runs require “I confirm this mutating run”.");
        return;
      }
      writeLog(`Running ${playbook}${check ? " in check mode" : ""}...`);
      try {
        const result = await requestJson(path, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({playbook, check, confirm}),
        });
        writeLog([`Exit code: ${result.returncode}`, result.stdout, result.stderr].filter(Boolean).join("\\n\\n"));
      } catch (error) {
        writeLog(`Run failed: ${error.message}`);
      }
    }

    document.getElementById("save-settings").addEventListener("click", saveSettings);
    document.getElementById("sync-run").addEventListener("click", () => run(
      "/api/ansible-pad/sync-run", formValue("sync-playbook")
    ));
    document.getElementById("run-existing").addEventListener("click", () => run(
      "/api/ansible-pad/run-existing", formValue("existing-playbook")
    ));
    loadSettings();
  </script>
</body>
</html>
"""
"""Ansible Pad browser page."""

ANSIBLE_PAD_PATH = "/ansible-pad"

ANSIBLE_PAD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Ansible Pad</title>
  <style>
    :root { --bg:#0f1115; --panel:#171a21; --panel-alt:#1e222b; --border:#2a2f3a; --text:#e8eaf0; --sub:#98a1b3; --accent:#4f8cff; --warn:#e0a63b; --danger:#e05b5b; }
    * { box-sizing:border-box; } body { margin:0; padding:24px; background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif; }
    main { max-width:1000px; margin:auto; } header { display:flex; align-items:start; justify-content:space-between; gap:16px; margin-bottom:20px; }
    h1 { margin:0; font-size:1.7rem; } h2 { margin:0 0 14px; font-size:1.05rem; } p, .sub { color:var(--sub); } .sub { margin:6px 0 0; } a { color:var(--sub); } a:hover { color:var(--text); }
    section { margin:16px 0; padding:20px; border:1px solid var(--border); border-radius:12px; background:var(--panel); }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:12px; } label { display:grid; gap:6px; color:var(--sub); font-size:.85rem; }
    input { width:100%; padding:10px; border:1px solid var(--border); border-radius:8px; background:var(--panel-alt); color:var(--text); font:inherit; }
    .check { display:flex; align-items:center; gap:8px; margin:14px 0; color:var(--text); } .check input { width:auto; }
    .actions { display:flex; flex-wrap:wrap; gap:10px; align-items:center; } button { border:0; border-radius:8px; padding:10px 14px; background:var(--accent); color:#fff; font:inherit; font-weight:600; cursor:pointer; }
    button.secondary { background:var(--panel-alt); border:1px solid var(--border); } button.warn { background:#8b5a11; } button:disabled { cursor:not-allowed; opacity:.6; }
    .hint { margin:10px 0 0; color:var(--warn); font-size:.85rem; } pre { min-height:180px; max-height:420px; overflow:auto; margin:0; padding:14px; border-radius:8px; background:#090b0f; color:#d9e2f2; white-space:pre-wrap; word-break:break-word; }
    .footer { margin-top:22px; color:var(--sub); font-size:.8rem; } @media (max-width:600px) { body { padding:16px; } header { flex-direction:column; } }
  </style>
</head>
<body>
  <main>
    <header>
      <div><h1>Ansible Pad</h1><p class="sub">Generate, sync, and run LaunchPad automation through the Ansible control host <strong>plp5-dz5-nw</strong>.</p></div>
      <a href="/">Health Dashboard</a>
    </header>
    <section>
      <h2>Control host settings</h2>
      <div class="grid">
        <label>Host<input id="host" autocomplete="off"></label>
        <label>User<input id="user" autocomplete="username"></label>
        <label>Remote directory<input id="remote_dir" placeholder="/srv/launchpad"></label>
        <label>SSH key path<input id="key_path" placeholder="Optional key path"></label>
        <label>Password<input id="password" type="password" placeholder="Leave unchanged to retain saved password" autocomplete="current-password"></label>
        <label>Key passphrase<input id="key_passphrase" type="password" placeholder="Leave unchanged to retain saved passphrase"></label>
      </div>
      <div class="actions" style="margin-top:14px"><button id="save-settings" class="secondary" type="button">Save settings</button><span id="settings-status" class="sub"></span></div>
    </section>
    <section>
      <h2>Package and run</h2>
      <div class="grid">
        <label>Generated package playbook<input id="playbook" value="playbooks/start_fc_consistgrp.yml"></label>
        <label>Existing remote playbook<input id="existing-playbook" placeholder="/opt/runbooks/existing.yml"></label>
      </div>
      <label class="check"><input id="check" type="checkbox" checked> Sync &amp; Run in check mode (safe default)</label>
      <label class="check"><input id="confirm" type="checkbox"> I confirm this run may mutate the target arrays</label>
      <p class="hint">Turning off check mode requires confirmation. Download ZIP never changes the control host or arrays.</p>
      <div class="actions">
        <button id="download" class="secondary" type="button">Download ZIP</button>
        <button id="sync-run" type="button">Sync &amp; Run</button>
        <button id="run-existing" class="warn" type="button">Run existing</button>
      </div>
    </section>
    <section><h2>Run log</h2><pre id="log" aria-live="polite">Ready.</pre></section>
    <div class="footer">LaunchPad {{APP_VERSION}}</div>
  </main>
  <script>
    const fields = ["host", "user", "remote_dir", "key_path", "password", "key_passphrase"];
    const logEl = document.getElementById("log");
    const checkEl = document.getElementById("check");
    const confirmEl = document.getElementById("confirm");
    const playbookEl = document.getElementById("playbook");
    const existingEl = document.getElementById("existing-playbook");
    function log(value) { logEl.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2); }
    async function request(url, options) {
      const response = await fetch(url, options);
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.error) throw new Error(payload.error || ("Request failed (" + response.status + ")"));
      return payload;
    }
    async function loadSettings() {
      try {
        const settings = await request("/api/ansible-pad/settings");
        fields.forEach((field) => {
          const element = document.getElementById(field);
          if (element && settings[field] != null) element.value = settings[field] === "***" ? "" : settings[field];
        });
        if (settings.default_playbook) playbookEl.value = settings.default_playbook;
      } catch (error) { log("Could not load settings: " + error.message); }
    }
    document.getElementById("save-settings").addEventListener("click", async () => {
      const status = document.getElementById("settings-status");
      status.textContent = "Saving…";
      const payload = {};
      fields.forEach((field) => {
        const element = document.getElementById(field);
        if (element && (field !== "password" && field !== "key_passphrase" || element.value)) payload[field] = element.value;
      });
      payload.default_playbook = playbookEl.value;
      try { await request("/api/ansible-pad/settings", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload) }); status.textContent = "Saved."; }
      catch (error) { status.textContent = "Save failed."; log(error.message); }
    });
    document.getElementById("download").addEventListener("click", () => { window.location.assign("/api/ansible-pad/export.zip"); });
    async function run(endpoint, payload) {
      log("Running…");
      try { log(await request(endpoint, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload) })); }
      catch (error) { log("Run failed: " + error.message); }
    }
    document.getElementById("sync-run").addEventListener("click", () => run("/api/ansible-pad/sync-run", { playbook:playbookEl.value, check:checkEl.checked, confirm:confirmEl.checked }));
    document.getElementById("run-existing").addEventListener("click", () => run("/api/ansible-pad/run-existing", { playbook:existingEl.value, check:checkEl.checked, confirm:confirmEl.checked }));
    loadSettings();
  </script>
</body>
</html>"""
