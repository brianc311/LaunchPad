import customtkinter as ctk
import json
import queue
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

from launchpad.backup import BackupDecryptError, read_backup_file, write_backup_file
from launchpad.branding import (
    clear_logo,
    get_app_name,
    load_ctk_logo_large,
    logo_path,
    save_app_name,
    save_logo,
)
from launchpad.capacity_email_send import send_capacity_email
from launchpad.capacity_email_settings import (
    load_capacity_email_settings,
    normalize_capacity_email_settings,
    save_capacity_email_settings,
    set_gmail_password,
    validate_for_send,
)
from launchpad.dell_report_settings import (
    load_dell_report_settings,
    save_dell_report_settings,
)
from launchpad.config import CARD_TYPES, DEFAULT_APP_NAME, DEFAULT_GLOW_COLOR, DEFAULT_SSH_PORT, APP_VERSION
from launchpad.crypto import decrypt_text, encrypt_text, verify_password
from launchpad.firmware_catalog import (
    eligible_firmware_profiles,
    get_profile_catalog,
    load_firmware_auto_add,
    load_firmware_catalog,
    merge_catalog_for_admin_save,
    merge_seed_into_catalog,
    save_firmware_auto_add,
    save_firmware_catalog,
)
from launchpad.firmware_catalog_seed import recommended_firmware_seed
from launchpad.icons import ICON_CHOICES, resolve_icon
from launchpad.storage_presets import (
    DEVICE_PROFILES,
    is_storage_profile,
    preset_command_text,
    preset_commands_for_profile,
)
from launchpad.ssh_test import probe_ssh_login_for_card, test_ssh_login
from launchpad.ssh_utils import normalize_key_file_path
from launchpad.ui.ssh_status import SSH_STATUS_INTERVAL_MS, create_ssh_status_led, set_ssh_status_led
from launchpad.ui.colors import normalize_color
from launchpad.ui.ssh_test_dialog import SshTestDialog
from launchpad.ui.theme import get_theme


