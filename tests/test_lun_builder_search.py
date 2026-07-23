from launchpad.lun_builder_search import (
    build_matches_query,
    find_builds_matching_query,
    host_row_matches,
    lun_row_matches,
    normalize_query,
)


def test_normalize_query_strips_and_lowers():
    assert normalize_query("  ArchVG  ") == "archvg"


def test_empty_query_matches_all_rows():
    assert host_row_matches({"lpar_name": "pconsps3"}, "") is True
    assert lun_row_matches({"purpose": "archvg", "count": 1, "host_names": ["pconsps3"]}, "") is True
    assert build_matches_query({"name": "X", "hosts": [], "luns": []}, "") is True


def test_find_empty_query_returns_no_builds():
    builds = [{"id": "a", "name": "Hartford", "hosts": [{"lpar_name": "pconsps3"}], "luns": []}]
    assert find_builds_matching_query(builds, "") == []
    assert find_builds_matching_query(builds, "   ") == []


def test_host_row_matches_lpar_name():
    host = {"lpar_name": "pconsps3"}
    assert host_row_matches(host, "sps3") is True
    assert host_row_matches(host, "nope") is False


def test_lun_row_matches_purpose_hosts_and_expanded_volume():
    lun = {
        "purpose": "archvg",
        "count": 2,
        "shared": True,
        "name_prefix": "pcon",
        "cluster": "sps",
        "host_names": ["pconsps3", "pconsps4"],
    }
    assert lun_row_matches(lun, "archvg") is True
    assert lun_row_matches(lun, "pconsps4") is True
    assert lun_row_matches(lun, "pconsps_archvg_1") is True
    assert lun_row_matches(lun, "missing") is False


def test_find_builds_sorted_by_name():
    builds = [
        {
            "id": "b",
            "name": "Zebra",
            "hosts": [{"lpar_name": "hostz"}],
            "luns": [],
        },
        {
            "id": "a",
            "name": "Alpha",
            "hosts": [],
            "luns": [{"purpose": "root", "count": 1, "host_names": ["hostz"], "exact_name": True}],
        },
    ]
    found = find_builds_matching_query(builds, "hostz")
    assert [b["name"] for b in found] == ["Alpha", "Zebra"]
