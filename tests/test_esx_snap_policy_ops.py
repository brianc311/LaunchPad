from datetime import datetime

from launchpad.esx_snap_policy_ops import (
    POLICY_NAME,
    backup_start_token,
    build_esx_snap_array_steps,
    collect_esx_snap_inventory,
    default_vg_name,
    parse_lsvdisk_membership,
    parse_named_objects,
    preview_hash,
    sanitize_site_token,
)


POLICY_SAMPLE = """id:name:backup_unit:backup_interval:retention_days
0:other-policy:day:1:7
"""

VG_SAMPLE = """id:name:snapshot_policy_name
0:Other_VG:other-policy
"""

VDISK_SAMPLE = """id:name:capacity:volume_group
0:WIN_ESX_DS01:1.00TB:
1:WIN_ESX_DS02:2.00TB:Already_VG
2:WIN_NFS:500.00GB:
"""


def test_sanitize_and_default_vg_name():
    assert sanitize_site_token("Windsor FS9200") == "Windsor_FS9200"
    assert default_vg_name("Windsor") == "Windsor_ESX-snap"
    assert default_vg_name("  ") == "Site_ESX-snap"
    assert default_vg_name("Windsor FS9200") == "Windsor_FS9200_ESX-snap"
    long_name = "A" * 80
    vg = default_vg_name(long_name)
    assert len(vg) <= 63
    assert vg.endswith("_ESX-snap")


def test_backup_start_token_uses_local_date_and_hhmm():
    now = datetime(2026, 8, 15, 18, 0, 0)
    assert backup_start_token("02:00", now=now) == "2608150200"
    assert backup_start_token("2:00", now=now) == "2608150200"


def test_parse_named_objects_and_volume_membership():
    assert parse_named_objects(POLICY_SAMPLE) == {"other-policy"}
    vols = parse_lsvdisk_membership(VDISK_SAMPLE)
    by_name = {row["name"]: row for row in vols}
    assert by_name["WIN_ESX_DS01"]["volume_group"] == ""
    assert by_name["WIN_ESX_DS02"]["volume_group"] == "Already_VG"
    assert by_name["WIN_ESX_DS01"]["capacity"] == "1.00TB"


def test_steps_daily_seven_day_policy_and_add_volume():
    now = datetime(2026, 8, 15, 9, 0, 0)
    volumes = parse_lsvdisk_membership(VDISK_SAMPLE)
    steps, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_ESX-snap",
        volume_names=["WIN_ESX_DS01", "WIN_NFS"],
        start_time="02:00",
        policies=set(),
        volume_groups=set(),
        volumes=volumes,
        now=now,
    )
    assert runnable is True
    assert warnings == []
    cmds = [step.cmd for step in steps]
    assert cmds[0] == (
        "svctask mksnapshotpolicy -backupunit day -backupinterval 1 "
        "-backupstarttime 2608150200 -retentiondays 7 -name ESX-snap"
    )
    assert cmds[1] == (
        "svctask mkvolumegroup -snapshotpolicy ESX-snap -name Windsor_ESX-snap"
    )
    assert cmds[2] == (
        "svctask addvolumetovolumegroup -volumegroup Windsor_ESX-snap WIN_ESX_DS01"
    )
    assert cmds[3] == (
        "svctask addvolumetovolumegroup -volumegroup Windsor_ESX-snap WIN_NFS"
    )
    assert POLICY_NAME == "ESX-snap"


def test_existence_and_membership_block_array():
    volumes = parse_lsvdisk_membership(VDISK_SAMPLE)
    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_ESX-snap",
        volume_names=["WIN_ESX_DS01"],
        start_time="02:00",
        policies={"ESX-snap"},
        volume_groups=set(),
        volumes=volumes,
    )
    assert runnable is False
    assert any("ESX-snap" in w for w in warnings)

    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_ESX-snap",
        volume_names=["WIN_ESX_DS01"],
        start_time="02:00",
        policies=set(),
        volume_groups={"Windsor_ESX-snap"},
        volumes=volumes,
    )
    assert runnable is False
    assert any("Windsor_ESX-snap" in w for w in warnings)

    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_ESX-snap",
        volume_names=["WIN_ESX_DS02"],
        start_time="02:00",
        policies=set(),
        volume_groups=set(),
        volumes=volumes,
    )
    assert runnable is False
    assert any("volume group" in w.lower() or "Already_VG" in w for w in warnings)

    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_ESX-snap",
        volume_names=[],
        start_time="02:00",
        policies=set(),
        volume_groups=set(),
        volumes=volumes,
    )
    assert runnable is False


def test_preview_hash_stable_and_order_independent():
    a = preview_hash(
        "02:00",
        [
            {"card_id": 2, "vg_name": "B_ESX-snap", "volume_names": ["v2", "v1"]},
            {"card_id": 1, "vg_name": "A_ESX-snap", "volume_names": ["v0"]},
        ],
    )
    b = preview_hash(
        "02:00",
        [
            {"card_id": 1, "vg_name": "A_ESX-snap", "volume_names": ["v0"]},
            {"card_id": 2, "vg_name": "B_ESX-snap", "volume_names": ["v1", "v2"]},
        ],
    )
    assert a == b
    c = preview_hash(
        "03:00",
        [
            {"card_id": 1, "vg_name": "A_ESX-snap", "volume_names": ["v0"]},
            {"card_id": 2, "vg_name": "B_ESX-snap", "volume_names": ["v1", "v2"]},
        ],
    )
    assert a != c


def test_collect_inventory_parses_and_flags_missing_policy_cli():
    calls: list[str] = []

    def run_cmd(command: str) -> str:
        calls.append(command)
        if "lssnapshotpolicy" in command:
            return POLICY_SAMPLE
        if "lsvolumegroup" in command:
            return VG_SAMPLE
        if "lsvdisk" in command:
            return VDISK_SAMPLE
        raise AssertionError(command)

    result = collect_esx_snap_inventory(run_cmd)
    assert result["ok"] is True
    assert "other-policy" in result["policies"]
    assert "Other_VG" in result["volume_groups"]
    assert {row["name"] for row in result["volumes"]} == {
        "WIN_ESX_DS01",
        "WIN_ESX_DS02",
        "WIN_NFS",
    }

    def reject(command: str) -> str:
        if "lssnapshotpolicy" in command:
            raise RuntimeError("not a valid command")
        return ""

    bad = collect_esx_snap_inventory(reject)
    assert bad["ok"] is False
    assert "8.5.1" in bad["error"]
