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
