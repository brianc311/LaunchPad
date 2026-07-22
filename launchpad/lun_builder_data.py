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
        "exact_name": _as_bool(raw.get("exact_name")),
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
    exact_name: bool = False,
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
        "exact_name": exact_name,
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


def _anderson_host(lpar_name: str, wwpn1: str = "", wwpn2: str = "") -> dict:
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

    and_kwargs = {
        "storage_profile": "flashsystem_7200",
        "pool_or_cpg": "G3_AND_Pool",
        "card_hint": "Williamston (Anderson)",
    }
    and_host_names = sorted(
        (
            "AAN1", "AAN1C", "FC_AAN1",
            "BIB_ADC_VM01", "BIB_ADC_VM02",
            "pen_andesx_vm03", "pen_andesx_vm04",
            "pla-wanoemcr01", "pla-wanoemcr02",
            "pandvio01a", "pandvio01b", "pandvio02a", "pandvio02b",
            "pandvio03a", "pandvio03b", "pandvio04a", "pandvio04b",
            "pandvio05a", "pandvio05b", "pandvio06a", "pandvio06b",
            "pandvio07a", "pandvio07b", "pandvio08a", "pandvio08b",
            "pandvio09a", "pandvio09b", "pandvio10a", "pandvio10b",
            "pandap01", "pandap02",
            "pandbt1", "pandbt2", "pandbt3", "pandbt4", "pandbtdg1",
            "panddb01", "panddb02",
            "pandmfs1", "pandmfs2", "pandmfs3", "pandmfs4", "pandmfs10", "pandmfsdg1",
            "pandnim01",
            "pandps1", "pandps2", "pandps3", "pandps4", "pandpspdg1",
            "pandpspa1", "pandpspa2",
            "dandmfs1",
            "tandbt1", "tandbt20",
            "tandmfs1", "tandmfs2", "tandmfs20",
            "tandsps1", "tandsps2", "tandsps20", "tandsps21",
            "tconbt20", "tconmfs20", "tconsps20", "tconsps21",
            "TLA_WANMFS01", "TLA_WANMFS02",
        )
    )
    and_hosts = [_anderson_host(name) for name in and_host_names]
    and_luns: list[dict] = []
    for stem, count, size, host_name in (
        ("aan1", 28, "120GB", "AAN1"),
        ("AAN1C", 4, "125GB", "AAN1C"),
        ("FC_AAN1", 28, "120GB", "FC_AAN1"),
    ):
        and_luns.extend(
            _lun_batch(
                f"{stem}_{index}", 1, size, False, [host_name], "",
                name_prefix="", exact_name=True, **and_kwargs,
            )
            for index in range(count)
        )

    esx_hosts = ["pen_andesx_vm03", "pen_andesx_vm04"]
    for volume_name, size in (
        ("ADC-Data01", "1023GB"),
        ("ADC-Data02", "4TB"),
        ("ADC-Data03", "4TB"),
        ("Andesx-DS01", "4TB"),
        ("Andesx-DS02", "4TB"),
        ("Andesx-DS03", "4TB"),
        ("RHEL-Networker01", "100GB"),
    ):
        and_luns.append(
            _lun_batch(
                volume_name, 1, size, True, esx_hosts, "",
                name_prefix="", exact_name=True, **and_kwargs,
            )
        )

    for index in range(5):
        and_luns.append(
            _lun_batch(
                f"pandap01_{index}", 1, "70GB" if index < 4 else "50GB",
                False, ["pandap01"], "", name_prefix="", exact_name=True,
                **and_kwargs,
            )
        )

    oem_hosts = ["pla-wanoemcr01", "pla-wanoemcr02"]
    for name_pattern, count, size in (
        ("pla-wanoemcr01_02_5GB{}", 20, "5GB"),
        ("pla-wanoemcr01_02_250GB{}", 10, "250GB"),
        ("pla-wanoemcr01_02_300GB_{}", 5, "300GB"),
        ("pla-wanoemcr01_02_50{}", 4, "50GB"),
        ("pla-wanoemcr01_02_FRA_{}", 4, "40GB"),
        ("pla-wanoemcr01_02_data_{}", 8, "50GB"),
        ("pla-wanoemcr01_02_redo_{}", 10, "10GB"),
    ):
        and_luns.extend(
            _lun_batch(
                name_pattern.format(index), 1, size, True, oem_hosts, "",
                name_prefix="", exact_name=True, **and_kwargs,
            )
            for index in range(1, count + 1)
        )

    def add_and_exact(
        name: str,
        size: str,
        host_names: list[str],
        *,
        shared: bool | None = None,
    ) -> None:
        and_luns.append(
            _lun_batch(
                name,
                1,
                size,
                len(host_names) > 1 if shared is None else shared,
                host_names,
                "",
                name_prefix="",
                exact_name=True,
                **and_kwargs,
            )
        )

    def add_and_numbered(
        stem: str,
        indexes: range | tuple[int, ...],
        size: str,
        host_names: list[str],
        *,
        shared: bool | None = None,
    ) -> None:
        for index in indexes:
            add_and_exact(
                f"{stem}{index}",
                size,
                host_names,
                shared=shared,
            )

    add_and_exact("Test_VMware_Lun", "100GB", ["BIB_ADC_VM01"])

    tla_hosts = ["TLA_WANMFS01", "TLA_WANMFS02"]
    for stem, indexes, size in (
        ("TLA-WANMFS01_02_5GB", range(1, 21), "5GB"),
        ("TLA-WANMFS01_02_50GB_", range(1, 5), "50GB"),
        ("TLA-WANMFS01_02_250GB_", range(1, 11), "250GB"),
        ("TLA-WANMFS01_02_500GB", range(1, 6), "300GB"),
    ):
        add_and_numbered(stem, indexes, size, tla_hosts)

    add_and_numbered("dandmfs1_", range(14), "100GB", ["dandmfs1"])
    for name, size in (
        ("pandap02_0", "70GB"),
        ("pandap02_1", "70GB"),
        ("pandap02_2", "70GB"),
        ("pandap02_03", "100GB"),
        ("pandap02_04", "100GB"),
    ):
        add_and_exact(name, size, ["pandap02"])

    pandbt12 = ["pandbt1", "pandbt2"]
    add_and_numbered(
        "Pandbt_1_2_shared_ORAEX_",
        range(1, 6),
        "200GB",
        pandbt12,
    )
    for host in pandbt12:
        add_and_numbered(f"{host}_", range(3), "100GB", [host])
    add_and_exact("pandbt_1_2_HA", "10GB", pandbt12)
    add_and_numbered(
        "pandbt_1_2_shared_",
        tuple(range(1, 19)) + tuple(range(20, 27)),
        "64GB",
        pandbt12,
    )
    add_and_exact("pandbt_1_2_shared_19", "1GB", pandbt12)
    add_and_numbered(
        "pandbt_1_2_shared_",
        range(27, 31),
        "50GB",
        pandbt12,
    )
    add_and_numbered(
        "pandbt_1_2_shared_",
        range(31, 37),
        "100GB",
        pandbt12,
    )

    pandbt34 = ["pandbt3", "pandbt4"]
    add_and_numbered("PANDBT3_ROOT_", range(1, 4), "50GB", ["pandbt3"])
    add_and_numbered("PANDBT4_ROOT_", range(1, 4), "50GB", ["pandbt4"])
    add_and_numbered(
        "PANDBT_3_4_ARCHVG_SHARED_",
        range(1, 4),
        "100GB",
        pandbt34,
    )
    add_and_numbered(
        "PANDBT_3_4_BTFS1REDOVG_SHARED_",
        range(1, 3),
        "100GB",
        pandbt34,
    )
    add_and_numbered(
        "PANDBT_3_4_DATA_SHARED_",
        range(1, 22),
        "100GB",
        pandbt34,
    )
    add_and_exact("PANDBT_3_4_REPO_CAAVG_SHARED", "10GB", pandbt34)
    add_and_numbered(
        "Pandbt_3_4_shared_ORAEX_",
        range(1, 6),
        "200GB",
        pandbt34,
    )
    add_and_numbered(
        "tandbt20_clone",
        range(3),
        "100GB",
        pandbt34,
    )

    add_and_numbered("pandbtdg1_", range(3), "72GB", ["pandbtdg1"])
    add_and_numbered(
        "pandbtdg1_dg_",
        tuple(range(1, 19)) + tuple(range(20, 27)),
        "64GB",
        ["pandbtdg1"],
    )
    add_and_numbered(
        "pandbtdg1_dg_",
        range(27, 31),
        "50GB",
        ["pandbtdg1"],
    )
    add_and_numbered("panddb01_", range(21), "70GB", ["panddb01"])
    add_and_numbered("panddb02_", range(3), "70GB", ["panddb02"])

    pandmfs12 = ["pandmfs1", "pandmfs2"]
    for host in pandmfs12:
        add_and_numbered(f"{host}_", range(3), "100GB", [host])
    add_and_exact("pandmfs_1_2_HA", "10GB", pandmfs12)
    add_and_exact("pandmfs_1_2_shared_1", "20GB", pandmfs12)
    add_and_numbered(
        "pandmfs_1_2_shared_",
        (2, 3, 4, 5, 7, 8, 11, 12, 14, 15, 16),
        "64GB",
        pandmfs12,
    )
    add_and_exact("pandmfs_1_2_shared_17", "20GB", pandmfs12)
    add_and_numbered(
        "pandmfs_1_2_shared_",
        (18, 19),
        "100GB",
        pandmfs12,
    )

    for index, size in (
        (1, "72GB"),
        (2, "72GB"),
        (3, "72GB"),
        (4, "100GB"),
        (5, "100GB"),
        (6, "100GB"),
        (7, "100GB"),
        (8, "100GB"),
    ):
        add_and_exact(f"pandmfs10_0{index}", size, ["pandmfs10"])
    add_and_numbered("pandmfs10_asm", range(7), "100GB", ["pandmfs10"])

    pandmfs34 = ["pandmfs3", "pandmfs4"]
    add_and_numbered("PANDMFS3_ROOT_", range(1, 4), "50GB", ["pandmfs3"])
    add_and_numbered("PANDMFS4_ROOT_", range(1, 4), "50GB", ["pandmfs4"])
    add_and_numbered(
        "PANDMFS_3_4_ARCHVG_SHARED_",
        range(1, 3),
        "100GB",
        pandmfs34,
    )
    add_and_numbered(
        "PANDMFS_3_4_MFS1REDOVG_SHARED_",
        range(1, 3),
        "50GB",
        pandmfs34,
    )
    add_and_numbered(
        "PANDMFS_3_4_ORA1VG_SHARED_",
        range(1, 9),
        "100GB",
        pandmfs34,
    )
    add_and_exact("PANDMFS_3_4_REPO_CAAVG_SHARED", "10GB", pandmfs34)
    add_and_numbered(
        "tandmfs20_clone",
        range(3),
        "100GB",
        pandmfs34,
    )

    add_and_numbered(
        "pandmfs_dg_mast_",
        (1, 17),
        "20GB",
        ["pandmfsdg1"],
    )
    add_and_numbered(
        "pandmfs_dg_mast_",
        (2, 3, 4, 5, 7, 8, 11, 12, 14, 15, 16),
        "64GB",
        ["pandmfsdg1"],
    )
    add_and_numbered("pandmfsdg1_", range(3), "72GB", ["pandmfsdg1"])

    for name in (
        "Pandnim01_13_1",
        "Pandnim01_13_2",
        "pandnim01_0",
        "pandnim01_1",
        "pandnim01_2",
        "pandnim01_3",
        "pandnim01_4",
        "pandnim01_5",
        "pandnim01_6",
        "pandnim01_7",
        "pandnim01_8",
        "pandnim01_9",
        "pandnim01_10",
        "pandnim01_11",
        "pandnim01_14",
    ):
        add_and_exact(name, "100GB", ["pandnim01"])

    pandsps12 = ["pandps1", "pandps2"]
    for host in pandsps12:
        add_and_numbered(f"{host}_", range(3), "100GB", [host])
    add_and_exact("pandps_1_2_HA", "10GB", pandsps12)
    add_and_numbered(
        "pandps_1_2_shared_",
        (1, 2, 3, 4, 6, 7, 11, 12, 13, 14, 15),
        "64GB",
        pandsps12,
    )
    add_and_numbered(
        "pandps_1_2_shared_",
        range(16, 20),
        "50GB",
        pandsps12,
    )
    add_and_numbered(
        "pandps_1_2_shared_",
        (20, 21),
        "100GB",
        pandsps12,
    )

    pandsps34 = ["pandps3", "pandps4"]
    add_and_numbered("PANDPS3_ROOT_", range(1, 4), "50GB", ["pandps3"])
    add_and_numbered("PANDPS4_ROOT_", range(3), "50GB", ["pandps4"])
    add_and_numbered(
        "PANDPS_3_4_ARCHVG_SHARED_",
        range(1, 3),
        "100GB",
        pandsps34,
    )
    add_and_numbered(
        "PANDPS_3_4_ORA1VG_SHARED_",
        range(1, 10),
        "100GB",
        pandsps34,
    )
    add_and_exact("PANDPS_3_4_REPO_CAAVG_SHARED", "10GB", pandsps34)
    add_and_numbered(
        "PANDPS_3_4_SPS1REDOVG_SHARED_",
        range(1, 3),
        "100GB",
        pandsps34,
    )
    add_and_numbered(
        "PANDPS_3_4_ROOT_",
        range(1, 4),
        "100GB",
        ["pandps3"],
    )

    pandspsa = ["pandpspa1", "pandpspa2"]
    for host in pandspsa:
        add_and_numbered(f"{host}_", range(3), "50GB", [host])
    add_and_exact("pandpspa1_2_DATA", "250GB", pandspsa)
    add_and_exact("pandpspa1_2_HA", "10GB", pandspsa)

    add_and_numbered("pandpspdg1_", range(3), "72GB", ["pandpspdg1"])
    add_and_numbered(
        "pandpspdg1_dg_",
        (1, 2, 3, 4, 6, 7, 11, 12, 13, 14, 15),
        "64GB",
        ["pandpspdg1"],
    )
    add_and_numbered(
        "pandpspdg1_dg_",
        range(16, 20),
        "50GB",
        ["pandpspdg1"],
    )

    vio_sizes = {
        "pandvio01a": (2, "100GB", "root_", 1),
        "pandvio01b": (2, "100GB", "root_", 1),
        "pandvio02a": (2, "100GB", "root_", 1),
        "pandvio02b": (2, "100GB", "root_", 1),
        "pandvio03a": (2, "100GB", "root_", 0),
        "pandvio03b": (2, "100GB", "root_", 0),
        "pandvio04a": (2, "100GB", "root_", 0),
        "pandvio04b": (2, "100GB", "root_", 0),
        "pandvio05a": (4, "100GB", "", 0),
        "pandvio05b": (3, "100GB", "", 0),
        "pandvio06a": (3, "100GB", "", 0),
        "pandvio06b": (3, "100GB", "", 0),
        "pandvio07a": (3, "100GB", "", 0),
        "pandvio07b": (3, "100GB", "", 0),
        "pandvio08a": (2, "50GB", "", 0),
        "pandvio08b": (2, "50GB", "", 0),
        "pandvio09a": (2, "50GB", "", 0),
        "pandvio09b": (2, "50GB", "", 0),
        "pandvio10a": (2, "100GB", "root_", 1),
        "pandvio10b": (2, "100GB", "root_", 1),
    }
    for host, (count, size, infix, start) in vio_sizes.items():
        add_and_numbered(
            f"{host}_{infix}",
            range(start, start + count),
            size,
            [host],
        )

    add_and_numbered("tandbt1_", range(3), "72GB", ["tandbt1"])
    add_and_numbered(
        "tandbt1_db_",
        tuple(range(1, 19)) + tuple(range(20, 27)),
        "64GB",
        ["tandbt1"],
    )
    add_and_numbered(
        "tandbt1_db_",
        range(27, 31),
        "50GB",
        ["tandbt1"],
    )

    add_and_numbered("tandbt20_", range(3), "100GB", ["tandbt20"])
    add_and_numbered("tandbt20_data_", range(1, 27), "64GB", ["tandbt20"])
    add_and_numbered("tandbt20_data_", range(27, 31), "50GB", ["tandbt20"])
    add_and_numbered("tandbt20_data_", range(31, 38), "100GB", ["tandbt20"])
    add_and_numbered("tandbt_clone_root", range(3), "100GB", ["tandbt20"])

    add_and_numbered("tandmfs1_", range(3), "72GB", ["tandmfs1"])
    for index, size in (
        (1, "20GB"),
        (2, "64GB"),
        (3, "64GB"),
        (4, "64GB"),
        (5, "64GB"),
        (7, "64GB"),
        (8, "64GB"),
        (11, "64GB"),
        (12, "64GB"),
        (14, "64GB"),
        (15, "64GB"),
        (16, "64GB"),
        (17, "20GB"),
    ):
        add_and_exact(
            f"pandmfs_dg_mast_{index}_01",
            size,
            ["tandmfs1"],
        )

    add_and_numbered("tandmfs2_", range(3), "72GB", ["tandmfs2"])
    add_and_numbered("tandmfs2_", range(3, 8), "100GB", ["tandmfs2"])
    add_and_numbered("tandmfs2_asm", range(7), "100GB", ["tandmfs2"])

    add_and_numbered("tandmfs20_", range(3), "100GB", ["tandmfs20"])
    add_and_exact("tandmfs20_data_1", "20GB", ["tandmfs20"])
    add_and_numbered(
        "tandmfs20_data_",
        (2, 3, 4, 5, 7, 8, 11, 12, 14, 15, 16),
        "64GB",
        ["tandmfs20"],
    )
    add_and_exact("tandmfs20_data_17", "20GB", ["tandmfs20"])
    add_and_numbered(
        "tandmfs20_data_",
        (18, 19),
        "100GB",
        ["tandmfs20"],
    )
    add_and_numbered("tandmfs_clone_root", range(3), "100GB", ["tandmfs20"])
    add_and_numbered("tandmfs20_clone_root", range(2), "100GB", ["tandmfs20"])

    tandsps12 = ["tandsps1", "tandsps2"]
    for host in tandsps12:
        add_and_numbered(f"{host}_", range(3), "72GB", [host])
    add_and_exact("tandsps_1_2_HA", "10GB", tandsps12)
    add_and_numbered(
        "tandsps_1_2_shared_",
        range(1, 12),
        "64GB",
        tandsps12,
    )
    add_and_numbered(
        "tandsps_1_2_shared_",
        range(12, 16),
        "50GB",
        tandsps12,
    )

    tandsps2021 = ["tandsps20", "tandsps21"]
    for host in tandsps2021:
        add_and_numbered(f"{host}_", range(3), "100GB", [host])
    add_and_exact("tandsps20_21_HA", "10GB", tandsps2021)
    add_and_numbered(
        "tandsps20_21_shared_",
        (1, 2, 3, 4, 6, 7, 11, 12, 13, 14, 15),
        "64GB",
        tandsps2021,
    )
    add_and_numbered(
        "tandsps20_21_shared_",
        range(16, 20),
        "50GB",
        tandsps2021,
    )
    add_and_numbered(
        "tandsps20_21_shared_",
        (20, 21),
        "100GB",
        tandsps2021,
    )
    add_and_numbered(
        "tandsps_clone_root",
        range(3),
        "100GB",
        ["tandsps20"],
    )

    tcon_specs = {
        "tconbt20": (
            ("pconbt1_2_archvg_dt", range(1, 3), "100GB"),
            ("pconbt1_2_btfs1redovg_dt", range(1, 3), "100GB"),
            ("pconbt1_2_ora1evg_dt_", range(1, 15), "100GB"),
            ("pconbt1_rootvg_dt_", range(1, 4), "50GB"),
        ),
        "tconmfs20": (
            ("pconmfs1_2_archvg_dt_", range(1, 2), "200GB"),
            ("pconmfs1_2_mfs1redovg_dt_", range(1, 3), "100GB"),
            ("pconmfs1_2_ora1vg_dt", range(1, 8), "100GB"),
            ("pconmfs1_root_sysvg_dt_", range(1, 4), "50GB"),
        ),
        "tconsps20": (
            ("pconsps1_root_sysvg_dt_", range(1, 4), "50GB"),
        ),
        "tconsps21": (
            ("pconsps2_root_sysvg_dt", range(1, 4), "50GB"),
        ),
    }
    for host, specs in tcon_specs.items():
        for stem, indexes, size in specs:
            add_and_numbered(stem, indexes, size, [host])
    add_and_exact("pconbt1_2_caavg_dt", "10GB", ["tconbt20"])
    add_and_exact("tconbt20_vol1", "100GB", ["tconbt20"])
    add_and_exact("pconmfs1_2_caavg_dt", "10GB", ["tconmfs20"])
    tconsps_hosts = ["tconsps20", "tconsps21"]
    add_and_numbered(
        "pconsps1_2_archvg_dt_",
        range(1, 3),
        "200GB",
        tconsps_hosts,
    )
    add_and_numbered(
        "pconsps1_2_ora1vg_dt_",
        range(1, 8),
        "100GB",
        tconsps_hosts,
    )
    add_and_numbered(
        "pconsps1_2_sps1redovg_dt_",
        range(1, 3),
        "100GB",
        tconsps_hosts,
    )
    add_and_exact("pconsps1_2_caavg_dt", "10GB", tconsps_hosts)

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
            "id": "template-williamston-anderson",
            "name": "Williamston (Anderson) (Template)",
            "location": "Williamston (Anderson)",
            "notes": (
                "Seeded from Anderson FlashSystem 7200 inventory (v7kand-g3v1). "
                "WWPNs are blank — set Port Definitions / Pull from FC WWPN before create. "
                "Defaults use card hint Williamston (Anderson), profile flashsystem_7200, "
                "pool G3_AND_Pool."
            ),
            "is_template": True,
            "default_storage_profile": "flashsystem_7200",
            "default_pool_or_cpg": "G3_AND_Pool",
            "default_card_hint": "Williamston (Anderson)",
            "hosts": and_hosts,
            "luns": and_luns,
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
    cluster = str(lun.get("cluster") or "").strip().lower()
    if _as_bool(lun.get("exact_name")):
        return None
    if not prefix:
        prefix = _infer_site_prefix(host_names)
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
