from pathlib import Path


def test_dashboard_has_vcenters_button():
    text = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")
    assert '("vCenters"' in text
    assert "_open_vcenters" in text
    ansible = text.index('("Ansible Pad"')
    vcenters = text.index('("vCenters"')
    host_power = text.index('("Host Power"')
    assert ansible < vcenters < host_power
    assert "open_url=lambda server: server.open_vcenters()" in text
    assert "_open_entries_browser_report" not in text.split("def _open_vcenters", 1)[1].split("def ", 1)[0]
