import pytest

from launchpad.lun_builder_create import build_lun_steps, run_lun_steps
from launchpad.lun_builder_data import normalize_build


def _build(lun: dict) -> dict:
    build = normalize_build(
        {
            "id": "b1",
            "name": "Lab",
            "hosts": [{"lpar_name": "host1"}],
            "luns": [lun],
        }
    )
    assert build is not None
    return build


def test_svc_steps_include_create_and_host_map():
    steps = build_lun_steps(
        _build(
            {
                "purpose": "vol",
                "count": 1,
                "size": "10GB",
                "pool_or_cpg": "Pool0",
                "storage_profile": "flashsystem_5200",
                "host_names": ["host1"],
                "scsi_or_lun_id": "0",
                "card_hint": "cardA",
            }
        ),
        inventory_by_card=None,
    )

    assert any(step["kind"] == "mkvdisk" and step["live"] for step in steps)
    assert any(
        step["kind"] == "mkvdiskhostmap" and step["live"] for step in steps
    )
    assert steps[0]["cmd"] == (
        "svctask mkvdisk -name host1_vol -mdiskgrp Pool0 -size 10 -unit gb"
    )


def test_svc_existing_vdisk_is_skipped():
    steps = build_lun_steps(
        _build(
            {
                "purpose": "vol",
                "count": 1,
                "size": "10GB",
                "pool_or_cpg": "Pool0",
                "storage_profile": "flashsystem_5200",
                "card_hint": "cardA",
            }
        ),
        inventory_by_card={"cardA": {"vdisks": {"vol"}}},
    )

    assert steps[0]["kind"] == "mkvdisk"
    assert steps[0]["skip"] is True


def test_threepar_createvv_uses_parsed_lowercase_g_size():
    steps = build_lun_steps(
        _build(
            {
                "purpose": "data",
                "count": 1,
                "size": "100GB",
                "pool_or_cpg": "FC_r6",
                "storage_profile": "hpe_3par_8450",
                "host_names": ["host1"],
                "card_hint": "cardA",
            }
        ),
        None,
    )

    createvv = next(step for step in steps if step["kind"] == "createvv")
    assert createvv["cmd"] == "createvv FC_r6 host1_data 100g"
    assert "100GB" not in createvv["cmd"]


def test_threepar_steps_use_auto_incrementing_lun_ids_per_host():
    steps = build_lun_steps(
        _build(
            {
                "purpose": "data",
                "count": 2,
                "size": "5GB",
                "pool_or_cpg": "FC_r6",
                "storage_profile": "hpe_3par_8450",
                "host_names": ["host1"],
                "card_hint": "cardA",
            }
        ),
        None,
    )

    map_commands = [
        step["cmd"] for step in steps if step["kind"] == "createvlun"
    ]
    assert map_commands == [
        "createvlun host1_data_1 0 host1",
        "createvlun host1_data_2 1 host1",
    ]


def test_ds_steps_are_plan_only():
    steps = build_lun_steps(
        _build(
            {
                "purpose": "root",
                "count": 1,
                "size": "50GB",
                "pool_or_cpg": "P0",
                "storage_profile": "ibm_ds8884",
                "card_hint": "dscli-host",
            }
        ),
        None,
    )

    assert steps
    assert all(step["live"] is False for step in steps)
    assert "dscli" in steps[0]["cmd"]


def test_unsafe_cli_token_is_rejected():
    with pytest.raises(ValueError, match="Unsafe CLI token"):
        build_lun_steps(
            _build(
                {
                    "purpose": "vol;rm",
                    "count": 1,
                    "size": "10GB",
                    "pool_or_cpg": "Pool0",
                    "storage_profile": "flashsystem_5200",
                    "card_hint": "cardA",
                }
            ),
            None,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("purpose", "-vol"),
        ("pool_or_cpg", "-Pool0"),
        ("host_names", ["-host1"]),
        ("scsi_or_lun_id", "-1"),
    ],
)
def test_leading_dash_command_tokens_are_rejected(field, value):
    lun = {
        "purpose": "vol",
        "count": 1,
        "size": "10GB",
        "pool_or_cpg": "Pool0",
        "storage_profile": "flashsystem_5200",
        "host_names": ["host1"] if field != "purpose" else [],
        "scsi_or_lun_id": "0",
        "card_hint": "cardA",
    }
    lun[field] = value

    with pytest.raises(ValueError, match="Unsafe CLI token"):
        build_lun_steps(_build(lun), None)


def test_explicit_lun_id_collision_for_same_host_is_rejected():
    build = normalize_build(
        {
            "id": "b1",
            "name": "Lab",
            "hosts": [{"lpar_name": "host1"}],
            "luns": [
                {
                    "purpose": "vol1",
                    "count": 1,
                    "size": "10GB",
                    "pool_or_cpg": "Pool0",
                    "storage_profile": "flashsystem_5200",
                    "host_names": ["host1"],
                    "scsi_or_lun_id": "3",
                    "card_hint": "cardA",
                },
                {
                    "purpose": "vol2",
                    "count": 1,
                    "size": "10GB",
                    "pool_or_cpg": "Pool0",
                    "storage_profile": "flashsystem_5200",
                    "host_names": ["host1"],
                    "scsi_or_lun_id": "3",
                    "card_hint": "cardA",
                },
            ],
        }
    )
    assert build is not None

    with pytest.raises(ValueError, match="LUN ID 3.*host1"):
        build_lun_steps(build, None)


def test_run_executes_only_live_non_skipped_steps():
    calls = []
    steps = [
        {
            "kind": "mkvdisk",
            "label": "create",
            "cmd": "create",
            "card_hint": "a",
            "profile": "flashsystem_5200",
            "live": True,
            "skip": False,
        },
        {
            "kind": "plan",
            "label": "plan",
            "cmd": "plan",
            "card_hint": "b",
            "profile": "ibm_ds8884",
            "live": False,
            "skip": False,
        },
        {
            "kind": "mkvdisk",
            "label": "existing",
            "cmd": "skip",
            "card_hint": "a",
            "profile": "flashsystem_5200",
            "live": True,
            "skip": True,
        },
    ]

    results = run_lun_steps(
        steps,
        lambda card_hint, command: calls.append((card_hint, command)) or "ok",
    )

    assert calls == [("a", "create")]
    assert [result["status"] for result in results] == [
        "ok",
        "plan-only",
        "skipped",
    ]
