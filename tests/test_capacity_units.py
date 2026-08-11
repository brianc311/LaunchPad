from launchpad.capacity_units import (
    bytes_to_capacity_unit,
    capacity_unit_header,
    format_bytes,
    get_capacity_unit_mode,
    iec_gib_to_display,
    normalize_capacity_unit_mode,
    set_capacity_unit_mode,
)
from launchpad.flashsystem_parse import _format_bytes, _parse_size_bytes


def test_normalize_capacity_unit_mode():
    assert normalize_capacity_unit_mode(None) == "iec"
    assert normalize_capacity_unit_mode("") == "iec"
    assert normalize_capacity_unit_mode("IEC") == "iec"
    assert normalize_capacity_unit_mode("nope") == "iec"
    assert normalize_capacity_unit_mode("si") == "si"
    assert normalize_capacity_unit_mode("SI") == "si"


def test_format_bytes_iec_default():
    set_capacity_unit_mode("iec")
    assert get_capacity_unit_mode() == "iec"
    assert format_bytes(0) == "0 GiB"
    assert format_bytes(-1) == "0 GiB"
    assert format_bytes(1024**3) == "1.0 GiB"
    assert format_bytes(1024**4) == "1.0 TiB"
    assert _format_bytes(1024**3) == "1.0 GiB"
    assert capacity_unit_header() == "GiB"
    assert bytes_to_capacity_unit(1024**3) == 1.0


def test_format_bytes_si_recalculates():
    set_capacity_unit_mode("si")
    assert format_bytes(0) == "0 GB"
    assert format_bytes(1024**3) == "1.1 GB"
    assert format_bytes(1024**4) == "1.1 TB"
    assert _format_bytes(1024**3) == "1.1 GB"
    assert capacity_unit_header() == "GB"
    assert abs(bytes_to_capacity_unit(1024**3) - 1.073741824) < 1e-9
    assert abs(iec_gib_to_display(1.0) - 1.073741824) < 1e-9


def test_parse_size_bytes_ignores_display_mode():
    set_capacity_unit_mode("si")
    assert _parse_size_bytes("1TB") == float(1024**4)
    assert _parse_size_bytes("1TiB") == float(1024**4)
    assert _parse_size_bytes("1GB") == float(1024**3)
