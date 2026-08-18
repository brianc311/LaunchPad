"""Call Home CLI page — contact, location, SMTP add/remove."""

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
      <p class="lede">Set shared contact and per-array location. Optionally add an SMTP server. Remove SMTP deletes email users and servers only — Cloud Call Home, contact, and location stay. Preview first. The first CLI error stops that array; other arrays continue. No rollback.</p>
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
      <h2>SMTP add (optional)</h2>
      <p class="hint">Leave empty to skip. If any field is filled, IP and port are required. Password is never stored.</p>
      <div class="grid">
        <label>IP or hostname <input id="smtp-ip"></label>
        <label>Port <input id="smtp-port"></label>
        <label>Username <input id="smtp-username"></label>
        <label>Password <input id="smtp-password" type="password"></label>
      </div>
      <div class="actions">
        <button type="button" class="secondary" id="select-all-btn">Select all</button>
        <button type="button" class="secondary" id="select-none-btn">Select none</button>
        <button type="button" class="secondary" id="load-btn">Load current</button>
        <button type="button" class="secondary" id="preview-apply-btn">Preview Apply</button>
        <button type="button" class="danger" id="run-apply-btn" disabled>Run Apply</button>
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
    const runApplyBtn = document.getElementById("run-apply-btn");
    const runRemoveBtn = document.getElementById("run-remove-btn");
    const modal = document.getElementById("modal");
    const modalBody = document.getElementById("modal-body");
    const modalTitle = document.getElementById("modal-title");
    const LOC = ["company","street","city","state","postal","country","comment"];
    let cards = [];
    window.__applyOk = false; window.__applyHash = "";
    window.__removeOk = false; window.__removeHash = "";

    function invalidatePreview() {
      window.__applyOk = false; window.__applyHash = "";
      window.__removeOk = false; window.__removeHash = "";
      runApplyBtn.disabled = true; runRemoveBtn.disabled = true;
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
    function smtpPayload() {
      return {
        ip: document.getElementById("smtp-ip").value,
        port: document.getElementById("smtp-port").value,
        username: document.getElementById("smtp-username").value,
        password: document.getElementById("smtp-password").value
      };
    }
    function locPayload(id) {
      const out = {};
      LOC.forEach((k) => { const el = document.getElementById("loc-" + k + "-" + id); out[k] = el ? el.value : ""; });
      return out;
    }
    function applyPayload() {
      return { contact: contactPayload(), smtp: smtpPayload(), arrays: selectedIds().map((id) => ({ card_id: id, location: locPayload(id) })) };
    }
    function removePayload() {
      return { arrays: selectedIds().map((id) => ({ card_id: id })) };
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
    function render() {
      if (!cards.length) { arraysEl.innerHTML = '<p class="hint">No IBM FlashSystem / SVC SSH cards.</p>'; return; }
      arraysEl.innerHTML = cards.map((card) => {
        const checked = document.querySelector('.array-check[data-card-id="'+card.id+'"]');
        const on = checked ? checked.checked : false;
        const loc = locPayload(card.id);
        const cloud = document.getElementById("cloud-" + card.id);
        const smtp = document.getElementById("smtp-sum-" + card.id);
        return '<div class="array" data-card-id="'+card.id+'">'
          + '<div class="array-head"><label><input class="array-check" type="checkbox" data-card-id="'+card.id+'"'+(on?" checked":"")+'> '+card.name+'</label>' + arrayHostLink(card.host)
          + '<span class="hint" id="cloud-'+card.id+'">'+(cloud ? cloud.textContent : "Cloud Call Home: —")+'</span></div>'
          + '<p class="hint" id="smtp-sum-'+card.id+'">'+(smtp ? smtp.textContent : "SMTP: —")+'</p>'
          + '<div class="grid">'
          + LOC.map((k) => '<label>'+k+' <input id="loc-'+k+'-'+card.id+'" value="'+(loc[k]||"").replace(/"/g,"")+'"></label>').join("")
          + '</div></div>';
      }).join("");
      arraysEl.querySelectorAll("input").forEach((el) => el.addEventListener("input", invalidatePreview));
      arraysEl.querySelectorAll(".array-check").forEach((el) => el.addEventListener("change", invalidatePreview));
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
      const url = kind === "apply" ? "/api/call-home/preview-apply" : "/api/call-home/preview-remove";
      const body = kind === "apply" ? applyPayload() : removePayload();
      try {
        const res = await fetch(url, { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify(body) });
        const data = await res.json();
        showModal(kind === "apply" ? "Preview Apply" : "Preview Remove SMTP", previewLines(data));
        if (kind === "apply") {
          window.__applyOk = !!data.ok; window.__applyHash = data.preview_hash || "";
          runApplyBtn.disabled = !window.__applyOk;
        } else {
          window.__removeOk = !!data.ok; window.__removeHash = data.preview_hash || "";
          runRemoveBtn.disabled = !window.__removeOk;
        }
        statusEl.textContent = data.ok ? "Preview succeeded." : "Preview found blocking errors.";
      } catch (err) { statusEl.textContent = "Preview failed: " + (err.message || err); }
    }
    document.getElementById("select-all-btn").onclick = () => { document.querySelectorAll(".array-check").forEach((el) => { el.checked = true; }); invalidatePreview(); };
    document.getElementById("select-none-btn").onclick = () => { document.querySelectorAll(".array-check").forEach((el) => { el.checked = false; }); invalidatePreview(); };
    document.getElementById("load-btn").onclick = () => loadCurrent();
    document.getElementById("preview-apply-btn").onclick = () => doPreview("apply");
    document.getElementById("preview-remove-btn").onclick = () => doPreview("remove");
    ["contact-name","contact-reply","contact-primary","contact-alternate","smtp-ip","smtp-port","smtp-username","smtp-password"].forEach((id) => {
      document.getElementById(id).addEventListener("input", invalidatePreview);
    });
    document.getElementById("modal-close").onclick = () => { modal.hidden = true; };
    document.getElementById("run-apply-btn").onclick = async () => {
      if (!window.__applyOk) return;
      if (!confirm("This writes Call Home contact/location and optional SMTP add on the selected arrays. The first CLI error stops that array; other arrays continue. No rollback.")) return;
      runApplyBtn.disabled = true; window.__applyOk = false;
      const body = Object.assign(applyPayload(), { confirm: true, preview_hash: window.__applyHash });
      try {
        const res = await fetch("/api/call-home/run-apply", { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify(body) });
        const data = await res.json();
        showModal("Run Apply", previewLines(data));
        statusEl.textContent = (data.ok && !runHadArrayErrors(data)) ? "Apply finished." : "Apply finished with errors.";
      } catch (err) { statusEl.textContent = "Apply failed: " + (err.message || err); }
    };
    document.getElementById("run-remove-btn").onclick = async () => {
      if (!window.__removeOk) return;
      if (!confirm("This stops email sending and deletes email users and email servers on the selected arrays. Cloud Call Home, contact, and location are not changed.")) return;
      runRemoveBtn.disabled = true; window.__removeOk = false;
      const body = Object.assign(removePayload(), { confirm: true, preview_hash: window.__removeHash });
      try {
        const res = await fetch("/api/call-home/run-remove", { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify(body) });
        const data = await res.json();
        showModal("Run Remove SMTP", previewLines(data));
        statusEl.textContent = (data.ok && !runHadArrayErrors(data)) ? "Remove finished." : "Remove finished with errors.";
      } catch (err) { statusEl.textContent = "Remove failed: " + (err.message || err); }
    };
    loadCards();
  </script>
</body>
</html>"""
