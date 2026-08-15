import customtkinter as ctk
import json
import threading
from pathlib import Path
from tkinter import Menu, filedialog, messagebox
from typing import Any

from launchpad.branding import get_app_name, load_ctk_logo
from launchpad.capacity_email_scheduler import is_capacity_email_due
from launchpad.capacity_email_send import send_capacity_email
from launchpad.capacity_email_settings import load_capacity_email_settings
from launchpad.capacity_units import (
    SETTING_CAPACITY_UNIT_MODE,
    get_capacity_unit_mode,
    load_capacity_unit_mode,
    set_capacity_unit_mode,
)
from launchpad.dell_report_family import dell_report_family
from launchpad.dell_report_settings import (
    is_dell_report_enabled,
    load_dell_report_settings,
    save_dell_report_settings,
)
from launchpad.command_format import resolve_card_commands
from launchpad.crypto import decrypt_text
from launchpad.dashboard_array_rail import (
    SETTING_ARRAY_RAIL_COLLAPSED,
    can_open_rail_gui,
    collapsed_from_setting,
    filter_dashboard_cards,
    open_rail_gui,
    rail_row_subtitle,
    rail_row_title,
    setting_from_collapsed,
)
from launchpad.database import Card
from launchpad.health_format import card_stats_columns, command_results_columns
from launchpad.health_alert_art import ensure_health_alert_art_dir
from launchpad.health_alert_state import same_health_alert_card_id
from launchpad.health_metrics import run_remote_metrics
from launchpad.health_server import get_health_server
from launchpad.launchers import launch_card
from launchpad.mouse_jiggler import SETTING_MOUSE_JIGGLER, setting_to_enabled
from launchpad.monitor import (
    build_health_dashboard_entries,
    ensure_health_dashboard_registered,
    get_monitor_states,
    open_capacity_report_for_cards,
    open_fc_wwpn_report_for_cards,
    open_ansible_pad_for_cards,
    open_host_power_for_cards,
    open_site_lookup_for_cards,
    open_health_dashboard,
    open_health_dashboard_for_cards,
    set_all_monitor_enabled,
    set_card_monitor_enabled,
)
from launchpad.ssh_commands import run_remote_command_suite
from launchpad.ssh_launcher import _log
from launchpad.ssh_test import probe_ssh_login_for_card
from launchpad.ssh_utils import (
    resolve_ssh_key,
    resolve_ssh_metrics_auth,
    resolve_sudo_password,
    ssh_stats_prereq_message,
)
from launchpad.ui.card_widget import GlowCard
from launchpad.ui.health_alert_dialog import (
    HEALTH_ALERT_POLL_MS,
    HealthAlertDialog,
    group_health_alerts,
    play_health_alert_beep,
)
from launchpad.ui.stats_snapshot_dialog import StatsSnapshotDialog
from launchpad.ui.colors import normalize_color
from launchpad.ui.theme import get_theme

SSH_STATUS_INTERVAL_MS = 90_000
CAPACITY_EMAIL_POLL_MS = 60_000
# Keep report tools on two horizontal rows so they stay on-screen.
HEADER_TOOLS_PER_ROW = 6


