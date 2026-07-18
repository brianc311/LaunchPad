import json
import re
import socket
import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from launchpad.capacity_report import CAPACITY_REPORT_HTML, CAPACITY_REPORT_PATH
from launchpad.command_format import resolve_card_commands
from launchpad.config import APP_VERSION
from launchpad.contingency_groups_data import (
    CONTINGENCY_GROUPS_SETTING,
    delete_group,
    normalize_group,
    normalize_groups,
    seed_contingency_groups,
    upsert_group,
)
from launchpad.contingency_groups import CONTINGENCY_GROUPS_HTML, CONTINGENCY_GROUPS_PATH
from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML, FC_WWPN_REPORT_PATH
from launchpad.flashsystem_fc import analyze_fc_inventory
from launchpad.flashsystem_health import analyze_health
from launchpad.health_metrics import run_remote_metrics
from launchpad.snapshot_schedule import SNAPSHOT_SCHEDULE_HTML, SNAPSHOT_SCHEDULE_PATH
from launchpad.snapshot_schedule_overrides import (
    SNAPSHOT_OVERRIDES_SETTING,
    normalize_override,
    normalize_overrides_map,
)
from launchpad.ssh_commands import run_remote_command_suite
from launchpad.ssh_launcher import _log
from launchpad.storage_presets import DEVICE_PROFILES

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
    password: str = ""
    device_profile: str = ""
    custom_commands: str = ""
    serial_number: str = ""
    category: str = ""
    metrics: dict[str, Any] | None = None
    command_results: list[dict[str, Any]] | None = None
    error: str | None = None
    updated_at: str | None = None

    def to_api(self) -> dict[str, Any]:
        analysis = analyze_health(self.name, self.command_results, self.metrics)
        fc = analyze_fc_inventory(self.command_results)
        model = DEVICE_PROFILES.get(self.device_profile, self.device_profile or "")
        return {
            "id": self.card_id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "device_profile": self.device_profile,
            "model": model,
            "category": self.category,
            "command_mode": bool(
                resolve_card_commands(
                    self.device_profile,
                    self.custom_commands,
                    instance_id=self.serial_number,
                )
            ),
            "metrics": self.metrics,
            "command_results": self.command_results,
            "error": self.error,
            "updated_at": self.updated_at,
            "health_issues": analysis["health_issues"],
            "capacity_summary": analysis["capacity_summary"],
            "capacity_popup_html": analysis["capacity_popup_html"],
            "pools": analysis.get("pools") or [],
            "fc_ports": fc.get("fc_ports") or [],
            "fc_hosts": fc.get("fc_hosts") or [],
            "fc_mappings": fc.get("fc_mappings") or [],
            "fc_fabric": fc.get("fc_fabric") or [],
            "fc_ports_by_node": fc.get("fc_ports_by_node") or [],
            "fc_available": bool(fc.get("fc_available")),
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
    .hero-actions { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-top: 16px; }
    .refresh-status { color: var(--muted); font-size: 0.9rem; }
    .summary { margin: 12px 0 0; font-size: 0.95rem; }
    .summary.ok { color: #4ade80; }
    .summary.warn { color: var(--warn); }
    .summary.bad { color: var(--bad); }
    .quick-cmds { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
    .quick-cmds button {
      background: #0f141d;
      color: var(--text);
      border: 1px solid var(--border);
      height: 30px;
      padding: 0 10px;
      font-size: 0.82rem;
      font-weight: 600;
    }
    .quick-cmds button:hover { border-color: var(--accent); color: var(--accent2); }
    .server.fail { border-color: rgba(239, 68, 68, 0.45); }
    .cmd-block {
      background: #0f141d;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 14px;
      margin-bottom: 12px;
    }
    .cmd-block.fail { border-color: rgba(239, 68, 68, 0.45); }
    .cmd-block h4 { margin: 0 0 6px; color: var(--accent2); font-size: 0.92rem; }
    .cmd-block code {
      display: block;
      color: var(--muted);
      font-size: 0.78rem;
      margin-bottom: 8px;
      word-break: break-word;
    }
    .cmd-block pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, monospace;
      font-size: 0.78rem;
      color: #d7e0ef;
      max-height: 260px;
      overflow: auto;
    }
    .cmd-summary {
      margin: 0 0 10px;
      color: #4ade80;
      font-weight: 600;
      font-size: 0.9rem;
    }
    .table-wrap {
      overflow-x: auto;
      margin-top: 4px;
      border: 1px solid var(--border);
      border-radius: 10px;
    }
    .data-table {
      width: 100%;
      border-collapse: collapse;
      font-family: Consolas, monospace;
      font-size: 0.76rem;
    }
    .data-table th,
    .data-table td {
      border-bottom: 1px solid var(--border);
      padding: 7px 10px;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }
    .data-table th {
      background: #0b0f14;
      color: var(--accent2);
      font-weight: 600;
      position: sticky;
      top: 0;
    }
    .data-table tr:last-child td,
    .data-table tr:last-child th {
      border-bottom: none;
    }
    .data-table tbody tr:nth-child(even) td {
      background: rgba(255, 255, 255, 0.02);
    }
    .data-table.df-table {
      table-layout: auto;
      min-width: 520px;
    }
    .data-table.df-table th,
    .data-table.df-table td {
      white-space: nowrap;
      min-width: 4.5rem;
    }
    .data-table.df-table th:first-child,
    .data-table.df-table td:first-child {
      min-width: 8rem;
    }
    .kv-table th {
      width: 220px;
      color: var(--muted);
      font-weight: 500;
    }
    .kv-table td {
      color: #d7e0ef;
      white-space: normal;
      word-break: break-word;
    }
    .raw-output {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, monospace;
      font-size: 0.78rem;
      color: #d7e0ef;
      max-height: 260px;
      overflow: auto;
    }
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
    .server.monitor-off { opacity: 0.6; }
    .server.monitor-off .metrics { filter: grayscale(0.7); }
    .monitor-toggle {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.85rem;
      color: var(--muted);
      cursor: pointer;
      user-select: none;
    }
    .monitor-toggle input { width: 15px; height: 15px; accent-color: var(--accent); cursor: pointer; }
    .monitor-toggle.on { color: #4ade80; }
    .paused-note {
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 0.82rem;
      font-style: italic;
    }
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
    .issues-panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 18px 22px;
      margin-bottom: 24px;
    }
    .issues-panel h2 {
      margin: 0 0 12px;
      color: var(--accent2);
      font-size: 1.15rem;
    }
    .issues-ok { color: #4ade80; margin: 0; }
    .issue-list { display: grid; gap: 8px; }
    .issue {
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 0.9rem;
      border: 1px solid var(--border);
      background: #0f141d;
    }
    .issue.critical { border-color: rgba(239, 68, 68, 0.45); color: #fecaca; }
    .issue.warn { border-color: rgba(245, 158, 11, 0.45); color: #fde68a; }
    .issue strong { color: var(--text); }
    .issue-group {
      border-radius: 10px;
      border: 1px solid var(--border);
      background: #0f141d;
      overflow: hidden;
    }
    .issue-group.critical { border-color: rgba(239, 68, 68, 0.45); }
    .issue-group.warn { border-color: rgba(245, 158, 11, 0.45); }
    .issue-group-head {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      width: 100%;
      padding: 10px 12px;
      background: transparent;
      border: none;
      color: inherit;
      font: inherit;
      text-align: left;
      cursor: pointer;
    }
    .issue-group-head:hover { background: rgba(255, 255, 255, 0.03); }
    .issue-chevron {
      flex-shrink: 0;
      margin-top: 2px;
      font-size: 0.75rem;
      color: var(--muted);
      transition: transform 0.2s ease;
    }
    .issue-group.open .issue-chevron { transform: rotate(180deg); }
    .issue-group-text { flex: 1; min-width: 0; font-size: 0.9rem; }
    .issue-group.critical .issue-group-text { color: #fecaca; }
    .issue-group.warn .issue-group-text { color: #fde68a; }
    .issue-count {
      flex-shrink: 0;
      min-width: 1.7rem;
      text-align: center;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 700;
      background: rgba(255, 255, 255, 0.08);
      color: var(--text);
    }
    .issue-group-body {
      display: none;
      padding: 0 12px 10px 36px;
      border-top: 1px solid var(--border);
    }
    .issue-group.open .issue-group-body { display: block; }
    .issue-sub {
      padding: 6px 0;
      font-size: 0.85rem;
      color: var(--muted);
      border-bottom: 1px solid rgba(42, 52, 68, 0.5);
    }
    .issue-sub:last-child { border-bottom: none; }
    .issue-sub strong { color: var(--text); }
    .issue-sub-count { color: var(--accent2); font-weight: 600; }
    .toggle-row {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 0 14px;
      height: 34px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: #0f141d;
      color: var(--text);
      font-size: 0.9rem;
      cursor: pointer;
      user-select: none;
    }
    .toggle-row input {
      width: 16px;
      height: 16px;
      accent-color: var(--accent);
      cursor: pointer;
    }
    body.hide-health-alerts #issues-panel { display: none; }
    body.hide-health-alerts .cmd-block[data-alert="1"] { display: none; }
    .filter-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-top: 14px;
      width: 100%;
    }
    .filter-bar input[type="search"] {
      flex: 1;
      min-width: 200px;
      height: 34px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: #0f141d;
      color: var(--text);
      padding: 0 12px;
      font: inherit;
    }
    .filter-bar input[type="search"]::placeholder { color: var(--muted); }
    .selection-count {
      color: var(--muted);
      font-size: 0.88rem;
      min-width: 120px;
    }
    .print-meta {
      display: none;
      color: var(--muted);
      font-size: 0.88rem;
      margin-top: 10px;
    }
    .server.search-match {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }
    .search-hint {
      color: var(--muted);
      font-size: 0.85rem;
      margin: 0;
      width: 100%;
    }
    .print-select-label {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.82rem;
      color: var(--muted);
      cursor: pointer;
      user-select: none;
      margin-right: 8px;
    }
    .print-select-label input {
      width: 15px;
      height: 15px;
      accent-color: var(--accent);
      cursor: pointer;
    }
    @media print {
      body {
        background: #fff;
        color: #111;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }
      .wrap { max-width: none; padding: 0; }
      .no-print { display: none !important; }
      .hero {
        background: none;
        border: none;
        border-bottom: 2px solid #ff6b00;
        border-radius: 0;
        padding: 0 0 12px;
        margin-bottom: 16px;
        box-shadow: none;
      }
      .hero h1 { color: #111; font-size: 1.5rem; }
      .hero p { color: #444; }
      .print-meta { display: block; color: #444; margin-bottom: 8px; }
      #summary { color: #444; }
      body.print-export .server:not(.print-selected) { display: none !important; }
      body.print-export #issues-panel { display: none !important; }
      .server {
        background: #fff;
        border: 1px solid #ccc;
        border-radius: 8px;
        page-break-inside: avoid;
        break-inside: avoid;
        margin-bottom: 16px;
        box-shadow: none;
      }
      .server-head h2 { color: #111; }
      .host, .updated { color: #555; }
      .cmd-block {
        background: #f8fafc;
        border-color: #ddd;
      }
      .cmd-block h4, .card h3 { color: #c2410c; }
      .cmd-summary { color: #166534; }
      .card {
        background: #f8fafc;
        border-color: #ddd;
      }
      .stat { color: #111; }
      .stat-label, .sub { color: #555; }
      .bar { background: #eee; border-color: #ccc; }
      .data-table th { color: #555; background: #f1f5f9; }
      .data-table td { color: #111; }
      .raw-output { color: #111; }
      .footer { display: none; }
    }
    button.secondary {
      background: #0f141d;
      color: var(--text);
      border: 1px solid var(--border);
      height: 30px;
      padding: 0 12px;
      font-size: 0.82rem;
    }
    button.secondary:hover { border-color: var(--accent); color: var(--accent2); }
    .cmd-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
    }
    .cmd-head h4 { margin: 0; }
    .capacity-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px;
      margin: 14px 0;
    }
    .capacity-pools-wrap { margin-top: 8px; }
    .capacity-pool-block {
      margin-top: 18px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
    }
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(3, 6, 10, 0.72);
      display: none;
      align-items: center;
      justify-content: center;
      padding: 24px;
      z-index: 1000;
    }
    .modal-backdrop.open { display: flex; }
    .modal {
      width: min(920px, 100%);
      max-height: 88vh;
      overflow: auto;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 20px 22px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.45);
    }
    .modal-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border);
    }
    .modal-head h3 {
      margin: 0;
      color: var(--accent);
      font-size: 1.2rem;
    }
    .modal-body .table-wrap { max-height: 58vh; }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>LaunchPad Health</h1>
      <p>SSH monitoring is <strong>off by default</strong> — turn on per site or use <strong>All monitoring on</strong> when you need live stats.</p>
      <div class="hero-actions">
        <button type="button" id="refresh-all-btn">Refresh On Sites (one by one)</button>
        <a class="btn secondary" href="/capacity" style="font:inherit;border-radius:10px;height:34px;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;padding:0 14px;font-weight:600;background:#0f141d;color:var(--text);border:1px solid var(--border);">Capacity Report</a>
        <a class="btn secondary" href="/fc-wwpn" style="font:inherit;border-radius:10px;height:34px;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;padding:0 14px;font-weight:600;background:#0f141d;color:var(--text);border:1px solid var(--border);">FC WWPN</a>
        <a class="btn secondary" href="/snapshot-schedule" style="font:inherit;border-radius:10px;height:34px;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;padding:0 14px;font-weight:600;background:#0f141d;color:var(--text);border:1px solid var(--border);">Snapshot Schedule</a>
        <label class="toggle-row" for="monitor-all-toggle" title="Connect and monitor every site. Leave off to keep SSH sessions closed.">
          <input type="checkbox" id="monitor-all-toggle">
          All monitoring on
        </label>
        <label class="toggle-row" for="show-alerts-toggle">
          <input type="checkbox" id="show-alerts-toggle" checked>
          Show alerts
        </label>
        <span id="refresh-status" class="refresh-status"></span>
      </div>
      <div class="filter-bar no-print">
        <input type="search" id="health-search" placeholder="Find sites for PDF (all sites stay visible)" aria-label="Search servers">
        <button type="button" id="select-visible-btn" class="secondary">Select matches</button>
        <button type="button" id="clear-selection-btn" class="secondary">Clear selection</button>
        <span id="selection-count" class="selection-count"></span>
        <button type="button" id="print-btn">Print / Save PDF</button>
      </div>
      <p id="print-meta" class="print-meta"></p>
      <p id="search-hint" class="search-hint no-print"></p>
      <p id="summary" class="summary"></p>
    </section>
    <section id="issues-panel" class="issues-panel">
      <h2>Issues Requiring Attention</h2>
      <div id="issues-list" class="issue-list"></div>
    </section>
    <div id="servers"></div>
    <p class="footer no-print">LaunchPad Health v{{APP_VERSION}} · Keep LaunchPad running and unlocked while refreshing. Use <strong>Health Dashboard</strong> in LaunchPad to refresh live stats. To print selected sites, check <strong>PDF</strong> on each card (or search and use <strong>Select matches</strong>), then <strong>Print / Save PDF</strong>.</p>
  </div>
  <div id="detail-modal" class="modal-backdrop" aria-hidden="true">
    <div class="modal" role="dialog" aria-modal="true">
      <div class="modal-head">
        <h3 id="modal-title">Details</h3>
        <button type="button" class="secondary" id="modal-close">Close</button>
      </div>
      <div id="modal-body" class="modal-body"></div>
    </div>
  </div>
  <script>
    const serversEl = document.getElementById("servers");
    const summaryEl = document.getElementById("summary");
    const refreshStatusEl = document.getElementById("refresh-status");
    const refreshAllBtn = document.getElementById("refresh-all-btn");
    const issuesListEl = document.getElementById("issues-list");
    const modalEl = document.getElementById("detail-modal");
    const modalTitleEl = document.getElementById("modal-title");
    const modalBodyEl = document.getElementById("modal-body");
    const modalCloseEl = document.getElementById("modal-close");
    const showAlertsToggle = document.getElementById("show-alerts-toggle");
    const monitorAllToggle = document.getElementById("monitor-all-toggle");
    const healthSearchEl = document.getElementById("health-search");
    const selectVisibleBtn = document.getElementById("select-visible-btn");
    const clearSelectionBtn = document.getElementById("clear-selection-btn");
    const selectionCountEl = document.getElementById("selection-count");
    const printBtn = document.getElementById("print-btn");
    const printMetaEl = document.getElementById("print-meta");
    const searchHintEl = document.getElementById("search-hint");
    const SHOW_ALERTS_PREF_KEY = "launchpad.healthDashboard.showAlerts";
    const MONITOR_PREF_PREFIX = "launchpad.healthDashboard.monitor-";
    const autoTimers = {};
    let monitorServerState = {};

    function isMonitorOn(cardId) {
      const key = String(cardId);
      if (Object.prototype.hasOwnProperty.call(monitorServerState, key)) {
        return Boolean(monitorServerState[key]);
      }
      try {
        return localStorage.getItem(MONITOR_PREF_PREFIX + cardId) === "1";
      } catch (_err) {
        return false;
      }
    }

    async function persistMonitor(cardId, on, syncServer = true) {
      monitorServerState[String(cardId)] = on;
      try {
        localStorage.setItem(MONITOR_PREF_PREFIX + cardId, on ? "1" : "0");
      } catch (_err) {
        /* ignore storage errors */
      }
      if (!syncServer) return;
      try {
        await fetch("/api/monitor", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ card_id: cardId, enabled: on }),
        });
      } catch (_err) {
        /* best effort */
      }
    }

    async function loadMonitorState() {
      try {
        const res = await fetch("/api/monitor");
        if (!res.ok) return;
        const data = await res.json();
        monitorServerState = data.states || {};
        for (const [id, enabled] of Object.entries(monitorServerState)) {
          try {
            localStorage.setItem(MONITOR_PREF_PREFIX + id, enabled ? "1" : "0");
          } catch (_err) {
            /* ignore storage errors */
          }
        }
      } catch (_err) {
        /* best effort */
      }
    }

    function updateMasterMonitorToggle() {
      if (!monitorAllToggle) return;
      const ids = cardsCache.map((card) => card.id);
      const allOn = ids.length > 0 && ids.every((id) => isMonitorOn(id));
      monitorAllToggle.checked = allOn;
    }

    function applyMonitorVisual(cardId) {
      const section = document.querySelector(`.server[data-id="${cardId}"]`);
      if (!section) return;
      const on = isMonitorOn(cardId);
      section.classList.toggle("monitor-off", !on);
      const toggle = section.querySelector(".monitor-toggle");
      if (toggle) toggle.classList.toggle("on", on);
      const input = section.querySelector(".monitor-switch");
      if (input) input.checked = on;
      const note = section.querySelector(".paused-note");
      if (note) note.style.display = on ? "none" : "";
      const select = section.querySelector(".auto-select");
      if (select) select.disabled = !on;
    }

    function setMonitor(cardId, on, { refresh = true } = {}) {
      void persistMonitor(cardId, on).then(() => {
        applyMonitorVisual(cardId);
        if (on) {
          applyAutoSelect(cardId);
          if (refresh) refreshCard(cardId).catch(() => {});
        } else if (autoTimers[cardId]) {
          clearInterval(autoTimers[cardId]);
          delete autoTimers[cardId];
        }
        updateMasterMonitorToggle();
      });
    }

    async function setAllMonitoring(on) {
      const ids = cardsCache.map((card) => card.id).sort((a, b) => a - b);
      try {
        await fetch("/api/monitor", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ all: true, enabled: on }),
        });
        const res = await fetch("/api/monitor");
        if (res.ok) {
          const data = await res.json();
          monitorServerState = data.states || {};
        }
      } catch (_err) {
        /* best effort */
      }
      ids.forEach((id) => {
        void persistMonitor(id, on, false);
        applyMonitorVisual(id);
        if (!on && autoTimers[id]) {
          clearInterval(autoTimers[id]);
          delete autoTimers[id];
        }
      });
      updateMasterMonitorToggle();
      if (!on) {
        if (refreshStatusEl) refreshStatusEl.textContent = "All monitoring off.";
        return;
      }
      if (!ids.length) return;
      if (refreshAllRunning) return;
      refreshAllRunning = true;
      if (refreshAllBtn) refreshAllBtn.disabled = true;
      try {
        for (let index = 0; index < ids.length; index += 1) {
          const id = ids[index];
          applyAutoSelect(id);
          const card = cardsCache.find((entry) => entry.id === id);
          if (refreshStatusEl) {
            refreshStatusEl.textContent =
              `Connecting ${card ? card.name : id} (${index + 1}/${ids.length})...`;
          }
          try {
            await refreshCard(id);
          } catch (_err) {
            /* refreshCard shows its own error */
          }
        }
        if (refreshStatusEl) refreshStatusEl.textContent = "All sites connected.";
      } finally {
        refreshAllRunning = false;
        if (refreshAllBtn) refreshAllBtn.disabled = false;
      }
    }

    const knownIds = new Set();
    const printSelectedIds = new Set();
    let refreshAllRunning = false;
    let cardsCache = [];

    function isAlertCmdBlock(item) {
      const label = (item.label || "").toLowerCase();
      const cmd = (item.command || "").toLowerCase();
      return (
        label.includes("alert") ||
        cmd.includes("lseventlog") ||
        cmd.includes("showalert") ||
        cmd.includes("lsalertentry")
      );
    }

    function applyShowAlerts(show) {
      document.body.classList.toggle("hide-health-alerts", !show);
    }

    function loadShowAlertsPref() {
      let show = true;
      if (localStorage.getItem(SHOW_ALERTS_PREF_KEY) === "0") show = false;
      applyShowAlerts(show);
      if (showAlertsToggle) showAlertsToggle.checked = show;
    }

    function saveShowAlertsPref(show) {
      localStorage.setItem(SHOW_ALERTS_PREF_KEY, show ? "1" : "0");
      applyShowAlerts(show);
    }

    function cardSearchText(card) {
      const port = card.port ? `:${card.port}` : "";
      return `${card.name} ${card.host}${port} ${card.username || ""}`.toLowerCase();
    }

    function healthSearchQuery() {
      return (healthSearchEl?.value || "").toLowerCase().trim();
    }

    function serverMatchesSearch(section, query) {
      if (!query) return true;
      return (section.dataset.search || "").toLowerCase().includes(query);
    }

    function applyHealthSearch() {
      const query = healthSearchQuery();
      let matchCount = 0;
      document.querySelectorAll(".server").forEach((section) => {
        const match = serverMatchesSearch(section, query);
        section.classList.toggle("search-match", Boolean(query) && match);
        if (match) matchCount += 1;
      });
      if (searchHintEl) {
        if (!query) {
          searchHintEl.textContent = "";
        } else {
          searchHintEl.textContent =
            matchCount === 1
              ? "1 site matches — use Select matches to check PDF on it."
              : `${matchCount} sites match — use Select matches to check PDF on them.`;
        }
      }
      updateSelectionCount();
    }

    function serversMatchingSearch() {
      const query = healthSearchQuery();
      return [...document.querySelectorAll(".server")].filter((section) =>
        serverMatchesSearch(section, query)
      );
    }

    function updateSelectionCount() {
      if (!selectionCountEl) return;
      const count = printSelectedIds.size;
      selectionCountEl.textContent = count
        ? `${count} selected for PDF`
        : "Check PDF on cards to select sites";
    }

    function syncPrintSelectionClasses() {
      document.querySelectorAll(".server").forEach((section) => {
        const id = parseInt(section.dataset.id, 10);
        section.classList.toggle("print-selected", printSelectedIds.has(id));
      });
    }

    function wirePrintCheckboxes() {
      document.querySelectorAll(".print-select").forEach((checkbox) => {
        const id = parseInt(checkbox.dataset.id, 10);
        checkbox.checked = printSelectedIds.has(id);
        if (checkbox.dataset.wired) return;
        checkbox.dataset.wired = "1";
        checkbox.addEventListener("change", () => {
          if (checkbox.checked) printSelectedIds.add(id);
          else printSelectedIds.delete(id);
          syncPrintSelectionClasses();
          updateSelectionCount();
        });
      });
    }

    function selectVisibleServers() {
      serversMatchingSearch().forEach((section) => {
        printSelectedIds.add(parseInt(section.dataset.id, 10));
      });
      wirePrintCheckboxes();
      syncPrintSelectionClasses();
      updateSelectionCount();
    }

    function clearPrintSelection() {
      printSelectedIds.clear();
      wirePrintCheckboxes();
      syncPrintSelectionClasses();
      updateSelectionCount();
    }

    function printSelectedHealth() {
      if (!printSelectedIds.size) {
        window.alert(
          "Select at least one server to print.\\n\\nCheck PDF on each card, or search for sites and click Select matches."
        );
        return;
      }
      syncPrintSelectionClasses();
      if (printMetaEl) {
        const names = [...printSelectedIds]
          .map((id) => cardsCache.find((entry) => entry.id === id)?.name)
          .filter(Boolean);
        printMetaEl.textContent = `LaunchPad Health · ${names.join(" · ")} · ${new Date().toLocaleString()}`;
      }
      document.body.classList.add("print-export");
      const afterPrint = () => {
        document.body.classList.remove("print-export");
        window.removeEventListener("afterprint", afterPrint);
      };
      window.addEventListener("afterprint", afterPrint);
      window.print();
    }

    function openModal(title, htmlBody) {
      modalTitleEl.textContent = title;
      modalBodyEl.innerHTML = htmlBody || "<p class='sub'>(no details)</p>";
      modalEl.classList.add("open");
      modalEl.setAttribute("aria-hidden", "false");
    }

    function closeModal() {
      modalEl.classList.remove("open");
      modalEl.setAttribute("aria-hidden", "true");
      modalBodyEl.innerHTML = "";
    }

    modalCloseEl.addEventListener("click", closeModal);
    modalEl.addEventListener("click", (event) => {
      if (event.target === modalEl) closeModal();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeModal();
    });

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
      if (card.command_results && card.command_results.length) {
        return commandResultsHtml(card);
      }
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

    function commandResultsHtml(card) {
      let banner = "";
      if (card.error && card.command_results && card.command_results.length) {
        banner = `<div class="error">${escapeHtml(card.error)}</div>`;
      }
      return banner + card.command_results.map((item, index) => {
        const failClass = item.error ? " fail" : "";
        let body;
        if (item.error) {
          body = `<div class="error">${escapeHtml(item.error)}</div>`;
        } else if (item.output_html) {
          body = item.output_html;
        } else {
          body = `<pre class="raw-output">${escapeHtml(item.output || "(no output)")}</pre>`;
        }
        const alertAttr = isAlertCmdBlock(item) ? "1" : "0";
        return `
          <article class="cmd-block${failClass}" data-label="${escapeHtml(item.label)}" data-index="${index}" data-alert="${alertAttr}">
            <div class="cmd-head">
              <h4>${escapeHtml(item.label)}</h4>
              <button type="button" class="detail-btn secondary no-print" data-card-id="${card.id}" data-index="${index}">Details</button>
            </div>
            <code>${escapeHtml(item.command)}</code>
            ${body}
          </article>`;
      }).join("");
    }

    function groupIssues(allIssues) {
      const groups = new Map();
      for (const issue of allIssues) {
        const key = `${issue.severity}|${issue.category}|${issue.message}`;
        if (!groups.has(key)) {
          groups.set(key, {
            severity: issue.severity,
            category: issue.category,
            message: issue.message,
            items: [],
          });
        }
        groups.get(key).items.push(issue);
      }
      return Array.from(groups.values());
    }

    function issueSubRows(items) {
      const byServer = new Map();
      for (const item of items) {
        byServer.set(item.server, (byServer.get(item.server) || 0) + 1);
      }
      return Array.from(byServer.entries())
        .sort((a, b) => a[0].localeCompare(b[0]))
        .map(
          ([server, count]) =>
            `<div class="issue-sub"><strong>${escapeHtml(server)}</strong>${
              count > 1 ? ` <span class="issue-sub-count">×${count}</span>` : ""
            }</div>`
        )
        .join("");
    }

    function wireIssueGroupToggles() {
      issuesListEl.querySelectorAll(".issue-group-head").forEach((btn) => {
        if (btn.dataset.wired) return;
        btn.dataset.wired = "1";
        btn.addEventListener("click", () => {
          const group = btn.closest(".issue-group");
          if (!group) return;
          const open = group.classList.toggle("open");
          btn.setAttribute("aria-expanded", open ? "true" : "false");
        });
      });
    }

    function renderIssues(cards) {
      if (!issuesListEl) return;
      const allIssues = [];
      cards.forEach((card) => {
        if (!isMonitorOn(card.id)) return;
        (card.health_issues || []).forEach((issue) => allIssues.push(issue));
      });
      if (!allIssues.length) {
        issuesListEl.innerHTML = '<p class="issues-ok">No issues detected across monitored systems.</p>';
        return;
      }
      const rank = { critical: 0, warn: 1 };
      const groups = groupIssues(allIssues);
      groups.sort(
        (a, b) =>
          (rank[a.severity] ?? 9) - (rank[b.severity] ?? 9) ||
          a.message.localeCompare(b.message)
      );
      issuesListEl.innerHTML = groups
        .map((group) => {
          const count = group.items.length;
          const sev = escapeHtml(group.severity);
          const cat = escapeHtml(group.category);
          const msg = escapeHtml(group.message);
          if (count === 1) {
            const issue = group.items[0];
            return `
          <div class="issue ${sev}">
            <strong>${escapeHtml(issue.server)}</strong>
            <span> · ${cat} · ${msg}</span>
          </div>`;
          }
          return `
          <div class="issue-group ${sev}">
            <button type="button" class="issue-group-head" aria-expanded="false">
              <span class="issue-chevron" aria-hidden="true">▼</span>
              <span class="issue-group-text">${cat} · ${msg}</span>
              <span class="issue-count" title="${count} matching alerts">${count}</span>
            </button>
            <div class="issue-group-body">${issueSubRows(group.items)}</div>
          </div>`;
        })
        .join("");
      wireIssueGroupToggles();
    }

    function cardHasData(card) {
      if (card.metrics && Object.keys(card.metrics).length) return true;
      if (card.command_results && card.command_results.length) {
        return card.command_results.some((item) => !item.error);
      }
      return false;
    }

    function updateSummary(cards) {
      if (!summaryEl) return;
      if (!cards.length) {
        summaryEl.textContent = "";
        summaryEl.className = "summary";
        return;
      }
      const active = cards.filter((card) => isMonitorOn(card.id));
      const off = cards.length - active.length;
      const ok = active.filter((card) => card.updated_at && cardHasData(card)).length;
      const failed = active.filter((card) => card.error && !cardHasData(card)).length;
      const pending = active.length - ok - failed;
      const parts = [`${cards.length} server${cards.length === 1 ? "" : "s"}`];
      if (ok) parts.push(`${ok} healthy`);
      if (failed) parts.push(`${failed} failing`);
      if (pending) parts.push(`${pending} not refreshed`);
      if (off) parts.push(`${off} monitoring off`);
      summaryEl.textContent = parts.join(" · ");
      summaryEl.className = "summary " + (failed ? (ok ? "warn" : "bad") : "ok");
    }

    function quickCmdButtons(cardId, hasCapacity) {
      const capacityBtn = hasCapacity
        ? `<button type="button" class="capacity-btn secondary" data-card-id="${cardId}">Capacity</button>`
        : "";
      return `
        <div class="quick-cmds no-print">
          ${capacityBtn}
          <button type="button" class="quick-btn" data-id="${cardId}" data-kind="health">Health</button>
          <button type="button" class="quick-btn" data-id="${cardId}" data-kind="cpu">CPU</button>
          <button type="button" class="quick-btn" data-id="${cardId}" data-kind="memory">Memory</button>
          <button type="button" class="quick-btn" data-id="${cardId}" data-kind="disk">Disk</button>
          <button type="button" class="quick-btn" data-id="${cardId}" data-kind="capacity">Capacity</button>
          <button type="button" class="quick-btn" data-id="${cardId}" data-kind="all">Full Health</button>
        </div>`;
    }

    function highlightMetric(cardId, kind) {
      const section = document.querySelector(`.server[data-id="${cardId}"]`);
      if (!section) return;
      section.scrollIntoView({ behavior: "smooth", block: "start" });
      if (kind === "all") {
        refreshCard(cardId);
        return;
      }
      if (kind === "capacity") {
        const card = cardsCache.find((entry) => entry.id === cardId);
        if (card && card.capacity_popup_html) {
          openModal(`${card.name} - Capacity`, card.capacity_popup_html);
          return;
        }
      }
      const matchers = {
        cpu: (label) => label.includes("cpu"),
        memory: (label) => label.includes("memory"),
        disk: (label) => label.includes("disk") || label.includes("mdisk"),
        capacity: (label) => label.includes("capacity") || label.includes("system"),
        health: (label) => label.includes("health") || label.includes("alert") || label.includes("controller"),
      };
      const match = matchers[kind] || (() => true);
      let found = false;
      section.querySelectorAll(".cmd-block, .card").forEach((block) => {
        block.style.outline = "";
        const label = (block.dataset.label || block.querySelector("h3,h4")?.textContent || "").toLowerCase();
        if (match(label)) {
          block.style.outline = "2px solid var(--accent)";
          if (!found) {
            block.scrollIntoView({ behavior: "smooth", block: "nearest" });
            found = true;
          }
        }
      });
      if (!found && kind !== "all") {
        refreshCard(cardId);
      }
    }
    function hostLabel(card) {
      const port = card.port ? `:${card.port}` : "";
      const user = card.username ? `${card.username}@` : "";
      return `${user}${card.host}${port}`;
    }

    function renderCard(card) {
      const updated = card.updated_at ? `Last updated: ${card.updated_at}` : "Not refreshed yet";
      const monitorOn = isMonitorOn(card.id);
      const failClass = monitorOn && card.error && !cardHasData(card) ? " fail" : "";
      const offClass = monitorOn ? "" : " monitor-off";
      const hasCapacity = Boolean(card.capacity_popup_html);
      const selectedClass = printSelectedIds.has(card.id) ? " print-selected" : "";
      return `
        <section class="server${failClass}${offClass}${selectedClass}" data-id="${card.id}" data-search="${escapeHtml(cardSearchText(card))}">
          <div class="server-head">
            <label class="print-select-label no-print">
              <input type="checkbox" class="print-select" data-id="${card.id}"${printSelectedIds.has(card.id) ? " checked" : ""}>
              PDF
            </label>
            <h2>${escapeHtml(card.name)}</h2>
            <span class="host">${escapeHtml(hostLabel(card))}</span>
            <div class="controls no-print">
              <label class="monitor-toggle${monitorOn ? " on" : ""}" title="Turn on to connect over SSH and refresh this site.">
                <input type="checkbox" class="monitor-switch" data-id="${card.id}"${monitorOn ? " checked" : ""}>
                Monitor
              </label>
              ${hasCapacity ? `<button type="button" class="capacity-btn secondary" data-card-id="${card.id}">Capacity</button>` : ""}
              <button type="button" class="refresh-btn" data-id="${card.id}">Refresh</button>
              <select class="auto-select" data-id="${card.id}" aria-label="Auto refresh interval"${monitorOn ? "" : " disabled"}>
                <option value="0">Auto: Off</option>
                <option value="10">Auto: 10 sec</option>
                <option value="30">Auto: 30 sec</option>
                <option value="60">Auto: 60 sec</option>
              </select>
            </div>
          </div>
          ${quickCmdButtons(card.id, hasCapacity)}
          <div class="metrics">${metricsHtml(card)}</div>
          <p class="paused-note"${monitorOn ? ' style="display:none"' : ""}>Monitoring off — showing last snapshot. Turn on Monitor to connect over SSH.</p>
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
      if (seconds > 0 && isMonitorOn(cardId)) {
        autoTimers[cardId] = setInterval(() => {
          if (isMonitorOn(cardId)) refreshCard(cardId);
        }, seconds * 1000);
      }
    }

    function wireServerSection(card) {
      const section = document.querySelector(`.server[data-id="${card.id}"]`);
      if (!section) return;
      applyAutoSelect(card.id);
      const refreshBtn = section.querySelector(".refresh-btn");
      if (refreshBtn) refreshBtn.onclick = () => refreshCard(card.id);
      section.querySelectorAll(".quick-btn").forEach((btn) => {
        btn.onclick = () => highlightMetric(card.id, btn.dataset.kind);
      });
      const monitorSwitch = section.querySelector(".monitor-switch");
      if (monitorSwitch) {
        monitorSwitch.onchange = () => setMonitor(card.id, monitorSwitch.checked);
      }
      const autoSelect = section.querySelector(".auto-select");
      if (autoSelect && !autoSelect.dataset.wired) {
        autoSelect.dataset.wired = "1";
        autoSelect.onchange = () =>
          setAutoRefresh(card.id, parseInt(autoSelect.value, 10) || 0);
      }
      applyMonitorVisual(card.id);
      section.classList.toggle(
        "fail",
        isMonitorOn(card.id) && Boolean(card.error) && !cardHasData(card)
      );
    }

    function updateCardSection(card) {
      const section = document.querySelector(`.server[data-id="${card.id}"]`);
      if (!section) return false;
      const wrapper = document.createElement("div");
      wrapper.innerHTML = renderCard(card);
      const newSection = wrapper.firstElementChild;
      section.replaceWith(newSection);
      wireServerSection(card);
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
        const cacheIndex = cardsCache.findIndex((entry) => entry.id === card.id);
        if (cacheIndex >= 0) cardsCache[cacheIndex] = card;
        else cardsCache.push(card);
        updateSummary(cardsCache);
        renderIssues(cardsCache);
        wireInteractiveButtons();
        return card;
      } catch (err) {
        if (section) {
          section.querySelector(".metrics").innerHTML =
            `<div class="error">${escapeHtml(err.message || err)}</div>`;
          section.classList.add("fail");
        }
        throw err;
      } finally {
        if (section) section.classList.remove("loading");
        if (button) button.disabled = false;
      }
    }

    async function refreshAllSequential() {
      if (refreshAllRunning) return;
      refreshAllRunning = true;
      if (refreshAllBtn) refreshAllBtn.disabled = true;
      try {
        const res = await fetch("/api/cards");
        const all = (await res.json()).sort((a, b) => a.id - b.id);
        const cards = all.filter((card) => isMonitorOn(card.id));
        if (!cards.length) {
          if (refreshStatusEl) {
            refreshStatusEl.textContent = all.length
              ? "No sites are on. Turn on Monitor or use All monitoring on."
              : "No servers to refresh.";
          }
          return;
        }
        for (let index = 0; index < cards.length; index += 1) {
          const card = cards[index];
          if (refreshStatusEl) {
            refreshStatusEl.textContent =
              `Refreshing ${card.name} (${index + 1}/${cards.length})...`;
          }
          try {
            await refreshCard(card.id);
          } catch (_err) {
            // refreshCard already shows the error on the server section
          }
        }
        if (refreshStatusEl) refreshStatusEl.textContent = "Refresh complete.";
      } finally {
        refreshAllRunning = false;
        if (refreshAllBtn) refreshAllBtn.disabled = false;
      }
    }

    function renderAll(cards) {
      document.body.classList.remove("print-export");
      if (!cards.length) {
        serversEl.innerHTML =
          '<div class="empty">No servers loaded yet. Keep LaunchPad running and unlocked, then click <strong>Health Dashboard</strong> in LaunchPad.</div>';
        updateSummary([]);
        renderIssues([]);
        return;
      }
      const sorted = [...cards].sort((a, b) => a.id - b.id);
      const seen = new Set(sorted.map((card) => card.id));

      try {
        serversEl.innerHTML = sorted.map((card) => renderCard(card)).join("");
      } catch (err) {
        serversEl.innerHTML =
          `<div class="error">Could not render servers: ${escapeHtml(err.message || err)}</div>`;
        return;
      }

      knownIds.forEach((id) => {
        if (!seen.has(id)) knownIds.delete(id);
      });
      sorted.forEach((card) => {
        knownIds.add(card.id);
        applyAutoSelect(card.id);
      });

      document.querySelectorAll(".refresh-btn").forEach((btn) => {
        const id = parseInt(btn.dataset.id, 10);
        btn.onclick = () => refreshCard(id);
      });
      document.querySelectorAll(".quick-btn").forEach((btn) => {
        const id = parseInt(btn.dataset.id, 10);
        const kind = btn.dataset.kind;
        btn.onclick = () => highlightMetric(id, kind);
      });
      document.querySelectorAll(".auto-select").forEach((select) => {
        const cardId = parseInt(select.dataset.id, 10);
        if (!select.dataset.wired) {
          select.dataset.wired = "1";
          select.onchange = () => setAutoRefresh(cardId, parseInt(select.value, 10) || 0);
        }
      });
      document.querySelectorAll(".monitor-switch").forEach((input) => {
        const cardId = parseInt(input.dataset.id, 10);
        input.onchange = () => setMonitor(cardId, input.checked);
      });
      sorted.forEach((card) => applyMonitorVisual(card.id));
      updateMasterMonitorToggle();
      updateSummary(sorted);
      renderIssues(sorted);
      wireInteractiveButtons();
      wirePrintCheckboxes();
      applyHealthSearch();
      syncPrintSelectionClasses();
      updateSelectionCount();
    }

    function wireInteractiveButtons() {
      document.querySelectorAll(".detail-btn").forEach((btn) => {
        btn.onclick = () => {
          const cardId = parseInt(btn.dataset.cardId, 10);
          const index = parseInt(btn.dataset.index, 10);
          const card = cardsCache.find((entry) => entry.id === cardId);
          if (!card || !card.command_results || !card.command_results[index]) return;
          const item = card.command_results[index];
          openModal(
            `${card.name} - ${item.label}`,
            item.output_html_detail || item.output_html || `<pre class="raw-output">${escapeHtml(item.output || "")}</pre>`
          );
        };
      });
      document.querySelectorAll(".capacity-btn").forEach((btn) => {
        btn.onclick = () => {
          const cardId = parseInt(btn.dataset.cardId, 10);
          const card = cardsCache.find((entry) => entry.id === cardId);
          if (!card || !card.capacity_popup_html) return;
          openModal(`${card.name} - Capacity`, card.capacity_popup_html);
        };
      });
    }

    async function loadCards() {
      try {
        if (refreshStatusEl && !refreshAllRunning) {
          refreshStatusEl.textContent = "Loading servers from LaunchPad...";
        }
        if (serversEl && !cardsCache.length) {
          serversEl.innerHTML = '<div class="empty">Loading servers from LaunchPad...</div>';
        }
        try {
          await fetch("/api/sync", { method: "POST" });
        } catch (_syncErr) {
          // Sync is best-effort; /api/cards also syncs when LaunchPad is unlocked.
        }
        await loadMonitorState();
        const res = await fetch("/api/cards");
        if (!res.ok) {
          throw new Error(`Health server returned ${res.status}`);
        }
        const cards = await res.json();
        cardsCache = Array.isArray(cards) ? cards : [];
        renderAll(cardsCache);
        wireInteractiveButtons();
        if (refreshStatusEl && !refreshAllRunning) {
          refreshStatusEl.textContent = cardsCache.length
            ? `${cardsCache.length} server(s) loaded`
            : "No servers — keep LaunchPad unlocked and click Health Dashboard";
        }
      } catch (err) {
        serversEl.innerHTML =
          `<div class="error">${escapeHtml(err.message || err)}. Keep LaunchPad running and unlocked, then click <strong>Health Dashboard</strong> in the app.</div>`;
        if (summaryEl) {
          summaryEl.textContent = "";
          summaryEl.className = "summary";
        }
        if (refreshStatusEl) {
          refreshStatusEl.textContent = "Could not load servers";
        }
      }
    }

    if (refreshAllBtn) {
      refreshAllBtn.onclick = () => refreshAllSequential();
    }

    if (showAlertsToggle) {
      showAlertsToggle.addEventListener("change", () => {
        saveShowAlertsPref(showAlertsToggle.checked);
      });
    }
    if (monitorAllToggle) {
      monitorAllToggle.addEventListener("change", () => {
        setAllMonitoring(monitorAllToggle.checked);
      });
    }
    if (healthSearchEl) {
      healthSearchEl.addEventListener("input", applyHealthSearch);
    }
    if (selectVisibleBtn) {
      selectVisibleBtn.addEventListener("click", selectVisibleServers);
    }
    if (clearSelectionBtn) {
      clearSelectionBtn.addEventListener("click", clearPrintSelection);
    }
    if (printBtn) {
      printBtn.addEventListener("click", printSelectedHealth);
    }
    loadShowAlertsPref();

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
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(
        self,
        body: bytes,
        *,
        content_type: str,
        filename: str,
        status: int = 200,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="{filename}"',
        )
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        server = get_health_server()
        if path == "/":
            self._send_html(DASHBOARD_HTML.replace("{{APP_VERSION}}", APP_VERSION))
            return
        if path == CAPACITY_REPORT_PATH:
            self._send_html(CAPACITY_REPORT_HTML.replace("{{APP_VERSION}}", APP_VERSION))
            return
        if path == SNAPSHOT_SCHEDULE_PATH:
            self._send_html(SNAPSHOT_SCHEDULE_HTML.replace("{{APP_VERSION}}", APP_VERSION))
            return
        if path == CONTINGENCY_GROUPS_PATH:
            self._send_html(CONTINGENCY_GROUPS_HTML.replace("{{APP_VERSION}}", APP_VERSION))
            return
        if path == FC_WWPN_REPORT_PATH:
            self._send_html(FC_WWPN_REPORT_HTML.replace("{{APP_VERSION}}", APP_VERSION))
            return
        if path == "/api/cards":
            self._send_json(server.list_cards())
            return
        if path == "/api/sync":
            count = server.sync_from_app()
            cards = server.list_cards(allow_sync=False)
            self._send_json({"synced": count, "total": len(cards)})
            return
        if path == "/api/monitor":
            self._send_json({"states": server.monitor_states(), "default": False})
            return
        if path == "/api/snapshot-notes":
            self._send_json({"notes": server.get_snapshot_notes(), "persisted": True})
            return
        if path == "/api/snapshot-schedule-overrides":
            persisted = server.snapshot_schedule_persist_available()
            self._send_json(
                {
                    "overrides": server.get_snapshot_overrides() if persisted else {},
                    "persisted": persisted,
                }
            )
            return
        if path == "/api/contingency-groups":
            persisted = server.contingency_groups_persist_available()
            self._send_json(
                {
                    "groups": server.get_contingency_groups() if persisted else [],
                    "persisted": persisted,
                }
            )
            return
        if path == "/api/contingency-groups-export":
            from launchpad.contingency_groups_export import (
                build_contingency_groups_workbook,
                workbook_to_bytes,
            )

            query = parse_qs(parsed.query)
            group_id = (query.get("id") or [""])[0].strip()
            try:
                groups = server.get_contingency_groups()
                if group_id:
                    groups = [
                        g
                        for g in groups
                        if str(g.get("id") or "").strip() == group_id
                    ]
                wb = build_contingency_groups_workbook(groups)
                body = workbook_to_bytes(wb)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
            if group_id:
                safe_id = re.sub(r"[^\w\-]+", "_", group_id).strip("_") or "group"
                filename = f"Contingency_{safe_id}_{stamp}.xlsx"
            else:
                filename = f"Contingency_Groups_{stamp}.xlsx"
            self._send_bytes(
                body,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=filename,
            )
            return
        if path == "/api/snapshot-schedule-export":
            from launchpad.snapshot_schedule_export import (
                build_snapshot_schedule_workbook,
                workbook_to_bytes,
            )

            query = parse_qs(parsed.query)
            try:
                threshold = float((query.get("threshold") or ["80"])[0])
            except (TypeError, ValueError):
                threshold = 80.0
            threshold = max(50.0, min(95.0, threshold))
            groups_raw = (query.get("groups") or ["wag1,wag2,other"])[0]
            groups = {
                part.strip().lower()
                for part in str(groups_raw).split(",")
                if part.strip()
            }
            try:
                server.sync_from_app()
                cards = server.list_cards(allow_sync=False)
                notes = server.get_snapshot_notes()
                overrides = server.get_snapshot_overrides()
                wb = build_snapshot_schedule_workbook(
                    cards,
                    notes,
                    threshold=threshold,
                    groups=groups,
                    overrides=overrides,
                )
                body = workbook_to_bytes(wb)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
            if groups >= {"wag1", "wag2", "other"}:
                group_label = "All"
            elif not groups:
                group_label = "None"
            else:
                group_label = "_".join(
                    sorted("Other" if g == "other" else g.upper() for g in groups)
                )
            self._send_bytes(
                body,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=f"Snapshot_Schedule_{group_label}_{stamp}.xlsx",
            )
            return
        if path == "/api/fc-wwpn-export":
            from launchpad.capacity_export import open_exported_workbook
            from launchpad.config import TEMP_DIR
            from launchpad.fc_wwpn_export import build_fc_wwpn_workbook, workbook_to_bytes
            from launchpad.storage_presets import is_svc_fc_profile

            query = parse_qs(parsed.query)
            open_after = (query.get("open") or ["1"])[0].strip().lower() in {
                "1",
                "true",
                "yes",
            }
            try:
                server.sync_from_app()
                cards = [
                    card
                    for card in server.list_cards(allow_sync=False)
                    if is_svc_fc_profile(str(card.get("device_profile") or ""))
                    or bool(card.get("fc_available"))
                ]
                wb, port_count, host_count, map_count = build_fc_wwpn_workbook(cards)
                body = workbook_to_bytes(wb)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
            filename = f"FC_WWPN_Report_{stamp}.xlsx"
            if open_after:
                try:
                    TEMP_DIR.mkdir(parents=True, exist_ok=True)
                    saved = TEMP_DIR / filename
                    saved.write_bytes(body)
                    open_exported_workbook(saved)
                    _log(
                        f"FC Excel opened: {saved} "
                        f"({port_count} ports, {host_count} hosts, {map_count} maps)"
                    )
                except Exception as open_exc:
                    _log(f"FC Excel saved for download but could not open: {open_exc}")
            self._send_bytes(
                body,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=filename,
            )
            return
        self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        server = get_health_server()
        if path == "/api/sync":
            count = server.sync_from_app()
            cards = server.list_cards(allow_sync=False)
            self._send_json({"synced": count, "total": len(cards)})
            return
        if path == "/api/monitor":
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, status=400)
                return
            enabled = bool(payload.get("enabled"))
            if payload.get("all"):
                server.set_monitor_enabled(enabled=enabled, all_cards=True)
            else:
                try:
                    card_id = int(payload.get("card_id"))
                except (TypeError, ValueError):
                    self._send_json({"error": "card_id required"}, status=400)
                    return
                server.set_monitor_enabled(card_id=card_id, enabled=enabled)
            self._send_json({"states": server.monitor_states(), "default": False})
            return
        if path == "/api/snapshot-notes":
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, status=400)
                return
            try:
                if "notes" in payload and isinstance(payload.get("notes"), dict):
                    notes = server.set_snapshot_notes(
                        {str(k): str(v) for k, v in payload["notes"].items()}
                    )
                else:
                    card_id = payload.get("card_id")
                    if card_id is None:
                        self._send_json({"error": "card_id or notes required"}, status=400)
                        return
                    notes = server.set_snapshot_note(card_id, str(payload.get("note", "")))
            except RuntimeError as exc:
                self._send_json({"error": str(exc), "persisted": False}, status=503)
                return
            self._send_json({"notes": notes, "persisted": True})
            return
        if path == "/api/snapshot-schedule-overrides":
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, status=400)
                return
            try:
                if "overrides" in payload and isinstance(payload["overrides"], dict):
                    overrides = server.set_snapshot_overrides(payload["overrides"])
                else:
                    card_id = payload.get("card_id")
                    if card_id is None:
                        self._send_json({"error": "card_id required"}, status=400)
                        return
                    overrides = server.set_snapshot_override(
                        card_id, payload.get("override") or {}
                    )
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=503)
                return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json({"overrides": overrides, "persisted": True})
            return
        if path == "/api/contingency-groups":
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, status=400)
                return
            if not isinstance(payload, dict):
                self._send_json({"error": "JSON object required"}, status=400)
                return
            try:
                if "groups" in payload:
                    if not isinstance(payload["groups"], list):
                        raise ValueError("groups must be a list")
                    groups = server.set_contingency_groups(payload["groups"])
                elif "group" in payload:
                    if not isinstance(payload["group"], dict):
                        raise ValueError("group must be an object")
                    groups = server.upsert_contingency_group(payload["group"])
                elif "delete_id" in payload:
                    groups = server.delete_contingency_group(str(payload["delete_id"]))
                else:
                    raise ValueError("groups, group, or delete_id required")
            except RuntimeError as exc:
                self._send_json({"error": str(exc), "persisted": False}, status=503)
                return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json({"groups": groups, "persisted": True})
            return
        if not path.startswith("/api/refresh/"):
            self.send_error(404)
            return
        suffix = path.removeprefix("/api/refresh/")
        try:
            card_id = int(suffix)
        except ValueError:
            self.send_error(400)
            return
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


SNAPSHOT_NOTES_SETTING = "snapshot_schedule_notes"


class HealthServer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cards: dict[int, HealthCard] = {}
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._port = DEFAULT_PORT
        self._browser_opened = False
        self._capacity_browser_opened = False
        self._fc_browser_opened = False
        self._started = False
        self._sync_provider: Callable[[], int] | None = None
        self._get_setting: Callable[[str, str], str] | None = None
        self._set_setting: Callable[[str, str], None] | None = None
        self._monitor_enabled: dict[int, bool] = {}

    def set_sync_provider(self, provider: Callable[[], int] | None) -> None:
        with self._lock:
            self._sync_provider = provider

    def set_settings_backend(
        self,
        get_setting: Callable[[str, str], str] | None,
        set_setting: Callable[[str, str], None] | None,
    ) -> None:
        with self._lock:
            self._get_setting = get_setting
            self._set_setting = set_setting

    def snapshot_schedule_persist_available(self) -> bool:
        with self._lock:
            return self._get_setting is not None

    def contingency_groups_persist_available(self) -> bool:
        with self._lock:
            return self._get_setting is not None

    def get_contingency_groups(self) -> list[dict]:
        with self._lock:
            getter = self._get_setting
            setter = self._set_setting
        if not getter:
            return []
        raw = getter(CONTINGENCY_GROUPS_SETTING, "[]") or "[]"
        try:
            groups = normalize_groups(json.loads(raw))
        except json.JSONDecodeError:
            groups = []
        if groups or not setter:
            return groups
        groups = seed_contingency_groups()
        setter(CONTINGENCY_GROUPS_SETTING, json.dumps(groups))
        return groups

    def set_contingency_groups(self, groups: list[dict]) -> list[dict]:
        with self._lock:
            setter = self._set_setting
        if not setter:
            raise RuntimeError("LaunchPad must be unlocked to save contingency groups.")
        cleaned = normalize_groups(groups)
        setter(CONTINGENCY_GROUPS_SETTING, json.dumps(cleaned))
        return cleaned

    def upsert_contingency_group(self, group: dict) -> list[dict]:
        cleaned = normalize_group(group)
        if cleaned is None:
            raise ValueError("Invalid contingency group")
        return self.set_contingency_groups(
            upsert_group(self.get_contingency_groups(), cleaned)
        )

    def delete_contingency_group(self, group_id: str) -> list[dict]:
        return self.set_contingency_groups(
            delete_group(self.get_contingency_groups(), group_id)
        )

    def get_snapshot_notes(self) -> dict[str, str]:
        with self._lock:
            getter = self._get_setting
        if not getter:
            return {}
        raw = getter(SNAPSHOT_NOTES_SETTING, "{}") or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): str(value) for key, value in data.items()}

    def set_snapshot_note(self, card_id: int | str, note: str) -> dict[str, str]:
        with self._lock:
            getter = self._get_setting
            setter = self._set_setting
        if not getter or not setter:
            raise RuntimeError("LaunchPad must be unlocked to save notes to the database.")
        notes = self.get_snapshot_notes()
        key = str(card_id)
        cleaned = (note or "").strip()
        if cleaned:
            notes[key] = note
        else:
            notes.pop(key, None)
        setter(SNAPSHOT_NOTES_SETTING, json.dumps(notes))
        return notes

    def set_snapshot_notes(self, notes: dict[str, str]) -> dict[str, str]:
        with self._lock:
            setter = self._set_setting
        if not setter:
            raise RuntimeError("LaunchPad must be unlocked to save notes to the database.")
        cleaned = {
            str(key): str(value)
            for key, value in (notes or {}).items()
            if str(value).strip()
        }
        setter(SNAPSHOT_NOTES_SETTING, json.dumps(cleaned))
        return cleaned

    def get_snapshot_overrides(self) -> dict[str, dict]:
        with self._lock:
            getter = self._get_setting
        if not getter:
            return {}
        raw = getter(SNAPSHOT_OVERRIDES_SETTING, "{}") or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return normalize_overrides_map(data)

    def set_snapshot_override(
        self, card_id: int | str, override: dict
    ) -> dict[str, dict]:
        with self._lock:
            getter = self._get_setting
            setter = self._set_setting
        if not getter or not setter:
            raise RuntimeError("LaunchPad must be unlocked to save schedule overrides.")
        cleaned = normalize_override(override)
        if cleaned is None:
            raise ValueError("Invalid schedule override")
        mapping = self.get_snapshot_overrides()
        mapping[str(card_id)] = cleaned
        setter(SNAPSHOT_OVERRIDES_SETTING, json.dumps(mapping))
        return mapping

    def set_snapshot_overrides(self, overrides: dict) -> dict[str, dict]:
        with self._lock:
            setter = self._set_setting
        if not setter:
            raise RuntimeError("LaunchPad must be unlocked to save schedule overrides.")
        cleaned = normalize_overrides_map(overrides)
        setter(SNAPSHOT_OVERRIDES_SETTING, json.dumps(cleaned))
        return cleaned

    def clear_cards(self) -> None:
        with self._lock:
            self._cards.clear()
            self._monitor_enabled.clear()

    def prune_cards(self, keep_ids: set[int]) -> None:
        with self._lock:
            for card_id in list(self._cards.keys()):
                if card_id not in keep_ids:
                    del self._cards[card_id]
                    self._monitor_enabled.pop(card_id, None)

    def monitor_states(self) -> dict[str, bool]:
        with self._lock:
            return {str(card_id): self._monitor_enabled.get(card_id, False) for card_id in self._cards}

    def set_monitor_enabled(
        self,
        *,
        card_id: int | None = None,
        enabled: bool,
        all_cards: bool = False,
    ) -> None:
        with self._lock:
            if all_cards:
                for registered_id in self._cards:
                    self._monitor_enabled[registered_id] = enabled
            elif card_id is not None:
                self._monitor_enabled[card_id] = enabled

    def is_monitor_enabled(self, card_id: int) -> bool:
        with self._lock:
            return self._monitor_enabled.get(card_id, False)

    def sync_from_app(self) -> int:
        with self._lock:
            provider = self._sync_provider
        if not provider:
            return 0
        try:
            count = provider()
            if count:
                _log(f"Health dashboard synced {count} card(s) from LaunchPad")
            return count
        except Exception as exc:
            _log(f"Health dashboard sync failed: {exc}")
            return 0

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._port}/"

    @property
    def capacity_report_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{CAPACITY_REPORT_PATH}"

    @property
    def fc_wwpn_report_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{FC_WWPN_REPORT_PATH}"

    @property
    def contingency_groups_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{CONTINGENCY_GROUPS_PATH}"

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
        password: str = "",
        device_profile: str = "",
        custom_commands: str = "",
        serial_number: str = "",
        category: str = "",
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
                key_passphrase=key_passphrase,
                password=password,
                device_profile=device_profile,
                custom_commands=custom_commands,
                serial_number=serial_number,
                category=category,
                metrics=existing.metrics if existing else None,
                command_results=existing.command_results if existing else None,
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
            password = card.password
            device_profile = card.device_profile
            custom_commands = card.custom_commands
            serial_number = card.serial_number

        commands = resolve_card_commands(
            device_profile,
            custom_commands,
            instance_id=serial_number,
        )
        if commands:
            command_results = run_remote_command_suite(
                host,
                port,
                username,
                commands,
                key_path,
                key_passphrase,
                password,
                device_profile=device_profile,
            )
            failures = [item for item in command_results if item.get("error")]
            if failures and len(failures) == len(command_results):
                error = failures[0]["error"]
            elif failures:
                error = f"{len(failures)} of {len(command_results)} command(s) failed"
            else:
                error = None
            metrics = None
        else:
            try:
                metrics = run_remote_metrics(
                    host,
                    port,
                    username,
                    key_path,
                    key_passphrase,
                    password,
                )
                error = None
                command_results = None
            except Exception as exc:
                metrics = None
                command_results = None
                error = str(exc)

        with self._lock:
            card.metrics = metrics
            card.command_results = command_results
            card.error = error
            card.updated_at = _utc_now()
            return card

    def update_card_live_data(
        self,
        card_id: int,
        *,
        command_results: list[dict[str, Any]] | None = None,
        metrics: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> bool:
        """Push live SSH results from the desktop UI into the health API cards."""
        with self._lock:
            card = self._cards.get(card_id)
            if not card:
                return False
            if command_results is not None:
                card.command_results = command_results
            if metrics is not None:
                card.metrics = metrics
            if error is not None:
                card.error = error
            elif command_results is not None or metrics is not None:
                card.error = None
            card.updated_at = _utc_now()
            return True

    def list_cards(self, *, allow_sync: bool = True) -> list[dict[str, Any]]:
        if allow_sync:
            self.sync_from_app()
        with self._lock:
            stored = list(sorted(self._cards.values(), key=lambda c: c.card_id))
        results: list[dict[str, Any]] = []
        for card in stored:
            try:
                results.append(card.to_api())
            except Exception as exc:
                _log(f"Health API serialize failed for {card.name}: {exc}")
                results.append(
                    {
                        "id": card.card_id,
                        "name": card.name,
                        "host": card.host,
                        "port": card.port,
                        "username": card.username,
                        "device_profile": card.device_profile,
                        "command_mode": False,
                        "metrics": card.metrics,
                        "command_results": card.command_results,
                        "error": card.error or str(exc),
                        "updated_at": card.updated_at,
                        "health_issues": [],
                        "capacity_summary": None,
                        "capacity_popup_html": None,
                        "pools": [],
                        "fc_ports": [],
                        "fc_hosts": [],
                        "fc_mappings": [],
                        "fc_fabric": [],
                        "fc_ports_by_node": [],
                        "fc_available": False,
                        "model": DEVICE_PROFILES.get(card.device_profile, card.device_profile or ""),
                        "category": card.category,
                    }
                )
        return results

    def open_browser_once(self) -> str:
        """Open the health dashboard in the default browser (every call)."""
        return self.open_browser()

    def open_browser(self) -> str:
        self.ensure_running()
        webbrowser.open(self.url)
        self._browser_opened = True
        _log(f"Opened health dashboard in browser: {self.url}")
        return self.url

    def open_capacity_report_once(self) -> str:
        """Open the capacity report in the default browser (every call)."""
        return self.open_capacity_report()

    def open_capacity_report(self) -> str:
        self.ensure_running()
        webbrowser.open(self.capacity_report_url)
        self._capacity_browser_opened = True
        _log(f"Opened capacity report in browser: {self.capacity_report_url}")
        return self.capacity_report_url

    def open_fc_wwpn_report_once(self) -> str:
        """Open the FC WWPN report in the default browser (every call)."""
        return self.open_fc_wwpn_report()

    def open_fc_wwpn_report(self) -> str:
        self.ensure_running()
        webbrowser.open(self.fc_wwpn_report_url)
        self._fc_browser_opened = True
        _log(f"Opened FC WWPN report in browser: {self.fc_wwpn_report_url}")
        return self.fc_wwpn_report_url

    def open_contingency_groups(self) -> str:
        """Open the contingency groups reference page in the default browser."""
        self.ensure_running()
        webbrowser.open(self.contingency_groups_url)
        _log(f"Opened contingency groups in browser: {self.contingency_groups_url}")
        return self.contingency_groups_url


_instance: HealthServer | None = None
_instance_lock = threading.Lock()


def get_health_server() -> HealthServer:
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = HealthServer()
        return _instance
