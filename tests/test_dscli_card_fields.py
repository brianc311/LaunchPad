from launchpad.database import Database


def test_card_persists_dscli_path_and_hmc(tmp_path):
    db = Database(tmp_path / "t.db")
    cid = db.add_card(
        {
            "name": "DS1",
            "card_type": "ssh",
            "host": "10.0.0.5",
            "device_profile": "ibm_ds8884",
            "dscli_path": r"C:\dscli\dscli.bat",
            "dscli_hmc": "10.0.0.9",
            "encrypted_password": "",
            "encrypted_sudo_password": "",
            "encrypted_key_passphrase": "",
            "encrypted_key": "",
        }
    )
    card = db.get_card(cid)
    assert card.dscli_path == r"C:\dscli\dscli.bat"
    assert card.dscli_hmc == "10.0.0.9"
    db.update_card(
        cid,
        {
            "name": "DS1",
            "card_type": "ssh",
            "host": "10.0.0.5",
            "device_profile": "ibm_ds8884",
            "dscli_path": "",
            "dscli_hmc": "10.0.0.8",
            "encrypted_password": "",
            "encrypted_sudo_password": "",
            "encrypted_key_passphrase": "",
            "encrypted_key": "",
            "username": "",
            "url": "",
            "icon": "default",
            "category": "General",
            "sort_order": 0,
            "glow_color": "#FF6B00",
            "key_file_path": "",
            "custom_commands": "",
            "serial_number": "",
            "port": None,
        },
    )
    card2 = db.get_card(cid)
    assert card2.dscli_path == ""
    assert card2.dscli_hmc == "10.0.0.8"
