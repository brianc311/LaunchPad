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


def parse_showhost_hosts(output: str) -> list[dict[str, str]]:
    """Parse HPE showhost CSV/table for Name (+ optional Port_WWN / WWN columns)."""
    text = str(output or "").strip()
    if not text:
        return []
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    header = lines[0]
    delim = "," if "," in header else (":" if ":" in header else None)
    wwn_cols = {"port_wwn", "wwn", "wwpn", "port_wwpn", "host_wwn"}
    status_cols = {"state", "status", "host_state"}
    hosts: list[dict[str, str]] = []
    if delim:
        cols = [c.strip() for c in header.split(delim)]
        name_i = next((i for i, c in enumerate(cols) if c.lower() in {"name", "hostname", "host_name"}), None)
        wwn_indices = [i for i, c in enumerate(cols) if c.lower() in wwn_cols]
        status_i = next((i for i, c in enumerate(cols) if c.lower() in status_cols), None)
        if name_i is None:
            return []
        for line in lines[1:]:
            parts = [p.strip() for p in line.split(delim)]
            if len(parts) <= name_i:
                continue
            name = parts[name_i]
            if not name or name.lower() == "name":
                continue
            wwpns = [
                parts[i]
                for i in wwn_indices
                if i < len(parts) and parts[i] and parts[i] not in {"-", "--"}
            ]
            status = parts[status_i] if status_i is not None and len(parts) > status_i else ""
            hosts.append({"host_name": name, "wwpns": " ".join(wwpns), "status": status})
        return hosts

    cols = header.split()
    name_i = next((i for i, c in enumerate(cols) if c.lower() in {"name", "hostname", "host_name"}), None)
    wwn_indices = [i for i, c in enumerate(cols) if c.lower() in wwn_cols]
    status_i = next((i for i, c in enumerate(cols) if c.lower() in status_cols), None)
    if name_i is None:
        return []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) <= name_i:
            continue
        name = parts[name_i]
        if not name or name.lower() == "name":
            continue
        wwpns = [
            parts[i]
            for i in wwn_indices
            if i < len(parts) and parts[i] and parts[i] not in {"-", "--"}
        ]
        status = parts[status_i] if status_i is not None and len(parts) > status_i else ""
        hosts.append({"host_name": name, "wwpns": " ".join(wwpns), "status": status})
    return hosts


def _showvv_column_index(cols: list[str], names: set[str]) -> int | None:
    return next((i for i, c in enumerate(cols) if c.lower() in names), None)


def _showvv_pick_status(parts: list[str], cols: list[str]) -> str:
    """Prefer State / Detailed_State over ownership columns like Mstr."""
    by_name = {c.lower(): i for i, c in enumerate(cols)}
    for key in ("detailed_state", "state", "status"):
        index = by_name.get(key)
        if index is None or len(parts) <= index:
            continue
        value = parts[index].strip()
        if value and value not in {"-", "--"}:
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
    header = lines[0]
    delim = "," if "," in header else (":" if ":" in header else None)
    volumes: list[dict[str, str]] = []
    if delim:
        cols = [c.strip() for c in header.split(delim)]
        name_i = _showvv_column_index(cols, {"name", "vvname", "vv_name"})
        cpg_i = _showvv_column_index(
            cols, {"usrcpg", "cpg", "snpcpg", "usr_cpg"}
        )
        mstr_i = _showvv_column_index(cols, {"mstr"})
        if name_i is None:
            return []
        for line in lines[1:]:
            parts = [p.strip() for p in line.split(delim)]
            if len(parts) <= name_i:
                continue
            name = parts[name_i]
            if not name or name.lower() == "name":
                continue
            pool = parts[cpg_i] if cpg_i is not None and len(parts) > cpg_i else ""
            if pool in {"-", "--"}:
                pool = ""
            status = _showvv_pick_status(parts, cols)
            mstr = parts[mstr_i] if mstr_i is not None and len(parts) > mstr_i else ""
            if mstr in {"-", "--"}:
                mstr = ""
            volumes.append(
                {
                    "name": name,
                    "pool_or_cpg": pool,
                    "status": status,
                    "mstr": mstr,
                }
            )
        return volumes

    # Whitespace table fallback (no comma/colon delimiters in header).
    cols = header.split()
    name_i = _showvv_column_index(cols, {"name", "vvname", "vv_name"})
    cpg_i = _showvv_column_index(cols, {"usrcpg", "cpg", "snpcpg", "usr_cpg"})
    mstr_i = _showvv_column_index(cols, {"mstr"})
    if name_i is None:
        return []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) <= name_i:
            continue
        name = parts[name_i]
        if not name or name.lower() == "name":
            continue
        pool = parts[cpg_i] if cpg_i is not None and len(parts) > cpg_i else ""
        if pool in {"-", "--"}:
            pool = ""
        status = _showvv_pick_status(parts, cols)
        mstr = parts[mstr_i] if mstr_i is not None and len(parts) > mstr_i else ""
        if mstr in {"-", "--"}:
            mstr = ""
        volumes.append(
            {
                "name": name,
                "pool_or_cpg": pool,
                "status": status,
                "mstr": mstr,
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
