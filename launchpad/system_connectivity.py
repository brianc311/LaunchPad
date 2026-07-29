"""System Connectivity helpers — Call Home / DNS / SNMP / NTP parsers."""

from __future__ import annotations

import re
from typing import Any

from launchpad.firmware_catalog import latest_in_catalog, normalize_hpe_firmware_version, versions_behind
from launchpad.flashsystem_parse import _parse_colon_table
from launchpad.storage_presets import HPE_SHELL_PROFILES, SVC_PROFILES, is_svc_fc_profile
from launchpad.volume_find import vendor_for_profile as _vendor_for_profile

TOPICS: tuple[str, ...] = ("call_home", "dns", "snmp", "ntp", "firmware")
FIRMWARE_EXTRA_FIELDS: tuple[str, ...] = ("current", "latest", "versions_behind")
ROW_FIELDS: tuple[str, ...] = (
    "site",
    "card_name",
    "host",
    "vendor",
    "profile",
    "configured",
    "status",
    "details",
    "error",
)

_DS8884_PROFILE = "ibm_ds8884"
_HPE_CALL_HOME_NA = (
    "n/a",
    "n/a",
    "Call Home is on the Service Processor (not collected via array SSH)",
)
_DS_CALL_HOME_NA = (
    "n/a",
    "n/a",
    "Call Home not available via DSCLI on this path (often HMC)",
)

_HPE_LABEL_RE = re.compile(
    r"^(?P<label>DNS server|NTP server)\s*:\s*(?P<value>\S.*)?$",
    re.IGNORECASE,
)
_HPE_VERSION_RE = re.compile(
    r"^(?:Release\s+version|Version)\s*:\s*(?P<version>\S.+)$",
    re.IGNORECASE,
)
_DS_FIRMWARE_NA = (
    "n/a",
    "n/a",
    "Firmware not available via DSCLI on this path",
    "",
)
_SVC_CODE_LEVEL_BUILD_RE = re.compile(
    r"\s*\([^)]*build[^)]*\)\s*$",
    re.IGNORECASE,
)


def normalize_svc_code_level(code_level: str) -> str:
    """Strip trailing ``(build …)``-style suffixes for display and catalog match."""
    text = str(code_level or "").strip()
    if not text:
        return ""
    return _SVC_CODE_LEVEL_BUILD_RE.sub("", text).strip()


def vendor_for_profile(profile: str) -> str:
    key = (profile or "").strip().lower()
    if key == _DS8884_PROFILE or key.startswith("ibm_ds"):
        return "ibm"
    return _vendor_for_profile(profile)


def is_system_connectivity_eligible(card: dict, *, monitor_on: bool) -> bool:
    if not monitor_on:
        return False
    if str(card.get("card_type") or "").lower() != "ssh":
        return False
    profile = str(card.get("device_profile") or "").strip().lower()
    if not profile:
        return False
    if profile in SVC_PROFILES or is_svc_fc_profile(profile):
        return True
    if profile in HPE_SHELL_PROFILES:
        return True
    if profile == _DS8884_PROFILE:
        return True
    return False


def base_row(
    *,
    card_name: str,
    host: str,
    vendor: str,
    profile: str,
    card_id: int | None = None,
    site: str = "",
) -> dict:
    row: dict[str, Any] = {
        "site": site or card_name,
        "card_name": card_name,
        "host": host,
        "vendor": vendor,
        "profile": profile,
        "configured": "",
        "status": "",
        "details": "",
        "error": "",
    }
    if card_id is not None:
        row["card_id"] = int(card_id)
    return row


def finalize_row(
    row: dict,
    *,
    configured: str,
    status: str = "",
    details: str = "",
    error: str = "",
) -> dict:
    out = dict(row)
    out["configured"] = configured
    out["status"] = status
    out["details"] = details
    out["error"] = error
    return out


def _header_index(headers: list[str], *names: str) -> int | None:
    lowered = [h.strip().lower() for h in headers]
    for name in names:
        key = name.lower()
        if key in lowered:
            return lowered.index(key)
    return None


def _cell(row: list[str], idx: int | None) -> str:
    if idx is None or idx < 0 or idx >= len(row):
        return ""
    return str(row[idx] or "").strip()


