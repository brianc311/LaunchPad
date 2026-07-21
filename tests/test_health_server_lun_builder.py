import inspect
import io
import json

import pytest

from launchpad.health_server import DASHBOARD_HTML, HealthServer, _HealthHandler
from launchpad.lun_builder import LUN_BUILDER_PATH
from launchpad.lun_builder_data import LUN_BUILDS_SETTING


def _settings_backend(initial: dict[str, str] | None = None):
    settings = dict(initial or {})

    def get_setting(key: str, default: str) -> str:
        return settings.get(key, default)

    def set_setting(key: str, value: str) -> None:
        settings[key] = value

    return settings, get_setting, set_setting


def _call_lun_builds_api(
    monkeypatch,
    server: HealthServer,
    method: str,
    payload: dict | None = None,
) -> tuple[int, dict]:
    body = json.dumps(payload or {}).encode()
    handler = object.__new__(_HealthHandler)
    handler.path = "/api/lun-builds"
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = io.BytesIO(body)
    responses: list[tuple[int, dict]] = []
    handler._send_json = lambda data, status=200: responses.append((status, data))
    monkeypatch.setattr(
        "launchpad.health_server.get_health_server",
        lambda: server,
    )

    getattr(handler, f"do_{method}")()

    return responses[0]


def test_health_server_exposes_lun_builder_url():
    server = HealthServer()

    assert server.lun_builder_url.endswith(LUN_BUILDER_PATH)


def test_health_dashboard_links_to_lun_builder():
    assert f'href="{LUN_BUILDER_PATH}"' in DASHBOARD_HTML


def test_lun_builds_replace_upsert_and_delete_persist():
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    first = {
        "id": "first",
        "name": "First build",
        "hosts": [],
        "luns": [],
    }
    second = {
        "id": "second",
        "name": "Second build",
        "hosts": [],
        "luns": [],
    }

    assert server.set_lun_builds([first]) == [
        {
            "id": "first",
            "name": "First build",
            "location": "",
            "notes": "",
            "updated_at": "",
            "is_template": False,
            "default_storage_profile": "",
            "default_pool_or_cpg": "",
            "default_card_hint": "",
            "plan_done": {},
            "command_done": {},
            "hosts": [],
            "luns": [],
        }
    ]
    assert {build["id"] for build in server.upsert_lun_build(second)} == {
        "first",
        "second",
    }
    builds = server.delete_lun_build("first")

    assert [build["id"] for build in builds] == ["second"]
    assert json.loads(settings[LUN_BUILDS_SETTING]) == builds


def test_api_get_lun_builds_includes_site_templates(monkeypatch):
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)

    status, payload = _call_lun_builds_api(monkeypatch, server, "GET")

    assert status == 200
    template_ids = {t["id"] for t in payload["templates"]}
    assert template_ids == {
        "template-hartford-ct",
        "template-jupiter-fl",
        "template-pendergrass-ga",
        "template-mount-vernon-il",
    }
    assert all(
        build["id"] not in template_ids for build in payload["builds"]
    )
    assert LUN_BUILDS_SETTING not in settings


@pytest.mark.parametrize(
    "build",
    [
        {
            "id": "template-hartford-ct",
            "name": "Overwrite",
            "hosts": [],
            "luns": [],
        },
        {
            "id": "copied-template",
            "name": "Copied template",
            "is_template": True,
            "hosts": [],
            "luns": [],
        },
    ],
)
def test_api_rejects_template_upsert(monkeypatch, build):
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)

    status, payload = _call_lun_builds_api(
        monkeypatch,
        server,
        "POST",
        {"build": build},
    )

    assert status == 400
    assert payload["error"] == (
        "Cannot overwrite a built-in template; use Save as new."
    )
    assert LUN_BUILDS_SETTING not in settings


def test_api_rejects_template_delete(monkeypatch):
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)

    status, payload = _call_lun_builds_api(
        monkeypatch,
        server,
        "POST",
        {"delete_id": "template-hartford-ct"},
    )

    assert status == 400
    assert payload["error"] == "Cannot delete a built-in template."
    assert LUN_BUILDS_SETTING not in settings


