from pathlib import Path

from launchpad.ansible_pad import ANSIBLE_PAD_HTML, ANSIBLE_PAD_PATH


def test_ansible_pad_markers():
    assert ANSIBLE_PAD_PATH == "/ansible-pad"
    assert "Ansible Pad" in ANSIBLE_PAD_HTML
    assert "/api/ansible-pad/export.zip" in ANSIBLE_PAD_HTML
    assert "/api/ansible-pad/sync-run" in ANSIBLE_PAD_HTML
    assert "/api/ansible-pad/run-existing" in ANSIBLE_PAD_HTML
    assert "plp5-dz5-nw" in ANSIBLE_PAD_HTML


def test_dashboard_lists_ansible_pad_tool():
    dashboard_path = Path(__file__).parents[1] / "launchpad" / "ui" / "dashboard_view.py"

    assert '"Ansible Pad"' in dashboard_path.read_text(encoding="utf-8")
