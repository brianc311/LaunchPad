from launchpad.contingency_snap_create import (
    SnapStep,
    append_snap_cg_assign_steps,
    build_snap_steps,
    collect_inventory,
    maps_touched_this_run,
    parse_capacity_to_gb,
    run_snap_steps,
    safe_fcmap_name,
)


def test_parse_capacity_tib():
    assert parse_capacity_to_gb("4.00 TiB") == 4096.0


def test_build_steps_blocking_without_pool_size():
    group = {
        "id": "x",
        "name": "X",
        "storage_hint": "array1",
        "volumes": [
            {"name": "V1", "role": "source", "pool": "", "capacity": ""},
            {
                "name": "V1_snap",
                "role": "snap",
                "source_volume": "V1",
                "pool": "",
                "capacity": "",
            },
        ],
        "maps": [
            {"volume": "V1", "host": "h1", "scsi_id": "0", "role": "source"},
            {"volume": "V1_snap", "host": "h1", "scsi_id": "0", "role": "snap"},
        ],
    }
    steps, warnings = build_snap_steps(
        group, inventory={"vdisks": set(), "fcmaps": set(), "hostmaps": set()}
    )
    assert any("pool" in w.lower() or "size" in w.lower() for w in warnings)


def test_build_steps_happy_path_and_skip():
    group = {
        "id": "x",
        "name": "X",
        "storage_hint": "array1",
        "volumes": [
            {"name": "V1", "role": "source", "pool": "P0", "capacity": "4.00 TiB"},
            {
                "name": "V1_snap",
                "role": "snap",
                "source_volume": "V1",
                "pool": "P0",
                "capacity": "4.00 TiB",
            },
        ],
        "maps": [
            {"volume": "V1_snap", "host": "h1", "scsi_id": "0", "role": "snap"},
        ],
    }
    steps, warnings = build_snap_steps(
        group,
        inventory={
            "vdisks": {"V1", "V1_snap"},
            "fcmaps": set(),
            "hostmaps": set(),
        },
    )
    assert not warnings
    assert any(s.skip and "mkvdisk" in s.cmd for s in steps)
    assert any("mkfcmap" in s.cmd and not s.skip for s in steps)
    assert any("startfcmap" in s.cmd for s in steps)
    assert any("mkvdiskhostmap" in s.cmd for s in steps)
    assert "fc_" in safe_fcmap_name("V1", "V1_snap")


def test_build_steps_skips_existing_flashcopy_map_and_start():
    group = {
        "id": "x",
        "name": "X",
        "storage_hint": "array1",
        "volumes": [
            {"name": "V1", "role": "source", "pool": "P0", "capacity": "4.00 TiB"},
            {
                "name": "V1_snap",
                "role": "snap",
                "source_volume": "V1",
                "pool": "P0",
                "capacity": "4.00 TiB",
            },
        ],
        "maps": [],
    }

    steps, warnings = build_snap_steps(
        group,
        inventory={
            "vdisks": {"V1", "V1_snap"},
            "fcmaps": {"fc_V1_to_V1_snap"},
            "hostmaps": set(),
        },
    )

    assert not warnings
    flashcopy_steps = [step for step in steps if "fcmap" in step.kind]
    assert len(flashcopy_steps) == 2
    assert all(step.skip for step in flashcopy_steps)
    assert all(step.reason == "FlashCopy map already exists" for step in flashcopy_steps)


def test_build_steps_blocks_unsafe_cli_tokens_without_raw_command_text():
    unsafe_value = "V1_snap; rm -rf /"
    group = {
        "id": "x",
        "name": "X",
        "storage_hint": "array1",
        "volumes": [
            {"name": "V1; rm -rf /", "role": "source", "pool": "P0", "capacity": "1 GB"},
            {
                "name": unsafe_value,
                "role": "snap",
                "source_volume": "V1; rm -rf /",
                "pool": "P0; rm -rf /",
                "capacity": "1 GB",
            },
        ],
        "maps": [
            {
                "volume": unsafe_value,
                "host": "host1; rm -rf /",
                "scsi_id": "0; rm -rf /",
                "role": "snap",
            },
        ],
    }

    steps, warnings = build_snap_steps(
        group, inventory={"vdisks": set(), "fcmaps": set(), "hostmaps": set()}
    )

    assert warnings
    assert any("unsafe" in warning.lower() for warning in warnings)
    assert all("; rm -rf /" not in step.cmd for step in steps)


