from launchpad.system_connectivity import (
    TOPICS,
    base_row,
    enrich_license_key_row,
    parse_hpe_showlicense,
    parse_svc_lsencryption,
    parse_svc_svqueryclock,
    topic_commands_for_profile,
)


def test_topics_include_license_key_after_firmware():
    assert TOPICS.index("firmware") < TOPICS.index("license_key")
    assert TOPICS[-1] == "license_key"


def test_parse_hpe_showlicense_features_and_key_date():
    output = """
License key was generated on Tue Sep 19 10:37:04 2017
License features currently enabled:
3PAR OS Suite
Peer Motion
  Expiration Date: Sep 24, 2017 8:00:00 PM EDT
Thin Provisioning (20480000G)
"""
    rows = parse_hpe_showlicense(output)
    assert len(rows) >= 2
    assert all(r.get("key_generation_date") for r in rows)
    names = {r["feature"] for r in rows}
    assert "3PAR OS Suite" in names or any("3PAR OS Suite" in n for n in names)
    peer = next(r for r in rows if "Peer Motion" in r["feature"])
    assert peer["expiration"]  # non-empty when dated


def test_parse_hpe_showlicense_emdash_expiration_empty_or_dash():
    output = """
License key was generated on Mon Sep 20 16:37:50 2018
License features currently enabled:
Compression
"""
    rows = parse_hpe_showlicense(output)
    assert rows
    assert rows[0]["key_generation_date"]
    # no dated expiry → empty or em-dash
    assert rows[0].get("expiration", "") in ("", "—", "-")


def test_parse_svc_lsencryption_licensed():
    output = "status:licensed\nerror_sequence_number:\n"
    configured, status, details, enc = parse_svc_lsencryption(output)
    assert configured == "yes"
    assert enc in ("yes", "licensed") or enc == "yes"
    # Prefer normalized enc == "yes" for licensed/enabled


def test_parse_svc_svqueryclock():
    date_s, time_s = parse_svc_svqueryclock("Fri Nov  5 14:53:21 CET 2021")
    assert date_s
    assert time_s


def test_enrich_license_key_row_fields():
    row = base_row(
        card_name="HPE1", host="1.2.3.4", vendor="hpe", profile="hpe_3par"
    )
    out = enrich_license_key_row(
        row,
        configured="yes",
        status="ok",
        details="3 features",
        key_generation_date="2017-09-19",
        feature="Remote Copy",
        expiration="—",
    )
    assert out["feature"] == "Remote Copy"
    assert out["key_generation_date"] == "2017-09-19"


def test_topic_commands_license_key():
    svc = topic_commands_for_profile("flashsystem_7300")
    assert "lsencryption" in " ".join(svc["license_key"])
    assert any("svqueryclock" in c for c in svc["license_key"])
    hpe = topic_commands_for_profile("hpe_3par_8450")
    assert hpe["license_key"] == ["showlicense"]
    ds = topic_commands_for_profile("ibm_ds8884")
    assert ds["license_key"] == []
