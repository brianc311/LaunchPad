import zipfile, io

from launchpad.ansible_pad_export import build_ansible_pad_files, build_ansible_pad_zip_bytes
from launchpad.ansible_pad_settings import DEFAULT_ANSIBLE_PAD_HOST, normalize_ansible_pad_settings

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


def test_inventory_disambiguates_duplicate_card_names():
    files = build_ansible_pad_files(
        cards=[
            {"id": 1, "name": "Site A", "host": "10.0.0.1"},
            {"id": 2, "name": "Site A", "host": "10.0.0.2"},
        ],
        contingency_groups=[],
    )

    inventory = files["inventory/hosts.yml"]
    assert "Site_A:" in inventory
    assert "Site_A_card_2:" in inventory


def test_playbooks_use_raw_quoted_and_explicit_target_hosts():
    files = build_ansible_pad_files(cards=[], contingency_groups=[])
    start_playbook = files["playbooks/start_fc_consistgrp.yml"]
    snap_playbook = files["playbooks/snap_copy_stub.yml"]

    assert 'hosts: "{{ target_hosts | default([]) }}"' in start_playbook
    assert 'hosts: "{{ target_hosts | default([]) }}"' in snap_playbook
    assert "ansible.builtin.raw" in start_playbook
    assert "ansible.builtin.raw" in snap_playbook
    assert "{{ cg_name | quote }}" in start_playbook
    assert "ansible_connection: ssh" in files["README.md"]
    assert "--limit" in files["README.md"]


def test_zip_bytes_roundtrip():
    raw = build_ansible_pad_zip_bytes(cards=[], contingency_groups=[])
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = zf.namelist()
    assert "README.md" in names
    assert any(n.startswith("playbooks/") for n in names)
