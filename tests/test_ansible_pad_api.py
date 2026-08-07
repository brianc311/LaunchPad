import io
import json

import launchpad.health_server as health_server_module
from launchpad.ansible_pad_settings import (
    ANSIBLE_PAD_HOST,
    ANSIBLE_PAD_PASSWORD,
    ANSIBLE_PAD_REMOTE_DIR,
    ANSIBLE_PAD_USER,
)
from launchpad.health_server import HealthCard, HealthServer, _HealthHandler


def _settings_backend(initial: dict[str, str] | None = None):
    settings = dict(initial or {})

    def get_setting(key: str, default: str) -> str:
        return settings.get(key, default)

    def set_setting(key: str, value: str) -> None:
        settings[key] = value

    return settings, get_setting, set_setting


def _card() -> HealthCard:
    return HealthCard(
        card_id=1,
        name="Array A",
        host="10.0.0.1",
        port=22,
        username="superuser",
        password="array-secret",
        key_path="",
        device_profile="flashsystem_5200",
    )


def _post(path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    handler = _HealthHandler.__new__(_HealthHandler)
    handler.path = path
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = io.BytesIO(body)
    sent = {}
    handler._send_json = lambda response, status=200: sent.update(
        payload=response, status=status
    )
    handler.do_POST()
    return sent


def test_export_ansible_pad_zip_contains_package_files():
    server = HealthServer()
    server._cards[1] = _card()

    body = server.export_ansible_pad_zip_bytes()

    assert body.startswith(b"PK")


def test_ansible_pad_settings_persist_and_mask_password():
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)

    saved = server.set_ansible_pad_settings(
        {
            "host": "control.example",
            "user": "ansible",
            "password": "control-secret",
            "remote_dir": "/srv/launchpad",
        }
    )

    assert saved["password"] == "***"
    assert settings[ANSIBLE_PAD_HOST] == "control.example"
    assert settings[ANSIBLE_PAD_USER] == "ansible"
    assert settings[ANSIBLE_PAD_PASSWORD] == "control-secret"
    assert settings[ANSIBLE_PAD_REMOTE_DIR] == "/srv/launchpad"
    assert server.get_ansible_pad_settings()["password"] == "***"


def test_sync_run_check_uploads_and_executes_without_confirm():
    settings, getter, setter = _settings_backend(
        {
            ANSIBLE_PAD_HOST: "control.example",
            ANSIBLE_PAD_USER: "ansible",
            ANSIBLE_PAD_REMOTE_DIR: "/srv/launchpad",
        }
    )
    del settings, setter
    server = HealthServer()
    server._cards[1] = _card()
    server.set_settings_backend(getter, lambda *_args: None)
    uploaded: list[str] = []
    commands: list[str] = []

    class FakeSftp:
        def stat(self, _path):
            return None

        def putfo(self, _payload, remote_path):
            uploaded.append(remote_path)

    server.set_ansible_pad_remote_backend(
        connect=lambda _settings: object(),
        sftp=lambda _client: FakeSftp(),
        execute=lambda _client, command: commands.append(command)
        or {"returncode": 0, "stdout": "checked", "stderr": ""},
    )

    result = server.ansible_pad_sync_run(
        playbook="playbooks/start_fc_consistgrp.yml",
        check=True,
        confirm=False,
        extra_vars={"cg_name": "CG_A"},
    )

    assert result["returncode"] == 0
    assert any(path.endswith("inventory/hosts.yml") for path in uploaded)
    assert "--check" in commands[0]
    assert "cg_name" in commands[0]


def test_sync_run_mutating_without_confirm_returns_400(monkeypatch):
    monkeypatch.setattr(
        health_server_module,
        "get_health_server",
        lambda: type(
            "FakeServer",
            (),
            {
                "ansible_pad_sync_run": lambda self, **_kwargs: (_ for _ in ()).throw(
                    ValueError("confirm=true is required for mutating ansible-playbook runs")
                )
            },
        )(),
    )

    response = _post(
        "/api/ansible-pad/sync-run",
        {"playbook": "playbooks/start_fc_consistgrp.yml", "check": False, "confirm": False},
    )

    assert response["status"] == 400
    assert "confirm=true" in response["payload"]["error"]


def test_run_existing_executes_requested_remote_playbook():
    _settings, getter, setter = _settings_backend(
        {
            ANSIBLE_PAD_HOST: "control.example",
            ANSIBLE_PAD_REMOTE_DIR: "/srv/launchpad",
        }
    )
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    commands: list[str] = []
    server.set_ansible_pad_remote_backend(
        connect=lambda _settings: object(),
        sftp=lambda _client: None,
        execute=lambda _client, command: commands.append(command)
        or {"returncode": 0, "stdout": "", "stderr": ""},
    )

    result = server.ansible_pad_run_existing(
        playbook="/opt/runbooks/existing.yml", check=True, confirm=False
    )

    assert result["returncode"] == 0
    assert "/opt/runbooks/existing.yml" in commands[0]