def test_set_lun_builds_does_not_persist_templates():
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)

    builds = server.set_lun_builds(
        [
            {
                "id": "template-injected",
                "name": "Injected",
                "hosts": [],
                "luns": [],
            },
            {
                "id": "saved",
                "name": "Saved",
                "hosts": [],
                "luns": [],
            },
        ]
    )

    assert [build["id"] for build in builds] == ["saved"]
    assert json.loads(settings[LUN_BUILDS_SETTING]) == builds


def test_lun_builds_require_settings_backend_for_writes():
    server = HealthServer()

    assert server.lun_builds_persist_available() is False
    assert server.get_lun_builds() == []
    with pytest.raises(
        RuntimeError,
        match="LaunchPad must be unlocked to save LUN builds.",
    ):
        server.set_lun_builds([])


def test_import_lun_build_merges_without_running_create():
    _settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    server.set_lun_builds(
        [
            {
                "id": "first",
                "name": "First",
                "hosts": [{"lpar_name": "existing", "wwpn1": "AA"}],
                "luns": [],
            }
        ]
    )
    content = (
        "lpar_name,wwpn1\n"
        "existing,AA\n"
        "new-host,BB\n"
    ).encode()

    result = server.import_lun_build_upload(
        "hosts.csv",
        content,
        mode="merge",
        build_id="first",
    )

    assert [host["lpar_name"] for host in result["build"]["hosts"]] == [
        "existing",
        "new-host",
    ]
    assert "create" not in result


def test_pull_fc_hosts_filters_card_and_merges_into_build(monkeypatch):
    _settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    server.set_lun_builds(
        [{"id": "first", "name": "First", "hosts": [], "luns": []}]
    )
    monkeypatch.setattr(
        server,
        "list_cards",
        lambda **_kwargs: [
            {
                "name": "Storage A",
                "fc_hosts": [{"host_name": "host1", "wwpns": "AA; BB"}],
            },
            {
                "name": "Storage B",
                "fc_hosts": [{"host_name": "host2", "wwpns": "CC; DD"}],
            },
        ],
    )

    result = server.pull_fc_hosts("first", card_name="Storage A")

    assert result["build"]["hosts"][0]["lpar_name"] == "host1"
    assert result["build"]["hosts"][0]["wwpn1"] == "AA"
    assert result["build"]["hosts"][0]["wwpn2"] == "BB"
    assert len(result["build"]["hosts"]) == 1


def test_health_handler_declares_import_and_pull_fc_routes():
    source = inspect.getsource(_HealthHandler.do_POST)

    assert "/api/lun-builds/import" in source
    assert "/api/lun-builds/pull-fc" in source


def test_health_handler_declares_lun_preview_and_create_routes():
    source = inspect.getsource(_HealthHandler.do_POST)

    assert "/api/lun-builds/preview" in source
    assert "/api/lun-builds/create" in source


def test_preview_lun_build_reports_missing_live_card():
    _settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    server.set_lun_builds(
        [
            {
                "id": "first",
                "name": "First",
                "hosts": [],
                "luns": [
                    {
                        "purpose": "vol",
                        "count": 1,
                        "size": "10GB",
                        "pool_or_cpg": "Pool0",
                        "storage_profile": "flashsystem_5200",
                        "card_hint": "missing",
                    }
                ],
            }
        ]
    )

    result = server.preview_lun_build("first")

    assert result["ok"] is False
    assert "No Health Card matches" in result["warnings"][0]


def test_preview_plan_only_build_succeeds_without_card():
    _settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    server.set_lun_builds(
        [
            {
                "id": "plan",
                "name": "Plan",
                "hosts": [],
                "luns": [
                    {
                        "purpose": "vol",
                        "count": 1,
                        "size": "10GB",
                        "pool_or_cpg": "P0",
                        "storage_profile": "ibm_ds8884",
                    }
                ],
            }
        ]
    )

    result = server.preview_lun_build("plan")

    assert result["ok"] is True
    assert result["plan_only"] is True
    assert result["runnable"] is False
    assert result["steps"][0]["live"] is False


