import pytest

from launchpad.vcenters_directory import (
    SETTING_VCENTERS_DIRECTORY,
    delete_vcenter,
    effective_vcenter_url,
    normalize_vcenter,
    normalize_vcenters,
    parse_vcenters_setting,
    upsert_vcenter,
    vcenter_default_url,
)


def test_setting_key_and_default_url():
    assert SETTING_VCENTERS_DIRECTORY == "vcenters_directory"
    assert vcenter_default_url("10.1.2.3") == "https://10.1.2.3/ui"
    assert effective_vcenter_url({"address": "vc.example.com", "url": ""}) == (
        "https://vc.example.com/ui"
    )
    assert effective_vcenter_url(
        {"address": "10.1.2.3", "url": "https://10.1.2.3/vsphere-client"}
    ) == "https://10.1.2.3/vsphere-client"


def test_normalize_vcenter_requires_name_and_address():
    with pytest.raises(ValueError):
        normalize_vcenter({"name": "", "address": "10.0.0.1"})
    with pytest.raises(ValueError):
        normalize_vcenter({"name": "VC1", "address": ""})
    with pytest.raises(ValueError):
        normalize_vcenter({"name": "VC1", "address": "https://10.0.0.1"})
    with pytest.raises(ValueError):
        normalize_vcenter({"name": "VC1", "address": "10.0.0.1", "url": "vc.local/ui"})


def test_parse_corrupt_or_missing_setting_is_empty():
    assert parse_vcenters_setting(None) == []
    assert parse_vcenters_setting("") == []
    assert parse_vcenters_setting("{not json") == []
    assert normalize_vcenters("nope") == []
    assert normalize_vcenters([{"name": "", "address": "x"}]) == []


def test_upsert_assigns_id_sorts_and_delete_unknown_is_noop():
    store = upsert_vcenter([], {"name": "Bravo", "address": "10.0.0.2", "location": "DVN"})
    store = upsert_vcenter(
        store, {"name": "alpha", "address": "10.0.0.1", "location": "WAG"}
    )
    assert [row["name"] for row in store] == ["alpha", "Bravo"]
    assert all(row["id"] for row in store)
    vid = store[0]["id"]
    updated = upsert_vcenter(
        store,
        {
            "id": vid,
            "name": "alpha",
            "address": "10.0.0.9",
            "location": "WAG",
            "url": "https://10.0.0.9/ui",
        },
    )
    assert len(updated) == 2
    assert updated[0]["address"] == "10.0.0.9"
    assert delete_vcenter(updated, "missing") == updated
    assert len(delete_vcenter(updated, vid)) == 1
