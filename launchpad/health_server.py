import json
import socket
import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from launchpad.health_metrics import run_remote_metrics
from launchpad.ssh_launcher import _log

DEFAULT_PORT = 18765
PREFERRED_PORTS = (18765, 18766, 18767, 18768)


@dataclass
class HealthCard:
    card_id: int
    name: str
    host: str
    port: int | None
    username: str
    key_path: str
    key_passphrase: str = ""
    metrics: dict[str, Any] | None = None
    error: str | None = None
    updated_at: str | None = None

    def to_api(self) -> dict[str, Any]:
        return {
            "id": self.card_id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "metrics": self.metrics,
            "error": self.error,
            "updated_at": self.updated_at,
        }


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Health Dashboard</title>
  <style>
    :root {
      --bg: #0b0f14;
      --panel: #121821;
      --text: #e8edf5;
      --muted: #8b98ab;
      --accent: #ff6b00;
      --accent2: #ff8533;
      --warn: #f59e0b;
      --bad: #ef4444;
      --border: #2a3444;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Segoe UI, Inter, Arial, sans-serif;
      background: radial-gradient(circle at top, #172033 0%, var(--bg) 45%);
      color: var(--text);
      min-height: 100vh;
    }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 28px 20px 48px; }
    .hero {
      background: linear-gradient(135deg, #1a2230 0%, #101722 100%);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 24px 28px;
      box-shadow: 0 0 40px rgba(255, 107, 0, 0.08);
      margin-bottom: 24px;
    }
    .hero h1 { margin: 0 0 6px; color: var(--accent); font-size: 2rem; }
    .hero p { margin: 0; color: var(--muted); }
    .empty { color: var(--muted); padding: 24px; text-align: center; }
    .server {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 20px 22px 22px;
      margin-bottom: 20px;
      transition: opacity 0.2s;
    }
    .server.loading { opacity: 0.72; }
    .server-head {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
      padding-bottom: 14px;
      border-bottom: 1px solid var(--border);
    }
    .server-head h2 { margin: 0; color: var(--accent2); font-size: 1.35rem; }
    .host { color: var(--muted); font-size: 0.92rem; flex: 1; min-width: 180px; }
    .controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    button, select {
      font: inherit;
      border-radius: 10px;
      height: 34px;
      cursor: pointer;
    }
    button {
      background: var(--accent);
      color: #111;
      border: none;
      padding: 0 14px;
      font-weight: 600;
    }
    button:hover { background: var(--accent2); }
    button:disabled { opacity: 0.55; cursor: wait; }
    select {
      background: #0f141d;
      color: var(--text);
      border: 1px solid var(--border);
      padding: 0 10px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
    }
    .card {
      background: #0f141d;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
    }
    .card h3 { margin: 0 0 10px; font-size: 0.95rem; color: var(--accent2); }
    .stat { font-size: 1.75rem; font-weight: 700; margin-bottom: 4px; }
    .stat-label { color: var(--muted); font-size: 0.85rem; margin-bottom: 8px; }
    .metric { margin-top: 8px; }
    .metric-head { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 0.88rem; }
    .bar { height: 9px; background: #0b0f14; border-radius: 999px; overflow: hidden; border: 1px solid var(--border); }
    .fill { height: 100%; border-radius: 999px; background: var(--accent); transition: width 0.35s ease; }
    .sub { color: var(--muted); font-size: 0.8rem; margin-top: 5px; }
    .updated { color: var(--muted); font-size: 0.82rem; margin: 14px 0 0; }
    .error {
      background: rgba(239, 68, 68, 0.12);
      border: 1px solid rgba(239, 68, 68, 0.35);
      color: #fecaca;
      border-radius: 10px;
      padding: 12px 14px;
      margin-bottom: 12px;
      white-space: pre-wrap;
      font-size: 0.88rem;
    }
    .footer { margin-top: 8px; color: var(--muted); font-size: 0.85rem; }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>LaunchPad Health</h1>
      <p>All monitored SSH servers in one place. Refresh individually or set auto-refresh per server.</p>
    </section>
    <div id="servers"></div>
    <p class="footer">Keep LaunchPad running while using refresh. Click <strong>Health</strong> on another SSH card to add it here.</p>
  </div>
  <script>
    const serversEl = document.getElementById("servers");
    const autoTimers = {};
    const knownIds = new Set();

    function escapeHtml(value) {
      return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function formatBytes(value) {
      if (!value || value <= 0) return "0 B";
      const units = ["B", "KB", "MB", "GB", "TB"];
      let size = value;
      let unit = 0;
      while (size >= 1024 && unit < units.length - 1) {
        size /= 1024;
        unit += 1;
      }
      return unit === 0 ? `${Math.round(size)} ${units[unit]}` : `${size.toFixed(1)} ${units[unit]}`;
    }

    function formatUptime(seconds) {
      const days = Math.floor(seconds / 86400);
      const hours = Math.floor((seconds % 86400) / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      const parts = [];
      if (days) parts.push(`${days}d`);
      if (hours || days) parts.push(`${hours}h`);
      parts.push(`${minutes}m`);
      return parts.join(" ");
    }

    function barTone(pct) {
      if (pct >= 90) return "#ef4444";
      if (pct >= 80) return "#f59e0b";
      return "#ff6b00";
    }

    function barHtml(label, pct, sub) {
      const tone = barTone(pct);
      const clamped = Math.max(0, Math.min(100, pct));
      return `
        <div class="metric">
          <div class="metric-head"><span>${label}</span><span>${clamped.toFixed(1)}%</span></div>
          <div class="bar"><div class="fill" style="width:${clamped.toFixed(1)}%; background:${tone};"></div></div>
          <div class="sub">${sub}</div>
        </div>`;
    }

    function metricsHtml(card) {
      if (card.error) {
        return `<div class="error">${escapeHtml(card.error)}</div>`;
      }
      const m = card.metrics || {};
      const memTotal = (m.mem_total_kb || 0) * 1024;
      const memAvail = (m.mem_avail_kb || 0) * 1024;
      const memUsed = Math.max(0, memTotal - memAvail);
      const memPct = memTotal ? (memUsed / memTotal) * 100 : 0;

      const diskTotal = m.disk_total || 0;
      const diskUsed = m.disk_used || 0;
      const diskFree = m.disk_free || 0;
      const diskPct = diskTotal ? (diskUsed / diskTotal) * 100 : 0;

      const swapTotal = (m.swap_total_kb || 0) * 1024;
      const swapFree = (m.swap_free_kb || 0) * 1024;
      const swapUsed = Math.max(0, swapTotal - swapFree);
      const swapPct = swapTotal ? (swapUsed / swapTotal) * 100 : 0;

      const cpuPct = m.cpu_percent || 0;
      const cores = m.cpu_cores || 1;

      return `
        <div class="grid">
          <article class="card">
            <h3>CPU</h3>
            <div class="stat">${cpuPct.toFixed(1)}%</div>
            <div class="stat-label">${cores} cores · load ${(m.load_1||0).toFixed(2)} / ${(m.load_5||0).toFixed(2)} / ${(m.load_15||0).toFixed(2)}</div>
            ${barHtml("CPU usage", cpuPct, `Current utilization across ${cores} cores`)}
          </article>
          <article class="card">
            <h3>Memory</h3>
            <div class="stat">${formatBytes(memUsed)}</div>
            <div class="stat-label">used of ${formatBytes(memTotal)}</div>
            ${barHtml("RAM usage", memPct, `${formatBytes(memAvail)} available`)}
          </article>
          <article class="card">
            <h3>Disk</h3>
            <div class="stat">${formatBytes(diskUsed)}</div>
            <div class="stat-label">used of ${formatBytes(diskTotal)}</div>
            ${barHtml("Root disk", diskPct, `${formatBytes(diskFree)} free`)}
          </article>
          <article class="card">
            <h3>Capacity</h3>
            <div class="stat">${formatUptime(m.uptime_seconds || 0)}</div>
            <div class="stat-label">uptime · ${m.hostname || card.host}</div>
            <div class="sub">Processes: ${m.process_count || 0} · Users: ${m.users_logged_in || 0}</div>
            <div class="sub">${m.ipv4_interface ? m.ipv4_interface + ': ' : 'IP: '}${m.ipv4_address || card.host}</div>
            ${barHtml("Swap", swapPct, `${formatBytes(swapUsed)} used · ${formatBytes(swapTotal)} total`)}
          </article>
        </div>`;
    }

    function hostLabel(card) {
      const port = card.port ? `:${card.port}` : "";
      const user = card.username ? `${card.username}@` : "";
      return `${user}${card.host}${port}`;
    }

    function renderCard(card) {
      const updated = card.updated_at ? `Last updated: ${card.updated_at}` : "Not refreshed yet";
      return `
        <section class="server" data-id="${card.id}">
          <div class="server-head">
            <h2>${escapeHtml(card.name)}</h2>
            <span class="host">${escapeHtml(hostLabel(card))}</span>
            <div class="controls">
              <button type="button" class="refresh-btn" data-id="${card.id}">Refresh</button>
              <select class="auto-select" data-id="${card.id}" aria-label="Auto refresh interval">
                <option value="0">Auto: Off</option>
                <option value="10">Auto: 10 sec</option>
                <option value="30">Auto: 30 sec</option>
                <option value="60">Auto: 60 sec</option>
              </select>
            </div>
          </div>
          <div class="metrics">${metricsHtml(card)}</div>
          <p class="updated">${updated}</p>
        </section>`;
    }

    function applyAutoSelect(cardId) {
      const select = document.querySelector(`.auto-select[data-id="${cardId}"]`);
      if (!select) return;
      const saved = localStorage.getItem(`health-auto-${cardId}`) || "0";
      select.value = saved;
      setAutoRefresh(cardId, parseInt(saved, 10) || 0, false);
    }

    function setAutoRefresh(cardId, seconds, persist = true) {
      if (autoTimers[cardId]) {
        clearInterval(autoTimers[cardId]);
        delete autoTimers[cardId];
      }
      if (persist) {
        localStorage.setItem(`health-auto-${cardId}`, String(seconds));
      }
      if (seconds > 0) {
        autoTimers[cardId] = setInterval(() => refreshCard(cardId), seconds * 1000);
      }
    }

    function updateCardSection(card) {
      const section = document.querySelector(`.server[data-id="${card.id}"]`);
      if (!section) return false;
      section.querySelector(".metrics").innerHTML = metricsHtml(card);
      section.querySelector(".updated").textContent = card.updated_at
        ? `Last updated: ${card.updated_at}`
        : "Not refreshed yet";
      return true;
    }

    async function refreshCard(cardId) {
      const section = document.querySelector(`.server[data-id="${cardId}"]`);
      const button = section ? section.querySelector(".refresh-btn") : null;
      if (section) section.classList.add("loading");
      if (button) button.disabled = true;
      try {
        const res = await fetch(`/api/refresh/${cardId}`, { method: "POST" });
        const card = await res.json();
        if (!res.ok) throw new Error(card.error || "Refresh failed");
        updateCardSection(card);
      } catch (err) {
        if (section) {
          section.querySelector(".metrics").innerHTML =
            `<div class="error">${err.message || err}</div>`;
        }
      } finally {
        if (section) section.classList.remove("loading");
        if (button) button.disabled = false;
      }
    }

    function renderAll(cards) {
      if (!cards.length) {
        serversEl.innerHTML = '<div class="empty">No servers yet. Click Health on an SSH card in LaunchPad.</div>';
        return;
      }
      const sorted = [...cards].sort((a, b) => a.id - b.id);

      sorted.forEach((card) => {
        if (updateCardSection(card)) {
          if (!knownIds.has(card.id)) {
            knownIds.add(card.id);
            applyAutoSelect(card.id);
          }
          return;
        }
        serversEl.insertAdjacentHTML("beforeend", renderCard(card));
        knownIds.add(card.id);
        applyAutoSelect(card.id);
      });

      document.querySelectorAll(".refresh-btn").forEach((btn) => {
        const id = parseInt(btn.dataset.id, 10);
        btn.onclick = () => refreshCard(id);
      });
      document.querySelectorAll(".auto-select").forEach((select) => {
        const cardId = parseInt(select.dataset.id, 10);
        if (!select.dataset.wired) {
          select.dataset.wired = "1";
          select.onchange = () => setAutoRefresh(cardId, parseInt(select.value, 10) || 0);
        }
      });
    }

    async function loadCards() {
      const res = await fetch("/api/cards");
      const cards = await res.json();
      renderAll(cards);
    }

    loadCards();
    setInterval(loadCards, 15000);
  </script>
</body>
</html>"""


class _HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        _log(f"Health server: {fmt % args}")

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        server = get_health_server()
        if path == "/":
            self._send_html(DASHBOARD_HTML)
            return
        if path == "/api/cards":
            self._send_json(server.list_cards())
            return
        self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith("/api/refresh/"):
            self.send_error(404)
            return
        suffix = path.removeprefix("/api/refresh/")
        try:
            card_id = int(suffix)
        except ValueError:
            self.send_error(400)
            return
        server = get_health_server()
        try:
            card = server.refresh_card(card_id)
            self._send_json(card.to_api())
        except KeyError:
            self._send_json({"error": f"Unknown card id {card_id}"}, status=404)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _pick_port() -> int:
    for port in PREFERRED_PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("Could not find a free port for the health dashboard server.")


class HealthServer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cards: dict[int, HealthCard] = {}
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._port = DEFAULT_PORT
        self._browser_opened = False
        self._started = False

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._port}/"

    def ensure_running(self) -> None:
        with self._lock:
            if self._started:
                return
            self._port = _pick_port()
            self._httpd = ThreadingHTTPServer(("127.0.0.1", self._port), _HealthHandler)
            self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
            self._thread.start()
            self._started = True
            _log(f"Health dashboard server started at {self.url}")

    def register_card(
        self,
        card_id: int,
        name: str,
        host: str,
        port: int | None,
        username: str,
        key_path: str,
        key_passphrase: str = "",
    ) -> None:
        with self._lock:
            existing = self._cards.get(card_id)
            self._cards[card_id] = HealthCard(
                card_id=card_id,
                name=name,
                host=host,
                port=port,
                username=username,
                key_path=key_path,
                key_passphrase=key_passphrase or (existing.key_passphrase if existing else ""),
                metrics=existing.metrics if existing else None,
                error=existing.error if existing else None,
                updated_at=existing.updated_at if existing else None,
            )

    def refresh_card(self, card_id: int) -> HealthCard:
        with self._lock:
            if card_id not in self._cards:
                raise KeyError(card_id)
            card = self._cards[card_id]
            host = card.host
            port = card.port
            username = card.username
            key_path = card.key_path
            key_passphrase = card.key_passphrase

        try:
            metrics = run_remote_metrics(host, port, username, key_path, key_passphrase)
            error = None
        except Exception as exc:
            metrics = None
            error = str(exc)

        with self._lock:
            card.metrics = metrics
            card.error = error
            card.updated_at = _utc_now()
            return card

    def list_cards(self) -> list[dict[str, Any]]:
        with self._lock:
            return [card.to_api() for card in sorted(self._cards.values(), key=lambda c: c.card_id)]

    def open_browser_once(self) -> str:
        self.ensure_running()
        if not self._browser_opened:
            webbrowser.open(self.url)
            self._browser_opened = True
            _log(f"Opened health dashboard in browser: {self.url}")
        return self.url


_instance: HealthServer | None = None
_instance_lock = threading.Lock()


def get_health_server() -> HealthServer:
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = HealthServer()
        return _instance
