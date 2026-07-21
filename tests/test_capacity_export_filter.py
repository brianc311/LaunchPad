from pathlib import Path
from unittest.mock import MagicMock

from launchpad.capacity_export import (
    card_ids_included_for_export,
    export_storage_capacity_excel,
    keep_inventory_row,
)
from launchpad.database import Card


def _ssh_card(card_id: int, name: str) -> Card:
    return Card(
        id=card_id,
        name=name,
        card_type="ssh",
        host=f"10.0.0.{card_id}",
        port=22,
        serial_number="",
        username="",
        encrypted_password="",
        encrypted_key_passphrase="",
        encrypted_key="",
        url="",
        icon="",
        category="Cat",
        sort_order=0,
        glow_color="",
        key_file_path="",
        device_profile="FlashSystem",
        custom_commands="",
    )


def test_include_off_false_keeps_only_monitor_on():
    ids = card_ids_included_for_export(
        [1, 2, 3],
        include_monitor_off=False,
        monitor_enabled={1: True, 2: False},
    )
    assert ids == frozenset({1})


def test_include_off_true_keeps_all_ids():
    ids = card_ids_included_for_export(
        [1, 2],
        include_monitor_off=True,
        monitor_enabled={1: False, 2: False},
    )
    assert ids == frozenset({1, 2})


def test_missing_monitor_key_treated_as_off():
    ids = card_ids_included_for_export(
        [9],
        include_monitor_off=False,
        monitor_enabled={},
    )
    assert ids == frozenset()


def test_keep_inventory_row_rules():
    included = frozenset({5})
    assert keep_inventory_row(
        matched_card_id=5,
        included_card_ids=included,
        include_monitor_off=False,
    )
    assert not keep_inventory_row(
        matched_card_id=6,
        included_card_ids=included,
        include_monitor_off=False,
    )
    assert not keep_inventory_row(
        matched_card_id=None,
        included_card_ids=included,
        include_monitor_off=False,
    )
    assert keep_inventory_row(
        matched_card_id=None,
        included_card_ids=included,
        include_monitor_off=True,
    )


def test_export_skips_monitor_off_cards(monkeypatch, tmp_path: Path):
    entry_on = MagicMock(card_id=1, name="On")
    entry_off = MagicMock(card_id=2, name="Off")
    monkeypatch.setattr(
        "launchpad.capacity_export.build_health_dashboard_entries",
        lambda db, key: [entry_on, entry_off],
    )
    monkeypatch.setattr(
        "launchpad.capacity_export._refresh_entry_capacity",
        lambda entry: ({"name": entry.name, "used_pct": 1, "used_bytes": 1, "total_bytes": 100}, [], None),
    )
    db = MagicMock()
    db.list_cards.return_value = [_ssh_card(1, "On"), _ssh_card(2, "Off")]
    monkeypatch.setattr("launchpad.capacity_export.INVENTORY_ROWS", [])

    out = tmp_path / "cap.xlsx"
    result = export_storage_capacity_excel(
        db,
        b"0" * 32,
        out,
        include_monitor_off=False,
        monitor_enabled={1: True, 2: False},
    )
    assert out.exists()
    assert result.extra_rows == 1
