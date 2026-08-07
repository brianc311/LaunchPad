"""Volume Find helpers — eligibility, match, cache/live parsers."""

from __future__ import annotations

import re
from typing import Any

from launchpad.flashsystem_fc import parse_fc_hosts, parse_lsvdisk_volumes
from launchpad.storage_presets import HPE_SHELL_PROFILES, is_svc_fc_profile

ANDERSON_TARGET_NAME = "Anderson, SC"
ANDERSON_DEFAULT_HOST = "10.244.25.158"

_WILLIAMSTON_ANDERSON_NAME = re.compile(
    r"williamston\s*\(\s*anderson\s*\)\s*sc",
    re.IGNORECASE,
)


def normalize_site_host(raw: str) -> str:
    host = str(raw or "").strip()
    for prefix in ("https://", "http://"):
        if host.lower().startswith(prefix):
            host = host[len(prefix) :]
            break
    return host.rstrip("/").strip()


def site_ip_href(host: str) -> str:
    normalized = normalize_site_host(host)
    if not normalized:
        return ""
    return f"https://{normalized}"


def is_williamston_anderson_name(name: str) -> bool:
    return bool(_WILLIAMSTON_ANDERSON_NAME.fullmatch(str(name or "").strip()))


def anderson_rename_plan(cards: list[dict]) -> dict | None:
    williamston_card: dict | None = None
    for card in cards:
        if not isinstance(card, dict):
            continue
        card_name = str(card.get("name") or "")
        if is_williamston_anderson_name(card_name):
            williamston_card = card
            break
    if williamston_card is None:
        return None
    for card in cards:
        if not isinstance(card, dict):
            continue
        if card is williamston_card:
            continue
        if str(card.get("name") or "") == ANDERSON_TARGET_NAME:
            return None
    host = str(williamston_card.get("host") or "").strip()
    return {
        "card_id": williamston_card.get("id"),
        "new_name": ANDERSON_TARGET_NAME,
        "new_host": host or ANDERSON_DEFAULT_HOST,
    }


def volume_name_matches(name: str, query: str) -> bool:
    q = str(query or "").strip().lower()
    if not q:
        return False
    return q in str(name or "").strip().lower()


def vendor_for_profile(profile: str) -> str:
    key = (profile or "").strip().lower()
    if key in HPE_SHELL_PROFILES or key.startswith("hpe_"):
        return "hpe"
    if is_svc_fc_profile(profile):
        return "ibm"
    return "unknown"


def is_volume_find_eligible(card: dict[str, Any], *, monitor_on: bool) -> bool:
    if not monitor_on:
        return False
    if str(card.get("card_type") or "").lower() != "ssh":
        return False
    profile = str(card.get("device_profile") or "")
    if is_svc_fc_profile(profile):
        return True
    if profile.strip().lower() in HPE_SHELL_PROFILES:
        return True
    return False


def host_name_matches(name: str, query: str) -> bool:
    return volume_name_matches(name, query)


def _norm_hpe_col(name: str) -> str:
    """Normalize 3PAR headers like ``-Name-`` or ``Port_WWN/iSCSI_Name``."""
    text = str(name or "").strip().strip("-").strip().lower()
    text = text.replace(" ", "_")
    if "/" in text:
        text = text.split("/", 1)[0]
    return text


def _hpe_col_index(cols: list[str], names: set[str]) -> int | None:
    wanted = {n.lower() for n in names}
    for i, col in enumerate(cols):
        if _norm_hpe_col(col) in wanted:
            return i
    return None


def _hpe_wwn_indices(cols: list[str]) -> list[int]:
    indices: list[int] = []
    for i, col in enumerate(cols):
        norm = _norm_hpe_col(col)
        raw = str(col or "").lower()
        if norm in {"port_wwn", "wwn", "wwpn", "port_wwpn", "host_wwn"}:
            indices.append(i)
        elif "wwn" in norm or "wwpn" in raw:
            indices.append(i)
    return indices


def _find_hpe_table_header(
    lines: list[str],
) -> tuple[str, list[str], int] | None:
    """Return (delim_or_empty, columns, header_line_index) for Name tables."""
    for idx, line in enumerate(lines):
        if "," in line and line.count(",") >= 1:
            cols = [c.strip() for c in line.split(",")]
            if _hpe_col_index(cols, {"name", "hostname", "host_name", "vvname", "vv_name"}) is not None:
                return ",", cols, idx
        if ":" in line and line.count(":") >= 1:
            cols = [c.strip() for c in line.split(":")]
            if _hpe_col_index(cols, {"name", "hostname", "host_name", "vvname", "vv_name"}) is not None:
                return ":", cols, idx
        cols = line.split()
        if _hpe_col_index(cols, {"name", "hostname", "host_name", "vvname", "vv_name"}) is not None:
            return "", cols, idx
    return None


