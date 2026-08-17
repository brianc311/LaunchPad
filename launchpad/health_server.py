import base64
import binascii
import hashlib
import json
import re
import socket
import tempfile
import threading
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import paramiko

from launchpad.ansible_pad import ANSIBLE_PAD_HTML, ANSIBLE_PAD_PATH
from launchpad.ansible_pad_export import (
    build_ansible_pad_files,
    build_ansible_pad_zip_bytes,
)
from launchpad.ansible_pad_remote import (
    build_ansible_playbook_argv,
    require_confirm_for_mutate,
    run_remote_argv,
    sync_files_via_sftp,
)
from launchpad.ansible_pad_settings import (
    ANSIBLE_PAD_DEFAULT_PLAYBOOK,
    ANSIBLE_PAD_HOST,
    ANSIBLE_PAD_KEY_PASSPHRASE_ENCRYPTED,
    ANSIBLE_PAD_KEY_PATH,
    ANSIBLE_PAD_PASSWORD_ENCRYPTED,
    ANSIBLE_PAD_REMOTE_DIR,
    ANSIBLE_PAD_USER,
    normalize_ansible_pad_settings,
)
from launchpad.capacity_report import CAPACITY_REPORT_HTML, CAPACITY_REPORT_PATH
from launchpad.capacity_units import get_capacity_unit_mode
from launchpad.command_format import resolve_card_commands
from launchpad.config import APP_VERSION, TEMP_DIR
from launchpad.contingency_groups_data import (
    CONTINGENCY_GROUPS_SETTING,
    delete_group,
    ensure_groups_for_cards,
    generate_snap_rows,
    new_group_id,
    normalize_group,
    normalize_groups,
    seed_contingency_groups,
    upsert_group,
)
from launchpad.contingency_groups import CONTINGENCY_GROUPS_HTML, CONTINGENCY_GROUPS_PATH
from launchpad.contingency_snap_create import (
    SnapStep,
    append_snap_cg_assign_steps,
    build_snap_steps,
    cli_token,
    collect_inventory,
    resolve_card_by_storage_hint,
    run_snap_steps,
)
from launchpad.crypto import decrypt_text, encrypt_text
from launchpad.fc_cg_summary import (
    build_cg_summaries,
    schedule_context_from_capacity,
)
from launchpad.esx_snap_policy import ESX_SNAP_POLICY_HTML, ESX_SNAP_POLICY_PATH
from launchpad.fc_consistgrp import FC_CONSISTGRP_HTML, FC_CONSISTGRP_PATH
from launchpad.esx_snap_policy_ops import (
    POLICY_NAME,
    apply_checked_volume_details,
    build_esx_snap_array_steps,
    collect_esx_snap_inventory,
    default_vg_name,
    preview_hash,
    steps_payload,
)
from launchpad.fc_consistgrp_ops import (
    build_fc_consistgrp_steps,
    collect_fc_consistgrp_inventory,
    format_flash_time_display,
    is_fc_consistgrp_status_eligible,
    normalize_fc_cg_status_bucket,
    partition_maps,
    preview_ok as fc_consistgrp_preview_ok,
)
from launchpad.fc_cg_summary_export import (
    export_fc_cg_summary_multisite_xlsx,
    export_fc_cg_summary_xlsx,
)
from launchpad.fc_consistgrp_status_export import (
    export_fc_consistgrp_status_xlsx,
    filter_status_rows,
)
from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML, FC_WWPN_REPORT_PATH
from launchpad.host_volume_health import (
    filter_problem_hosts,
    filter_problem_volumes,
    is_volume_find_eligible,
)
from launchpad.host_volume_health_page import (
    HOST_VOLUME_HEALTH_HTML,
    HOST_VOLUME_HEALTH_PATH,
)
from launchpad.host_power import HOST_POWER_HTML, HOST_POWER_PATH
from launchpad.host_power_ops import (
    HOST_POWER_MODE_SHUTDOWN_ONLY,
    HOST_POWER_MUTATE_SSH_TIMEOUT,
    HOST_POWER_PRECHECK_SSH_TIMEOUT,
    build_host_power_preview,
    coerce_card_ids,
    extract_power_steps,
    host_power_precheck_catalog_payload,
    normalize_host_power_mode,
    normalize_precheck_letter,
    require_host_power_confirm,
    run_host_power_for_card,
    run_host_power_precheck_for_card,
    steps_for_host_power_mode,
)
from launchpad.snapcopy_summary_page import (
    SNAPCOPY_SUMMARY_HTML,
    SNAPCOPY_SUMMARY_PATH,
)
from launchpad.firmware_catalog import (
    get_profile_catalog,
    grow_catalog_from_currents,
    load_firmware_auto_add,
    load_firmware_catalog,
    save_firmware_catalog,
)
from launchpad.system_connectivity import (
    TOPICS,
    base_row,
    enrich_firmware_row,
    enrich_license_key_row,
    finalize_row,
    hpe_call_home_na_row,
    is_system_connectivity_eligible,
    parse_ds_firmware,
    parse_ds_license_key,
    parse_ds_networkport_dns,
    parse_ds_showsp_call_home,
    parse_hpe_showlicense,
    parse_hpe_shownet_dns_ntp,
    parse_hpe_showversion_firmware,
    parse_hpe_snmpmgr,
    parse_svc_call_home,
    parse_svc_dns,
    parse_svc_firmware_from_lssystem,
    parse_svc_lsencryption,
    parse_svc_ntp_from_lssystem,
    parse_svc_snmp,
    parse_svc_svqueryclock,
    topic_commands_for_profile,
    wrap_topic_commands_for_card,
    vendor_for_profile as system_connectivity_vendor,
)
from launchpad.system_connectivity_page import (
    SYSTEM_CONNECTIVITY_HTML,
    SYSTEM_CONNECTIVITY_PATH,
)
from launchpad.storage_inventory import (
    StorageInventoryProgress,
    build_inventory_row,
    export_storage_inventory_xlsx,
    inventory_commands_for_profile,
    inventory_totals,
    is_hpe_inventory_profile,
    is_storage_inventory_eligible,
    wrap_inventory_commands_for_card,
    parse_hpe_showrcopy_protection,
    parse_svc_lsemailserver,
    parse_svc_lsrcrelationship,
    parse_svc_lssystem_identity,
    parse_svc_lssystem_volume_protection,
)
from launchpad.storage_inventory_page import (
    STORAGE_INVENTORY_HTML,
    STORAGE_INVENTORY_PATH,
)
from launchpad.flashsystem_fc import (
    analyze_fc_inventory,
    parse_fabric_logins,
    parse_fc_hosts,
    parse_host_lun_maps,
    parse_lsconsistgrp,
    parse_lsvdisk_volumes,
)
from launchpad.capacity_pool_family import capacity_pool_family
from launchpad.dell_report_family import dell_report_family, dell_report_family_for_site
from launchpad.flashsystem_health import analyze_health, pool_capacity_from_commands
from launchpad.health_alert_art import resolve_health_alert_art
from launchpad.health_alert_state import (
    HEALTH_ALERT_SETTING,
    acknowledge,
    dump_state,
    empty_state,
    fingerprints_for_card,
    list_popup_alerts,
    load_state,
    pause_card,
    prepare_health_issue_limit,
    prune_acknowledgements,
    set_alarm,
    visible_health_issues,
)
from launchpad.health_excel_export import (
    HealthExcelSections,
    build_health_workbook,
    parse_health_excel_sections,
)
from launchpad.health_metrics import run_remote_metrics
from launchpad.inventory_sync import build_inventory_sync
from launchpad.lun_builder import LUN_BUILDER_HTML, LUN_BUILDER_PATH
from launchpad.lun_offline_inventory import (
    LUN_OFFLINE_INVENTORY_SETTING,
    is_lun_offline_inventory_eligible,
    normalize_store,
    record_snapshot_error,
    snapshot_from_command_results,
    summarize_snapshot,
    upsert_snapshot,
)
from launchpad.volume_find_page import VOLUME_FIND_HTML, VOLUME_FIND_PATH
from launchpad.lun_builder_data import (
    LUN_BUILDS_SETTING,
    delete_build,
    normalize_build,
    normalize_builds,
    seed_lun_builder_templates,
    supports_live_run,
    upsert_build,
    validate_build_for_preview,
)
from launchpad.lun_builder_create import build_lun_steps, run_lun_steps
from launchpad.mouse_jiggler import SETTING_MOUSE_JIGGLER, setting_to_enabled
from launchpad.site_lookup import SITE_LOOKUP_HTML, SITE_LOOKUP_PATH
from launchpad.site_lookup_data import (
    inventory_from_command_results,
    payload_from_card_cache,
    payload_from_live,
    payload_from_lun_offline,
    payload_from_offline_snapshot,
    payload_has_inventory,
    shape_hosts_for_lookup,
    shape_volumes_for_lookup,
    showvv_inventory_note,
)
from launchpad.site_lookup_offline import (
    SITE_LOOKUP_OFFLINE_SETTING,
    normalize_store as normalize_site_lookup_offline_store,
    snapshot_from_live_payload,
    upsert_snapshot as upsert_site_lookup_offline_snapshot,
)
from launchpad.lun_builder_export import (
    export_lun_build_csv_zip,
    export_lun_build_xlsx,
)
from launchpad.lun_builder_import import (
    map_fc_hosts,
    merge_hosts,
    parse_lun_builder_upload,
)
from launchpad.snapshot_schedule import SNAPSHOT_SCHEDULE_HTML, SNAPSHOT_SCHEDULE_PATH
from launchpad.snapshot_schedule_overrides import (
    SNAPSHOT_OVERRIDES_SETTING,
    normalize_override,
    normalize_overrides_map,
)
from launchpad.ssh_commands import run_remote_command_suite, run_remote_ssh_command
from launchpad.ssh_launcher import _log
from launchpad.ssh_paramiko import run_ssh_auth_hpe_commands
from launchpad.storage_presets import (
    DEVICE_PROFILES,
    HPE_SHELL_PROFILES,
    SVC_PROFILES,
    is_svc_fc_profile,
)
from launchpad.volume_find import (
    anderson_rename_plan,
    apply_pathsum_status_to_hosts,
    find_hosts_in_cards,
    find_volumes_in_cards,
    host_name_matches,
    is_volume_find_eligible,
    normalize_site_host,
    parse_showhost_hosts,
    parse_showhost_pathsum_status,
    parse_showvv_volumes,
    vendor_for_profile,
    volume_name_matches,
)

DEFAULT_PORT = 18765
PREFERRED_PORTS = (18765, 18766, 18767, 18768)

