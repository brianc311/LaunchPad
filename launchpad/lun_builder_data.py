"""LUN Builder build seeds, normalization, expand, and validation helpers."""

from __future__ import annotations

import re
from typing import Any

from launchpad.storage_presets import (
    DEVICE_PROFILES,
    HP_3PAR_PROFILES,
    SVC_PROFILES,
)

LUN_BUILDS_SETTING = "lun_builds"

_LUN_BUILDER_PROFILE_KEYS: tuple[str, ...] = (
    "hpe_3par_8200",
    "hpe_3par_8450",
    "hpe_primera_600",
    "ibm_ds8884",
    "flashsystem_5200",
    "flashsystem_7200",
    "flashsystem_7300",
    "flashsystem_9200",
    "flashsystem_9500",
    "ibm_svc_2145",
    "ibm_storwize_v7000",
    "ibm_storwize_v7000_g2",
    "ibm_storwize_v7000_g3",
    "ibm_xiv_114",
    "ibm_xiv_gen3",
)

LUN_BUILDER_PROFILES: list[tuple[str, str]] = [
    (key, DEVICE_PROFILES[key]) for key in _LUN_BUILDER_PROFILE_KEYS
]

_LIVE_RUN_PROFILES = frozenset(
    SVC_PROFILES | HP_3PAR_PROFILES | frozenset({"hpe_primera_600"})
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")
# pconsps3 → (pcon, sps3). Require 2+ letters before digits so host1 is not split.
_SITE_HOST_RE = re.compile(r"^([A-Za-z]{3,4})([A-Za-z]{2,}\d+.*)$")


def supports_live_run(profile_key: str) -> bool:
    return str(profile_key or "").strip() in _LIVE_RUN_PROFILES


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    return text in ("1", "true", "yes", "y", "on")


def _normalize_count(value: Any) -> int:
    if value is None or value == "":
        return 1
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize_str_list(raw: Any) -> list[str]:
    if isinstance(raw, str):
        parts = [part.strip() for part in raw.replace(";", ",").split(",")]
        return [part for part in parts if part]
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def normalize_host_row(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    lpar_name = str(raw.get("lpar_name") or "").strip()
    if not lpar_name:
        return None
    slot_raw = raw.get("slot")
    slot = str(slot_raw).strip() if slot_raw is not None else ""
    remote_slot_raw = raw.get("remote_slot")
    remote_slot = (
        str(remote_slot_raw).strip() if remote_slot_raw is not None else ""
    )
    return {
        "lpar_name": lpar_name,
        "slot": slot,
        "state": str(raw.get("state") or "").strip(),
        "required": _as_bool(raw.get("required")),
        "type": str(raw.get("type") or "").strip(),
        "remote_lpar": str(raw.get("remote_lpar") or "").strip(),
        "remote_slot": remote_slot,
        "wwpn1": str(raw.get("wwpn1") or "").strip(),
        "wwpn2": str(raw.get("wwpn2") or "").strip(),
        "physical_fc_slot": str(raw.get("physical_fc_slot") or "").strip(),
        "managed_system_name": str(raw.get("managed_system_name") or "").strip(),
        "managed_system_serial": str(
            raw.get("managed_system_serial") or ""
        ).strip(),
        "notes": str(raw.get("notes") or "").strip(),
        "done": _as_bool(raw.get("done")),
    }


def normalize_lun_row(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    purpose = str(raw.get("purpose") or raw.get("name") or "").strip()
    return {
        "purpose": purpose,
        "count": _normalize_count(raw.get("count")),
        "size": str(raw.get("size") or "").strip(),
        "shared": _as_bool(raw.get("shared")),
        "storage_profile": str(raw.get("storage_profile") or "").strip(),
        "pool_or_cpg": str(raw.get("pool_or_cpg") or "").strip(),
        "host_names": _normalize_str_list(raw.get("host_names")),
        "scsi_or_lun_id": str(raw.get("scsi_or_lun_id") or "").strip(),
        "card_hint": str(raw.get("card_hint") or "").strip(),
        "cluster": str(raw.get("cluster") or raw.get("group") or "").strip(),
        "name_prefix": str(raw.get("name_prefix") or "").strip().rstrip("_"),
        "done": _as_bool(raw.get("done")),
    }


def _normalize_plan_done(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, dict):
        return {}
    return {
        str(key).strip(): True
        for key, value in raw.items()
        if str(key).strip() and _as_bool(value)
    }


def _normalize_command_done(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): True
        for key, value in raw.items()
        if str(key) and _as_bool(value)
    }


def normalize_build(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    build_id = str(raw.get("id") or "").strip()
    if not build_id:
        return None
    hosts_raw = raw.get("hosts") or []
    luns_raw = raw.get("luns") or []
    hosts: list[dict[str, Any]] = []
    if isinstance(hosts_raw, list):
        for item in hosts_raw:
            cleaned = normalize_host_row(item)
            if cleaned:
                hosts.append(cleaned)
    luns: list[dict[str, Any]] = []
    if isinstance(luns_raw, list):
        for item in luns_raw:
            cleaned = normalize_lun_row(item)
            if cleaned is not None:
                luns.append(cleaned)
    return {
        "id": build_id,
        "name": str(raw.get("name") or "").strip(),
        "location": str(raw.get("location") or "").strip(),
        "notes": str(raw.get("notes") or "").strip(),
        "updated_at": str(raw.get("updated_at") or "").strip(),
        "is_template": _as_bool(raw.get("is_template")),
        "default_storage_profile": str(raw.get("default_storage_profile") or "").strip(),
        "default_pool_or_cpg": str(raw.get("default_pool_or_cpg") or "").strip(),
        "default_card_hint": str(raw.get("default_card_hint") or "").strip(),
        "plan_done": _normalize_plan_done(raw.get("plan_done")),
        "command_done": _normalize_command_done(raw.get("command_done")),
        "hosts": hosts,
        "luns": luns,
    }


def normalize_builds(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        cleaned = normalize_build(item)
        if cleaned is not None:
            out.append(cleaned)
    return out


def _hartford_host(
    lpar_name: str,
    slot: int,
    remote_lpar: str,
    remote_slot: int,
    wwpn1: str,
    wwpn2: str,
    physical_fc_slot: str,
    managed_system_name: str,
    managed_system_serial: str,
) -> dict:
    return {
        "lpar_name": lpar_name,
        "slot": str(slot),
        "state": "Off",
        "required": False,
        "type": "client",
        "remote_lpar": remote_lpar,
        "remote_slot": str(remote_slot),
        "wwpn1": wwpn1,
        "wwpn2": wwpn2,
        "physical_fc_slot": physical_fc_slot,
        "managed_system_name": managed_system_name,
        "managed_system_serial": managed_system_serial,
        "notes": "",
    }


def _lun_batch(
    purpose: str,
    count: int,
    size: str,
    shared: bool,
    host_names: list[str],
    cluster: str,
    *,
    name_prefix: str = "pcon",
    storage_profile: str = "",
    pool_or_cpg: str = "",
    card_hint: str = "",
) -> dict:
    return {
        "purpose": purpose,
        "count": count,
        "size": size,
        "shared": shared,
        "storage_profile": storage_profile,
        "pool_or_cpg": pool_or_cpg,
        "host_names": host_names,
        "scsi_or_lun_id": "",
        "card_hint": card_hint,
        "cluster": cluster,
        "name_prefix": name_prefix,
    }


def _jupiter_host(lpar_name: str) -> dict:
    return {
        "lpar_name": lpar_name,
        "slot": "",
        "state": "",
        "required": False,
        "type": "Generic",
        "remote_lpar": "",
        "remote_slot": "",
        "wwpn1": "",
        "wwpn2": "",
        "physical_fc_slot": "",
        "managed_system_name": "",
        "managed_system_serial": "",
        "notes": "",
    }


def _pendergrass_host(lpar_name: str) -> dict:
    return {
        "lpar_name": lpar_name,
        "slot": "",
        "state": "",
        "required": False,
        "type": "Generic",
        "remote_lpar": "",
        "remote_slot": "",
        "wwpn1": "",
        "wwpn2": "",
        "physical_fc_slot": "",
        "managed_system_name": "",
        "managed_system_serial": "",
        "notes": "",
    }


def _mount_vernon_host(lpar_name: str, wwpn1: str = "", wwpn2: str = "") -> dict:
    return {
        "lpar_name": lpar_name,
        "slot": "",
        "state": "",
        "required": False,
        "type": "Generic",
        "remote_lpar": "",
        "remote_slot": "",
        "wwpn1": wwpn1,
        "wwpn2": wwpn2,
        "physical_fc_slot": "",
        "managed_system_name": "",
        "managed_system_serial": "",
        "notes": "",
    }


def _windsor_host(lpar_name: str, wwpn1: str = "", wwpn2: str = "") -> dict:
    return {
        "lpar_name": lpar_name,
        "slot": "",
        "state": "",
        "required": False,
        "type": "Generic",
        "remote_lpar": "",
        "remote_slot": "",
        "wwpn1": wwpn1,
        "wwpn2": wwpn2,
        "physical_fc_slot": "",
        "managed_system_name": "",
        "managed_system_serial": "",
        "notes": "",
    }


def _woodland_hills_host(lpar_name: str) -> dict:
    return {
        "lpar_name": lpar_name,
        "slot": "",
        "state": "",
        "required": False,
        "type": "Generic",
        "remote_lpar": "",
        "remote_slot": "",
        "wwpn1": "",
        "wwpn2": "",
        "physical_fc_slot": "",
        "managed_system_name": "",
        "managed_system_serial": "",
        "notes": "",
    }


def seed_lun_builder_templates() -> list[dict]:
    hosts = [
        _hartford_host("pconsps3", 5, "pconvio01b", 17, "c050760c9594000e", "c050760c9594000f", "U78DA.ND0.WZS05WT-P0-C7-T0", "F_PCONSLS3-9105-22A-78A9F81", "78A9F81"),
        _hartford_host("pconsps3", 4, "pconvio01a", 14, "c050760c9594000c", "c050760c9594000d", "U78DA.ND0.WZS05WT-P0-C1-T0", "F_PCONSLS3-9105-22A-78A9F81", "78A9F81"),
        _hartford_host("pconsps3", 3, "pconvio01b", 16, "c050760c9594000a", "c050760c9594000b", "U78DA.ND0.WZS05WT-P0-C7-T1", "F_PCONSLS3-9105-22A-78A9F81", "78A9F81"),
        _hartford_host("pconsps3", 2, "pconvio01a", 10, "c050760c95940008", "c050760c95940009", "U78DA.ND0.WZS05WT-P0-C1-T1", "F_PCONSLS3-9105-22A-78A9F81", "78A9F81"),
        _hartford_host("pconsps4", 5, "pconvio10b", 22, "c050760c95750012", "c050760c95750013", "U78DA.ND0.WZS05WS-P0-C7-T0", "F_PCONSLS5-9105-22A-78A9F71", "78A9F71"),
        _hartford_host("pconsps4", 4, "pconvio10a", 16, "c050760c95750010", "c050760c95750011", "U78DA.ND0.WZS05WS-P0-C1-T1", "F_PCONSLS5-9105-22A-78A9F71", "78A9F71"),
        _hartford_host("pconsps4", 3, "pconvio10b", 21, "c050760c9575000e", "c050760c9575000f", "U78DA.ND0.WZS05WS-P0-C7-T1", "F_PCONSLS5-9105-22A-78A9F71", "78A9F71"),
        _hartford_host("pconsps4", 2, "pconvio10a", 15, "c050760c9575000c", "c050760c9575000d", "U78DA.ND0.WZS05WS-P0-C1-T0", "F_PCONSLS5-9105-22A-78A9F71", "78A9F71"),
        _hartford_host("pconmfs3", 5, "pconvio02a", 10, "c050760c95930006", "c050760c95930007", "U78DA.ND0.WZS05T5-P0-C1-T0", "F_PCONSLS4-9105-22A-78A9FA1", "78A9FA1"),
        _hartford_host("pconmfs3", 4, "pconvio02b", 10, "c050760c95930004", "c050760c95930005", "U78DA.ND0.WZS05T5-P0-C7-T0", "F_PCONSLS4-9105-22A-78A9FA1", "78A9FA1"),
        _hartford_host("pconmfs3", 3, "pconvio02a", 9, "c050760c95930002", "c050760c95930003", "U78DA.ND0.WZS05T5-P0-C1-T1", "F_PCONSLS4-9105-22A-78A9FA1", "78A9FA1"),
        _hartford_host("pconmfs3", 2, "pconvio02b", 9, "c050760c95930000", "c050760c95930001", "U78DA.ND0.WZS05T5-P0-C7-T1", "F_PCONSLS4-9105-22A-78A9FA1", "78A9FA1"),
        _hartford_host("pconmfs4", 5, "pconvio09a", 4, "c050760aea77003e", "c050760aea77003f", "U78D3.001.WZS04TS-P1-C2-T1", "F_PCONSLS2-9009-22A-783CDF0", "783CDF0"),
        _hartford_host("pconmfs4", 4, "pconvio09b", 4, "c050760aea77003c", "c050760aea77003d", "U78D3.001.WZS04TS-P1-C8-T1", "F_PCONSLS2-9009-22A-783CDF0", "783CDF0"),
        _hartford_host("pconmfs4", 3, "pconvio09a", 3, "c050760aea77003a", "c050760aea77003b", "U78D3.001.WZS04TS-P1-C2-T2", "F_PCONSLS2-9009-22A-783CDF0", "783CDF0"),
        _hartford_host("pconmfs4", 2, "pconvio09b", 3, "c050760aea770038", "c050760aea770039", "U78D3.001.WZS04TS-P1-C8-T2", "F_PCONSLS2-9009-22A-783CDF0", "783CDF0"),
        _hartford_host("pconbt3", 6, "pconvio10b", 17, "c050760c9575000a", "c050760c9575000b", "U78DA.ND0.WZS05WS-P0-C7-T3", "F_PCONSLS5-9105-22A-78A9F71", "78A9F71"),
        _hartford_host("pconbt3", 5, "pconvio10a", 14, "c050760c95750008", "c050760c95750009", "U78DA.ND0.WZS05WS-P0-C1-T1", "F_PCONSLS5-9105-22A-78A9F71", "78A9F71"),
        _hartford_host("pconbt3", 4, "pconvio10b", 16, "c050760c95750006", "c050760c95750007", "U78DA.ND0.WZS05WS-P0-C7-T1", "F_PCONSLS5-9105-22A-78A9F71", "78A9F71"),
        _hartford_host("pconbt3", 3, "pconvio10a", 2, "c050760c95750004", "c050760c95750005", "U78DA.ND0.WZS05WS-P0-C1-T0", "F_PCONSLS5-9105-22A-78A9F71", "78A9F71"),
        _hartford_host("pconbt4", 5, "pconvio01b", 15, "c050760c95940006", "c050760c95940007", "U78DA.ND0.WZS05WT-P0-C7-T1", "F_PCONSLS3-9105-22A-78A9F81", "78A9F81"),
        _hartford_host("pconbt4", 4, "pconvio01a", 9, "c050760c95940004", "c050760c95940005", "U78DA.ND0.WZS05WT-P0-C1-T1", "F_PCONSLS3-9105-22A-78A9F81", "78A9F81"),
        _hartford_host("pconbt4", 3, "pconvio01b", 10, "c050760c95940002", "c050760c95940003", "U78DA.ND0.WZS05WT-P0-C7-T0", "F_PCONSLS3-9105-22A-78A9F81", "78A9F81"),
        _hartford_host("pconbt4", 2, "pconvio01a", 8, "c050760c95940000", "c050760c95940001", "U78DA.ND0.WZS05WT-P0-C1-T0", "F_PCONSLS3-9105-22A-78A9F81", "78A9F81"),
    ]
    luns: list[dict] = []
    cluster_specs = (
        ("SPS", ["pconsps3", "pconsps4"], 7, 2, "200GB", "sps1redovg1", "sps1redovg2"),
        ("MFS", ["pconmfs3", "pconmfs4"], 7, 1, "200GB", "mfs1redovg1", "mfs1redovg2"),
        ("BT", ["pconbt3", "pconbt4"], 14, 2, "100GB", "btfs1redovg1", "btfs2redovg2"),
    )
    for cluster, host_names, ora_count, arch_count, arch_size, redo1, redo2 in cluster_specs:
        luns.extend(
            _lun_batch("root", 3, "50GB", False, [host_name], cluster)
            for host_name in host_names
        )
        luns.extend(
            [
                _lun_batch("ora1vg", ora_count, "100GB", True, host_names, cluster),
                _lun_batch("archvg", arch_count, arch_size, True, host_names, cluster),
                _lun_batch(redo1, 1, "100GB", True, host_names, cluster),
                _lun_batch(redo2, 1, "100GB", True, host_names, cluster),
                _lun_batch("caavg_private", 1, "10GB", True, host_names, cluster),
            ]
        )
    jup_hosts = [
        _jupiter_host(name)
        for name in (
            "pjupvio01a",
            "pjupvio01b",
            "pjupvio02a",
            "pjupvio02b",
            "pjupvio03a",
            "pjupvio03b",
            "pjupvio04a",
            "pjupvio04b",
            "pjupmhcdb2",
            "pjupmhcdg2",
            "pjupres01",
        )
    ]
    jup_kwargs = {
        "name_prefix": "pjup",
        "storage_profile": "flashsystem_5200",
        "pool_or_cpg": "JUP_G3_Pool",
        "card_hint": "Jupiter, FL",
    }
    jup_luns: list[dict] = []
    for vio in (
        "pjupvio01a",
        "pjupvio01b",
        "pjupvio02a",
        "pjupvio02b",
        "pjupvio03a",
        "pjupvio03b",
        "pjupvio04a",
        "pjupvio04b",
    ):
        jup_luns.append(_lun_batch("root", 2, "100GB", False, [vio], "vio", **jup_kwargs))
    for db_host in ("pjupmhcdb2", "pjupmhcdg2"):
        jup_luns.append(_lun_batch("root", 3, "50GB", False, [db_host], "db", **jup_kwargs))
        jup_luns.append(_lun_batch("data", 9, "100GB", False, [db_host], "db", **jup_kwargs))
    jup_luns.append(_lun_batch("data", 5, "100GB", False, ["pjupres01"], "res", **jup_kwargs))

    pen_hosts = [
        _pendergrass_host(name)
        for name in ("pen_penesx_vm05", "pen_penesx_vm06")
    ]
    pen_kwargs = {
        "name_prefix": "PEN",
        "storage_profile": "flashsystem_5200",
        "pool_or_cpg": "G3_PEN_Pool1",
        "card_hint": "Pendergrass, GA",
    }
    pen_both = ["pen_penesx_vm05", "pen_penesx_vm06"]
    pen_luns = [
        _lun_batch("ESX_VOL", 3, "2TB", True, pen_both, "esx", **pen_kwargs),
        _lun_batch("ESX_VOL", 1, "4TB", True, pen_both, "esx", **pen_kwargs),
        _lun_batch("ESX_VOL_COREDUMP", 1, "100GB", True, pen_both, "esx", **pen_kwargs),
    ]

    mtv_hosts = [
        _mount_vernon_host("amv1_as400", "C050760B552B0004", "C050760B552B0006"),
        _mount_vernon_host("amv1_as400", "C050760B552B0010", ""),
        _mount_vernon_host("pen-mtvesx-vm01", "51402EC012434DDC", "51402EC012434DDE"),
        _mount_vernon_host("pen-mtvesx-vm02", "51402EC012435D38", "51402EC012435D3A"),
        _mount_vernon_host("pen-mtvesx-vm03", "51402EC01243643C", "51402EC01243643E"),
        _mount_vernon_host("pmtvvio01a", "21000024FF85BB40", "21000024FF85BB41"),
        _mount_vernon_host("pmtvvio01b", "21000024FF85F054", "21000024FF85F055"),
        _mount_vernon_host("pmtvvio02a", "21000024FF860A60", "21000024FF860A61"),
        _mount_vernon_host("pmtvvio02b", "21000024FF86373E", "21000024FF86373F"),
        _mount_vernon_host("tmtvtst1", "C050760B20CA0008", "C050760B20CA000A"),
        _mount_vernon_host("tmtvtst1", "C050760B20CA000C", "C050760B20CA000E"),
    ]
    mtv_kwargs = {
        "storage_profile": "flashsystem_5200",
        "pool_or_cpg": "MtVerno_Pool1",
        "card_hint": "Mount Vernon, IL",
    }
    mtv_esx = ["pen-mtvesx-vm01", "pen-mtvesx-vm02", "pen-mtvesx-vm03"]
    mtv_luns: list[dict] = [
        _lun_batch(
            "AS400", 10, "500GB", True, ["amv1_as400"], "",
            name_prefix="AVM1", **mtv_kwargs,
        ),
        _lun_batch(
            "ESXI_DS", 4, "4TB", True, mtv_esx, "",
            name_prefix="MTV", **mtv_kwargs,
        ),
    ]
    for vio in ("pmtvvio01a", "pmtvvio01b", "pmtvvio02a", "pmtvvio02b"):
        mtv_luns.append(
            _lun_batch(
                "root", 2, "100GB", False, [vio], "vio",
                name_prefix="pmtv", **mtv_kwargs,
            )
        )
    mtv_luns.append(
        _lun_batch(
            "root", 3, "100GB", False, ["tmtvtst1"], "test",
            name_prefix="", **mtv_kwargs,
        )
    )

    win_hosts = [
        _windsor_host("AWN1", "C050760B518B0000", "C050760B518B0002"),
        _windsor_host("AWN1", "C050760B518B0004", "C050760B518B0006"),
        _windsor_host("PEN_WINESX_VM01", "51402EC012CFD072", "51402EC012CFD2BE"),
        _windsor_host("PEN_WINESX_VM02", "51402EC012CFD090", "51402EC012CFD2C4"),
        _windsor_host("PEN_WINESX_VM03", "51402EC012C90280", "51402EC012C904A4"),
        _windsor_host("pwinap01", "", ""),
        _windsor_host("pwinmq01", "C050760B53990018", "C050760B5399001A"),
        _windsor_host("pwinmq01", "C050760B5399001C", "C050760B5399001E"),
        _windsor_host("pwinvio01a", "21000024FF86027C", "21000024FF86027D"),
        _windsor_host("pwinvio01b", "21000024FF86025C", "21000024FF86025D"),
        _windsor_host("pwinvio01b", "21000024FF86025E", ""),
        _windsor_host("pwinvio02a", "21000024FF860A7C", "21000024FF860A7D"),
        _windsor_host("pwinvio02b", "21000024FF86048C", "21000024FF86048D"),
        _windsor_host("pwinvio02b", "21000024FF86048E", ""),
    ]
    win_kwargs = {
        "storage_profile": "flashsystem_5200",
        "pool_or_cpg": "Windsor_G3_Pool0",
        "card_hint": "Windsor, WI",
    }
    win_esx = ["PEN_WINESX_VM01", "PEN_WINESX_VM02", "PEN_WINESX_VM03"]
    win_luns: list[dict] = [
        _lun_batch(
            "AWN1", 6, "500GB", True, ["AWN1"], "",
            name_prefix="AS400", **win_kwargs,
        ),
        _lun_batch(
            "ESX_DataStore", 3, "4TB", True, win_esx, "",
            name_prefix="WIN", **win_kwargs,
        ),
        _lun_batch(
            "root", 3, "50GB", False, ["pwinap01"], "app",
            name_prefix="pwin", **win_kwargs,
        ),
        _lun_batch(
            "data", 2, "100GB", False, ["pwinap01"], "app",
            name_prefix="pwin", **win_kwargs,
        ),
        _lun_batch(
            "root", 3, "50GB", False, ["pwinmq01"], "mq",
            name_prefix="pwin", **win_kwargs,
        ),
    ]
    for vio in ("pwinvio01a", "pwinvio02a", "pwinvio02b"):
        win_luns.append(
            _lun_batch(
                "root", 2, "100GB", False, [vio], "vio",
                name_prefix="pwin", **win_kwargs,
            )
        )
    win_luns.append(
        _lun_batch(
            "root", 5, "100GB", False, ["pwinvio01b"], "vio",
            name_prefix="pwin", **win_kwargs,
        )
    )

    woo_hosts = [
        _woodland_hills_host("AWD1_New_as400"),
        _woodland_hills_host("AWD1_New_as400"),
        _woodland_hills_host("AWD1_New_as400"),
        _woodland_hills_host("AWD1_New_as400"),
        _woodland_hills_host("PEN-WODESX-VM01"),
        _woodland_hills_host("PEN-WODESX-VM02"),
        _woodland_hills_host("PEN-WODESX-VM03"),
        _woodland_hills_host("PEN-WODESX-VM04"),
        _woodland_hills_host("pwoovio01a"),
        _woodland_hills_host("pwoovio01b"),
        _woodland_hills_host("pwoovio02a"),
        _woodland_hills_host("pwoovio02b"),
    ]
    woo_kwargs = {
        "storage_profile": "flashsystem_5200",
        "pool_or_cpg": "WOO_Pool1",
        "card_hint": "Woodland Hills, CA",
    }
    woo_esx = [
        "PEN-WODESX-VM01",
        "PEN-WODESX-VM02",
        "PEN-WODESX-VM03",
        "PEN-WODESX-VM04",
    ]
    woo_luns: list[dict] = [
        _lun_batch(
            "AS400", 6, "500GB", True, ["AWD1_New_as400"], "",
            name_prefix="AWD1", **woo_kwargs,
        ),
        _lun_batch(
            "ESX_DataStore", 4, "4TB", True, woo_esx, "",
            name_prefix="WOO", **woo_kwargs,
        ),
    ]
    for vio in ("pwoovio01a", "pwoovio01b", "pwoovio02a", "pwoovio02b"):
        woo_luns.append(
            _lun_batch(
                "root", 2, "100GB", False, [vio], "vio",
                name_prefix="pwoo", **woo_kwargs,
            )
        )

    return [
        {
            "id": "template-hartford-ct",
            "name": "Hartford, CT (Template)",
            "location": "Hartford, CT",
            "notes": (
                "Seeded from Connecticut New Hosts / WWPN planning sheet. "
                "Set storage profile and pool/CPG before Preview or Run Create."
            ),
            "is_template": True,
            "hosts": hosts,
            "luns": luns,
        },
        {
            "id": "template-jupiter-fl",
            "name": "Jupiter, FL (Template)",
            "location": "Jupiter, FL",
            "notes": (
                "Seeded from Jupiter FlashSystem 5200 inventory. "
                "WWPNs are blank — set Port Definitions / Pull from FC WWPN before create. "
                "Defaults use card hint Jupiter, FL, profile flashsystem_5200, pool JUP_G3_Pool."
            ),
            "is_template": True,
            "default_storage_profile": "flashsystem_5200",
            "default_pool_or_cpg": "JUP_G3_Pool",
            "default_card_hint": "Jupiter, FL",
            "hosts": jup_hosts,
            "luns": jup_luns,
        },
        {
            "id": "template-pendergrass-ga",
            "name": "Pendergrass, GA (Template)",
            "location": "Pendergrass, GA",
            "notes": (
                "Seeded from Pendergrass FlashSystem 5200 inventory. "
                "WWPNs are blank — set Port Definitions / Pull from FC WWPN before create. "
                "Defaults use card hint Pendergrass, GA, profile flashsystem_5200, pool G3_PEN_Pool1."
            ),
            "is_template": True,
            "default_storage_profile": "flashsystem_5200",
            "default_pool_or_cpg": "G3_PEN_Pool1",
            "default_card_hint": "Pendergrass, GA",
            "hosts": pen_hosts,
            "luns": pen_luns,
        },
        {
            "id": "template-mount-vernon-il",
            "name": "Mount Vernon, IL (Template)",
            "location": "Mount Vernon, IL",
            "notes": (
                "Seeded from Mount Vernon FlashSystem 5200 inventory. "
                "Active Port Definition WWPNs are filled; Offline ports omitted. "
                "Defaults use card hint Mount Vernon, IL, profile flashsystem_5200, pool MtVerno_Pool1."
            ),
            "is_template": True,
            "default_storage_profile": "flashsystem_5200",
            "default_pool_or_cpg": "MtVerno_Pool1",
            "default_card_hint": "Mount Vernon, IL",
            "hosts": mtv_hosts,
            "luns": mtv_luns,
        },
        {
            "id": "template-windsor-wi",
            "name": "Windsor, WI (Template)",
            "location": "Windsor, WI",
            "notes": (
                "Seeded from Windsor FlashSystem 5200 inventory (Windsor_Cluster site). "
                "Active Port Definition WWPNs are filled except pwinap01 (blank). "
                "Offline ports omitted. Defaults use card hint Windsor, WI, "
                "profile flashsystem_5200, pool Windsor_G3_Pool0."
            ),
            "is_template": True,
            "default_storage_profile": "flashsystem_5200",
            "default_pool_or_cpg": "Windsor_G3_Pool0",
            "default_card_hint": "Windsor, WI",
            "hosts": win_hosts,
            "luns": win_luns,
        },
        {
            "id": "template-woodland-hills-ca",
            "name": "Woodland Hills, CA (Template)",
            "location": "Woodland Hills, CA",
            "notes": (
                "Seeded from Woodland Hills FlashSystem 5200 inventory. "
                "WWPNs are blank — set Port Definitions / Pull from FC WWPN before create. "
                "Defaults use card hint Woodland Hills, CA, profile flashsystem_5200, "
                "pool WOO_Pool1."
            ),
            "is_template": True,
            "default_storage_profile": "flashsystem_5200",
            "default_pool_or_cpg": "WOO_Pool1",
            "default_card_hint": "Woodland Hills, CA",
            "hosts": woo_hosts,
            "luns": woo_luns,
        },
    ]


def upsert_build(builds: list[dict], build: dict) -> list[dict]:
    build_id = str(build.get("id") or "").strip()
    result: list[dict] = []
    replaced = False
    for existing in builds:
        if str(existing.get("id") or "").strip() == build_id:
            result.append(build)
            replaced = True
        else:
            result.append(existing)
    if not replaced:
        result.append(build)
    return result


def delete_build(builds: list[dict], build_id: str) -> list[dict]:
    target = str(build_id or "").strip()
    return [b for b in builds if str(b.get("id") or "").strip() != target]


def _slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug or "build"


def new_build_id(name: str, existing: list[dict]) -> str:
    taken = {str(b.get("id") or "").strip() for b in existing}
    base = _slugify(name)
    candidate = base
    suffix = 2
    while candidate in taken:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _infer_site_prefix(host_names: list[str]) -> str:
    """Infer a short site prefix from host names (e.g. pconsps3 → pcon)."""
    for host in host_names:
        match = _SITE_HOST_RE.match(host)
        if match:
            return match.group(1).lower()
    return ""


def _volume_name_base(lun: dict, purpose: str) -> str | None:
    """Build a unique stem for expanded volume names.

    Site prefix and host/cluster qualifier are joined without an underscore
    (pconsps3_root, pconmfs_ora1vg), then purpose is appended with ``_``.
    Returns None only when there is no host/cluster/prefix context.
    """
    host_names = _normalize_str_list(lun.get("host_names"))
    prefix = str(lun.get("name_prefix") or "").strip().rstrip("_")
    if not prefix:
        prefix = _infer_site_prefix(host_names)
    cluster = str(lun.get("cluster") or "").strip().lower()
    shared = _as_bool(lun.get("shared"))
    head = ""
    if not shared and len(host_names) == 1:
        host = host_names[0]
        if prefix and host.lower().startswith(prefix.lower()):
            short = host[len(prefix) :].lstrip("_-")
            head = f"{prefix}{short}" if short else host
        elif prefix:
            head = f"{prefix}{host}"
        else:
            head = host
    elif cluster:
        head = f"{prefix}{cluster}" if prefix else cluster
    elif prefix:
        head = prefix
    else:
        return None
    return f"{head}_{purpose}"


def expand_lun_batch(lun: dict) -> list[dict]:
    purpose = str(lun.get("purpose") or "").strip()
    count = _normalize_count(lun.get("count"))
    if count < 1:
        count = 1
    size = str(lun.get("size") or "").strip()
    pool_or_cpg = str(lun.get("pool_or_cpg") or "").strip()
    shared = _as_bool(lun.get("shared"))
    storage_profile = str(lun.get("storage_profile") or "").strip()
    host_names = _normalize_str_list(lun.get("host_names"))
    scsi_or_lun_id = str(lun.get("scsi_or_lun_id") or "").strip()
    card_hint = str(lun.get("card_hint") or "").strip()
    cluster = str(lun.get("cluster") or "").strip()
    base = _volume_name_base(lun, purpose)
    rows: list[dict] = []
    for index in range(count):
        if base is not None:
            if count == 1:
                name = base
            else:
                name = f"{base}_{index + 1}"
        elif count == 1:
            name = purpose
        else:
            name = f"{purpose}_{index + 1}"
        rows.append(
            {
                "name": name,
                "size": size,
                "pool_or_cpg": pool_or_cpg,
                "shared": shared,
                "storage_profile": storage_profile,
                "host_names": list(host_names),
                "scsi_or_lun_id": scsi_or_lun_id,
                "card_hint": card_hint,
                "cluster": cluster,
                "source_batch": purpose,
            }
        )
    return rows


def validate_build_for_preview(build: dict | None) -> list[str]:
    if not isinstance(build, dict):
        return ["Build is required."]
    messages: list[str] = []
    luns = build.get("luns") or []
    if not luns:
        messages.append("At least one LUN spec is required.")
        return messages
    for index, lun in enumerate(luns, start=1):
        if not isinstance(lun, dict):
            messages.append(f"LUN row {index}: invalid row.")
            continue
        prefix = f"LUN row {index}"
        purpose = str(lun.get("purpose") or "").strip()
        if not purpose:
            messages.append(f"{prefix}: purpose is required.")
        count = lun.get("count")
        try:
            count_value = int(count)
        except (TypeError, ValueError):
            count_value = 0
        if count_value < 1:
            messages.append(f"{prefix}: count must be at least 1.")
        if not str(lun.get("size") or "").strip():
            messages.append(f"{prefix}: size is required.")
        if not str(lun.get("pool_or_cpg") or "").strip():
            messages.append(f"{prefix}: pool_or_cpg is required.")
        if not str(lun.get("storage_profile") or "").strip():
            messages.append(f"{prefix}: storage_profile is required.")
    return messages
