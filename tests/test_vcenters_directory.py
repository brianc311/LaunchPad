import pytest
from cryptography.fernet import Fernet

from launchpad.crypto import decrypt_text, encrypt_text
from launchpad.vcenters_directory import (
    SETTING_VCENTERS_DIRECTORY,
    VCENTER_PASSWORD_PLACEHOLDER,
    VPXCLIENT_PATH,
    delete_vcenter,
    effective_vcenter_url,
    normalize_vcenter,
    normalize_vcenters,
    parse_vcenters_setting,
    public_vcenter,
    resolve_password_encrypted,
    upsert_vcenter,
    use_vsphere_client_enabled,
    vcenter_default_url,
    vcenter_matches_query,
    vpxclient_argv,
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


def test_vsphere_client_fields_default_off_and_public_hides_secret():
    row = normalize_vcenter(
        {"name": "VC1", "address": "10.0.0.1"}, assign_id=True
    )
    assert row["use_vsphere_client"] is False
    assert row["username"] == ""
    assert row["password_encrypted"] == ""
    pub = public_vcenter(row)
    assert "password_encrypted" not in pub
    assert pub["password"] == ""
    assert pub["use_vsphere_client"] is False


def test_resolve_password_keeps_placeholder_and_clears_empty():
    key = Fernet.generate_key()
    stored = encrypt_text(key, "secret")
    assert (
        resolve_password_encrypted(
            {"password": VCENTER_PASSWORD_PLACEHOLDER}, stored, key
        )
        == stored
    )
    assert resolve_password_encrypted({}, stored, key) == stored
    assert resolve_password_encrypted({"password": ""}, stored, key) == ""
    fresh = resolve_password_encrypted({"password": "n3w"}, stored, key)
    assert decrypt_text(key, fresh) == "n3w"


def test_vpxclient_argv_and_path():
    assert str(VPXCLIENT_PATH) == (
        r"C:\Program Files (x86)\VMware\Infrastructure\Virtual Infrastructure Client\Launcher\VpxClient.exe"
    )
    assert vpxclient_argv("10.1.2.3") == [str(VPXCLIENT_PATH), "-s", "10.1.2.3"]
    assert vpxclient_argv("10.1.2.3", "admin", "pw") == [
        str(VPXCLIENT_PATH),
        "-s",
        "10.1.2.3",
        "-u",
        "admin",
        "-p",
        "pw",
    ]
    assert use_vsphere_client_enabled(True) is True
    assert use_vsphere_client_enabled("true") is True
    assert use_vsphere_client_enabled(None) is False


def test_description_and_vm_notes_default_empty_and_public():
    row = normalize_vcenter(
        {"name": "VC1", "address": "10.0.0.1"}, assign_id=True
    )
    assert row["description"] == ""
    assert row["vm_notes"] == ""
    stored = normalize_vcenter(
        {
            "name": "VC1",
            "address": "10.0.0.1",
            "description": "  purpose line  ",
            "vm_notes": "  web01\napp02  ",
        },
        assign_id=True,
    )
    assert stored["description"] == "purpose line"
    assert stored["vm_notes"] == "web01\napp02"
    pub = public_vcenter(stored)
    assert pub["description"] == "purpose line"
    assert pub["vm_notes"] == "web01\napp02"


def test_vcenter_matches_query_name_address_vm_notes_not_description():
    row = {
        "name": "HPEW101VCENTER6",
        "address": "172.19.195.31",
        "description": "WAG1 compute cluster",
        "vm_notes": "sql01\nweb-prod",
    }
    assert vcenter_matches_query(row, "") is True
    assert vcenter_matches_query(row, "   ") is True
    assert vcenter_matches_query(row, "hpew101") is True
    assert vcenter_matches_query(row, "195.31") is True
    assert vcenter_matches_query(row, "SQL01") is True
    assert vcenter_matches_query(row, "compute cluster") is False
    assert vcenter_matches_query(row, "no-such") is False