class AdminView(ctk.CTkFrame):
    _SECRET_ENTRY_KEYS = frozenset({"password", "key_passphrase"})
    _MASK_CHAR = "•"
    _EMAIL_MODE_LABELS = {"daily": "Daily", "weekly": "Weekly", "every_n_days": "Every N days"}
    _EMAIL_MODE_KEYS = {label: key for key, label in _EMAIL_MODE_LABELS.items()}
    _EMAIL_WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def __init__(self, master, db, crypto_key, on_back) -> None:
        super().__init__(master, fg_color="transparent")
        self.db = db
        self.crypto_key = crypto_key
        self.on_back = on_back
        self.theme = get_theme(self.db.get_setting("theme", "dark"))
        self.editing_id: int | None = None
        self._authenticated = False
        self._ssh_test_in_flight = False
        self._ssh_test_dialog: SshTestDialog | None = None
        self._ssh_test_poll_id: str | None = None
        self._admin_ssh_leds: dict[int, ctk.CTkFrame] = {}
        self._admin_ssh_status_in_flight: set[int] = set()
        self._admin_ssh_status_timer: str | None = None
        self._capacity_email_settings: dict | None = None
        self._capacity_email_send_in_flight = False
        self._dell_report_settings: dict | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.auth_frame = ctk.CTkFrame(self, fg_color=self.theme["surface"], corner_radius=16)
        self.auth_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=80, pady=80)
        self.auth_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.auth_frame,
            text="Admin Access",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=self.theme["accent"],
        ).grid(row=0, column=0, pady=(28, 8))

        self.admin_password = ctk.CTkEntry(self.auth_frame, placeholder_text="Admin password", show="*", width=280)
        self.admin_password.grid(row=1, column=0, pady=8)
        self.admin_password.bind("<Return>", lambda _e: self._authenticate())

        self.auth_error = ctk.CTkLabel(self.auth_frame, text="", text_color=self.theme["danger"])
        self.auth_error.grid(row=2, column=0, pady=4)

        ctk.CTkButton(
            self.auth_frame,
            text="Enter Admin",
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_soft"],
            command=self._authenticate,
        ).grid(row=3, column=0, pady=(8, 28))

        ctk.CTkButton(
            self.auth_frame,
            text="Back to Dashboard",
            fg_color="transparent",
            border_width=1,
            border_color=self.theme["border"],
            command=self.on_back,
        ).grid(row=4, column=0, pady=(0, 24))

    def _authenticate(self) -> None:
        password = self.admin_password.get()
        salt = self.db.get_setting("admin_salt")
        stored = self.db.get_setting("admin_hash")
        if not verify_password(password, salt, stored):
            self.auth_error.configure(text="Incorrect admin password.")
            return
        self._authenticated = True
        self.auth_frame.destroy()
        self._build_admin_ui()

    def _build_admin_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text=f"Admin Dashboard  ·  v{APP_VERSION}",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=self.theme["accent"],
        ).grid(row=0, column=0, sticky="w")

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(
            actions,
            text="Export Backup",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._export_backup,
        ).grid(row=0, column=0, padx=4)

        ctk.CTkButton(
            actions,
            text="Import Backup",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._import_backup,
        ).grid(row=0, column=1, padx=4)

        ctk.CTkButton(actions, text="Back", command=self.on_back).grid(row=0, column=2, padx=(8, 0))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 20))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.tabs = ctk.CTkTabview(body, fg_color=self.theme["surface"])
        self.tabs.grid(row=0, column=0, sticky="nsew")

        connections_tab = self.tabs.add("Connections")
        connections_tab.grid_columnconfigure(0, weight=2)
        connections_tab.grid_columnconfigure(1, weight=3)
        connections_tab.grid_rowconfigure(0, weight=1)

        branding_tab = self.tabs.add("Branding")
        branding_tab.grid_columnconfigure(0, weight=1)
        branding_tab.grid_rowconfigure(0, weight=1)

        email_tab = self.tabs.add("Capacity Email")
        email_tab.grid_columnconfigure(0, weight=1)
        email_tab.grid_rowconfigure(0, weight=1)

        firmware_tab = self.tabs.add("Firmware catalog")
        firmware_tab.grid_columnconfigure(0, weight=1)
        firmware_tab.grid_rowconfigure(0, weight=1)

        self._build_card_list(connections_tab)
        self._build_card_form(connections_tab)
        self._build_branding_panel(branding_tab)
        self._build_capacity_email_panel(email_tab)
        self._build_firmware_catalog_panel(firmware_tab)
        self.refresh_list()

        self.admin_status = ctk.CTkLabel(
            self,
            text="",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=12),
        )
        self.admin_status.grid(row=2, column=0, sticky="w", padx=24, pady=(0, 12))

    def _build_branding_panel(self, parent) -> None:
        panel = ctk.CTkFrame(parent, fg_color=self.theme["surface_alt"], corner_radius=16)
        panel.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        panel.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            panel,
            text="White Label & Branding",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.theme["text"],
        ).grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 4), sticky="w")

        ctk.CTkLabel(
            panel,
            text="Change the app name and logo shown on the login screen and dashboard.",
            font=ctk.CTkFont(size=12),
            text_color=self.theme["muted"],
            wraplength=520,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 16), sticky="w")

        ctk.CTkLabel(panel, text="App Name", text_color=self.theme["muted"]).grid(
            row=2, column=0, padx=20, pady=8, sticky="w"
        )
        self.brand_name_entry = ctk.CTkEntry(panel, width=320)
        self.brand_name_entry.grid(row=2, column=1, padx=20, pady=8, sticky="w")
        self.brand_name_entry.insert(0, get_app_name(self.db))
        self.brand_name_entry.bind("<KeyRelease>", lambda _e: self._refresh_branding_preview())

        ctk.CTkLabel(panel, text="Logo", text_color=self.theme["muted"]).grid(
            row=3, column=0, padx=20, pady=8, sticky="nw"
        )

        logo_row = ctk.CTkFrame(panel, fg_color="transparent")
        logo_row.grid(row=3, column=1, padx=20, pady=8, sticky="w")

        ctk.CTkButton(
            logo_row,
            text="Upload Logo",
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_soft"],
            command=self._upload_logo,
        ).grid(row=0, column=0, padx=(0, 8))

        ctk.CTkButton(
            logo_row,
            text="Remove Logo",
            fg_color=self.theme["surface"],
            hover_color=self.theme["border"],
            command=self._remove_logo,
        ).grid(row=0, column=1, padx=(0, 8))

        self.logo_path_label = ctk.CTkLabel(
            logo_row,
            text=self._logo_status_text(),
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=11),
        )
        self.logo_path_label.grid(row=0, column=2, padx=(8, 0), sticky="w")

        preview_frame = ctk.CTkFrame(panel, fg_color=self.theme["surface"], corner_radius=12)
        preview_frame.grid(row=4, column=0, columnspan=2, padx=20, pady=(12, 8), sticky="ew")

        preview_inner = ctk.CTkFrame(preview_frame, fg_color="transparent")
        preview_inner.pack(padx=20, pady=16, anchor="w")

        self._brand_logo_image = load_ctk_logo_large(self.db)
        if self._brand_logo_image:
            self.brand_logo_preview = ctk.CTkLabel(
                preview_inner,
                text="",
                image=self._brand_logo_image,
            )
            self.brand_logo_preview.pack(side="left", padx=(0, 12))
        else:
            self.brand_logo_preview = None

        self.brand_title_preview = ctk.CTkLabel(
            preview_inner,
            text=get_app_name(self.db),
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=self.theme["accent"],
        )
        self.brand_title_preview.pack(side="left")

        ctk.CTkLabel(
            panel,
            text="Preview — how the header will look after you save.",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=11),
        ).grid(row=5, column=0, columnspan=2, padx=20, pady=(0, 8), sticky="w")

        ctk.CTkButton(
            panel,
            text="Save Branding",
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_soft"],
            width=180,
            command=self._save_branding,
        ).grid(row=6, column=0, columnspan=2, padx=20, pady=(8, 24), sticky="w")

    def _logo_status_text(self) -> str:
        path = logo_path(self.db)
        if path:
            return path.name
        return "No logo uploaded"

    def _upload_logo(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Logo",
            filetypes=[
                ("Images", "*.png;*.jpg;*.jpeg;*.gif;*.webp;*.bmp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            save_logo(self.db, path)
            self._refresh_branding_preview()
            self.admin_status.configure(text="Logo uploaded. Click Save Branding to apply.", text_color=self.theme["accent"])
        except Exception as exc:
            messagebox.showerror("Admin", f"Could not upload logo:\n{exc}")

    def _remove_logo(self) -> None:
        clear_logo(self.db)
        self._refresh_branding_preview()
        self.admin_status.configure(text="Logo removed. Click Save Branding to apply.", text_color=self.theme["muted"])

    def _refresh_branding_preview(self) -> None:
        if hasattr(self, "logo_path_label"):
            self.logo_path_label.configure(text=self._logo_status_text())

        name = self.brand_name_entry.get().strip() or DEFAULT_APP_NAME
        self.brand_title_preview.configure(text=name)

        image = load_ctk_logo_large(self.db)
        if image:
            self._brand_logo_image = image
            if self.brand_logo_preview:
                self.brand_logo_preview.configure(image=image)
            else:
                preview_inner = self.brand_title_preview.master
                self.brand_logo_preview = ctk.CTkLabel(preview_inner, text="", image=image)
                self.brand_logo_preview.pack(side="left", padx=(0, 12), before=self.brand_title_preview)
        elif self.brand_logo_preview:
            self.brand_logo_preview.destroy()
            self.brand_logo_preview = None
            self._brand_logo_image = None

    def _save_branding(self) -> None:
        name = save_app_name(self.db, self.brand_name_entry.get())
        self._refresh_branding_preview()
        self.admin_status.configure(
            text=f"Branding saved. App name is now '{name}'. Return to dashboard to see changes.",
            text_color=self.theme["accent"],
        )

    def _build_capacity_email_panel(self, parent) -> None:
        panel = ctk.CTkFrame(parent, fg_color=self.theme["surface_alt"], corner_radius=16)
        panel.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        panel.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            panel,
            text="Capacity Report Email",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.theme["text"],
        ).grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 4), sticky="w")

        ctk.CTkLabel(
            panel,
            text="Email the storage capacity report on a schedule via Gmail SMTP or local Outlook.",
            font=ctk.CTkFont(size=12),
            text_color=self.theme["muted"],
            wraplength=520,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 16), sticky="w")

        row = 2
        ctk.CTkLabel(panel, text="Provider", text_color=self.theme["muted"]).grid(
            row=row, column=0, padx=20, pady=8, sticky="w"
        )
        self.email_provider_var = ctk.StringVar(value="Gmail")
        self.email_provider_menu = ctk.CTkOptionMenu(
            panel,
            variable=self.email_provider_var,
            values=["Gmail", "Outlook"],
            command=lambda _v: self._update_capacity_email_visibility(),
        )
        self.email_provider_menu.grid(row=row, column=1, padx=20, pady=8, sticky="ew")
        row += 1

        self.email_gmail_address_label = ctk.CTkLabel(
            panel, text="Gmail Address", text_color=self.theme["muted"]
        )
        self.email_gmail_address_label.grid(row=row, column=0, padx=20, pady=8, sticky="w")
        self.email_gmail_address_entry = ctk.CTkEntry(
            panel, placeholder_text="you@gmail.com"
        )
        self.email_gmail_address_entry.grid(row=row, column=1, padx=20, pady=8, sticky="ew")
        row += 1

        self.email_gmail_password_label = ctk.CTkLabel(
            panel, text="Gmail App Password", text_color=self.theme["muted"]
        )
        self.email_gmail_password_label.grid(row=row, column=0, padx=20, pady=8, sticky="w")
        self.email_gmail_password_entry = ctk.CTkEntry(
            panel,
            placeholder_text="Leave blank to keep the saved password",
            show=self._MASK_CHAR,
        )
        self.email_gmail_password_entry.grid(row=row, column=1, padx=20, pady=8, sticky="ew")
        row += 1

        ctk.CTkLabel(panel, text="To", text_color=self.theme["muted"]).grid(
            row=row, column=0, padx=20, pady=8, sticky="w"
        )
        self.email_to_entry = ctk.CTkEntry(
            panel, placeholder_text="ops@example.com; manager@example.com"
        )
        self.email_to_entry.grid(row=row, column=1, padx=20, pady=8, sticky="ew")
        row += 1

        ctk.CTkLabel(panel, text="Cc", text_color=self.theme["muted"]).grid(
            row=row, column=0, padx=20, pady=8, sticky="w"
        )
        self.email_cc_entry = ctk.CTkEntry(
            panel, placeholder_text="Optional, comma or semicolon separated"
        )
        self.email_cc_entry.grid(row=row, column=1, padx=20, pady=8, sticky="ew")
        row += 1

        ctk.CTkLabel(panel, text="Mode", text_color=self.theme["muted"]).grid(
            row=row, column=0, padx=20, pady=8, sticky="w"
        )
        self.email_mode_var = ctk.StringVar(value="Weekly")
        self.email_mode_menu = ctk.CTkOptionMenu(
            panel,
            variable=self.email_mode_var,
            values=list(self._EMAIL_MODE_LABELS.values()),
            command=lambda _v: self._update_capacity_email_visibility(),
        )
        self.email_mode_menu.grid(row=row, column=1, padx=20, pady=8, sticky="ew")
        row += 1

        self.email_weekday_label = ctk.CTkLabel(panel, text="Weekday", text_color=self.theme["muted"])
        self.email_weekday_label.grid(row=row, column=0, padx=20, pady=8, sticky="w")
        self.email_weekday_var = ctk.StringVar(value=self._EMAIL_WEEKDAY_LABELS[0])
        self.email_weekday_menu = ctk.CTkOptionMenu(
            panel,
            variable=self.email_weekday_var,
            values=self._EMAIL_WEEKDAY_LABELS,
        )
        self.email_weekday_menu.grid(row=row, column=1, padx=20, pady=8, sticky="ew")
        row += 1

        self.email_every_n_label = ctk.CTkLabel(
            panel, text="Every N Days", text_color=self.theme["muted"]
        )
        self.email_every_n_label.grid(row=row, column=0, padx=20, pady=8, sticky="w")
        self.email_every_n_entry = ctk.CTkEntry(panel, placeholder_text="7")
        self.email_every_n_entry.grid(row=row, column=1, padx=20, pady=8, sticky="ew")
        row += 1

        ctk.CTkLabel(panel, text="Time (local, HH:MM)", text_color=self.theme["muted"]).grid(
            row=row, column=0, padx=20, pady=8, sticky="w"
        )
        self.email_time_entry = ctk.CTkEntry(panel, placeholder_text="08:00")
        self.email_time_entry.grid(row=row, column=1, padx=20, pady=8, sticky="ew")
        row += 1

        self.email_enabled_var = ctk.BooleanVar(value=False)
        self.email_enabled_check = ctk.CTkCheckBox(
            panel,
            text="Enable schedule",
            variable=self.email_enabled_var,
        )
        self.email_enabled_check.grid(row=row, column=0, columnspan=2, padx=20, pady=8, sticky="w")
        row += 1

        buttons = ctk.CTkFrame(panel, fg_color="transparent")
        buttons.grid(row=row, column=0, columnspan=2, padx=20, pady=(8, 8), sticky="w")

        ctk.CTkButton(
            buttons,
            text="Save Capacity Email Settings",
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_soft"],
            command=self._save_capacity_email_form,
        ).grid(row=0, column=0, padx=(0, 8))

        self.email_send_btn = ctk.CTkButton(
            buttons,
            text="Send Now",
            fg_color=self.theme["surface"],
            hover_color=self.theme["border"],
            border_width=1,
            border_color=self.theme["accent"],
            command=self._send_capacity_email_now,
        )
        self.email_send_btn.grid(row=0, column=1, padx=(0, 8))
        row += 1

        self.email_last_sent_label = ctk.CTkLabel(
            panel, text="Last sent: never", text_color=self.theme["muted"], font=ctk.CTkFont(size=11)
        )
        self.email_last_sent_label.grid(row=row, column=0, columnspan=2, padx=20, pady=(4, 0), sticky="w")
        row += 1

        self.email_last_status_label = ctk.CTkLabel(
            panel, text="Last status: —", text_color=self.theme["muted"], font=ctk.CTkFont(size=11)
        )
        self.email_last_status_label.grid(row=row, column=0, columnspan=2, padx=20, pady=(0, 0), sticky="w")
        row += 1

        self.email_last_error_label = ctk.CTkLabel(
            panel,
            text="Last error: —",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=11),
            wraplength=520,
            justify="left",
        )
        self.email_last_error_label.grid(row=row, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="w")
        row += 1

        ctk.CTkLabel(
            panel,
            text="Dell Report",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.theme["text"],
        ).grid(row=row, column=0, columnspan=2, padx=20, pady=(8, 4), sticky="w")
        row += 1

        ctk.CTkLabel(
            panel,
            text="Show or hide the Dell Report export button on the Capacity Report page and dashboard.",
            font=ctk.CTkFont(size=12),
            text_color=self.theme["muted"],
            wraplength=520,
            justify="left",
        ).grid(row=row, column=0, columnspan=2, padx=20, pady=(0, 8), sticky="w")
        row += 1

        self.dell_report_enabled_var = ctk.BooleanVar(value=True)
        self.dell_report_enabled_check = ctk.CTkCheckBox(
            panel,
            text="Show Dell Report button",
            variable=self.dell_report_enabled_var,
        )
        self.dell_report_enabled_check.grid(row=row, column=0, columnspan=2, padx=20, pady=8, sticky="w")
        row += 1

        ctk.CTkLabel(
            panel,
            text="Card overrides (JSON object keyed by card_id: facility, array_name, model)",
            font=ctk.CTkFont(size=12),
            text_color=self.theme["muted"],
            wraplength=520,
            justify="left",
        ).grid(row=row, column=0, columnspan=2, padx=20, pady=(8, 4), sticky="w")
        row += 1

        self.dell_report_overrides_text = ctk.CTkTextbox(panel, height=120, width=520)
        self.dell_report_overrides_text.grid(
            row=row, column=0, columnspan=2, padx=20, pady=(0, 8), sticky="ew"
        )
        row += 1

        ctk.CTkButton(
            panel,
            text="Save Dell Report Settings",
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_soft"],
            command=self._save_dell_report_form,
        ).grid(row=row, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="w")

        self._load_capacity_email_form()
        self._load_dell_report_form()

    def _build_firmware_catalog_panel(self, parent) -> None:
        panel = ctk.CTkFrame(parent, fg_color=self.theme["surface_alt"], corner_radius=16)
        panel.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        panel.grid_columnconfigure(1, weight=1)
        panel.grid_rowconfigure(7, weight=1)

        ctk.CTkLabel(
            panel,
            text="Firmware Catalog",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.theme["text"],
        ).grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 4), sticky="w")

        ctk.CTkLabel(
            panel,
            text=(
                "Ordered release list per device profile (oldest at top, newest at bottom). "
                "Used by System Connectivity Versions behind."
            ),
            font=ctk.CTkFont(size=12),
            text_color=self.theme["muted"],
            wraplength=520,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 8), sticky="w")

        self.firmware_auto_add_var = ctk.BooleanVar(value=load_firmware_auto_add(self.db))
        self.firmware_auto_add_check = ctk.CTkCheckBox(
            panel,
            text="Auto-add firmware from live scans",
            variable=self.firmware_auto_add_var,
            command=self._on_firmware_auto_add_toggle,
        )
        self.firmware_auto_add_check.grid(row=2, column=0, columnspan=2, padx=20, pady=(0, 4), sticky="w")

        ctk.CTkLabel(
            panel,
            text=(
                "When on, Refresh live inserts unseen Current versions into this profile's list "
                "by version order."
            ),
            font=ctk.CTkFont(size=11),
            text_color=self.theme["muted"],
            wraplength=520,
            justify="left",
        ).grid(row=3, column=0, columnspan=2, padx=20, pady=(0, 8), sticky="w")

        ctk.CTkButton(
            panel,
            text="Load recommended catalog seed",
            fg_color=self.theme["surface"],
            hover_color=self.theme["border"],
            border_width=1,
            border_color=self.theme["accent"],
            command=self._firmware_catalog_load_seed,
        ).grid(row=4, column=0, columnspan=2, padx=20, pady=(0, 4), sticky="w")

        ctk.CTkLabel(
            panel,
            text=(
                "Merges built-in IBM/HPE release lists into each profile; "
                "does not remove your entries."
            ),
            font=ctk.CTkFont(size=11),
            text_color=self.theme["muted"],
            wraplength=520,
            justify="left",
        ).grid(row=5, column=0, columnspan=2, padx=20, pady=(0, 16), sticky="w")

        profiles = eligible_firmware_profiles()
        self._firmware_catalog_map = {
            profile: list(versions)
            for profile, versions in load_firmware_catalog(self.db).items()
        }
        self._firmware_selected_index: int | None = None

        ctk.CTkLabel(panel, text="Profile", text_color=self.theme["muted"]).grid(
            row=6, column=0, padx=20, pady=8, sticky="w"
        )
        initial = profiles[0] if profiles else ""
        self.firmware_profile_var = ctk.StringVar(value=initial)
        self._firmware_current_profile = initial
        self.firmware_profile_menu = ctk.CTkOptionMenu(
            panel,
            variable=self.firmware_profile_var,
            values=profiles or [""],
            command=self._on_firmware_profile_change,
        )
        self.firmware_profile_menu.grid(row=6, column=1, padx=20, pady=8, sticky="ew")

        self.firmware_list_frame = ctk.CTkScrollableFrame(
            panel,
            fg_color=self.theme["surface"],
            corner_radius=8,
            height=220,
        )
        self.firmware_list_frame.grid(row=7, column=0, columnspan=2, padx=20, pady=8, sticky="nsew")
        self.firmware_list_frame.grid_columnconfigure(0, weight=1)

        add_row = ctk.CTkFrame(panel, fg_color="transparent")
        add_row.grid(row=8, column=0, columnspan=2, padx=20, pady=8, sticky="ew")
        add_row.grid_columnconfigure(0, weight=1)

        self.firmware_version_entry = ctk.CTkEntry(
            add_row, placeholder_text="Version string (exact match)"
        )
        self.firmware_version_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            add_row,
            text="Add",
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_soft"],
            width=80,
            command=self._firmware_catalog_add,
        ).grid(row=0, column=1)

        buttons = ctk.CTkFrame(panel, fg_color="transparent")
        buttons.grid(row=9, column=0, columnspan=2, padx=20, pady=(8, 8), sticky="w")

        ctk.CTkButton(
            buttons,
            text="Remove",
            fg_color=self.theme["surface"],
            hover_color=self.theme["border"],
            border_width=1,
            border_color=self.theme["accent"],
            command=self._firmware_catalog_remove,
        ).grid(row=0, column=0, padx=(0, 8))

        ctk.CTkButton(
            buttons,
            text="Move up",
            fg_color=self.theme["surface"],
            hover_color=self.theme["border"],
            border_width=1,
            border_color=self.theme["accent"],
            command=self._firmware_catalog_move_up,
        ).grid(row=0, column=1, padx=(0, 8))

        ctk.CTkButton(
            buttons,
            text="Move down",
            fg_color=self.theme["surface"],
            hover_color=self.theme["border"],
            border_width=1,
            border_color=self.theme["accent"],
            command=self._firmware_catalog_move_down,
        ).grid(row=0, column=2, padx=(0, 8))

        ctk.CTkButton(
            buttons,
            text="Save",
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_soft"],
            command=self._firmware_catalog_save,
        ).grid(row=0, column=3, padx=(0, 8))

        self.firmware_catalog_status = ctk.CTkLabel(
            panel,
            text="",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=11),
            wraplength=520,
            justify="left",
        )
        self.firmware_catalog_status.grid(
            row=10, column=0, columnspan=2, padx=20, pady=(4, 20), sticky="w"
        )

        self._refresh_firmware_version_list()

    def _firmware_catalog_load_seed(self) -> None:
        self._stash_firmware_profile()
        current = self._firmware_current_profile
        ui_versions = (
            list(get_profile_catalog(self._firmware_catalog_map, current)) if current else []
        )
        # Prefer fresh DB (live auto-grow); overlay current profile UI edits; then merge seed.
        base = merge_catalog_for_admin_save(
            load_firmware_catalog(self.db), current, ui_versions
        )
        updated, inserted = merge_seed_into_catalog(base, recommended_firmware_seed())
        if inserted > 0:
            updated = save_firmware_catalog(self.db, updated)
            message = f"Seed merged: {inserted} new version(s)."
        else:
            message = "Seed already up to date."
        self._firmware_catalog_map = {
            profile: list(versions) for profile, versions in updated.items()
        }
        self._refresh_firmware_version_list()
        self.firmware_catalog_status.configure(text=message)
        self.admin_status.configure(text=message)

    def _on_firmware_auto_add_toggle(self) -> None:
        enabled = bool(self.firmware_auto_add_var.get())
        save_firmware_auto_add(self.db, enabled)
        state = "on" if enabled else "off"
        message = f"Auto-add from live scans: {state}."
        self.firmware_catalog_status.configure(text=message)
        self.admin_status.configure(text=message)

    def _firmware_versions_for_current(self) -> list[str]:
        profile = self._firmware_current_profile
        if not profile:
            return []
        return get_profile_catalog(self._firmware_catalog_map, profile)

    def _stash_firmware_profile(self) -> None:
        profile = self._firmware_current_profile
        if not profile:
            return
        self._firmware_catalog_map[profile] = list(
            get_profile_catalog(self._firmware_catalog_map, profile)
        )

    def _on_firmware_profile_change(self, selected: str) -> None:
        self._stash_firmware_profile()
        self._firmware_current_profile = selected
        self._firmware_selected_index = None
        self._refresh_firmware_version_list()
        self.firmware_catalog_status.configure(text="")

    def _refresh_firmware_version_list(self) -> None:
        for child in self.firmware_list_frame.winfo_children():
            child.destroy()
        versions = self._firmware_versions_for_current()
        if self._firmware_selected_index is not None and (
            self._firmware_selected_index < 0 or self._firmware_selected_index >= len(versions)
        ):
            self._firmware_selected_index = None
        for index, version in enumerate(versions):
            selected = index == self._firmware_selected_index
            btn = ctk.CTkButton(
                self.firmware_list_frame,
                text=version,
                anchor="w",
                fg_color=self.theme["accent"] if selected else self.theme["surface_alt"],
                hover_color=self.theme["accent_soft"] if selected else self.theme["border"],
                text_color=self.theme["text"],
                command=lambda i=index: self._select_firmware_version(i),
            )
            btn.grid(row=index, column=0, sticky="ew", padx=4, pady=2)

    def _select_firmware_version(self, index: int) -> None:
        self._firmware_selected_index = index
        self._refresh_firmware_version_list()

    def _firmware_catalog_add(self) -> None:
        profile = self._firmware_current_profile
        if not profile:
            self.firmware_catalog_status.configure(text="No profile selected.")
            return
        version = self.firmware_version_entry.get().strip()
        if not version:
            self.firmware_catalog_status.configure(text="Version cannot be blank.")
            return
        versions = list(get_profile_catalog(self._firmware_catalog_map, profile))
        if version in versions:
            self.firmware_catalog_status.configure(text=f"Duplicate version: {version}")
            return
        versions.append(version)
        self._firmware_catalog_map[profile] = versions
        self.firmware_version_entry.delete(0, "end")
        self._firmware_selected_index = len(versions) - 1
        self._refresh_firmware_version_list()
        self.firmware_catalog_status.configure(text=f"Added {version}.")

    def _firmware_catalog_remove(self) -> None:
        profile = self._firmware_current_profile
        versions = list(get_profile_catalog(self._firmware_catalog_map, profile))
        if not versions:
            self.firmware_catalog_status.configure(text="Nothing to remove.")
            return
        index = self._firmware_selected_index
        if index is None or index < 0 or index >= len(versions):
            index = len(versions) - 1
        removed = versions.pop(index)
        self._firmware_catalog_map[profile] = versions
        if not versions:
            self._firmware_selected_index = None
        elif index >= len(versions):
            self._firmware_selected_index = len(versions) - 1
        else:
            self._firmware_selected_index = index
        self._refresh_firmware_version_list()
        self.firmware_catalog_status.configure(text=f"Removed {removed}.")

    def _firmware_catalog_move_up(self) -> None:
        profile = self._firmware_current_profile
        versions = list(get_profile_catalog(self._firmware_catalog_map, profile))
        index = self._firmware_selected_index
        if index is None or index <= 0 or index >= len(versions):
            self.firmware_catalog_status.configure(text="Select a version to move up.")
            return
        versions[index - 1], versions[index] = versions[index], versions[index - 1]
        self._firmware_catalog_map[profile] = versions
        self._firmware_selected_index = index - 1
        self._refresh_firmware_version_list()
        self.firmware_catalog_status.configure(text="")

    def _firmware_catalog_move_down(self) -> None:
        profile = self._firmware_current_profile
        versions = list(get_profile_catalog(self._firmware_catalog_map, profile))
        index = self._firmware_selected_index
        if index is None or index < 0 or index >= len(versions) - 1:
            self.firmware_catalog_status.configure(text="Select a version to move down.")
            return
        versions[index + 1], versions[index] = versions[index], versions[index + 1]
        self._firmware_catalog_map[profile] = versions
        self._firmware_selected_index = index + 1
        self._refresh_firmware_version_list()
        self.firmware_catalog_status.configure(text="")

    def _firmware_catalog_save(self) -> None:
        self._stash_firmware_profile()
        current = self._firmware_current_profile
        current_list = (
            list(get_profile_catalog(self._firmware_catalog_map, current)) if current else []
        )
        # Prefer DB (live auto-grow) for other profiles; overlay current profile UI edits.
        to_save = merge_catalog_for_admin_save(
            load_firmware_catalog(self.db), current, current_list
        )
        saved = save_firmware_catalog(self.db, to_save)
        self._firmware_catalog_map = {
            profile: list(versions) for profile, versions in saved.items()
        }
        self._refresh_firmware_version_list()
        self.firmware_catalog_status.configure(text="Firmware catalog saved.")
        self.admin_status.configure(text="Firmware catalog saved.")

    def _load_capacity_email_form(self) -> None:
        settings = load_capacity_email_settings(self.db)
        self._capacity_email_settings = settings
        self._apply_capacity_email_form(settings)

    def _apply_capacity_email_form(self, settings: dict) -> None:
        self.email_provider_var.set("Outlook" if settings["provider"] == "outlook" else "Gmail")
        self.email_gmail_address_entry.delete(0, "end")
        self.email_gmail_address_entry.insert(0, settings["gmail_address"])
        self.email_gmail_password_entry.delete(0, "end")
        self.email_to_entry.delete(0, "end")
        self.email_to_entry.insert(0, "; ".join(settings["to"]))
        self.email_cc_entry.delete(0, "end")
        self.email_cc_entry.insert(0, "; ".join(settings["cc"]))
        self.email_mode_var.set(self._EMAIL_MODE_LABELS.get(settings["mode"], "Weekly"))
        weekday_index = settings["weekday"] if 0 <= settings["weekday"] <= 6 else 0
        self.email_weekday_var.set(self._EMAIL_WEEKDAY_LABELS[weekday_index])
        self.email_every_n_entry.delete(0, "end")
        self.email_every_n_entry.insert(0, str(settings["every_n_days"]))
        self.email_time_entry.delete(0, "end")
        self.email_time_entry.insert(0, settings["time_local"])
        if settings["enabled"]:
            self.email_enabled_check.select()
        else:
            self.email_enabled_check.deselect()
        self._apply_capacity_email_status(settings)
        self._update_capacity_email_visibility()

    def _apply_capacity_email_status(self, settings: dict) -> None:
        self.email_last_sent_label.configure(
            text=f"Last sent: {settings['last_sent_at'] or 'never'}"
        )
        self.email_last_status_label.configure(
            text=f"Last status: {settings['last_status'] or '—'}"
        )
        self.email_last_error_label.configure(
            text=f"Last error: {settings['last_error'] or '—'}",
            text_color=self.theme["danger"] if settings["last_error"] else self.theme["muted"],
        )

    def _update_capacity_email_visibility(self) -> None:
        is_gmail = self.email_provider_var.get() == "Gmail"
        for widget in (self.email_gmail_address_label, self.email_gmail_address_entry):
            widget.grid() if is_gmail else widget.grid_remove()
        for widget in (self.email_gmail_password_label, self.email_gmail_password_entry):
            widget.grid() if is_gmail else widget.grid_remove()

        mode_key = self._EMAIL_MODE_KEYS.get(self.email_mode_var.get(), "weekly")
        is_weekly = mode_key == "weekly"
        is_every_n = mode_key == "every_n_days"
        for widget in (self.email_weekday_label, self.email_weekday_menu):
            widget.grid() if is_weekly else widget.grid_remove()
        for widget in (self.email_every_n_label, self.email_every_n_entry):
            widget.grid() if is_every_n else widget.grid_remove()

    def _save_capacity_email_form(self, *, silent: bool = False) -> dict | None:
        current = self._capacity_email_settings or load_capacity_email_settings(self.db)
        raw = dict(current)
        raw["enabled"] = bool(self.email_enabled_var.get())
        raw["provider"] = "outlook" if self.email_provider_var.get() == "Outlook" else "gmail"
        raw["gmail_address"] = self.email_gmail_address_entry.get().strip()
        raw["to"] = self.email_to_entry.get()
        raw["cc"] = self.email_cc_entry.get()
        raw["mode"] = self._EMAIL_MODE_KEYS.get(self.email_mode_var.get(), "weekly")
        raw["weekday"] = self._EMAIL_WEEKDAY_LABELS.index(self.email_weekday_var.get())
        raw["every_n_days"] = self.email_every_n_entry.get().strip() or raw.get("every_n_days", 7)
        raw["time_local"] = self.email_time_entry.get().strip()
        normalized = normalize_capacity_email_settings(raw)

        password = self.email_gmail_password_entry.get()
        if password:
            normalized = set_gmail_password(normalized, self.crypto_key, password)

        saved = save_capacity_email_settings(self.db, normalized)
        self._capacity_email_settings = saved
        self._apply_capacity_email_form(saved)
        if not silent and hasattr(self, "admin_status"):
            self.admin_status.configure(
                text="Capacity email settings saved.", text_color=self.theme["accent"]
            )
        return saved

    def _send_capacity_email_now(self) -> None:
        if self._capacity_email_send_in_flight:
            return
        saved = self._save_capacity_email_form(silent=True)
        if saved is None:
            return
        errors = validate_for_send(saved, crypto_key=self.crypto_key)
        if errors:
            messagebox.showerror("Capacity Email", "\n".join(errors))
            return

        self._capacity_email_send_in_flight = True
        self.email_send_btn.configure(state="disabled", text="Sending...")
        if hasattr(self, "admin_status"):
            self.admin_status.configure(
                text="Sending capacity email...", text_color=self.theme["accent"]
            )

        def worker() -> None:
            try:
                result = send_capacity_email(self.db, self.crypto_key, saved)
            except Exception as exc:
                result = {"ok": False, "settings": None, "path": "", "error": str(exc)}
            self.after(0, lambda: self._on_capacity_email_send_done(result))

        threading.Thread(target=worker, daemon=True).start()

    def _on_capacity_email_send_done(self, result: dict) -> None:
        self._capacity_email_send_in_flight = False
        self.email_send_btn.configure(state="normal", text="Send Now")
        settings = result.get("settings")
        if settings:
            self._capacity_email_settings = settings
            self._apply_capacity_email_status(settings)
        if hasattr(self, "admin_status"):
            if result.get("ok"):
                self.admin_status.configure(
                    text="Capacity email sent.", text_color=self.theme["accent"]
                )
            else:
                self.admin_status.configure(
                    text=f"Capacity email failed: {result.get('error', '')}",
                    text_color=self.theme["danger"],
                )

    def _load_dell_report_form(self) -> None:
        settings = load_dell_report_settings(self.db)
        self._dell_report_settings = settings
        self.dell_report_enabled_var.set(bool(settings.get("enabled", True)))
        overrides = settings.get("card_overrides") or {}
        if hasattr(self, "dell_report_overrides_text"):
            self.dell_report_overrides_text.delete("1.0", "end")
            self.dell_report_overrides_text.insert(
                "1.0", json.dumps(overrides, indent=2)
            )

    def _save_dell_report_form(self) -> None:
        overrides_raw = {}
        if hasattr(self, "dell_report_overrides_text"):
            text = self.dell_report_overrides_text.get("1.0", "end").strip() or "{}"
            try:
                overrides_raw = json.loads(text)
            except json.JSONDecodeError:
                messagebox.showerror(
                    "Dell Report", "Card overrides must be a valid JSON object."
                )
                return
            if not isinstance(overrides_raw, dict):
                messagebox.showerror(
                    "Dell Report", "Card overrides must be a JSON object."
                )
                return
        existing = load_dell_report_settings(self.db)
        raw = {
            "enabled": bool(self.dell_report_enabled_var.get()),
            "card_overrides": overrides_raw,
            "include_card_ids": list(existing.get("include_card_ids") or []),
        }
        saved = save_dell_report_settings(self.db, raw)
        self._dell_report_settings = saved
        self.dell_report_enabled_var.set(bool(saved.get("enabled", True)))
        if hasattr(self, "dell_report_overrides_text"):
            self.dell_report_overrides_text.delete("1.0", "end")
            self.dell_report_overrides_text.insert(
                "1.0",
                json.dumps(saved.get("card_overrides") or {}, indent=2),
            )
        if hasattr(self, "admin_status"):
            self.admin_status.configure(
                text="Dell Report settings saved.", text_color=self.theme["accent"]
            )

    def _build_card_list(self, parent) -> None:
        list_panel = ctk.CTkFrame(parent, fg_color=self.theme["surface"], corner_radius=16)
        list_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        list_panel.grid_rowconfigure(1, weight=1)
        list_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            list_panel,
            text="Connections",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.theme["text"],
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        self.list_box = ctk.CTkScrollableFrame(list_panel, fg_color="transparent")
        self.list_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.list_box.grid_columnconfigure(0, weight=1)

    def _build_card_form(self, parent) -> None:
        form_panel = ctk.CTkFrame(parent, fg_color=self.theme["surface"], corner_radius=16)
        form_panel.grid(row=0, column=1, sticky="nsew")
        form_panel.grid_rowconfigure(1, weight=1)
        form_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            form_panel,
            text="Add / Edit Card",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.theme["text"],
        ).grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")

        self.form_mode_label = ctk.CTkLabel(
            form_panel,
            text="New card",
            font=ctk.CTkFont(size=12),
            text_color=self.theme["muted"],
        )
        self.form_mode_label.grid(row=0, column=0, padx=16, pady=(0, 8), sticky="e")

        scroll = ctk.CTkScrollableFrame(form_panel, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        scroll.grid_columnconfigure(1, weight=1)

        fields = [
            ("Name", "name"),
            ("Serial Number", "serial_number"),
            ("Host", "host"),
            ("Port", "port"),
            ("Username", "username"),
            ("Password", "password"),
            ("SSH Key File Path", "key_file_path"),
            ("SSH Key Passphrase", "key_passphrase"),
            ("SSH Private Key", "ssh_key"),
            ("URL (web)", "url"),
            ("Category", "category"),
            ("Glow Color", "glow_color"),
            ("Sort Order", "sort_order"),
        ]
        self.entries: dict[str, ctk.CTkEntry] = {}
        for row, (label, key) in enumerate(fields, start=0):
            ctk.CTkLabel(scroll, text=label, text_color=self.theme["muted"]).grid(
                row=row, column=0, padx=8, pady=6, sticky="w"
            )
            show = self._MASK_CHAR if key in self._SECRET_ENTRY_KEYS else None
            entry = ctk.CTkEntry(scroll, show=show)
            entry.grid(row=row, column=1, padx=8, pady=6, sticky="ew")
            self.entries[key] = entry
            if key == "key_file_path":
                entry.configure(placeholder_text=str(Path.home() / ".ssh" / "wcelease_ed25519"))
            if key == "serial_number":
                entry.configure(
                    placeholder_text="Device serial or Vultr instance ID (optional)"
                )
            if key == "port":
                entry.configure(placeholder_text=str(DEFAULT_SSH_PORT))
            if key == "password":
                entry.configure(
                    placeholder_text="SSH/RDP login password — for SSH, used instead of keys when set",
                    show=self._MASK_CHAR,
                )
            if key == "key_passphrase":
                entry.configure(
                    placeholder_text="Only if your private key file is encrypted",
                    show=self._MASK_CHAR,
                )

        ctk.CTkLabel(
            scroll,
            text="SSH: set Password for login without keys. Use key fields only when you prefer key auth.",
            text_color=self.theme["accent"],
            font=ctk.CTkFont(size=11),
            wraplength=420,
            justify="left",
        ).grid(row=len(fields), column=0, columnspan=2, padx=8, pady=(0, 8), sticky="w")

        ctk.CTkLabel(scroll, text="Type", text_color=self.theme["muted"]).grid(
            row=len(fields) + 1, column=0, padx=8, pady=6, sticky="w"
        )
        self.type_var = ctk.StringVar(value="ssh")
        self.type_menu = ctk.CTkOptionMenu(scroll, variable=self.type_var, values=list(CARD_TYPES))
        self.type_menu.grid(row=len(fields) + 1, column=1, padx=8, pady=6, sticky="ew")

        ctk.CTkLabel(scroll, text="Icon", text_color=self.theme["muted"]).grid(
            row=len(fields) + 2, column=0, padx=8, pady=6, sticky="w"
        )
        self.icon_var = ctk.StringVar(value="terminal")
        self.icon_menu = ctk.CTkOptionMenu(
            scroll,
            variable=self.icon_var,
            values=list(ICON_CHOICES.keys()),
        )
        self.icon_menu.grid(row=len(fields) + 2, column=1, padx=8, pady=6, sticky="ew")

        self.icon_preview = ctk.CTkLabel(
            scroll,
            text=ICON_CHOICES["terminal"],
            font=ctk.CTkFont(size=28),
            text_color=self.theme["accent"],
        )
        self.icon_preview.grid(row=len(fields) + 2, column=2, padx=8, pady=6)
        self.icon_var.trace_add("write", self._update_icon_preview)

        profile_row = len(fields) + 3
        ctk.CTkLabel(scroll, text="Device Profile", text_color=self.theme["muted"]).grid(
            row=profile_row, column=0, padx=8, pady=6, sticky="w"
        )
        self.device_profile_var = ctk.StringVar(value="")
        profile_keys = list(DEVICE_PROFILES.keys())
        profile_labels = [DEVICE_PROFILES[key] for key in profile_keys]
        general = DEVICE_PROFILES[""]
        sorted_labels = [general] + sorted(label for label in profile_labels if label != general)
        sorted_keys = [""] + sorted(
            (key for key in profile_keys if key),
            key=lambda key: DEVICE_PROFILES[key].lower(),
        )
        self._device_profile_keys = sorted_keys
        self.device_profile_menu = ctk.CTkComboBox(
            scroll,
            variable=self.device_profile_var,
            values=sorted_labels,
            command=self._on_device_profile_change,
            width=320,
            height=32,
            dropdown_hover_color=self.theme["border"],
        )
        self.device_profile_menu.grid(row=profile_row, column=1, padx=8, pady=6, sticky="ew")
        self._device_profile_label_to_key = dict(
            zip(sorted_labels, sorted_keys, strict=True)
        )
        self.device_profile_var.set(general)

        ctk.CTkLabel(
            scroll,
            text=f"{len(sorted_labels) - 1} device platforms (v{APP_VERSION}) — scroll list for Vultr",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=11),
        ).grid(row=profile_row, column=2, padx=8, pady=6, sticky="w")

        commands_row = profile_row + 1
        ctk.CTkLabel(scroll, text="SSH Commands", text_color=self.theme["muted"]).grid(
            row=commands_row, column=0, padx=8, pady=(6, 0), sticky="nw"
        )
        commands_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        commands_frame.grid(row=commands_row, column=1, padx=8, pady=6, sticky="ew")
        commands_frame.grid_columnconfigure(0, weight=1)

        self.commands_box = ctk.CTkTextbox(
            commands_frame,
            height=180,
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self.commands_box.grid(row=0, column=0, sticky="ew")
        self.commands_box.insert(
            "1.0",
            "# One command per line. Optional label:\n"
            "# Health - Nodes|svcinfo lsnode\n"
            "# svcinfo lssystem\n",
        )

        ctk.CTkButton(
            commands_frame,
            text="Load Device Presets",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._load_device_presets,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

        ctk.CTkLabel(
            scroll,
            text=(
                "Pick a device profile (storage, Vultr, etc.) and click Load Device Presets for health, "
                "CPU, memory, and capacity commands — or paste your own CLI commands."
            ),
            text_color=self.theme["accent"],
            font=ctk.CTkFont(size=11),
            wraplength=420,
            justify="left",
        ).grid(row=commands_row + 1, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="w")

        actions = ctk.CTkFrame(form_panel, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        actions.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(
            actions,
            text="Save Card",
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_soft"],
            command=self._save_card,
        ).grid(row=0, column=0, padx=4, sticky="ew")

        ctk.CTkButton(actions, text="New Card", command=self._clear_form).grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(
            actions,
            text="Delete",
            fg_color=self.theme["danger"],
            hover_color="#B91C1C",
            command=self._delete_card,
        ).grid(row=0, column=2, padx=4, sticky="ew")

        self.test_ssh_btn = ctk.CTkButton(
            actions,
            text="Test SSH Login",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            border_width=1,
            border_color=self.theme["accent"],
            command=self._test_ssh_connection,
        )
        self.test_ssh_btn.grid(row=1, column=0, columnspan=3, padx=4, pady=(10, 0), sticky="ew")

        self.entries["glow_color"].insert(0, DEFAULT_GLOW_COLOR)
        self.entries["category"].insert(0, "General")
        self.entries["sort_order"].insert(0, "0")
        self.entries["port"].insert(0, str(DEFAULT_SSH_PORT))
        self._set_form_mode(editing=False)

    def _ssh_form_values(self) -> tuple[str, int, str, str, str, str, str]:
        host = self.entries["host"].get().strip()
        port_raw = self.entries["port"].get().strip()
        port = int(port_raw) if port_raw else DEFAULT_SSH_PORT
        username = self.entries["username"].get().strip()
        password = self.entries["password"].get()
        key_passphrase = self.entries["key_passphrase"].get()
        key_path = normalize_key_file_path(self.entries["key_file_path"].get().strip())
        ssh_key = self.entries["ssh_key"].get().strip()
        return host, port, username, password, key_passphrase, key_path, ssh_key

    def _test_ssh_connection(self) -> None:
        if self._ssh_test_in_flight:
            return
        if self.type_var.get() != "ssh":
            messagebox.showinfo("Admin", "SSH login test is only available for SSH cards.")
            return

        name = self.entries["name"].get().strip() or "SSH Card"
        try:
            host, port, username, password, key_passphrase, key_path, ssh_key = self._ssh_form_values()
            if not host:
                raise ValueError("Host is required.")
            if not username:
                raise ValueError("Username is required.")
            if ssh_key and "PRIVATE KEY" not in ssh_key:
                raise ValueError(
                    "SSH Private Key must be your private key file, not the .pub public key."
                )
            key_path_raw = self.entries["key_file_path"].get().strip()
            if key_path_raw and not Path(key_path).expanduser().exists() and not password and not ssh_key:
                raise ValueError(f"SSH key file not found:\n{key_path}")
            if not password and not key_path_raw and not ssh_key:
                raise ValueError("Set SSH Password or an SSH key file / private key to test login.")
        except ValueError as exc:
            messagebox.showerror("Admin", str(exc))
            return

        port_label = f":{port}"
        target_label = f"{username}@{host}{port_label}"
        self._ssh_test_in_flight = True
        self.test_ssh_btn.configure(state="disabled", text="Testing SSH...")
        if hasattr(self, "admin_status"):
            self.admin_status.configure(
                text=f"Testing SSH login to {target_label}...",
                text_color=self.theme["accent"],
            )

        result_queue: queue.Queue[tuple[bool, str]] = queue.Queue(maxsize=1)

        def worker() -> None:
            try:
                summary = test_ssh_login(
                    host,
                    port,
                    username,
                    password=password,
                    key_file_path=key_path,
                    key_passphrase=key_passphrase,
                    ssh_key_text=ssh_key,
                )
                result_queue.put((True, summary))
            except Exception as exc:
                result_queue.put((False, str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        deadline = time.monotonic() + 35
        self._poll_ssh_test_result(name, target_label, result_queue, deadline)

    def _poll_ssh_test_result(
        self,
        card_name: str,
        target_label: str,
        result_queue: queue.Queue[tuple[bool, str]],
        deadline: float,
    ) -> None:
        if self._ssh_test_poll_id:
            try:
                self.after_cancel(self._ssh_test_poll_id)
            except ValueError:
                pass
            self._ssh_test_poll_id = None

        try:
            success, message = result_queue.get_nowait()
            self._show_ssh_test_result(
                card_name,
                target_label,
                success=success,
                message=message,
            )
            return
        except queue.Empty:
            pass

        if time.monotonic() >= deadline:
            self._show_ssh_test_result(
                card_name,
                target_label,
                success=False,
                message=(
                    "SSH test timed out after 35 seconds.\n\n"
                    "Check host, port, firewall, username, and credentials.\n"
                    "If the key is encrypted, enter the key passphrase."
                ),
            )
            return

        self._ssh_test_poll_id = self.after(
            200,
            lambda: self._poll_ssh_test_result(card_name, target_label, result_queue, deadline),
        )

    def _show_ssh_test_result(
        self,
        card_name: str,
        target_label: str,
        *,
        success: bool,
        message: str,
    ) -> None:
        self._ssh_test_in_flight = False
        self.test_ssh_btn.configure(state="normal", text="Test SSH Login")
        if hasattr(self, "admin_status"):
            status = f"SSH test OK for {target_label}" if success else f"SSH test failed for {target_label}"
            self.admin_status.configure(
                text=status,
                text_color=self.theme["accent"] if success else self.theme["danger"],
            )

        if self.editing_id and self.editing_id in self._admin_ssh_leds:
            set_ssh_status_led(
                self._admin_ssh_leds[self.editing_id],
                "ok" if success else "fail",
                message,
            )

        if self._ssh_test_dialog and self._ssh_test_dialog.winfo_exists():
            self._ssh_test_dialog.destroy()

        self._ssh_test_dialog = SshTestDialog(
            self.winfo_toplevel(),
            theme_name=self.db.get_setting("theme", "dark"),
            card_name=card_name,
            target_label=target_label,
            success=success,
            message=message,
            on_return_admin=None,
            on_return_dashboard=self.on_back,
        )
        self._ssh_test_dialog.focus_force()

    def _on_device_profile_change(self, selected_label: str) -> None:
        profile_key = self._device_profile_label_to_key.get(selected_label, "")
        if is_storage_profile(profile_key):
            self.commands_box.delete("1.0", "end")
            self.commands_box.insert("1.0", preset_command_text(profile_key))

    def _load_device_presets(self) -> None:
        selected_label = self.device_profile_var.get()
        profile_key = self._device_profile_label_to_key.get(selected_label, "")
        if not is_storage_profile(profile_key):
            messagebox.showinfo(
                "Admin",
                "Choose a storage device profile first (IBM, HPE, etc.).",
            )
            return
        self.commands_box.delete("1.0", "end")
        self.commands_box.insert("1.0", preset_command_text(profile_key))
        if hasattr(self, "admin_status"):
            self.admin_status.configure(
                text=f"Loaded {len(preset_commands_for_profile(profile_key))} preset command(s) for {selected_label}.",
                text_color=self.theme["accent"],
            )

    def _selected_device_profile_key(self) -> str:
        return self._device_profile_label_to_key.get(self.device_profile_var.get(), "")

    def _get_commands_text(self) -> str:
        return self.commands_box.get("1.0", "end").strip()

    def _set_commands_text(self, text: str) -> None:
        self.commands_box.delete("1.0", "end")
        if text:
            self.commands_box.insert("1.0", text)
        else:
            self.commands_box.insert(
                "1.0",
                "# One command per line. Optional label:\n"
                "# Health - Nodes|svcinfo lsnode\n",
            )

    def _update_icon_preview(self, *_args) -> None:
        key = self.icon_var.get()
        self.icon_preview.configure(text=ICON_CHOICES.get(key, "●"))

    def refresh_list(self) -> None:
        if not hasattr(self, "list_box"):
            return
        if self._admin_ssh_status_timer:
            self.after_cancel(self._admin_ssh_status_timer)
            self._admin_ssh_status_timer = None
        for child in self.list_box.winfo_children():
            child.destroy()
        self._admin_ssh_leds.clear()
        for card in self.db.list_cards():
            row = ctk.CTkFrame(self.list_box, fg_color=self.theme["surface_alt"], corner_radius=10)
            row.grid(sticky="ew", padx=4, pady=4)
            row.grid_columnconfigure(2, weight=1)

            if card.card_type == "ssh":
                led = create_ssh_status_led(row, self.theme, state="unknown")
                led.grid(row=0, column=0, padx=(10, 6), pady=8, sticky="w")
                self._admin_ssh_leds[card.id] = led
            else:
                spacer = ctk.CTkFrame(row, width=10, height=10, fg_color="transparent")
                spacer.grid(row=0, column=0, padx=(10, 6), pady=8, sticky="w")
                spacer.grid_propagate(False)

            ctk.CTkLabel(
                row,
                text=resolve_icon(card.icon, card.card_type),
                font=ctk.CTkFont(size=20),
                width=32,
            ).grid(row=0, column=1, padx=(0, 4), pady=8)

            ctk.CTkLabel(
                row,
                text=f"{card.name}  [{card.card_type.upper()}]",
                text_color=self.theme["text"],
            ).grid(row=0, column=2, padx=4, pady=8, sticky="w")

            ctk.CTkButton(
                row,
                text="Edit",
                width=60,
                command=lambda cid=card.id: self._load_card(cid),
            ).grid(row=0, column=3, padx=(8, 4), pady=8)

            ctk.CTkButton(
                row,
                text="Delete",
                width=60,
                fg_color=self.theme["danger"],
                hover_color="#B91C1C",
                command=lambda cid=card.id, cname=card.name: self._delete_card_by_id(cid, cname),
            ).grid(row=0, column=4, padx=(4, 8), pady=8)

        self.after(300, self._probe_admin_ssh_status)
        self._schedule_admin_ssh_status_checks()

    def _schedule_admin_ssh_status_checks(self) -> None:
        if self._admin_ssh_status_timer:
            self.after_cancel(self._admin_ssh_status_timer)
        self._admin_ssh_status_timer = self.after(
            SSH_STATUS_INTERVAL_MS, self._on_admin_ssh_status_timer
        )

    def _on_admin_ssh_status_timer(self) -> None:
        self._admin_ssh_status_timer = None
        self._probe_admin_ssh_status()
        self._schedule_admin_ssh_status_checks()

    def _probe_admin_ssh_status(self) -> None:
        for card_id, led in list(self._admin_ssh_leds.items()):
            set_ssh_status_led(led, "checking")
            if card_id in self._admin_ssh_status_in_flight:
                continue
            threading.Thread(
                target=self._probe_admin_ssh_status_worker,
                args=(card_id,),
                daemon=True,
            ).start()

    def _probe_admin_ssh_status_worker(self, card_id: int) -> None:
        if card_id in self._admin_ssh_status_in_flight:
            return
        self._admin_ssh_status_in_flight.add(card_id)
        try:
            card = self.db.get_card(card_id)
            if not card or card.card_type != "ssh":
                return
            status, message = probe_ssh_login_for_card(card, self.crypto_key)
            self.after(
                0,
                lambda cid=card_id, s=status, m=message: self._apply_admin_ssh_status(cid, s, m),
            )
        finally:
            self._admin_ssh_status_in_flight.discard(card_id)

    def _apply_admin_ssh_status(self, card_id: int, status: str, message: str = "") -> None:
        set_ssh_status_led(self._admin_ssh_leds.get(card_id), status, message)

    def _mask_secret_entries(self) -> None:
        """CustomTkinter can drop show= after insert/configure — re-apply masking."""
        for key in self._SECRET_ENTRY_KEYS:
            entry = self.entries.get(key)
            if entry:
                entry.configure(show=self._MASK_CHAR)

    def _set_form_mode(self, *, editing: bool, name: str = "") -> None:
        if not hasattr(self, "form_mode_label"):
            return
        if editing and name:
            self.form_mode_label.configure(text=f"Editing: {name}")
        else:
            self.form_mode_label.configure(text="New card")

    def _reset_form(self, *, defaults: bool = False) -> None:
        self.editing_id = None
        for entry in self.entries.values():
            entry.delete(0, "end")
        self.type_var.set("ssh")
        self.icon_var.set("terminal")
        if hasattr(self, "device_profile_var"):
            self.device_profile_var.set(DEVICE_PROFILES[""])
        if hasattr(self, "commands_box"):
            self._set_commands_text("")
        if defaults:
            self.entries["glow_color"].insert(0, DEFAULT_GLOW_COLOR)
            self.entries["category"].insert(0, "General")
            self.entries["sort_order"].insert(0, "0")
            self.entries["port"].insert(0, str(DEFAULT_SSH_PORT))
        self._mask_secret_entries()
        self._set_form_mode(editing=False)

    def _clear_form(self) -> None:
        self._reset_form(defaults=True)

    def _load_card(self, card_id: int) -> None:
        card = self.db.get_card(card_id)
        if not card:
            return
        self._reset_form(defaults=False)
        self.editing_id = card_id
        self._set_form_mode(editing=True, name=card.name)
        self.entries["name"].insert(0, card.name)
        self.entries["serial_number"].insert(0, getattr(card, "serial_number", "") or "")
        self.entries["host"].insert(0, card.host)
        if card.card_type == "ssh":
            self.entries["port"].insert(
                0, str(card.port if card.port is not None else DEFAULT_SSH_PORT)
            )
        elif card.port is not None:
            self.entries["port"].insert(0, str(card.port))
        self.entries["username"].insert(0, card.username)
        self.entries["url"].insert(0, card.url)
        self.entries["category"].insert(0, card.category or "General")
        self.entries["glow_color"].insert(0, card.glow_color or DEFAULT_GLOW_COLOR)
        self.entries["sort_order"].insert(0, str(card.sort_order))
        key_path = normalize_key_file_path(getattr(card, "key_file_path", "") or "")
        self.entries["key_file_path"].insert(0, key_path)
        self.type_var.set(card.card_type)
        icon_key = card.icon if card.icon in ICON_CHOICES else "terminal"
        self.icon_var.set(icon_key)

        if card.encrypted_password:
            try:
                self.entries["password"].insert(
                    0, decrypt_text(self.crypto_key, card.encrypted_password)
                )
            except ValueError:
                messagebox.showwarning(
                    "Admin",
                    "Could not decrypt the stored SSH/RDP password for this card.\n\n"
                    "It may have been imported from a backup using a different vault password. "
                    "Re-enter the password and click Save.",
                )
        if card.encrypted_key_passphrase:
            try:
                self.entries["key_passphrase"].insert(
                    0, decrypt_text(self.crypto_key, card.encrypted_key_passphrase)
                )
            except ValueError:
                messagebox.showwarning(
                    "Admin",
                    "Could not decrypt the stored key passphrase for this card.\n\n"
                    "Re-enter the passphrase and click Save.",
                )
        if card.encrypted_key:
            try:
                self.entries["ssh_key"].insert(0, decrypt_text(self.crypto_key, card.encrypted_key))
            except ValueError:
                messagebox.showwarning(
                    "Admin",
                    "Could not decrypt the stored private key for this card.\n\n"
                    "Re-enter the key and click Save.",
                )
        self._mask_secret_entries()

        if hasattr(self, "commands_box"):
            self._set_commands_text(getattr(card, "custom_commands", "") or "")

        profile_key = getattr(card, "device_profile", "") or ""
        profile_label = DEVICE_PROFILES.get(profile_key, DEVICE_PROFILES[""])
        if hasattr(self, "device_profile_var"):
            self.device_profile_var.set(profile_label)
        if hasattr(self, "admin_status") and is_storage_profile(profile_key):
            self.admin_status.configure(
                text=(
                    f"Editing '{card.name}' — click Load Device Presets to load the latest "
                    f"{profile_label} CLI commands, then Save."
                ),
                text_color=self.theme["accent"],
            )
        elif hasattr(self, "admin_status"):
            self.admin_status.configure(text="", text_color=self.theme["muted"])

    def _save_card(self) -> None:
        name = self.entries["name"].get().strip()
        card_type = self.type_var.get()
        host = self.entries["host"].get().strip()
        url = self.entries["url"].get().strip()
        if not name:
            messagebox.showerror("Admin", "Name is required.")
            return
        if card_type == "web" and not (url or host):
            messagebox.showerror("Admin", "Web cards need a URL or host.")
            return
        if card_type != "web" and not host:
            messagebox.showerror("Admin", "Host is required for SSH and RDP cards.")
            return

        port_raw = self.entries["port"].get().strip()
        if card_type == "ssh":
            port = int(port_raw) if port_raw else DEFAULT_SSH_PORT
        else:
            port = int(port_raw) if port_raw else None
        sort_raw = self.entries["sort_order"].get().strip()
        sort_order = int(sort_raw) if sort_raw else 0

        password = self.entries["password"].get()
        key_passphrase = self.entries["key_passphrase"].get()
        ssh_key = self.entries["ssh_key"].get().strip()
        if card_type == "ssh" and ssh_key and "PRIVATE KEY" not in ssh_key:
            messagebox.showerror(
                "Admin",
                "SSH Private Key must be your private key file (id_ed25519), "
                "not the .pub public key.",
            )
            return

        key_path_raw = self.entries["key_file_path"].get().strip()
        key_path = normalize_key_file_path(key_path_raw)
        if card_type == "ssh" and key_path_raw and not Path(key_path).expanduser().exists():
            messagebox.showerror("Admin", f"SSH key file not found:\n{key_path}")
            return

        data = {
            "name": name,
            "card_type": card_type,
            "host": host,
            "port": port,
            "serial_number": self.entries["serial_number"].get().strip(),
            "username": self.entries["username"].get().strip(),
            "encrypted_password": encrypt_text(self.crypto_key, password),
            "encrypted_key_passphrase": encrypt_text(self.crypto_key, key_passphrase),
            "encrypted_key": encrypt_text(self.crypto_key, ssh_key),
            "url": url,
            "category": self.entries["category"].get().strip() or "General",
            "sort_order": sort_order,
            "glow_color": normalize_color(self.entries["glow_color"].get().strip(), DEFAULT_GLOW_COLOR),
            "icon": self.icon_var.get(),
            "key_file_path": key_path,
            "device_profile": self._selected_device_profile_key(),
            "custom_commands": self._get_commands_text(),
        }

        if self.editing_id:
            self.db.update_card(self.editing_id, data)
        else:
            self.db.add_card(data)

        self.refresh_list()
        saved_name = name
        self._clear_form()
        if hasattr(self, "admin_status"):
            self.admin_status.configure(
                text=f"Saved '{saved_name}'. Ready for a new card — or click Edit on the left to change it.",
                text_color=self.theme["accent"],
            )

    def _delete_card(self) -> None:
        if not self.editing_id:
            messagebox.showwarning("Admin", "Select a card to delete (click Edit first).")
            return
        card = self.db.get_card(self.editing_id)
        if not card:
            messagebox.showwarning("Admin", "Card not found.")
            self._clear_form()
            self.refresh_list()
            return
        self._delete_card_by_id(self.editing_id, card.name)

    def _delete_card_by_id(self, card_id: int, card_name: str) -> None:
        if not messagebox.askyesno("Admin", f"Delete '{card_name}'?"):
            return
        self.db.delete_card(card_id)
        if self.editing_id == card_id:
            self._clear_form()
        self.refresh_list()
        if hasattr(self, "admin_status"):
            self.admin_status.configure(text=f"Deleted '{card_name}'.", text_color=self.theme["muted"])

    def _export_backup(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export LaunchPad Backup",
            defaultextension=".lpb",
            filetypes=[("LaunchPad Backup", "*.lpb"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            cards = self.db.export_cards_raw()
            write_backup_file(
                path,
                self.crypto_key,
                cards,
                master_salt=self.db.get_setting("master_salt"),
            )
            messagebox.showinfo("Admin", f"Backup exported to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Admin", f"Export failed: {exc}")

    def _import_backup(self) -> None:
        path = filedialog.askopenfilename(
            title="Import LaunchPad Backup",
            filetypes=[("LaunchPad Backup", "*.lpb"), ("All files", "*.*")],
        )
        if not path:
            return

        merge = messagebox.askyesno(
            "Import Mode",
            "Choose import mode:\n\n"
            "Yes = Merge (add cards from backup)\n"
            "No = Replace (delete existing cards first)",
        )
        mode = "merge" if merge else "replace"

        if mode == "replace" and not messagebox.askyesno(
            "Confirm Replace",
            "This will delete all existing cards. Continue?",
        ):
            return

        try:
            cards = read_backup_file(path, self.crypto_key)
        except BackupDecryptError:
            cards = self._read_backup_with_export_password(path)
            if cards is None:
                return

        try:
            count = self.db.import_cards(cards, mode=mode)
            self.refresh_list()
            messagebox.showinfo("Admin", f"Imported {count} card(s) successfully.")
        except Exception as exc:
            messagebox.showerror("Admin", f"Import failed: {exc}")

    def _read_backup_with_export_password(self, path: str) -> list[dict] | None:
        from launchpad.backup import read_backup_wrapper

        try:
            wrapper = read_backup_wrapper(Path(path).read_text(encoding="utf-8"))
        except ValueError as exc:
            messagebox.showerror("Admin", f"Import failed: {exc}")
            return None

        master_salt = wrapper.get("master_salt", "")
        if not master_salt:
            messagebox.showerror(
                "Admin",
                "This backup could not be decrypted with your current vault password.\n\n"
                "It was exported from a different vault and does not include migration "
                "information (older LaunchPad versions).\n\n"
                "Fix options:\n"
                "• Export a new backup from the original PC using LaunchPad v1.2.0+\n"
                "• Or copy the entire folder:\n"
                "  %APPDATA%\\LaunchPad",
            )
            return None

        password = simpledialog.askstring(
            "Backup Master Password",
            "This backup was created on another vault.\n\n"
            "Enter the master password that was used when the backup was exported.\n"
            "Your cards will be re-encrypted for this vault after import.",
            show="*",
            parent=self.winfo_toplevel(),
        )
        if not password:
            return None

        try:
            return read_backup_file(
                path,
                self.crypto_key,
                backup_password=password,
                backup_master_salt=master_salt,
                vault_crypto_key=self.crypto_key,
            )
        except BackupDecryptError:
            messagebox.showerror(
                "Admin",
                "That password did not open the backup.\n\n"
                "Use the exact master password from the PC where you exported the backup.",
            )
            return None
        except ValueError as exc:
            messagebox.showerror("Admin", f"Import failed: {exc}")
            return None

    def apply_theme(self, theme_name: str) -> None:
        self.theme = get_theme(theme_name)
