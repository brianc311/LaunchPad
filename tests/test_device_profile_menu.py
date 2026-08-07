"""Device profile Admin dropdown mapping must stay label↔key aligned."""

from launchpad.storage_presets import (
    DEVICE_PROFILES,
    device_profile_menu_labels,
    device_profile_label_to_key,
)


def test_hadoop_label_maps_to_hadoop_linux_not_primera():
    mapping = device_profile_label_to_key()
    assert mapping["Hadoop / Linux SSH"] == "hadoop_linux"
    assert mapping["HPE Primera 600 4-way"] == "hpe_primera_600"


def test_every_menu_label_maps_to_matching_profile_key():
    labels = device_profile_menu_labels()
    mapping = device_profile_label_to_key()
    assert labels[0] == DEVICE_PROFILES[""]
    for label in labels:
        key = mapping[label]
        assert DEVICE_PROFILES[key] == label


def test_menu_labels_are_case_insensitive_sorted_after_general():
    labels = device_profile_menu_labels()
    rest = labels[1:]
    assert rest == sorted(rest, key=str.lower)
