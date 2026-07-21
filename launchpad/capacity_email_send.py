"""Capacity email send: export workbook and dispatch via Gmail SMTP or Outlook COM."""

from __future__ import annotations

import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable

from launchpad.capacity_email_settings import (
    get_gmail_password,
    load_capacity_email_settings,
    normalize_capacity_email_settings,
    save_capacity_email_settings,
    validate_for_send,
)
from launchpad.capacity_export import export_storage_capacity_excel
from launchpad.config import TEMP_DIR

GmailSendFn = Callable[..., None]
OutlookSendFn = Callable[..., None]
ExportFn = Callable[..., Any]


def _build_subject(now: datetime) -> str:
    return f"LaunchPad Capacity Report — {now.strftime('%Y-%m-%d')}"


def _build_body(export_result) -> str:
    return (
        "LaunchPad storage capacity report\n\n"
        f"Generated: {export_result.generated_at}\n"
        f"Sites with capacity: {export_result.filled_count}\n"
        f"Sites with pool stats: {export_result.pool_filled_count}\n"
        f"SSH errors: {export_result.error_count}\n"
        f"Extra rows (unmatched cards): {export_result.extra_rows}\n"
        f"Pool detail rows: {export_result.pool_rows_written}\n"
    )


def _send_via_gmail_smtp(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    from_addr: str,
    to: list[str],
    cc: list[str],
    subject: str,
    body: str,
    attachment_path: Path,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.set_content(body)
    msg.add_attachment(
        Path(attachment_path).read_bytes(),
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=Path(attachment_path).name,
    )
    recipients = list(to) + list(cc)
    with smtplib.SMTP(host, port, timeout=60) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg, to_addrs=recipients)


def _send_via_outlook_com(
    *,
    to: list[str],
    cc: list[str],
    subject: str,
    body: str,
    attachment_path: Path,
) -> None:
    try:
        import win32com.client
    except ImportError as exc:
        raise RuntimeError(
            "Outlook send requires pywin32 on Windows (pip install pywin32)."
        ) from exc
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To = "; ".join(to)
        if cc:
            mail.CC = "; ".join(cc)
        mail.Subject = subject
        mail.Body = body
        mail.Attachments.Add(str(attachment_path))
        mail.Send()
    except Exception as exc:
        raise RuntimeError(f"Outlook COM send failed: {exc}") from exc


def send_capacity_email(
    db,
    crypto_key: bytes,
    settings: dict | None = None,
    *,
    progress=None,
    export_fn: ExportFn | None = None,
    smtp_send_fn: GmailSendFn | None = None,
    outlook_send_fn: OutlookSendFn | None = None,
    temp_dir: Path | str | None = None,
) -> dict:
    current = normalize_capacity_email_settings(
        settings if settings is not None else load_capacity_email_settings(db)
    )
    validation_errors = validate_for_send(current, crypto_key=crypto_key)
    if validation_errors:
        failed = dict(current)
        failed["last_status"] = "Failed"
        failed["last_error"] = "; ".join(validation_errors)
        saved = save_capacity_email_settings(db, failed)
        return {
            "ok": False,
            "settings": saved,
            "path": "",
            "error": failed["last_error"],
        }

    now = datetime.now()
    out_dir = Path(temp_dir) if temp_dir is not None else TEMP_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"Storage_Capacity_Report_{now.strftime('%Y%m%d_%H%M')}.xlsx"

    export = export_fn or export_storage_capacity_excel
    try:
        export_result = export(db, crypto_key, output_path, progress=progress)
        attachment_path = Path(export_result.path)
    except Exception as exc:
        failed = dict(current)
        failed["last_status"] = "Failed"
        failed["last_error"] = str(exc)
        saved = save_capacity_email_settings(db, failed)
        return {"ok": False, "settings": saved, "path": str(output_path), "error": str(exc)}

    subject = _build_subject(now)
    body = _build_body(export_result)

    try:
        if current["provider"] == "gmail":
            smtp_kwargs = {
                "host": "smtp.gmail.com",
                "port": 587,
                "user": current["gmail_address"],
                "password": get_gmail_password(current, crypto_key),
                "from_addr": current["gmail_address"],
                "to": current["to"],
                "cc": current["cc"],
                "subject": subject,
                "body": body,
                "attachment_path": attachment_path,
            }
            if smtp_send_fn is not None:
                smtp_send_fn(**smtp_kwargs)
            else:
                _send_via_gmail_smtp(**smtp_kwargs)
        else:
            outlook_kwargs = {
                "to": current["to"],
                "cc": current["cc"],
                "subject": subject,
                "body": body,
                "attachment_path": attachment_path,
            }
            if outlook_send_fn is not None:
                outlook_send_fn(**outlook_kwargs)
            else:
                _send_via_outlook_com(**outlook_kwargs)
    except Exception as exc:
        failed = dict(current)
        failed["last_status"] = "Failed"
        failed["last_error"] = f"{exc} (attachment: {attachment_path})"
        saved = save_capacity_email_settings(db, failed)
        return {
            "ok": False,
            "settings": saved,
            "path": str(attachment_path),
            "error": str(exc),
        }

    success = dict(current)
    success["last_sent_at"] = now.isoformat(timespec="seconds")
    success["last_status"] = f"Sent {now.strftime('%Y-%m-%d %H:%M')}"
    success["last_error"] = ""
    saved = save_capacity_email_settings(db, success)

    path_str = str(attachment_path)
    try:
        attachment_path.unlink(missing_ok=True)
    except OSError:
        pass

    return {"ok": True, "settings": saved, "path": path_str, "error": ""}