class DashboardView(ctk.CTkFrame):
    def __init__(self, master, db, crypto_key, on_admin, on_lock) -> None:
        self.theme_name = db.get_setting("theme", "dark")
        self.theme = get_theme(self.theme_name)
        super().__init__(master, fg_color=self.theme["bg"])
        self.db = db
        load_capacity_unit_mode(self.db)
        self.crypto_key = crypto_key
        self.on_admin = on_admin
        self.on_lock = on_lock
        self.card_widgets: list[GlowCard] = []
        self._ssh_cards: list[Card] = []
        self._stats_timer: str | None = None
        self._logo_image = None
        self._snapshot_dialog: StatsSnapshotDialog | None = None
        self._stats_in_flight: set[int] = set()
        self._ssh_status_in_flight: set[int] = set()
        self._ssh_status_timer: str | None = None
        self._capacity_alert_timer: str | None = None
        self._health_alert_timer: str | None = None
        self._health_alert_dialog = None
        self._health_alert_queue: list[dict] = []
        self._health_alert_queue_index = 0
        self._health_alert_beeped: set[str] = set()
        self._health_alert_poll_in_flight = False
        self._health_alert_cards_meta: dict[str, dict] = {}
        self._health_alert_overlay_dismissed: dict[int, str] = {}
        ensure_health_alert_art_dir()
        self._capacity_email_timer: str | None = None
        self._capacity_email_send_in_flight = False
        self._visible_cards: dict[int, Card] = {}
        self._monitor_states: dict[int, bool] = {}
        self._cards_compact = self.db.get_setting("cards_compact", "true") == "true"
        self._expanded_card_ids = self._load_expanded_card_ids()
        self._mouse_jiggler_enabled = setting_to_enabled(
            self.db.get_setting(SETTING_MOUSE_JIGGLER, "")
        )

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_filters()

        self.array_rail_collapsed = collapsed_from_setting(
            self.db.get_setting(SETTING_ARRAY_RAIL_COLLAPSED, "false")
        )

        self.body_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.body_frame.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 16))
        self.body_frame.grid_columnconfigure(1, weight=1)
        self.body_frame.grid_rowconfigure(0, weight=1)

        self.rail_frame = ctk.CTkFrame(self.body_frame, fg_color=self.theme["surface"], width=220)
        self.rail_frame.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        self.rail_frame.grid_propagate(False)

        rail_header = ctk.CTkFrame(self.rail_frame, fg_color="transparent")
        rail_header.pack(fill="x", padx=8, pady=(8, 4))

        self.array_rail_title = ctk.CTkLabel(
            rail_header,
            text="Arrays",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.theme["text"],
        )
        self.array_rail_title.pack(side="left")

        self.array_rail_toggle = ctk.CTkButton(
            rail_header,
            text="«",
            width=28,
            height=28,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._toggle_array_rail,
        )
        self.array_rail_toggle.pack(side="right")

        self.array_rail_list = ctk.CTkScrollableFrame(self.rail_frame, fg_color="transparent")
        self.array_rail_list.pack(fill="both", expand=True, padx=4, pady=(0, 8))

        self.cards_frame = ctk.CTkScrollableFrame(self.body_frame, fg_color=self.theme["surface"])
        self.cards_frame.grid(row=0, column=1, sticky="nsew")
        self._card_columns = 4
        for col in range(self._card_columns):
            self.cards_frame.grid_columnconfigure(col, weight=1)

        self._apply_array_rail_collapsed()

        self.status_row = ctk.CTkFrame(self, fg_color="transparent")
        self.status_row.grid(row=3, column=0, sticky="ew", padx=28, pady=(0, 12))
        self.status_row.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            self.status_row,
            text="",
            text_color=self.theme["muted"],
            anchor="w",
            justify="left",
        )
        self.status_label.grid(row=0, column=0, sticky="ew")

        self.report_url_var = ctk.StringVar(value="")
        self.report_url_entry = ctk.CTkEntry(
            self.status_row,
            textvariable=self.report_url_var,
            height=28,
            border_width=1,
            fg_color=self.theme["surface_alt"],
            border_color=self.theme["border"],
            text_color=self.theme["text"],
        )
        self.report_url_entry.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.report_url_entry.bind("<FocusIn>", lambda _e: self.report_url_entry.select_range(0, "end"))
        self.report_url_entry.grid_remove()

        self.copy_url_btn = ctk.CTkButton(
            self.status_row,
            text="Copy URL",
            width=90,
            height=28,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._copy_report_url,
        )
        self.copy_url_btn.grid(row=1, column=1, padx=(8, 0), pady=(6, 0))
        self.copy_url_btn.grid_remove()

        self.hint_label = ctk.CTkLabel(
            self,
            text="",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=11),
        )
        self.hint_label.grid(row=4, column=0, sticky="w", padx=28, pady=(0, 8))

        self.refresh_cards()
        self.after(200, self._register_health_cards_main_thread)
        self._schedule_capacity_email_timer()

    def _register_health_cards_main_thread(self) -> None:
        def worker() -> None:
            try:
                count = ensure_health_dashboard_registered(self.db, self.crypto_key)
                if count:
                    _log(f"Health dashboard pre-registered {count} SSH card(s)")
            except Exception as exc:
                _log(f"Health dashboard pre-register failed: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        header.grid_columnconfigure(1, weight=1)

        title_row = ctk.CTkFrame(header, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="w")

        self._logo_image = load_ctk_logo(self.db, size=(40, 40))
        if self._logo_image:
            self.logo_label = ctk.CTkLabel(title_row, text="", image=self._logo_image)
            self.logo_label.pack(side="left", padx=(0, 10))

        title_text = ctk.CTkFrame(title_row, fg_color="transparent")
        title_text.pack(side="left")

        app_name = get_app_name(self.db)
        self.title_label = ctk.CTkLabel(
            title_text,
            text=app_name,
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=self.theme["accent"],
            anchor="w",
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            title_text,
            text="Connection Dashboard",
            font=ctk.CTkFont(size=14),
            text_color=self.theme["muted"],
            anchor="w",
        )
        self.subtitle_label.pack(anchor="w")

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=2, sticky="e")

        self.capacity_unit_switch = ctk.CTkSwitch(
            controls,
            text="GB/TB" if get_capacity_unit_mode() == "si" else "GiB/TiB",
            command=self._toggle_capacity_unit_mode,
        )
        self.capacity_unit_switch.grid(row=0, column=0, padx=6)
        if get_capacity_unit_mode() == "si":
            self.capacity_unit_switch.select()

        self.theme_switch = ctk.CTkSwitch(
            controls,
            text="Light mode" if self.theme_name == "dark" else "Dark mode",
            command=self._toggle_theme,
        )
        self.theme_switch.grid(row=0, column=1, padx=6)

        ctk.CTkButton(
            controls,
            text="Admin",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self.on_admin,
        ).grid(row=0, column=2, padx=6)

        ctk.CTkButton(
            controls,
            text="Lock",
            fg_color=self.theme["danger"],
            hover_color="#B91C1C",
            command=self.on_lock,
        ).grid(row=0, column=3, padx=6)

        # Full-width tools under the title, fixed to two horizontal rows.
        tools = ctk.CTkFrame(header, fg_color="transparent")
        tools.grid(row=1, column=0, columnspan=3, sticky="w", pady=(12, 0))

        tool_specs = [
            ("Health Dashboard", self._open_health_dashboard_all, None),
            ("Capacity Report", self._open_capacity_report_all, None),
            ("FC WWPN", self._open_fc_wwpn_report_all, None),
            ("Site Lookup", self._open_site_lookup_all, None),
            ("Ansible Pad", self._open_ansible_pad, None),
            ("Host Power", self._open_host_power, None),
            ("Consistency Groups", self._open_contingency_groups, None),
            ("FlashCopy CGs", self._open_fc_consistgrp, None),
            ("ESX-snap Policy", self._open_esx_snap_policy, None),
            ("LUN Builder", self._open_lun_builder, None),
            ("Host / Volume Find", self._open_volume_find, None),
            ("Hosts & Volumes", self._open_host_volume_health, None),
            ("System Connectivity", self._open_system_connectivity, None),
            ("Storage Inventory", self._open_storage_inventory, None),
            ("Export Excel ▾", self._open_export_excel_menu, 140),
            ("Refresh Stats", self._fetch_all_ssh_stats, None),
        ]
        for index, (text, command, width) in enumerate(tool_specs):
            kwargs = {
                "text": text,
                "fg_color": self.theme["surface_alt"],
                "hover_color": self.theme["border"],
                "command": command,
            }
            if width is not None:
                kwargs["width"] = width
            btn = ctk.CTkButton(tools, **kwargs)
            row, col = divmod(index, HEADER_TOOLS_PER_ROW)
            btn.grid(row=row, column=col, padx=6, pady=(0, 6), sticky="w")
            if text.startswith("Export Excel"):
                self.export_excel_btn = btn

        self.capacity_alert_strip = ctk.CTkFrame(
            header,
            fg_color="#7f1d1d",
            corner_radius=10,
            border_width=1,
            border_color="#ef4444",
        )
        self.capacity_alert_strip.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.capacity_alert_strip.grid_columnconfigure(0, weight=1)
        self.capacity_alert_label = ctk.CTkLabel(
            self.capacity_alert_strip,
            text="",
            text_color="#fecaca",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        self.capacity_alert_label.grid(row=0, column=0, padx=12, pady=8, sticky="ew")
        self.capacity_alert_btn = ctk.CTkButton(
            self.capacity_alert_strip,
            text="Open Capacity Report",
            width=170,
            fg_color="#ef4444",
            hover_color="#dc2626",
            command=self._open_capacity_report_all,
        )
        self.capacity_alert_btn.grid(row=0, column=1, padx=12, pady=8)
        self.capacity_alert_strip.grid_remove()

    def _build_filters(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 8))
        bar.grid_columnconfigure(1, weight=1)

        self.category_var = ctk.StringVar(value="All")
        self.category_menu = ctk.CTkOptionMenu(
            bar,
            variable=self.category_var,
            values=self.db.list_categories(),
            command=lambda _v: self.refresh_cards(),
            width=160,
        )
        self.category_menu.grid(row=0, column=0, padx=(0, 12))

        self.search_entry = ctk.CTkEntry(bar, placeholder_text="Search cards...")
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.search_entry.bind("<KeyRelease>", lambda _e: self._filter_visible_cards())

        bulk = ctk.CTkFrame(bar, fg_color="transparent")
        bulk.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        bulk.grid_columnconfigure(0, weight=1)

        # Row 0: toggles + selection count (keeps the button row from overflowing).
        toggles = ctk.CTkFrame(bulk, fg_color="transparent")
        toggles.grid(row=0, column=0, sticky="ew")
        toggles.grid_columnconfigure(3, weight=1)

        self.compact_switch = ctk.CTkSwitch(
            toggles,
            text="Compact cards",
            command=self._toggle_compact_cards,
        )
        if self._cards_compact:
            self.compact_switch.select()
        self.compact_switch.grid(row=0, column=0, padx=(0, 12))

        self.monitor_all_switch = ctk.CTkSwitch(
            toggles,
            text="All monitoring on",
            command=self._toggle_all_monitoring,
        )
        self.monitor_all_switch.grid(row=0, column=1, padx=(0, 12))

        self.mouse_jiggler_switch = ctk.CTkSwitch(
            toggles,
            text="Mouse jiggler",
            command=self._toggle_mouse_jiggler,
        )
        if self._mouse_jiggler_enabled:
            self.mouse_jiggler_switch.select()
        self.mouse_jiggler_switch.grid(row=0, column=2, padx=(0, 12))

        self.selection_label = ctk.CTkLabel(
            toggles,
            text="0 selected",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=12),
        )
        self.selection_label.grid(row=0, column=3, padx=(12, 0), sticky="e")

        # Row 1: bulk action buttons (own line so Expand/Collapse stay on-screen).
        actions = ctk.CTkFrame(bulk, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="w", pady=(8, 0))

        ctk.CTkButton(
            actions,
            text="Select All",
            width=90,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._select_all_cards,
        ).grid(row=0, column=0, padx=(0, 4))

        ctk.CTkButton(
            actions,
            text="Clear",
            width=70,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._clear_card_selection,
        ).grid(row=0, column=1, padx=4)

        ctk.CTkButton(
            actions,
            text="Monitor Checked",
            width=125,
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_soft"],
            command=lambda: self._set_checked_monitoring(True),
        ).grid(row=0, column=2, padx=4)

        ctk.CTkButton(
            actions,
            text="Unmonitor Checked",
            width=135,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=lambda: self._set_checked_monitoring(False),
        ).grid(row=0, column=3, padx=4)

        ctk.CTkButton(
            actions,
            text="Open Checked",
            width=110,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._open_checked_cards,
        ).grid(row=0, column=4, padx=4)

        ctk.CTkButton(
            actions,
            text="Open All",
            width=90,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._open_all_visible_cards,
        ).grid(row=0, column=5, padx=4)

        ctk.CTkButton(
            actions,
            text="Expand Checked",
            width=115,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._expand_checked_cards,
        ).grid(row=0, column=6, padx=4)

        ctk.CTkButton(
            actions,
            text="Expand All",
            width=90,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=lambda: self._set_all_cards_collapsed(False),
        ).grid(row=0, column=7, padx=4)

        ctk.CTkButton(
            actions,
            text="Collapse All",
            width=100,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=lambda: self._set_all_cards_collapsed(True),
        ).grid(row=0, column=8, padx=4)

    def _toggle_theme(self) -> None:
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.db.set_setting("theme", self.theme_name)
        if hasattr(self.master, "apply_theme"):
            self.master.apply_theme(self.theme_name)

    def _capacity_unit_switch_label(self) -> str:
        return "GB/TB" if get_capacity_unit_mode() == "si" else "GiB/TiB"

    def _toggle_capacity_unit_mode(self) -> None:
        mode = "si" if bool(self.capacity_unit_switch.get()) else "iec"
        set_capacity_unit_mode(mode)
        self.db.set_setting(SETTING_CAPACITY_UNIT_MODE, mode)
        self.capacity_unit_switch.configure(text=self._capacity_unit_switch_label())
        self._reformat_visible_card_stats()

    def _reformat_visible_card_stats(self) -> None:
        try:
            cards = get_health_server().list_cards(allow_sync=False)
        except Exception:
            return

        for card in cards:
            if card.get("card_type") != "ssh":
                continue
            results = card.get("command_results")
            widget = self._find_card_widget(card["id"])
            if not widget:
                continue
            if results:
                left, right = command_results_columns(results)
            else:
                metrics = card.get("metrics")
                if not metrics:
                    continue
                left, right = card_stats_columns(metrics)
            widget.set_stats(left, right)

    def apply_theme(self, theme_name: str) -> None:
        self.theme_name = theme_name
        self.theme = get_theme(theme_name)
        self.configure(fg_color=self.theme["bg"])
        if isinstance(self.master, ctk.CTk):
            self.master.configure(fg_color=self.theme["bg"])
        self.cards_frame.configure(fg_color=self.theme["surface"])
        if hasattr(self, "rail_frame"):
            self.rail_frame.configure(fg_color=self.theme["surface"])
        if hasattr(self, "array_rail_title"):
            self.array_rail_title.configure(text_color=self.theme["text"])
        if hasattr(self, "array_rail_toggle"):
            self.array_rail_toggle.configure(
                fg_color=self.theme["surface_alt"],
                hover_color=self.theme["border"],
            )
        self.theme_switch.configure(text="Light mode" if theme_name == "dark" else "Dark mode")
        if hasattr(self, "capacity_unit_switch"):
            self.capacity_unit_switch.configure(text=self._capacity_unit_switch_label())
        if hasattr(self, "export_excel_btn"):
            self.export_excel_btn.configure(
                fg_color=self.theme["surface_alt"],
                hover_color=self.theme["border"],
            )
        self.status_label.configure(text_color=self.theme["muted"])
        if hasattr(self, "report_url_entry"):
            self.report_url_entry.configure(
                fg_color=self.theme["surface_alt"],
                border_color=self.theme["border"],
                text_color=self.theme["text"],
            )
        if hasattr(self, "copy_url_btn"):
            self.copy_url_btn.configure(
                fg_color=self.theme["surface_alt"],
                hover_color=self.theme["border"],
            )
        for card in self.card_widgets:
            card.apply_theme(self.theme)
        self.refresh_cards()

    def _set_status(self, text: str, *, url: str | None = None) -> None:
        self.status_label.configure(text=text)
        if url:
            self.report_url_var.set(url)
            self.report_url_entry.grid()
            self.copy_url_btn.grid()
        else:
            self.report_url_var.set("")
            self.report_url_entry.grid_remove()
            self.copy_url_btn.grid_remove()

    def _copy_report_url(self) -> None:
        url = (self.report_url_var.get() or "").strip()
        if not url:
            self.status_label.configure(text="No report URL to copy.")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(url)
            self.update_idletasks()
            self.status_label.configure(text=f"Copied URL to clipboard: {url}")
        except Exception as exc:
            self.status_label.configure(text=f"Could not copy URL: {exc}")

    def _filter_visible_cards(self) -> None:
        query = self.search_entry.get() if hasattr(self, "search_entry") else ""
        cards = [
            self._visible_cards[widget.card_id]
            for widget in self.card_widgets
            if widget.card_id in self._visible_cards
        ]
        filtered = filter_dashboard_cards(cards, query=query)
        match_ids = {card.id for card in filtered}
        index = 0
        cols = self._card_columns
        for widget in self.card_widgets:
            if widget.card_id in match_ids:
                row, col = divmod(index, cols)
                widget.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
                index += 1
            else:
                widget.grid_remove()
        self._rebuild_array_rail(filtered)
        self._update_selection_status()

    def refresh_cards(self) -> None:
        if self._stats_timer:
            self.after_cancel(self._stats_timer)
            self._stats_timer = None
        if self._ssh_status_timer:
            self.after_cancel(self._ssh_status_timer)
            self._ssh_status_timer = None
        if self._capacity_alert_timer:
            self.after_cancel(self._capacity_alert_timer)
            self._capacity_alert_timer = None
        if self._health_alert_timer:
            self.after_cancel(self._health_alert_timer)
            self._health_alert_timer = None

        for widget in self.cards_frame.winfo_children():
            widget.destroy()
        self.card_widgets.clear()
        self._ssh_cards.clear()
        self._visible_cards.clear()

        cols = 4
        self._card_columns = cols
        for col in range(cols):
            self.cards_frame.grid_columnconfigure(col, weight=1)

        query = self.search_entry.get() if hasattr(self, "search_entry") else ""
        category = self.category_var.get() if hasattr(self, "category_var") else "All"
        cards = self.db.list_cards(None if category == "All" else category)

        filtered = filter_dashboard_cards(cards, query=query)
        self._rebuild_array_rail(filtered)

        can_reorder = category == "All" and not query.strip()
        self.hint_label.configure(
            text=(
                "SSH monitoring is off by default — check cards and click Monitor Checked, "
                "or use All monitoring on"
                if any(card.card_type == "ssh" for card in filtered)
                else (
                    "Check sites to open SSH or expand cards · ▶ opens one card · Expand Checked for several"
                    if can_reorder and filtered
                    else ("Check sites, then Open Checked or Expand Checked" if filtered else "")
                )
            )
        )

        if not filtered:
            ctk.CTkLabel(
                self.cards_frame,
                text="No cards yet. Open Admin to add SSH, RDP, or Web connections.",
                text_color=self.theme["muted"],
                font=ctk.CTkFont(size=14),
            ).grid(row=0, column=0, columnspan=cols, padx=12, pady=24, sticky="w")
            self._refresh_capacity_alerts()
            self._schedule_capacity_alert_poll()
            self._refresh_health_alerts()
            self._schedule_health_alert_poll()
            return

        self._load_monitor_states()
        dell_include_ids = set(
            load_dell_report_settings(self.db).get("include_card_ids") or []
        )

        visible_ids = {card.id for card in filtered}
        self._expanded_card_ids &= visible_ids
        if not self._cards_compact and not self._expanded_card_ids and filtered:
            self._expanded_card_ids = visible_ids.copy()
            self._save_expanded_card_ids()

        for index, card in enumerate(filtered):
            row, col = divmod(index, cols)
            subtitle = self._card_subtitle(card)
            start_collapsed = card.id not in self._expanded_card_ids
            show_dell_include = (
                card.card_type == "ssh"
                and dell_report_family(getattr(card, "device_profile", "") or "")
                in {"ibm", "hp"}
            )
            try:
                widget = GlowCard(
                    self.cards_frame,
                    theme=self.theme,
                    name=card.name,
                    card_type=card.card_type,
                    subtitle=subtitle,
                    glow_color=card.glow_color,
                    icon=card.icon,
                    card_id=card.id,
                    on_click=lambda c=card: self._launch_card(c),
                    on_health=(lambda c=card: self._monitor_card(c)) if card.card_type == "ssh" else None,
                    on_snapshot=(lambda c=card: self._snapshot_card(c)) if card.card_type == "ssh" else None,
                    **(
                        {
                            "on_power_off": (
                                lambda cid=card.id: self._open_host_power(card_id=cid)
                            )
                        }
                        if card.card_type == "ssh" and card.device_profile == "hadoop_linux"
                        else {}
                    ),
                    on_monitor_change=(
                        (lambda enabled, c=card: self._on_card_monitor_toggle(c, enabled))
                        if card.card_type == "ssh"
                        else None
                    ),
                    monitor_enabled=self._is_monitor_on(card.id),
                    show_stats=card.card_type == "ssh",
                    on_reorder=self._reorder_cards if can_reorder else None,
                    draggable=can_reorder,
                    dashboard=self,
                    collapsed=start_collapsed,
                    on_selection_change=self._update_selection_status,
                    on_collapsed_change=self._on_card_collapsed_change,
                    show_dell_report_include=show_dell_include,
                    dell_report_include=str(card.id) in dell_include_ids,
                    on_dell_report_include_change=(
                        (
                            lambda enabled, c=card: self._set_dell_report_include(
                                c.id, enabled
                            )
                        )
                        if show_dell_include
                        else None
                    ),
                )
            except Exception as exc:
                self.status_label.configure(text=f"Could not render card '{card.name}': {exc}")
                continue
            widget.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            self.card_widgets.append(widget)
            self._visible_cards[card.id] = card
            if card.card_type == "ssh":
                self._ssh_cards.append(card)
                if not self._is_monitor_on(card.id):
                    widget.set_ssh_status("off")

        self._update_selection_status()
        self._sync_master_monitor_switch()
        self._probe_monitored_ssh_status()
        self._refresh_capacity_alerts()
        self._schedule_capacity_alert_poll()
        self._refresh_health_alerts()
        self._schedule_health_alert_poll()

        # SSH stats run only when Monitor is on and you click Refresh Stats.

    def _schedule_capacity_alert_poll(self) -> None:
        if self._capacity_alert_timer:
            self.after_cancel(self._capacity_alert_timer)
        from launchpad.dashboard_capacity_alerts import CAPACITY_ALERT_POLL_MS
        self._capacity_alert_timer = self.after(
            CAPACITY_ALERT_POLL_MS, self._on_capacity_alert_timer
        )

    def _on_capacity_alert_timer(self) -> None:
        self._capacity_alert_timer = None
        self._refresh_capacity_alerts()
        self._schedule_capacity_alert_poll()

    def _refresh_capacity_alerts(self) -> None:
        from launchpad.dashboard_capacity_alerts import (
            card_capacity_severity,
            filter_capacity_issues,
            fleet_capacity_alert_summary,
        )
        from launchpad.health_server import get_health_server

        try:
            server = get_health_server()
            cards = server.list_cards(allow_sync=False)
        except Exception:
            cards = []
        monitor_states = dict(self._monitor_states)
        summary = fleet_capacity_alert_summary(cards, monitor_states)
        by_id = {int(c.get("id")): c for c in cards if c.get("id") is not None}

        if summary["has_alert"]:
            critical = summary["critical_sites"] > 0
            self.capacity_alert_strip.configure(
                fg_color="#7f1d1d" if critical else "#78350f",
                border_color="#ef4444" if critical else "#f59e0b",
            )
            self.capacity_alert_label.configure(
                text=summary["label"],
                text_color="#fecaca" if critical else "#fde68a",
            )
            self.capacity_alert_btn.configure(
                fg_color="#ef4444" if critical else "#f59e0b",
                hover_color="#dc2626" if critical else "#d97706",
                text_color="#ffffff" if critical else "#111111",
            )
            self.capacity_alert_strip.grid()
        else:
            self.capacity_alert_strip.grid_remove()

        for widget in self.card_widgets:
            payload = by_id.get(widget.card_id)
            if not payload:
                widget.set_capacity_alert(None)
                continue
            severity = card_capacity_severity(
                payload.get("health_issues"),
                monitor_on=self._is_monitor_on(widget.card_id),
                updated_at=payload.get("updated_at"),
            )
            messages = [
                str(i.get("message") or "")
                for i in filter_capacity_issues(payload.get("health_issues"))
            ]
            widget.set_capacity_alert(severity, messages)

    @staticmethod
    def _same_health_alert_card_id(left, right) -> bool:
        return same_health_alert_card_id(left, right)

    def _force_close_health_alert_dialog(self) -> None:
        dialog = self._health_alert_dialog
        self._health_alert_dialog = None
        if dialog is None:
            return
        try:
            dialog.withdraw()
        except Exception:
            pass
        try:
            dialog.destroy()
        except Exception:
            pass

    def _finish_health_alert_dialog(
        self,
        dialog,
        *,
        advance_queue: bool,
        payload: dict | None = None,
    ) -> None:
        if dialog is not None and self._health_alert_dialog is dialog:
            self._health_alert_dialog = None
        elif dialog is None:
            self._health_alert_dialog = None
        if dialog is not None:
            try:
                dialog.withdraw()
            except Exception:
                pass
            try:
                dialog.destroy()
            except Exception:
                pass
        if payload is not None:
            # Defer so Tk can finish tearing down the previous toplevel before
            # opening the next card's dialog (prevents stacked orphan windows).
            self.after(50, lambda p=payload: self._apply_health_alert_payload(p))
            return
        if advance_queue:
            self._health_alert_queue_index += 1
            self.after(50, self._show_next_health_alert)

    def _schedule_health_alert_poll(self) -> None:
        if self._health_alert_timer:
            self.after_cancel(self._health_alert_timer)

        self._health_alert_timer = self.after(
            HEALTH_ALERT_POLL_MS, self._on_health_alert_timer
        )

    def _on_health_alert_timer(self) -> None:
        self._health_alert_timer = None
        self._refresh_health_alerts()
        self._schedule_health_alert_poll()

    def _refresh_health_alerts(self) -> None:
        if self._health_alert_poll_in_flight:
            return
        self._health_alert_poll_in_flight = True
        try:
            server = get_health_server()
            payload = server.get_health_alerts()
        except Exception:
            return
        finally:
            self._health_alert_poll_in_flight = False
        self._apply_health_alert_payload(payload)

    def _apply_health_alert_payload(self, payload: dict) -> None:
        alerts = payload.get("alerts") or []
        active_fingerprints = {
            str(alert.get("fingerprint"))
            for alert in alerts
            if alert.get("fingerprint") is not None
        }
        self._health_alert_beeped &= active_fingerprints
        beeped_this_poll = False
        for alert in alerts:
            fingerprint = str(alert.get("fingerprint") or "")
            if not fingerprint or fingerprint in self._health_alert_beeped:
                continue
            if not beeped_this_poll:
                play_health_alert_beep()
                beeped_this_poll = True
            self._health_alert_beeped.add(fingerprint)

        self._health_alert_cards_meta = payload.get("cards") or {}
        self._sync_health_alarm_muted_indicators()
        groups = group_health_alerts(alerts)
        self._sync_health_alert_overlays(groups)

        if self._health_alert_dialog is not None:
            return

        self._health_alert_queue = groups
        self._health_alert_queue_index = 0
        self._show_next_health_alert()

    @staticmethod
    def _health_alert_group_key(group: dict) -> str:
        return "\x1f".join(
            sorted(
                str(issue.get("fingerprint") or issue.get("message") or "")
                for issue in group.get("issues") or []
            )
        )

    def _dismiss_health_alert_overlay(self, widget, group_key: str) -> None:
        # Remember the dismissal so the next poll does not immediately re-raise the
        # same overlay; a new fingerprint set clears it.
        self._health_alert_overlay_dismissed[widget.card_id] = group_key
        widget.clear_health_alert_overlay()

    def _sync_health_alert_overlays(self, groups: list[dict]) -> None:
        by_card_id = {
            int(group.get("card_id")): group
            for group in groups
            if group.get("card_id") is not None
        }
        for widget in self.card_widgets:
            group = by_card_id.get(widget.card_id)
            if group is None:
                self._health_alert_overlay_dismissed.pop(widget.card_id, None)
                widget.clear_health_alert_overlay()
                continue
            group_key = self._health_alert_group_key(group)
            if self._health_alert_overlay_dismissed.get(widget.card_id) == group_key:
                widget.clear_health_alert_overlay()
                continue
            self._health_alert_overlay_dismissed.pop(widget.card_id, None)
            widget.set_health_alert_overlay(
                group,
                on_acknowledge=(
                    lambda alert_group=group: self._acknowledge_health_alert_group(alert_group)
                ),
                on_pause=(
                    lambda minutes, card_id=widget.card_id: self._pause_health_alert_card(
                        card_id, minutes
                    )
                ),
                on_alarm_toggle=(
                    lambda card_id=widget.card_id: self._toggle_health_alarm_for_card(card_id)
                ),
                on_close=(
                    lambda card_widget=widget, key=group_key: (
                        self._dismiss_health_alert_overlay(card_widget, key)
                    )
                ),
                alarm_muted=self._card_alarm_muted(widget.card_id),
            )

    def _sync_health_alarm_muted_indicators(self) -> None:
        for widget in self.card_widgets:
            meta = self._health_alert_cards_meta.get(str(widget.card_id), {})
            muted = bool(meta.get("alarm_muted"))
            widget.set_health_alarm_muted(
                muted,
                on_toggle=(
                    lambda cid=widget.card_id: self._toggle_health_alarm_for_card(cid)
                ),
            )

    def _card_alarm_muted(self, card_id: int) -> bool:
        meta = self._health_alert_cards_meta.get(str(card_id), {})
        return bool(meta.get("alarm_muted"))

    def _show_next_health_alert(self) -> None:
        while self._health_alert_queue_index < len(self._health_alert_queue):
            group = self._health_alert_queue[self._health_alert_queue_index]
            if group.get("issues"):
                self._open_health_alert_dialog(group)
                return
            self._health_alert_queue_index += 1

    def _open_health_alert_dialog(self, group: dict) -> None:
        # Always tear down any prior toplevel first so a failed destroy / stale
        # reference cannot leave multiple Critical Health Alert windows stacked.
        self._force_close_health_alert_dialog()
        holder: dict[str, Any] = {"dialog": None}

        def on_acknowledge() -> None:
            dialog = holder["dialog"]
            if dialog is None:
                return
            self._acknowledge_health_alert_group(dialog.group, dialog=dialog)

        def on_pause(minutes: int) -> None:
            dialog = holder["dialog"]
            if dialog is None:
                return
            card_id = dialog.group.get("card_id")
            if card_id is None:
                return
            self._pause_health_alert_card(card_id, minutes, dialog=dialog)

        def on_alarm_toggle() -> None:
            dialog = holder["dialog"]
            if dialog is None:
                return
            card_id = dialog.group.get("card_id")
            if card_id is None:
                return
            self._toggle_health_alarm_for_card(card_id, dialog=dialog)

        def on_close(advance_queue: bool) -> None:
            dialog = holder["dialog"]
            self._finish_health_alert_dialog(dialog, advance_queue=advance_queue)

        dialog = HealthAlertDialog(
            self.winfo_toplevel(),
            theme_name=self.theme_name,
            group=group,
            on_acknowledge=on_acknowledge,
            on_pause=on_pause,
            on_alarm_toggle=on_alarm_toggle,
            on_close=on_close,
            alarm_muted=self._card_alarm_muted(int(group.get("card_id") or 0)),
        )
        holder["dialog"] = dialog
        self._health_alert_dialog = dialog

    def _close_health_alert_dialog(self, *, advance_queue: bool) -> None:
        self._finish_health_alert_dialog(
            self._health_alert_dialog,
            advance_queue=advance_queue,
        )

    def _on_health_alert_close(self, advance_queue: bool) -> None:
        self._close_health_alert_dialog(advance_queue=advance_queue)

    def _on_health_alert_acknowledge(self) -> None:
        dialog = self._health_alert_dialog
        if dialog is None:
            return
        self._acknowledge_health_alert_group(dialog.group, dialog=dialog)

    def _acknowledge_health_alert_group(self, group: dict, *, dialog=None) -> None:
        fingerprints = [
            str(issue.get("fingerprint") or "")
            for issue in group.get("issues") or []
            if issue.get("fingerprint") is not None
        ]
        if not fingerprints:
            if dialog is not None:
                self._finish_health_alert_dialog(dialog, advance_queue=False)
            return
        try:
            server = get_health_server()
            payload = server.acknowledge_health_alerts(fingerprints)
        except Exception as exc:
            self.status_label.configure(text=f"Could not acknowledge health alert: {exc}")
            return
        target = dialog if dialog is not None else self._health_alert_dialog
        if target is not None and self._same_health_alert_card_id(
            target.group.get("card_id"), group.get("card_id")
        ):
            self._finish_health_alert_dialog(
                target, advance_queue=False, payload=payload
            )
        else:
            self._close_matching_health_alert_dialog(group.get("card_id"))
            self._apply_health_alert_payload(payload)

    def _on_health_alert_pause(self, minutes: int) -> None:
        dialog = self._health_alert_dialog
        if dialog is None:
            return
        card_id = dialog.group.get("card_id")
        if card_id is None:
            return
        self._pause_health_alert_card(card_id, minutes, dialog=dialog)

    def _pause_health_alert_card(self, card_id, minutes: int, *, dialog=None) -> None:
        try:
            server = get_health_server()
            payload = server.pause_health_alert(int(card_id), int(minutes))
        except Exception as exc:
            self.status_label.configure(text=f"Could not pause health alert: {exc}")
            return
        target = dialog if dialog is not None else self._health_alert_dialog
        if target is not None and self._same_health_alert_card_id(
            target.group.get("card_id"), card_id
        ):
            self._finish_health_alert_dialog(
                target, advance_queue=False, payload=payload
            )
        else:
            self._close_matching_health_alert_dialog(card_id)
            self._apply_health_alert_payload(payload)

    def _on_health_alert_alarm_toggle(self) -> None:
        dialog = self._health_alert_dialog
        if dialog is None:
            return
        card_id = dialog.group.get("card_id")
        if card_id is None:
            return
        self._toggle_health_alarm_for_card(card_id, dialog=dialog)

    def _toggle_health_alarm_for_card(self, card_id, *, dialog=None) -> None:
        muted = not self._card_alarm_muted(int(card_id))
        self._set_health_alarm(card_id, muted, close_dialog=True, dialog=dialog)

    def _close_matching_health_alert_dialog(self, card_id) -> None:
        dialog = self._health_alert_dialog
        if dialog is None:
            return
        if self._same_health_alert_card_id(dialog.group.get("card_id"), card_id):
            self._finish_health_alert_dialog(dialog, advance_queue=False)

    def _on_card_health_alarm_on(self, card_id: int) -> None:
        self._set_health_alarm(card_id, False, close_dialog=False)

    def _set_health_alarm(
        self, card_id, muted: bool, *, close_dialog: bool, dialog=None
    ) -> None:
        try:
            server = get_health_server()
            payload = server.set_health_alarm(int(card_id), muted)
        except Exception as exc:
            action = "mute" if muted else "restore"
            self.status_label.configure(text=f"Could not {action} health alarm: {exc}")
            return
        if close_dialog:
            target = dialog if dialog is not None else self._health_alert_dialog
            if target is not None and self._same_health_alert_card_id(
                target.group.get("card_id"), card_id
            ):
                self._finish_health_alert_dialog(
                    target, advance_queue=False, payload=payload
                )
                return
            self._close_matching_health_alert_dialog(card_id)
        self._apply_health_alert_payload(payload)

    def _apply_array_rail_collapsed(self) -> None:
        if self.array_rail_collapsed:
            self.rail_frame.configure(width=44)
            self.array_rail_title.pack_forget()
            self.array_rail_list.pack_forget()
            self.array_rail_toggle.configure(text="»")
        else:
            self.rail_frame.configure(width=220)
            self.array_rail_title.pack(side="left")
            self.array_rail_list.pack(fill="both", expand=True, padx=4, pady=(0, 8))
            self.array_rail_toggle.configure(text="«")

    def _toggle_array_rail(self) -> None:
        self.array_rail_collapsed = not self.array_rail_collapsed
        self.db.set_setting(
            SETTING_ARRAY_RAIL_COLLAPSED,
            setting_from_collapsed(self.array_rail_collapsed),
        )
        self._apply_array_rail_collapsed()
        if not self.array_rail_collapsed:
            query = self.search_entry.get() if hasattr(self, "search_entry") else ""
            category = self.category_var.get() if hasattr(self, "category_var") else "All"
            cards = self.db.list_cards(None if category == "All" else category)
            filtered = filter_dashboard_cards(cards, query=query)
            self._rebuild_array_rail(filtered)

    def _rebuild_array_rail(self, filtered: list[Card]) -> None:
        for widget in self.array_rail_list.winfo_children():
            widget.destroy()

        if self.array_rail_collapsed:
            self.array_rail_toggle.configure(text="»")
            return

        self.array_rail_toggle.configure(text="«")

        if not filtered:
            ctk.CTkLabel(
                self.array_rail_list,
                text="No arrays match.",
                text_color=self.theme["muted"],
                font=ctk.CTkFont(size=12),
                wraplength=180,
                justify="left",
            ).pack(fill="x", padx=4, pady=8)
            return

        for card in filtered:
            title = rail_row_title(card)
            subtitle = rail_row_subtitle(card)
            enabled = can_open_rail_gui(card)
            btn = ctk.CTkButton(
                self.array_rail_list,
                text=f"{title}\n{subtitle}",
                anchor="w",
                fg_color=self.theme["surface_alt"] if enabled else "transparent",
                hover_color=self.theme["border"] if enabled else "transparent",
                text_color=self.theme["text"] if enabled else self.theme["muted"],
                command=(lambda c=card: self._open_array_gui(c)) if enabled else None,
                state="normal" if enabled else "disabled",
            )
            btn.pack(fill="x", padx=4, pady=2)

    def _open_array_gui(self, card: Card) -> None:
        try:
            message = open_rail_gui(card)
            self._set_status(f"{card.name}: {message}")
        except ValueError as exc:
            self._set_status(str(exc))

    def _schedule_ssh_status_checks(self) -> None:
        if self._ssh_status_timer:
            self.after_cancel(self._ssh_status_timer)
        self._ssh_status_timer = self.after(SSH_STATUS_INTERVAL_MS, self._on_ssh_status_timer)

    def _on_ssh_status_timer(self) -> None:
        self._ssh_status_timer = None
        self._probe_all_ssh_status()
        self._schedule_ssh_status_checks()

    def _schedule_capacity_email_timer(self) -> None:
        if self._capacity_email_timer:
            self.after_cancel(self._capacity_email_timer)
        self._capacity_email_timer = self.after(
            CAPACITY_EMAIL_POLL_MS, self._on_capacity_email_timer
        )

    def _on_capacity_email_timer(self) -> None:
        self._capacity_email_timer = None
        self._check_capacity_email_due()
        self._schedule_capacity_email_timer()

    def _check_capacity_email_due(self) -> None:
        if self._capacity_email_send_in_flight:
            return
        try:
            settings = load_capacity_email_settings(self.db)
        except Exception:
            return
        if not is_capacity_email_due(settings):
            return
        self._run_capacity_email_send(settings, source="Scheduled")

    def _email_capacity_now(self) -> None:
        if self._capacity_email_send_in_flight:
            self.status_label.configure(text="Capacity email already sending...")
            return
        settings = load_capacity_email_settings(self.db)
        self._run_capacity_email_send(settings, source="Manual")

    def _run_capacity_email_send(self, settings: dict, *, source: str) -> None:
        self._capacity_email_send_in_flight = True
        self.status_label.configure(text=f"{source} capacity email sending...")

        def progress(name: str, index: int, total: int) -> None:
            self.after(
                0,
                lambda: self.status_label.configure(
                    text=f"{source} capacity email ({index}/{total}): {name}..."
                ),
            )

        def worker() -> None:
            try:
                result = send_capacity_email(
                    self.db, self.crypto_key, settings, progress=progress
                )
            except Exception as exc:
                result = {"ok": False, "settings": None, "path": "", "error": str(exc)}
            self.after(0, lambda: self._on_capacity_email_send_done(result, source=source))

        threading.Thread(target=worker, daemon=True).start()

    def _on_capacity_email_send_done(self, result: dict, *, source: str) -> None:
        self._capacity_email_send_in_flight = False
        if result.get("ok"):
            text = f"{source} capacity email sent."
            _log(text)
        else:
            text = f"{source} capacity email failed: {result.get('error', '')}"
            _log(text)
        self.status_label.configure(text=text)

    def _probe_all_ssh_status(self) -> None:
        cards = [card for card in self._ssh_cards if card.card_type == "ssh"]
        if not cards:
            cards = [card for card in self.db.list_cards() if card.card_type == "ssh"]
        for card in cards:
            if not self._is_monitor_on(card.id):
                self._set_card_ssh_monitor_off(card.id)
                continue
            widget = self._find_card_widget(card.id)
            if widget:
                widget.set_ssh_status("checking")
            if card.id in self._ssh_status_in_flight:
                continue
            threading.Thread(
                target=self._probe_ssh_status_worker,
                args=(card.id,),
                daemon=True,
            ).start()

    def _probe_ssh_status_worker(self, card_id: int) -> None:
        if card_id in self._ssh_status_in_flight:
            return
        self._ssh_status_in_flight.add(card_id)
        try:
            card = self._visible_cards.get(card_id) or self.db.get_card(card_id)
            if not card:
                return
            status, message = probe_ssh_login_for_card(card, self.crypto_key)
            self.after(
                0,
                lambda cid=card_id, s=status, m=message: self._apply_ssh_status(cid, s, m),
            )
        finally:
            self._ssh_status_in_flight.discard(card_id)

    def _set_card_ssh_monitor_off(self, card_id: int) -> None:
        widget = self._find_card_widget(card_id)
        if widget:
            widget.set_ssh_status("off")

    def _apply_ssh_status(self, card_id: int, status: str, message: str) -> None:
        if not self._is_monitor_on(card_id):
            status = "off"
            message = ""
        widget = self._find_card_widget(card_id)
        if widget:
            widget.set_ssh_status(status, message)

    def _load_monitor_states(self) -> None:
        try:
            self._monitor_states = get_monitor_states()
        except Exception as exc:
            _log(f"Could not load monitor states: {exc}")
            self._monitor_states = {}

    def _is_monitor_on(self, card_id: int) -> bool:
        return bool(self._monitor_states.get(card_id, False))

    def _sync_master_monitor_switch(self) -> None:
        if not hasattr(self, "monitor_all_switch"):
            return
        ssh_ids = [card.id for card in self._ssh_cards]
        if not ssh_ids:
            self.monitor_all_switch.deselect()
            return
        all_on = all(self._is_monitor_on(card_id) for card_id in ssh_ids)
        if all_on:
            self.monitor_all_switch.select()
        else:
            self.monitor_all_switch.deselect()

    def _on_card_monitor_toggle(self, card: Card, enabled: bool) -> None:
        try:
            set_card_monitor_enabled(card.id, enabled)
            self._monitor_states[card.id] = enabled
        except Exception as exc:
            _log(f"Monitor toggle failed for {card.name}: {exc}")
            self.status_label.configure(text=f"Monitor toggle failed: {exc}")
            widget = self._find_card_widget(card.id)
            if widget:
                widget.set_monitor_enabled(not enabled)
            return

        widget = self._find_card_widget(card.id)
        if widget:
            widget.set_monitor_enabled(enabled)
        self._sync_master_monitor_switch()
        self._refresh_capacity_alerts()
        if enabled:
            self.status_label.configure(text=f"Monitoring on for {card.name} — refreshing stats...")
            self._probe_card_ssh_status(card.id)
            threading.Thread(target=self._fetch_ssh_stats_worker, args=(card,), daemon=True).start()
        else:
            self.status_label.configure(text=f"Monitoring off for {card.name} — no background SSH.")
            self._set_card_ssh_monitor_off(card.id)

    def _set_dell_report_include(self, card_id: int, enabled: bool) -> None:
        settings = load_dell_report_settings(self.db)
        ids = list(settings.get("include_card_ids") or [])
        key = str(card_id)
        if enabled and key not in ids:
            ids.append(key)
        if not enabled:
            ids = [x for x in ids if x != key]
        settings["include_card_ids"] = ids
        save_dell_report_settings(self.db, settings)
        widget = self._find_card_widget(card_id)
        if widget is not None and hasattr(widget, "set_dell_report_include"):
            widget.set_dell_report_include(enabled)

    def _toggle_all_monitoring(self) -> None:
        enabled = bool(self.monitor_all_switch.get())
        ssh_cards = list(self._ssh_cards)
        for card in ssh_cards:
            self._monitor_states[card.id] = enabled
            widget = self._find_card_widget(card.id)
            if widget:
                widget.set_monitor_enabled(enabled)
        self._refresh_capacity_alerts()
        if enabled:
            self.status_label.configure(text="All monitoring on — refreshing stats for SSH cards...")
        else:
            self.status_label.configure(text="All monitoring off — no background SSH.")
            for card in ssh_cards:
                self._set_card_ssh_monitor_off(card.id)

        def start_ssh_stats(card: Card) -> None:
            if card.id not in self._stats_in_flight:
                threading.Thread(
                    target=self._fetch_ssh_stats_worker,
                    args=(card,),
                    daemon=True,
                ).start()

        def worker() -> None:
            try:
                ensure_health_dashboard_registered(self.db, self.crypto_key)
                set_all_monitor_enabled(enabled)
            except Exception as exc:
                self.after(0, lambda msg=str(exc): self.status_label.configure(text=f"Monitor toggle failed: {msg}"))
                self.after(0, self._sync_master_monitor_switch)
                return
            if not enabled:
                return
            for card in ssh_cards:
                self.after(0, lambda c=card: self._probe_card_ssh_status(c.id))
                start_ssh_stats(card)

        threading.Thread(target=worker, daemon=True).start()

    def _ssh_stats_prereq(self, card: Card) -> str | None:
        return ssh_stats_prereq_message(card, self.crypto_key)

    def _fetch_all_ssh_stats(self) -> None:
        if not self._ssh_cards:
            self._ssh_cards = [card for card in self.db.list_cards() if card.card_type == "ssh"]
        if not self._ssh_cards:
            self.status_label.configure(text="No SSH cards to refresh.")
            return

        fetchable: list[Card] = []
        for card in self._ssh_cards:
            widget = self._find_card_widget(card.id)
            reason = self._ssh_stats_prereq(card)
            if reason:
                if widget:
                    widget.set_stats_prompt(reason)
                continue
            if not self._is_monitor_on(card.id):
                if widget:
                    widget.set_stats_prompt("Monitoring off — turn on Monitor to refresh SSH stats.")
                continue
            if widget:
                widget.set_stats_loading()
            fetchable.append(card)

        if not fetchable:
            monitored = [card for card in self._ssh_cards if self._is_monitor_on(card.id)]
            if not monitored:
                self.status_label.configure(
                    text="No sites monitoring. Turn on Monitor on cards or use All monitoring on."
                )
            else:
                self.status_label.configure(text="Configure SSH credentials in Admin to load stats.")
            return

        self.status_label.configure(text="Refreshing SSH card stats...")
        for card in fetchable:
            threading.Thread(target=self._fetch_ssh_stats_worker, args=(card,), daemon=True).start()

    def _find_card_widget(self, card_id: int) -> GlowCard | None:
        for widget in self.card_widgets:
            if widget.card_id == card_id and widget.winfo_exists():
                return widget
        return None

    def _ssh_key_passphrase(self, card: Card) -> str:
        try:
            return decrypt_text(self.crypto_key, card.encrypted_key_passphrase)
        except ValueError:
            return ""

    def _fetch_ssh_stats_worker(self, card: Card) -> None:
        if card.id in self._stats_in_flight:
            return
        self._stats_in_flight.add(card.id)
        try:
            reason = self._ssh_stats_prereq(card)
            if reason:
                raise ValueError(reason.replace("\n", " "))
            auth = resolve_ssh_metrics_auth(card, self.crypto_key)
            commands = resolve_card_commands(
                card.device_profile,
                card.custom_commands,
                instance_id=getattr(card, "serial_number", "") or "",
                dscli_path=getattr(card, "dscli_path", "") or "",
                dscli_hmc=getattr(card, "dscli_hmc", "") or "",
                username=str(getattr(card, "username", "") or ""),
                password=auth.password,
            )
            if commands:
                results = run_remote_command_suite(
                    card.host,
                    card.port,
                    card.username,
                    commands,
                    auth.key_path,
                    auth.key_passphrase,
                    auth.password,
                    device_profile=card.device_profile,
                )
                left, right = command_results_columns(results)
                try:
                    ensure_health_dashboard_registered(self.db, self.crypto_key)
                    get_health_server().update_card_live_data(
                        card.id,
                        command_results=results,
                        error=None,
                    )
                except Exception as push_exc:
                    _log(f"Could not push live stats to health API for {card.name}: {push_exc}")
            else:
                metrics = run_remote_metrics(
                    card.host,
                    card.port,
                    card.username,
                    auth.key_path,
                    auth.key_passphrase,
                    auth.password,
                )
                left, right = card_stats_columns(metrics)
            self.after(0, lambda cid=card.id, l=left, r=right: self._apply_card_stats(cid, l, r, None))
        except Exception as exc:
            message = str(exc)
            self.after(0, lambda cid=card.id, msg=message: self._apply_card_stats(cid, [], [], msg))
        finally:
            self._stats_in_flight.discard(card.id)

    def _apply_card_stats(
        self,
        card_id: int,
        left: list[str],
        right: list[str],
        error: str | None,
    ) -> None:
        widget = self._find_card_widget(card_id)
        if not widget:
            return
        if error:
            widget.set_stats_error(error)
            if self._is_monitor_on(card_id):
                widget.set_ssh_status("fail", error)
            else:
                widget.set_ssh_status("off")
        else:
            widget.set_stats(left, right)
            if self._is_monitor_on(card_id):
                widget.set_ssh_status("ok")
            else:
                widget.set_ssh_status("off")

    def _probe_card_ssh_status(self, card_id: int) -> None:
        widget = self._find_card_widget(card_id)
        if widget:
            widget.set_ssh_status("checking")
        if card_id in self._ssh_status_in_flight:
            return
        threading.Thread(
            target=self._probe_ssh_status_worker,
            args=(card_id,),
            daemon=True,
        ).start()

    def _probe_monitored_ssh_status(self) -> None:
        for card in self._ssh_cards:
            if self._is_monitor_on(card.id):
                self._probe_card_ssh_status(card.id)

    def highlight_drop_target(self, target) -> None:
        for card in self.card_widgets:
            card.set_drop_highlight(card is target)

    def clear_drop_highlights(self) -> None:
        for card in self.card_widgets:
            card.set_drop_highlight(False)

    def _reorder_cards(self, source_id: int, target_id: int) -> None:
        ordered = [card.id for card in self.db.list_cards()]
        if source_id not in ordered or target_id not in ordered:
            self.refresh_cards()
            return
        source_idx = ordered.index(source_id)
        target_idx = ordered.index(target_id)
        ordered.pop(source_idx)
        ordered.insert(target_idx, source_id)
        self.db.update_sort_orders(ordered)
        self.refresh_cards()
        self.status_label.configure(text="Card order updated.")

    def _load_expanded_card_ids(self) -> set[int]:
        raw = self.db.get_setting("cards_expanded", "[]")
        try:
            return {int(card_id) for card_id in json.loads(raw)}
        except (json.JSONDecodeError, TypeError, ValueError):
            return set()

    def _save_expanded_card_ids(self) -> None:
        self.db.set_setting("cards_expanded", json.dumps(sorted(self._expanded_card_ids)))

    def _on_card_collapsed_change(self, card_id: int, collapsed: bool) -> None:
        if collapsed:
            self._expanded_card_ids.discard(card_id)
        else:
            self._expanded_card_ids.add(card_id)
        self._save_expanded_card_ids()

    def _toggle_mouse_jiggler(self) -> None:
        enabled = bool(self.mouse_jiggler_switch.get())
        self._mouse_jiggler_enabled = enabled
        self.db.set_setting(SETTING_MOUSE_JIGGLER, "true" if enabled else "false")
        if hasattr(self.master, "set_mouse_jiggler_enabled"):
            self.master.set_mouse_jiggler_enabled(enabled)

    def _toggle_compact_cards(self) -> None:
        self._cards_compact = bool(self.compact_switch.get())
        self.db.set_setting("cards_compact", "true" if self._cards_compact else "false")
        if self._cards_compact:
            for widget in self.card_widgets:
                if widget.card_id not in self._expanded_card_ids:
                    widget.set_collapsed(True, notify=False)
        self.status_label.configure(
            text=(
                "Compact mode on — use ▶ or Expand Checked to open individual cards"
                if self._cards_compact
                else "Compact mode off — per-card expand state kept"
            )
        )

    def _set_all_cards_collapsed(self, collapsed: bool) -> None:
        if collapsed:
            self._expanded_card_ids.clear()
            self._save_expanded_card_ids()
        else:
            self._expanded_card_ids = {widget.card_id for widget in self.card_widgets}
            self._save_expanded_card_ids()
        for widget in self.card_widgets:
            widget.set_collapsed(collapsed, notify=False)

    def _expand_checked_cards(self) -> None:
        expanded = 0
        for widget in self.card_widgets:
            if not widget.is_selected():
                continue
            self._expanded_card_ids.add(widget.card_id)
            widget.set_collapsed(False, notify=False)
            expanded += 1
        if expanded:
            self._save_expanded_card_ids()
            self.status_label.configure(text=f"Expanded {expanded} checked card(s).")
        else:
            self.status_label.configure(text="Check one or more cards, then Expand Checked.")

    def _update_selection_status(self) -> None:
        if not hasattr(self, "selection_label"):
            return
        selected = sum(1 for widget in self.card_widgets if widget.is_selected())
        total = len(self.card_widgets)
        self.selection_label.configure(text=f"{selected} of {total} selected")

    def _select_all_cards(self) -> None:
        for widget in self.card_widgets:
            widget.set_selected(True)
        self._update_selection_status()

    def _clear_card_selection(self) -> None:
        for widget in self.card_widgets:
            widget.set_selected(False)
        self._update_selection_status()

    def _set_checked_monitoring(self, enabled: bool) -> None:
        selected_widgets = [
            widget
            for widget in self.card_widgets
            if widget.is_selected() and self._visible_cards.get(widget.card_id)
        ]
        ssh_widgets = [
            widget
            for widget in selected_widgets
            if self._visible_cards[widget.card_id].card_type == "ssh"
        ]
        if not selected_widgets:
            self.status_label.configure(
                text="Check one or more cards, then Monitor Checked / Unmonitor Checked."
            )
            return
        if not ssh_widgets:
            self.status_label.configure(text="No SSH cards in the selection.")
            return

        try:
            for widget in ssh_widgets:
                card = self._visible_cards[widget.card_id]
                set_card_monitor_enabled(card.id, enabled)
                self._monitor_states[card.id] = enabled
                widget.set_monitor_enabled(enabled)
                if enabled:
                    self._probe_card_ssh_status(card.id)
                    if card.id not in self._stats_in_flight:
                        threading.Thread(
                            target=self._fetch_ssh_stats_worker,
                            args=(card,),
                            daemon=True,
                        ).start()
                else:
                    self._set_card_ssh_monitor_off(card.id)
            self._sync_master_monitor_switch()
            self._refresh_capacity_alerts()
            action = "Monitoring on" if enabled else "Monitoring off"
            self.status_label.configure(
                text=f"{action} for {len(ssh_widgets)} checked SSH card(s)."
            )
        except Exception as exc:
            self._sync_master_monitor_switch()
            self.status_label.configure(text=f"Could not update monitoring: {exc}")

    def _cards_for_widgets(self, widgets: list[GlowCard]) -> list[Card]:
        cards: list[Card] = []
        for widget in widgets:
            card = self._visible_cards.get(widget.card_id)
            if card:
                cards.append(card)
        return cards

    def _open_cards_staggered(self, cards: list[Card], *, label: str) -> None:
        if not cards:
            self.status_label.configure(text=f"No cards to open for {label}.")
            return

        self.status_label.configure(text=f"Opening {len(cards)} connection(s)...")

        def launch_at(index: int) -> None:
            if index >= len(cards):
                self.status_label.configure(text=f"Opened {len(cards)} connection(s).")
                return
            card = cards[index]
            try:
                self._launch_card(card)
            except Exception as exc:
                self.status_label.configure(text=f"Failed opening {card.name}: {exc}")
            delay = 500 if card.card_type == "ssh" else 250
            self.after(delay, lambda: launch_at(index + 1))

        launch_at(0)

    def _open_checked_cards(self) -> None:
        widgets = [widget for widget in self.card_widgets if widget.is_selected()]
        cards = self._cards_for_widgets(widgets)
        if not cards:
            self.status_label.configure(text="Check one or more sites, then click Open Checked.")
            return
        self._open_cards_staggered(cards, label="checked")

    def _open_all_visible_cards(self) -> None:
        cards = list(self._visible_cards.values())
        if not cards:
            self.status_label.configure(text="No visible cards to open.")
            return
        if not messagebox.askyesno(
            "Open All",
            f"Open all {len(cards)} visible connection(s)?\n\n"
            "SSH sessions open in separate windows.",
        ):
            return
        self._open_cards_staggered(cards, label="all visible")

    @staticmethod
    def _card_subtitle(card: Card) -> str:
        if card.card_type == "web":
            return card.url or card.host
        port = f":{card.port}" if card.port else ""
        host_line = f"{card.host}{port}"
        serial = (getattr(card, "serial_number", "") or "").strip()
        if serial:
            return f"{host_line}  ·  SN {serial}"
        return host_line

    def _snapshot_card(self, card: Card) -> None:
        widget = self._find_card_widget(card.id)
        left, right, error = widget.get_stats_snapshot() if widget else ([], [], None)

        if self._snapshot_dialog and self._snapshot_dialog.winfo_exists():
            self._snapshot_dialog.destroy()

        self._snapshot_dialog = StatsSnapshotDialog(
            self,
            theme_name=self.theme_name,
            card_name=card.name,
            subtitle=self._card_subtitle(card),
            left_lines=left,
            right_lines=right,
            error=error,
            on_refresh=lambda dialog: self._refresh_snapshot(card, dialog),
        )
        self._refresh_snapshot(card, self._snapshot_dialog)

    def _refresh_snapshot(self, card: Card, dialog: StatsSnapshotDialog) -> None:
        dialog.update_stats([], [], "Refreshing...")
        threading.Thread(
            target=self._fetch_snapshot_worker,
            args=(card, dialog),
            daemon=True,
        ).start()

    def _fetch_snapshot_worker(self, card: Card, dialog: StatsSnapshotDialog) -> None:
        self._stats_in_flight.add(card.id)
        try:
            reason = self._ssh_stats_prereq(card)
            if reason:
                raise ValueError(reason.replace("\n", " "))
            auth = resolve_ssh_metrics_auth(card, self.crypto_key)
            commands = resolve_card_commands(
                card.device_profile,
                card.custom_commands,
                instance_id=getattr(card, "serial_number", "") or "",
                dscli_path=getattr(card, "dscli_path", "") or "",
                dscli_hmc=getattr(card, "dscli_hmc", "") or "",
                username=str(getattr(card, "username", "") or ""),
                password=auth.password,
            )
            if commands:
                results = run_remote_command_suite(
                    card.host,
                    card.port,
                    card.username,
                    commands,
                    auth.key_path,
                    auth.key_passphrase,
                    auth.password,
                    device_profile=card.device_profile,
                )
                left, right = command_results_columns(results)
            else:
                metrics = run_remote_metrics(
                    card.host,
                    card.port,
                    card.username,
                    auth.key_path,
                    auth.key_passphrase,
                    auth.password,
                )
                left, right = card_stats_columns(metrics)
            widget = self._find_card_widget(card.id)
            if widget:
                self.after(0, lambda: widget.set_stats(left, right))
            self.after(0, lambda: dialog.update_stats(left, right, None))
        except Exception as exc:
            self.after(0, lambda msg=str(exc): dialog.update_stats([], [], msg))
        finally:
            self._stats_in_flight.discard(card.id)

    def _monitor_card(self, card: Card) -> None:
        from launchpad.ssh_launcher import _log

        _log(f"Health clicked for card '{card.name}' (id={card.id})")
        auth = resolve_ssh_metrics_auth(card, self.crypto_key)
        if not auth.is_valid:
            self.status_label.configure(
                text="Health check failed: set SSH Password or a key in Admin.",
            )
            return

        self.status_label.configure(text=f"Fetching health metrics for {card.name}...")
        threading.Thread(target=self._monitor_card_worker, args=(card,), daemon=True).start()

    def _monitor_card_worker(self, card: Card) -> None:
        from launchpad.ssh_launcher import _log

        try:
            auth = resolve_ssh_metrics_auth(card, self.crypto_key)
            output = open_health_dashboard(
                card.id,
                card.name,
                card.host,
                card.port,
                card.username,
                auth.key_path,
                auth.key_passphrase,
                auth.password,
                card.device_profile,
                card.custom_commands,
                getattr(card, "serial_number", "") or "",
                (
                    resolve_sudo_password(card, self.crypto_key)
                    if card.device_profile == "hadoop_linux"
                    else ""
                ),
            )
        except Exception as exc:
            _log(f"Health check failed: {exc}")
            self.after(
                0,
                lambda: self.status_label.configure(
                    text=f"Health check failed for {card.name}: {exc}"
                ),
            )
            return

        self.after(
            0,
            lambda: self.status_label.configure(
                text=(
                    f"Added {card.name} to health dashboard. "
                    f"Open {output} or keep the existing tab."
                )
            ),
        )
        threading.Thread(target=self._fetch_ssh_stats_worker, args=(card,), daemon=True).start()

    def _health_ssh_cards(self) -> list[Card]:
        return [
            card
            for card in self.db.list_cards()
            if card.card_type == "ssh" and not ssh_stats_prereq_message(card, self.crypto_key)
        ]

    def _open_sync_browser_report(
        self,
        *,
        status: str,
        fail_log: str,
        open_url,
        summary: str,
    ):
        self.status_label.configure(text=status)
        self.update_idletasks()

        def worker() -> None:
            try:
                server = get_health_server()
                server.sync_from_app()
                url = open_url(server)
                _log(f"{summary} ({url})")
                self.after(0, lambda u=url, s=summary: self._set_status(s, url=u))
            except Exception as exc:
                _log(f"{fail_log}: {exc}")
                self.after(0, lambda msg=str(exc): self._set_status(f"{fail_log}: {msg}"))

        return worker

    def _open_entries_browser_report(
        self,
        *,
        status: str,
        fail_log: str,
        opener,
        summary_for,
        after_success=None,
    ):
        self.status_label.configure(text=status)
        self.update_idletasks()

        def worker() -> None:
            try:
                entries = build_health_dashboard_entries(self.db, self.crypto_key)
                if not entries:
                    self.after(
                        0,
                        lambda: self.status_label.configure(
                            text="No SSH cards with credentials found. Add SSH Password or a key in Admin first."
                        ),
                    )
                    return
                result = opener(entries)
                if isinstance(result, tuple):
                    url, extra = result
                    summary = summary_for(entries, extra)
                else:
                    url = result
                    summary = summary_for(entries)
                _log(f"{summary} ({url})")
                self.after(0, lambda u=url, s=summary: self._set_status(s, url=u))
                if after_success is not None:
                    self.after(0, after_success)
            except Exception as exc:
                _log(f"{fail_log}: {exc}")
                self.after(0, lambda msg=str(exc): self._set_status(f"{fail_log}: {msg}"))

        return worker

    def _open_health_dashboard_all(self) -> None:
        worker = self._open_entries_browser_report(
            status="Opening health dashboard...",
            fail_log="Health dashboard failed",
            opener=open_health_dashboard_for_cards,
            summary_for=lambda entries, results: (
                f"Health dashboard opened — {len(results)} site(s) loaded (monitoring off). "
                "Turn on Monitor per site, or All monitoring on, to connect."
            ),
            after_success=self._refresh_capacity_alerts,
        )
        threading.Thread(target=worker, daemon=True).start()

    def _open_capacity_report_all(self) -> None:
        worker = self._open_entries_browser_report(
            status="Opening capacity report...",
            fail_log="Capacity report failed",
            opener=open_capacity_report_for_cards,
            summary_for=lambda entries: (
                f"Capacity report opened — {len(entries)} site(s) loaded (monitoring off). "
                "Turn on monitoring on the page, then Refresh On Sites."
            ),
            after_success=self._refresh_capacity_alerts,
        )
        threading.Thread(target=worker, daemon=True).start()

    def _open_fc_wwpn_report_all(self) -> None:
        worker = self._open_entries_browser_report(
            status="Opening FC WWPN report...",
            fail_log="FC WWPN report failed",
            opener=open_fc_wwpn_report_for_cards,
            summary_for=lambda entries: (
                f"FC WWPN report opened — {len(entries)} site(s). "
                "Turn on Monitor, refresh, then open Hosts & LUN Mappings."
            ),
        )
        threading.Thread(target=worker, daemon=True).start()

    def _open_site_lookup_all(self) -> None:
        worker = self._open_entries_browser_report(
            status="Opening Site Lookup...",
            fail_log="Site Lookup failed",
            opener=open_site_lookup_for_cards,
            summary_for=lambda entries: (
                f"Site Lookup opened — {len(entries)} site(s). "
                "Pick a site, then Live Refresh to load hosts, volumes, and pools."
            ),
        )
        threading.Thread(target=worker, daemon=True).start()

    def _open_ansible_pad(self) -> None:
        worker = self._open_entries_browser_report(
            status="Opening Ansible Pad…",
            fail_log="Ansible Pad failed",
            opener=open_ansible_pad_for_cards,
            summary_for=lambda entries: (
                f"Ansible Pad opened — {len(entries)} site(s) are available for package export."
            ),
        )
        threading.Thread(target=worker, daemon=True).start()

    def _open_host_power(self, card_id: int | None = None) -> None:
        worker = self._open_entries_browser_report(
            status="Opening Host Power…",
            fail_log="Host Power failed",
            opener=lambda entries: open_host_power_for_cards(entries, card_id=card_id),
            summary_for=lambda entries: (
                "Host Power opened — select a Hadoop host and confirm before powering it off."
            ),
        )
        threading.Thread(target=worker, daemon=True).start()

    def _open_contingency_groups(self) -> None:
        worker = self._open_sync_browser_report(
            status="Opening Consistency Groups…",
            fail_log="Consistency Groups failed",
            open_url=lambda server: server.open_contingency_groups(),
            summary="Consistency Groups opened — reference library only; it does not modify arrays.",
        )
        threading.Thread(target=worker, daemon=True).start()

    def _open_fc_consistgrp(self) -> None:
        worker = self._open_sync_browser_report(
            status="Opening FlashCopy CGs…",
            fail_log="FlashCopy CGs failed",
            open_url=lambda server: server.open_fc_consistgrp(),
            summary="FlashCopy CGs opened — confirmed actions mutate arrays on the linked array.",
        )
        threading.Thread(target=worker, daemon=True).start()

    def _open_esx_snap_policy(self) -> None:
        worker = self._open_sync_browser_report(
            status="Opening ESX-snap Policy…",
            fail_log="ESX-snap Policy failed",
            open_url=lambda server: server.open_esx_snap_policy(),
            summary="ESX-snap Policy opened — Preview then Run Create mutates the selected arrays.",
        )
        threading.Thread(target=worker, daemon=True).start()

    def _open_lun_builder(self) -> None:
        worker = self._open_sync_browser_report(
            status="Opening LUN Builder…",
            fail_log="LUN Builder failed",
            open_url=lambda server: server.open_lun_builder(),
            summary="LUN Builder opened — planning and CRUD are available.",
        )
        threading.Thread(target=worker, daemon=True).start()

    def _open_volume_find(self) -> None:
        worker = self._open_sync_browser_report(
            status="Opening Volume Find…",
            fail_log="Volume Find failed",
            open_url=lambda server: server.open_volume_find(),
            summary="Volume Find opened — cache and live search are available.",
        )
        threading.Thread(target=worker, daemon=True).start()

    def _open_host_volume_health(self) -> None:
        worker = self._open_sync_browser_report(
            status="Opening Hosts & Volumes Health…",
            fail_log="Hosts & Volumes Health failed",
            open_url=lambda server: server.open_host_volume_health(),
            summary="Hosts & Volumes Health opened — refresh live for offline/degraded rows.",
        )
        threading.Thread(target=worker, daemon=True).start()

    def _open_system_connectivity(self) -> None:
        worker = self._open_sync_browser_report(
            status="Opening System Connectivity…",
            fail_log="System Connectivity failed",
            open_url=lambda server: server.open_system_connectivity(),
            summary="System Connectivity opened — refresh live for Call Home/DNS/SNMP/NTP.",
        )
        threading.Thread(target=worker, daemon=True).start()

    def _open_storage_inventory(self) -> None:
        worker = self._open_sync_browser_report(
            status="Opening Storage Inventory…",
            fail_log="Storage Inventory failed",
            open_url=lambda server: server.open_storage_inventory(),
            summary="Storage Inventory opened — refresh live for fleet device inventory.",
        )
        threading.Thread(target=worker, daemon=True).start()

    def _open_export_excel_menu(self) -> None:
        menu = Menu(self, tearoff=0)
        menu.add_command(label="Capacity", command=self._export_capacity_excel)
        if is_dell_report_enabled(self.db):
            menu.add_command(label="Dell Report…", command=self._export_dell_report_excel)
        menu.add_command(label="FC WWPN", command=self._export_fc_wwpn_excel)
        menu.add_command(label="Snapshot Schedule", command=self._export_snapshot_schedule_excel)
        menu.add_separator()
        menu.add_command(label="Email Capacity Now", command=self._email_capacity_now)
        try:
            x = self.export_excel_btn.winfo_rootx()
            y = self.export_excel_btn.winfo_rooty() + self.export_excel_btn.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _export_fc_wwpn_excel(self) -> None:
        from datetime import datetime

        from launchpad.capacity_export import open_exported_workbook
        from launchpad.fc_wwpn_export import export_fc_wwpn_excel

        default_name = f"FC_WWPN_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        output_path = filedialog.asksaveasfilename(
            title="Save FC WWPN Excel report",
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=default_name,
        )
        if not output_path:
            return

        ssh_count = sum(1 for card in self.db.list_cards() if card.card_type == "ssh")
        if not ssh_count:
            self.status_label.configure(
                text="No SSH cards with credentials found. Add SSH Password or a key in Admin first.",
            )
            return

        path = Path(output_path)
        self.status_label.configure(text=f"Exporting FC WWPN Excel for {ssh_count} site(s)...")
        self.update_idletasks()

        def start_export(target) -> None:
            threading.Thread(target=target, daemon=True).start()

        def progress(name: str, index: int, total: int) -> None:
            self.after(
                0,
                lambda: self.status_label.configure(
                    text=f"Exporting FC WWPN ({index}/{total}): {name}..."
                ),
            )

        def worker() -> None:
            try:
                ensure_health_dashboard_registered(self.db, self.crypto_key)
                result = export_fc_wwpn_excel(
                    self.db,
                    self.crypto_key,
                    path,
                    progress=progress,
                )
                summary = (
                    f"FC Excel saved: {result.path.name} — "
                    f"{result.port_rows} port(s), {result.host_rows} host(s), "
                    f"{result.map_rows} LUN map(s)"
                )
                if result.error_count:
                    summary += f", {result.error_count} error(s)"
                _log(summary)

                def on_done() -> None:
                    self.status_label.configure(text=summary)
                    opened = False
                    try:
                        open_exported_workbook(result.path)
                        opened = True
                    except Exception as open_exc:
                        _log(f"Could not open FC Excel file: {open_exc}")
                    messagebox.showinfo(
                        "FC export complete",
                        f"Saved to:\n{result.path}\n\n"
                        f"FC port rows: {result.port_rows}\n"
                        f"Host rows: {result.host_rows}\n"
                        f"LUN map rows: {result.map_rows}\n"
                        f"Errors: {result.error_count}\n"
                        f"Generated: {result.generated_at}"
                        + ("\n\nOpened in Excel." if opened else ""),
                    )

                self.after(0, on_done)
            except Exception as exc:
                _log(f"FC WWPN Excel export failed: {exc}")
                self.after(
                    0,
                    lambda msg=str(exc): self.status_label.configure(
                        text=f"FC Excel export failed: {msg}"
                    ),
                )
                self.after(
                    0,
                    lambda msg=str(exc): messagebox.showerror("Export failed", msg),
                )

        start_export(worker)

    def _export_snapshot_schedule_excel(self) -> None:
        from datetime import datetime

        from launchpad.capacity_export import open_exported_workbook
        from launchpad.snapshot_schedule_export import export_snapshot_schedule_excel

        default_name = f"Snapshot_Schedule_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        output_path = filedialog.asksaveasfilename(
            title="Save Snapshot Schedule Excel report",
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=default_name,
        )
        if not output_path:
            return

        ssh_count = sum(1 for card in self.db.list_cards() if card.card_type == "ssh")
        if not ssh_count:
            self.status_label.configure(
                text="No SSH cards with credentials found. Add SSH Password or a key in Admin first.",
            )
            return

        path = Path(output_path)
        self.status_label.configure(
            text=f"Exporting Snapshot Schedule Excel for {ssh_count} site(s)..."
        )
        self.update_idletasks()

        def start_export(target) -> None:
            threading.Thread(target=target, daemon=True).start()

        def progress(name: str, index: int, total: int) -> None:
            self.after(
                0,
                lambda: self.status_label.configure(
                    text=f"Exporting Snapshot Schedule ({index}/{total}): {name}..."
                ),
            )

        def worker() -> None:
            try:
                ensure_health_dashboard_registered(self.db, self.crypto_key)
                result = export_snapshot_schedule_excel(
                    self.db,
                    self.crypto_key,
                    path,
                    progress=progress,
                )
                summary = (
                    f"Snapshot Excel saved: {result.path.name} — "
                    f"{result.scheduled_count} scheduled, {result.flagged_count} flagged"
                )
                if result.error_count:
                    summary += f", {result.error_count} error(s)"
                _log(summary)

                def on_done() -> None:
                    self.status_label.configure(text=summary)
                    opened = False
                    try:
                        open_exported_workbook(result.path)
                        opened = True
                    except Exception as open_exc:
                        _log(f"Could not open Snapshot Excel file: {open_exc}")
                    messagebox.showinfo(
                        "Snapshot export complete",
                        f"Saved to:\n{result.path}\n\n"
                        f"Scheduled: {result.scheduled_count}\n"
                        f"Flagged / hold: {result.flagged_count}\n"
                        f"Errors: {result.error_count}\n"
                        f"Generated: {result.generated_at}"
                        + ("\n\nOpened in Excel." if opened else ""),
                    )

                self.after(0, on_done)
            except Exception as exc:
                _log(f"Snapshot Schedule Excel export failed: {exc}")
                self.after(
                    0,
                    lambda msg=str(exc): self.status_label.configure(
                        text=f"Snapshot Excel export failed: {msg}"
                    ),
                )
                self.after(
                    0,
                    lambda msg=str(exc): messagebox.showerror("Export failed", msg),
                )

        start_export(worker)

    def _export_capacity_excel(self) -> None:
        from datetime import datetime
        from pathlib import Path

        from launchpad.capacity_export import export_storage_capacity_excel, open_exported_workbook

        default_name = f"Storage_Capacity_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        output_path = filedialog.asksaveasfilename(
            title="Save capacity Excel report",
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=default_name,
        )
        if not output_path:
            return

        ssh_count = sum(1 for card in self.db.list_cards() if card.card_type == "ssh")
        if not ssh_count:
            self.status_label.configure(
                text="No SSH cards with credentials found. Add SSH Password or a key in Admin first.",
            )
            return

        path = Path(output_path)
        self.status_label.configure(text=f"Exporting capacity to Excel for {ssh_count} site(s)...")
        self.update_idletasks()

        def start_export(target) -> None:
            threading.Thread(target=target, daemon=True).start()

        def progress(name: str, index: int, total: int) -> None:
            self.after(
                0,
                lambda: self.status_label.configure(
                    text=f"Exporting capacity ({index}/{total}): {name}..."
                ),
            )

        def worker() -> None:
            try:
                ensure_health_dashboard_registered(self.db, self.crypto_key)
                result = export_storage_capacity_excel(
                    self.db,
                    self.crypto_key,
                    path,
                    progress=progress,
                )
                summary = (
                    f"Excel saved: {result.path.name} — "
                    f"{result.filled_count} site(s) with capacity"
                )
                if result.pool_filled_count:
                    summary += f", {result.pool_filled_count} with pool stats"
                if result.pool_rows_written:
                    summary += f" ({result.pool_rows_written} pool rows)"
                if result.error_count:
                    summary += f", {result.error_count} error(s)"
                if result.extra_rows:
                    summary += f", {result.extra_rows} extra LaunchPad site(s) appended"
                _log(summary)

                def on_export_done() -> None:
                    self.status_label.configure(text=summary)
                    opened = False
                    open_error = ""
                    try:
                        open_exported_workbook(result.path)
                        opened = True
                    except Exception as open_exc:
                        open_error = str(open_exc)
                        _log(f"Could not open Excel file: {open_exc}")

                    def show_result_dialog() -> None:
                        note = "\n\nOpened in Excel." if opened else (
                            f"\n\nCould not open automatically: {open_error}"
                            if open_error
                            else "\n\nCould not open file automatically."
                        )
                        messagebox.showinfo(
                            "Export complete",
                            f"Saved to:\n{result.path}\n\n"
                            f"Capacity filled: {result.filled_count}\n"
                            f"Pool stats filled: {result.pool_filled_count}\n"
                            f"Pool detail rows: {result.pool_rows_written}\n"
                            f"Errors: {result.error_count}\n"
                            f"Extra LaunchPad rows: {result.extra_rows}\n"
                            f"Generated: {result.generated_at}"
                            + note,
                        )

                    # Let Excel launch before the modal dialog takes focus.
                    self.after(400 if opened else 0, show_result_dialog)

                self.after(0, on_export_done)
            except Exception as exc:
                _log(f"Capacity Excel export failed: {exc}")
                self.after(
                    0,
                    lambda msg=str(exc): self.status_label.configure(
                        text=f"Excel export failed: {msg}"
                    ),
                )
                self.after(
                    0,
                    lambda msg=str(exc): messagebox.showerror("Export failed", msg),
                )

        start_export(worker)

    def _export_dell_report_excel(self) -> None:
        from datetime import datetime

        from launchpad.capacity_export import open_exported_workbook

        if not is_dell_report_enabled(self.db):
            messagebox.showinfo("Dell Report", "Dell Report is disabled in Admin.")
            return

        default_name = f"Dell_Capacity_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        output_path = filedialog.asksaveasfilename(
            title="Save Dell Report Excel workbook",
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=default_name,
        )
        if not output_path:
            return

        ssh_count = sum(1 for card in self.db.list_cards() if card.card_type == "ssh")
        if not ssh_count:
            self.status_label.configure(
                text="No SSH cards with credentials found. Add SSH Password or a key in Admin first.",
            )
            return

        path = Path(output_path)
        self.status_label.configure(text=f"Exporting Dell Report for {ssh_count} site(s)...")
        self.update_idletasks()

        def start_export(target) -> None:
            threading.Thread(target=target, daemon=True).start()

        def worker() -> None:
            try:
                ensure_health_dashboard_registered(self.db, self.crypto_key)
                server = get_health_server()
                body, filename = server.export_dell_report_excel_bytes(
                    include_monitor_off=False,
                )
                path.write_bytes(body)
                summary = f"Dell Report saved: {path.name}"
                _log(summary)

                def on_export_done() -> None:
                    self.status_label.configure(text=summary)
                    opened = False
                    open_error = ""
                    try:
                        open_exported_workbook(path)
                        opened = True
                    except Exception as open_exc:
                        open_error = str(open_exc)
                        _log(f"Could not open Dell Report file: {open_exc}")

                    def show_result_dialog() -> None:
                        note = "\n\nOpened in Excel." if opened else (
                            f"\n\nCould not open automatically: {open_error}"
                            if open_error
                            else "\n\nCould not open file automatically."
                        )
                        messagebox.showinfo(
                            "Dell Report export complete",
                            f"Saved to:\n{path}\n\nSuggested filename: {filename}" + note,
                        )

                    self.after(400 if opened else 0, show_result_dialog)

                self.after(0, on_export_done)
            except Exception as exc:
                _log(f"Dell Report Excel export failed: {exc}")
                self.after(
                    0,
                    lambda msg=str(exc): self.status_label.configure(
                        text=f"Dell Report export failed: {msg}"
                    ),
                )
                self.after(
                    0,
                    lambda msg=str(exc): messagebox.showerror("Export failed", msg),
                )

        start_export(worker)

    def _launch_card(self, card: Card) -> None:
        from pathlib import Path

        from launchpad.ssh_launcher import _log

        _log(f"Connect clicked for card '{card.name}' (id={card.id})")
        try:
            password = decrypt_text(self.crypto_key, card.encrypted_password)
            key_text = decrypt_text(self.crypto_key, card.encrypted_key)
            _log(f"Decrypted key length: {len(key_text.strip())}, password set: {bool(password)}")
        except ValueError as exc:
            _log(f"Decrypt failed: {exc}")
            self.status_label.configure(text=f"Connect failed: {exc}")
            return

        try:
            key_path = resolve_ssh_key(card, self.crypto_key) if card.card_type == "ssh" else ""
        except OSError as exc:
            _log(f"SSH key prepare failed: {exc}")
            self.status_label.configure(text=f"Connect failed: {exc}")
            return

        key_passphrase = self._ssh_key_passphrase(card) if card.card_type == "ssh" else ""

        if card.card_type == "ssh" and not key_path and not password:
            _log("No SSH password or key available")
            self.status_label.configure(
                text="Connect failed: set SSH Password or a key in Admin.",
            )
            return

        try:
            _log(f"Calling launch_card for {card.host}")
            message = launch_card(
                card.card_type,
                card.host,
                card.port,
                card.username,
                password,
                key_path if not password else "",
                card.url,
                card.name,
                key_passphrase,
            )
            _log(f"Launch result: {message}")
        except Exception as exc:
            _log(f"Launch exception: {exc}")
            self.status_label.configure(text=f"Connect failed: {exc}")
            widget = self._find_card_widget(card.id)
            if widget and card.card_type == "ssh":
                widget.set_ssh_status("fail", str(exc))
            return

        if card.card_type == "ssh":
            widget = self._find_card_widget(card.id)
            if widget:
                widget.set_ssh_status("ok", "SSH session launched")

        self.status_label.configure(text=message)
        self.update_idletasks()
