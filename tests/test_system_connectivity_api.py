from launchpad.health_server import HealthCard, HealthServer
from launchpad.system_connectivity_page import SYSTEM_CONNECTIVITY_PATH


def _unlock(server: HealthServer) -> None:
    server.set_settings_backend(lambda _key, default: default, lambda _key, _value: None)


def test_live_requires_unlock(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(server, "is_unlocked", lambda: False)
    try:
        server.scan_system_connectivity_live()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "unlock" in str(exc).lower()


def test_live_svc_happy_path(monkeypatch):
    server = HealthServer()
    _unlock(server)
    card = HealthCard(
        card_id=1, name="Hartford", host="10.0.0.1", port=22, username="u",
        key_path="/tmp/key", device_profile="flashsystem_7200",
    )
    server._cards[1] = card
    server.set_monitor_enabled(card_id=1, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)

    def _runner(_card):
        def run(command):
            if "lscloudcallhome" in command:
                return "id:status\n0:enabled\n"
            if "lsdnsserver" in command:
                return "id:name:IP_address\n0:dns1:10.1.1.1\n"
            if "lssnmpserver" in command:
                return "id:IP:port\n0:10.2.2.2:162\n"
            if "lssystem" in command:
                return "name:c1\ncluster_ntp_IP_address:10.3.3.3\n"
            return ""
        return run

    monkeypatch.setattr(server, "_lun_run_command", _runner)
    result = server.scan_system_connectivity_live()
    assert result["errors"] == []
    assert result["dns"][0]["configured"] == "yes"
    assert result["ntp"][0]["configured"] == "yes"
    assert result["call_home"][0]["configured"] == "yes"


def test_live_hpe_call_home_na(monkeypatch):
    server = HealthServer()
    _unlock(server)
    card = HealthCard(
        card_id=2,
        name="Primera",
        host="10.0.0.2",
        port=22,
        username="3paradm",
        key_path="",
        password="secret",
        device_profile="hpe_primera_600",
    )
    server._cards[2] = card
    server.set_monitor_enabled(card_id=2, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)

    def fake_hpe(_host, _port, _user, commands, **_kwargs):
        outputs = []
        for command in commands:
            if command == "shownet":
                outputs.append(
                    "Default route :   10.1.1.1\n"
                    "NTP server    :   10.5.5.5\n"
                    "DNS server    :   10.6.6.6\n"
                )
            elif command == "showsnmpmgr":
                outputs.append("Id IPAddr Port\n1 10.2.2.2 162\n")
            else:
                outputs.append("")
        return outputs

    monkeypatch.setattr(
        "launchpad.health_server.run_ssh_auth_hpe_commands",
        fake_hpe,
    )
    result = server.scan_system_connectivity_live()
    assert result["errors"] == []
    assert result["call_home"][0]["configured"] == "n/a"
    assert result["dns"][0]["configured"] == "yes"
    assert result["ntp"][0]["configured"] == "yes"
    assert result["snmp"][0]["configured"] == "yes"


def test_page_route_constant():
    assert SYSTEM_CONNECTIVITY_PATH == "/system-connectivity"
