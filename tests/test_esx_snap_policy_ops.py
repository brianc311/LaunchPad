from datetime import datetime

from launchpad.esx_snap_policy_ops import (
    POLICY_NAME,
    apply_checked_volume_details,
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
    assert default_vg_name("Windsor") == "Windsor_esx_snap"
    assert default_vg_name("  ") == "Site_esx_snap"
    assert default_vg_name("Windsor FS9200") == "Windsor_FS9200_esx_snap"
    long_name = "A" * 80
    vg = default_vg_name(long_name)
    assert len(vg) <= 63
    assert vg.endswith("_esx_snap")


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
        vg_name="Windsor_esx_snap",
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
        "-backupstarttime 2608150200 -retentiondays 7 -name esx_snap"
    )
    assert cmds[1] == (
        "svctask mkvolumegroup -snapshotpolicy esx_snap -name Windsor_esx_snap"
    )
    assert cmds[2] == (
        "svctask addvolumetovolumegroup -volumegroup Windsor_esx_snap WIN_ESX_DS01"
    )
    assert cmds[3] == (
        "svctask addvolumetovolumegroup -volumegroup Windsor_esx_snap WIN_NFS"
    )
    assert POLICY_NAME == "esx_snap"


def test_existence_and_membership_block_array():
    volumes = parse_lsvdisk_membership(VDISK_SAMPLE)
    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_esx_snap",
        volume_names=["WIN_ESX_DS01"],
        start_time="02:00",
        policies={"esx_snap"},
        volume_groups=set(),
        volumes=volumes,
    )
    assert runnable is False
    assert any("esx_snap" in w for w in warnings)

    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_esx_snap",
        volume_names=["WIN_ESX_DS01"],
        start_time="02:00",
        policies={"ESX-snap"},
        volume_groups=set(),
        volumes=volumes,
    )
    assert runnable is True

    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_esx_snap",
        volume_names=["WIN_ESX_DS01"],
        start_time="02:00",
        policies=set(),
        volume_groups={"Windsor_esx_snap"},
        volumes=volumes,
    )
    assert runnable is False
    assert any("Windsor_esx_snap" in w for w in warnings)

    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_esx_snap",
        volume_names=["WIN_ESX_DS02"],
        start_time="02:00",
        policies=set(),
        volume_groups=set(),
        volumes=volumes,
    )
    assert runnable is False
    assert any("volume group" in w.lower() or "Already_VG" in w for w in warnings)

    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_esx_snap",
        volume_names=[],
        start_time="02:00",
        policies=set(),
        volume_groups=set(),
        volumes=volumes,
    )
    assert runnable is False


def test_vg_name_over_63_is_not_runnable():
    volumes = parse_lsvdisk_membership(VDISK_SAMPLE)
    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="A" * 64,
        volume_names=["WIN_ESX_DS01"],
        start_time="02:00",
        policies=set(),
        volume_groups=set(),
        volumes=volumes,
    )
    assert runnable is False
    assert any("ERROR: volume group name exceeds 63 characters" in w for w in warnings)


def test_preview_hash_stable_and_order_independent():
    a = preview_hash(
        "02:00",
        [
            {"card_id": 2, "vg_name": "B_ESX-snap", "volume_names": ["v2", "v1"]},
            {"card_id": 1, "vg_name": "A_ESX-snap", "volume_names": ["v0"]},
        ],
        policy_name="esx_snap",
    )
    b = preview_hash(
        "02:00",
        [
            {"card_id": 1, "vg_name": "A_ESX-snap", "volume_names": ["v0"]},
            {"card_id": 2, "vg_name": "B_ESX-snap", "volume_names": ["v1", "v2"]},
        ],
        policy_name="esx_snap",
    )
    assert a == b
    c = preview_hash(
        "03:00",
        [
            {"card_id": 1, "vg_name": "A_ESX-snap", "volume_names": ["v0"]},
            {"card_id": 2, "vg_name": "B_ESX-snap", "volume_names": ["v1", "v2"]},
        ],
        policy_name="esx_snap",
    )
    assert a != c
    d = preview_hash(
        "02:00",
        [
            {"card_id": 1, "vg_name": "A_ESX-snap", "volume_names": ["v0"]},
            {"card_id": 2, "vg_name": "B_ESX-snap", "volume_names": ["v1", "v2"]},
        ],
        policy_name="other",
    )
    assert a != d


