"""Site Lookup offline store and payload helpers."""

from launchpad.site_lookup_data import (
    payload_from_lun_offline,
    payload_from_offline_snapshot,
    payload_has_inventory,
)
from launchpad.site_lookup_offline import (
    normalize_store,
    snapshot_from_live_payload,
    upsert_snapshot,
)


def test_payload_has_inventory():
    assert not payload_has_inventory({})
    assert not payload_has_inventory({"hosts": []})
    assert payload_has_inventory({"hosts": [{"name": "h1"}]})
    assert payload_has_inventory({"pools": [{"name": "P0"}]})


def test_upsert_and_normalize_store():
    store = upsert_snapshot(
        {},
        {
            "card_id": 1,
            "card": {"id": 1, "name": "site-a", "host": "10.0.0.1"},
            "hosts": [{"name": "h1"}],
            "volumes": [],
            "mappings": [],
            "consistency_groups": [],
            "pools": [{"name": "P0"}],
            "refreshed_at": "2026-08-06T12:00:00Z",
        },
    )
    cleaned = normalize_store(store)
    assert cleaned["1"]["card"]["name"] == "site-a"
    assert cleaned["1"]["hosts"][0]["name"] == "h1"


def test_snapshot_from_live_payload_and_offline_source():
    live = {
        "card": {"id": 2, "name": "b", "host": "1.1.1.1", "model": "FS", "device_profile": "flashsystem_5200", "serial": "S"},
        "hosts": [{"name": "h"}],
        "volumes": [{"name": "v"}],
        "mappings": [{"vdisk_name": "v"}],
        "consistency_groups": [{"name": "cg"}],
        "pools": [{"name": "P0", "used_pct": 10}],
        "refreshed_at": "2026-08-06T13:00:00Z",
        "source": "ssh",
    }
    snap = snapshot_from_live_payload(live)
    assert snap is not None
    payload = payload_from_offline_snapshot(snap)
    assert payload["source"] == "offline"
    assert payload["hosts"][0]["name"] == "h"
    assert payload["refreshed_at"] == "2026-08-06T13:00:00Z"


def test_payload_from_lun_offline():
    payload = payload_from_lun_offline(
        {
            "card_id": 3,
            "site_name": "lun-site",
            "host": "2.2.2.2",
            "device_profile": "flashsystem_5200",
            "updated_at": "2026-08-01T00:00:00Z",
            "hosts": [{"name": "host-a"}],
            "volumes": [{"name": "vol-a"}],
        }
    )
    assert payload["source"] == "offline_lun"
    assert payload["card"]["name"] == "lun-site"
    assert payload["hosts"][0]["name"] == "host-a"
    assert payload["volumes"][0]["name"] == "vol-a"
    assert payload["mappings"] == []
