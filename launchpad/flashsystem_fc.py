"""Parse IBM Spectrum Virtualize FC WWPN / host / LUN mapping CLI output."""

from __future__ import annotations

from typing import Any

from launchpad.flashsystem_parse import _parse_colon_table, _parse_space_table


def _table_records(output: str) -> list[dict[str, str]]:
    headers, rows = _parse_colon_table(output)
    if not rows:
        headers, rows = _parse_space_table(output)
    if not headers or not rows:
        return []
    records: list[dict[str, str]] = []
    for row in rows:
        record: dict[str, str] = {}
        for index, header in enumerate(headers):
            key = (header or "").strip()
            if not key:
                continue
            record[key] = row[index].strip() if index < len(row) else ""
        if any(record.values()):
            records.append(record)
    return records


def _get(record: dict[str, str], *keys: str) -> str:
    lower_map = {k.lower(): v for k, v in record.items()}
    for key in keys:
        value = lower_map.get(key.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _find_command_output(
    command_results: list[dict[str, Any]] | None,
    *needles: str,
    exclude: tuple[str, ...] = (),
) -> str:
    if not command_results:
        return ""
    for item in command_results:
        if item.get("error"):
            continue
        haystack = f"{item.get('label', '')} {item.get('command', '')}".lower()
        if exclude and any(token in haystack for token in exclude):
            continue
        if any(needle in haystack for needle in needles):
            return (item.get("output") or "").strip()
    return ""


def parse_fc_ports(output: str) -> list[dict[str, str]]:
    """Parse svcinfo lsportfc into port / canister WWPN rows."""
    ports: list[dict[str, str]] = []
    for record in _table_records(output):
        wwpn = _get(record, "WWPN", "local_wwpn", "wwpn")
        if not wwpn:
            continue
        ports.append(
            {
                "port_id": _get(record, "id", "fc_io_port_id", "port_id"),
                "fc_io_port_id": _get(record, "fc_io_port_id"),
                "node_id": _get(record, "node_id"),
                "node_name": _get(record, "node_name", "node"),
                "wwpn": wwpn.upper(),
                "nportid": _get(record, "nportid", "NPortID"),
                "status": _get(record, "status", "state"),
                "speed": _get(record, "port_speed", "speed"),
                "type": _get(record, "type"),
                "attachment": _get(record, "attachment"),
                "adapter_location": _get(record, "adapter_location"),
            }
        )
    return ports


def parse_fc_hosts(output: str) -> list[dict[str, str]]:
    """Parse svcinfo lshost summary rows."""
    hosts: list[dict[str, str]] = []
    for record in _table_records(output):
        name = _get(record, "name", "host_name")
        if not name:
            continue
        hosts.append(
            {
                "host_id": _get(record, "id", "host_id"),
                "host_name": name,
                "status": _get(record, "status"),
                "protocol": _get(record, "protocol"),
                "port_count": _get(record, "port_count"),
                "site_name": _get(record, "site_name"),
            }
        )
    return hosts


def parse_host_lun_maps(output: str) -> list[dict[str, str]]:
    """Parse svcinfo lshostvdiskmap / lsvdiskhostmap rows."""
    maps: list[dict[str, str]] = []
    for record in _table_records(output):
        # lshostvdiskmap: name = vdisk, host_name = host
        # lsvdiskhostmap: name = host, vdisk_name = vdisk
        host = _get(record, "host_name", "host")
        vdisk = _get(record, "vdisk_name", "volume_name", "vdisk")
        if host and not vdisk:
            vdisk = _get(record, "name")
        elif vdisk and not host:
            host = _get(record, "name")
        elif not host and not vdisk:
            # Ambiguous single-name row — skip rather than mis-label
            continue
        maps.append(
            {
                "host_id": _get(record, "host_id", "id"),
                "host_name": host,
                "vdisk_id": _get(record, "vdisk_id", "volume_id"),
                "vdisk_name": vdisk,
                "scsi_id": _get(record, "SCSI_id", "scsi_id", "lun", "UID"),
                "io_group_id": _get(record, "IO_group_id", "iogrp_id"),
                "io_group_name": _get(record, "IO_group_name", "iogrp_name"),
            }
        )
    return maps


def parse_fabric_logins(output: str) -> list[dict[str, str]]:
    """Parse svcinfo lsfabric — links array WWPN to remote (host) WWPN."""
    logins: list[dict[str, str]] = []
    for record in _table_records(output):
        local = _get(record, "local_wwpn", "WWPN")
        remote = _get(record, "remote_wwpn", "partner_wwpn")
        if not local and not remote:
            continue
        logins.append(
            {
                "local_wwpn": local.upper() if local else "",
                "remote_wwpn": remote.upper() if remote else "",
                "node_id": _get(record, "node_id"),
                "node_name": _get(record, "node_name", "node"),
                "local_port": _get(record, "local_port", "port_id"),
                "state": _get(record, "state", "status"),
                "host_name": _get(record, "name", "host_name", "host"),
                "type": _get(record, "type"),
            }
        )
    return logins


def analyze_fc_inventory(
    command_results: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Build FC port / host / mapping inventory from SSH command results."""
    ports_out = _find_command_output(
        command_results, "lsportfc", "fc - ports", "ports wwpn"
    )
    hosts_out = _find_command_output(
        command_results,
        "fc - hosts",
        "lshost -delim",
        "svcinfo lshost",
        exclude=("lshostvdiskmap", "lsvdiskhostmap", "host lun"),
    )
    maps_out = _find_command_output(
        command_results,
        "lshostvdiskmap",
        "lsvdiskhostmap",
        "host lun maps",
        "fc - host lun",
    )
    fabric_out = _find_command_output(command_results, "lsfabric", "fc - fabric")

    ports = parse_fc_ports(ports_out)
    hosts = parse_fc_hosts(hosts_out)
    mappings = parse_host_lun_maps(maps_out)
    fabric = parse_fabric_logins(fabric_out)

    # Attach logged-in remote WWPNs to ports via local WWPN
    remotes_by_local: dict[str, list[dict[str, str]]] = {}
    for login in fabric:
        local = login.get("local_wwpn") or ""
        if not local:
            continue
        remotes_by_local.setdefault(local, []).append(login)

    for port in ports:
        wwpn = port.get("wwpn") or ""
        logins = remotes_by_local.get(wwpn, [])
        port["logged_in_count"] = str(len(logins))
        port["remote_wwpns"] = "; ".join(
            sorted({login["remote_wwpn"] for login in logins if login.get("remote_wwpn")})
        )
        port["fabric_hosts"] = "; ".join(
            sorted({login["host_name"] for login in logins if login.get("host_name")})
        )

    # Host initiator WWPNs from fabric (name → remote_wwpn)
    host_wwpns: dict[str, set[str]] = {}
    for login in fabric:
        host = login.get("host_name") or ""
        remote = login.get("remote_wwpn") or ""
        if host and remote:
            host_wwpns.setdefault(host, set()).add(remote)

    for host in hosts:
        name = host.get("host_name") or ""
        wwpns = sorted(host_wwpns.get(name, set()))
        host["wwpns"] = "; ".join(wwpns)
        host["wwpn_count"] = str(len(wwpns))

    # Enrich mappings with host WWPNs
    for mapping in mappings:
        name = mapping.get("host_name") or ""
        mapping["host_wwpns"] = "; ".join(sorted(host_wwpns.get(name, set())))

    by_node: dict[str, list[dict[str, str]]] = {}
    for port in ports:
        node = port.get("node_name") or port.get("node_id") or "Unknown node"
        by_node.setdefault(node, []).append(port)

    return {
        "fc_ports": ports,
        "fc_hosts": hosts,
        "fc_mappings": mappings,
        "fc_fabric": fabric,
        "fc_ports_by_node": [
            {"node_name": node, "ports": node_ports}
            for node, node_ports in sorted(by_node.items(), key=lambda item: item[0].lower())
        ],
        "fc_available": bool(ports or hosts or mappings or fabric),
    }
