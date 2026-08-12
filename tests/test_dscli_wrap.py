from launchpad.dscli_wrap import (
    wrap_dscli_command,
    wrap_dscli_command_list,
    wrap_dscli_labeled_commands,
)


def test_wrap_empty_options_unchanged():
    assert wrap_dscli_command("dscli lssi") == "dscli lssi"


def test_wrap_path_only_quotes_executable():
    out = wrap_dscli_command(
        "dscli lssi",
        dscli_path=r"C:\Program Files\IBM\dscli\dscli.bat",
    )
    assert out.startswith('"C:\\Program Files\\IBM\\dscli\\dscli.bat"')
    assert out.endswith(" lssi")
    assert " -hmc1 " not in out


def test_wrap_hmc_and_auth_flags():
    out = wrap_dscli_command(
        "dscli lssi",
        dscli_path="dscli.bat",
        hmc_host="10.1.2.3",
        username="admin",
        password="s3cret",
    )
    assert out.startswith('"dscli.bat"') or out.startswith("dscli.bat")
    assert " -hmc1 10.1.2.3 " in f" {out} " or " -hmc1 10.1.2.3" in out
    assert " -user admin " in f" {out} " or out.find("-user admin") >= 0
    assert " -passwd s3cret " in f" {out} " or out.find("-passwd s3cret") >= 0
    assert out.rstrip().endswith("lssi")


def test_wrap_hmc_without_password_skips_auth_flags():
    out = wrap_dscli_command("dscli lssi", hmc_host="10.1.2.3", username="admin")
    assert "-hmc1 10.1.2.3" in out
    assert "-passwd" not in out
    assert "-user" not in out


def test_wrap_non_dscli_unchanged():
    assert wrap_dscli_command("lssystem") == "lssystem"


def test_wrap_list_and_labeled():
    assert wrap_dscli_command_list(
        ["dscli showsp", "shownet"],
        hmc_host="1.2.3.4",
    ) == [
        wrap_dscli_command("dscli showsp", hmc_host="1.2.3.4"),
        "shownet",
    ]
    labeled = wrap_dscli_labeled_commands(
        [("Health", "dscli lssi")],
        dscli_path="dscli.bat",
    )
    assert labeled[0][0] == "Health"
    assert "dscli.bat" in labeled[0][1]