_ANSIBLE_PAD_SETTING_FIELDS = {
    ANSIBLE_PAD_HOST: "host",
    ANSIBLE_PAD_USER: "user",
    ANSIBLE_PAD_KEY_PATH: "key_path",
    ANSIBLE_PAD_REMOTE_DIR: "remote_dir",
    ANSIBLE_PAD_DEFAULT_PLAYBOOK: "default_playbook",
}
_ANSIBLE_PAD_SECRET_SETTINGS = {
    ANSIBLE_PAD_KEY_PASSPHRASE_ENCRYPTED: "key_passphrase",
    ANSIBLE_PAD_PASSWORD_ENCRYPTED: "password",
}


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
    sudo_password: str = ""
    device_profile: str = ""
    custom_commands: str = ""
    serial_number: str = ""
    dscli_path: str = ""
    dscli_hmc: str = ""
    category: str = ""
    url: str = ""
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
            "card_type": "ssh",
            "capacity_unit_mode": get_capacity_unit_mode(),
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "device_profile": self.device_profile,
            "dell_report_family": dell_report_family_for_site(
                self.device_profile, site_name=self.name
            ),
            "pool_family": capacity_pool_family(
                self.device_profile, site_name=self.name
            ),
            "model": model,
            "serial_number": self.serial_number,
            "category": self.category,
            "command_mode": bool(
                resolve_card_commands(
                    self.device_profile,
                    self.custom_commands,
                    instance_id=self.serial_number,
                    dscli_path=self.dscli_path or "",
                    dscli_hmc=self.dscli_hmc or "",
                    username=str(self.username or ""),
                    password=self.password or "",
                )
            ),
            "metrics": self.metrics,
            "command_results": self.command_results,
            "error": self.error,
            "updated_at": self.updated_at,
            "health_issues": analysis["health_issues"],
            "capacity_summary": analysis["capacity_summary"],
            "raw_capacity_summary": analysis.get("raw_capacity_summary"),
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
    a:not(.btn) {
      color: #9ec1ff;
      text-decoration: underline;
      text-underline-offset: 2px;
    }
    a:not(.btn):hover { color: #c5d9ff; }
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
    .card-active-issues {
      margin-top: 12px;
      border: 1px solid rgba(255, 107, 0, 0.45);
      border-radius: 12px;
      padding: 12px 14px;
      background: #121821;
    }
    .card-active-issues h3 {
      margin: 0 0 10px;
      color: var(--accent);
      font-size: 1rem;
    }
    .card-active-issues .issue-list { margin: 0; }
    .card-active-issues .issues-ok { font-size: 0.9rem; }
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
    #health-alert-modal { z-index: 1100; }
    .health-alert-modal {
      background-position: center;
      background-repeat: no-repeat;
      background-size: cover;
    }
    .health-alert-modal > .modal-head,
    .health-alert-modal > .modal-body {
      background: rgba(15, 20, 29, 0.88);
      border-radius: 12px;
      padding: 14px;
    }
    .health-alert-card-name {
      margin: 0 0 12px;
      font-size: 1.35rem;
      color: var(--bad);
    }
    .health-alert-issues {
      margin: 0 0 18px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .health-alert-issues .issue { margin: 0; }
    .health-alert-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .health-alert-actions .pause-group {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
    }
    .health-alert-actions .pause-label {
      color: var(--muted);
      font-size: 0.82rem;
      margin-right: 2px;
    }
    .alarm-muted-badge {
      display: inline-flex;
      align-items: center;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 0.75rem;
      font-weight: 600;
      color: #fde68a;
      background: rgba(251, 191, 36, 0.15);
      border: 1px solid rgba(251, 191, 36, 0.35);
    }
    .server.alarm-muted .server-head h2::after {
      content: " · alarm muted";
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 600;
    }
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
        <a class="btn secondary" href="/esx-snap-policy" style="font:inherit;border-radius:10px;height:34px;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;padding:0 14px;font-weight:600;background:#0f141d;color:var(--text);border:1px solid var(--border);">ESX-snap Policy</a>
        <a class="btn secondary" href="/lun-builder" style="font:inherit;border-radius:10px;height:34px;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;padding:0 14px;font-weight:600;background:#0f141d;color:var(--text);border:1px solid var(--border);">LUN Builder</a>
        <a class="btn secondary" href="/fc-consistgrp" style="font:inherit;border-radius:10px;height:34px;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;padding:0 14px;font-weight:600;background:#0f141d;color:var(--text);border:1px solid var(--border);">FlashCopy CGs</a>
        <a class="btn secondary" href="/host-volume-health" style="font:inherit;border-radius:10px;height:34px;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;padding:0 14px;font-weight:600;background:#0f141d;color:var(--text);border:1px solid var(--border);">Hosts & Volumes</a>
        <a class="btn secondary" href="/system-connectivity" style="font:inherit;border-radius:10px;height:34px;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;padding:0 14px;font-weight:600;background:#0f141d;color:var(--text);border:1px solid var(--border);">System Connectivity</a>
        <label class="toggle-row" for="monitor-all-toggle" title="Connect and monitor every site. Leave off to keep SSH sessions closed.">
          <input type="checkbox" id="monitor-all-toggle">
          All monitoring on
        </label>
        <label class="toggle-row" for="include-off-toggle" title="When unchecked, only Monitor-on sites are shown. Check to show monitoring-off sites again.">
          <input type="checkbox" id="include-off-toggle">
          Include monitoring-off sites
        </label>
        <label class="toggle-row" for="show-alerts-toggle">
          <input type="checkbox" id="show-alerts-toggle" checked>
          Show alerts
        </label>
        <span id="refresh-status" class="refresh-status"></span>
        <span id="jiggler-status" class="refresh-status">Mouse jiggler: Off</span>
      </div>
      <div class="filter-bar no-print">
        <label>Site <select id="health-site-select"><option value="">All servers</option></select></label>
        <input type="search" id="health-search" placeholder="Find sites for PDF (all sites stay visible)" aria-label="Search servers">
        <button type="button" id="select-visible-btn" class="secondary">Select matches</button>
        <button type="button" id="clear-selection-btn" class="secondary">Clear selection</button>
        <span id="selection-count" class="selection-count"></span>
        <button type="button" id="print-btn">Print / Save PDF</button>
        <button type="button" id="health-excel-btn" class="secondary">Export Excel</button>
        <label class="toggle-row"><input type="checkbox" id="health-excel-summary" checked> Summary</label>
        <label class="toggle-row"><input type="checkbox" id="health-excel-issues" checked> Issues</label>
        <label class="toggle-row"><input type="checkbox" id="health-excel-cmd-summaries" checked> Command summaries</label>
        <label class="toggle-row"><input type="checkbox" id="health-excel-raw"> Raw output</label>
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
  <div id="health-alert-modal" class="modal-backdrop" aria-hidden="true">
    <div class="modal health-alert-modal" role="dialog" aria-modal="true" aria-labelledby="health-alert-title">
      <div class="modal-head">
        <h3 id="health-alert-title">Critical Health Alert</h3>
        <button type="button" class="secondary" id="health-alert-close-btn">Close</button>
      </div>
      <div class="modal-body">
        <p id="health-alert-card-name" class="health-alert-card-name"></p>
        <div id="health-alert-issues" class="health-alert-issues issue-list"></div>
        <div class="health-alert-actions">
          <button type="button" id="health-alert-ack-btn">Suppress</button>
          <button type="button" class="secondary" id="health-alert-alarm-btn">Alarm off</button>
          <div class="pause-group">
            <button type="button" class="secondary health-alert-pause-btn" data-minutes="5">Snooze 5 min</button>
            <button type="button" class="secondary health-alert-pause-btn" data-minutes="10">Snooze 10 min</button>
            <button type="button" class="secondary health-alert-pause-btn" data-minutes="15">Snooze 15 min</button>
            <button type="button" class="secondary health-alert-pause-btn" data-minutes="20">Snooze 20 min</button>
          </div>
        </div>
      </div>
    </div>
  </div>
  <script>
    let CAPACITY_UNIT_MODE = "{{CAPACITY_UNIT_MODE}}";
    const serversEl = document.getElementById("servers");
    const summaryEl = document.getElementById("summary");
    const refreshStatusEl = document.getElementById("refresh-status");
    const jigglerStatusEl = document.getElementById("jiggler-status");
    const refreshAllBtn = document.getElementById("refresh-all-btn");
    const issuesListEl = document.getElementById("issues-list");
    const modalEl = document.getElementById("detail-modal");
    const modalTitleEl = document.getElementById("modal-title");
    const modalBodyEl = document.getElementById("modal-body");
    const modalCloseEl = document.getElementById("modal-close");
    const healthAlertModalEl = document.getElementById("health-alert-modal");
    const healthAlertArtEl = healthAlertModalEl?.querySelector(".health-alert-modal");
    const healthAlertCardNameEl = document.getElementById("health-alert-card-name");
    const healthAlertIssuesEl = document.getElementById("health-alert-issues");
    const healthAlertAckBtn = document.getElementById("health-alert-ack-btn");
    const healthAlertAlarmBtn = document.getElementById("health-alert-alarm-btn");
    const healthAlertCloseBtn = document.getElementById("health-alert-close-btn");
    const healthAlertPauseBtns = document.querySelectorAll(".health-alert-pause-btn");
    const showAlertsToggle = document.getElementById("show-alerts-toggle");
    const monitorAllToggle = document.getElementById("monitor-all-toggle");
    const includeOffToggle = document.getElementById("include-off-toggle");
    const healthSiteSelectEl = document.getElementById("health-site-select");
    const healthSearchEl = document.getElementById("health-search");
    const selectVisibleBtn = document.getElementById("select-visible-btn");
    const clearSelectionBtn = document.getElementById("clear-selection-btn");
    const selectionCountEl = document.getElementById("selection-count");
    const printBtn = document.getElementById("print-btn");
    const healthExcelBtn = document.getElementById("health-excel-btn");
    const healthExcelSummaryEl = document.getElementById("health-excel-summary");
    const healthExcelIssuesEl = document.getElementById("health-excel-issues");
    const healthExcelCmdSummariesEl = document.getElementById("health-excel-cmd-summaries");
    const healthExcelRawEl = document.getElementById("health-excel-raw");
    const printMetaEl = document.getElementById("print-meta");
    const searchHintEl = document.getElementById("search-hint");
    const SHOW_ALERTS_PREF_KEY = "launchpad.healthDashboard.showAlerts";
    const MONITOR_PREF_PREFIX = "launchpad.healthDashboard.monitor-";
    const HEALTH_EXCEL_PREF = {
      summary: "launchpad.healthExcel.summary",
      issues: "launchpad.healthExcel.issues",
      commandSummaries: "launchpad.healthExcel.commandSummaries",
      rawOutput: "launchpad.healthExcel.rawOutput",
    };
    const autoTimers = {};
    let monitorServerState = {};
    const HEALTH_ALERT_POLL_MS = 30000;
    let healthAlertQueue = [];
    let healthAlertQueueIndex = 0;
    let healthAlertCurrent = null;
    let healthAlertModalOpen = false;
    let healthAlertPollRunning = false;
    let healthAlertCardsMeta = {};

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
        renderAll(cardsCache);
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
      renderAll(cardsCache);
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

    function siteOptionLabel(card) {
      return `${card.name} (${card.host || ""})`;
    }

    function selectedSiteId() {
      if (!healthSiteSelectEl) return null;
      const raw = healthSiteSelectEl.value;
      if (!raw) return null;
      const id = parseInt(raw, 10);
      return Number.isFinite(id) ? id : null;
    }

    function populateHealthSiteSelect(cards) {
      if (!healthSiteSelectEl) return;
      const previous = healthSiteSelectEl.value;
      const sorted = [...cards].sort((a, b) =>
        (a.name || "").localeCompare(b.name || "", undefined, { sensitivity: "base" })
      );
      healthSiteSelectEl.innerHTML =
        '<option value="">All servers</option>' +
        sorted
          .map(
            (card) =>
              `<option value="${card.id}">${escapeHtml(siteOptionLabel(card))}</option>`
          )
          .join("");
      if (previous && sorted.some((card) => String(card.id) === previous)) {
        healthSiteSelectEl.value = previous;
      } else {
        healthSiteSelectEl.value = "";
      }
    }

    function applySiteFilter() {
      const siteId = selectedSiteId();
      document.querySelectorAll(".server").forEach((section) => {
        const id = parseInt(section.dataset.id, 10);
        const visible = siteId == null || id === siteId;
        section.style.display = visible ? "" : "none";
      });
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

    function loadHealthExcelPrefs() {
      const pairs = [
        [healthExcelSummaryEl, HEALTH_EXCEL_PREF.summary, true],
        [healthExcelIssuesEl, HEALTH_EXCEL_PREF.issues, true],
        [healthExcelCmdSummariesEl, HEALTH_EXCEL_PREF.commandSummaries, true],
        [healthExcelRawEl, HEALTH_EXCEL_PREF.rawOutput, false],
      ];
      for (const [el, key, defaultOn] of pairs) {
        if (!el) continue;
        const saved = localStorage.getItem(key);
        if (saved === null) el.checked = defaultOn;
        else el.checked = saved === "1";
      }
    }

    function saveHealthExcelPref(el, key) {
      if (!el) return;
      localStorage.setItem(key, el.checked ? "1" : "0");
    }

    function healthExcelSectionFlag(el, defaultOn) {
      if (!el) return defaultOn ? "1" : "0";
      return el.checked ? "1" : "0";
    }

    async function downloadHealthExcel() {
      if (!healthExcelBtn) return;
      const summaryOn = !healthExcelSummaryEl || healthExcelSummaryEl.checked;
      const siteId = selectedSiteId();
      const detailIds = siteId != null ? [siteId] : [...printSelectedIds];
      if (!detailIds.length && !summaryOn) {
        if (refreshStatusEl) {
          refreshStatusEl.textContent =
            "Select PDF sites or pick a site, or enable Summary, before exporting.";
        }
        return;
      }
      healthExcelBtn.disabled = true;
      if (refreshStatusEl) refreshStatusEl.textContent = "Building Health Summary Excel…";
      try {
        const parts = [];
        for (const id of detailIds) {
          parts.push(`card_id=${encodeURIComponent(id)}`);
        }
        parts.push(`summary=${healthExcelSectionFlag(healthExcelSummaryEl, true)}`);
        parts.push(`issues=${healthExcelSectionFlag(healthExcelIssuesEl, true)}`);
        parts.push(
          `command_summaries=${healthExcelSectionFlag(healthExcelCmdSummariesEl, true)}`
        );
        parts.push(`raw=${healthExcelSectionFlag(healthExcelRawEl, false)}`);
        parts.push("open=1");
        const res = await fetch(`/api/health-export?${parts.join("&")}`);
        if (!res.ok) {
          let detail = `HTTP ${res.status}`;
          try {
            const err = await res.json();
            if (err && err.error) detail = err.error;
          } catch (_err) {
            /* ignore */
          }
          throw new Error(detail);
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        const stamp = new Date().toISOString().slice(0, 16).replace(/[:-]/g, "");
        a.href = url;
        a.download = `Health_Summary_${stamp}.xlsx`;
        a.click();
        URL.revokeObjectURL(url);
        if (refreshStatusEl) {
          refreshStatusEl.textContent = "Health Summary Excel downloaded and opened in Excel.";
        }
      } catch (err) {
        if (refreshStatusEl) {
          refreshStatusEl.textContent = `Health Excel export failed: ${err.message || err}`;
        }
      } finally {
        healthExcelBtn.disabled = false;
      }
    }

    function printSelectedHealth() {
      const siteId = selectedSiteId();
      let idsToPrint;
      if (siteId != null) {
        idsToPrint = new Set([siteId]);
      } else if (printSelectedIds.size) {
        idsToPrint = new Set(printSelectedIds);
      } else {
        idsToPrint = new Set(cardsCache.map((card) => card.id));
      }
      if (!idsToPrint.size) {
        window.alert("No servers to print.");
        return;
      }
      document.querySelectorAll(".server").forEach((section) => {
        const id = parseInt(section.dataset.id, 10);
        section.classList.toggle("print-selected", idsToPrint.has(id));
      });
      if (printMetaEl) {
        const names = [...idsToPrint]
          .map((id) => cardsCache.find((entry) => entry.id === id)?.name)
          .filter(Boolean);
        printMetaEl.textContent = `LaunchPad Health · ${names.join(" · ")} · ${new Date().toLocaleString()}`;
      }
      document.body.classList.add("print-export");
      const afterPrint = () => {
        document.body.classList.remove("print-export");
        syncPrintSelectionClasses();
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
      if (event.key !== "Escape") return;
      if (healthAlertModalOpen) {
        closeHealthAlertModal(true);
        return;
      }
      closeModal();
    });

    function groupHealthAlerts(alerts) {
      const groups = new Map();
      (alerts || []).forEach((alert) => {
        const cardId = alert.card_id;
        const key = String(cardId);
        if (!groups.has(key)) {
          groups.set(key, {
            card_id: cardId,
            card_name: alert.card_name || `Card ${cardId}`,
            art_url: alert.art_url || "",
            issues: [],
          });
        }
        groups.get(key).issues.push(alert);
      });
      return [...groups.values()].sort(
        (a, b) =>
          String(a.card_name).localeCompare(String(b.card_name)) ||
          Number(a.card_id) - Number(b.card_id)
      );
    }

    function renderHealthAlertIssues(issues) {
      return (issues || [])
        .map((issue) => {
          const sev = escapeHtml(issue.severity || "critical");
          const cat = escapeHtml(issue.category || "");
          const msg = escapeHtml(issue.message || "");
          return `<div class="issue ${sev}"><span>${cat ? cat + " · " : ""}${msg}</span></div>`;
        })
        .join("");
    }

    function isCardAlarmMuted(cardId) {
      const meta = healthAlertCardsMeta[String(cardId)] || {};
      return Boolean(meta.alarm_muted);
    }

    function syncHealthAlertAlarmButton() {
      if (!healthAlertAlarmBtn || !healthAlertCurrent) return;
      const muted = isCardAlarmMuted(healthAlertCurrent.card_id);
      healthAlertAlarmBtn.textContent = muted ? "Alarm on" : "Alarm off";
      healthAlertAlarmBtn.title = muted
        ? "Re-enable popups and sound for this site"
        : "Mute popups and sound for this site until Alarm on";
    }

    function updateAlarmMutedVisuals() {
      document.querySelectorAll(".server[data-id]").forEach((section) => {
        const cardId = section.dataset.id;
        const muted = isCardAlarmMuted(cardId);
        section.classList.toggle("alarm-muted", muted);
        let btn = section.querySelector(".alarm-on-btn");
        if (muted) {
          if (!btn) {
            btn = document.createElement("button");
            btn.type = "button";
            btn.className = "alarm-on-btn secondary";
            btn.dataset.id = cardId;
            btn.textContent = "Alarm on";
            btn.title = "Re-enable popups and sound for this site";
            btn.onclick = () => setCardHealthAlarm(cardId, false);
            const controls = section.querySelector(".controls");
            if (controls) controls.appendChild(btn);
          }
        } else if (btn) {
          btn.remove();
        }
      });
    }

    async function setCardHealthAlarm(cardId, muted) {
      try {
        const payload = await postHealthAlertAction("/api/health-alerts/alarm", {
          card_id: cardId,
          muted,
        });
        healthAlertCardsMeta = payload?.cards || healthAlertCardsMeta;
        updateAlarmMutedVisuals();
        syncHealthAlertAlarmButton();
        if (!healthAlertModalOpen) {
          applyHealthAlertPayload(payload);
        }
      } catch (err) {
        window.alert(err.message || err);
      }
    }

    function openHealthAlertModal(group) {
      if (!group || !group.issues?.length || !healthAlertModalEl) return;
      healthAlertCurrent = group;
      healthAlertModalOpen = true;
      if (healthAlertCardNameEl) {
        healthAlertCardNameEl.textContent = group.card_name || `Card ${group.card_id}`;
      }
      if (healthAlertIssuesEl) {
        healthAlertIssuesEl.innerHTML = renderHealthAlertIssues(group.issues);
      }
      if (healthAlertArtEl) {
        healthAlertArtEl.style.backgroundImage = group.art_url
          ? `url("${group.art_url}")`
          : "";
      }
      healthAlertModalEl.classList.add("open");
      healthAlertModalEl.setAttribute("aria-hidden", "false");
      syncHealthAlertAlarmButton();
    }

    function closeHealthAlertModal(advanceQueue) {
      if (!healthAlertModalEl) return;
      healthAlertModalOpen = false;
      healthAlertCurrent = null;
      healthAlertModalEl.classList.remove("open");
      healthAlertModalEl.setAttribute("aria-hidden", "true");
      if (healthAlertArtEl) healthAlertArtEl.style.backgroundImage = "";
      if (healthAlertIssuesEl) healthAlertIssuesEl.innerHTML = "";
      if (advanceQueue) {
        healthAlertQueueIndex += 1;
        showNextHealthAlertFromQueue();
      }
    }

    function showNextHealthAlertFromQueue() {
      while (healthAlertQueueIndex < healthAlertQueue.length) {
        const group = healthAlertQueue[healthAlertQueueIndex];
        if (group?.issues?.length) {
          openHealthAlertModal(group);
          return;
        }
        healthAlertQueueIndex += 1;
      }
    }

    function applyHealthAlertPayload(payload) {
      healthAlertCardsMeta = payload?.cards || healthAlertCardsMeta;
      updateAlarmMutedVisuals();
      healthAlertQueue = groupHealthAlerts(payload?.alerts || []);
      if (healthAlertModalOpen) return;
      healthAlertQueueIndex = 0;
      showNextHealthAlertFromQueue();
    }

    async function postHealthAlertAction(path, body) {
      const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.error || "Request failed");
      return payload;
    }

    async function pollHealthAlerts() {
      if (healthAlertPollRunning) return;
      healthAlertPollRunning = true;
      try {
        const res = await fetch("/api/health-alerts");
        const payload = await res.json();
        if (!res.ok) throw new Error(payload.error || "Alert poll failed");
        applyHealthAlertPayload(payload);
      } catch (_err) {
        /* best-effort poll */
      } finally {
        healthAlertPollRunning = false;
      }
    }

    async function acknowledgeCurrentHealthAlert() {
      if (!healthAlertCurrent?.issues?.length) return;
      const fingerprints = healthAlertCurrent.issues.map((issue) => issue.fingerprint);
      try {
        const payload = await postHealthAlertAction("/api/health-alerts/acknowledge", {
          fingerprints,
        });
        closeHealthAlertModal(false);
        applyHealthAlertPayload(payload);
      } catch (err) {
        window.alert(err.message || err);
      }
    }

    async function pauseCurrentHealthAlert(minutes) {
      if (!healthAlertCurrent) return;
      try {
        const payload = await postHealthAlertAction("/api/health-alerts/pause", {
          card_id: healthAlertCurrent.card_id,
          minutes,
        });
        closeHealthAlertModal(false);
        applyHealthAlertPayload(payload);
      } catch (err) {
        window.alert(err.message || err);
      }
    }

    async function toggleCurrentHealthAlarm() {
      if (!healthAlertCurrent) return;
      const muted = !isCardAlarmMuted(healthAlertCurrent.card_id);
      try {
        const payload = await postHealthAlertAction("/api/health-alerts/alarm", {
          card_id: healthAlertCurrent.card_id,
          muted,
        });
        healthAlertCardsMeta = payload?.cards || healthAlertCardsMeta;
        updateAlarmMutedVisuals();
        closeHealthAlertModal(false);
        applyHealthAlertPayload(payload);
      } catch (err) {
        window.alert(err.message || err);
      }
    }

    if (healthAlertCloseBtn) {
      healthAlertCloseBtn.addEventListener("click", () => closeHealthAlertModal(true));
    }
    if (healthAlertAckBtn) {
      healthAlertAckBtn.addEventListener("click", () => acknowledgeCurrentHealthAlert());
    }
    if (healthAlertAlarmBtn) {
      healthAlertAlarmBtn.addEventListener("click", () => toggleCurrentHealthAlarm());
    }
    healthAlertPauseBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const minutes = parseInt(btn.dataset.minutes, 10);
        if (minutes) pauseCurrentHealthAlert(minutes);
      });
    });
    if (healthAlertModalEl) {
      healthAlertModalEl.addEventListener("click", (event) => {
        if (event.target === healthAlertModalEl) closeHealthAlertModal(true);
      });
    }

    function escapeHtml(value) {
      return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function formatBytes(value) {
      if (!value || value <= 0) return "0 B";
      const si = CAPACITY_UNIT_MODE === "si";
      const units = si
        ? ["B", "KB", "MB", "GB", "TB", "PB"]
        : ["B", "KiB", "MiB", "GiB", "TiB", "PiB"];
      const step = si ? 1000 : 1024;
      let size = value;
      let unit = 0;
      while (size >= step && unit < units.length - 1) {
        size /= step;
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

    const issuesForDashboard = (card) =>
      Array.isArray(card.visible_health_issues)
        ? card.visible_health_issues
        : (card.health_issues || []);

    function renderIssues(cards) {
      if (!issuesListEl) return;
      const allIssues = [];
      cards.forEach((card) => {
        if (!isMonitorOn(card.id)) return;
        issuesForDashboard(card).forEach((issue) => allIssues.push(issue));
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

    function cardActiveIssuesHtml(card) {
      if (!isMonitorOn(card.id)) return "";
      const issues = issuesForDashboard(card).slice();
      const rank = { critical: 0, warn: 1 };
      issues.sort(
        (a, b) =>
          (rank[a.severity] ?? 9) - (rank[b.severity] ?? 9) ||
          String(a.category || "").localeCompare(String(b.category || "")) ||
          String(a.message || "").localeCompare(String(b.message || ""))
      );
      let body;
      if (!issues.length) {
        body = '<p class="issues-ok">No active issues.</p>';
      } else {
        body =
          '<div class="issue-list">' +
          issues
            .map((issue) => {
              const sev = escapeHtml(issue.severity || "warn");
              const cat = escapeHtml(issue.category || "");
              const msg = escapeHtml(issue.message || "");
              return `<div class="issue ${sev}"><span>${cat ? cat + " · " : ""}${msg}</span></div>`;
            })
            .join("") +
          "</div>";
      }
      return `<div class="card-active-issues"><h3>Active Issues</h3>${body}</div>`;
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
          ${cardActiveIssuesHtml(card)}
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
        pollHealthAlerts();
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
        if (all.length && ["iec", "si"].includes(all[0].capacity_unit_mode)) {
          CAPACITY_UNIT_MODE = all[0].capacity_unit_mode;
        }
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

    function visibleCards(cards) {
      if (includeOffToggle && includeOffToggle.checked) {
        return cards;
      }
      return cards.filter((card) => isMonitorOn(card.id));
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
      const visible = visibleCards(cards);
      if (!visible.length) {
        serversEl.innerHTML =
          '<div class="empty">All sites have Monitor off. Check <strong>Include monitoring-off sites</strong> to view them, or turn on Monitor.</div>';
        updateSummary(cards);
        renderIssues(cards);
        updateMasterMonitorToggle();
        if (refreshStatusEl) {
          refreshStatusEl.textContent = `0 of ${cards.length} monitored site(s) shown`;
        }
        return;
      }
      const sorted = [...visible].sort((a, b) => a.id - b.id);
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
      updateSummary(cards);
      renderIssues(cards);
      wireInteractiveButtons();
      wirePrintCheckboxes();
      populateHealthSiteSelect(sorted);
      applySiteFilter();
      applyHealthSearch();
      syncPrintSelectionClasses();
      updateSelectionCount();
      if (refreshStatusEl && !refreshAllRunning) {
        const includeOff = includeOffToggle && includeOffToggle.checked;
        refreshStatusEl.textContent = includeOff
          ? `${sorted.length} of ${cards.length} site(s) shown`
          : `${sorted.length} monitored site(s) shown (${cards.length} total)`;
      }
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

    async function loadJigglerStatus() {
      if (!jigglerStatusEl) return;
      try {
        const res = await fetch("/api/mouse-jiggler");
        if (!res.ok) return;
        const data = await res.json();
        jigglerStatusEl.textContent = data.enabled ? "Mouse jiggler: On" : "Mouse jiggler: Off";
      } catch (_err) {
        /* ignore network errors */
      }
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
        await loadJigglerStatus();
        await loadMonitorState();
        const res = await fetch("/api/cards");
        if (!res.ok) {
          throw new Error(`Health server returned ${res.status}`);
        }
        const cards = await res.json();
        cardsCache = Array.isArray(cards) ? cards : [];
        if (cardsCache.length && ["iec", "si"].includes(cardsCache[0].capacity_unit_mode)) {
          CAPACITY_UNIT_MODE = cardsCache[0].capacity_unit_mode;
        }
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
    if (includeOffToggle) {
      const savedIncludeOff = localStorage.getItem("launchpad.healthDashboard.includeOff");
      if (savedIncludeOff === "1") includeOffToggle.checked = true;
      includeOffToggle.addEventListener("change", () => {
        localStorage.setItem(
          "launchpad.healthDashboard.includeOff",
          includeOffToggle.checked ? "1" : "0"
        );
        renderAll(cardsCache);
      });
    }
    if (healthSiteSelectEl) {
      healthSiteSelectEl.addEventListener("change", applySiteFilter);
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
    if (healthExcelBtn) {
      healthExcelBtn.addEventListener("click", downloadHealthExcel);
    }
    if (healthExcelSummaryEl) {
      healthExcelSummaryEl.addEventListener("change", () => {
        saveHealthExcelPref(healthExcelSummaryEl, HEALTH_EXCEL_PREF.summary);
      });
    }
    if (healthExcelIssuesEl) {
      healthExcelIssuesEl.addEventListener("change", () => {
        saveHealthExcelPref(healthExcelIssuesEl, HEALTH_EXCEL_PREF.issues);
      });
    }
    if (healthExcelCmdSummariesEl) {
      healthExcelCmdSummariesEl.addEventListener("change", () => {
        saveHealthExcelPref(
          healthExcelCmdSummariesEl,
          HEALTH_EXCEL_PREF.commandSummaries
        );
      });
    }
    if (healthExcelRawEl) {
      healthExcelRawEl.addEventListener("change", () => {
        saveHealthExcelPref(healthExcelRawEl, HEALTH_EXCEL_PREF.rawOutput);
      });
    }
    loadHealthExcelPrefs();
    loadShowAlertsPref();

    loadJigglerStatus();
    loadCards();
    pollHealthAlerts();
    setInterval(loadCards, 15000);
    setInterval(loadJigglerStatus, 30000);
    setInterval(pollHealthAlerts, HEALTH_ALERT_POLL_MS);
  </script>
</body>
</html>"""


def _fill_page(html: str) -> str:
    return html.replace("{{APP_VERSION}}", APP_VERSION).replace(
        "{{CAPACITY_UNIT_MODE}}", get_capacity_unit_mode()
    )


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
        filename: str | None = None,
        status: int = 200,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if filename:
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
            self._send_html(_fill_page(DASHBOARD_HTML))
            return
        if path == CAPACITY_REPORT_PATH or path == "/capacity-report":
            self._send_html(_fill_page(CAPACITY_REPORT_HTML))
            return
        if path == SNAPSHOT_SCHEDULE_PATH:
            self._send_html(_fill_page(SNAPSHOT_SCHEDULE_HTML))
            return
        if path == CONTINGENCY_GROUPS_PATH:
            self._send_html(_fill_page(CONTINGENCY_GROUPS_HTML))
            return
        if path == LUN_BUILDER_PATH:
            self._send_html(_fill_page(LUN_BUILDER_HTML))
            return
        if path == VOLUME_FIND_PATH:
            self._send_html(_fill_page(VOLUME_FIND_HTML))
            return
        if path == FC_WWPN_REPORT_PATH:
            self._send_html(_fill_page(FC_WWPN_REPORT_HTML))
            return
        if path == FC_CONSISTGRP_PATH:
            self._send_html(_fill_page(FC_CONSISTGRP_HTML))
            return
        if path == ESX_SNAP_POLICY_PATH:
            self._send_html(_fill_page(ESX_SNAP_POLICY_HTML))
            return
        if path == HOST_VOLUME_HEALTH_PATH:
            self._send_html(_fill_page(HOST_VOLUME_HEALTH_HTML))
            return
        if path == SNAPCOPY_SUMMARY_PATH:
            self._send_html(_fill_page(SNAPCOPY_SUMMARY_HTML))
            return
        if path == SYSTEM_CONNECTIVITY_PATH:
            self._send_html(_fill_page(SYSTEM_CONNECTIVITY_HTML))
            return
        if path == STORAGE_INVENTORY_PATH:
            self._send_html(_fill_page(STORAGE_INVENTORY_HTML))
            return
        if path == SITE_LOOKUP_PATH:
            self._send_html(_fill_page(SITE_LOOKUP_HTML))
            return
        if path == ANSIBLE_PAD_PATH:
            self._send_html(_fill_page(ANSIBLE_PAD_HTML))
            return
        if path == HOST_POWER_PATH:
            self._send_html(_fill_page(HOST_POWER_HTML))
            return
        if path == "/api/ansible-pad/settings":
            try:
                self._send_json(server.get_ansible_pad_settings())
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return
        if path == "/api/ansible-pad/export.zip":
            try:
                body = server.export_ansible_pad_zip_bytes()
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            self._send_bytes(
                body,
                content_type="application/zip",
                filename="LaunchPad_Ansible_Pad.zip",
            )
            return
        if path == "/api/host-power/cards":
            self._send_json({"cards": server.host_power_cards()})
            return
        if path == "/api/host-power/prechecks":
            self._send_json({"prechecks": host_power_precheck_catalog_payload()})
            return
        if path == "/api/fc-consistgrp/cards":
            self._send_json({"cards": server.fc_consistgrp_cards()})
            return
        if path == "/api/esx-snap-policy/cards":
            self._send_json({"cards": server.esx_snap_policy_cards()})
            return
        if path == "/api/fc-consistgrp/status/live":
            query = parse_qs(parsed.query)
            raw_card_id = (query.get("card_id") or [""])[0].strip()
            card_id: int | None = None
            if raw_card_id:
                try:
                    card_id = int(raw_card_id)
                except ValueError:
                    self._send_json({"error": "card_id must be an integer"}, status=400)
                    return
            try:
                payload = server.scan_fc_consistgrp_status_live(card_id=card_id)
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=403)
                return
            self._send_json(payload)
            return
        if path == "/api/fc-consistgrp/status/export":
            from launchpad.capacity_export import open_exported_workbook
            from launchpad.config import TEMP_DIR

            query = parse_qs(parsed.query)
            export_format = (query.get("format") or [""])[0].strip().lower()
            if export_format != "xlsx":
                self._send_json(
                    {"error": "Export format must be xlsx."},
                    status=400,
                )
                return
            raw_card_id = (query.get("card_id") or [""])[0].strip()
            card_id = None
            if raw_card_id:
                try:
                    card_id = int(raw_card_id)
                except ValueError:
                    self._send_json({"error": "card_id must be an integer"}, status=400)
                    return
            bucket = (query.get("bucket") or ["all"])[0].strip().lower() or "all"
            open_after = (query.get("open") or ["1"])[0].strip().lower() in {
                "1",
                "true",
                "yes",
            }
            try:
                body, filename, content_type = server.export_fc_consistgrp_status_bytes(
                    format=export_format,
                    card_id=card_id,
                    bucket=bucket,
                )
            except LookupError as exc:
                self._send_json({"error": str(exc)}, status=404)
                return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            if open_after:
                try:
                    TEMP_DIR.mkdir(parents=True, exist_ok=True)
                    saved = TEMP_DIR / filename
                    saved.write_bytes(body)
                    open_exported_workbook(saved)
                    _log(f"FlashCopy CG Status export opened: {saved}")
                except Exception as open_exc:
                    _log(
                        "FlashCopy CG Status export saved for download but "
                        f"could not open: {open_exc}"
                    )
            self._send_bytes(body, content_type=content_type, filename=filename)
            return
        if path == "/api/fc-consistgrp/inventory":
            query = parse_qs(parsed.query)
            raw_card_id = (query.get("card_id") or [""])[0].strip()
            try:
                card_id = int(raw_card_id)
            except ValueError:
                self._send_json(
                    {"ok": False, "warnings": ["card_id is required"], "groups": [], "maps": [], "stand_alone": []},
                    status=400,
                )
                return
            result = server.fc_consistgrp_inventory(card_id)
            self._send_json(result, status=200 if result.get("ok") else 400)
            return
        if path == "/api/contingency-groups/fc-cg-summary/live":
            query = parse_qs(parsed.query)
            raw_card_id = (query.get("card_id") or [""])[0].strip()
            card_id: int | None = None
            if raw_card_id:
                try:
                    card_id = int(raw_card_id)
                except ValueError:
                    self._send_json({"error": "card_id must be an integer"}, status=400)
                    return
            reset = (query.get("reset") or ["0"])[0].strip().lower() in {
                "1",
                "true",
                "yes",
            }
            try:
                payload = server.scan_fc_cg_summary_live(
                    card_id=card_id, reset=reset
                )
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=403)
                return
            self._send_json(payload)
            return
        if path == "/api/contingency-groups/fc-cg-summary":
            query = parse_qs(parsed.query)
            group_id = (query.get("group_id") or [""])[0].strip()
            if not group_id:
                self._send_json(
                    {
                        "ok": False,
                        "warnings": ["group_id is required"],
                        "summaries": [],
                        "card": None,
                    },
                    status=400,
                )
                return
            result = server.contingency_fc_cg_summary(group_id)
            self._send_json(result, status=200 if result.get("ok") else 400)
            return
        if path == "/api/contingency-groups/fc-cg-summary/export":
            from launchpad.capacity_export import open_exported_workbook
            from launchpad.config import TEMP_DIR

            query = parse_qs(parsed.query)
            export_format = (query.get("format") or [""])[0].strip().lower()
            if export_format != "xlsx":
                self._send_json(
                    {"error": "Export format must be xlsx."},
                    status=400,
                )
                return
            group_id = (query.get("group_id") or [""])[0].strip()
            if not group_id:
                self._send_json({"error": "group_id is required"}, status=400)
                return
            open_after = (query.get("open") or ["1"])[0].strip().lower() in {
                "1",
                "true",
                "yes",
            }
            try:
                body, filename, content_type = server.export_fc_cg_summary_bytes(
                    group_id=group_id,
                )
            except LookupError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            if open_after:
                try:
                    TEMP_DIR.mkdir(parents=True, exist_ok=True)
                    saved = TEMP_DIR / filename
                    saved.write_bytes(body)
                    open_exported_workbook(saved)
                    _log(f"FlashCopy CG summary export opened: {saved}")
                except Exception as open_exc:
                    _log(
                        "FlashCopy CG summary export saved for download but "
                        f"could not open: {open_exc}"
                    )
            self._send_bytes(body, content_type=content_type, filename=filename)
            return
        if path == "/api/cards":
            self._send_json(server.list_cards())
            return
        if path == "/api/site-lookup/cache":
            query = parse_qs(parsed.query)
            raw_card_id = (query.get("card_id") or [""])[0].strip()
            try:
                card_id = int(raw_card_id)
            except ValueError:
                self._send_json({"error": "card_id must be an integer"}, status=400)
                return
            try:
                payload = server.site_lookup_cache(card_id)
            except KeyError:
                self._send_json({"error": f"Unknown card id {card_id}"}, status=404)
                return
            self._send_json(payload)
            return
        if path == "/api/sync":
            count = server.sync_from_app()
            cards = server.list_cards(allow_sync=False)
            self._send_json({"synced": count, "total": len(cards)})
            return
        if path == "/api/monitor":
            self._send_json({"states": server.monitor_states(), "default": False})
            return
        if path == "/api/mouse-jiggler":
            self._send_json({"enabled": server.mouse_jiggler_enabled()})
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
                    "groups": (
                        server.ensure_contingency_groups_from_cards()
                        if persisted
                        else []
                    ),
                    "persisted": persisted,
                }
            )
            return
        if path == "/api/lun-builds":
            persisted = server.lun_builds_persist_available()
            self._send_json(
                {
                    "builds": server.get_lun_builds() if persisted else [],
                    "templates": seed_lun_builder_templates(),
                    "persisted": persisted,
                }
            )
            return
        if path == "/api/lun-offline-inventory":
            query = parse_qs(parsed.query)
            raw_card_id = (query.get("card_id") or [""])[0].strip()
            if raw_card_id:
                try:
                    card_id = int(raw_card_id)
                except ValueError:
                    self._send_json({"error": "card_id must be an integer"}, status=400)
                    return
                store = server.get_lun_offline_inventory()
                snapshot = store.get(str(card_id))
                if snapshot is None:
                    self._send_json(
                        {
                            "ok": False,
                            "snapshot": None,
                            "error": "Offline inventory snapshot not found.",
                        }
                    )
                    return
                self._send_json({"ok": True, "snapshot": snapshot})
                return
            store = server.get_lun_offline_inventory()
            snapshots = [summarize_snapshot(item) for item in store.values()]
            self._send_json({"ok": True, "snapshots": snapshots})
            return
        if path == "/api/lun-builds-export":
            query = parse_qs(parsed.query)
            build_id = (query.get("id") or [""])[0].strip()
            export_format = (query.get("format") or [""])[0].strip().lower()
            if not build_id:
                self._send_json({"error": "LUN build id is required."}, status=400)
                return
            if export_format not in {"xlsx", "csv"}:
                self._send_json(
                    {"error": "Export format must be xlsx or csv."},
                    status=400,
                )
                return
            build = next(
                (
                    item
                    for item in server.get_lun_builds()
                    if str(item.get("id") or "").strip() == build_id
                ),
                None,
            )
            if build is None:
                self._send_json({"error": "LUN build not found."}, status=404)
                return
            try:
                if export_format == "xlsx":
                    body = export_lun_build_xlsx(build)
                    content_type = (
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    )
                else:
                    body = export_lun_build_csv_zip(build)
                    content_type = "application/zip"
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            safe_id = re.sub(r"[^\w\-]+", "_", build_id).strip("_") or "build"
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
            extension = "xlsx" if export_format == "xlsx" else "zip"
            self._send_bytes(
                body,
                content_type=content_type,
                filename=f"LUN_Builder_{safe_id}_{stamp}.{extension}",
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
        if path == "/api/volume-find/progress":
            self._send_json(server.volume_find_progress_snapshot())
            return
        if path == "/api/volume-find":
            query = parse_qs(parsed.query)
            q = (query.get("q") or [""])[0]
            mode = (query.get("mode") or ["cache"])[0]
            find_type = (query.get("type") or ["volume"])[0]
            try:
                payload = server.find_volumes(q, mode=mode, find_type=find_type)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=403)
                return
            self._send_json(payload)
            return
        if path == "/api/host-volume-health/progress":
            self._send_json(server.host_volume_health_progress_snapshot())
            return
        if path == "/api/host-volume-health/live":
            query = parse_qs(parsed.query)
            raw_card_id = (query.get("card_id") or [""])[0].strip()
            card_id: int | None = None
            if raw_card_id:
                try:
                    card_id = int(raw_card_id)
                except ValueError:
                    self._send_json({"error": "card_id must be an integer"}, status=400)
                    return
            try:
                payload = server.scan_host_volume_health_live(card_id=card_id)
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=403)
                return
            self._send_json(payload)
            return
        if path == "/api/host-volume-health/export":
            from launchpad.capacity_export import open_exported_workbook
            from launchpad.config import TEMP_DIR

            query = parse_qs(parsed.query)
            export_format = (query.get("format") or [""])[0].strip().lower()
            if export_format not in {"xlsx", "csv"}:
                self._send_json(
                    {"error": "Export format must be xlsx or csv."},
                    status=400,
                )
                return
            raw_card_id = (query.get("card_id") or [""])[0].strip()
            card_id: int | None = None
            if raw_card_id:
                try:
                    card_id = int(raw_card_id)
                except ValueError:
                    self._send_json({"error": "card_id must be an integer"}, status=400)
                    return
            open_after = (query.get("open") or ["1"])[0].strip().lower() in {
                "1",
                "true",
                "yes",
            }
            try:
                body, filename, content_type = server.export_host_volume_health_bytes(
                    export_format=export_format,
                    card_id=card_id,
                )
            except LookupError as exc:
                self._send_json({"error": str(exc)}, status=404)
                return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            if open_after:
                try:
                    TEMP_DIR.mkdir(parents=True, exist_ok=True)
                    saved = TEMP_DIR / filename
                    saved.write_bytes(body)
                    open_exported_workbook(saved)
                    _log(f"Hosts & Volumes Health export opened: {saved}")
                except Exception as open_exc:
                    _log(
                        "Hosts & Volumes Health export saved for download but "
                        f"could not open: {open_exc}"
                    )
            self._send_bytes(body, content_type=content_type, filename=filename)
            return
        if path == "/api/system-connectivity/live":
            query = parse_qs(parsed.query)
            raw_card_id = (query.get("card_id") or [""])[0].strip()
            card_id: int | None = None
            if raw_card_id:
                try:
                    card_id = int(raw_card_id)
                except ValueError:
                    self._send_json({"error": "card_id must be an integer"}, status=400)
                    return
            try:
                payload = server.scan_system_connectivity_live(card_id=card_id)
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=403)
                return
            self._send_json(payload)
            return
        if path == "/api/system-connectivity/export":
            from launchpad.capacity_export import open_exported_workbook
            from launchpad.config import TEMP_DIR

            query = parse_qs(parsed.query)
            export_format = (query.get("format") or [""])[0].strip().lower()
            if export_format not in {"xlsx", "csv"}:
                self._send_json(
                    {"error": "Export format must be xlsx or csv."},
                    status=400,
                )
                return
            raw_card_id = (query.get("card_id") or [""])[0].strip()
            card_id: int | None = None
            if raw_card_id:
                try:
                    card_id = int(raw_card_id)
                except ValueError:
                    self._send_json({"error": "card_id must be an integer"}, status=400)
                    return
            open_after = (query.get("open") or ["1"])[0].strip().lower() in {
                "1",
                "true",
                "yes",
            }
            try:
                body, filename, content_type = server.export_system_connectivity_bytes(
                    export_format=export_format,
                    card_id=card_id,
                )
            except LookupError as exc:
                self._send_json({"error": str(exc)}, status=404)
                return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            if open_after:
                try:
                    TEMP_DIR.mkdir(parents=True, exist_ok=True)
                    saved = TEMP_DIR / filename
                    saved.write_bytes(body)
                    open_exported_workbook(saved)
                    _log(f"System Connectivity export opened: {saved}")
                except Exception as open_exc:
                    _log(
                        "System Connectivity export saved for download but "
                        f"could not open: {open_exc}"
                    )
            self._send_bytes(body, content_type=content_type, filename=filename)
            return
        if path == "/api/storage-inventory/cache":
            cached = server.get_storage_inventory_cache()
            if cached is None:
                self._send_json(
                    {
                        "rows": [],
                        "generated_at": "",
                        "errors": [],
                        "total_devices": 0,
                        "devices_with_issues": 0,
                    }
                )
                return
            self._send_json(cached)
            return
        if path == "/api/storage-inventory/progress":
            self._send_json(server.storage_inventory_progress_snapshot())
            return
        if path == "/api/storage-inventory/live":
            query = parse_qs(parsed.query)
            raw_card_id = (query.get("card_id") or [""])[0].strip()
            card_id: int | None = None
            if raw_card_id:
                try:
                    card_id = int(raw_card_id)
                except ValueError:
                    self._send_json({"error": "card_id must be an integer"}, status=400)
                    return
            try:
                payload = server.scan_storage_inventory_live(card_id=card_id)
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=403)
                return
            self._send_json(payload)
            return
        if path == "/api/storage-inventory/export":
            # Inline: capacity_export -> monitor -> health_server is a
            # circular dependency, so this module can't import capacity_export
            # at top level. TEMP_DIR is already imported at module scope above.
            from launchpad.capacity_export import open_exported_workbook

            query = parse_qs(parsed.query)
            export_format = (query.get("format") or ["xlsx"])[0].strip().lower()
            if export_format != "xlsx":
                self._send_json(
                    {"error": "Export format must be xlsx."},
                    status=400,
                )
                return
            open_after = (query.get("open") or [""])[0].strip().lower() in {
                "1",
                "true",
                "yes",
            }
            try:
                body, filename, content_type = server.export_storage_inventory_bytes()
            except LookupError as exc:
                self._send_json({"error": str(exc)}, status=404)
                return
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            if open_after:
                try:
                    TEMP_DIR.mkdir(parents=True, exist_ok=True)
                    saved = TEMP_DIR / filename
                    saved.write_bytes(body)
                    open_exported_workbook(saved)
                    _log(f"Storage Inventory export opened: {saved}")
                except Exception as open_exc:
                    _log(
                        "Storage Inventory export saved for download but "
                        f"could not open: {open_exc}"
                    )
            self._send_bytes(body, content_type=content_type, filename=filename)
            return
        if path == "/api/fc-wwpn-find":
            from launchpad.fc_wwpn_search import find_cards_matching_fc_query
            from launchpad.storage_presets import is_svc_fc_profile

            query = parse_qs(parsed.query)
            q = (query.get("q") or [""])[0]
            if not str(q).strip():
                self._send_json({"error": "q required"}, status=400)
                return
            server.sync_from_app()
            cards = [
                card
                for card in server.list_cards(allow_sync=False)
                if is_svc_fc_profile(str(card.get("device_profile") or ""))
                or bool(card.get("fc_available"))
            ]
            matches = find_cards_matching_fc_query(cards, q)
            self._send_json(
                {
                    "query": q,
                    "matches": [
                        {"id": c.get("id"), "name": c.get("name")} for c in matches
                    ],
                }
            )
            return
        if path == "/api/fc-wwpn-export":
            from launchpad.capacity_export import open_exported_workbook
            from launchpad.config import TEMP_DIR
            from launchpad.fc_wwpn_export import (
                build_fc_wwpn_workbook,
                cards_for_fc_export,
                filter_cards_for_fc_export,
                parse_fc_export_groups,
                workbook_to_bytes,
            )
            from launchpad.storage_presets import is_svc_fc_profile

            query = parse_qs(parsed.query, keep_blank_values=True)
            open_after = (query.get("open") or ["1"])[0].strip().lower() in {
                "1",
                "true",
                "yes",
            }
            groups = parse_fc_export_groups(query)
            try:
                server.sync_from_app()
                cards = [
                    card
                    for card in server.list_cards(allow_sync=False)
                    if is_svc_fc_profile(str(card.get("device_profile") or ""))
                    or bool(card.get("fc_available"))
                ]
                cards = cards_for_fc_export(cards, groups)
                card_id = (query.get("card_id") or [""])[0].strip()
                card_name = (query.get("card_name") or [""])[0].strip()
                cards = filter_cards_for_fc_export(
                    cards, card_id=card_id or None, card_name=card_name or None
                )
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
        if path == "/api/fc-wwpn-mappings-export":
            from launchpad.capacity_export import open_exported_workbook
            from launchpad.config import TEMP_DIR
            from launchpad.fc_wwpn_export import (
                build_fc_mappings_workbook,
                export_fc_mappings_csv_zip,
                filter_cards_for_fc_export,
                workbook_to_bytes,
            )
            from launchpad.storage_presets import is_svc_fc_profile

            query = parse_qs(parsed.query)
            card_id = (query.get("card_id") or [""])[0].strip()
            if not card_id:
                self._send_json({"error": "card_id required"}, status=400)
                return
            export_format = (query.get("format") or ["xlsx"])[0].strip().lower()
            if export_format not in {"xlsx", "csv"}:
                self._send_json(
                    {"error": "format must be xlsx or csv"}, status=400
                )
                return
            open_after = (query.get("open") or ["0"])[0].strip().lower() in {
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
                cards = filter_cards_for_fc_export(cards, card_id=card_id)
                if not cards:
                    self._send_json({"error": "Unknown card_id"}, status=400)
                    return
                site_name = str(cards[0].get("name") or card_id)
                safe_name = re.sub(r"[^\w\-]+", "_", site_name).strip("_") or "site"
                stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
                if export_format == "csv":
                    body = export_fc_mappings_csv_zip(cards)
                    filename = f"FC_Mappings_{safe_name}_{stamp}.zip"
                    content_type = "application/zip"
                else:
                    wb, host_count, map_count, fabric_count = build_fc_mappings_workbook(
                        cards
                    )
                    body = workbook_to_bytes(wb)
                    filename = f"FC_Mappings_{safe_name}_{stamp}.xlsx"
                    content_type = (
                        "application/vnd.openxmlformats-officedocument"
                        ".spreadsheetml.sheet"
                    )
                    if open_after:
                        try:
                            TEMP_DIR.mkdir(parents=True, exist_ok=True)
                            saved = TEMP_DIR / filename
                            saved.write_bytes(body)
                            open_exported_workbook(saved)
                            _log(
                                f"FC mappings Excel opened: {saved} "
                                f"({host_count} hosts, {map_count} maps, "
                                f"{fabric_count} fabric)"
                            )
                        except Exception as open_exc:
                            _log(
                                "FC mappings Excel saved for download but "
                                f"could not open: {open_exc}"
                            )
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            self._send_bytes(body, content_type=content_type, filename=filename)
            return
        if path == "/api/health-export":
            from launchpad.capacity_export import open_exported_workbook
            from launchpad.config import TEMP_DIR

            query = parse_qs(parsed.query)
            card_ids: list[int] = []
            for raw_card_id in query.get("card_id") or []:
                text = str(raw_card_id).strip()
                if not text:
                    continue
                try:
                    card_ids.append(int(text))
                except ValueError:
                    self._send_json({"error": "Invalid card_id"}, status=400)
                    return
            section_keys = ("summary", "issues", "command_summaries", "raw")
            if any(key in query for key in section_keys):
                sections = parse_health_excel_sections(
                    summary=(query.get("summary") or ["1"])[0],
                    issues=(query.get("issues") or ["1"])[0],
                    command_summaries=(query.get("command_summaries") or ["1"])[0],
                    raw=(query.get("raw") or ["0"])[0],
                )
            else:
                # No section params: preserve Summary-only backward compatibility.
                sections = None
            open_after = (query.get("open") or ["0"])[0].strip().lower() in {
                "1",
                "true",
                "yes",
            }
            try:
                server.sync_from_app()
                body, filename = server.export_health_excel_bytes(
                    card_ids=card_ids or None,
                    sections=sections,
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            if open_after:
                try:
                    TEMP_DIR.mkdir(parents=True, exist_ok=True)
                    saved = TEMP_DIR / filename
                    saved.write_bytes(body)
                    open_exported_workbook(saved)
                    _log(f"Health Summary Excel opened: {saved}")
                except Exception as open_exc:
                    _log(
                        "Health Summary Excel saved for download but could not open: "
                        f"{open_exc}"
                    )
            self._send_bytes(
                body,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=filename,
            )
            return
        if path == "/api/capacity-export":
            from launchpad.capacity_export import open_exported_workbook
            from launchpad.config import TEMP_DIR

            query = parse_qs(parsed.query)
            include_off = (query.get("include_off") or ["0"])[0].strip().lower() in {
                "1",
                "true",
                "yes",
            }
            raw_card_id = (query.get("card_id") or [""])[0].strip()
            card_id: int | None = None
            if raw_card_id:
                try:
                    card_id = int(raw_card_id)
                except ValueError:
                    self._send_json({"error": "Invalid card_id"}, status=400)
                    return
            open_after = (query.get("open") or ["0"])[0].strip().lower() in {
                "1",
                "true",
                "yes",
            }
            include_pools = (query.get("include_pools") or ["1"])[0].strip().lower() not in {
                "0",
                "false",
                "no",
            }
            show_raw = (query.get("show_raw") or ["0"])[0].strip().lower() in {
                "1",
                "true",
                "yes",
            }
            try:
                server.sync_from_app()
                body, filename = server.export_capacity_excel_bytes(
                    include_monitor_off=include_off,
                    card_id=card_id,
                    include_pools=include_pools,
                    show_raw=show_raw,
                )
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            if open_after:
                try:
                    TEMP_DIR.mkdir(parents=True, exist_ok=True)
                    saved = TEMP_DIR / filename
                    saved.write_bytes(body)
                    open_exported_workbook(saved)
                    _log(f"Capacity Excel opened: {saved}")
                except Exception as open_exc:
                    _log(f"Capacity Excel saved for download but could not open: {open_exc}")
            self._send_bytes(
                body,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=filename,
            )
            return
        if path == "/api/dell-report-settings":
            from launchpad.dell_report_settings import (
                load_dell_report_settings,
                normalize_dell_report_settings,
            )

            settings_view = server._settings_view_for_scan()
            if settings_view is None:
                self._send_json(normalize_dell_report_settings({}))
            else:
                self._send_json(load_dell_report_settings(settings_view))
            return
        if path == "/api/dell-report-export":
            # Inline: capacity_export / dell_report_export pull monitor→health_server.
            from launchpad.capacity_export import open_exported_workbook
            from launchpad.dell_report_export import DellReportEmptyError
            from launchpad.dell_report_settings import is_dell_report_enabled

            settings_view = server._settings_view_for_scan()
            if settings_view is not None and not is_dell_report_enabled(settings_view):
                self._send_json(
                    {"error": "Dell Report is disabled in Admin."},
                    status=403,
                )
                return

            query = parse_qs(parsed.query)
            include_off = (query.get("include_off") or ["0"])[0].strip().lower() in {
                "1",
                "true",
                "yes",
            }
            raw_card_id = (query.get("card_id") or [""])[0].strip()
            card_id: int | None = None
            if raw_card_id:
                try:
                    card_id = int(raw_card_id)
                except ValueError:
                    self._send_json({"error": "Invalid card_id"}, status=400)
                    return
            open_after = (query.get("open") or ["0"])[0].strip().lower() in {
                "1",
                "true",
                "yes",
            }
            include_pools = (query.get("include_pools") or ["1"])[0].strip().lower() not in {
                "0",
                "false",
                "no",
            }
            try:
                server.sync_from_app()
                body, filename = server.export_dell_report_excel_bytes(
                    include_monitor_off=include_off,
                    card_id=card_id,
                    include_pools=include_pools,
                )
            except DellReportEmptyError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            if open_after:
                try:
                    TEMP_DIR.mkdir(parents=True, exist_ok=True)
                    saved = TEMP_DIR / filename
                    saved.write_bytes(body)
                    open_exported_workbook(saved)
                    _log(f"Dell Report Excel opened: {saved}")
                except Exception as open_exc:
                    _log(
                        "Dell Report Excel saved for download but could not open: "
                        f"{open_exc}"
                    )
            self._send_bytes(
                body,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=filename,
            )
            return
        if path == "/api/health-alerts":
            try:
                self._send_json(server.get_health_alerts())
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return
        if path == "/api/health-alerts/art":
            query = parse_qs(parsed.query)
            raw_card_id = (query.get("card_id") or [""])[0].strip()
            try:
                card_id = int(raw_card_id)
            except ValueError:
                self._send_json({"error": "card_id must be an integer"}, status=400)
                return
            art_path = server.health_alert_art_path(card_id)
            if art_path is None:
                self.send_error(404)
                return
            try:
                body = art_path.read_bytes()
            except OSError:
                self.send_error(404)
                return
            self._send_bytes(
                body,
                content_type="image/png",
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
        if path == "/api/ansible-pad/settings":
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
                self._send_json(server.set_ansible_pad_settings(payload))
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=503)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
            return
        if path in {
            "/api/ansible-pad/sync-run",
            "/api/ansible-pad/run-existing",
        }:
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
                if path == "/api/ansible-pad/sync-run":
                    result = server.ansible_pad_sync_run(
                        playbook=str(payload.get("playbook") or ""),
                        check=payload.get("check") is True,
                        confirm=payload.get("confirm") is True,
                        extra_vars=payload.get("extra_vars") or {},
                    )
                else:
                    result = server.ansible_pad_run_existing(
                        playbook=str(payload.get("playbook") or ""),
                        check=payload.get("check") is True,
                        confirm=payload.get("confirm") is True,
                        extra_vars=payload.get("extra_vars") or {},
                    )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=502)
                return
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=502)
                return
            self._send_json(result)
            return
        if path in {"/api/host-power/preview", "/api/host-power/run"}:
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
            card_ids = payload.get("card_ids") or []
            if not isinstance(card_ids, list):
                self._send_json({"error": "card_ids must be a list"}, status=400)
                return
            try:
                if path == "/api/host-power/preview":
                    result = server.host_power_preview(card_ids)
                else:
                    mode = normalize_host_power_mode(payload.get("mode"))
                    result = server.host_power_run(
                        card_ids,
                        confirm=payload.get("confirm") is True,
                        mode=mode,
                    )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except (RuntimeError, OSError) as exc:
                self._send_json({"error": str(exc)}, status=502)
                return
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=502)
                return
            self._send_json(result)
            return
        if path == "/api/host-power/precheck":
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
            card_ids = payload.get("card_ids") or []
            if not isinstance(card_ids, list):
                self._send_json({"error": "card_ids must be a list"}, status=400)
                return
            letter = payload.get("letter")
            try:
                result = server.host_power_precheck(card_ids, letter=letter)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except (RuntimeError, OSError) as exc:
                self._send_json({"error": str(exc)}, status=502)
                return
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=502)
                return
            self._send_json(result)
            return
        if path == "/api/site-lookup/export":
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body_payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, status=400)
                return
            if not isinstance(body_payload, dict):
                self._send_json({"error": "JSON object required"}, status=400)
                return
            export_format = body_payload.get("format")
            include_offline = bool(body_payload.get("include_offline"))
            payload = body_payload.get("payload")
            if not isinstance(payload, dict):
                self._send_json({"error": "payload is required."}, status=400)
                return
            try:
                body, filename, content_type = server.export_site_lookup_bytes(
                    export_format=str(export_format or ""),
                    include_offline=include_offline,
                    payload=payload,
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            self._send_bytes(body, content_type=content_type, filename=filename)
            return
        if path == "/api/site-lookup/refresh":
            length = int(self.headers.get("Content-Length", "0") or "0")
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
                card_id = int(payload.get("card_id"))
            except (TypeError, ValueError):
                self._send_json({"error": "card_id required"}, status=400)
                return
            try:
                result = server.refresh_site_lookup(card_id)
            except KeyError:
                self._send_json({"error": f"Unknown card id {card_id}"}, status=404)
                return
            except (RuntimeError, OSError) as exc:
                self._send_json({"error": str(exc)}, status=502)
                return
            self._send_json(result)
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
        if path == "/api/health-alerts/acknowledge":
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
                if "fingerprints" in payload:
                    fingerprints = payload.get("fingerprints")
                    if not isinstance(fingerprints, list):
                        self._send_json({"error": "fingerprints must be a list"}, status=400)
                        return
                    result = server.acknowledge_health_alerts(
                        [str(item) for item in fingerprints]
                    )
                elif "fingerprint" in payload:
                    result = server.acknowledge_health_alert(str(payload["fingerprint"]))
                else:
                    self._send_json({"error": "fingerprint or fingerprints required"}, status=400)
                    return
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=503)
                return
            self._send_json(result)
            return
        if path == "/api/health-alerts/pause":
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
                card_id = int(payload.get("card_id"))
                minutes = int(payload.get("minutes"))
            except (TypeError, ValueError):
                self._send_json({"error": "card_id and minutes required"}, status=400)
                return
            try:
                result = server.pause_health_alert(card_id, minutes)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=503)
                return
            self._send_json(result)
            return
        if path == "/api/health-alerts/alarm":
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
            if "muted" not in payload:
                self._send_json({"error": "muted required"}, status=400)
                return
            try:
                card_id = int(payload.get("card_id"))
            except (TypeError, ValueError):
                self._send_json({"error": "card_id required"}, status=400)
                return
            try:
                result = server.set_health_alarm(card_id, bool(payload.get("muted")))
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=503)
                return
            self._send_json(result)
            return
        if path == "/api/dell-report-settings":
            from launchpad.dell_report_settings import set_dell_report_include_card

            settings_view = server._settings_view_for_scan()
            if settings_view is None:
                self._send_json(
                    {"error": "Settings backend unavailable"}, status=503
                )
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, status=400)
                return
            try:
                card_id = int(payload.get("card_id"))
            except (TypeError, ValueError):
                self._send_json({"error": "card_id required"}, status=400)
                return
            if "include" not in payload:
                self._send_json({"error": "include required"}, status=400)
                return
            saved = set_dell_report_include_card(
                settings_view, card_id, enabled=bool(payload.get("include"))
            )
            self._send_json(saved)
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
        if path == "/api/lun-builds":
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
                if "builds" in payload:
                    if not isinstance(payload["builds"], list):
                        raise ValueError("builds must be a list")
                    builds = server.set_lun_builds(payload["builds"])
                elif "build" in payload:
                    if not isinstance(payload["build"], dict):
                        raise ValueError("build must be an object")
                    builds = server.upsert_lun_build(payload["build"])
                elif "delete_id" in payload:
                    builds = server.delete_lun_build(str(payload["delete_id"]))
                else:
                    raise ValueError("builds, build, or delete_id required")
            except RuntimeError as exc:
                self._send_json({"error": str(exc), "persisted": False}, status=503)
                return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json({"builds": builds, "persisted": True})
            return
        if path in {
            "/api/lun-builds/import",
            "/api/lun-builds/pull-fc",
            "/api/lun-builds/sync-inventory",
        }:
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
            build_id = str(payload.get("build_id") or "").strip()
            if not build_id:
                self._send_json({"error": "build_id required"}, status=400)
                return
            try:
                if path == "/api/lun-builds/import":
                    filename = str(payload.get("filename") or "").strip()
                    content_base64 = payload.get("content_base64")
                    if not filename or not isinstance(content_base64, str):
                        raise ValueError("filename and content_base64 required")
                    try:
                        content = base64.b64decode(content_base64, validate=True)
                    except (binascii.Error, ValueError) as exc:
                        raise ValueError("content_base64 is invalid") from exc
                    result = server.import_lun_build_upload(
                        filename,
                        content,
                        mode=str(payload.get("mode") or "merge"),
                        build_id=build_id,
                    )
                elif path == "/api/lun-builds/pull-fc":
                    card_name = str(payload.get("card_name") or "").strip() or None
                    result = server.pull_fc_hosts(build_id, card_name=card_name)
                else:
                    card_name = str(payload.get("card_name") or "").strip()
                    if not card_name:
                        raise ValueError("card_name required")
                    result = server.sync_inventory(build_id, card_name=card_name)
            except RuntimeError as exc:
                self._send_json({"error": str(exc), "persisted": False}, status=503)
                return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json({**result, "persisted": True})
            return
        if path in {"/api/lun-builds/preview", "/api/lun-builds/create"}:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json({"ok": False, "error": "Invalid JSON"}, status=400)
                return
            if not isinstance(payload, dict) or not payload.get("build_id"):
                self._send_json(
                    {"ok": False, "error": "build_id required"},
                    status=400,
                )
                return
            try:
                if path == "/api/lun-builds/preview":
                    result = server.preview_lun_build(str(payload["build_id"]))
                else:
                    result = server.create_lun_build(
                        str(payload["build_id"]),
                        confirm=payload.get("confirm") is True,
                    )
            except RuntimeError as exc:
                self._send_json(
                    {"ok": False, "error": str(exc), "warnings": [], "log": []},
                    status=503,
                )
                return
            self._send_json(result, status=200 if result.get("ok") else 400)
            return
        if path == "/api/contingency-groups/sync-inventory":
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
            group_id = str(payload.get("group_id") or "").strip()
            if not group_id:
                self._send_json({"error": "group_id required"}, status=400)
                return
            card_name = str(payload.get("card_name") or "").strip()
            try:
                result = server.sync_contingency_inventory(
                    group_id, card_name=card_name
                )
            except RuntimeError as exc:
                self._send_json(
                    {"error": str(exc), "persisted": False}, status=503
                )
                return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json({**result, "persisted": True})
            return
        if path in {
            "/api/contingency-groups/generate-snaps",
            "/api/contingency-groups/snap-preview",
            "/api/contingency-groups/snap-create",
        }:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json({"ok": False, "error": "Invalid JSON"}, status=400)
                return
            if not isinstance(payload, dict) or not payload.get("group_id"):
                self._send_json(
                    {"ok": False, "error": "group_id required"},
                    status=400,
                )
                return
            group_id = str(payload["group_id"])
            assign_cg_enabled = (
                bool(payload.get("snap_assign_cg_enabled"))
                if "snap_assign_cg_enabled" in payload
                else None
            )
            assign_cg_name = (
                str(payload.get("snap_assign_cg_name") or "")
                if "snap_assign_cg_name" in payload
                else None
            )
            try:
                if path == "/api/contingency-groups/generate-snaps":
                    result = server.generate_contingency_snaps(group_id)
                elif path == "/api/contingency-groups/snap-preview":
                    result = server.preview_contingency_snaps(
                        group_id,
                        assign_cg_enabled=assign_cg_enabled,
                        assign_cg_name=assign_cg_name,
                    )
                else:
                    result = server.create_contingency_snaps(
                        group_id,
                        confirm=payload.get("confirm") is True,
                        assign_cg_enabled=assign_cg_enabled,
                        assign_cg_name=assign_cg_name,
                    )
            except RuntimeError as exc:
                self._send_json(
                    {"ok": False, "error": str(exc), "warnings": [], "log": []},
                    status=503,
                )
                return
            self._send_json(result, status=200 if result.get("ok") else 400)
            return
        if path in {"/api/fc-consistgrp/connect", "/api/fc-consistgrp/open-gui"}:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json({"ok": False, "error": "Invalid JSON"}, status=400)
                return
            if not isinstance(payload, dict):
                self._send_json({"ok": False, "error": "JSON object required"}, status=400)
                return
            try:
                card_id = int(payload.get("card_id"))
            except (TypeError, ValueError):
                self._send_json({"ok": False, "error": "card_id is required"}, status=400)
                return
            try:
                if path == "/api/fc-consistgrp/connect":
                    message = server.connect_card_by_id(card_id)
                else:
                    message = server.open_card_gui(card_id)
            except RuntimeError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=403)
                return
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            self._send_json({"ok": True, "message": message})
            return
        if path in {"/api/fc-consistgrp/preview", "/api/fc-consistgrp/run"}:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json({"ok": False, "error": "Invalid JSON"}, status=400)
                return
            if not isinstance(payload, dict):
                self._send_json({"ok": False, "error": "JSON object required"}, status=400)
                return
            action = str(payload.get("action") or "")
            try:
                card_id = int(payload.get("card_id"))
            except (TypeError, ValueError):
                self._send_json(
                    {"ok": False, "warnings": ["card_id is required"], "steps": []},
                    status=400,
                )
                return
            if path == "/api/fc-consistgrp/preview":
                result = server.preview_fc_consistgrp(card_id, action, payload)
            else:
                result = server.run_fc_consistgrp(
                    card_id, action, payload, confirm=payload.get("confirm") is True
                )
            self._send_json(result, status=200 if result.get("ok") else 400)
            return
        if path in {
            "/api/esx-snap-policy/volumes",
            "/api/esx-snap-policy/preview",
            "/api/esx-snap-policy/run",
        }:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json({"ok": False, "error": "Invalid JSON"}, status=400)
                return
            if not isinstance(payload, dict):
                self._send_json({"ok": False, "error": "JSON object required"}, status=400)
                return
            if path == "/api/esx-snap-policy/volumes":
                try:
                    card_id = int(payload.get("card_id"))
                except (TypeError, ValueError):
                    self._send_json(
                        {"ok": False, "error": "card_id is required"},
                        status=400,
                    )
                    return
                result = server.esx_snap_policy_volumes(card_id)
                self._send_json(result, status=200 if result.get("ok") else 400)
                return
            if path == "/api/esx-snap-policy/preview":
                result = server.preview_esx_snap_policy(payload)
                self._send_json(result, status=200 if result.get("ok") else 400)
                return
            result = server.run_esx_snap_policy(
                payload, confirm=payload.get("confirm") is True
            )
            self._send_json(result, status=200 if result.get("ok") else 400)
            return
        if path == "/api/volume-find/card-host":
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
                card_id = int(payload.get("card_id"))
            except (TypeError, ValueError):
                self._send_json({"error": "card_id required"}, status=400)
                return
            if "host" not in payload:
                self._send_json({"error": "host required"}, status=400)
                return
            try:
                try:
                    server.ensure_anderson_card_rename()
                except Exception:
                    pass
                result = server.update_volume_find_card_host(card_id, str(payload.get("host")))
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=403)
                return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json({"ok": True, **result})
            return
        if path == "/api/contingency-groups/fc-cg-summary/export-selected":
            from launchpad.capacity_export import open_exported_workbook
            from launchpad.config import TEMP_DIR

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
            selected = payload.get("selected")
            if not isinstance(selected, list):
                self._send_json({"error": "selected must be a list"}, status=400)
                return
            open_after = bool(payload.get("open"))
            try:
                body, filename, content_type = server.export_fc_cg_summary_selected_bytes(
                    selected=[str(item) for item in selected],
                    open_after=open_after,
                )
            except LookupError as exc:
                self._send_json({"error": str(exc)}, status=404)
                return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            if open_after:
                try:
                    TEMP_DIR.mkdir(parents=True, exist_ok=True)
                    saved = TEMP_DIR / filename
                    saved.write_bytes(body)
                    open_exported_workbook(saved)
                    _log(f"FlashCopy CG multi-site summary export opened: {saved}")
                except Exception as open_exc:
                    _log(
                        "FlashCopy CG multi-site summary export saved for download but "
                        f"could not open: {open_exc}"
                    )
            self._send_bytes(body, content_type=content_type, filename=filename)
            return
        if not path.startswith("/api/refresh/"):
            self.send_error(404)
            return
        parsed = urlparse(self.path)
        suffix = parsed.path.removeprefix("/api/refresh/")
        query = parse_qs(parsed.query)
        focus = (query.get("focus") or [""])[0].strip().lower()
        include_pools = (query.get("include_pools") or ["1"])[0].strip().lower() not in {
            "0",
            "false",
            "no",
        }
        try:
            card_id = int(suffix)
        except ValueError:
            self.send_error(400)
            return
        try:
            card = server.refresh_card(
                card_id,
                focus=focus,
                include_pools=include_pools,
            )
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

_LUN_PREVIEW_HASH_OMIT = frozenset(
    {
        "updated_at",
        "notes",
        "plan_done",
        "command_done",
        "name",
        "location",
    }
)


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
        self._crypto_key: bytes | None = None
        self._ansible_pad_connect: Callable[[dict], Any] = (
            self._default_ansible_pad_connect
        )
        self._ansible_pad_sftp: Callable[[Any], Any] = (
            self._default_ansible_pad_sftp
        )
        self._ansible_pad_execute: Callable[[Any, str], Any] = (
            self._default_ansible_pad_execute
        )
        self._card_patcher: Callable[..., dict] | None = None
        self._connect_card_fn: Callable[[int], str] | None = None
        self._open_gui_fn: Callable[[int], str] | None = None
        self._monitor_enabled: dict[int, bool] = {}
        self._lun_preview_session: dict[str, Any] | None = None
        self._host_volume_health_cache: dict[str, Any] | None = None
        self._system_connectivity_cache: dict[str, Any] | None = None
        self._storage_inventory_cache: dict[str, Any] | None = None
        self._storage_inventory_progress = StorageInventoryProgress()
        self._host_volume_health_progress = StorageInventoryProgress()
        self._volume_find_progress = StorageInventoryProgress()
        self._fc_consistgrp_status_cache: dict[str, Any] | None = None
        self._fc_cg_summary_live_cache: dict[str, Any] | None = None

    def set_sync_provider(self, provider: Callable[[], int] | None) -> None:
        with self._lock:
            self._sync_provider = provider

    def set_settings_backend(
        self,
        get_setting: Callable[[str, str], str] | None,
        set_setting: Callable[[str, str], None] | None,
        *,
        crypto_key: bytes | None = None,
    ) -> None:
        with self._lock:
            self._get_setting = get_setting
            self._set_setting = set_setting
            self._crypto_key = crypto_key

    @staticmethod
    def _default_ansible_pad_connect(settings: dict) -> Any:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=settings["host"],
            username=settings["user"] or None,
            key_filename=settings["key_path"] or None,
            passphrase=settings["key_passphrase"] or None,
            password=settings["password"] or None,
            timeout=30,
        )
        return client

    @staticmethod
    def _default_ansible_pad_sftp(client: Any) -> Any:
        return client.open_sftp()

    @staticmethod
    def _default_ansible_pad_execute(client: Any, command: str) -> dict:
        _stdin, stdout, stderr = client.exec_command(command)
        return {
            "returncode": stdout.channel.recv_exit_status(),
            "stdout": stdout.read().decode("utf-8", errors="replace"),
            "stderr": stderr.read().decode("utf-8", errors="replace"),
        }

    def set_ansible_pad_remote_backend(
        self,
        *,
        connect: Callable[[dict], Any] | None = None,
        sftp: Callable[[Any], Any] | None = None,
        execute: Callable[[Any, str], Any] | None = None,
    ) -> None:
        """Set injectable Ansible Pad remote operations; None restores defaults."""
        with self._lock:
            self._ansible_pad_connect = connect or self._default_ansible_pad_connect
            self._ansible_pad_sftp = sftp or self._default_ansible_pad_sftp
            self._ansible_pad_execute = execute or self._default_ansible_pad_execute

    def _ansible_pad_settings_raw(self) -> dict:
        with self._lock:
            getter = self._get_setting
            crypto_key = self._crypto_key
        if not getter:
            return normalize_ansible_pad_settings({})
        settings = normalize_ansible_pad_settings(
            {
                setting: getter(setting, "")
                for setting in _ANSIBLE_PAD_SETTING_FIELDS
            }
        )
        for setting, field in _ANSIBLE_PAD_SECRET_SETTINGS.items():
            encrypted = getter(setting, "")
            if encrypted:
                if crypto_key is None:
                    raise RuntimeError(
                        "LaunchPad must be unlocked to read Ansible Pad credentials."
                    )
                settings[field] = decrypt_text(crypto_key, encrypted)
        return settings

    @staticmethod
    def _ansible_pad_public_settings(settings: dict) -> dict:
        public = dict(settings)
        for field in ("password", "key_passphrase"):
            if public.get(field):
                public[field] = "***"
            else:
                public.pop(field, None)
        return public

    def get_ansible_pad_settings(self) -> dict:
        """Return normalized Ansible Pad settings without exposing secrets."""
        return self._ansible_pad_public_settings(self._ansible_pad_settings_raw())

    def set_ansible_pad_settings(self, settings: dict) -> dict:
        """Normalize and persist Ansible Pad settings using the configured backend."""
        if not isinstance(settings, dict):
            raise ValueError("settings must be an object")
        with self._lock:
            setter = self._set_setting
            crypto_key = self._crypto_key
        if not setter:
            raise RuntimeError("LaunchPad must be unlocked to save Ansible Pad settings.")

        merged = self._ansible_pad_settings_raw()
        fields = (
            tuple(_ANSIBLE_PAD_SETTING_FIELDS.values())
            + tuple(_ANSIBLE_PAD_SECRET_SETTINGS.values())
        )
        for field in fields:
            if field not in settings:
                continue
            value = settings[field]
            if field in {"password", "key_passphrase"} and value == "***":
                continue
            merged[field] = value
        cleaned = normalize_ansible_pad_settings(merged)
        if crypto_key is None and any(
            cleaned[field] for field in _ANSIBLE_PAD_SECRET_SETTINGS.values()
        ):
            raise RuntimeError("LaunchPad must be unlocked to save Ansible Pad credentials.")
        for setting, field in _ANSIBLE_PAD_SETTING_FIELDS.items():
            setter(setting, cleaned[field])
        for setting, field in _ANSIBLE_PAD_SECRET_SETTINGS.items():
            setter(setting, encrypt_text(crypto_key, cleaned[field]) if crypto_key else "")
        return self._ansible_pad_public_settings(cleaned)

    def _ansible_pad_export_cards(self) -> list[dict]:
        with self._lock:
            cards = list(self._cards.values())
        return [
            {
                "id": card.card_id,
                "name": card.name,
                "host": card.host,
                "username": card.username,
                "device_profile": card.device_profile,
            }
            for card in cards
        ]

    def export_ansible_pad_zip_bytes(self) -> bytes:
        settings = self._ansible_pad_settings_raw()
        return build_ansible_pad_zip_bytes(
            cards=self._ansible_pad_export_cards(),
            contingency_groups=self.get_contingency_groups(),
            control_host=settings["host"],
        )

    @staticmethod
    def _ansible_pad_relative_playbook(playbook: str) -> str:
        clean = str(playbook or "").replace("\\", "/").strip().lstrip("/")
        if not clean or ".." in clean.split("/"):
            raise ValueError("playbook must be a package-relative path")
        return clean

    def _ansible_pad_run_remote(
        self,
        *,
        settings: dict,
        argv: list[str],
        cwd: str | None,
        files: dict[str, str] | None = None,
    ) -> dict:
        with self._lock:
            connect = self._ansible_pad_connect
            sftp_factory = self._ansible_pad_sftp
            execute = self._ansible_pad_execute
        client = connect(settings)
        sftp = None
        try:
            if files is not None:
                sftp = sftp_factory(client)
                sync_files_via_sftp(sftp, settings["remote_dir"], files)
            return run_remote_argv(
                lambda command: execute(client, command),
                argv,
                cwd=cwd,
            )
        finally:
            if sftp is not None and hasattr(sftp, "close"):
                sftp.close()
            if hasattr(client, "close"):
                client.close()

    @staticmethod
    def _ansible_pad_generated_extra_vars(extra_vars: dict) -> dict:
        """Validate raw-task inputs and normalize explicit inventory targets."""
        if not isinstance(extra_vars, dict):
            raise ValueError("extra_vars must be an object")

        normalized: dict[str, Any] = {}
        for name, value in extra_vars.items():
            if name == "target_hosts":
                values = value.split(",") if isinstance(value, str) else value
                if not isinstance(values, list) or not values:
                    raise ValueError("target_hosts must name at least one inventory host")
                normalized[name] = [cli_token(str(host)) for host in values if str(host).strip()]
                if not normalized[name]:
                    raise ValueError("target_hosts must name at least one inventory host")
            elif name in {"cg_name", "source_volume", "snap_volume", "fc_map_name"}:
                normalized[name] = cli_token(str(value))
            elif name == "perform_changes" and isinstance(value, bool):
                normalized[name] = value
            else:
                raise ValueError(f"Unsupported Ansible Pad extra var: {name}")
        if not normalized.get("target_hosts"):
            raise ValueError("target_hosts must name at least one inventory host")
        return normalized

    def ansible_pad_sync_run(
        self,
        *,
        playbook: str,
        check: bool,
        confirm: bool,
        extra_vars: dict,
    ) -> dict:
        """Upload generated files, then run a generated playbook remotely."""
        require_confirm_for_mutate(check=check, confirm=confirm)
        extra_vars = self._ansible_pad_generated_extra_vars(extra_vars)
        settings = self._ansible_pad_settings_raw()
        remote_dir = settings["remote_dir"].rstrip("/")
        if not remote_dir:
            raise ValueError("remote_dir is required")
        relative_playbook = self._ansible_pad_relative_playbook(playbook)
        files = build_ansible_pad_files(
            cards=self._ansible_pad_export_cards(),
            contingency_groups=self.get_contingency_groups(),
            control_host=settings["host"],
        )
        if relative_playbook not in files:
            raise ValueError("playbook is not part of the generated package")
        argv = build_ansible_playbook_argv(
            playbook=f"{remote_dir}/{relative_playbook}",
            inventory=f"{remote_dir}/inventory/hosts.yml",
            check=check,
        )
        if extra_vars:
            argv.extend(["--extra-vars", json.dumps(extra_vars)])
        return self._ansible_pad_run_remote(
            settings=settings, argv=argv, cwd=remote_dir, files=files
        )

    def ansible_pad_run_existing(
        self, *, playbook: str, check: bool, confirm: bool, extra_vars: dict
    ) -> dict:
        """Run an existing playbook path on the configured control host."""
        require_confirm_for_mutate(check=check, confirm=confirm)
        if not isinstance(extra_vars, dict):
            raise ValueError("extra_vars must be an object")
        remote_playbook = str(playbook or "").strip()
        if not remote_playbook:
            raise ValueError("playbook is required")
        settings = self._ansible_pad_settings_raw()
        argv = build_ansible_playbook_argv(
            playbook=remote_playbook, inventory=None, check=check
        )
        if extra_vars:
            argv.extend(["--extra-vars", json.dumps(extra_vars)])
        return self._ansible_pad_run_remote(
            settings=settings, argv=argv, cwd=None
        )

    def set_card_patcher(self, patcher: Callable[..., dict] | None) -> None:
        with self._lock:
            self._card_patcher = patcher

    def set_card_launch_backend(
        self,
        connect_fn: Callable[[int], str] | None,
        open_gui_fn: Callable[[int], str] | None,
    ) -> None:
        with self._lock:
            self._connect_card_fn = connect_fn
            self._open_gui_fn = open_gui_fn

    def connect_card_by_id(self, card_id: int) -> str:
        if not self.is_unlocked():
            raise RuntimeError("LaunchPad must be unlocked to connect.")
        with self._lock:
            connect_fn = self._connect_card_fn
        if connect_fn is None:
            raise RuntimeError("LaunchPad must be unlocked to connect.")
        return connect_fn(card_id)

    def open_card_gui(self, card_id: int) -> str:
        if not self.is_unlocked():
            raise RuntimeError("LaunchPad must be unlocked to open GUI.")
        with self._lock:
            open_gui_fn = self._open_gui_fn
        if open_gui_fn is None:
            raise RuntimeError("LaunchPad must be unlocked to open GUI.")
        return open_gui_fn(card_id)

    def is_unlocked(self) -> bool:
        with self._lock:
            return self._get_setting is not None

    def snapshot_schedule_persist_available(self) -> bool:
        with self._lock:
            return self._get_setting is not None

    def contingency_groups_persist_available(self) -> bool:
        with self._lock:
            return self._get_setting is not None

    def lun_builds_persist_available(self) -> bool:
        with self._lock:
            return self._get_setting is not None

    def get_lun_builds(self) -> list[dict]:
        with self._lock:
            getter = self._get_setting
        if not getter:
            return []
        raw = getter(LUN_BUILDS_SETTING, "[]") or "[]"
        try:
            return normalize_builds(json.loads(raw))
        except json.JSONDecodeError:
            return []

    def set_lun_builds(self, builds: list[dict]) -> list[dict]:
        with self._lock:
            setter = self._set_setting
        if not setter:
            raise RuntimeError("LaunchPad must be unlocked to save LUN builds.")
        cleaned = [
            build
            for build in normalize_builds(builds)
            if not str(build.get("id") or "").strip().startswith("template-")
            and not build.get("is_template")
        ]
        setter(LUN_BUILDS_SETTING, json.dumps(cleaned))
        return cleaned

    def get_lun_offline_inventory(self) -> dict[str, dict]:
        with self._lock:
            getter = self._get_setting
        if not getter:
            return {}
        raw = getter(LUN_OFFLINE_INVENTORY_SETTING, "{}") or "{}"
        try:
            return normalize_store(json.loads(raw))
        except json.JSONDecodeError:
            return {}

    def set_lun_offline_inventory(self, store: dict[str, dict]) -> dict[str, dict]:
        with self._lock:
            setter = self._set_setting
        if not setter:
            raise RuntimeError(
                "LaunchPad must be unlocked to save LUN offline inventory."
            )
        cleaned = normalize_store(store)
        setter(LUN_OFFLINE_INVENTORY_SETTING, json.dumps(cleaned))
        return cleaned

    def get_site_lookup_offline_inventory(self) -> dict[str, dict]:
        with self._lock:
            getter = self._get_setting
        if not getter:
            return {}
        raw = getter(SITE_LOOKUP_OFFLINE_SETTING, "{}") or "{}"
        try:
            return normalize_site_lookup_offline_store(json.loads(raw))
        except json.JSONDecodeError:
            return {}

    def set_site_lookup_offline_inventory(self, store: dict[str, dict]) -> dict[str, dict]:
        with self._lock:
            setter = self._set_setting
        if not setter:
            raise RuntimeError(
                "LaunchPad must be unlocked to save Site Lookup offline inventory."
            )
        cleaned = normalize_site_lookup_offline_store(store)
        setter(SITE_LOOKUP_OFFLINE_SETTING, json.dumps(cleaned))
        return cleaned

    def _persist_site_lookup_offline(self, payload: dict) -> None:
        with self._lock:
            if self._set_setting is None:
                return
        snap = snapshot_from_live_payload(payload)
        if snap is None:
            return
        try:
            store = self.get_site_lookup_offline_inventory()
            store = upsert_site_lookup_offline_snapshot(store, snap)
            self.set_site_lookup_offline_inventory(store)
        except Exception as exc:
            _log(f"Site Lookup offline persist skipped: {exc}")

    def upsert_lun_offline_inventory_from_card(
        self,
        card: HealthCard,
        *,
        monitor_on: bool | None = None,
        success: bool | None = None,
    ) -> None:
        if monitor_on is None:
            monitor_on = self.is_monitor_enabled(card.card_id)
        if not is_lun_offline_inventory_eligible(card, monitor_on=monitor_on):
            return
        with self._lock:
            if self._set_setting is None:
                return
        if success is None:
            results = card.command_results
            success = (
                isinstance(results, list)
                and bool(results)
                and any(
                    isinstance(item, dict) and not item.get("error")
                    for item in results
                )
            )
        store = self.get_lun_offline_inventory()
        if success:
            snapshot = snapshot_from_command_results(
                card_id=card.card_id,
                site_name=card.name,
                host=card.host,
                device_profile=card.device_profile,
                command_results=card.command_results,
                updated_at=card.updated_at,
            )
            store = upsert_snapshot(store, snapshot)
        else:
            error = str(card.error or "").strip() or "Monitor refresh failed"
            store = record_snapshot_error(
                store,
                card_id=card.card_id,
                error=error,
                site_name=card.name,
                host=card.host,
                device_profile=card.device_profile,
            )
        self.set_lun_offline_inventory(store)

    def upsert_lun_build(self, build: dict) -> list[dict]:
        cleaned = normalize_build(build)
        if cleaned is None:
            raise ValueError("Invalid LUN build")
        if str(cleaned["id"]).startswith("template-") or cleaned["is_template"]:
            raise ValueError(
                "Cannot overwrite a built-in template; use Save as new."
            )
        return self.set_lun_builds(upsert_build(self.get_lun_builds(), cleaned))

    def delete_lun_build(self, build_id: str) -> list[dict]:
        if str(build_id or "").strip().startswith("template-"):
            raise ValueError("Cannot delete a built-in template.")
        return self.set_lun_builds(
            delete_build(self.get_lun_builds(), build_id)
        )

    def _find_lun_build(self, build_id: str) -> dict:
        target = str(build_id or "").strip()
        build = next(
            (
                item
                for item in self.get_lun_builds()
                if str(item.get("id") or "").strip() == target
            ),
            None,
        )
        if build is None:
            raise ValueError("LUN build not found.")
        return build

    def import_lun_build_upload(
        self,
        filename: str,
        content: bytes,
        *,
        mode: str,
        build_id: str,
    ) -> dict:
        import_mode = str(mode or "").strip().lower()
        if import_mode not in {"merge", "replace"}:
            raise ValueError("mode must be merge or replace")
        build = self._find_lun_build(build_id)
        parsed = parse_lun_builder_upload(filename, content)
        if import_mode == "replace":
            build["hosts"] = parsed["hosts"]
            build["luns"] = parsed["luns"]
        else:
            build["hosts"] = merge_hosts(build.get("hosts") or [], parsed["hosts"])
            build["luns"] = list(build.get("luns") or []) + parsed["luns"]
        builds = self.upsert_lun_build(build)
        saved = next(item for item in builds if item["id"] == build["id"])
        return {
            "build": saved,
            "builds": builds,
            "warnings": parsed["warnings"],
        }

    def pull_fc_hosts(self, build_id: str, *, card_name: str | None = None) -> dict:
        build = self._find_lun_build(build_id)
        self.sync_from_app()
        cards = self.list_cards(allow_sync=False)
        incoming, warnings = map_fc_hosts(
            cards,
            card_name=card_name,
            include_warnings=True,
        )
        build["hosts"] = merge_hosts(build.get("hosts") or [], incoming)
        builds = self.upsert_lun_build(build)
        saved = next(item for item in builds if item["id"] == build["id"])
        return {
            "build": saved,
            "builds": builds,
            "warnings": warnings,
            "pulled": len(incoming),
        }

    def sync_inventory(self, build_id: str, *, card_name: str) -> dict:
        build = self._find_lun_build(build_id)
        target_card = str(card_name or "").strip()
        if not target_card:
            raise ValueError("card_name required")
        card = self.find_card_by_hint(target_card)
        if card is None:
            raise ValueError(f'Card "{target_card}" was not found.')
        if card.device_profile not in SVC_PROFILES:
            raise ValueError(
                "Sync Inventory requires a FlashSystem / SVC card profile."
            )

        run = self._lun_run_command(card)
        hosts_out = run("svcinfo lshost -delim :")
        maps_out = run("svcinfo lshostvdiskmap -delim :")
        volumes_out = run("svcinfo lsvdisk -delim :")
        fabric_out = run("svcinfo lsfabric -delim :")
        result = build_inventory_sync(
            hosts=parse_fc_hosts(hosts_out),
            volumes=parse_lsvdisk_volumes(volumes_out),
            maps=parse_host_lun_maps(maps_out),
            card_name=card.name,
            storage_profile=card.device_profile,
            storage_hint=card.name,
            fabric_or_host_wwpns=parse_fabric_logins(fabric_out),
        )

        groups = self.get_contingency_groups()
        existing_group = next(
            (
                group
                for group in groups
                if str(group.get("name") or "") == result["group"]["name"]
            ),
            None,
        )
        group = result["group"]
        group["id"] = (
            existing_group["id"]
            if existing_group is not None
            else new_group_id(group["name"], groups)
        )
        group["location"] = group.get("location") or group["name"]
        groups = self.upsert_contingency_group(group)

        updated_build = dict(build)
        updated_build["hosts"] = result["hosts"]
        updated_build["luns"] = result["luns"]
        updated_build.update(result["defaults"])
        builds = self.upsert_lun_build(updated_build)
        saved_build = next(item for item in builds if item["id"] == updated_build["id"])
        saved_group = next(item for item in groups if item["id"] == group["id"])
        return {
            "build": saved_build,
            "builds": builds,
            "group": saved_group,
            "groups": groups,
            "pulled": result["pulled"],
            "warnings": result["warnings"],
        }

    def sync_contingency_inventory(
        self, group_id: str, *, card_name: str = ""
    ) -> dict:
        existing = self._contingency_group_by_id(group_id)
        if existing is None:
            raise ValueError(f'Contingency group "{group_id}" was not found.')
        hint = (
            str(card_name or "").strip()
            or str(existing.get("storage_hint") or "").strip()
            or str(existing.get("name") or "").strip()
        )
        card = self.find_card_by_hint(hint)
        if card is None:
            raise ValueError(f'Card "{hint}" was not found.')
        if card.device_profile not in SVC_PROFILES:
            raise ValueError(
                "Sync Inventory requires a FlashSystem / SVC card profile."
            )

        run = self._lun_run_command(card)
        hosts_out = run("svcinfo lshost -delim :")
        maps_out = run("svcinfo lshostvdiskmap -delim :")
        volumes_out = run("svcinfo lsvdisk -delim :")
        fabric_out = run("svcinfo lsfabric -delim :")
        result = build_inventory_sync(
            hosts=parse_fc_hosts(hosts_out),
            volumes=parse_lsvdisk_volumes(volumes_out),
            maps=parse_host_lun_maps(maps_out),
            card_name=card.name,
            storage_profile=card.device_profile,
            storage_hint=card.name,
            fabric_or_host_wwpns=parse_fabric_logins(fabric_out),
            group_id=existing["id"],
        )

        shaped_group = result["group"]
        merged = dict(existing)
        merged["storage_hint"] = card.name
        merged["hosts"] = shaped_group["hosts"]
        merged["volumes"] = shaped_group["volumes"]
        merged["maps"] = shaped_group["maps"]
        groups = self.upsert_contingency_group(merged)
        saved_group = next(item for item in groups if item["id"] == merged["id"])
        return {
            "group": saved_group,
            "groups": groups,
            "pulled": result["pulled"],
            "warnings": result["warnings"],
        }

    @staticmethod
    def _lun_run_command(card: HealthCard) -> Callable[[str], str]:
        return lambda command: run_remote_ssh_command(
            card.host,
            card.port,
            card.username,
            command,
            key_path=card.key_path,
            key_passphrase=card.key_passphrase,
            password=card.password,
            timeout=120,
        )

    @staticmethod
    def _lun_build_content_hash(build: dict[str, Any]) -> str:
        normalized = normalize_build(build)
        if normalized is None:
            raise ValueError("Invalid LUN build")
        content = {
            key: value
            for key, value in normalized.items()
            if key not in _LUN_PREVIEW_HASH_OMIT
        }
        content["hosts"] = [
            {key: value for key, value in row.items() if key != "done"}
            for row in normalized["hosts"]
        ]
        content["luns"] = [
            {key: value for key, value in row.items() if key != "done"}
            for row in normalized["luns"]
        ]
        payload = json.dumps(content, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _lun_card_profile_warning(profile: str, card: HealthCard) -> str | None:
        card_profile = str(card.device_profile or "").strip()
        if not card_profile:
            return None
        expected_family = (
            "Spectrum Virtualize"
            if profile in SVC_PROFILES
            else "HPE"
            if profile in HPE_SHELL_PROFILES
            else ""
        )
        mismatch = (
            profile in SVC_PROFILES and card_profile in HPE_SHELL_PROFILES
        ) or (
            profile in HPE_SHELL_PROFILES and card_profile in SVC_PROFILES
        )
        if not mismatch:
            return None
        return (
            f"{expected_family} build profile {profile} conflicts with "
            f"Health Card {card.name} profile {card_profile}"
        )

    def _prepare_lun_build_preview(self, build: dict[str, Any]) -> dict[str, Any]:
        warnings = validate_build_for_preview(build)
        inventory_by_card: dict[str, dict[str, Any]] = {}
        cards: dict[str, HealthCard] = {}
        svc_hints: set[str] = set()
        for lun in build.get("luns") or []:
            profile = str(lun.get("storage_profile") or "").strip()
            if not supports_live_run(profile):
                continue
            hint = str(lun.get("card_hint") or "").strip()
            card = self.find_card_by_hint(hint)
            if card is None:
                msg = (
                    f"No Health Card matches storage hint {hint or '(empty)'}"
                )
                if msg not in warnings:
                    warnings.append(msg)
                continue
            cards[hint] = card
            profile_warning = self._lun_card_profile_warning(profile, card)
            if profile_warning and profile_warning not in warnings:
                warnings.append(profile_warning)
            if profile in SVC_PROFILES:
                svc_hints.add(hint)

        for hint, card in cards.items():
            if hint in svc_hints:
                try:
                    inventory_by_card[hint] = collect_inventory(
                        self._lun_run_command(card)
                    )
                except Exception as exc:
                    warnings.append(
                        f"Unable to collect inventory from {card.name}: {exc}"
                    )

        try:
            steps = build_lun_steps(build, inventory_by_card)
        except ValueError as exc:
            warnings.append(str(exc))
            steps = []
        live_steps = [step for step in steps if step["live"]]
        runnable = any(not step["skip"] for step in live_steps)
        plan_only = bool(steps) and not live_steps
        if live_steps and not runnable:
            warnings.append("No runnable live create steps remain.")
        return {
            "ok": not warnings and (runnable or plan_only),
            "warnings": warnings,
            "steps": steps,
            "log": [],
            "plan_only": plan_only,
            "runnable": runnable,
            "cards": [
                {"id": card.card_id, "name": card.name, "host": card.host}
                for card in cards.values()
            ],
        }

    def preview_lun_build(self, build_id: str) -> dict[str, Any]:
        try:
            build = self._find_lun_build(build_id)
        except ValueError as exc:
            result = {
                "ok": False,
                "warnings": [str(exc)],
                "steps": [],
                "log": [],
                "plan_only": False,
                "runnable": False,
            }
        else:
            result = self._prepare_lun_build_preview(build)

        with self._lock:
            self._lun_preview_session = None
            if result["ok"]:
                self._lun_preview_session = {
                    "build_id": str(build_id or "").strip(),
                    "content_hash": self._lun_build_content_hash(build),
                    "runnable": bool(result["runnable"]),
                    "expires_at": time.monotonic() + 300,
                }
        return result

    def create_lun_build(
        self,
        build_id: str,
        *,
        confirm: bool,
    ) -> dict[str, Any]:
        if confirm is not True:
            return {
                "ok": False,
                "warnings": ["confirm must be true before creating LUNs"],
                "log": [],
            }
        try:
            build = self._find_lun_build(build_id)
            content_hash = self._lun_build_content_hash(build)
        except ValueError:
            build = {}
            content_hash = ""
        target = str(build_id or "").strip()
        now = time.monotonic()
        with self._lock:
            session = self._lun_preview_session
            session_matches = bool(
                session
                and session.get("build_id") == target
                and session.get("content_hash") == content_hash
                and session.get("runnable") is True
                and float(session.get("expires_at") or 0) > now
            )
            if not session_matches:
                self._lun_preview_session = None
        if not session_matches:
            return {
                "ok": False,
                "warnings": [
                    "Preview must be run again before creating this LUN build."
                ],
                "log": [],
            }

        preview = self._prepare_lun_build_preview(build)
        if not preview["ok"]:
            return {
                "ok": False,
                "warnings": preview["warnings"],
                "log": [],
            }

        def run_for_card(card_hint: str, command: str) -> str:
            card = self.find_card_by_hint(card_hint)
            if card is None:
                raise RuntimeError(
                    f"No Health Card matches storage hint {card_hint or '(empty)'}"
                )
            return self._lun_run_command(card)(command)

        log = run_lun_steps(preview["steps"], run_for_card)
        ok = not any(entry["status"] == "failed" for entry in log)
        if ok:
            with self._lock:
                self._lun_preview_session = None
        return {
            "ok": ok,
            "warnings": preview["warnings"],
            "log": log,
            "plan_only": preview["plan_only"],
        }

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

    def find_card_by_hint(self, hint: str) -> HealthCard | None:
        with self._lock:
            cards = list(self._cards.values())
        card = resolve_card_by_storage_hint(cards, hint)
        return card if isinstance(card, HealthCard) else None

    def monitored_svc_card_dicts(self) -> list[dict]:
        with self._lock:
            cards = list(self._cards.values())
        return [
            {
                "id": card.card_id,
                "name": card.name,
                "device_profile": card.device_profile,
            }
            for card in cards
            if self.is_monitor_enabled(card.card_id)
            and card.device_profile in SVC_PROFILES
        ]

    def ensure_contingency_groups_from_cards(self) -> list[dict]:
        groups = self.get_contingency_groups()
        ensured = ensure_groups_for_cards(groups, self.monitored_svc_card_dicts())
        if self.contingency_groups_persist_available():
            return self.set_contingency_groups(ensured)
        return ensured

    def _contingency_group_by_id(self, group_id: str) -> dict | None:
        for group in self.get_contingency_groups():
            if str(group.get("id") or "") == str(group_id):
                return group
        return None

    @staticmethod
    def _snap_steps_payload(steps: list[Any]) -> list[dict[str, Any]]:
        return [
            {
                "kind": step.kind,
                "purpose": step.purpose,
                "cmd": step.cmd,
                "skip": step.skip,
                "reason": step.reason,
            }
            for step in steps
        ]

    @staticmethod
    def _snap_run_command(
        card: HealthCard,
        *,
        timeout: int = HOST_POWER_MUTATE_SSH_TIMEOUT,
    ) -> Callable[[str], str]:
        return lambda command: run_remote_ssh_command(
            card.host,
            card.port,
            card.username,
            command,
            key_path=card.key_path,
            key_passphrase=card.key_passphrase,
            password=card.password,
            timeout=timeout,
            device_profile=card.device_profile,
            sudo_password=card.sudo_password if card.device_profile == "hadoop_linux" else "",
        )

    @staticmethod
    def _host_power_card_payload(card: HealthCard) -> dict[str, Any]:
        return {
            "id": card.card_id,
            "name": card.name,
            "host": card.host,
            "commands": resolve_card_commands(
                card.device_profile,
                card.custom_commands,
                instance_id=card.serial_number,
                dscli_path=getattr(card, "dscli_path", "") or "",
                dscli_hmc=getattr(card, "dscli_hmc", "") or "",
                username=str(getattr(card, "username", "") or ""),
                password=card.password or "",
            ),
        }

    def _host_power_cards_for_ids(self, card_ids: list[int]) -> list[HealthCard]:
        selected_ids = set(card_ids)
        with self._lock:
            cards = list(self._cards.values())
        return [
            card
            for card in cards
            if card.card_id in selected_ids
            and card.device_profile == "hadoop_linux"
            and str(card.host or "").strip()
        ]

    def _host_power_selection(
        self,
        raw_card_ids: list[Any],
    ) -> tuple[list[HealthCard], list[str]]:
        parsed_ids, warnings = coerce_card_ids(raw_card_ids)
        cards = self._host_power_cards_for_ids(parsed_ids)
        if not cards:
            if not parsed_ids:
                if raw_card_ids:
                    warnings.append("No valid card_ids in selection")
                else:
                    warnings.append("No hosts selected")
            else:
                warnings.append("No eligible Hadoop hosts matched the selection")
        return cards, warnings

    def host_power_cards(self) -> list[dict[str, Any]]:
        with self._lock:
            cards = list(self._cards.values())
        return [
            {
                "id": card.card_id,
                "name": card.name,
                "host": card.host,
                "device_profile": card.device_profile,
            }
            for card in cards
            if card.device_profile == "hadoop_linux"
            and str(card.host or "").strip()
        ]

    def host_power_preview(self, card_ids: list[Any]) -> dict[str, Any]:
        cards, selection_warnings = self._host_power_selection(card_ids)
        preview = build_host_power_preview(
            [self._host_power_card_payload(card) for card in cards]
        )
        if selection_warnings:
            preview["warnings"] = selection_warnings + preview.get("warnings", [])
        if not cards:
            preview["ok"] = False
        return preview

    def host_power_run(
        self,
        card_ids: list[Any],
        *,
        confirm: bool,
        mode: str,
    ) -> dict[str, Any]:
        require_host_power_confirm(confirm)
        mode_n = normalize_host_power_mode(mode)
        cards, selection_warnings = self._host_power_selection(card_ids)
        if not cards:
            return {"ok": False, "warnings": selection_warnings, "hosts": []}
        hosts: list[dict[str, Any]] = []
        for card in cards:
            payload = self._host_power_card_payload(card)
            steps = steps_for_host_power_mode(
                extract_power_steps(payload["commands"]),
                mode_n,
            )
            if mode_n == HOST_POWER_MODE_SHUTDOWN_ONLY and not steps:
                hosts.append(
                    {
                        "card_id": card.card_id,
                        "name": card.name,
                        "host": card.host,
                        "ok": False,
                        "error": "No OS shutdown Power - step",
                        "results": [],
                        "aborted": False,
                    }
                )
                continue
            result = run_host_power_for_card(
                steps=steps,
                run_command=self._snap_run_command(
                    card, timeout=HOST_POWER_MUTATE_SSH_TIMEOUT
                ),
            )
            hosts.append(
                {
                    "card_id": card.card_id,
                    "name": card.name,
                    "host": card.host,
                    **result,
                }
            )
        response: dict[str, Any] = {
            "ok": all(host["ok"] for host in hosts),
            "hosts": hosts,
        }
        if selection_warnings:
            response["warnings"] = selection_warnings
        return response

    def host_power_precheck(self, card_ids: list[Any], *, letter: str) -> dict[str, Any]:
        letter_n = normalize_precheck_letter(letter)
        cards, selection_warnings = self._host_power_selection(card_ids)
        if not cards:
            return {
                "ok": False,
                "letter": letter_n,
                "warnings": selection_warnings,
                "hosts": [],
            }
        hosts: list[dict[str, Any]] = []
        for card in cards:
            payload = self._host_power_card_payload(card)
            result = run_host_power_precheck_for_card(
                letter=letter_n,
                commands=payload["commands"],
                run_command=self._snap_run_command(
                    card, timeout=HOST_POWER_PRECHECK_SSH_TIMEOUT
                ),
            )
            hosts.append(
                {
                    "card_id": card.card_id,
                    "name": card.name,
                    "host": card.host,
                    **result,
                }
            )
        response: dict[str, Any] = {
            "ok": all(host["ok"] for host in hosts),
            "letter": letter_n,
            "hosts": hosts,
        }
        if selection_warnings:
            response["warnings"] = selection_warnings
        return response

    def generate_contingency_snaps(self, group_id: str) -> dict[str, Any]:
        group = self._contingency_group_by_id(group_id)
        if group is None:
            return {
                "ok": False,
                "warnings": [f"Unknown contingency group {group_id}"],
                "log": [],
            }
        generated = generate_snap_rows(group)
        groups = upsert_group(self.get_contingency_groups(), generated)
        self.set_contingency_groups(groups)
        return {"ok": True, "group": generated, "warnings": [], "log": []}

    def preview_contingency_snaps(
        self,
        group_id: str,
        *,
        assign_cg_enabled: bool | None = None,
        assign_cg_name: str | None = None,
    ) -> dict[str, Any]:
        group = self._contingency_group_by_id(group_id)
        if group is None:
            return {
                "ok": False,
                "warnings": [f"Unknown contingency group {group_id}"],
                "log": [],
                "steps": [],
            }
        hint = str(group.get("storage_hint") or "").strip()
        card = self.find_card_by_hint(hint)
        if card is None:
            return {
                "ok": False,
                "warnings": [f"No Health Card matches storage hint {hint or '(empty)'}"],
                "log": [],
                "steps": [],
            }
        try:
            inventory = collect_inventory(self._snap_run_command(card))
        except Exception as exc:
            return {
                "ok": False,
                "warnings": [f"Unable to collect array inventory: {exc}"],
                "log": [],
                "steps": [],
            }
        snap_steps, snap_warnings = build_snap_steps(group, inventory=inventory)
        enabled = (
            assign_cg_enabled
            if assign_cg_enabled is not None
            else bool(group.get("snap_assign_cg_enabled"))
        )
        cg_name = (
            assign_cg_name
            if assign_cg_name is not None
            else str(group.get("snap_assign_cg_name") or "")
        )
        fc_groups: list[dict] = []
        fc_maps: list[dict] = []
        if enabled:
            try:
                fc_groups, fc_maps = collect_fc_consistgrp_inventory(
                    self._snap_run_command(card)
                )
            except Exception as exc:
                return {
                    "ok": False,
                    "warnings": [
                        f"ERROR: Unable to collect FlashCopy CG inventory: {exc}"
                    ],
                    "log": [],
                    "steps": [],
                    "card": {
                        "id": card.card_id,
                        "name": card.name,
                        "host": card.host,
                    },
                }
        steps, assign_warnings = append_snap_cg_assign_steps(
            snap_steps,
            cg_name=cg_name,
            enabled=enabled,
            fc_groups=fc_groups,
            fc_maps=fc_maps,
        )
        warnings = snap_warnings + assign_warnings
        ok = (not snap_warnings) and (
            not any(w.startswith("ERROR:") for w in assign_warnings)
        )
        return {
            "ok": ok,
            "warnings": warnings,
            "log": [],
            "steps": self._snap_steps_payload(steps),
            "card": {
                "id": card.card_id,
                "name": card.name,
                "host": card.host,
            },
        }

    def create_contingency_snaps(
        self,
        group_id: str,
        *,
        confirm: bool,
        assign_cg_enabled: bool | None = None,
        assign_cg_name: str | None = None,
    ) -> dict[str, Any]:
        if confirm is not True:
            return {
                "ok": False,
                "warnings": ["confirm must be true before creating snap volumes"],
                "log": [],
            }
        preview = self.preview_contingency_snaps(
            group_id,
            assign_cg_enabled=assign_cg_enabled,
            assign_cg_name=assign_cg_name,
        )
        if not preview["ok"]:
            return {
                "ok": False,
                "warnings": preview["warnings"],
                "log": preview["log"],
            }
        group = self._contingency_group_by_id(group_id)
        card = self.find_card_by_hint(str(group.get("storage_hint") or "")) if group else None
        if card is None:
            return {
                "ok": False,
                "warnings": ["No Health Card matches the contingency group storage hint"],
                "log": [],
            }
        steps = [
            SnapStep(
                kind=step["kind"],
                purpose=step["purpose"],
                cmd=step["cmd"],
                skip=step["skip"],
                reason=step["reason"],
            )
            for step in preview["steps"]
        ]
        result = run_snap_steps(steps, self._snap_run_command(card))
        result["warnings"] = preview["warnings"]
        return result

    def _fc_consistgrp_card_by_id(self, card_id: int) -> HealthCard | None:
        with self._lock:
            return self._cards.get(card_id)

    def fc_consistgrp_cards(self) -> list[dict[str, Any]]:
        self.sync_from_app()
        with self._lock:
            stored = list(sorted(self._cards.values(), key=lambda card: card.card_id))
        cards: list[dict[str, Any]] = []
        for card in stored:
            site = str(card.category or "").strip() or card.name
            cards.append(
                {
                    "id": card.card_id,
                    "name": card.name,
                    "host": card.host,
                    "url": card.url or "",
                    "site": site,
                    "monitor_on": self.is_monitor_enabled(card.card_id),
                    "device_profile": card.device_profile or "",
                    "card_type": "ssh",
                    "capacity_unit_mode": get_capacity_unit_mode(),
                }
            )
        return cards

    def _esx_snap_card_by_id(self, card_id: int) -> HealthCard | None:
        with self._lock:
            return self._cards.get(card_id)

    def _esx_snap_eligible(self, card: HealthCard) -> bool:
        return (
            str(card.device_profile or "") in SVC_PROFILES
            and str(card.host or "").strip() != ""
        )

    def esx_snap_policy_cards(self) -> list[dict[str, Any]]:
        with self._lock:
            stored = list(sorted(self._cards.values(), key=lambda card: card.card_id))
        return [
            {
                "id": card.card_id,
                "name": card.name,
                "host": card.host,
                "device_profile": card.device_profile or "",
                "default_vg_name": default_vg_name(card.name),
            }
            for card in stored
            if self._esx_snap_eligible(card)
        ]

    def _esx_snap_inventory(self, card: HealthCard) -> dict[str, Any]:
        return collect_esx_snap_inventory(self._snap_run_command(card))

    def esx_snap_policy_volumes(self, card_id: int) -> dict[str, Any]:
        card = self._esx_snap_card_by_id(card_id)
        if card is None or not self._esx_snap_eligible(card):
            return {
                "ok": False,
                "error": f"Unknown or ineligible Health Card id {card_id}",
                "volumes": [],
                "policies": [],
                "volume_groups": [],
            }
        inventory = self._esx_snap_inventory(card)
        if not inventory.get("ok"):
            return {
                "ok": False,
                "error": inventory.get("error") or "Unable to collect inventory",
                "volumes": [],
                "policies": [],
                "volume_groups": [],
            }
        return {
            "ok": True,
            "error": "",
            "volumes": inventory["volumes"],
            "policies": sorted(inventory["policies"]),
            "volume_groups": sorted(inventory["volume_groups"]),
        }

    def preview_esx_snap_policy(self, payload: dict) -> dict[str, Any]:
        start_time = str(payload.get("start_time") or "02:00")
        policy_name = str(payload.get("policy_name") or "").strip() or POLICY_NAME
        raw_arrays = payload.get("arrays") or []
        if not isinstance(raw_arrays, list) or not raw_arrays:
            return {
                "ok": False,
                "arrays": [],
                "preview_hash": "",
                "policy_name": policy_name,
                "warnings": ["ERROR: select at least one array"],
            }
        arrays_out: list[dict[str, Any]] = []
        for item in raw_arrays:
            if not isinstance(item, dict):
                continue
            try:
                card_id = int(item.get("card_id"))
            except (TypeError, ValueError):
                arrays_out.append(
                    {
                        "card_id": item.get("card_id"),
                        "name": "",
                        "vg_name": str(item.get("vg_name") or ""),
                        "runnable": False,
                        "warnings": ["ERROR: card_id is required"],
                        "steps": [],
                    }
                )
                continue
            card = self._esx_snap_card_by_id(card_id)
            vg_name = str(item.get("vg_name") or "") or (
                default_vg_name(card.name) if card is not None else ""
            )
            volume_names = [
                str(name) for name in (item.get("volume_names") or []) if str(name).strip()
            ]
            if card is None or not self._esx_snap_eligible(card):
                arrays_out.append(
                    {
                        "card_id": card_id,
                        "name": "",
                        "vg_name": vg_name,
                        "runnable": False,
                        "warnings": [f"ERROR: Unknown or ineligible Health Card id {card_id}"],
                        "steps": [],
                    }
                )
                continue
            inventory = self._esx_snap_inventory(card)
            if not inventory.get("ok"):
                arrays_out.append(
                    {
                        "card_id": card_id,
                        "name": card.name,
                        "vg_name": vg_name,
                        "runnable": False,
                        "warnings": [f"ERROR: {inventory.get('error') or 'inventory failed'}"],
                        "steps": [],
                    }
                )
                continue
            volumes = list(inventory["volumes"])
            apply_checked_volume_details(
                self._snap_run_command(card), volumes, volume_names
            )
            steps, warnings, runnable = build_esx_snap_array_steps(
                vg_name=vg_name,
                volume_names=volume_names,
                start_time=start_time,
                policies=set(inventory["policies"]),
                volume_groups=set(inventory["volume_groups"]),
                volumes=volumes,
                policy_name=policy_name,
            )
            arrays_out.append(
                {
                    "card_id": card_id,
                    "name": card.name,
                    "vg_name": vg_name,
                    "runnable": runnable,
                    "warnings": warnings,
                    "steps": steps_payload(steps),
                }
            )
        ok = any(row.get("runnable") for row in arrays_out)
        return {
            "ok": ok,
            "arrays": arrays_out,
            "policy_name": policy_name,
            "preview_hash": preview_hash(start_time, list(raw_arrays), policy_name),
        }

    def run_esx_snap_policy(self, payload: dict, *, confirm: bool) -> dict[str, Any]:
        policy_name = str(payload.get("policy_name") or "").strip() or POLICY_NAME
        if confirm is not True:
            return {
                "ok": False,
                "arrays": [],
                "policy_name": policy_name,
                "warnings": ["confirm must be true before creating policy or volume group"],
            }
        start_time = str(payload.get("start_time") or "02:00")
        raw_arrays = payload.get("arrays") or []
        expected = preview_hash(
            start_time,
            list(raw_arrays) if isinstance(raw_arrays, list) else [],
            policy_name,
        )
        given = str(payload.get("preview_hash") or "")
        if not given or given != expected:
            return {
                "ok": False,
                "arrays": [],
                "policy_name": policy_name,
                "warnings": ["Preview must be run again before creating policy or volume group."],
            }
        preview = self.preview_esx_snap_policy(payload)
        results: list[dict[str, Any]] = []
        for row in preview.get("arrays") or []:
            if not row.get("runnable"):
                results.append(
                    {
                        "card_id": row.get("card_id"),
                        "name": row.get("name") or "",
                        "ok": False,
                        "warnings": row.get("warnings") or [],
                        "log": [],
                    }
                )
                continue
            card_id = int(row["card_id"])
            card = self._esx_snap_card_by_id(card_id)
            live = self._esx_snap_inventory(card)
            vg_name = str(row.get("vg_name") or "")
            if not live.get("ok"):
                results.append(
                    {
                        "card_id": card_id,
                        "name": card.name if card else "",
                        "ok": False,
                        "warnings": [f"ERROR: {live.get('error')}"],
                        "log": [],
                    }
                )
                continue
            if policy_name in set(live["policies"]) or vg_name in set(live["volume_groups"]):
                results.append(
                    {
                        "card_id": card_id,
                        "name": card.name if card else "",
                        "ok": False,
                        "warnings": [
                            f"ERROR: {policy_name} or {vg_name} already exists; "
                            "no commands were run. If a previous Run created the policy, "
                            f"delete {policy_name} on the array before retrying."
                        ],
                        "log": [],
                    }
                )
                continue
            steps = [
                SnapStep(
                    kind=step["kind"],
                    purpose=step["purpose"],
                    cmd=step["cmd"],
                    skip=step.get("skip") or False,
                    reason=step.get("reason") or "",
                )
                for step in row.get("steps") or []
            ]
            executed = run_snap_steps(steps, self._snap_run_command(card))
            if not executed.get("ok"):
                executed.setdefault("warnings", [])
                executed["warnings"].append(
                    f"No automatic rollback. If {policy_name} was created, "
                    "delete it on the array before retrying."
                )
            results.append(
                {
                    "card_id": card_id,
                    "name": card.name if card else "",
                    "ok": bool(executed.get("ok")),
                    "warnings": executed.get("warnings") or [],
                    "log": executed.get("log") or [],
                }
            )
        overall_ok = any(row.get("ok") for row in results)
        return {"ok": overall_ok, "arrays": results, "policy_name": policy_name}

    def _fc_host_lun_maps(self, card: HealthCard) -> tuple[list[dict], str | None]:
        try:
            run = self._snap_run_command(card)
            host_out = run("svcinfo lshostvdiskmap -delim :")
            if not str(host_out or "").strip():
                host_out = run("svcinfo lshostvdiskmap")
            return parse_host_lun_maps(host_out or ""), None
        except Exception as exc:
            return [], f"Unable to collect host maps: {exc}"

    def schedule_context_for_card(
        self, card: HealthCard, *, threshold: float = 80.0
    ) -> dict:
        pools = pool_capacity_from_commands(card.command_results)
        used_pct: float | None = None
        if pools:
            used_pct = max(float(pool.get("used_pct") or 0) for pool in pools)
        else:
            analysis = analyze_health(card.name, card.command_results, card.metrics)
            capacity = analysis.get("capacity_summary") or {}
            if capacity.get("used_pct") is not None:
                used_pct = float(capacity.get("used_pct") or 0)
        overrides = self.get_snapshot_overrides()
        override = overrides.get(str(card.card_id)) or overrides.get(card.name)
        return schedule_context_from_capacity(
            used_pct=used_pct,
            threshold=threshold,
            override=override,
        )

    def fc_consistgrp_inventory(
        self, card_id: int, *, include_summaries: bool = True
    ) -> dict[str, Any]:
        card = self._fc_consistgrp_card_by_id(card_id)
        if card is None:
            return {
                "ok": False,
                "warnings": [f"Unknown Health Card id {card_id}"],
                "groups": [],
                "maps": [],
                "stand_alone": [],
                "summaries": [],
            }
        try:
            groups, maps = collect_fc_consistgrp_inventory(self._snap_run_command(card))
        except Exception as exc:
            return {
                "ok": False,
                "warnings": [f"Unable to collect array inventory: {exc}"],
                "groups": [],
                "maps": [],
                "stand_alone": [],
                "summaries": [],
            }
        warnings: list[str] = []
        host_maps: list[dict] = []
        summaries: list[dict] = []
        if include_summaries:
            host_maps, host_warn = self._fc_host_lun_maps(card)
            if host_warn:
                warnings.append(host_warn)
            schedule = self.schedule_context_for_card(card)
            summaries = build_cg_summaries(
                groups=groups,
                maps=maps,
                host_maps=host_maps,
                schedule=schedule,
            )
        _in_group, stand_alone = partition_maps(maps)
        return {
            "ok": True,
            "warnings": warnings,
            "card": {"id": card.card_id, "name": card.name, "host": card.host},
            "groups": groups,
            "maps": maps,
            "stand_alone": stand_alone,
            "summaries": summaries,
            "host_maps": host_maps,
        }

    def contingency_fc_cg_summary(self, group_id: str) -> dict[str, Any]:
        group = self._contingency_group_by_id(group_id)
        if group is None:
            return {
                "ok": False,
                "warnings": [f"Unknown contingency group {group_id}"],
                "summaries": [],
                "card": None,
            }
        if not self.is_unlocked():
            return {
                "ok": False,
                "warnings": [
                    "LaunchPad must be unlocked to collect FlashCopy CG summary."
                ],
                "summaries": [],
                "card": None,
            }
        hint = (
            str(group.get("storage_hint") or "").strip()
            or str(group.get("name") or "").strip()
        )
        card = self.find_card_by_hint(hint)
        if card is None:
            return {
                "ok": False,
                "warnings": [
                    f"No Health Card matches storage hint {hint or '(empty)'}"
                ],
                "summaries": [],
                "card": None,
            }
        inventory = self.fc_consistgrp_inventory(card.card_id)
        if not inventory.get("ok"):
            return {
                "ok": False,
                "warnings": inventory.get("warnings") or [],
                "summaries": [],
                "card": inventory.get("card"),
            }
        return {
            "ok": True,
            "card": inventory["card"],
            "summaries": inventory.get("summaries") or [],
            "warnings": inventory.get("warnings") or [],
        }

    def preview_fc_consistgrp(
        self,
        card_id: int,
        action: str,
        payload: dict,
    ) -> dict[str, Any]:
        inventory = self.fc_consistgrp_inventory(card_id, include_summaries=False)
        if not inventory["ok"]:
            return {"ok": False, "warnings": inventory["warnings"], "steps": []}
        steps, warnings = build_fc_consistgrp_steps(
            action, payload, groups=inventory["groups"], maps=inventory["maps"]
        )
        return {
            "ok": fc_consistgrp_preview_ok(steps, warnings),
            "warnings": warnings,
            "steps": self._snap_steps_payload(steps),
            "card": inventory["card"],
        }

    def run_fc_consistgrp(
        self,
        card_id: int,
        action: str,
        payload: dict,
        *,
        confirm: bool,
    ) -> dict[str, Any]:
        if confirm is not True:
            return {
                "ok": False,
                "warnings": ["confirm must be true before running consistency group actions"],
                "log": [],
            }
        preview = self.preview_fc_consistgrp(card_id, action, payload)
        if not preview["ok"]:
            return {"ok": False, "warnings": preview["warnings"], "log": []}
        card = self._fc_consistgrp_card_by_id(card_id)
        if card is None:
            return {
                "ok": False,
                "warnings": [f"Unknown Health Card id {card_id}"],
                "log": [],
            }
        steps = [
            SnapStep(
                kind=step["kind"],
                purpose=step["purpose"],
                cmd=step["cmd"],
                skip=step["skip"],
                reason=step["reason"],
            )
            for step in preview["steps"]
        ]
        result = run_snap_steps(steps, self._snap_run_command(card))
        result["warnings"] = preview["warnings"]
        return result

    def mouse_jiggler_enabled(self) -> bool:
        with self._lock:
            getter = self._get_setting
        if not getter:
            return False
        return setting_to_enabled(getter(SETTING_MOUSE_JIGGLER, ""))

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

    def health_alert_persist_available(self) -> bool:
        with self._lock:
            return self._get_setting is not None and self._set_setting is not None

    def _load_health_alert_state(self) -> dict[str, Any]:
        with self._lock:
            getter = self._get_setting
        if not getter:
            return empty_state()
        return load_state(getter(HEALTH_ALERT_SETTING, "") or "")

    def _save_health_alert_state(self, state: dict[str, Any]) -> None:
        with self._lock:
            setter = self._set_setting
        if not setter:
            raise RuntimeError("LaunchPad must be unlocked to save health alert state.")
        setter(HEALTH_ALERT_SETTING, dump_state(state))

    @staticmethod
    def _active_health_alert_fingerprints(
        cards: list[dict[str, Any]], monitor_states: dict[str, bool]
    ) -> set[str]:
        del monitor_states
        active: set[str] = set()
        for card in cards:
            active |= fingerprints_for_card(card)
        return active

    def _health_alert_cards_payload(
        self,
        cards: list[dict[str, Any]],
        state: dict[str, Any],
        *,
        now: float,
    ) -> dict[str, dict[str, Any]]:
        alarm_muted = state.get("alarm_muted") or {}
        paused_until = state.get("paused_until") or {}
        out: dict[str, dict[str, Any]] = {}
        for card in cards:
            card_id = card.get("id")
            if card_id is None:
                continue
            key = str(card_id)
            pause_end = paused_until.get(key)
            if pause_end is not None and now >= float(pause_end):
                pause_end = None
            out[key] = {
                "alarm_muted": bool(alarm_muted.get(key)),
                "paused_until": float(pause_end) if pause_end is not None else None,
            }
        return out

    @staticmethod
    def _health_alert_art_urls(cards: list[dict[str, Any]]) -> dict[str, str]:
        urls: dict[str, str] = {}
        for card in cards:
            card_id = card.get("id")
            card_name = str(card.get("name") or "")
            if card_id is None or not card_name:
                continue
            try:
                art_path = resolve_health_alert_art(card_name)
            except OSError:
                art_path = None
            if art_path is not None:
                urls[str(card_id)] = f"/api/health-alerts/art?card_id={card_id}"
        return urls

    def health_alert_art_path(self, card_id: int) -> Path | None:
        with self._lock:
            card = self._cards.get(int(card_id))
            card_name = card.name if card is not None else ""
        if not card_name:
            return None
        try:
            return resolve_health_alert_art(card_name)
        except OSError:
            return None

    def get_health_alerts(self) -> dict[str, Any]:
        cards = self.list_cards(allow_sync=False)
        monitor = self.monitor_states()
        state = self._load_health_alert_state()
        active = self._active_health_alert_fingerprints(cards, monitor)
        pruned = prune_acknowledgements(state, active)
        if dump_state(pruned) != dump_state(state):
            try:
                self._save_health_alert_state(pruned)
            except RuntimeError:
                pass
            state = pruned
        now = time.time()
        alerts = list_popup_alerts(cards, monitor, state, now=now)
        art_urls = self._health_alert_art_urls(cards)
        for alert in alerts:
            art_url = art_urls.get(str(alert.get("card_id")))
            if art_url:
                alert["art_url"] = art_url
        cards_payload = self._health_alert_cards_payload(cards, state, now=now)
        for card_id, art_url in art_urls.items():
            if card_id in cards_payload:
                cards_payload[card_id]["art_url"] = art_url
        return {
            "alerts": alerts,
            "cards": cards_payload,
        }

    def acknowledge_health_alert(self, fingerprint: str) -> dict[str, Any]:
        state = acknowledge(self._load_health_alert_state(), str(fingerprint))
        self._save_health_alert_state(state)
        return self.get_health_alerts()

    def acknowledge_health_alerts(self, fingerprints: list[str]) -> dict[str, Any]:
        state = self._load_health_alert_state()
        for fingerprint in fingerprints:
            state = acknowledge(state, str(fingerprint))
        self._save_health_alert_state(state)
        return self.get_health_alerts()

    def pause_health_alert(self, card_id: int, minutes: int) -> dict[str, Any]:
        state = pause_card(
            self._load_health_alert_state(),
            card_id,
            minutes,
            now=time.time(),
        )
        self._save_health_alert_state(state)
        return self.get_health_alerts()

    def set_health_alarm(self, card_id: int, muted: bool) -> dict[str, Any]:
        state = set_alarm(self._load_health_alert_state(), card_id, muted)
        self._save_health_alert_state(state)
        return self.get_health_alerts()

    def update_volume_find_card_host(self, card_id: int, host: str) -> dict:
        if not self.is_unlocked():
            raise RuntimeError("LaunchPad must be unlocked to update card host.")
        normalized = normalize_site_host(host)
        if not normalized:
            raise ValueError("host is required after normalize")
        with self._lock:
            patcher = self._card_patcher
        if patcher is None:
            raise RuntimeError("LaunchPad must be unlocked to update card host.")
        cid = int(card_id)
        result = patcher(cid, host=normalized)
        with self._lock:
            card = self._cards.get(cid)
            if card is not None:
                card.host = normalized
                name = card.name
            else:
                name = str(result.get("name") or "")
        return {
            "card_id": cid,
            "host": normalized,
            "name": name or str(result.get("name") or ""),
        }

    def ensure_anderson_card_rename(self) -> dict | None:
        if not self.is_unlocked():
            raise RuntimeError("LaunchPad must be unlocked to rename Anderson card.")
        with self._lock:
            patcher = self._card_patcher
        if patcher is None:
            return None
        cards = self.list_cards(allow_sync=False)
        plan = anderson_rename_plan(cards)
        if plan is None:
            return None
        cid = int(plan["card_id"])
        new_name = str(plan["new_name"])
        new_host = str(plan["new_host"])
        patcher(cid, host=new_host, name=new_name)
        with self._lock:
            card = self._cards.get(cid)
            if card is not None:
                card.name = new_name
                card.host = new_host
        return plan

    def scan_fc_consistgrp_status_live(
        self, *, card_id: int | None = None
    ) -> dict[str, Any]:
        if not self.is_unlocked():
            raise RuntimeError(
                "LaunchPad must be unlocked to refresh FlashCopy CG Status live."
            )
        self.sync_from_app()
        cards = self.list_cards(allow_sync=False)
        rows: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for card_dict in cards:
            current_id = card_dict.get("id")
            if current_id is None:
                continue
            if card_id is not None and int(current_id) != int(card_id):
                continue
            monitor_on = self.is_monitor_enabled(int(current_id))
            eligible_card = dict(card_dict)
            eligible_card["monitor_on"] = monitor_on
            if not is_fc_consistgrp_status_eligible(eligible_card):
                continue
            card = self._cards.get(int(current_id))
            if card is None:
                continue
            site = str(card.category or "").strip() or card.name
            try:
                groups, _maps = collect_fc_consistgrp_inventory(
                    self._snap_run_command(card)
                )
                for group in groups:
                    status = str(group.get("status") or "")
                    rows.append(
                        {
                            "site": site,
                            "card_name": card.name,
                            "host": str(card.host or ""),
                            "name": str(group.get("name") or ""),
                            "status": status,
                            "map_count": group.get("map_count", 0),
                            "flash_time": format_flash_time_display(
                                str(group.get("flash_time") or "")
                            ),
                            "error": "",
                            "card_id": card.card_id,
                            "bucket": normalize_fc_cg_status_bucket(status),
                        }
                    )
            except Exception as exc:
                errors.append(
                    {
                        "card_id": card.card_id,
                        "card_name": card.name,
                        "error": str(exc),
                    }
                )
        rows.sort(
            key=lambda row: (
                str(row.get("site") or "").lower(),
                str(row.get("card_name") or "").lower(),
                str(row.get("name") or "").lower(),
            )
        )
        payload = {"rows": rows, "errors": errors}
        with self._lock:
            self._fc_consistgrp_status_cache = payload
        return payload

    def get_fc_consistgrp_status_cache(self) -> dict[str, Any] | None:
        with self._lock:
            if self._fc_consistgrp_status_cache is None:
                return None
            return {
                "rows": list(self._fc_consistgrp_status_cache.get("rows") or []),
                "errors": list(self._fc_consistgrp_status_cache.get("errors") or []),
            }

    def set_fc_consistgrp_status_cache(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._fc_consistgrp_status_cache = {
                "rows": list(payload.get("rows") or []),
                "errors": list(payload.get("errors") or []),
            }

    def export_fc_consistgrp_status_bytes(
        self,
        *,
        format: str,
        card_id: int | None = None,
        bucket: str = "all",
    ) -> tuple[bytes, str, str]:
        cached = self.get_fc_consistgrp_status_cache()
        if cached is None:
            raise LookupError("Refresh live before exporting.")
        export_format = str(format or "").strip().lower()
        if export_format != "xlsx":
            raise ValueError("Export format must be xlsx.")
        rows = list(cached.get("rows") or [])
        if card_id is not None:
            rows = [row for row in rows if int(row.get("card_id") or -1) == int(card_id)]
        rows = filter_status_rows(rows, bucket=bucket)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        body = export_fc_consistgrp_status_xlsx(rows)
        return (
            body,
            f"FC_CG_Status_{stamp}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def scan_fc_cg_summary_live(
        self, *, card_id: int | None = None, reset: bool = False
    ) -> dict[str, Any]:
        if not self.is_unlocked():
            raise RuntimeError(
                "LaunchPad must be unlocked to refresh FlashCopy CG summary live."
            )
        self.sync_from_app()
        cards = self.list_cards(allow_sync=False)
        rows: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        skipped_monitor_off: list[str] = []
        eligible = 0
        for card_dict in cards:
            current_id = card_dict.get("id")
            if current_id is None:
                continue
            if card_id is not None and int(current_id) != int(card_id):
                continue
            monitor_on = self.is_monitor_enabled(int(current_id))
            eligible_card = dict(card_dict)
            eligible_card["monitor_on"] = monitor_on
            if not is_fc_consistgrp_status_eligible(eligible_card):
                profile = str(card_dict.get("device_profile") or "")
                if (
                    not monitor_on
                    and str(card_dict.get("card_type") or "ssh").lower() == "ssh"
                    and is_svc_fc_profile(profile)
                ):
                    card_obj = self._cards.get(int(current_id))
                    card_name = str(
                        card_dict.get("name")
                        or (card_obj.name if card_obj is not None else "")
                        or current_id
                    ).strip()
                    skipped_monitor_off.append(card_name or str(current_id))
                continue
            card = self._cards.get(int(current_id))
            if card is None:
                continue
            eligible += 1
            site = str(card.name or "").strip() or "Unknown"
            try:
                inventory = self.fc_consistgrp_inventory(int(current_id))
                if not inventory.get("ok"):
                    warnings = [
                        str(w) for w in (inventory.get("warnings") or []) if w
                    ]
                    errors.append(
                        {
                            "card_id": card.card_id,
                            "card_name": card.name,
                            "error": "; ".join(warnings) or "inventory failed",
                        }
                    )
                    continue
                for summary in inventory.get("summaries") or []:
                    name = str(summary.get("name") or "")
                    rows.append(
                        {
                            "site": site,
                            "card_name": card.name,
                            "host": str(card.host or ""),
                            "card_id": card.card_id,
                            "name": name,
                            "status": str(summary.get("status") or ""),
                            "flash_time": str(summary.get("flash_time") or ""),
                            "progress_pct": summary.get("progress_pct"),
                            "fc_map_count": summary.get("fc_map_count", 0),
                            "host_map_count": summary.get("host_map_count", 0),
                            "total_size": str(summary.get("total_size") or ""),
                            "policy": str(summary.get("policy") or ""),
                            "snaps_per_week": summary.get("snaps_per_week"),
                            "row_key": f"{card.card_id}:{name}",
                        }
                    )
            except Exception as exc:
                errors.append(
                    {
                        "card_id": card.card_id,
                        "card_name": card.name,
                        "error": str(exc),
                    }
                )
        if card_id is not None and not reset:
            with self._lock:
                prior = self._fc_cg_summary_live_cache
            if prior is not None:
                prior_rows = [
                    row
                    for row in (prior.get("rows") or [])
                    if int(row.get("card_id") or -1) != int(card_id)
                ]
                prior_errors = [
                    err
                    for err in (prior.get("errors") or [])
                    if int(err.get("card_id") or -1) != int(card_id)
                ]
                prior_skipped = [
                    name
                    for name in (prior.get("skipped_monitor_off") or [])
                    if name not in skipped_monitor_off
                ]
                rows = prior_rows + rows
                errors = prior_errors + errors
                skipped_monitor_off = prior_skipped + skipped_monitor_off
                # eligible for this request is only the current card; expose
                # total unique cards represented in merged rows/errors.
                card_ids = {
                    int(row.get("card_id"))
                    for row in rows
                    if row.get("card_id") is not None
                } | {
                    int(err.get("card_id"))
                    for err in errors
                    if err.get("card_id") is not None
                }
                eligible = len(card_ids)
        rows.sort(
            key=lambda row: (
                str(row.get("site") or "").lower(),
                str(row.get("card_name") or "").lower(),
                str(row.get("name") or "").lower(),
            )
        )
        payload = {
            "rows": rows,
            "errors": errors,
            "eligible": eligible,
            "skipped_monitor_off": skipped_monitor_off,
        }
        with self._lock:
            self._fc_cg_summary_live_cache = payload
        return payload

    def get_fc_cg_summary_live_cache(self) -> dict[str, Any] | None:
        with self._lock:
            if self._fc_cg_summary_live_cache is None:
                return None
            return {
                "rows": list(self._fc_cg_summary_live_cache.get("rows") or []),
                "errors": list(self._fc_cg_summary_live_cache.get("errors") or []),
            }

    def set_fc_cg_summary_live_cache(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._fc_cg_summary_live_cache = {
                "rows": list(payload.get("rows") or []),
                "errors": list(payload.get("errors") or []),
            }

    def export_fc_cg_summary_selected_bytes(
        self,
        *,
        selected: list[str],
        open_after: bool = False,
    ) -> tuple[bytes, str, str]:
        del open_after
        if not selected:
            raise ValueError("At least one row must be selected.")
        with self._lock:
            cached = self._fc_cg_summary_live_cache
        if cached is None:
            raise LookupError("Refresh CG summary before exporting.")
        selected_set = set(selected)
        rows = [
            row
            for row in (cached.get("rows") or [])
            if row.get("row_key") in selected_set
        ]
        if not rows:
            raise ValueError("No matching rows for the selected keys.")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        body = export_fc_cg_summary_multisite_xlsx(rows)
        return (
            body,
            f"FC_CG_Summary_MultiSite_{stamp}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def export_fc_cg_summary_bytes(
        self, *, group_id: str
    ) -> tuple[bytes, str, str]:
        result = self.contingency_fc_cg_summary(group_id)
        if not result.get("ok"):
            warnings = [str(w) for w in (result.get("warnings") or []) if w]
            raise LookupError("; ".join(warnings) or "FlashCopy CG summary failed.")
        card = result.get("card") or {}
        card_name = str(card.get("name") or "").strip() or "group"
        safe_card = re.sub(r"[^\w\-]+", "_", card_name).strip("_") or "group"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        body = export_fc_cg_summary_xlsx(list(result.get("summaries") or []))
        return (
            body,
            f"FC_CG_Summary_{safe_card}_{stamp}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def scan_host_volume_health_live(
        self, *, card_id: int | None = None
    ) -> dict[str, Any]:
        if not self.is_unlocked():
            raise RuntimeError(
                "LaunchPad must be unlocked to refresh Hosts & Volumes Health live."
            )
        self.sync_from_app()
        if self.is_unlocked():
            try:
                self.ensure_anderson_card_rename()
            except Exception:
                pass
        cards = self.list_cards(allow_sync=False)
        monitor = {
            c["id"]: self.is_monitor_enabled(int(c["id"]))
            for c in cards
            if c.get("id") is not None
        }
        hosts: list[dict[str, Any]] = []
        volumes: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        eligible_dicts = self._eligible_volume_find_card_dicts(
            cards, monitor, card_id=card_id
        )
        eligible_cards: list[HealthCard] = []
        for card_dict in eligible_dicts:
            card = self._cards.get(int(card_dict["id"]))
            if card is not None:
                eligible_cards.append(card)
        self._host_volume_health_progress.begin(len(eligible_cards))
        try:
            for card in eligible_cards:
                self._host_volume_health_progress.start_card(str(card.name or ""))
                profile = str(card.device_profile or "")
                vendor = vendor_for_profile(profile)
                card_host = str(card.host or "")
                try:
                    if vendor == "hpe":
                        host_output, vv_output = run_ssh_auth_hpe_commands(
                            card.host,
                            card.port,
                            card.username,
                            ["showhost", "showvv"],
                            password=card.password,
                            key_path=card.key_path,
                            key_passphrase=card.key_passphrase,
                        )
                        host_rows = parse_showhost_hosts(host_output or "")
                        vol_rows = parse_showvv_volumes(vv_output or "")
                    else:
                        run = self._lun_run_command(card)
                        host_rows = parse_fc_hosts(run("svcinfo lshost -delim :"))
                        vol_rows = parse_lsvdisk_volumes(run("svcinfo lsvdisk -delim :"))
                    hosts.extend(
                        filter_problem_hosts(
                            host_rows,
                            card_name=card.name,
                            host=card_host,
                            vendor=vendor,
                            card_id=card.card_id,
                        )
                    )
                    volumes.extend(
                        filter_problem_volumes(
                            vol_rows,
                            card_name=card.name,
                            host=card_host,
                            vendor=vendor,
                            card_id=card.card_id,
                        )
                    )
                except Exception as exc:
                    errors.append(
                        {
                            "card_id": card.card_id,
                            "card_name": card.name,
                            "error": str(exc),
                        }
                    )
                self._host_volume_health_progress.finish_card()
        finally:
            self._host_volume_health_progress.end()
        hosts.sort(
            key=lambda row: (
                str(row.get("card_name") or "").lower(),
                str(row.get("host_name") or "").lower(),
            )
        )
        volumes.sort(
            key=lambda row: (
                str(row.get("card_name") or "").lower(),
                str(row.get("volume_name") or "").lower(),
            )
        )
        payload = {"hosts": hosts, "volumes": volumes, "errors": errors}
        with self._lock:
            self._host_volume_health_cache = payload
        return payload

    def get_host_volume_health_cache(self) -> dict[str, Any] | None:
        with self._lock:
            if self._host_volume_health_cache is None:
                return None
            return {
                "hosts": list(self._host_volume_health_cache.get("hosts") or []),
                "volumes": list(self._host_volume_health_cache.get("volumes") or []),
                "errors": list(self._host_volume_health_cache.get("errors") or []),
            }

    def set_host_volume_health_cache(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._host_volume_health_cache = {
                "hosts": list(payload.get("hosts") or []),
                "volumes": list(payload.get("volumes") or []),
                "errors": list(payload.get("errors") or []),
            }

    def export_host_volume_health_bytes(
        self,
        *,
        export_format: str,
        card_id: int | None = None,
    ) -> tuple[bytes, str, str]:
        from launchpad.host_volume_health_export import (
            export_host_volume_health_csv_zip,
            export_host_volume_health_xlsx,
            filter_payload_by_card_id,
        )

        cached = self.get_host_volume_health_cache()
        if cached is None:
            raise LookupError("Refresh live before exporting.")
        card_name: str | None = None
        if card_id is not None:
            with self._lock:
                card = self._cards.get(int(card_id))
            if card is None:
                raise ValueError(f"Unknown card_id: {card_id}")
            card_name = card.name
        scoped = filter_payload_by_card_id(
            cached, card_id=card_id, card_name=card_name
        )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        if export_format == "xlsx":
            body = export_host_volume_health_xlsx(scoped)
            return (
                body,
                f"Host_Volume_Health_{stamp}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        body = export_host_volume_health_csv_zip(scoped)
        return body, f"Host_Volume_Health_{stamp}.zip", "application/zip"

    def export_site_lookup_bytes(
        self,
        *,
        export_format: str,
        include_offline: bool,
        payload: dict,
    ) -> tuple[bytes, str, str]:
        from launchpad.site_lookup_export import (
            export_site_lookup_csv_zip,
            export_site_lookup_xlsx,
        )

        fmt = str(export_format or "").strip().lower()
        if fmt not in {"xlsx", "csv"}:
            raise ValueError("Export format must be xlsx or csv.")
        if not isinstance(payload, dict) or not payload:
            raise ValueError("payload is required.")
        card = payload.get("card") if isinstance(payload.get("card"), dict) else {}
        site = str(card.get("name") or card.get("id") or "site").strip() or "site"
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in site)[:60]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        if fmt == "xlsx":
            body = export_site_lookup_xlsx(payload, include_offline=bool(include_offline))
            return (
                body,
                f"Site_Lookup_{safe}_{stamp}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        body = export_site_lookup_csv_zip(payload)
        return body, f"Site_Lookup_{safe}_{stamp}.zip", "application/zip"

    @staticmethod
    def _system_connectivity_svc_command(command: str) -> str:
        cmd = str(command or "").strip()
        if not cmd:
            return cmd
        if cmd.startswith("svcinfo ") or cmd.startswith("svctask "):
            return cmd
        # svqueryclock is a standalone binary, not an svcinfo subcommand.
        if cmd == "svqueryclock" or cmd.startswith("svqueryclock "):
            return cmd
        return f"svcinfo {cmd}"

    @staticmethod
    def _system_connectivity_na_row(
        identity: dict[str, Any], *, details: str
    ) -> dict[str, Any]:
        return finalize_row(
            dict(identity),
            configured="n/a",
            status="n/a",
            details=details,
        )

    @staticmethod
    def _system_connectivity_unknown_row(
        identity: dict[str, Any], *, error: str
    ) -> dict[str, Any]:
        return finalize_row(
            dict(identity),
            configured="unknown",
            status="error",
            error=error,
        )

    def _settings_view_for_scan(self):
        with self._lock:
            getter = self._get_setting
            setter = self._set_setting
        if getter is None:
            return None

        class _SettingsView:
            @staticmethod
            def get_setting(key: str, default: str = "") -> str:
                return getter(key, default)

            @staticmethod
            def set_setting(key: str, value: str) -> None:
                if setter is None:
                    raise RuntimeError("Settings backend is not writable.")
                setter(key, value)

        return _SettingsView()

    def _firmware_catalog_for_scan(self) -> dict[str, list[str]]:
        view = self._settings_view_for_scan()
        if view is None:
            return {}
        return load_firmware_catalog(view)

    def _enrich_scanned_firmware_row(
        self,
        identity: dict[str, Any],
        *,
        catalog: dict[str, list[str]],
        profile: str,
        configured: str,
        details: str,
        current: str,
        status: str = "",
        error: str = "",
    ) -> dict[str, Any]:
        return enrich_firmware_row(
            dict(identity),
            current=current,
            catalog=get_profile_catalog(catalog, profile),
            configured=configured,
            status="error" if error else status,
            details=details,
            error=error,
        )

    def _scan_system_connectivity_svc_card(
        self,
        card: HealthCard,
        identity: dict[str, Any],
        *,
        catalog: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        run = self._lun_run_command(card)
        commands = topic_commands_for_profile(card.device_profile or "")
        profile = str(card.device_profile or "")
        fw_catalog = catalog or {}
        parsers = {
            "call_home": parse_svc_call_home,
            "dns": parse_svc_dns,
            "snmp": parse_svc_snmp,
            "ntp": parse_svc_ntp_from_lssystem,
        }
        rows: dict[str, dict[str, Any]] = {}
        lssystem_output: str | None = None
        for topic in ("call_home", "dns", "snmp", "ntp"):
            topic_cmds = list(commands.get(topic) or [])
            if not topic_cmds:
                rows[topic] = self._system_connectivity_na_row(
                    identity,
                    details=f"{topic} not available for this profile",
                )
                continue
            try:
                cmd = self._system_connectivity_svc_command(topic_cmds[0])
                if "lssystem" in topic_cmds[0] and lssystem_output is not None:
                    output = lssystem_output
                else:
                    output = run(cmd) or ""
                    if "lssystem" in topic_cmds[0]:
                        lssystem_output = output
                configured, status, details = parsers[topic](output)
                rows[topic] = finalize_row(
                    dict(identity),
                    configured=configured,
                    status=status,
                    details=details,
                )
            except Exception as exc:
                rows[topic] = self._system_connectivity_unknown_row(
                    identity, error=str(exc)
                )

        try:
            topic_cmds = list(commands.get("firmware") or [])
            if not topic_cmds:
                configured, status, details, current = parse_svc_firmware_from_lssystem(
                    ""
                )
            else:
                cmd = self._system_connectivity_svc_command(topic_cmds[0])
                if "lssystem" in topic_cmds[0] and lssystem_output is not None:
                    output = lssystem_output
                else:
                    output = run(cmd) or ""
                configured, status, details, current = parse_svc_firmware_from_lssystem(
                    output
                )
            rows["firmware"] = self._enrich_scanned_firmware_row(
                identity,
                catalog=fw_catalog,
                profile=profile,
                configured=configured,
                status=status,
                details=details,
                current=current,
            )
        except Exception as exc:
            rows["firmware"] = self._enrich_scanned_firmware_row(
                identity,
                catalog=fw_catalog,
                profile=profile,
                configured="unknown",
                details="",
                current="",
                error=str(exc),
            )

        lk_configured = "unknown"
        lk_status = ""
        lk_details = ""
        lk_encryption = "unknown"
        lk_date = ""
        lk_time = ""
        lk_error = ""
        topic_cmds = list(commands.get("license_key") or [])
        try:
            enc_out = ""
            if topic_cmds:
                enc_cmd = self._system_connectivity_svc_command(topic_cmds[0])
                enc_out = run(enc_cmd) or ""
            lk_configured, lk_status, lk_details, lk_encryption = (
                parse_svc_lsencryption(enc_out)
            )
        except Exception as exc:
            lk_error = str(exc)
        if len(topic_cmds) > 1:
            try:
                clock_cmd = self._system_connectivity_svc_command(topic_cmds[1])
                clock_out = run(clock_cmd) or ""
                lk_date, lk_time = parse_svc_svqueryclock(clock_out)
            except Exception as exc:
                clock_note = f"svqueryclock failed: {exc}"
                lk_details = f"{lk_details}; {clock_note}".strip("; ")
                if not lk_error:
                    lk_error = clock_note
        rows["license_key"] = enrich_license_key_row(
            dict(identity),
            configured=lk_configured,
            status=lk_status,
            details=lk_details,
            encryption_licensed=lk_encryption,
            date=lk_date,
            time=lk_time,
            error=lk_error,
        )
        return rows

    def _scan_system_connectivity_hpe_card(
        self,
        card: HealthCard,
        identity: dict[str, Any],
        *,
        catalog: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        shownet_out, snmp_out, version_out, license_out = run_ssh_auth_hpe_commands(
            card.host,
            card.port,
            card.username,
            ["shownet", "showsnmpmgr", "showversion", "showlicense"],
            password=card.password,
            key_path=card.key_path,
            key_passphrase=card.key_passphrase,
        )
        ch_configured, ch_status, ch_details = hpe_call_home_na_row()
        net = parse_hpe_shownet_dns_ntp(shownet_out or "")
        snmp_configured, snmp_status, snmp_details = parse_hpe_snmpmgr(snmp_out or "")
        fw_configured, fw_status, fw_details, fw_current = (
            parse_hpe_showversion_firmware(version_out or "")
        )
        profile = str(card.device_profile or "")
        license_features = parse_hpe_showlicense(license_out or "")
        if license_features:
            license_rows = [
                enrich_license_key_row(
                    dict(identity),
                    configured="yes",
                    status=str(feat.get("status") or "ok"),
                    details=str(feat.get("details") or ""),
                    key_generation_date=str(feat.get("key_generation_date") or ""),
                    feature=str(feat.get("feature") or ""),
                    expiration=str(feat.get("expiration") or ""),
                )
                for feat in license_features
            ]
        else:
            license_rows = [
                enrich_license_key_row(
                    dict(identity),
                    configured="unknown",
                    status="",
                    details="empty showlicense output",
                )
            ]
        return {
            "call_home": finalize_row(
                dict(identity),
                configured=ch_configured,
                status=ch_status,
                details=ch_details,
            ),
            "dns": finalize_row(
                dict(identity),
                configured=net["dns"][0],
                status=net["dns"][1],
                details=net["dns"][2],
            ),
            "snmp": finalize_row(
                dict(identity),
                configured=snmp_configured,
                status=snmp_status,
                details=snmp_details,
            ),
            "ntp": finalize_row(
                dict(identity),
                configured=net["ntp"][0],
                status=net["ntp"][1],
                details=net["ntp"][2],
            ),
            "firmware": self._enrich_scanned_firmware_row(
                identity,
                catalog=catalog or {},
                profile=profile,
                configured=fw_configured,
                status=fw_status,
                details=fw_details,
                current=fw_current,
            ),
            "license_key": license_rows,
        }

    def _scan_system_connectivity_ds_card(
        self,
        card: HealthCard,
        identity: dict[str, Any],
        *,
        catalog: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        run = self._lun_run_command(card)
        commands = wrap_topic_commands_for_card(
            topic_commands_for_profile(card.device_profile or ""),
            dscli_path=getattr(card, "dscli_path", "") or "",
            dscli_hmc=getattr(card, "dscli_hmc", "") or "",
            username=str(card.username or ""),
            password=card.password or "",
        )
        profile = str(card.device_profile or "")
        fw_catalog = catalog or {}
        rows: dict[str, dict[str, Any]] = {}

        def _run_first(topic: str) -> str:
            topic_cmds = list(commands.get(topic) or [])
            if not topic_cmds:
                return ""
            return run(topic_cmds[0]) or ""

        try:
            call_home_out = _run_first("call_home")
            configured, status, details = parse_ds_showsp_call_home(call_home_out)
            rows["call_home"] = finalize_row(
                dict(identity),
                configured=configured,
                status=status,
                details=details,
            )
        except Exception as exc:
            rows["call_home"] = self._system_connectivity_unknown_row(
                identity, error=str(exc)
            )

        try:
            dns_out = _run_first("dns")
            configured, status, details = parse_ds_networkport_dns(dns_out)
            rows["dns"] = finalize_row(
                dict(identity),
                configured=configured,
                status=status,
                details=details,
            )
        except Exception as exc:
            rows["dns"] = self._system_connectivity_unknown_row(
                identity, error=str(exc)
            )

        rows["snmp"] = self._system_connectivity_na_row(
            identity,
            details="SNMP not available via DSCLI on this path",
        )
        rows["ntp"] = self._system_connectivity_na_row(
            identity,
            details="NTP not available via DSCLI on this path (often HMC)",
        )
        try:
            fw_out = _run_first("firmware")
            configured, status, details, current = parse_ds_firmware(fw_out)
            rows["firmware"] = self._enrich_scanned_firmware_row(
                identity,
                catalog=fw_catalog,
                profile=profile,
                configured=configured,
                status=status,
                details=details,
                current=current,
            )
        except Exception as exc:
            rows["firmware"] = self._enrich_scanned_firmware_row(
                identity,
                catalog=fw_catalog,
                profile=profile,
                configured="unknown",
                details="",
                current="",
                error=str(exc),
            )

        try:
            configured, status, details = parse_ds_license_key()
            rows["license_key"] = enrich_license_key_row(
                dict(identity),
                configured=configured,
                status=status,
                details=details,
            )
        except Exception as exc:
            rows["license_key"] = enrich_license_key_row(
                dict(identity),
                configured="unknown",
                status="error",
                details="",
                error=str(exc),
            )
        return rows

    def scan_system_connectivity_live(
        self, *, card_id: int | None = None
    ) -> dict[str, Any]:
        if not self.is_unlocked():
            raise RuntimeError(
                "LaunchPad must be unlocked to refresh System Connectivity live."
            )
        self.sync_from_app()
        if self.is_unlocked():
            try:
                self.ensure_anderson_card_rename()
            except Exception:
                pass
        cards = self.list_cards(allow_sync=False)
        monitor = {
            c["id"]: self.is_monitor_enabled(int(c["id"]))
            for c in cards
            if c.get("id") is not None
        }
        topic_rows: dict[str, list[dict[str, Any]]] = {topic: [] for topic in TOPICS}
        errors: list[dict[str, Any]] = []
        catalog = self._firmware_catalog_for_scan()
        for card_dict in cards:
            current_id = card_dict.get("id")
            if current_id is None:
                continue
            if card_id is not None and int(current_id) != int(card_id):
                continue
            monitor_on = bool(
                monitor.get(current_id, monitor.get(str(current_id), False))
            )
            if not is_system_connectivity_eligible(card_dict, monitor_on=monitor_on):
                continue
            card = self._cards.get(int(current_id))
            if card is None:
                continue
            profile = str(card.device_profile or "")
            vendor = system_connectivity_vendor(profile)
            identity = base_row(
                card_name=card.name,
                host=str(card.host or ""),
                vendor=vendor,
                profile=profile,
                card_id=card.card_id,
            )
            try:
                if profile in HPE_SHELL_PROFILES:
                    scanned = self._scan_system_connectivity_hpe_card(
                        card, identity, catalog=catalog
                    )
                elif profile.strip().lower() == "ibm_ds8884":
                    scanned = self._scan_system_connectivity_ds_card(
                        card, identity, catalog=catalog
                    )
                else:
                    scanned = self._scan_system_connectivity_svc_card(
                        card, identity, catalog=catalog
                    )
                for topic in TOPICS:
                    value = scanned[topic]
                    if topic == "license_key" and isinstance(value, list):
                        topic_rows[topic].extend(value)
                        for row in value:
                            if row.get("error"):
                                errors.append(
                                    {
                                        "card_id": card.card_id,
                                        "card_name": card.name,
                                        "topic": topic,
                                        "error": row["error"],
                                    }
                                )
                    else:
                        topic_rows[topic].append(value)
                        if value.get("error"):
                            errors.append(
                                {
                                    "card_id": card.card_id,
                                    "card_name": card.name,
                                    "topic": topic,
                                    "error": value["error"],
                                }
                            )
            except Exception as exc:
                err = str(exc)
                errors.append(
                    {
                        "card_id": card.card_id,
                        "card_name": card.name,
                        "error": err,
                    }
                )
                for topic in TOPICS:
                    if topic == "call_home" and profile in HPE_SHELL_PROFILES:
                        ch_configured, ch_status, ch_details = hpe_call_home_na_row()
                        topic_rows[topic].append(
                            finalize_row(
                                dict(identity),
                                configured=ch_configured,
                                status=ch_status,
                                details=ch_details,
                                error=err,
                            )
                        )
                    elif topic == "firmware":
                        topic_rows[topic].append(
                            self._enrich_scanned_firmware_row(
                                identity,
                                catalog=catalog,
                                profile=profile,
                                configured="unknown",
                                details="",
                                current="",
                                error=err,
                            )
                        )
                    elif topic == "license_key":
                        topic_rows[topic].append(
                            enrich_license_key_row(
                                dict(identity),
                                configured="unknown",
                                status="error",
                                details="",
                                error=err,
                            )
                        )
                    else:
                        topic_rows[topic].append(
                            self._system_connectivity_unknown_row(
                                identity, error=err
                            )
                        )
        catalog_updates = 0
        db_view = self._settings_view_for_scan()
        if db_view is not None and load_firmware_auto_add(db_view):
            currents: list[tuple[str, str]] = []
            for row in topic_rows["firmware"]:
                profile = str(row.get("profile") or "").strip()
                current = str(row.get("current") or "").strip()
                if profile and current:
                    currents.append((profile, current))
            if currents:
                updated, catalog_updates = grow_catalog_from_currents(
                    catalog, currents
                )
                if catalog_updates > 0:
                    save_firmware_catalog(db_view, updated)
                    catalog = updated
                    reenriched: list[dict[str, Any]] = []
                    for row in topic_rows["firmware"]:
                        profile = str(row.get("profile") or "")
                        error = str(row.get("error") or "")
                        identity = {
                            key: row[key]
                            for key in (
                                "site",
                                "card_name",
                                "host",
                                "vendor",
                                "profile",
                                "card_id",
                            )
                            if key in row
                        }
                        reenriched.append(
                            self._enrich_scanned_firmware_row(
                                identity,
                                catalog=catalog,
                                profile=profile,
                                configured=str(row.get("configured") or ""),
                                details=str(row.get("details") or ""),
                                current=str(row.get("current") or ""),
                                status="",
                                error=error,
                            )
                        )
                    topic_rows["firmware"] = reenriched

        for topic in TOPICS:
            if topic == "license_key":
                topic_rows[topic].sort(
                    key=lambda row: (
                        str(row.get("card_name") or "").lower(),
                        str(row.get("feature") or "").lower(),
                    )
                )
            else:
                topic_rows[topic].sort(
                    key=lambda row: (str(row.get("card_name") or "").lower(),)
                )
        payload: dict[str, Any] = {
            "call_home": topic_rows["call_home"],
            "dns": topic_rows["dns"],
            "snmp": topic_rows["snmp"],
            "ntp": topic_rows["ntp"],
            "firmware": topic_rows["firmware"],
            "license_key": topic_rows["license_key"],
            "errors": errors,
        }
        if catalog_updates > 0:
            payload["catalog_updates"] = catalog_updates
        with self._lock:
            self._system_connectivity_cache = payload
        return payload

    def get_system_connectivity_cache(self) -> dict[str, Any] | None:
        with self._lock:
            if self._system_connectivity_cache is None:
                return None
            return {
                "call_home": list(
                    self._system_connectivity_cache.get("call_home") or []
                ),
                "dns": list(self._system_connectivity_cache.get("dns") or []),
                "snmp": list(self._system_connectivity_cache.get("snmp") or []),
                "ntp": list(self._system_connectivity_cache.get("ntp") or []),
                "firmware": list(
                    self._system_connectivity_cache.get("firmware") or []
                ),
                "license_key": list(
                    self._system_connectivity_cache.get("license_key") or []
                ),
                "errors": list(self._system_connectivity_cache.get("errors") or []),
            }

    def set_system_connectivity_cache(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._system_connectivity_cache = {
                "call_home": list(payload.get("call_home") or []),
                "dns": list(payload.get("dns") or []),
                "snmp": list(payload.get("snmp") or []),
                "ntp": list(payload.get("ntp") or []),
                "firmware": list(payload.get("firmware") or []),
                "license_key": list(payload.get("license_key") or []),
                "errors": list(payload.get("errors") or []),
            }

    def export_system_connectivity_bytes(
        self,
        *,
        export_format: str,
        card_id: int | None = None,
    ) -> tuple[bytes, str, str]:
        from launchpad.system_connectivity_export import (
            export_system_connectivity_csv_zip,
            export_system_connectivity_xlsx,
            filter_payload_by_card_id,
        )

        cached = self.get_system_connectivity_cache()
        if cached is None:
            raise LookupError("Refresh live before exporting.")
        card_name: str | None = None
        if card_id is not None:
            with self._lock:
                card = self._cards.get(int(card_id))
            if card is None:
                raise ValueError(f"Unknown card_id: {card_id}")
            card_name = card.name
        scoped = filter_payload_by_card_id(
            cached, card_id=card_id, card_name=card_name
        )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        if export_format == "xlsx":
            body = export_system_connectivity_xlsx(scoped)
            return (
                body,
                f"System_Connectivity_{stamp}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        body = export_system_connectivity_csv_zip(scoped)
        return body, f"System_Connectivity_{stamp}.zip", "application/zip"

    @staticmethod
    def _storage_inventory_health_issues(card: HealthCard) -> list:
        if not card.command_results:
            return []
        try:
            analysis = analyze_health(card.name, card.command_results, card.metrics)
        except Exception:
            return []
        return list(analysis.get("health_issues") or [])

    def _scan_storage_inventory_svc_card(
        self, card: HealthCard, commands: dict[str, list[str]]
    ) -> tuple[str, str, tuple, tuple, tuple, tuple, tuple, list[str], tuple]:
        run = self._lun_run_command(card)
        lssystem_output: str | None = None
        extra_errors: list[str] = []
        unknown = ("unknown", "", "")

        def _run_first(topic: str) -> str:
            nonlocal lssystem_output
            topic_cmds = list(commands.get(topic) or [])
            if not topic_cmds:
                return ""
            cmd = self._system_connectivity_svc_command(topic_cmds[0])
            if "lssystem" in topic_cmds[0] and lssystem_output is not None:
                return lssystem_output
            output = run(cmd) or ""
            if "lssystem" in topic_cmds[0]:
                lssystem_output = output
            return output

        try:
            model, serial = parse_svc_lssystem_identity(_run_first("identity"))
        except Exception as exc:
            model, serial = "", ""
            extra_errors.append(f"identity scan failed: {exc}")

        try:
            volume_protection = parse_svc_lssystem_volume_protection(_run_first("identity"))
        except Exception as exc:
            volume_protection = unknown
            extra_errors.append(f"volume protection scan failed: {exc}")

        try:
            ntp = parse_svc_ntp_from_lssystem(_run_first("ntp"))
        except Exception as exc:
            ntp = unknown
            extra_errors.append(f"ntp scan failed: {exc}")

        try:
            phone = parse_svc_call_home(_run_first("call_home"))
        except Exception as exc:
            phone = unknown
            extra_errors.append(f"call home scan failed: {exc}")

        try:
            dns = parse_svc_dns(_run_first("dns"))
        except Exception as exc:
            dns = unknown
            extra_errors.append(f"dns scan failed: {exc}")

        try:
            smtp = parse_svc_lsemailserver(_run_first("smtp"))
        except Exception as exc:
            smtp = unknown
            extra_errors.append(f"smtp scan failed: {exc}")

        try:
            dp_cfg, dp_status, _dp_details = parse_svc_lsrcrelationship(
                _run_first("data_protection")
            )
            data_protection = (dp_cfg, dp_status, "")
        except Exception as exc:
            data_protection = unknown
            extra_errors.append(f"data protection scan failed: {exc}")

        return model, serial, phone, data_protection, smtp, dns, ntp, extra_errors, volume_protection

    def _scan_storage_inventory_hpe_card(
        self, card: HealthCard, commands: dict[str, list[str]]
    ) -> tuple[str, str, tuple, tuple, tuple, tuple, tuple, list[str], tuple]:
        identity_cmds = list(commands.get("identity") or [])
        dp_cmds = list(commands.get("data_protection") or [])
        identity_cmd = identity_cmds[0] if identity_cmds else "showsys"
        dp_cmd = dp_cmds[0] if dp_cmds else "showrcopy"
        identity_out, shownet_out, rcopy_out = run_ssh_auth_hpe_commands(
            card.host,
            card.port,
            card.username,
            [identity_cmd, "shownet", dp_cmd],
            password=card.password,
            key_path=card.key_path,
            key_passphrase=card.key_passphrase,
        )
        model, serial = self._parse_hpe_showsys_identity(identity_out or "")
        net = parse_hpe_shownet_dns_ntp(shownet_out or "")
        phone = hpe_call_home_na_row()
        smtp = ("n/a", "", "smtp not available for this profile")
        dp_cfg, dp_status, _dp_details = parse_hpe_showrcopy_protection(rcopy_out or "")
        data_protection = (dp_cfg, dp_status, "")
        volume_protection = ("n/a", "", "volume protection not available for this profile")
        return (
            model,
            serial,
            phone,
            data_protection,
            smtp,
            net["dns"],
            net["ntp"],
            [],
            volume_protection,
        )

    @staticmethod
    def _parse_hpe_showsys_identity(output: str) -> tuple[str, str]:
        text = str(output or "")
        model = ""
        serial = ""
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            key, _, value = stripped.partition(":")
            token = key.strip().lower()
            val = value.strip()
            if not val:
                continue
            if "serial" in token and not serial:
                serial = val
            elif "model" in token and not model:
                model = val
        return model, serial

    def _scan_storage_inventory_ds_card(
        self, card: HealthCard, commands: dict[str, list[str]]
    ) -> tuple[str, str, tuple, tuple, tuple, tuple, tuple, list[str], tuple]:
        run = self._lun_run_command(card)
        extra_errors: list[str] = []
        unknown = ("unknown", "", "")

        def _run_first(topic: str) -> str:
            topic_cmds = list(commands.get(topic) or [])
            if not topic_cmds:
                return ""
            return run(topic_cmds[0]) or ""

        try:
            phone = parse_ds_showsp_call_home(_run_first("call_home"))
        except Exception as exc:
            phone = unknown
            extra_errors.append(f"call home scan failed: {exc}")

        try:
            dns = parse_ds_networkport_dns(_run_first("dns"))
        except Exception as exc:
            dns = unknown
            extra_errors.append(f"dns scan failed: {exc}")

        smtp = ("n/a", "", "smtp not available for this profile")
        data_protection = ("n/a", "", "data protection not available for this profile")
        ntp = ("n/a", "", "ntp not available via DSCLI on this path (often HMC)")
        volume_protection = ("n/a", "", "volume protection not available for this profile")
        return "", "", phone, data_protection, smtp, dns, ntp, extra_errors, volume_protection

    def _scan_storage_inventory_card(self, card: HealthCard) -> dict[str, Any]:
        profile = str(card.device_profile or "")
        vendor = system_connectivity_vendor(profile)
        commands = inventory_commands_for_profile(profile)
        health_issues = self._storage_inventory_health_issues(card)
        alert_state = getattr(self, "_storage_inventory_alert_state", None)
        if alert_state is None:
            alert_state = self._load_health_alert_state()
        now = getattr(self, "_storage_inventory_now", None)
        if now is None:
            now = time.time()

        if is_hpe_inventory_profile(profile):
            model, serial, phone, dp, smtp, dns, ntp, extra_errors, volume_protection = (
                self._scan_storage_inventory_hpe_card(card, commands)
            )
        elif profile.strip().lower() == "ibm_ds8884" or profile.strip().lower().startswith(
            "ibm_ds"
        ):
            commands = wrap_inventory_commands_for_card(
                commands,
                dscli_path=getattr(card, "dscli_path", "") or "",
                dscli_hmc=getattr(card, "dscli_hmc", "") or "",
                username=str(card.username or ""),
                password=card.password or "",
            )
            model, serial, phone, dp, smtp, dns, ntp, extra_errors, volume_protection = (
                self._scan_storage_inventory_ds_card(card, commands)
            )
        else:
            model, serial, phone, dp, smtp, dns, ntp, extra_errors, volume_protection = (
                self._scan_storage_inventory_svc_card(card, commands)
            )

        card_serial = str(card.serial_number or "").strip()
        if card_serial:
            serial = card_serial
        if not model:
            model = DEVICE_PROFILES.get(profile, profile)

        return build_inventory_row(
            site=card.name,
            host=card.name,
            ip=str(card.host or ""),
            model=model,
            serial=serial,
            location=card.name,
            vendor=vendor,
            profile=profile,
            card_id=card.card_id,
            phone=phone,
            data_protection=dp,
            smtp=smtp,
            dns=dns,
            ntp=ntp,
            health_issues=health_issues,
            extra_errors=extra_errors,
            alert_state=alert_state,
            now=now,
            volume_protection=volume_protection,
        )

    def host_volume_health_progress_snapshot(self) -> dict:
        return self._host_volume_health_progress.snapshot()

    def volume_find_progress_snapshot(self) -> dict:
        return self._volume_find_progress.snapshot()

    def _eligible_volume_find_card_dicts(
        self,
        cards: list[dict[str, Any]],
        monitor: dict,
        *,
        card_id: int | None = None,
    ) -> list[dict[str, Any]]:
        eligible: list[dict[str, Any]] = []
        for card_dict in cards:
            current_id = card_dict.get("id")
            if current_id is None:
                continue
            if card_id is not None and int(current_id) != int(card_id):
                continue
            monitor_on = bool(
                monitor.get(current_id, monitor.get(str(current_id), False))
            )
            if not is_volume_find_eligible(card_dict, monitor_on=monitor_on):
                continue
            eligible.append(card_dict)
        return eligible

    def storage_inventory_progress_snapshot(self) -> dict:
        return self._storage_inventory_progress.snapshot()

    def scan_storage_inventory_live(self, *, card_id: int | None = None) -> dict[str, Any]:
        if not self.is_unlocked():
            raise RuntimeError(
                "LaunchPad must be unlocked to refresh Storage Inventory live."
            )
        self.sync_from_app()
        if self.is_unlocked():
            try:
                self.ensure_anderson_card_rename()
            except Exception:
                pass
        cards = self.list_cards(allow_sync=False)
        rows: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        eligible: list[HealthCard] = []
        for card_dict in cards:
            current_id = card_dict.get("id")
            if current_id is None:
                continue
            if card_id is not None and int(current_id) != int(card_id):
                continue
            if not is_storage_inventory_eligible(card_dict):
                continue
            card = self._cards.get(int(current_id))
            if card is None:
                continue
            eligible.append(card)
        alert_state = self._load_health_alert_state()
        now = time.time()
        self._storage_inventory_alert_state = alert_state
        self._storage_inventory_now = now
        self._storage_inventory_progress.begin(len(eligible))
        try:
            for card in eligible:
                self._storage_inventory_progress.start_card(str(card.name or ""))
                try:
                    row = self._scan_storage_inventory_card(card)
                except Exception as exc:
                    err = str(exc)
                    errors.append(
                        {"card_id": card.card_id, "card_name": card.name, "error": err}
                    )
                    unknown = ("unknown", "", "")
                    profile = str(card.device_profile or "")
                    if is_hpe_inventory_profile(profile) or profile.strip().lower() == "ibm_ds8884" or profile.strip().lower().startswith("ibm_ds"):
                        volume_protection = (
                            "n/a",
                            "",
                            "volume protection not available for this profile",
                        )
                    else:
                        volume_protection = unknown
                    row = build_inventory_row(
                        site=card.name,
                        host=card.name,
                        ip=str(card.host or ""),
                        model=DEVICE_PROFILES.get(
                            str(card.device_profile or ""), str(card.device_profile or "")
                        ),
                        serial=str(card.serial_number or ""),
                        location=card.name,
                        vendor=system_connectivity_vendor(str(card.device_profile or "")),
                        profile=str(card.device_profile or ""),
                        card_id=card.card_id,
                        phone=unknown,
                        data_protection=unknown,
                        smtp=unknown,
                        dns=unknown,
                        ntp=unknown,
                        health_issues=self._storage_inventory_health_issues(card),
                        extra_errors=[err],
                        alert_state=alert_state,
                        now=now,
                        volume_protection=volume_protection,
                    )
                rows.append(row)
                self._storage_inventory_progress.finish_card()
        finally:
            self._storage_inventory_progress.end()

        rows.sort(key=lambda row: str(row.get("site") or "").lower())
        totals = inventory_totals(rows)
        payload: dict[str, Any] = {
            "rows": rows,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "errors": errors,
            "total_devices": totals["total_devices"],
            "devices_with_issues": totals["devices_with_issues"],
        }
        with self._lock:
            self._storage_inventory_cache = payload
        return payload

    def get_storage_inventory_cache(self) -> dict[str, Any] | None:
        with self._lock:
            if self._storage_inventory_cache is None:
                return None
            return {
                "rows": list(self._storage_inventory_cache.get("rows") or []),
                "generated_at": str(
                    self._storage_inventory_cache.get("generated_at") or ""
                ),
                "errors": list(self._storage_inventory_cache.get("errors") or []),
                "total_devices": int(
                    self._storage_inventory_cache.get("total_devices") or 0
                ),
                "devices_with_issues": int(
                    self._storage_inventory_cache.get("devices_with_issues") or 0
                ),
            }

    def set_storage_inventory_cache(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._storage_inventory_cache = {
                "rows": list(payload.get("rows") or []),
                "generated_at": str(payload.get("generated_at") or ""),
                "errors": list(payload.get("errors") or []),
                "total_devices": int(payload.get("total_devices") or 0),
                "devices_with_issues": int(payload.get("devices_with_issues") or 0),
            }

    def export_storage_inventory_bytes(self) -> tuple[bytes, str, str]:
        cached = self.get_storage_inventory_cache()
        if cached is None or not cached.get("rows"):
            raise LookupError("Refresh live before exporting.")
        body = export_storage_inventory_xlsx(
            cached["rows"], generated_at=cached.get("generated_at")
        )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        return (
            body,
            f"LaunchPad_Storage_Inventory_{stamp}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def find_volumes(
        self, query: str, *, mode: str = "cache", find_type: str = "volume"
    ) -> dict[str, Any]:
        q = str(query or "").strip()
        if not q:
            return {"matches": [], "errors": []}
        type_key = str(find_type or "volume").strip().lower()
        if type_key not in {"volume", "host"}:
            raise ValueError("type must be volume or host")
        mode_key = str(mode or "cache").strip().lower()
        if mode_key not in {"cache", "live"}:
            raise ValueError("mode must be cache or live")
        self.sync_from_app()
        if self.is_unlocked():
            try:
                self.ensure_anderson_card_rename()
            except Exception:
                pass
        cards = self.list_cards(allow_sync=False)
        monitor = {
            c["id"]: self.is_monitor_enabled(int(c["id"]))
            for c in cards
            if c.get("id") is not None
        }
        if type_key == "host":
            if mode_key == "live" and not self.is_unlocked():
                raise RuntimeError("LaunchPad must be unlocked to search hosts live.")
            eligible = self._eligible_volume_find_card_dicts(cards, monitor)
            self._volume_find_progress.begin(len(eligible))
            try:
                if mode_key == "cache":
                    matches: list[dict[str, Any]] = []
                    for card_dict in eligible:
                        self._volume_find_progress.start_card(
                            str(card_dict.get("name") or "")
                        )
                        matches.extend(
                            find_hosts_in_cards(
                                [card_dict],
                                q,
                                monitor_enabled=monitor,
                                source="cache",
                            )
                        )
                        self._volume_find_progress.finish_card()
                    matches.sort(
                        key=lambda m: (
                            str(m.get("card_name") or "").lower(),
                            str(m.get("host_name") or "").lower(),
                        )
                    )
                    return {"matches": matches, "errors": []}
                matches = []
                errors: list[dict[str, Any]] = []
                for card_dict in eligible:
                    self._volume_find_progress.start_card(
                        str(card_dict.get("name") or "")
                    )
                    card = self._cards.get(int(card_dict["id"]))
                    if card is None:
                        self._volume_find_progress.finish_card()
                        continue
                    profile = str(card.device_profile or "")
                    try:
                        if vendor_for_profile(profile) == "hpe":
                            outputs = run_ssh_auth_hpe_commands(
                                card.host,
                                card.port,
                                card.username,
                                ["showhost"],
                                password=card.password,
                                key_path=card.key_path,
                                key_passphrase=card.key_passphrase,
                            )
                            output = outputs[0] if outputs else ""
                            host_rows = parse_showhost_hosts(output)
                        else:
                            run = self._lun_run_command(card)
                            output = run("svcinfo lshost -delim :")
                            host_rows = parse_fc_hosts(output)
                        for host_row in host_rows:
                            host_name = host_row.get("host_name") or ""
                            if not host_name_matches(host_name, q):
                                continue
                            matches.append(
                                {
                                    "card_id": card.card_id,
                                    "card_name": card.name,
                                    "profile": profile,
                                    "vendor": vendor_for_profile(profile),
                                    "host_name": host_name,
                                    "wwpns": host_row.get("wwpns") or "",
                                    "source": "live",
                                    "host": str(card.host or ""),
                                }
                            )
                    except Exception as exc:
                        errors.append(
                            {
                                "card_id": card.card_id,
                                "card_name": card.name,
                                "error": str(exc),
                            }
                        )
                    self._volume_find_progress.finish_card()
                matches.sort(
                    key=lambda m: (
                        str(m.get("card_name") or "").lower(),
                        str(m.get("host_name") or "").lower(),
                    )
                )
                return {"matches": matches, "errors": errors}
            finally:
                self._volume_find_progress.end()
        if mode_key == "live" and not self.is_unlocked():
            raise RuntimeError("LaunchPad must be unlocked to search volumes live.")
        eligible = self._eligible_volume_find_card_dicts(cards, monitor)
        self._volume_find_progress.begin(len(eligible))
        try:
            if mode_key == "cache":
                matches = []
                for card_dict in eligible:
                    self._volume_find_progress.start_card(
                        str(card_dict.get("name") or "")
                    )
                    matches.extend(
                        find_volumes_in_cards(
                            [card_dict],
                            q,
                            monitor_enabled=monitor,
                            source="cache",
                        )
                    )
                    self._volume_find_progress.finish_card()
                matches.sort(
                    key=lambda m: (
                        str(m.get("card_name") or "").lower(),
                        str(m.get("volume") or "").lower(),
                    )
                )
                return {"matches": matches, "errors": []}
            matches = []
            errors = []
            for card_dict in eligible:
                self._volume_find_progress.start_card(
                    str(card_dict.get("name") or "")
                )
                card = self._cards.get(int(card_dict["id"]))
                if card is None:
                    self._volume_find_progress.finish_card()
                    continue
                profile = str(card.device_profile or "")
                try:
                    if vendor_for_profile(profile) == "hpe":
                        outputs = run_ssh_auth_hpe_commands(
                            card.host,
                            card.port,
                            card.username,
                            ["showvv"],
                            password=card.password,
                            key_path=card.key_path,
                            key_passphrase=card.key_passphrase,
                        )
                        output = outputs[0] if outputs else ""
                        vols = parse_showvv_volumes(output)
                    else:
                        run = self._lun_run_command(card)
                        output = run("svcinfo lsvdisk -delim :")
                        vols = [
                            {
                                "name": r["name"],
                                "pool_or_cpg": r.get("pool") or "",
                            }
                            for r in parse_lsvdisk_volumes(output)
                        ]
                    for vol in vols:
                        if volume_name_matches(vol["name"], q):
                            matches.append(
                                {
                                    "card_id": card.card_id,
                                    "card_name": card.name,
                                    "profile": profile,
                                    "vendor": vendor_for_profile(profile),
                                    "volume": vol["name"],
                                    "pool_or_cpg": vol.get("pool_or_cpg") or "",
                                    "source": "live",
                                    "host": str(card.host or ""),
                                }
                            )
                except Exception as exc:
                    errors.append(
                        {
                            "card_id": card.card_id,
                            "card_name": card.name,
                            "error": str(exc),
                        }
                    )
                self._volume_find_progress.finish_card()
            matches.sort(
                key=lambda m: (
                    str(m.get("card_name") or "").lower(),
                    str(m.get("volume") or "").lower(),
                )
            )
            return {"matches": matches, "errors": errors}
        finally:
            self._volume_find_progress.end()

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

    @property
    def lun_builder_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{LUN_BUILDER_PATH}"

    @property
    def volume_find_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{VOLUME_FIND_PATH}"

    @property
    def fc_consistgrp_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{FC_CONSISTGRP_PATH}"

    @property
    def esx_snap_policy_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{ESX_SNAP_POLICY_PATH}"

    @property
    def host_volume_health_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{HOST_VOLUME_HEALTH_PATH}"

    @property
    def snapcopy_summary_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{SNAPCOPY_SUMMARY_PATH}"

    @property
    def system_connectivity_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{SYSTEM_CONNECTIVITY_PATH}"

    @property
    def storage_inventory_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{STORAGE_INVENTORY_PATH}"

    @property
    def site_lookup_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{SITE_LOOKUP_PATH}"

    @property
    def ansible_pad_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{ANSIBLE_PAD_PATH}"

    @property
    def host_power_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{HOST_POWER_PATH}"

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
        url: str = "",
        sudo_password: str = "",
        dscli_path: str = "",
        dscli_hmc: str = "",
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
                sudo_password=sudo_password if device_profile == "hadoop_linux" else "",
                device_profile=device_profile,
                custom_commands=custom_commands,
                serial_number=serial_number,
                dscli_path=dscli_path,
                dscli_hmc=dscli_hmc,
                category=category,
                url=url,
                metrics=existing.metrics if existing else None,
                command_results=existing.command_results if existing else None,
                error=existing.error if existing else None,
                updated_at=existing.updated_at if existing else None,
            )

    def refresh_card(
        self,
        card_id: int,
        *,
        focus: str = "",
        include_pools: bool = True,
    ) -> HealthCard:
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
            sudo_password = card.sudo_password
            device_profile = card.device_profile
            custom_commands = card.custom_commands
            serial_number = card.serial_number
            dscli_path = card.dscli_path
            dscli_hmc = card.dscli_hmc
            prior_results = list(card.command_results or [])

        from launchpad.command_format import (
            drop_pool_capacity_results,
            filter_capacity_focus_commands,
        )

        commands = resolve_card_commands(
            device_profile,
            custom_commands,
            instance_id=serial_number,
            dscli_path=dscli_path or "",
            dscli_hmc=dscli_hmc or "",
            username=str(username or ""),
            password=password or "",
        )
        if (focus or "").strip().lower() == "capacity":
            commands = filter_capacity_focus_commands(
                commands,
                include_pools=include_pools,
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
                sudo_password=sudo_password if device_profile == "hadoop_linux" else "",
            )
            if (focus or "").strip().lower() == "capacity" and prior_results:
                # Preserve non-capacity health outputs from the last full refresh.
                by_key = {
                    f"{item.get('label')}|{item.get('command')}": item
                    for item in prior_results
                }
                for item in command_results:
                    by_key[f"{item.get('label')}|{item.get('command')}"] = item
                command_results = list(by_key.values())
                if not include_pools:
                    command_results = drop_pool_capacity_results(command_results)
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
        self.upsert_lun_offline_inventory_from_card(card)
        if (focus or "").strip().lower() == "capacity" and error is None:
            self._capture_dell_snapshot_best_effort(card)
        return card

    def refresh_site_lookup(self, card_id: int) -> dict:
        cid = int(card_id)
        with self._lock:
            if cid not in self._cards:
                raise KeyError(cid)

        try:
            card = self.refresh_card(cid)
        except KeyError:
            raise
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc

        results = list(card.command_results or [])
        has_successful_command = any(not item.get("error") for item in results)
        if card.error and not card.metrics and not has_successful_command:
            raise RuntimeError(card.error)

        try:
            meta = card.to_api()
            hosts = shape_hosts_for_lookup(list(meta.get("fc_hosts") or []))
            maps = list(meta.get("fc_mappings") or [])
            pools = list(meta.get("pools") or []) or pool_capacity_from_commands(results)

            parsed_hosts, parsed_volumes, parsed_maps = inventory_from_command_results(
                results,
                device_profile=str(card.device_profile or ""),
            )
            if not hosts and parsed_hosts:
                hosts = parsed_hosts
            if not maps and parsed_maps:
                maps = parsed_maps
            volumes = list(parsed_volumes)

            # HPE: always fetch showhost/showvv for Site Lookup (health suite may
            # run showvv after checkhealth and return polluted/unparseable output).
            profile = str(card.device_profile or "")
            hpe_warning: str | None = None
            if profile in HPE_SHELL_PROFILES:
                try:
                    host_output, pathsum_output, vv_output = run_ssh_auth_hpe_commands(
                        card.host,
                        card.port,
                        card.username,
                        ["showhost", "showhost -pathsum", "showvv"],
                        password=card.password,
                        key_path=card.key_path,
                        key_passphrase=card.key_passphrase,
                    )
                    fetched_hosts = shape_hosts_for_lookup(
                        parse_showhost_hosts(host_output or "")
                    )
                    if fetched_hosts:
                        apply_pathsum_status_to_hosts(
                            fetched_hosts,
                            parse_showhost_pathsum_status(pathsum_output or ""),
                        )
                        hosts = fetched_hosts
                    volumes = shape_volumes_for_lookup(
                        parse_showvv_volumes(vv_output or "")
                    )
                    if not volumes:
                        hpe_warning = showvv_inventory_note(
                            results, raw_showvv=vv_output or ""
                        )
                except Exception as exc:
                    hpe_warning = f"Volumes empty because showvv fetch failed: {exc}"
                    if not hosts and parsed_hosts:
                        hosts = parsed_hosts

            if not volumes:
                for item in results:
                    command = str(item.get("command") or "")
                    if (
                        "lsvdisk" in command
                        and "lshostvdiskmap" not in command
                        and "lsvdiskhostmap" not in command
                    ):
                        volumes = shape_volumes_for_lookup(
                            parse_lsvdisk_volumes(str(item.get("output") or ""))
                        )
                        break

            consist_groups: list[dict] = []
            if card.device_profile in SVC_PROFILES:
                try:
                    output = self._lun_run_command(card)(
                        "svcinfo lsconsistgrp -delim :"
                    )
                    consist_groups = parse_lsconsistgrp(output)
                except Exception:
                    consist_groups = []

            if (
                profile in HPE_SHELL_PROFILES
                and not volumes
                and not hpe_warning
            ):
                hpe_warning = showvv_inventory_note(results)

            payload = payload_from_live(
                card=meta,
                hosts=hosts,
                volumes=volumes,
                maps=maps,
                consist_groups=consist_groups,
                pools=pools,
                contingency_groups=self.get_contingency_groups(),
                refreshed_at=datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                warning=hpe_warning,
            )
            self._persist_site_lookup_offline(payload)
            return payload
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc

    def site_lookup_cache(self, card_id: int) -> dict:
        cid = int(card_id)
        with self._lock:
            card = self._cards.get(cid)
            if card is None:
                raise KeyError(cid)
            meta = card.to_api()
            command_results = list(card.command_results or [])
        memory = payload_from_card_cache(
            meta,
            contingency_groups=self.get_contingency_groups(),
            command_results=command_results,
        )
        if payload_has_inventory(memory):
            return memory

        offline_store = self.get_site_lookup_offline_inventory()
        offline = offline_store.get(str(cid))
        if offline:
            return payload_from_offline_snapshot(offline)

        lun_store = self.get_lun_offline_inventory()
        lun_snap = lun_store.get(str(cid))
        if isinstance(lun_snap, dict) and (
            (isinstance(lun_snap.get("hosts"), list) and lun_snap.get("hosts"))
            or (isinstance(lun_snap.get("volumes"), list) and lun_snap.get("volumes"))
        ):
            return payload_from_lun_offline(lun_snap, card=meta)

        return memory

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
            should_upsert = command_results is not None
            target = card
        if should_upsert:
            self.upsert_lun_offline_inventory_from_card(target)
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
                        "card_type": "ssh",
                        "host": card.host,
                        "port": card.port,
                        "username": card.username,
                        "device_profile": card.device_profile,
                        "pool_family": capacity_pool_family(
                            card.device_profile, site_name=card.name
                        ),
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
        return self._decorate_cards_with_issue_limit(results)

    def _decorate_cards_with_issue_limit(
        self, results: list[dict[str, Any]], *, now: float | None = None
    ) -> list[dict[str, Any]]:
        if now is None:
            now = time.time()
        state = self._load_health_alert_state()
        prepared = prepare_health_issue_limit(state, results, now=now)
        if dump_state(prepared) != dump_state(state):
            try:
                self._save_health_alert_state(prepared)
            except RuntimeError:
                pass
        annotated: list[dict[str, Any]] = []
        for payload in results:
            item = dict(payload)
            item["visible_health_issues"] = visible_health_issues(
                item.get("health_issues") or [],
                item.get("id"),
                prepared,
                now=now,
            )
            annotated.append(item)
        return annotated

    def export_health_excel_bytes(
        self,
        *,
        card_id: int | None = None,
        card_ids: list[int] | None = None,
        sections: HealthExcelSections | None = None,
    ) -> tuple[bytes, str]:
        if sections is None:
            sections = HealthExcelSections(
                summary=True,
                issues=False,
                command_summaries=False,
                raw=False,
            )
        if card_ids:
            detail_card_ids: list[int] | None = [int(value) for value in card_ids]
        elif card_id is not None:
            detail_card_ids = [int(card_id)]
        else:
            detail_card_ids = None

        cards = self.list_cards(allow_sync=False)
        monitor_enabled = {
            int(card["id"]): self.is_monitor_enabled(int(card["id"]))
            for card in cards
            if card.get("id") is not None
        }
        body = build_health_workbook(
            cards,
            monitor_enabled=monitor_enabled,
            sections=sections,
            detail_card_ids=detail_card_ids,
        )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        filename = f"Health_Summary_{stamp}.xlsx"
        return body, filename

    def export_capacity_excel_bytes(
        self,
        *,
        include_monitor_off: bool = False,
        card_id: int | None = None,
        include_pools: bool = True,
        show_raw: bool = False,
    ) -> tuple[bytes, str]:
        """Build the browser-facing Storage Capacity workbook from registered cards.

        Returns (xlsx_bytes, filename). Refresh failures are captured per-card
        as an `ExportSite.error` string instead of aborting the whole export.
        """
        # Inline import: capacity_export -> monitor -> health_server is a
        # circular dependency, so this module can't import capacity_export
        # at top level.
        from launchpad.capacity_export import (
            ExportSite,
            card_ids_included_for_export,
            export_storage_capacity_excel_from_sites,
            filter_capacity_entries_by_card_id,
        )

        with self._lock:
            card_ids = sorted(self._cards.keys())
        monitor_enabled = {
            cid: self.is_monitor_enabled(cid) for cid in card_ids
        }
        included = card_ids_included_for_export(
            card_ids,
            include_monitor_off=include_monitor_off,
            monitor_enabled=monitor_enabled,
        )
        included = filter_capacity_entries_by_card_id(included, card_id=card_id)
        included_ids = sorted(included)

        sites: list[ExportSite] = []
        for site_id in included_ids:
            with self._lock:
                card = self._cards.get(site_id)
            if card is None:
                continue
            try:
                # Capacity-only suite — full health refresh on every monitored site
                # made Export Excel hang the Capacity Report UI for minutes.
                card = self.refresh_card(
                    site_id, focus="capacity", include_pools=include_pools
                )
                error = card.error
            except Exception as exc:
                error = str(exc)
            analysis = analyze_health(card.name, card.command_results, card.metrics)
            pools = pool_capacity_from_commands(card.command_results)
            sites.append(
                ExportSite(
                    card_id=site_id,
                    name=card.name,
                    host=card.host,
                    serial_number=card.serial_number,
                    category=card.category,
                    device_profile=card.device_profile,
                    capacity_summary=analysis.get("capacity_summary"),
                    pools=pools,
                    error=error,
                    raw_capacity_summary=analysis.get("raw_capacity_summary"),
                )
            )

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        filename = f"Storage_Capacity_Report_{stamp}.xlsx"
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / filename
            export_storage_capacity_excel_from_sites(
                sites,
                tmp_path,
                include_monitor_off=include_monitor_off,
                monitor_enabled=monitor_enabled,
                include_pools=include_pools,
                show_raw=show_raw,
            )
            body = tmp_path.read_bytes()
        return body, filename

    def _capture_dell_snapshot_best_effort(self, card: HealthCard) -> None:
        try:
            from launchpad.dell_report_export import maybe_upsert_dell_snapshot_for_card
            from launchpad.dell_report_snapshots import (
                load_dell_snapshots,
                save_dell_snapshots,
            )

            store = load_dell_snapshots()
            updated = maybe_upsert_dell_snapshot_for_card(card, snapshot_store=store)
            if updated is not store:
                save_dell_snapshots(updated)
        except Exception as exc:
            _log(f"Dell Report snapshot capture failed (ignored): {exc}")

    def export_dell_report_excel_bytes(
        self,
        *,
        include_monitor_off: bool = False,
        card_id: int | None = None,
        include_pools: bool = True,
    ) -> tuple[bytes, str]:
        """Build the Dell Managed Services capacity workbook from registered cards.

        Always exports monitored-on cards only (`include_monitor_off` is ignored).
        Refreshes IBM/HPE cards only; raises DellReportEmptyError when no rows.
        """
        # Inline: capacity_export / dell_report_export pull monitor→health_server.
        from launchpad.capacity_export import (
            ExportSite,
            card_ids_included_for_export,
            filter_capacity_entries_by_card_id,
        )
        from launchpad.dell_report_export import (
            build_dell_report_workbook,
            collect_dell_report_rows,
            ensure_dell_report_has_rows,
            workbook_to_bytes,
        )
        from launchpad.dell_report_snapshots import (
            load_dell_snapshots,
            save_dell_snapshots,
        )

        # Spec: monitored-on by default; include_off from Capacity Report; include_card_ids always eligible.
        # (Do not force include_monitor_off=False — callers pass the page toggle.)

        from launchpad.dell_report_settings import (
            load_dell_report_settings,
            normalize_dell_report_settings,
        )

        settings_view = self._settings_view_for_scan()
        if settings_view is not None:
            dell_settings = load_dell_report_settings(settings_view)
        else:
            dell_settings = normalize_dell_report_settings({})
        overrides = dell_settings.get("card_overrides") or {}
        include_ids = list(dell_settings.get("include_card_ids") or [])

        with self._lock:
            card_ids = sorted(self._cards.keys())
        monitor_enabled = {
            cid: self.is_monitor_enabled(cid) for cid in card_ids
        }
        included = card_ids_included_for_export(
            card_ids,
            include_monitor_off=include_monitor_off,
            monitor_enabled=monitor_enabled,
        )
        included = filter_capacity_entries_by_card_id(included, card_id=card_id)
        included_ids = sorted(included)

        ibm_hp_ids: list[int] = []
        for site_id in included_ids:
            with self._lock:
                card = self._cards.get(site_id)
            if card is None:
                continue
            if dell_report_family_for_site(
                card.device_profile, site_name=card.name
            ) in {"ibm", "hp"}:
                ibm_hp_ids.append(site_id)

        # Forced-include IBM/HPE cards even when Monitor is off.
        seen = set(ibm_hp_ids)
        for cid_str in include_ids:
            try:
                cid = int(cid_str)
            except (TypeError, ValueError):
                continue
            if card_id is not None and cid != card_id:
                continue
            with self._lock:
                card = self._cards.get(cid)
            if card is None:
                continue
            if dell_report_family_for_site(
                card.device_profile, site_name=card.name
            ) not in {"ibm", "hp"}:
                continue
            if cid not in seen:
                ibm_hp_ids.append(cid)
                seen.add(cid)

        sites: list[ExportSite] = []
        for site_id in ibm_hp_ids:
            with self._lock:
                card = self._cards.get(site_id)
            if card is None:
                continue
            try:
                # Capacity-only suite — full health (checkhealth/showalert/…) is too
                # slow for Dell Report and left the Capacity Report UI spinning.
                card = self.refresh_card(
                    site_id, focus="capacity", include_pools=include_pools
                )
                error = card.error
            except Exception as exc:
                error = str(exc)
            analysis = analyze_health(card.name, card.command_results, card.metrics)
            pools = pool_capacity_from_commands(card.command_results)
            sites.append(
                ExportSite(
                    card_id=site_id,
                    name=card.name,
                    host=card.host,
                    serial_number=card.serial_number,
                    category=card.category,
                    device_profile=card.device_profile,
                    capacity_summary=analysis.get("capacity_summary"),
                    pools=pools,
                    error=error,
                    raw_capacity_summary=analysis.get("raw_capacity_summary"),
                )
            )

        store = load_dell_snapshots()
        ibm_rows, hp_rows, store = collect_dell_report_rows(
            sites,
            snapshot_store=store,
            include_pools=include_pools,
            card_overrides=overrides,
            include_card_ids=include_ids,
        )
        save_dell_snapshots(store)
        ensure_dell_report_has_rows(ibm_rows, hp_rows)

        wb = build_dell_report_workbook(
            ibm_rows=ibm_rows, hp_rows=hp_rows, snapshot_store=store
        )
        body = workbook_to_bytes(wb)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        filename = f"Dell_Capacity_Report_{stamp}.xlsx"
        return body, filename

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

    def open_site_lookup(self) -> str:
        """Open Site Lookup in the default browser."""
        self.ensure_running()
        webbrowser.open(self.site_lookup_url)
        _log(f"Opened Site Lookup in browser: {self.site_lookup_url}")
        return self.site_lookup_url

    def open_ansible_pad(self) -> str:
        """Open Ansible Pad in the default browser."""
        self.ensure_running()
        webbrowser.open(self.ansible_pad_url)
        _log(f"Opened Ansible Pad in browser: {self.ansible_pad_url}")
        return self.ansible_pad_url

    def open_host_power(self, card_id: int | None = None) -> str:
        """Open Host Power in the default browser."""
        self.ensure_running()
        url = self.host_power_url
        if card_id is not None:
            url = f"{url}?card_id={card_id}"
        webbrowser.open(url)
        _log(f"Opened Host Power in browser: {url}")
        return url

    def open_contingency_groups(self) -> str:
        """Open the contingency groups reference page in the default browser."""
        self.ensure_running()
        webbrowser.open(self.contingency_groups_url)
        _log(f"Opened contingency groups in browser: {self.contingency_groups_url}")
        return self.contingency_groups_url

    def open_lun_builder(self) -> str:
        """Open the LUN build planning page in the default browser."""
        self.ensure_running()
        webbrowser.open(self.lun_builder_url)
        _log(f"Opened LUN Builder in browser: {self.lun_builder_url}")
        return self.lun_builder_url

    def open_volume_find(self) -> str:
        """Open the Volume Find page in the default browser."""
        self.ensure_running()
        webbrowser.open(self.volume_find_url)
        _log(f"Opened Volume Find in browser: {self.volume_find_url}")
        return self.volume_find_url

    def open_fc_consistgrp(self, card_id: int | None = None) -> str:
        """Open the FlashCopy consistency groups page in the default browser."""
        self.ensure_running()
        url = self.fc_consistgrp_url
        if card_id is not None:
            url = f"{url}?card={card_id}"
        webbrowser.open(url)
        _log(f"Opened FlashCopy consistency groups in browser: {url}")
        return url

    def open_esx_snap_policy(self) -> str:
        """Open the ESX-snap policy page in the default browser."""
        self.ensure_running()
        webbrowser.open(self.esx_snap_policy_url)
        _log(f"Opened ESX-snap Policy in browser: {self.esx_snap_policy_url}")
        return self.esx_snap_policy_url

    def open_host_volume_health(self) -> str:
        """Open the Hosts & Volumes Health page in the default browser."""
        self.ensure_running()
        webbrowser.open(self.host_volume_health_url)
        _log(f"Opened Hosts & Volumes Health in browser: {self.host_volume_health_url}")
        return self.host_volume_health_url

    def open_snapcopy_summary(self) -> str:
        """Open the Snapcopy Summary page in the default browser."""
        self.ensure_running()
        webbrowser.open(self.snapcopy_summary_url)
        _log(f"Opened Snapcopy Summary in browser: {self.snapcopy_summary_url}")
        return self.snapcopy_summary_url

    def open_system_connectivity(self) -> str:
        """Open the System Connectivity page in the default browser."""
        self.ensure_running()
        webbrowser.open(self.system_connectivity_url)
        _log(f"Opened System Connectivity in browser: {self.system_connectivity_url}")
        return self.system_connectivity_url

    def open_storage_inventory(self) -> str:
        """Open the Storage Inventory page in the default browser."""
        self.ensure_running()
        webbrowser.open(self.storage_inventory_url)
        _log(f"Opened Storage Inventory in browser: {self.storage_inventory_url}")
        return self.storage_inventory_url


_instance: HealthServer | None = None
_instance_lock = threading.Lock()


def get_health_server() -> HealthServer:
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = HealthServer()
        return _instance
