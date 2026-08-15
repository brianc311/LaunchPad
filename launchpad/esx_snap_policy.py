"""ESX-snap snapshot policy and per-site volume group page."""

ESX_SNAP_POLICY_PATH = "/esx-snap-policy"

ESX_SNAP_POLICY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad ESX-snap Policy</title>
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
    a:not(.btn):hover { color:#c5d9ff; }
    .actions { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:14px; }
    button, .btn { min-height:34px; padding:0 14px; border:0; border-radius:10px; background:var(--accent); color:#111; font:inherit; font-weight:600; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; justify-content:center; }
    button.secondary, .btn.secondary { color:var(--text); background:#0f141d; border:1px solid var(--border); }
    button.danger { color:#fff; background:#b91c1c; }
    button:disabled { cursor:not-allowed; opacity:.6; }
    input { color:var(--text); background:#0f141d; border:1px solid var(--border); border-radius:8px; padding:6px 9px; font:inherit; }
    label { color:var(--muted); font-size:.85rem; font-weight:600; }
    .array { border:1px solid var(--border); border-radius:12px; padding:12px; margin-top:10px; background:#0f141d; }
    .array-head { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
    table { width:100%; border-collapse:collapse; margin-top:8px; }
    th, td { padding:6px; text-align:left; border:1px solid var(--border); }
    th { color:var(--muted); font-size:.78rem; }
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
      <h1>ESX-snap Policy</h1>
      <p class="lede">Create IBM snapshot policy ESX-snap (daily, keep 7 days) and a per-site volume group. Preview / Dry-run first. Run Create mutates selected arrays. Creating objects is operator-initiated. The policy schedules snapshots; Run does not create snapshots immediately.</p>
      <div class="actions">
        <a class="btn secondary" href="/">Health Dashboard</a>
        <a class="btn secondary" href="/snapshot-schedule">Snapshot Schedule</a>
        <a class="btn secondary" href="/fc-consistgrp">FlashCopy CGs</a>
      </div>
    </section>
    <section class="section">
      <h2>Policy</h2>
      <p>Name <strong>ESX-snap</strong> · daily · keep 7 days · start
        <input id="start-time" value="02:00" size="6" aria-label="Start time">
      </p>
      <div class="actions">
        <button type="button" class="secondary" id="select-all-btn">Select all</button>
        <button type="button" class="secondary" id="select-none-btn">Select none</button>
        <button type="button" class="secondary" id="preview-btn">Preview / Dry-run</button>
        <button type="button" class="danger" id="run-btn" disabled>Run Create</button>
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
    const startEl = document.getElementById("start-time");
    const runBtn = document.getElementById("run-btn");
    const modal = document.getElementById("modal");
    const modalBody = document.getElementById("modal-body");
    const modalTitle = document.getElementById("modal-title");
    let cards = [];
    const volumesByCard = {};
    const vgByCard = {};
    window.__esxPreviewOk = false;
    window.__esxPreviewHash = "";

    function invalidatePreview() {
      window.__esxPreviewOk = false;
      window.__esxPreviewHash = "";
      runBtn.disabled = true;
    }

    function showModal(title, text) {
      modalTitle.textContent = title;
      modalBody.textContent = text;
      modal.hidden = false;
    }

    async function loadCards() {
      const res = await fetch("/api/esx-snap-policy/cards");
      const data = await res.json();
      cards = data.cards || [];
      render();
    }

    function selectedIds() {
      return [...document.querySelectorAll(".array-check:checked")].map((el) => Number(el.dataset.cardId));
    }

    function arrayPayload() {
      return selectedIds().map((id) => {
        const vg = document.getElementById("vg-" + id);
        const names = [...document.querySelectorAll(".vol-" + id + ":checked")].map((el) => el.dataset.name);
        return { card_id: id, vg_name: vg ? vg.value : "", volume_names: names };
      });
    }

    function bindVolumeBox(cardId) {
      const box = document.getElementById("vols-" + cardId);
      if (!box) return;
      box.querySelectorAll("input").forEach((el) => el.addEventListener("change", invalidatePreview));
      const search = document.querySelector('.vol-search[data-card-id="' + cardId + '"]');
      if (search) {
        search.oninput = () => {
          const q = search.value.toLowerCase();
          box.querySelectorAll("tbody tr").forEach((tr) => {
            tr.style.display = (tr.dataset.name || "").toLowerCase().includes(q) ? "" : "none";
          });
        };
      }
    }

    function render() {
      cards.forEach((card) => {
        const vg = document.getElementById("vg-" + card.id);
        if (vg) vgByCard[card.id] = vg.value;
        const vols = document.getElementById("vols-" + card.id);
        if (vols) volumesByCard[card.id] = vols.innerHTML;
      });
      if (!cards.length) {
        arraysEl.innerHTML = '<p class="hint">No IBM FlashSystem / SVC SSH cards.</p>';
        return;
      }
      arraysEl.innerHTML = cards.map((card) => {
        const checked = document.querySelector('.array-check[data-card-id="' + card.id + '"]');
        const on = checked ? checked.checked : false;
        const vgVal = vgByCard[card.id] !== undefined ? vgByCard[card.id] : (card.default_vg_name || "");
        const panel = on ? (
          '<div class="actions">' +
          '<label>Volume group <input id="vg-' + card.id + '" value="' + vgVal + '"></label>' +
          '<button type="button" class="secondary load-vols" data-card-id="' + card.id + '">Load volumes</button>' +
          '<input class="vol-search" data-card-id="' + card.id + '" placeholder="Search volumes">' +
          '</div><div id="vols-' + card.id + '"><p class="hint">Load volumes for this array.</p></div>'
        ) : "";
        return '<div class="array"><label class="array-head"><input class="array-check" type="checkbox" data-card-id="' + card.id + '"' + (on ? " checked" : "") + '> <strong>' + card.name + '</strong> <span class="hint">' + (card.host || "") + '</span></label>' + panel + '</div>';
      }).join("");
      arraysEl.querySelectorAll(".array-check, .load-vols, .vol-search").forEach((el) => {
        el.addEventListener("change", () => { if (el.classList.contains("array-check")) { render(); } invalidatePreview(); });
        el.addEventListener("input", invalidatePreview);
      });
      arraysEl.querySelectorAll("input[id^='vg-']").forEach((el) => {
        el.addEventListener("input", () => { vgByCard[el.id.slice(3)] = el.value; invalidatePreview(); });
      });
      arraysEl.querySelectorAll(".load-vols").forEach((btn) => btn.addEventListener("click", () => loadVolumes(Number(btn.dataset.cardId))));
      cards.forEach((card) => {
        const box = document.getElementById("vols-" + card.id);
        if (box && volumesByCard[card.id]) {
          box.innerHTML = volumesByCard[card.id];
          bindVolumeBox(card.id);
        }
      });
    }

    async function loadVolumes(cardId) {
      invalidatePreview();
      const box = document.getElementById("vols-" + cardId);
      box.innerHTML = '<p class="hint">Loading volumes…</p>';
      const res = await fetch("/api/esx-snap-policy/volumes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ card_id: cardId }) });
      const data = await res.json();
      if (!data.ok) { box.innerHTML = '<p class="warning">' + (data.error || "Load failed") + '</p>'; volumesByCard[cardId] = box.innerHTML; return; }
      const rows = (data.volumes || []).map((vol) => {
        const grouped = !!(vol.volume_group || "").trim();
        return '<tr data-name="' + vol.name + '"><td><input class="vol-' + cardId + '" type="checkbox" data-name="' + vol.name + '"' + (grouped ? " disabled" : "") + '></td><td>' + vol.name + '</td><td>' + (vol.capacity || "") + '</td><td>' + (vol.volume_group || "") + '</td></tr>';
      }).join("");
      box.innerHTML = '<table><thead><tr><th></th><th>Name</th><th>Capacity</th><th>Volume group</th></tr></thead><tbody>' + rows + '</tbody></table>';
      volumesByCard[cardId] = box.innerHTML;
      bindVolumeBox(cardId);
    }

    document.getElementById("select-all-btn").onclick = () => {
      document.querySelectorAll(".array-check").forEach((el) => { el.checked = true; });
      render(); invalidatePreview();
    };
    document.getElementById("select-none-btn").onclick = () => {
      document.querySelectorAll(".array-check").forEach((el) => { el.checked = false; });
      render(); invalidatePreview();
    };
    startEl.addEventListener("input", invalidatePreview);
    document.getElementById("modal-close").onclick = () => { modal.hidden = true; };

    document.getElementById("preview-btn").onclick = async () => {
      invalidatePreview();
      statusEl.textContent = "Preview…";
      const body = { start_time: startEl.value, arrays: arrayPayload() };
      const res = await fetch("/api/esx-snap-policy/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await res.json();
      const lines = [];
      (data.arrays || []).forEach((row) => {
        lines.push("# " + (row.name || row.card_id) + " vg=" + (row.vg_name || "") + " runnable=" + row.runnable);
        (row.warnings || []).forEach((w) => lines.push(w));
        (row.steps || []).forEach((s) => lines.push(s.cmd));
        lines.push("");
      });
      showModal("Preview / Dry-run", lines.join("\\n") || JSON.stringify(data, null, 2));
      window.__esxPreviewOk = !!data.ok;
      window.__esxPreviewHash = data.preview_hash || "";
      runBtn.disabled = !window.__esxPreviewOk;
      statusEl.textContent = data.ok ? "Preview succeeded; Run Create is enabled." : "Preview found blocking errors.";
    };

    document.getElementById("run-btn").onclick = async () => {
      if (!window.__esxPreviewOk) return;
      if (!confirm("Create ESX-snap policy and volume groups on the listed arrays? This mutates the arrays.")) return;
      const body = { start_time: startEl.value, arrays: arrayPayload(), confirm: true, preview_hash: window.__esxPreviewHash };
      const res = await fetch("/api/esx-snap-policy/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await res.json();
      showModal("Run Create", JSON.stringify(data, null, 2));
      invalidatePreview();
      statusEl.textContent = data.ok ? "Run finished." : "Run failed or blocked.";
    };

    loadCards();
  </script>
</body>
</html>
"""
