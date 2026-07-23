from launchpad.contingency_groups_search import (
    find_groups_matching_content,
    find_groups_matching_identity,
    group_content_matches,
    group_identity_matches,
    host_row_matches,
    map_row_matches,
    volume_row_matches,
)


def test_identity_matches_name_and_location():
    group = {"name": "Hartford, CT", "location": "Hartford, CT", "hosts": [], "volumes": [], "maps": []}
    assert group_identity_matches(group, "hartford") is True
    assert group_identity_matches(group, "xyz") is False


def test_find_identity_empty_returns_none():
    groups = [{"name": "Hartford, CT", "location": "", "hosts": [], "volumes": [], "maps": []}]
    assert find_groups_matching_identity(groups, "") == []


def test_content_matches_host_volume_map():
    group = {
        "name": "Site",
        "location": "",
        "hosts": [{"name": "pconsps3", "wwpns": ["AA:BB"]}],
        "volumes": [{"name": "pconsps_archvg_1"}],
        "maps": [{"volume": "pconsps_archvg_1", "host": "pconsps3"}],
    }
    assert group_content_matches(group, "pconsps3") is True
    assert group_content_matches(group, "archvg") is True
    assert host_row_matches(group["hosts"][0], "aabb") is True
    assert volume_row_matches(group["volumes"][0], "archvg") is True
    assert map_row_matches(group["maps"][0], "pconsps3") is True
    assert group_content_matches(group, "nope") is False


def test_find_content_sorted_and_skips_identity_only():
    groups = [
        {"name": "Zebra", "location": "", "hosts": [{"name": "hostz", "wwpns": []}], "volumes": [], "maps": []},
        {"name": "Alpha", "location": "Alpha Loc", "hosts": [], "volumes": [], "maps": []},
    ]
    assert [g["name"] for g in find_groups_matching_content(groups, "hostz")] == ["Zebra"]
    assert [g["name"] for g in find_groups_matching_identity(groups, "alpha")] == ["Alpha"]
