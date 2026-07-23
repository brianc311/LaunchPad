from pathlib import Path
from types import SimpleNamespace

from launchpad.capacity_email_send import send_capacity_email
from launchpad.capacity_email_settings import (
    normalize_capacity_email_settings,
    set_gmail_password,
)
from launchpad.crypto import derive_key, generate_salt


class _FakeDb:
    def __init__(self):
        self.values = {}

    def get_setting(self, key, default=""):
        return self.values.get(key, default)

    def set_setting(self, key, value):
        self.values[key] = value


def test_send_gmail_success_updates_status_and_deletes_temp(tmp_path, monkeypatch):
    key = derive_key("pw", generate_salt())
    db = _FakeDb()
    settings = set_gmail_password(
        normalize_capacity_email_settings(
            {
                "provider": "gmail",
                "gmail_address": "ops@gmail.com",
                "to": ["a@b.com"],
                "cc": ["c@d.com"],
            }
        ),
        key,
        "app-pass",
    )
    created = tmp_path / "Storage_Capacity_Report_20260721_0800.xlsx"
    created.write_bytes(b"xlsx")

    def fake_export(db_, crypto_key, output_path, progress=None):
        Path(output_path).write_bytes(b"xlsx")
        return SimpleNamespace(
            path=Path(output_path),
            filled_count=2,
            pool_filled_count=1,
            pool_rows_written=3,
            error_count=0,
            extra_rows=0,
            generated_at="2026-07-21T08:00:00",
        )

    sent = {}

    def fake_smtp(**kwargs):
        sent.update(kwargs)
        return None

    result = send_capacity_email(
        db,
        key,
        settings,
        export_fn=fake_export,
        smtp_send_fn=fake_smtp,
        temp_dir=tmp_path,
    )
    assert result["ok"] is True
    assert sent["to"] == ["a@b.com"]
    assert sent["cc"] == ["c@d.com"]
    assert "LaunchPad Capacity Report" in sent["subject"]
    assert not Path(result["path"]).exists()  # deleted after success
    saved = normalize_capacity_email_settings(__import__("json").loads(db.values["capacity_email_settings"]))
    assert saved["last_status"].startswith("Sent")
    assert saved["last_sent_at"]


def test_send_outlook_uses_outlook_transport(tmp_path):
    key = derive_key("pw", generate_salt())
    db = _FakeDb()
    settings = normalize_capacity_email_settings(
        {"provider": "outlook", "to": ["a@b.com"]}
    )
    called = {}

    def fake_export(db_, crypto_key, output_path, progress=None):
        Path(output_path).write_bytes(b"xlsx")
        return SimpleNamespace(
            path=Path(output_path),
            filled_count=1,
            pool_filled_count=0,
            pool_rows_written=0,
            error_count=0,
            extra_rows=0,
            generated_at="2026-07-21T08:00:00",
        )

    def fake_outlook(**kwargs):
        called.update(kwargs)

    result = send_capacity_email(
        db,
        key,
        settings,
        export_fn=fake_export,
        outlook_send_fn=fake_outlook,
        temp_dir=tmp_path,
    )
    assert result["ok"] is True
    assert called["to"] == ["a@b.com"]
