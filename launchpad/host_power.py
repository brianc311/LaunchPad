"""Browser page for controlled Hadoop host shutdowns."""

HOST_POWER_PATH = "/host-power"

HOST_POWER_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Host Power</title>
  <style>
    :root { --bg:#0b0f14; --panel:#151c27; --panel-alt:#0f141d; --text:#e8edf5; --muted:#a9b6c8; --accent:#ff6b00; --border:#2a3444; --danger:#ef4444; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; color:var(--text); font-family:Segoe UI,Inter,Arial,sans-serif; background:radial-gradient(circle at top,#172033 0%,var(--bg) 45%); }
    main { max-width:920px; margin:0 auto; padding:28px 20px 48px; }
    section { margin-bottom:18px; padding:20px; border:1px solid var(--border); border-radius:14px; background:var(--panel); }
    .hero { background:linear-gradient(135deg,#1a2230,#101722); }
    h1 { margin:0 0 8px; color:var(--accent); font-size:1.9rem; }
    h2 { margin:0 0 14px; color:#ff9a56; font-size:1.12rem; }
    p, .hint { color:var(--muted); line-height:1.5; }
    .host { display:flex; gap:10px; padding:10px; border-top:1px solid var(--border); color:var(--muted); }
    .host:first-child { border-top:0; }
    .host input { accent-color:var(--accent); }
    .host strong { color:var(--text); }
    .actions, .checks { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:14px; }
    .checks label { color:var(--muted); cursor:pointer; }
    button, a.button { min-height:36px; padding:0 14px; border:0; border-radius:9px; background:var(--accent); color:#111; font:inherit; font-weight:700; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; }
    button.secondary, a.secondary { color:var(--text); background:var(--panel-alt); border:1px solid var(--border); }
    button:disabled { opacity:.6; cursor:wait; }
    pre { min-height:150px; max-height:420px; overflow:auto; margin:0; padding:13px; color:#d8e3f2; background:#080c11; border:1px solid var(--border); border-radius:9px; white-space:pre-wrap; word-break:break-word; font:13px/1.5 Consolas,monospace; }
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Host Power</h1>
      <p>Stop Hadoop services, then shut down selected hosts through native SSH.</p>
      <a class="button secondary" href="/">Back to dashboard</a>
    </section>
    <section>
      <h2>Hadoop hosts</h2>
      <div id="hosts"><p class="hint">Loading hosts…</p></div>
      <div class="checks">
        <label><input id="confirm-mutate" type="checkbox"> I confirm this will stop Hadoop and shut down the selected hosts</label>
      </div>
      <div class="actions">
        <button id="preview" class="secondary" type="button">Preview</button>
        <button id="run" type="button">Run</button>
      </div>
    </section>
    <section>
      <h2>Run log</h2>
      <pre id="log" aria-live="polite">Choose one or more hosts, then preview.</pre>
    </section>
    <p class="hint">LaunchPad {{APP_VERSION}}</p>
  </main>
  <script>
    const hostsEl = document.getElementById("hosts");
    const log = document.getElementById("log");
    const requestedCardId = new URLSearchParams(window.location.search).get("card_id");

    function writeLog(value) {
      log.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
    }

    function selectedIds() {
      return [...document.querySelectorAll("input[name=card_id]:checked")]
        .map((input) => Number(input.value));
    }

    async function requestJson(path, options = {}) {
      const response = await fetch(path, options);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
      return data;
    }

    async function loadCards() {
      try {
        const data = await requestJson("/api/host-power/cards");
        const cards = data.cards || [];
        hostsEl.replaceChildren();
        if (!cards.length) {
          hostsEl.innerHTML = '<p class="hint">No Hadoop / Linux SSH cards with a host are available. In Admin, set Device Profile to <strong>Hadoop / Linux SSH</strong> (or name the card with Hadoop/HDP so LaunchPad can promote it).</p>';
          return;
        }
        cards.forEach((card) => {
          const label = document.createElement("label");
          label.className = "host";
          const input = document.createElement("input");
          input.type = "checkbox";
          input.name = "card_id";
          input.value = card.id;
          input.checked = requestedCardId === String(card.id);
          const detail = document.createElement("span");
          const name = document.createElement("strong");
          name.textContent = card.name;
          detail.append(name, document.createElement("br"), document.createTextNode(card.host));
          label.append(input, detail);
          hostsEl.append(label);
        });
      } catch (error) {
        hostsEl.textContent = `Could not load hosts: ${error.message}`;
      }
    }

    const previewBtn = document.getElementById("preview");
    const runBtn = document.getElementById("run");
    let requestInFlight = false;

    async function withButtonsLocked(action) {
      if (requestInFlight) return;
      requestInFlight = true;
      previewBtn.disabled = true;
      runBtn.disabled = true;
      try {
        await action();
      } finally {
        requestInFlight = false;
        previewBtn.disabled = false;
        runBtn.disabled = false;
      }
    }

    async function preview() {
      await withButtonsLocked(async () => {
        try {
          writeLog("Building preview…");
          writeLog(await requestJson("/api/host-power/preview", {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({card_ids: selectedIds()}),
          }));
        } catch (error) {
          writeLog(`Preview failed: ${error.message}`);
        }
      });
    }

    async function run() {
      await withButtonsLocked(async () => {
        try {
          writeLog("Running host power steps…");
          writeLog(await requestJson("/api/host-power/run", {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
              card_ids: selectedIds(),
              confirm: document.getElementById("confirm-mutate").checked,
            }),
          }));
        } catch (error) {
          writeLog(`Run failed: ${error.message}`);
        }
      });
    }

    document.getElementById("preview").addEventListener("click", preview);
    document.getElementById("run").addEventListener("click", run);
    loadCards();
  </script>
</body>
</html>
"""