def test_run_snap_steps_stops_on_error():
    calls = []

    def run_cmd(cmd: str) -> str:
        calls.append(cmd)
        if "startfcmap" in cmd:
            raise RuntimeError("boom")
        return "OK"

    steps = [
        SnapStep("mkvdisk", "create", "svctask mkvdisk ...", skip=True),
        SnapStep("mkfcmap", "map", "svctask mkfcmap ..."),
        SnapStep("startfcmap", "start", "svctask startfcmap ..."),
        SnapStep("hostmap", "map host", "svctask mkvdiskhostmap ..."),
    ]

    result = run_snap_steps(steps, run_cmd)

    assert result["ok"] is False
    assert len(calls) == 2
    assert "mkvdiskhostmap" not in "".join(calls)


def test_collect_inventory_parses_delimited_tables():
    responses = {
        "svcinfo lsvdisk -delim :": "id:name\n0:V1\n1:V1_snap",
        "svcinfo lsfcmap -delim :": "id:name\n0:fc_V1_to_V1_snap",
        "svcinfo lshostvdiskmap -delim :": "host_name:SCSI_id:vdisk_name\nh1:0:V1_snap",
    }
    calls: list[str] = []

    def run_cmd(cmd: str) -> str:
        calls.append(cmd)
        return responses.get(cmd, "")

    inventory = collect_inventory(run_cmd)

    assert inventory["vdisks"] == {"V1", "V1_snap"}
    assert inventory["fcmaps"] == {"fc_V1_to_V1_snap"}
    assert ("h1", "0", "V1_snap") in inventory["hostmaps"]
    assert all(cmd.endswith("-delim :") for cmd in calls)
    assert "svcinfo lsvdisk" in calls[0]


def test_maps_touched_this_run_only_nonskipped():
    steps = [
        SnapStep("mkfcmap", "create", "svctask mkfcmap -source A -target B -name fc_A_to_B", skip=False),
        SnapStep("startfcmap", "start", "svctask startfcmap fc_A_to_B", skip=False),
        SnapStep("mkfcmap", "create", "svctask mkfcmap -source C -target D -name fc_C_to_D", skip=True),
        SnapStep("startfcmap", "start", "svctask startfcmap fc_C_to_D", skip=True),
    ]
    assert maps_touched_this_run(steps) == ["fc_A_to_B"]


def test_append_cg_assign_off_is_noop():
    base = [SnapStep("mkvdisk", "create", "svctask mkvdisk -name X -mdiskgrp P -size 1 -unit gb")]
    out, warnings = append_snap_cg_assign_steps(
        base, cg_name="WIN_ESX_snap", enabled=False, fc_groups=[], fc_maps=[]
    )
    assert out == base
    assert warnings == []


def test_append_cg_assign_creates_group_and_assigns():
    base = [
        SnapStep("mkfcmap", "create", "svctask mkfcmap -source A -target B -name fc_A_to_B"),
        SnapStep("startfcmap", "start", "svctask startfcmap fc_A_to_B"),
    ]
    out, warnings = append_snap_cg_assign_steps(
        base,
        cg_name="WIN_ESX_snap",
        enabled=True,
        fc_groups=[],
        fc_maps=[{"name": "fc_A_to_B", "consistgrp": ""}],
    )
    kinds = [s.kind for s in out]
    assert "mkfcconsistgrp" in kinds
    assert kinds.count("chfcmap") == 1
    assert not any(w.startswith("ERROR:") for w in warnings)


def test_append_cg_assign_existing_group_advisory():
    base = [
        SnapStep("mkfcmap", "create", "svctask mkfcmap -source A -target B -name fc_A_to_B"),
        SnapStep("startfcmap", "start", "svctask startfcmap fc_A_to_B"),
    ]
    out, warnings = append_snap_cg_assign_steps(
        base,
        cg_name="WIN_ESX_snap",
        enabled=True,
        fc_groups=[{"name": "WIN_ESX_snap"}],
        fc_maps=[{"name": "fc_A_to_B", "consistgrp": ""}],
    )
    cg_steps = [s for s in out if s.kind == "mkfcconsistgrp"]
    assert len(cg_steps) == 1 and cg_steps[0].skip is True
    assert any("already exists" in w.lower() for w in warnings)
    assert not any(w.startswith("ERROR:") for w in warnings)


def test_append_cg_assign_skips_map_in_other_cg():
    base = [
        SnapStep("mkfcmap", "create", "svctask mkfcmap -source A -target B -name fc_A_to_B"),
        SnapStep("startfcmap", "start", "svctask startfcmap fc_A_to_B"),
    ]
    out, warnings = append_snap_cg_assign_steps(
        base,
        cg_name="WIN_ESX_snap",
        enabled=True,
        fc_groups=[{"name": "WIN_ESX_snap"}],
        fc_maps=[{"name": "fc_A_to_B", "consistgrp": "OTHER_CG"}],
    )
    assert not any(s.kind == "chfcmap" and not s.skip for s in out)
    assert any("OTHER_CG" in w for w in warnings)
