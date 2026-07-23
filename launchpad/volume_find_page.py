"""Volume Find page — search volume names across monitored arrays."""

VOLUME_FIND_PATH = "/volume-find"

VOLUME_FIND_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Volume Find</title>
  <style>
    :root {
      --bg: #0b0f14;
      --panel: #121821;
      --text: #e8edf5;
      --muted: #8b98ab;
      --accent: #ff6b00;
      --accent2: #ff8533;
      --border: #2a3444;
      --card: #151c27;
      --danger: #fecaca;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Segoe UI, Inter, Arial, sans-serif;
      background: radial-gradient(circle at top, #172033 0%, var(--bg) 45%);
      color: var(--text);
    }
    .wrap { max-width: 1100px; margin: 0 auto; padding: 28px 20px 48px; }
    .hero {
      background: linear-gradient(135deg, #1a2230 0%, #101722 100%);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 24px 28px;
      margin-bottom: 18px;
    }
    .hero h1 { margin: 0 0 8px; color: var(--accent); font-size: 1.85rem; }
    .hero p { margin: 0; color: var(--muted); line-height: 1.45; }
    .hero-actions {
      display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 16px;
    }
    .btn, a.btn, button.btn {
      background: var(--accent); color: #111; border: none; border-radius: 10px;
      height: 34px; padding: 0 14px; font: inherit; font-weight: 600; cursor: pointer;
      display: inline-flex; align-items: center; text-decoration: none;
    }
    a.btn.secondary, button.btn.secondary {
      background: #0f141d; color: var(--text); border: 1px solid var(--border);
    }
    button.btn:disabled { opacity: .55; cursor: not-allowed; }
    #volume-search {
      width: min(420px, 100%); background: #0f141d; color: var(--text);
      border: 1px solid var(--border); border-radius: 10px; height: 34px;
      padding: 0 12px; font: inherit;
    }
    .status { color: var(--muted); font-size: 0.9rem; }
    .section {
      background: var(--card); border: 1px solid var(--border); border-radius: 16px;
      padding: 18px 20px; margin-bottom: 16px;
    }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th, td {
      border: 1px solid var(--border); padding: 8px 10px; text-align: left; vertical-align: top;
    }
    th {
      color: var(--muted); background: #0f141d; font-size: 0.76rem;
      text-transform: uppercase; letter-spacing: 0.03em;
    }
    .empty { padding: 14px 0; color: var(--muted); }
    .errors {
      margin: 0 0 12px; padding: 10px 12px; border-radius: 10px;
      background: #32151a; border: 1px solid #7f1d1d; color: var(--danger);
      white-space: pre-wrap; font-size: 0.88rem;
    }
    .errors:empty, .errors[hidden] { display: none; }
    .footer { margin-top: 18px; color: var(--muted); font-size: 0.85rem; }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <h1>Volume Find</h1>
      <p>
        Search volume names across monitor-on IBM FlashSystem / Storwize / SVC and HPE 3PAR / Primera SSH cards.
        Find uses cached health command output; Search live runs SSH queries after LaunchPad is unlocked.
      </p>
      <div class="hero-actions">
        <input type="search" id="volume-search" placeholder="Search volume name…" aria-label="Search volumes">
        <button type="button" id="volume-find-btn" class="btn">Find</button>
        <button type="button" id="volume-live-btn" class="btn secondary">Search live</button>
        <a class="btn secondary" href="/fc-wwpn">FC WWPN</a>
        <a class="btn secondary" href="/capacity">Capacity Report</a>
        <a class="btn secondary" href="/">Health Dashboard</a>
        <span id="status" class="status" aria-live="polite"></span>
      </div>
    </section>

    <section class="section">
      <div id="errors" class="errors" hidden></div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Card</th>
              <th>Vendor</th>
              <th>Volume</th>
              <th>Pool / CPG</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody id="results-body">
            <tr><td colspan="5" class="empty">Enter a volume name fragment and click Find.</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <p class="footer">LaunchPad Volume Find v{{APP_VERSION}} · Keep LaunchPad running while searching live.</p>
  </main>

  <script>
    const searchEl = document.getElementById("volume-search");
    const findBtn = document.getElementById("volume-find-btn");
    const liveBtn = document.getElementById("volume-live-btn");
    const statusEl = document.getElementById("status");
    const errorsEl = document.getElementById("errors");
    const bodyEl = document.getElementById("results-body");

    function escapeHtml(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function setBusy(busy) {
      findBtn.disabled = busy;
      liveBtn.disabled = busy;
    }

    function renderErrors(errors) {
      if (!errors || !errors.length) {
        errorsEl.hidden = true;
        errorsEl.textContent = "";
        return;
      }
      errorsEl.hidden = false;
      errorsEl.textContent = errors.map((e) => {
        const name = e.card_name || e.card_id || "card";
        return name + ": " + (e.error || "error");
      }).join("\\n");
    }

    function renderMatches(matches) {
      if (!matches || !matches.length) {
        bodyEl.innerHTML = '<tr><td colspan="5" class="empty">No matches.</td></tr>';
        return;
      }
      bodyEl.innerHTML = matches.map((m) => (
        "<tr>"
        + "<td>" + escapeHtml(m.card_name || m.card_id || "") + "</td>"
        + "<td>" + escapeHtml(m.vendor || "") + "</td>"
        + "<td>" + escapeHtml(m.volume || "") + "</td>"
        + "<td>" + escapeHtml(m.pool_or_cpg || "") + "</td>"
        + "<td>" + escapeHtml(m.source || "") + "</td>"
        + "</tr>"
      )).join("");
    }

    async function runVolumeFind(mode) {
      const q = (searchEl.value || "").trim();
      if (!q) {
        statusEl.textContent = "Enter a search term.";
        renderErrors([]);
        bodyEl.innerHTML = '<tr><td colspan="5" class="empty">Enter a volume name fragment and click Find.</td></tr>';
        return;
      }
      setBusy(true);
      statusEl.textContent = mode === "live" ? "Searching live…" : "Searching cache…";
      renderErrors([]);
      try {
        const url = "/api/volume-find?q=" + encodeURIComponent(q)
          + (mode === "live" ? "&mode=live" : "&mode=cache");
        const res = await fetch(url);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          const msg = data.error || ("Request failed (" + res.status + ")");
          statusEl.textContent = msg;
          renderErrors([{ card_name: "API", error: msg }]);
          bodyEl.innerHTML = '<tr><td colspan="5" class="empty">No matches.</td></tr>';
          return;
        }
        const matches = data.matches || [];
        const errors = data.errors || [];
        renderMatches(matches);
        renderErrors(errors);
        if (matches.length) {
          const label = mode === "live" ? "live" : "cache";
          statusEl.textContent = matches.length + " " + label + " match"
            + (matches.length === 1 ? "" : "es")
            + (errors.length ? " · " + errors.length + " error" + (errors.length === 1 ? "" : "s") : "");
        } else if (mode === "cache") {
          statusEl.textContent = "No cache matches — try Search live";
        } else {
          statusEl.textContent = errors.length
            ? ("No live matches · " + errors.length + " error" + (errors.length === 1 ? "" : "s"))
            : "No live matches.";
        }
      } catch (err) {
        statusEl.textContent = String(err && err.message ? err.message : err);
        renderErrors([{ card_name: "Network", error: String(err) }]);
        bodyEl.innerHTML = '<tr><td colspan="5" class="empty">No matches.</td></tr>';
      } finally {
        setBusy(false);
      }
    }

    findBtn.addEventListener("click", () => runVolumeFind("cache"));
    liveBtn.addEventListener("click", () => runVolumeFind("live"));
    searchEl.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") {
        ev.preventDefault();
        runVolumeFind("cache");
      }
    });
  </script>
</body>
</html>
"""
