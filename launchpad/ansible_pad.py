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
        writeLog("Mutating runs require \"I confirm this mutating run\".");
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
