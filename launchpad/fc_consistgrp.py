"""FlashCopy Consistency Groups page: array card picker + live CG/map inventory."""

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
    .wrap { max-width:1180px; margin:0 auto; padding:28px 20px 48px; }
    .hero, .section { background:var(--card); border:1px solid var(--border); border-radius:16px; padding:20px; margin-bottom:18px; }
    .hero { background:linear-gradient(135deg,#1a2230 0%,#101722 100%); }
    h1 { margin:0 0 8px; color:var(--accent); font-size:1.85rem; }
    h2 { margin:0 0 12px; color:var(--accent2); font-size:1.05rem; }
    p { line-height:1.45; }
    .lede, .hint, .status { color:var(--muted); }
    .picker { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:16px; }
    select, button { min-height:34px; font:inherit; }
    select { min-width:260px; color:var(--text); background:#0f141d; border:1px solid var(--border); border-radius:8px; padding:6px 9px; }
    button { padding:0 14px; border:0; border-radius:10px; background:var(--accent); color:#111; font-weight:600; cursor:pointer; }
    button:disabled { cursor:not-allowed; opacity:.6; }
    pre { margin:0; padding:12px; overflow:auto; border:1px solid var(--border); border-radius:8px; background:#0b0f14; color:#d8e3f2; white-space:pre-wrap; max-height:420px; }
    .footer { color:var(--muted); font-size:.8rem; margin-top:8px; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>FlashCopy Consistency Groups</h1>
      <p class="lede">View and manage array-level FlashCopy Consistency Groups (create, assign, remove, start, delete) with Preview &rarr; Confirm &rarr; Run safety.</p>
      <div class="picker">
        <label for="card-select">Array</label>
        <select id="card-select"><option value="">Loading arrays&hellip;</option></select>
        <button id="refresh-btn" type="button">Refresh</button>
      </div>
      <p class="hint">Select a Health Card above to load live consistency group and FlashCopy map inventory.</p>
    </div>
    <div class="section">
      <h2>Inventory</h2>
      <p id="status" class="status">Loading&hellip;</p>
      <pre id="inventory-output"></pre>
    </div>
  </div>
  <script>
    const cardSelect = document.getElementById("card-select");
    const refreshBtn = document.getElementById("refresh-btn");
    const statusEl = document.getElementById("status");
    const outputEl = document.getElementById("inventory-output");

    function currentCardId() {
      const value = cardSelect.value;
      return value ? Number(value) : null;
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
          return;
        }
        cardSelect.innerHTML = '<option value="">Select an array&hellip;</option>' + cards.map(
          (card) => `<option value="${card.id}">${card.name} (${card.host})</option>`
        ).join("");
        if (preselect) {
          cardSelect.value = preselect;
          if (cardSelect.value === preselect) {
            loadInventory();
            return;
          }
        }
        statusEl.textContent = "Select an array to load inventory.";
      } catch (err) {
        statusEl.textContent = `Unable to load arrays: ${err}`;
      }
    }

    async function loadInventory() {
      const cardId = currentCardId();
      if (cardId === null) {
        outputEl.textContent = "";
        statusEl.textContent = "Select an array to load inventory.";
        return;
      }
      statusEl.textContent = "Loading inventory\u2026";
      try {
        const res = await fetch(`/api/fc-consistgrp/inventory?card_id=${cardId}`);
        const data = await res.json();
        outputEl.textContent = JSON.stringify(data, null, 2);
        statusEl.textContent = data.ok
          ? `Loaded ${data.groups.length} group(s), ${data.maps.length} map(s).`
          : (data.warnings || []).join(" ") || "Inventory load failed.";
      } catch (err) {
        statusEl.textContent = `Unable to load inventory: ${err}`;
      }
    }

    cardSelect.addEventListener("change", loadInventory);
    refreshBtn.addEventListener("click", loadInventory);
    loadCards();
  </script>
</body>
</html>"""
