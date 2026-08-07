"""Ansible Pad control-host settings: key constants and normalization."""

from __future__ import annotations

from typing import Any

ANSIBLE_PAD_HOST = "ansible_pad_host"
ANSIBLE_PAD_USER = "ansible_pad_user"
ANSIBLE_PAD_KEY_PATH = "ansible_pad_key_path"
ANSIBLE_PAD_KEY_PASSPHRASE = "ansible_pad_key_passphrase"
ANSIBLE_PAD_PASSWORD = "ansible_pad_password"
ANSIBLE_PAD_REMOTE_DIR = "ansible_pad_remote_dir"
ANSIBLE_PAD_DEFAULT_PLAYBOOK = "ansible_pad_default_playbook"

DEFAULT_ANSIBLE_PAD_HOST = "plp5-dz5-nw"

_SETTING_TO_FIELD = {
    ANSIBLE_PAD_HOST: "host",
    ANSIBLE_PAD_USER: "user",
    ANSIBLE_PAD_KEY_PATH: "key_path",
    ANSIBLE_PAD_KEY_PASSPHRASE: "key_passphrase",
    ANSIBLE_PAD_PASSWORD: "password",
    ANSIBLE_PAD_REMOTE_DIR: "remote_dir",
    ANSIBLE_PAD_DEFAULT_PLAYBOOK: "default_playbook",
}

_DEFAULTS: dict[str, str] = {
    "host": DEFAULT_ANSIBLE_PAD_HOST,
    "user": "",
    "key_path": "",
    "key_passphrase": "",
    "password": "",
    "remote_dir": "",
    "default_playbook": "",
}


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_ansible_pad_settings(raw: dict) -> dict:
    """Return host, user, key_path, key_passphrase, password, remote_dir, default_playbook."""
    data = raw if isinstance(raw, dict) else {}
    out = dict(_DEFAULTS)
    for setting_key, field in _SETTING_TO_FIELD.items():
        if setting_key in data:
            val = _clean_str(data[setting_key])
        elif field in data:
            val = _clean_str(data[field])
        else:
            continue
        if field == "host" and not val:
            continue
        out[field] = val
    return out
