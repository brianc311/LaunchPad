from launchpad.vcenters import VCENTERS_HTML, VCENTERS_PATH


def test_vcenters_page_markers():
    assert VCENTERS_PATH == "/vcenters"
    assert "vCenters" in VCENTERS_HTML
    assert "No vCenters yet" in VCENTERS_HTML
    assert "/api/vcenters" in VCENTERS_HTML
    assert "/api/vcenters/delete" in VCENTERS_HTML
    assert 'id="name"' in VCENTERS_HTML
    assert 'id="location"' in VCENTERS_HTML
    assert 'id="address"' in VCENTERS_HTML
    assert 'id="url"' in VCENTERS_HTML
    assert 'target="_blank"' in VCENTERS_HTML
    assert 'rel="noopener"' in VCENTERS_HTML
    assert "Unlock LaunchPad" in VCENTERS_HTML
    assert "{{APP_VERSION}}" in VCENTERS_HTML


def test_vcenters_page_has_vsphere_client_controls():
    assert 'id="use_vsphere_client"' in VCENTERS_HTML
    assert "vSphere Client" in VCENTERS_HTML
    assert 'id="username"' in VCENTERS_HTML
    assert 'id="password"' in VCENTERS_HTML
    assert "Open vSphere Client" in VCENTERS_HTML
    assert "/api/vcenters/launch" in VCENTERS_HTML
    assert 'id="d-username"' in VCENTERS_HTML
    assert 'id="launch-btn"' in VCENTERS_HTML
    assert 'id="detail-status"' in VCENTERS_HTML


def test_vcenters_page_has_description_vm_notes_and_search():
    assert 'id="vcenter-search"' in VCENTERS_HTML
    assert 'placeholder="Search name, IP, or VM"' in VCENTERS_HTML
    assert 'id="description"' in VCENTERS_HTML
    assert "<strong>Description</strong>" in VCENTERS_HTML
    assert 'id="vm_notes"' in VCENTERS_HTML
    assert "<textarea" in VCENTERS_HTML
    assert 'id="d-description"' in VCENTERS_HTML
    assert "<details" in VCENTERS_HTML
    assert "<summary>VM names</summary>" in VCENTERS_HTML
    assert 'id="d-vm-notes"' in VCENTERS_HTML
    assert "function rowMatchesQuery" in VCENTERS_HTML
    assert "No matching vCenters" in VCENTERS_HTML
    assert "<th>Name</th><th>Location</th><th>Address</th><th>Link</th>" in VCENTERS_HTML