def parse_svc_call_home(output: str) -> tuple[str, str, str]:
    text = str(output or "").strip()
    if not text:
        return "unknown", "", "empty Call Home output"
    headers, rows = _parse_colon_table(text)
    if not headers and not rows:
        # Header-only empty table still means "no" when present as a colon header line.
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) == 1 and ":" in lines[0] and lines[0].lower().startswith("id"):
            return "no", "empty", "no Call Home entries"
        return "unknown", "", "unrecognized Call Home output"
    if not rows:
        return "no", "empty", "no Call Home entries"
    status_idx = _header_index(headers, "status")
    statuses: list[str] = []
    for row in rows:
        status = _cell(row, status_idx) if status_idx is not None else ""
        if not status and len(row) > 1:
            status = str(row[1] or "").strip()
        if status:
            statuses.append(status)
    if not statuses:
        return "no", "empty", "no Call Home entries"
    primary = statuses[0]
    folded = primary.lower()
    configured = "yes" if folded not in {"disabled", "off", "inactive", "none"} else "no"
    details = f"status={primary}" if len(statuses) == 1 else ", ".join(statuses)
    return configured, primary, details


def parse_svc_dns(output: str) -> tuple[str, str, str]:
    text = str(output or "").strip()
    if not text:
        return "unknown", "", "empty DNS output"
    headers, rows = _parse_colon_table(text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not headers and not rows:
        if len(lines) == 1 and ":" in lines[0] and lines[0].lower().startswith("id"):
            return "no", "empty", "no DNS servers"
        return "unknown", "", "unrecognized DNS output"
    if not rows:
        return "no", "empty", "no DNS servers"
    ip_idx = _header_index(headers, "IP_address", "ip_address", "IP", "ip")
    name_idx = _header_index(headers, "name")
    ips: list[str] = []
    for row in rows:
        ip = _cell(row, ip_idx)
        if not ip and len(row) >= 3:
            ip = str(row[2] or "").strip()
        name = _cell(row, name_idx)
        if ip:
            ips.append(f"{name}={ip}" if name else ip)
        elif name:
            ips.append(name)
    if not ips:
        return "no", "empty", "no DNS servers"
    return "yes", "configured", ", ".join(ips)


def parse_svc_snmp(output: str) -> tuple[str, str, str]:
    text = str(output or "").strip()
    if not text:
        return "unknown", "", "empty SNMP output"
    headers, rows = _parse_colon_table(text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not headers and not rows:
        if len(lines) == 1 and ":" in lines[0] and lines[0].lower().startswith("id"):
            return "no", "empty", "no SNMP servers"
        return "unknown", "", "unrecognized SNMP output"
    if not rows:
        return "no", "empty", "no SNMP servers"
    # Never include community/password columns in details.
    secret_headers = {"community", "password", "community_name", "passphrase", "auth_password", "priv_password"}
    ip_idx = _header_index(headers, "IP", "ip", "IP_address", "ip_address", "address")
    port_idx = _header_index(headers, "port")
    parts: list[str] = []
    for row in rows:
        ip = _cell(row, ip_idx)
        port = _cell(row, port_idx)
        if not ip:
            # Fall back to non-secret columns by position when headers are sparse.
            for i, header in enumerate(headers):
                if header.strip().lower() in secret_headers:
                    continue
                if header.strip().lower() in {"id"}:
                    continue
                value = _cell(row, i)
                if value and re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", value):
                    ip = value
                    break
        if not ip and not port:
            continue
        if ip and port:
            parts.append(f"{ip}:{port}")
        elif ip:
            parts.append(ip)
        else:
            parts.append(f"port={port}")
    if not parts:
        return "no", "empty", "no SNMP servers"
    return "yes", "configured", ", ".join(parts)


def parse_svc_firmware_from_lssystem(output: str) -> tuple[str, str, str, str]:
    text = str(output or "")
    if not text.strip():
        return "unknown", "", "empty lssystem output", ""
    code_level: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        key, sep, value = stripped.partition(":")
        if not sep:
            continue
        if key.strip().lower() == "code_level":
            code_level = value.strip()
            break
    if code_level is None:
        return "unknown", "", "code_level not found", ""
    if not code_level:
        return "no", "empty", "no firmware version", ""
    current = normalize_svc_code_level(code_level) or code_level
    return "yes", "configured", f"code_level={current}", current


def parse_hpe_showversion_firmware(output: str) -> tuple[str, str, str, str]:
    text = str(output or "")
    if not text.strip():
        return "unknown", "", "empty showversion output", ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _HPE_VERSION_RE.match(stripped)
        if not match:
            continue
        version = match.group("version").strip()
        if not version:
            continue
        lowered = version.lower()
        if lowered in {"public", "private", "community"}:
            continue
        current = normalize_hpe_firmware_version(version)
        return "yes", "configured", f"version={current}", current
    return "no", "empty", "no firmware version", ""


def parse_ds_firmware(output: str) -> tuple[str, str, str, str]:
    text = str(output or "").strip()
    if not text:
        return _DS_FIRMWARE_NA
    lowered = text.lower()
    version_keys = ("firmware", "version", "code level", "code_level", "microcode")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        key, sep, value = stripped.partition(":")
        if sep:
            label = key.strip().lower()
            if any(token in label for token in version_keys):
                version = value.strip()
                if version:
                    return "yes", "configured", f"{key.strip()}={version}", version
        match = re.search(
            r"(?:firmware|version|code[_ ]level|microcode)\s*[:=]\s*(\S.+)",
            stripped,
            re.IGNORECASE,
        )
        if match:
            version = match.group(1).strip()
            if version:
                return "yes", "configured", stripped, version
    if any(key in lowered for key in version_keys):
        return "unknown", "", "unrecognized DS firmware output", ""
    return _DS_FIRMWARE_NA


def enrich_firmware_row(
    row: dict,
    *,
    current: str,
    catalog: list[str],
    configured: str,
    status: str = "",
    details: str = "",
    error: str = "",
) -> dict:
    latest = latest_in_catalog(catalog)
    behind = versions_behind(current, catalog)
    resolved_status = status
    if not resolved_status and not error:
        if configured == "yes":
            if behind == "0":
                resolved_status = "current"
            elif behind.isdigit() and int(behind) > 0:
                resolved_status = "behind"
            elif behind == "unknown":
                resolved_status = "unknown"
    out = finalize_row(
        row,
        configured=configured,
        status=resolved_status,
        details=details,
        error=error,
    )
    out["current"] = current
    out["latest"] = latest
    out["versions_behind"] = behind
    return out


def parse_svc_ntp_from_lssystem(output: str) -> tuple[str, str, str]:
    text = str(output or "")
    if not text.strip():
        return "unknown", "", "empty lssystem output"
    ntp_value: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        key, sep, value = stripped.partition(":")
        if not sep:
            continue
        if key.strip().lower() == "cluster_ntp_ip_address":
            ntp_value = value.strip()
            break
    if ntp_value is None:
        return "unknown", "", "cluster_ntp_IP_address not found"
    if not ntp_value:
        return "no", "empty", "no NTP server"
    return "yes", "configured", ntp_value


def parse_hpe_shownet_dns_ntp(output: str) -> dict[str, tuple[str, str, str]]:
    text = str(output or "")
    dns_value = ""
    ntp_value = ""
    for line in text.splitlines():
        match = _HPE_LABEL_RE.match(line.strip())
        if not match:
            # Tolerate extra spaces around the colon (shownet style).
            lowered = line.strip()
            for label, attr in (("dns server", "dns"), ("ntp server", "ntp")):
                if label in lowered.lower() and ":" in lowered:
                    _, _, rest = lowered.partition(":")
                    value = rest.strip()
                    if attr == "dns":
                        dns_value = value
                    else:
                        ntp_value = value
            continue
        label = match.group("label").strip().lower()
        value = (match.group("value") or "").strip()
        if label.startswith("dns"):
            dns_value = value
        elif label.startswith("ntp"):
            ntp_value = value

    def _topic(value: str, empty_detail: str) -> tuple[str, str, str]:
        if value:
            return "yes", "configured", value
        if text.strip():
            return "no", "empty", empty_detail
        return "unknown", "", empty_detail

    return {
        "dns": _topic(dns_value, "no DNS server"),
        "ntp": _topic(ntp_value, "no NTP server"),
    }


def parse_hpe_snmpmgr(output: str) -> tuple[str, str, str]:
    text = str(output or "").strip()
    if not text:
        return "unknown", "", "empty SNMP manager output"
    # showsnmpmgr: avoid community/password tokens entirely.
    secret_tokens = ("community", "password", "passphrase", "authkey", "privkey")
    managers: list[str] = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "no", "empty", "no SNMP managers"
    # Skip banner/header-ish first line when it has no IP.
    for line in lines:
        lowered = line.lower()
        if any(tok in lowered for tok in secret_tokens):
            # Strip secret-looking trailing fields; keep IP/port-like tokens only.
            tokens = [t for t in line.split() if not any(s in t.lower() for s in secret_tokens)]
            line = " ".join(tokens)
        ip_match = re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", line)
        if not ip_match:
            continue
        ip = ip_match.group(0)
        # Numbers outside the IP token only (avoids octet false-positives and
        # row ids). Prefer SNMP ports 161/162; otherwise omit port.
        outside = line[: ip_match.start()] + " " + line[ip_match.end() :]
        outside_nums = re.findall(r"\b(\d{1,5})\b", outside)
        preferred = [c for c in outside_nums if c in {"161", "162"}]
        port = preferred[0] if preferred else ""
        managers.append(f"{ip}:{port}" if port else ip)
    if not managers:
        # Header-only / empty manager table.
        if len(lines) <= 2 and not re.search(r"\d+\.\d+\.\d+\.\d+", text):
            return "no", "empty", "no SNMP managers"
        return "unknown", "", "unrecognized SNMP manager output"
    return "yes", "configured", ", ".join(managers)


def hpe_call_home_na_row() -> tuple[str, str, str]:
    return _HPE_CALL_HOME_NA


def parse_ds_networkport_dns(output: str) -> tuple[str, str, str]:
    text = str(output or "").strip()
    if not text:
        return "unknown", "", "empty lsnetworkport output"
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "unknown", "", "empty lsnetworkport output"
    header_line = lines[0]
    header_tokens = header_line.split()
    # Multi-word columns: Primary DNS, Secondary DNS, Subnet Mask, IP address
    # Rebuild logical columns by scanning known phrases.
    logical: list[str] = []
    i = 0
    while i < len(header_tokens):
        two = f"{header_tokens[i]} {header_tokens[i + 1]}" if i + 1 < len(header_tokens) else ""
        if two.lower() in {
            "ip address",
            "subnet mask",
            "primary dns",
            "secondary dns",
        }:
            logical.append(two)
            i += 2
            continue
        logical.append(header_tokens[i])
        i += 1
    primary_idx = _header_index(logical, "Primary DNS", "primary dns")
    secondary_idx = _header_index(logical, "Secondary DNS", "secondary dns")
    state_idx = _header_index(logical, "State", "state")
    if primary_idx is None and secondary_idx is None:
        return "unknown", "", "DNS columns not found"
    data_lines = lines[1:]
    if not data_lines:
        return "no", "empty", "no DNS servers"
    dns_values: list[str] = []
    states: list[str] = []
    for line in data_lines:
        cols = line.split()
        # When IP/mask fields are single tokens, len(cols) should match logical headers.
        if len(cols) < len(logical):
            # Pad / best-effort align from the right for State / DNS fields.
            pass
        primary = _cell(cols, primary_idx)
        secondary = _cell(cols, secondary_idx)
        state = _cell(cols, state_idx)
        for value in (primary, secondary):
            if value and value not in dns_values and re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", value):
                dns_values.append(value)
        if state:
            states.append(state)
    if not dns_values:
        return "no", "empty", "no DNS servers"
    status = states[0] if states else "configured"
    return "yes", status, ", ".join(dns_values)


def parse_ds_showsp_call_home(output: str) -> tuple[str, str, str]:
    text = str(output or "").strip()
    if not text:
        return _DS_CALL_HOME_NA
    lowered = text.lower()
    # Best-effort: look for remote support / call home hints.
    call_home_keys = (
        "callhome",
        "call home",
        "call_home",
        "remote support",
        "remotesupport",
        "offload",
    )
    if not any(key in lowered for key in call_home_keys):
        return _DS_CALL_HOME_NA
    # Prefer enabled/disabled style tokens when present.
    status = ""
    for token in ("enabled", "disabled", "active", "inactive", "on", "off"):
        if re.search(rf"\b{token}\b", lowered):
            status = token
            break
    if not status:
        return _DS_CALL_HOME_NA
    configured = "yes" if status in {"enabled", "active", "on"} else "no"
    return configured, status, f"Call Home {status}"


def topic_commands_for_profile(profile: str) -> dict[str, list[str]]:
    key = (profile or "").strip().lower()
    empty = {topic: [] for topic in TOPICS}
    if key in SVC_PROFILES or is_svc_fc_profile(key):
        return {
            "call_home": ["lscloudcallhome -delim :"],
            "dns": ["lsdnsserver -delim :"],
            "snmp": ["lssnmpserver -delim :"],
            "ntp": ["lssystem -delim :"],
            "firmware": ["lssystem -delim :"],
        }
    if key in HPE_SHELL_PROFILES:
        return {
            "call_home": [],
            "dns": ["shownet"],
            "snmp": ["showsnmpmgr"],
            "ntp": ["shownet"],
            "firmware": ["showversion"],
        }
    if key == _DS8884_PROFILE:
        return {
            "call_home": ["dscli showsp"],
            "dns": ["dscli lsnetworkport"],
            "snmp": [],
            "ntp": [],
            "firmware": [],
        }
    return empty
