"""Call Home CLI page — contact, location, SMTP, users, Cloud."""

CALL_HOME_CLI_PATH = "/call-home-cli"

CALL_HOME_CLI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Call Home CLI</title>
  <style>
    :root { --bg:#0b0f14; --panel:#121821; --text:#e8edf5; --muted:#8b98ab; --accent:#ff6b00; --accent2:#ff8533; --ok:#4ade80; --border:#2a3444; --card:#151c27; --danger:#f87171; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; color:var(--text); font-family:Segoe UI,Inter,Arial,sans-serif; background:radial-gradient(circle at top,#172033 0%,var(--bg) 45%); }
    .wrap { max-width:1280px; margin:0 auto; padding:28px 20px 48px; }
    .hero, .section { background:var(--card); border:1px solid var(--border); border-radius:16px; padding:20px; margin-bottom:18px; }
    .hero { background:linear-gradient(135deg,#1a2230 0%,#101722 100%); }
    h1 { margin:0 0 8px; color:var(--accent); font-size:1.85rem; }
    h2 { margin:0 0 10px; color:var(--accent2); font-size:1.05rem; }
    p, .lede, .hint, .footer { color:var(--muted); line-height:1.45; }
    a:not(.btn) { color:#9ec1ff; text-decoration:underline; text-underline-offset:2px; }
    .actions { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:14px; }
    button, .btn { min-height:34px; padding:0 14px; border:0; border-radius:10px; background:var(--accent); color:#111; font:inherit; font-weight:600; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; justify-content:center; }
    button.secondary, .btn.secondary { color:var(--text); background:#0f141d; border:1px solid var(--border); }
    button.danger { color:#fff; background:#b91c1c; }
    button:disabled { cursor:not-allowed; opacity:.6; }
    input { color:var(--text); background:#0f141d; border:1px solid var(--border); border-radius:8px; padding:6px 9px; font:inherit; }
    select { color:var(--text); background:#0f141d; border:1px solid var(--border); border-radius:8px; padding:6px 9px; font:inherit; }
    label { color:var(--muted); font-size:.85rem; font-weight:600; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:8px; }
    .array { border:1px solid var(--border); border-radius:12px; padding:12px; margin-top:10px; background:#0f141d; }
    .array-head { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
    .modal-backdrop { position:fixed; inset:0; z-index:10; display:grid; place-items:center; padding:20px; background:rgba(0,0,0,.72); }
    .modal-backdrop[hidden] { display:none !important; }
    .modal { width:min(900px,100%); max-height:85vh; overflow:auto; padding:20px; border:1px solid var(--border); border-radius:14px; background:var(--panel); }
    pre { margin:0; padding:12px; overflow:auto; border:1px solid var(--border); border-radius:8px; background:#0b0f14; color:#d8e3f2; white-space:pre-wrap; }
    .warning { margin:8px 0; padding:9px 10px; border-left:3px solid var(--danger); background:#32151a; color:#fecaca; }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <h1>Call Home CLI</h1>
      <p class="lede">Set shared contact and per-array location, SMTP, email users, and Cloud Call Home. Each action has its own Preview and Run. Remove SMTP deletes email users and servers only. Preview first. The first CLI error stops that array; other arrays continue. No rollback.</p>
      <div class="actions">
        <a class="btn secondary" href="/">Health Dashboard</a>
        <a class="btn secondary" href="/system-connectivity">System Connectivity</a>
      </div>
    </section>
    <section class="section">
      <h2>Shared contact</h2>
      <div class="grid">
        <label>Name <input id="contact-name"></label>
        <label>Reply email <input id="contact-reply"></label>
        <label>Primary phone <input id="contact-primary"></label>
        <label>Alternate phone <input id="contact-alternate"></label>
      </div>
      <div class="actions">
        <button type="button" class="secondary" id="select-all-btn">Select all</button>
        <button type="button" class="secondary" id="select-none-btn">Select none</button>
        <button type="button" class="secondary" id="load-btn">Load current</button>
        <button type="button" class="secondary" id="preview-apply-btn">Preview Contact</button>
        <button type="button" class="danger" id="run-apply-btn" disabled>Run Contact</button>
        <button type="button" class="secondary" id="preview-smtp-btn">Preview SMTP</button>
        <button type="button" class="danger" id="run-smtp-btn" disabled>Run SMTP</button>
        <button type="button" class="secondary" id="preview-testemail-btn">Preview Test Email</button>
        <button type="button" class="danger" id="run-testemail-btn" disabled>Run Test Email</button>
        <button type="button" class="secondary" id="preview-users-btn">Preview Users</button>
        <button type="button" class="danger" id="run-users-btn" disabled>Run Users</button>
        <button type="button" class="secondary" id="preview-cloud-btn">Preview Cloud</button>
        <button type="button" class="danger" id="run-cloud-btn" disabled>Run Cloud</button>
        <button type="button" class="secondary" id="preview-remove-btn">Preview Remove SMTP</button>
        <button type="button" class="danger" id="run-remove-btn" disabled>Run Remove SMTP</button>
        <span class="hint" id="status"></span>
      </div>
      <div id="arrays"><p class="hint">Loading arrays…</p></div>
    </section>
  </main>
  <div class="modal-backdrop" id="modal" hidden>
    <div class="modal">
      <h2 id="modal-title">Preview</h2>
      <pre id="modal-body"></pre>
      <div class="actions"><button type="button" class="secondary" id="modal-close">Close</button></div>
    </div>
  </div>
  <p class="footer wrap">LaunchPad {{APP_VERSION}}</p>
  <script>
    const arraysEl = document.getElementById("arrays");
    const statusEl = document.getElementById("status");
    const modal = document.getElementById("modal");
    const modalBody = document.getElementById("modal-body");
    const modalTitle = document.getElementById("modal-title");
    const LOC = ["company","street","city","state","postal","country","comment"];
    const KINDS = ["apply","smtp","testemail","users","cloud","remove"];
    const runBtns = {};
    KINDS.forEach((k) => { runBtns[k] = document.getElementById(k === "apply" ? "run-apply-btn" : k === "remove" ? "run-remove-btn" : "run-"+k+"-btn"); });
    const PREVIEW_URL = { apply:"/api/call-home/preview-apply", smtp:"/api/call-home/preview-smtp", testemail:"/api/call-home/preview-testemail", users:"/api/call-home/preview-users", cloud:"/api/call-home/preview-cloud", remove:"/api/call-home/preview-remove" };
    const RUN_URL = { apply:"/api/call-home/run-apply", smtp:"/api/call-home/run-smtp", testemail:"/api/call-home/run-testemail", users:"/api/call-home/run-users", cloud:"/api/call-home/run-cloud", remove:"/api/call-home/run-remove" };
    const PREVIEW_TITLE = { apply:"Preview Contact", smtp:"Preview SMTP", testemail:"Preview Test Email", users:"Preview Users", cloud:"Preview Cloud", remove:"Preview Remove SMTP" };
    const RUN_TITLE = { apply:"Run Contact", smtp:"Run SMTP", testemail:"Run Test Email", users:"Run Users", cloud:"Run Cloud", remove:"Run Remove SMTP" };
    const STATUS_KIND = { apply:"Contact", smtp:"SMTP", testemail:"Test Email", users:"Users", cloud:"Cloud", remove:"Remove" };
    const CONFIRMS = {
      apply: "This writes Call Home contact/location on the selected arrays. The first CLI error stops that array; other arrays continue. No rollback.",
      smtp: "This writes SMTP (add or change the email server) on the selected arrays. The first CLI error stops that array; other arrays continue. No rollback.",
      testemail: "This sends a test email through the SMTP already on the selected arrays. It does not change SMTP, users, contact, or Cloud Call Home. The first CLI error stops that array; other arrays continue. No rollback.",
      users: "This writes Call Home email users on the selected arrays. The first CLI error stops that array; other arrays continue. No rollback.",
      cloud: "This enables or disables Cloud Call Home on the selected arrays. The first CLI error stops that array; other arrays continue. No rollback.",
      remove: "This stops email sending and deletes email users and email servers on the selected arrays. Cloud Call Home, contact, and location are not changed."
    };
    let cards = [];
    window.__applyOk = false; window.__applyHash = "";
    window.__smtpOk = false; window.__smtpHash = "";
    window.__testemailOk = false; window.__testemailHash = "";
    window.__usersOk = false; window.__usersHash = "";
    window.__cloudOk = false; window.__cloudHash = "";
    window.__removeOk = false; window.__removeHash = "";

    function invalidatePreview() {
      KINDS.forEach((k) => { window["__"+k+"Ok"] = false; window["__"+k+"Hash"] = ""; runBtns[k].disabled = true; });
    }
    function showModal(title, text) { modalTitle.textContent = title; modalBody.textContent = text; modal.hidden = false; }
    function arrayHostLink(host) {
      const raw = String(host || "").trim();
      if (!raw) return "";
      const lower = raw.toLowerCase();
      const href = (lower.startsWith("https://") || lower.startsWith("http://")) ? raw : ("https://" + raw);
      return ' <a class="array-ip-link" href="' + href + '" target="_blank" rel="noopener">' + raw + '</a>';
    }
    function selectedIds() {
      return [...document.querySelectorAll(".array-check:checked")].map((el) => Number(el.dataset.cardId));
    }
    function contactPayload() {
      return {
        name: document.getElementById("contact-name").value,
        reply: document.getElementById("contact-reply").value,
        primary: document.getElementById("contact-primary").value,
        alternate: document.getElementById("contact-alternate").value
      };
    }
    function smtpPayload(id) {
      return {
        ip: (document.getElementById("smtp-ip-"+id)||{}).value || "",
        port: (document.getElementById("smtp-port-"+id)||{}).value || "",
        username: (document.getElementById("smtp-username-"+id)||{}).value || "",
        password: (document.getElementById("smtp-password-"+id)||{}).value || ""
      };
    }
    function usersPayload(id) {
      const remove_ids = [...document.querySelectorAll(".user-rm[data-card-id='"+id+"']:checked")].map((el) => el.dataset.userId);
      const add = [];
      const addr = document.getElementById("user-add-addr-"+id);
      const typ = document.getElementById("user-add-type-"+id);
      if (addr && addr.value.trim()) add.push({ address: addr.value, user_type: typ ? typ.value : "local" });
      return { card_id: id, remove_ids, add };
    }
    function locPayload(id) {
      const out = {};
      LOC.forEach((k) => { const el = document.getElementById("loc-" + k + "-" + id); out[k] = el ? el.value : ""; });
      return out;
    }
    function applyPayload() {
      return { contact: contactPayload(), arrays: selectedIds().map((id) => ({ card_id: id, location: locPayload(id) })) };
    }
    function smtpKindPayload() {
      return { arrays: selectedIds().map((id) => ({ card_id: id, smtp: smtpPayload(id) })) };
    }
    function usersKindPayload() {
      return { arrays: selectedIds().map((id) => usersPayload(id)) };
    }
    function cloudKindPayload() {
      return { arrays: selectedIds().map((id) => ({ card_id: id, requested: (document.getElementById("cloud-req-"+id)||{}).value || "enable" })) };
    }
    function removePayload() {
      return { arrays: selectedIds().map((id) => ({ card_id: id })) };
    }
    function testemailKindPayload() {
      return {
        arrays: selectedIds().map((id) => {
          const sel = document.getElementById("test-user-" + id);
          const opt = sel && sel.selectedOptions && sel.selectedOptions[0];
          return {
            card_id: id,
            user_id: sel ? (sel.value || "") : "",
            address: opt ? (opt.getAttribute("data-address") || "") : ""
          };
        })
      };
    }
    function kindPayload(kind) {
      if (kind === "apply") return applyPayload();
      if (kind === "smtp") return smtpKindPayload();
      if (kind === "testemail") return testemailKindPayload();
      if (kind === "users") return usersKindPayload();
      if (kind === "cloud") return cloudKindPayload();
      return removePayload();
    }
    function contactEmpty() {
      const c = contactPayload();
      return !c.name && !c.reply && !c.primary && !c.alternate;
    }
    function fillContact(c) {
      if (!c) return;
      document.getElementById("contact-name").value = c.name || "";
      document.getElementById("contact-reply").value = c.reply || "";
      document.getElementById("contact-primary").value = c.primary || "";
      document.getElementById("contact-alternate").value = c.alternate || "";
    }
    function fillLoc(id, loc) {
      if (!loc) return;
      LOC.forEach((k) => { const el = document.getElementById("loc-" + k + "-" + id); if (el) el.value = loc[k] || ""; });
    }
    function fillUsers(id, users) {
      const el = document.getElementById("users-" + id);
      if (!el) return;
      const rows = (users || []).map((u) => {
        const uid = String(u.id || u.name || "").replace(/"/g, "");
        const addr = String(u.address || "").replace(/"/g, "");
        const typ = String(u.user_type || "").replace(/"/g, "");
        return '<div><label><input class="user-rm" type="checkbox" data-card-id="'+id+'" data-user-id="'+uid+'"> '+addr+' ('+typ+')</label></div>';
      }).join("");
      const add = '<div class="grid"><label>Add address <input id="user-add-addr-'+id+'"></label>'
        + '<label>Type <select id="user-add-type-'+id+'"><option value="support">support</option><option value="local">local</option></select></label></div>';
      const selected = (document.getElementById("test-user-"+id)||{}).value || "";
      const opts = ['<option value="">Select user</option>'].concat((users || []).map((u) => {
        const uid = String(u.id || u.name || "").replace(/"/g, "");
        const addr = String(u.address || "").replace(/"/g, "");
        const typ = String(u.user_type || "").replace(/"/g, "");
        const sel = uid === selected ? " selected" : "";
        return '<option value="'+uid+'" data-address="'+addr+'"'+sel+'>'+addr+' ('+typ+')</option>';
      }));
      const testSel = '<label>Test user <select id="test-user-'+id+'">'+opts.join("")+'</select></label>';
      el.innerHTML = rows + add + testSel;
      el.querySelectorAll("input,select").forEach((node) => {
        node.addEventListener("input", invalidatePreview);
        node.addEventListener("change", invalidatePreview);
      });
    }
    function render() {
      if (!cards.length) { arraysEl.innerHTML = '<p class="hint">No IBM FlashSystem / SVC SSH cards.</p>'; return; }
      arraysEl.innerHTML = cards.map((card) => {
        const checked = document.querySelector('.array-check[data-card-id="'+card.id+'"]');
        const on = checked ? checked.checked : false;
        const loc = locPayload(card.id);
        const smtpNow = smtpPayload(card.id);
        const cloud = document.getElementById("cloud-" + card.id);
        const smtp = document.getElementById("smtp-sum-" + card.id);
        const cloudReq = document.getElementById("cloud-req-" + card.id);
        const cloudReqVal = cloudReq ? cloudReq.value : "enable";
        const usersBox = document.getElementById("users-" + card.id);
        const usersHtml = usersBox ? usersBox.innerHTML : "";
        return '<div class="array" data-card-id="'+card.id+'">'
          + '<div class="array-head"><label><input class="array-check" type="checkbox" data-card-id="'+card.id+'"'+(on?" checked":"")+'> '+card.name+'</label>' + arrayHostLink(card.host)
          + '<span class="hint" id="cloud-'+card.id+'">'+(cloud ? cloud.textContent : "Cloud Call Home: —")+'</span>'
          + '<label>Cloud <select id="cloud-req-'+card.id+'"><option value="enable"'+(cloudReqVal==="enable"?" selected":"")+'>Enable</option><option value="disable"'+(cloudReqVal==="disable"?" selected":"")+'>Disable</option></select></label></div>'
          + '<p class="hint" id="smtp-sum-'+card.id+'">'+(smtp ? smtp.textContent : "SMTP: —")+'</p>'
          + '<div class="grid">'
          + '<label>IP or hostname <input id="smtp-ip-'+card.id+'" value="'+(smtpNow.ip||"").replace(/"/g,"")+'"></label>'
          + '<label>Port <input id="smtp-port-'+card.id+'" value="'+(smtpNow.port||"").replace(/"/g,"")+'"></label>'
          + '<label>Username <input id="smtp-username-'+card.id+'" value="'+(smtpNow.username||"").replace(/"/g,"")+'"></label>'
          + '<label>Password <input id="smtp-password-'+card.id+'" type="password" value="'+(smtpNow.password||"").replace(/"/g,"")+'"></label>'
          + '</div>'
          + '<div id="users-'+card.id+'">'+usersHtml+'</div>'
          + '<div class="grid">'
          + LOC.map((k) => '<label>'+k+' <input id="loc-'+k+'-'+card.id+'" value="'+(loc[k]||"").replace(/"/g,"")+'"></label>').join("")
          + '</div></div>';
      }).join("");
      arraysEl.querySelectorAll("input,select").forEach((el) => {
        el.addEventListener("input", invalidatePreview);
        el.addEventListener("change", invalidatePreview);
      });
      cards.forEach((card) => {
        const usersBox = document.getElementById("users-" + card.id);
        if (usersBox && !usersBox.innerHTML.trim()) fillUsers(card.id, []);
      });
    }
    async function loadCards() {
      try {
        const res = await fetch("/api/call-home/cards");
        const data = await res.json();
        cards = data.cards || [];
        render();
      } catch (err) { arraysEl.innerHTML = '<p class="warning">'+(err.message||err)+'</p>'; }
    }
    async function loadCurrent() {
      invalidatePreview();
      statusEl.textContent = "Loading…";
      let ids = selectedIds();
      if (!ids.length) ids = cards.map((c) => c.id);
      let filledShared = !contactEmpty();
      for (const id of ids) {
        try {
          const res = await fetch("/api/call-home/state", { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify({ card_id: id }) });
          const data = await res.json();
          const cloud = document.getElementById("cloud-" + id);
          const smtp = document.getElementById("smtp-sum-" + id);
          if (!data.ok) {
            if (cloud) cloud.textContent = data.error || "Load failed";
            continue;
          }
          if (cloud) cloud.textContent = "Cloud Call Home: " + (data.cloud_status || data.cloud_details || "unknown");
          if (smtp) smtp.textContent = "SMTP: " + (data.smtp_summary || "none");
          const req = document.getElementById("cloud-req-" + id);
          if (req) req.value = data.cloud_configured === "yes" ? "enable" : "disable";
          const srv = (data.servers && data.servers[0]) || null;
          const ipEl = document.getElementById("smtp-ip-" + id);
          const portEl = document.getElementById("smtp-port-" + id);
          const userEl = document.getElementById("smtp-username-" + id);
          const passEl = document.getElementById("smtp-password-" + id);
          if (ipEl) ipEl.value = srv ? (srv.ip || "") : "";
          if (portEl) portEl.value = srv ? (srv.port || "") : "";
          if (userEl) userEl.value = srv ? (srv.username || "") : "";
          if (passEl) passEl.value = "";
          fillUsers(id, data.users);
          fillLoc(id, data.location);
          if (!filledShared) { fillContact(data.contact); filledShared = true; }
        } catch (err) {
          const cloud = document.getElementById("cloud-" + id);
          if (cloud) cloud.textContent = err.message || String(err);
        }
      }
      statusEl.textContent = "Load current finished.";
    }
    function runHadArrayErrors(data) {
      return (data.arrays || []).some((row) => row.ok === false);
    }
    function previewLines(data) {
      const lines = [];
      (data.arrays || []).forEach((row) => {
        lines.push("# " + (row.name || row.card_id) + " runnable=" + row.runnable + " ok=" + row.ok);
        (row.warnings || []).forEach((w) => lines.push(w));
        (row.steps || []).forEach((s) => lines.push(s.cmd));
        (row.log || []).forEach((entry) => {
          lines.push((entry.cmd || "") + " ok=" + entry.ok);
          if (entry.error) lines.push(entry.error);
          else if (entry.output) lines.push(entry.output);
        });
        lines.push("");
      });
      (data.warnings || []).forEach((w) => lines.push(w));
      return lines.join("\\n") || JSON.stringify(data, null, 2);
    }
    async function doPreview(kind) {
      invalidatePreview();
      statusEl.textContent = "Preview…";
      const url = PREVIEW_URL[kind];
      const body = kindPayload(kind);
      try {
        const res = await fetch(url, { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify(body) });
        const data = await res.json();
        showModal(PREVIEW_TITLE[kind] || "Preview", previewLines(data));
        window["__"+kind+"Ok"] = !!data.ok;
        window["__"+kind+"Hash"] = data.preview_hash || "";
        if (runBtns[kind]) runBtns[kind].disabled = !window["__"+kind+"Ok"];
        statusEl.textContent = data.ok ? "Preview succeeded." : "Preview found blocking errors.";
      } catch (err) { statusEl.textContent = "Preview failed: " + (err.message || err); }
    }
    async function doRun(kind) {
      if (!window["__"+kind+"Ok"]) return;
      if (!confirm(CONFIRMS[kind])) return;
      runBtns[kind].disabled = true;
      window["__"+kind+"Ok"] = false;
      const body = Object.assign(kindPayload(kind), { confirm: true, preview_hash: window["__"+kind+"Hash"] });
      const label = STATUS_KIND[kind] || kind;
      try {
        const res = await fetch(RUN_URL[kind], { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify(body) });
        const data = await res.json();
        showModal(RUN_TITLE[kind] || "Run", previewLines(data));
        statusEl.textContent = (data.ok && !runHadArrayErrors(data)) ? (label + " finished.") : (label + " finished with errors.");
      } catch (err) { statusEl.textContent = label + " failed: " + (err.message || err); }
    }
    document.getElementById("select-all-btn").onclick = () => { document.querySelectorAll(".array-check").forEach((el) => { el.checked = true; }); invalidatePreview(); };
    document.getElementById("select-none-btn").onclick = () => { document.querySelectorAll(".array-check").forEach((el) => { el.checked = false; }); invalidatePreview(); };
    document.getElementById("load-btn").onclick = () => loadCurrent();
    document.getElementById("preview-apply-btn").onclick = () => doPreview("apply");
    document.getElementById("preview-smtp-btn").onclick = () => doPreview("smtp");
    document.getElementById("preview-testemail-btn").onclick = () => doPreview("testemail");
    document.getElementById("preview-users-btn").onclick = () => doPreview("users");
    document.getElementById("preview-cloud-btn").onclick = () => doPreview("cloud");
    document.getElementById("preview-remove-btn").onclick = () => doPreview("remove");
    KINDS.forEach((k) => { runBtns[k].onclick = () => doRun(k); });
    ["contact-name","contact-reply","contact-primary","contact-alternate"].forEach((id) => {
      document.getElementById(id).addEventListener("input", invalidatePreview);
    });
    document.getElementById("modal-close").onclick = () => { modal.hidden = true; };
    loadCards();
  </script>
</body>
</html>"""