def parse_showhost_hosts(output: str) -> list[dict[str, str]]:
    """Parse HPE showhost CSV/table for Name (+ Persona / Port_WWN / status)."""
    text = str(output or "").strip()
    if not text:
        return []
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    found = _find_hpe_table_header(lines)
    if found is None:
        return []
    delim, cols, header_idx = found
    name_i = _hpe_col_index(cols, {"name", "hostname", "host_name"})
    if name_i is None:
        return []
    wwn_indices = _hpe_wwn_indices(cols)
    status_i = _hpe_col_index(cols, {"state", "status", "host_state"})
    persona_i = _hpe_col_index(cols, {"persona", "host_persona", "type", "host_type"})
    hosts: list[dict[str, str]] = []
    for line in lines[header_idx + 1 :]:
        parts = [p.strip() for p in line.split(delim)] if delim else line.split()
        if len(parts) <= name_i:
            continue
        name = parts[name_i]
        if not name or _norm_hpe_col(name) in {"name", "hostname", "host_name"}:
            continue
        wwpns = [
            parts[i]
            for i in wwn_indices
            if i < len(parts) and parts[i] and parts[i] not in {"-", "--", "----"}
        ]
        status = parts[status_i] if status_i is not None and len(parts) > status_i else ""
        if status in {"-", "--", "----"}:
            status = ""
        persona = (
            parts[persona_i] if persona_i is not None and len(parts) > persona_i else ""
        )
        if persona in {"-", "--", "----"}:
            persona = ""
        hosts.append(
            {
                "host_name": name,
                "wwpns": " ".join(wwpns),
                "status": status,
                "type": persona,
                "port_count": str(len(wwpns)) if wwpns else "",
                "protocol": "SCSI",
            }
        )
    # showhost emits one row per port; merge ports onto unique host names.
    merged: dict[str, dict[str, str]] = {}
    for host in hosts:
        key = host["host_name"]
        existing = merged.get(key)
        if existing is None:
            merged[key] = dict(host)
            continue
        ports = (existing.get("wwpns") or "").split() + (host.get("wwpns") or "").split()
        uniq = list(dict.fromkeys(p for p in ports if p))
        existing["wwpns"] = " ".join(uniq)
        existing["port_count"] = str(len(uniq)) if uniq else existing.get("port_count") or ""
        if not existing.get("type") and host.get("type"):
            existing["type"] = host["type"]
        if not existing.get("status") and host.get("status"):
            existing["status"] = host["status"]
    return list(merged.values())


def _showvv_column_index(cols: list[str], names: set[str]) -> int | None:
    return _hpe_col_index(cols, names)


def _showvv_pick_status(parts: list[str], cols: list[str]) -> str:
    """Prefer State / Detailed_State over ownership columns like Mstr."""
    by_name = {_norm_hpe_col(c): i for i, c in enumerate(cols)}
    for key in ("detailed_state", "state", "status"):
        index = by_name.get(key)
        if index is None or len(parts) <= index:
            continue
        value = parts[index].strip()
        if value and value not in {"-", "--", "----"}:
            return value
    return ""


def parse_showvv_volumes(output: str) -> list[dict[str, str]]:
    """Parse HPE showvv CSV/delimited or whitespace table for Name + CPG + health."""
    text = str(output or "").strip()
    if not text:
        return []
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    found = _find_hpe_table_header(lines)
    if found is None:
        return []
    delim, cols, header_idx = found
    name_i = _showvv_column_index(cols, {"name", "vvname", "vv_name"})
    cpg_i = _showvv_column_index(
        cols, {"usrcpg", "cpg", "snpcpg", "usr_cpg"}
    )
    mstr_i = _showvv_column_index(cols, {"mstr"})
    capacity_i = _showvv_column_index(
        cols, {"vsize_mb", "vsize", "size_mb", "capacity", "usr_total_mb"}
    )
    uid_i = _showvv_column_index(cols, {"vv_wwn", "wwn", "uid", "vvid"})
    if name_i is None:
        return []
    volumes: list[dict[str, str]] = []
    for line in lines[header_idx + 1 :]:
        parts = [p.strip() for p in line.split(delim)] if delim else line.split()
        if len(parts) <= name_i:
            continue
        name = parts[name_i]
        if not name or _norm_hpe_col(name) in {"name", "vvname", "vv_name"}:
            continue
        pool = parts[cpg_i] if cpg_i is not None and len(parts) > cpg_i else ""
        if pool in {"-", "--", "----"}:
            pool = ""
        status = _showvv_pick_status(parts, cols)
        mstr = parts[mstr_i] if mstr_i is not None and len(parts) > mstr_i else ""
        if mstr in {"-", "--", "----"}:
            mstr = ""
        capacity = (
            parts[capacity_i]
            if capacity_i is not None and len(parts) > capacity_i
            else ""
        )
        if capacity in {"-", "--", "----"}:
            capacity = ""
        elif capacity and capacity_i is not None:
            col = _norm_hpe_col(cols[capacity_i])
            if "mb" in col and not capacity.lower().endswith("mb"):
                capacity = f"{capacity} MB"
        uid = parts[uid_i] if uid_i is not None and len(parts) > uid_i else ""
        if uid in {"-", "--", "----"}:
            uid = ""
        volumes.append(
            {
                "name": name,
                "pool_or_cpg": pool,
                "status": status,
                "mstr": mstr,
                "capacity": capacity,
                "uid": uid,
            }
        )
    return volumes

