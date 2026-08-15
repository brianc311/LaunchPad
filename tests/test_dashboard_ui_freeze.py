from pathlib import Path

SOURCE = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")


def _method(name: str) -> str:
    marker = f"    def {name}"
    rest = SOURCE.split(marker, 1)[1]
    nxt = rest.find("\n    def ")
    return rest if nxt < 0 else rest[:nxt]


def test_search_keyrelease_filters_in_place_not_refresh_cards():
    bind = SOURCE.split('self.search_entry.bind("<KeyRelease>"', 1)[1].split("\n", 1)[0]
    assert "refresh_cards" not in bind
    assert "_filter_visible_cards" in bind
    assert "def _filter_visible_cards" in SOURCE
    body = _method("_filter_visible_cards")
    assert "filter_dashboard_cards" in body
    assert "grid_remove" in body
    assert "_rebuild_array_rail" in body
    assert "_update_selection_status" in body
    assert "ensure_health_dashboard_registered" not in body
    assert "refresh_cards()" not in body


def test_load_monitor_states_does_not_register_health_cards():
    body = _method("_load_monitor_states")
    assert "get_monitor_states" in body
    assert "ensure_health_dashboard_registered" not in body


def test_startup_health_register_runs_on_worker_thread():
    body = _method("_register_health_cards_main_thread")
    assert "ensure_health_dashboard_registered" in body
    assert "threading.Thread" in body
    assert "daemon=True" in body


def test_refresh_stats_skips_monitor_off_before_ssh_status():
    body = _method("_fetch_all_ssh_stats")
    assert "_is_monitor_on" in body
    assert "Refreshing SSH card stats..." in body
    assert "No sites monitoring." in body
    fetch_status_at = body.index("Refreshing SSH card stats...")
    fetchable_return_at = body.index("if not fetchable:")
    assert fetchable_return_at < fetch_status_at


def _assert_thread_before_register(body: str) -> None:
    assert "threading.Thread" in body
    thread_at = body.index("threading.Thread")
    if "ensure_health_dashboard_registered" in body:
        assert thread_at < body.index("ensure_health_dashboard_registered")
    if "resolve_ssh_metrics_auth" in body:
        assert thread_at < body.index("resolve_ssh_metrics_auth")
    if "_health_ssh_cards" in body:
        assert thread_at < body.index("_health_ssh_cards")


def test_toggle_all_monitoring_flips_widgets_then_registers_off_thread():
    body = _method("_toggle_all_monitoring")
    states_at = body.index("self._monitor_states")
    thread_at = body.index("threading.Thread")
    assert states_at < thread_at
    assert "set_monitor_enabled" in body
    assert "_fetch_all_ssh_stats" not in body
    _assert_thread_before_register(body)
    assert "set_all_monitor_enabled" in body
    assert "_fetch_ssh_stats_worker" in body
    assert "_probe_card_ssh_status" in body
    assert "_set_card_ssh_monitor_off" in body


def test_set_checked_monitoring_does_not_register_on_click_stack():
    body = _method("_set_checked_monitoring")
    if "ensure_health_dashboard_registered" in body:
        _assert_thread_before_register(body)
    else:
        assert "set_card_monitor_enabled" in body


def test_on_card_monitor_toggle_does_not_register_on_click_stack():
    body = _method("_on_card_monitor_toggle")
    if "ensure_health_dashboard_registered" in body:
        _assert_thread_before_register(body)
    else:
        assert "set_card_monitor_enabled" in body


HEADER_OPENERS = (
    "_open_storage_inventory",
    "_open_health_dashboard_all",
    "_open_capacity_report_all",
    "_open_fc_wwpn_report_all",
    "_open_site_lookup_all",
    "_open_ansible_pad",
    "_open_host_power",
    "_open_contingency_groups",
    "_open_fc_consistgrp",
    "_open_esx_snap_policy",
    "_open_lun_builder",
    "_open_volume_find",
    "_open_host_volume_health",
    "_open_system_connectivity",
)

EXCEL_EXPORTERS = (
    "_export_fc_wwpn_excel",
    "_export_snapshot_schedule_excel",
    "_export_capacity_excel",
    "_export_dell_report_excel",
)


def test_header_openers_register_off_ui_thread():
    for name in HEADER_OPENERS:
        _assert_thread_before_register(_method(name))


def test_excel_exporters_register_off_ui_thread():
    for name in EXCEL_EXPORTERS:
        body = _method(name)
        assert "asksaveasfilename" in body
        _assert_thread_before_register(body)
        assert body.index("asksaveasfilename") < body.index("threading.Thread")
