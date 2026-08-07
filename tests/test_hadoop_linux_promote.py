from launchpad.command_format import parse_command_lines
from launchpad.database import Database
from launchpad.hadoop_linux_promote import (
    ensure_hadoop_linux_cards,
    looks_like_hadoop_host,
)


def _ssh_card(db: Database, **overrides) -> int:
    data = {
        "name": "SVR-WEB",
        "card_type": "ssh",
        "host": "10.0.0.9",
        "port": 22,
        "username": "root",
        "encrypted_password": "x",
        "device_profile": "",
        "custom_commands": "",
        "category": "General",
    }
    data.update(overrides)
    return db.add_card(data)


def test_looks_like_hadoop_host_matches_name_and_hdp():
    assert looks_like_hadoop_host("DLA-W02HDP01 - Hadoop WAG2")
    assert looks_like_hadoop_host("edge-node", category="Hadoop")
    assert not looks_like_hadoop_host("SVR-WEB")
    assert not looks_like_hadoop_host("FlashSystem 5200")


def test_ensure_hadoop_linux_cards_promotes_general_ssh_named_hadoop(tmp_path):
    db = Database(tmp_path / "launchpad.db")
    hadoop_id = _ssh_card(
        db,
        name="DLA-W02HDP01 - Hadoop WAG2",
        host="172.31.77.34",
        device_profile="",
        custom_commands="uptime",
    )
    other_id = _ssh_card(db, name="SVR-WEB", host="10.0.0.2")

    assert ensure_hadoop_linux_cards(db) == 1

    hadoop = db.get_card(hadoop_id)
    other = db.get_card(other_id)
    assert hadoop is not None and other is not None
    assert hadoop.device_profile == "hadoop_linux"
    assert other.device_profile == ""
    labels = [label for label, _ in parse_command_lines(hadoop.custom_commands)]
    assert any(label.startswith("Power -") for label in labels)
    assert "uptime" in hadoop.custom_commands


def test_ensure_hadoop_linux_cards_skips_storage_profiles(tmp_path):
    db = Database(tmp_path / "launchpad.db")
    card_id = _ssh_card(
        db,
        name="Hadoop on array? no",
        device_profile="flashsystem_5200",
        custom_commands="lsiogrp",
    )

    assert ensure_hadoop_linux_cards(db) == 0
    assert db.get_card(card_id).device_profile == "flashsystem_5200"


def test_ensure_hadoop_linux_cards_adds_missing_power_commands(tmp_path):
    db = Database(tmp_path / "launchpad.db")
    card_id = _ssh_card(
        db,
        name="Hadoop node",
        device_profile="hadoop_linux",
        custom_commands="Health - Uptime|uptime",
    )

    assert ensure_hadoop_linux_cards(db) == 1
    card = db.get_card(card_id)
    labels = [label for label, _ in parse_command_lines(card.custom_commands)]
    assert "Health - Uptime" in labels
    assert any(label.startswith("Power -") for label in labels)


def test_host_power_empty_state_mentions_device_profile():
    from launchpad.host_power import HOST_POWER_HTML

    assert "Hadoop / Linux SSH" in HOST_POWER_HTML