def volumes_from_command_results(
    command_results: list[dict[str, Any]] | None,
    profile: str,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in command_results or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        cmd = f"{item.get('label') or ''} {item.get('command') or ''}".lower()
        output = str(item.get("output") or "")
        parsed: list[dict[str, str]] = []
        if "lsvdisk" in cmd or "memory - volumes" in cmd:
            for row in parse_lsvdisk_volumes(output):
                parsed.append(
                    {"name": row.get("name") or "", "pool_or_cpg": row.get("pool") or ""}
                )
        elif "showvv" in cmd:
            parsed = parse_showvv_volumes(output)
        for row in parsed:
            name = str(row.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            out.append({"name": name, "pool_or_cpg": str(row.get("pool_or_cpg") or "")})
    return out


def hosts_from_card(card: dict[str, Any]) -> list[dict[str, str]]:
    profile = str(card.get("device_profile") or "")
    out: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(host_name: str, wwpns: str = "") -> None:
        name = str(host_name or "").strip()
        if not name or name in seen:
            return
        seen.add(name)
        out.append({"host_name": name, "wwpns": str(wwpns or "").strip()})

    if vendor_for_profile(profile) == "ibm":
        fc_hosts = card.get("fc_hosts")
        if isinstance(fc_hosts, list) and fc_hosts:
            for h in fc_hosts:
                if isinstance(h, dict):
                    add(h.get("host_name") or h.get("name") or "", h.get("wwpns") or "")
            return out
        for item in card.get("command_results") or []:
            if not isinstance(item, dict) or item.get("error"):
                continue
            cmd = f"{item.get('label') or ''} {item.get('command') or ''}".lower()
            if "lshostvdiskmap" in cmd or "lsvdiskhostmap" in cmd or "host lun" in cmd:
                continue
            if "lshost" in cmd or "fc - hosts" in cmd:
                for row in parse_fc_hosts(str(item.get("output") or "")):
                    add(row.get("host_name") or "", row.get("wwpns") or "")
        return out

    for item in card.get("command_results") or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        cmd = f"{item.get('label') or ''} {item.get('command') or ''}".lower()
        if "showhost" in cmd:
            for row in parse_showhost_hosts(str(item.get("output") or "")):
                add(row.get("host_name") or "", row.get("wwpns") or "")
    return out


def find_hosts_in_cards(
    cards: list[dict[str, Any]],
    query: str,
    *,
    monitor_enabled: dict[Any, bool],
    source: str,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        card_id = card.get("id")
        monitor_on = bool(
            monitor_enabled.get(card_id, monitor_enabled.get(str(card_id), False))
        )
        if not is_volume_find_eligible(card, monitor_on=monitor_on):
            continue
        profile = str(card.get("device_profile") or "")
        for host_row in hosts_from_card(card):
            if not host_name_matches(host_row["host_name"], query):
                continue
            matches.append(
                {
                    "card_id": card_id,
                    "card_name": str(card.get("name") or card_id or ""),
                    "profile": profile,
                    "vendor": vendor_for_profile(profile),
                    "host_name": host_row["host_name"],
                    "wwpns": host_row.get("wwpns") or "",
                    "source": source,
                    "host": str(card.get("host") or ""),
                }
            )
    return sorted(
        matches,
        key=lambda m: (
            str(m.get("card_name") or "").lower(),
            str(m.get("host_name") or "").lower(),
        ),
    )


def find_volumes_in_cards(
    cards: list[dict[str, Any]],
    query: str,
    *,
    monitor_enabled: dict[Any, bool],
    source: str,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        card_id = card.get("id")
        monitor_on = bool(monitor_enabled.get(card_id, monitor_enabled.get(str(card_id), False)))
        if not is_volume_find_eligible(card, monitor_on=monitor_on):
            continue
        profile = str(card.get("device_profile") or "")
        for vol in volumes_from_command_results(card.get("command_results"), profile):
            if not volume_name_matches(vol["name"], query):
                continue
            matches.append(
                {
                    "card_id": card_id,
                    "card_name": str(card.get("name") or card_id or ""),
                    "profile": profile,
                    "vendor": vendor_for_profile(profile),
                    "volume": vol["name"],
                    "pool_or_cpg": vol.get("pool_or_cpg") or "",
                    "source": source,
                    "host": str(card.get("host") or ""),
                }
            )
    return sorted(
        matches,
        key=lambda m: (str(m.get("card_name") or "").lower(), str(m.get("volume") or "").lower()),
    )