def test_collect_inventory_parses_and_flags_missing_policy_cli():
    calls: list[str] = []

    def run_cmd(command: str) -> str:
        calls.append(command)
        if "lsvolumegroupmember" in command:
            raise AssertionError(command)
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


VDISK_NO_VG_COL = """id:name:capacity
0:WIN_ESX_DS01:1.00TB
1:WIN_ESX_DS02:2.00TB
2:WIN_NFS:500.00GB
"""


def test_collect_inventory_does_not_call_lsvolumegroupmember():
    calls: list[str] = []

    def run_cmd(command: str) -> str:
        calls.append(command)
        if "lsvolumegroupmember" in command:
            raise AssertionError(command)
        if "lssnapshotpolicy" in command:
            return POLICY_SAMPLE
        if "lsvolumegroup" in command:
            return VG_SAMPLE
        if "lsvdisk" in command:
            return VDISK_SAMPLE
        raise AssertionError(command)

    result = collect_esx_snap_inventory(run_cmd)
    assert result["ok"] is True
    assert not any("lsvolumegroupmember" in c for c in calls)
    by_name = {row["name"]: row for row in result["volumes"]}
    assert by_name["WIN_ESX_DS02"]["volume_group"] == "Already_VG"


def test_apply_checked_volume_details_only_looks_up_empty_membership():
    volumes = parse_lsvdisk_membership(VDISK_NO_VG_COL)
    calls: list[str] = []

    def run_cmd(command: str) -> str:
        calls.append(command)
        if "lsvolumegroupmember" in command:
            raise AssertionError(command)
        if "lsvdisk" in command and "WIN_ESX_DS02" in command:
            return "id:name:volume_group_name\n0:WIN_ESX_DS02:Already_VG\n"
        return ""

    apply_checked_volume_details(run_cmd, volumes, ["WIN_ESX_DS02"])
    by_name = {row["name"]: row for row in volumes}
    assert by_name["WIN_ESX_DS02"]["volume_group"] == "Already_VG"
    assert all("WIN_ESX_DS01" not in c for c in calls)
    assert all("lsvolumegroupmember" not in c for c in calls)


def test_apply_checked_volume_details_parses_lsvdisk_key_value_detail():
    volumes = parse_lsvdisk_membership(VDISK_NO_VG_COL)

    def run_cmd(command: str) -> str:
        if "lsvdisk" in command and "WIN_ESX_DS02" in command:
            return "id:0\nname:WIN_ESX_DS02\nvolume_group_name:Already_VG\n"
        return ""

    apply_checked_volume_details(run_cmd, volumes, ["WIN_ESX_DS02"])
    by_name = {row["name"]: row for row in volumes}
    assert by_name["WIN_ESX_DS02"]["volume_group"] == "Already_VG"


def test_typed_policy_name_in_steps_and_too_long():
    volumes = parse_lsvdisk_membership(VDISK_SAMPLE)
    steps, _, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_esx_snap",
        volume_names=["WIN_ESX_DS01"],
        start_time="02:00",
        policies=set(),
        volume_groups=set(),
        volumes=volumes,
        policy_name="siteA_esx",
        now=datetime(2026, 8, 15, 9, 0, 0),
    )
    assert runnable is True
    assert "-name siteA_esx" in steps[0].cmd
    assert "-snapshotpolicy siteA_esx" in steps[1].cmd
    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_esx_snap",
        volume_names=["WIN_ESX_DS01"],
        start_time="02:00",
        policies=set(),
        volume_groups=set(),
        volumes=volumes,
        policy_name="P" * 64,
    )
    assert runnable is False
    assert any("63" in w for w in warnings)