def test_preview_svc_collects_inventory_from_resolved_card(monkeypatch):
    _settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    server.set_lun_builds(
        [
            {
                "id": "svc",
                "name": "SVC",
                "hosts": [],
                "luns": [
                    {
                        "purpose": "vol",
                        "count": 1,
                        "size": "10GB",
                        "pool_or_cpg": "P0",
                        "storage_profile": "flashsystem_5200",
                        "card_hint": "cardA",
                    }
                ],
            }
        ]
    )
    server.register_card(1, "cardA", "array.example", 22, "operator", "")
    monkeypatch.setattr(
        "launchpad.health_server.collect_inventory",
        lambda _run: {"vdisks": {"vol"}},
    )

    result = server.preview_lun_build("svc")

    assert result["steps"][0]["skip"] is True


def test_create_lun_build_requires_confirmation():
    server = HealthServer()

    result = server.create_lun_build("first", confirm=False)

    assert result["ok"] is False
    assert "confirm must be true" in result["warnings"][0]


def test_create_lun_build_requires_matching_runnable_preview():
    _settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    server.set_lun_builds(
        [
            {
                "id": "first",
                "name": "First",
                "hosts": [],
                "luns": [
                    {
                        "purpose": "vol",
                        "count": 1,
                        "size": "10GB",
                        "pool_or_cpg": "Pool0",
                        "storage_profile": "hpe_primera_600",
                        "card_hint": "cardA",
                    }
                ],
            }
        ]
    )

    result = server.create_lun_build("first", confirm=True)

    assert result["ok"] is False
    assert "Preview must be run again" in result["warnings"][0]


def test_create_lun_build_rejects_build_changed_after_preview(monkeypatch):
    _settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    build = {
        "id": "first",
        "name": "First",
        "hosts": [],
        "luns": [
            {
                "purpose": "vol",
                "count": 1,
                "size": "10GB",
                "pool_or_cpg": "Pool0",
                "storage_profile": "hpe_primera_600",
                "card_hint": "cardA",
            }
        ],
    }
    server.set_lun_builds([build])
    server.register_card(
        1,
        "cardA",
        "array.example",
        22,
        "operator",
        "",
        device_profile="hpe_primera_600",
    )
    monkeypatch.setattr(
        server,
        "_lun_run_command",
        lambda _card: lambda _command: "created",
    )
    assert server.preview_lun_build("first")["ok"] is True
    build["luns"][0]["size"] = "20GB"
    server.set_lun_builds([build])

    result = server.create_lun_build("first", confirm=True)

    assert result["ok"] is False
    assert "Preview must be run again" in result["warnings"][0]
    build["luns"][0]["size"] = "10GB"
    server.set_lun_builds([build])
    assert server.create_lun_build("first", confirm=True)["ok"] is False


def test_preview_warns_when_live_profile_conflicts_with_card_family():
    _settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    server.set_lun_builds(
        [
            {
                "id": "first",
                "name": "First",
                "hosts": [],
                "luns": [
                    {
                        "purpose": "vol",
                        "count": 1,
                        "size": "10GB",
                        "pool_or_cpg": "Pool0",
                        "storage_profile": "hpe_primera_600",
                        "card_hint": "cardA",
                    }
                ],
            }
        ]
    )
    server.register_card(
        1,
        "cardA",
        "array.example",
        22,
        "operator",
        "",
        device_profile="flashsystem_5200",
    )

    result = server.preview_lun_build("first")

    assert result["ok"] is False
    assert "profile" in result["warnings"][0].lower()
    assert "flashsystem_5200" in result["warnings"][0]


def test_create_lun_build_runs_live_steps(monkeypatch):
    _settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    server.set_lun_builds(
        [
            {
                "id": "first",
                "name": "First",
                "hosts": [],
                "luns": [
                    {
                        "purpose": "vol",
                        "count": 1,
                        "size": "10GB",
                        "pool_or_cpg": "Pool0",
                        "storage_profile": "hpe_primera_600",
                        "card_hint": "cardA",
                    }
                ],
            }
        ]
    )
    server.register_card(
        1,
        "cardA",
        "array.example",
        22,
        "operator",
        "",
        device_profile="hpe_primera_600",
    )
    calls = []
    monkeypatch.setattr(
        server,
        "_lun_run_command",
        lambda _card: lambda command: calls.append(command) or "created",
    )
    assert server.preview_lun_build("first")["ok"] is True

    result = server.create_lun_build("first", confirm=True)

    assert result["ok"] is True
    assert calls == ["createvv Pool0 vol 10g"]
    assert server.create_lun_build("first", confirm=True)["ok"] is False
