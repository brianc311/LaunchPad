from launchpad.lun_builder_size import join_lun_size, split_lun_size_for_ui


def test_split_bare_defaults_to_gb():
    assert split_lun_size_for_ui("100") == ("100", "GB")


def test_split_gb_and_tb():
    assert split_lun_size_for_ui("100GB") == ("100", "GB")
    assert split_lun_size_for_ui("1.5tb") == ("1.5", "TB")


def test_split_other_suffix_shows_amount_with_gb_display():
    assert split_lun_size_for_ui("500MB") == ("500", "GB")


def test_join_and_paste_normalize():
    assert join_lun_size("100", "GB") == "100GB"
    assert join_lun_size("1", "TB") == "1TB"
    assert join_lun_size("", "GB") == ""
    assert join_lun_size("500GB", "TB") == "500GB"
