from launchpad.host_volume_health import (
    filter_problem_hosts,
    filter_problem_volumes,
    normalize_gui_url,
    resolve_gui_url,
    status_is_offline_or_degraded,
)


def test_status_offline_degraded():
    assert status_is_offline_or_degraded("offline") is True
    assert status_is_offline_or_degraded("degraded") is True
    assert status_is_offline_or_degraded("offline_unconfigured") is True
    assert status_is_offline_or_degraded("online") is False
    assert status_is_offline_or_degraded("active") is False
    assert status_is_offline_or_degraded("") is False


def test_normalize_gui_url():
    assert normalize_gui_url("10.1.2.3") == "https://10.1.2.3"
    assert normalize_gui_url("https://x") == "https://x"
    assert normalize_gui_url("  ") == ""


def test_resolve_gui_url_prefers_url_then_host():
    assert resolve_gui_url("https://gui.example", "10.1.2.3") == "https://gui.example"
    assert resolve_gui_url("", "10.245.16.56") == "https://10.245.16.56"
    assert resolve_gui_url("  ", "  ") == ""


def test_resolve_gui_url_3par_appends_8443():
    assert (
        resolve_gui_url("", "pla-w023par01", "hpe_3par_8200")
        == "https://pla-w023par01:8443"
    )
    assert (
        resolve_gui_url("", "10.1.2.3", "hpe_3par_8400")
        == "https://10.1.2.3:8443"
    )
    assert (
        resolve_gui_url("", "pla-w023par01", "hpe_3par_8450")
        == "https://pla-w023par01:8443"
    )


def test_resolve_gui_url_prefers_admin_url_over_3par_default():
    assert (
        resolve_gui_url("https://gui.example", "pla-w023par01", "hpe_3par_8200")
        == "https://gui.example"
    )


def test_resolve_gui_url_primera_and_other_profiles_no_8443():
    assert (
        resolve_gui_url("", "pla-w023par01", "hpe_primera_600")
        == "https://pla-w023par01"
    )
    assert resolve_gui_url("", "10.1.2.3", "flashsystem_5200") == "https://10.1.2.3"
    assert resolve_gui_url("", "10.1.2.3", "") == "https://10.1.2.3"
    assert resolve_gui_url("", "10.1.2.3") == "https://10.1.2.3"


def test_resolve_gui_url_does_not_double_existing_port():
    assert (
        resolve_gui_url("", "pla-w023par01:8443", "hpe_3par_8200")
        == "https://pla-w023par01:8443"
    )
    assert (
        resolve_gui_url("", "10.1.2.3:9443", "hpe_3par_8200")
        == "https://10.1.2.3:9443"
    )


def test_filter_problem_hosts_offline_degraded_only():
    rows = [
        {"host_name": "host_a", "status": "offline"},
        {"host_name": "host_b", "status": "online"},
        {"host_name": "host_c", "status": "degraded"},
        {"host_name": "host_d", "status": "offline_unconfigured"},
    ]
    result = filter_problem_hosts(
        rows, card_name="Hartford", host="10.0.0.1", vendor="ibm"
    )
    assert len(result) == 3
    names = [row["host_name"] for row in result]
    assert names == ["host_a", "host_c", "host_d"]
    assert result[0]["card_name"] == "Hartford"
    assert result[0]["host"] == "10.0.0.1"
    assert result[0]["vendor"] == "ibm"
    assert result[0]["status"] == "offline"


def test_filter_problem_hosts_uses_state_field():
    rows = [{"host_name": "hpe_host", "state": "degraded"}]
    result = filter_problem_hosts(
        rows, card_name="Primera", host="10.0.0.2", vendor="hpe"
    )
    assert len(result) == 1
    assert result[0]["host_name"] == "hpe_host"
    assert result[0]["status"] == "degraded"


def test_filter_problem_volumes_offline_degraded_only():
    rows = [
        {"name": "vol_a", "status": "degraded", "pool": "Pool0"},
        {"name": "vol_b", "status": "online", "pool_or_cpg": "SSD_r5"},
        {"name": "vol_c", "status": "offline", "pool": "Pool1"},
    ]
    result = filter_problem_volumes(
        rows, card_name="Hartford", host="10.0.0.1", vendor="ibm"
    )
    assert len(result) == 2
    assert result[0]["volume_name"] == "vol_a"
    assert result[0]["pool_or_cpg"] == "Pool0"
    assert result[1]["volume_name"] == "vol_c"


def test_filter_problem_volumes_uses_state_for_hpe():
    rows = [{"name": "vv_bad", "state": "degraded", "pool_or_cpg": "SSD_r5"}]
    result = filter_problem_volumes(
        rows, card_name="Primera", host="10.0.0.2", vendor="hpe"
    )
    assert len(result) == 1
    assert result[0]["volume_name"] == "vv_bad"
    assert result[0]["status"] == "degraded"


def test_filter_problem_volumes_ignores_mstr_ownership():
    rows = [{"name": "vv_ok", "mstr": "degraded", "pool_or_cpg": "SSD_r5"}]
    result = filter_problem_volumes(
        rows, card_name="Primera", host="10.0.0.2", vendor="hpe"
    )
    assert result == []
