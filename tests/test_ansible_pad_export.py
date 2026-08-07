from launchpad.ansible_pad_export import build_ansible_pad_files, build_ansible_pad_zip_bytes
from launchpad.ansible_pad_settings import DEFAULT_ANSIBLE_PAD_HOST, normalize_ansible_pad_settings
import zipfile, io

def test_default_host():
    s = normalize_ansible_pad_settings({})
    assert s["host"] == "plp5-dz5-nw"

def test_package_contains_inventory_playbooks_readme():
    files = build_ansible_pad_files(
        cards=[{"id": 1, "name": "site-a", "host": "10.0.0.1", "username": "user", "device_profile": "flashsystem_5200"}],
        contingency_groups=[],
    )
    assert "inventory/hosts.yml" in files
    assert "10.0.0.1" in files["inventory/hosts.yml"]
    assert "playbooks/start_fc_consistgrp.yml" in files
    assert "prestartfcconsistgrp" in files["playbooks/start_fc_consistgrp.yml"]
    assert "startfcconsistgrp" in files["playbooks/start_fc_consistgrp.yml"]
    assert "plp5-dz5-nw" in files["README.md"]
    assert "BEGIN RSA PRIVATE KEY" not in "\n".join(files.values())

def test_zip_bytes_roundtrip():
    raw = build_ansible_pad_zip_bytes(cards=[], contingency_groups=[])
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = zf.namelist()
    assert "README.md" in names
    assert any(n.startswith("playbooks/") for n in names)
