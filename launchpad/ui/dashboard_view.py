import customtkinter as ctk
import json
import threading
from pathlib import Path
from tkinter import Menu, filedialog, messagebox

from launchpad.branding import get_app_name, load_ctk_logo
from launchpad.capacity_email_scheduler import is_capacity_email_due
from launchpad.capacity_email_send import send_capacity_email
from launchpad.capacity_email_settings import load_capacity_email_settings
from launchpad.command_format import resolve_card_commands
from launchpad.crypto import decrypt_text
from launchpad.database import Card
from launchpad.health_format import card_stats_columns, command_results_columns
from launchpad.health_metrics import run_remote_metrics
from launchpad.health_server import get_health_server
from launchpad.launchers import launch_card
from launchpad.monitor import (
    HealthDashboardEntry,
    ensure_health_dashboard_registered,
    get_monitor_states,
    open_capacity_report_for_cards,
    open_fc_wwpn_report_for_cards,
    open_health_dashboard,
    open_health_dashboard_for_cards,
    set_all_monitor_enabled,
    set_card_monitor_enabled,
)
from launchpad.ssh_commands import run_remote_command_suite
from launchpad.ssh_launcher import _log
from launchpad.ssh_test import probe_ssh_login_for_card
from launchpad.ssh_utils import resolve_ssh_key, resolve_ssh_metrics_auth, ssh_stats_prereq_message
from launchpad.ui.card_widget import GlowCard
from launchpad.ui.stats_snapshot_dialog import StatsSnapshotDialog
from launchpad.ui.colors import normalize_color
from launchpad.ui.theme import get_theme

SSH_STATUS_INTERVAL_MS = 90_000
CAPACITY_EMAIL_POLL_MS = 60_000


class DashboardView(ctk.CTkFrame):
    def __init__(self, master, db, crypto_key, on_admin, on_lock) -> None:
        self.theme_name = db.get_setting("theme", "dark")
        self.theme = get_theme(self.theme_name)
        super().__init__(master, fg_color=self.theme["bg"])
        self.db = db
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
        self._capacity_email_timer: str | None = None
        self._capacity_email_send_in_flight = False
        self._visible_cards: dict[int, Card] = {}
        self._monitor_states: dict[int, bool] = {}
        self._cards_compact = self.db.get_setting("cards_compact", "true") == "true"
        self._expanded_card_ids = self._load_expanded_card_ids()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_filters()
        self.cards_frame = ctk.CTkScrollableFrame(self, fg_color=self.theme["surface"])
        self.cards_frame.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 16))
        self._card_columns = 4
        for col in range(self._card_columns):
            self.cards_frame.grid_columnconfigure(col, weight=1)

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
        try:
            count = ensure_health_dashboard_registered(self.db, self.crypto_key)
            if count:
                from launchpad.ssh_launcher import _log

                _log(f"Health dashboard pre-registered {count} SSH card(s)")
        except Exception as exc:
            from launchpad.ssh_launcher import _log

            _log(f"Health dashboard pre-register failed: {exc}")

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        header.grid_columnconfigure(1, weight=1)

        title_row = ctk.CTkFrame(header, fg_color="transparent")
        title_row.grid(row=0, column=0, rowspan=2, sticky="w")

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

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=2, rowspan=2, sticky="e")

        ctk.CTkButton(
            actions,
            text="Health Dashboard",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._open_health_dashboard_all,
        ).grid(row=0, column=0, padx=6)

        ctk.CTkButton(
            actions,
            text="Capacity Report",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._open_capacity_report_all,
        ).grid(row=0, column=1, padx=6)

        ctk.CTkButton(
            actions,
            text="FC WWPN",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._open_fc_wwpn_report_all,
        ).grid(row=0, column=2, padx=6)

        ctk.CTkButton(
            actions,
            text="Consistency Groups",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._open_contingency_groups,
        ).grid(row=0, column=3, padx=6)

        ctk.CTkButton(
            actions,
            text="LUN Builder",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._open_lun_builder,
        ).grid(row=0, column=4, padx=6)

        self.export_excel_btn = ctk.CTkButton(
            actions,
            text="Export Excel ▾",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._open_export_excel_menu,
            width=140,
        )
        self.export_excel_btn.grid(row=0, column=5, padx=6)

        ctk.CTkButton(
            actions,
            text="Refresh Stats",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._fetch_all_ssh_stats,
        ).grid(row=0, column=6, padx=6)

        self.theme_switch = ctk.CTkSwitch(
            actions,
            text="Light mode" if self.theme_name == "dark" else "Dark mode",
            command=self._toggle_theme,
        )
        self.theme_switch.grid(row=0, column=7, padx=6)

        ctk.CTkButton(
            actions,
            text="Admin",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self.on_admin,
        ).grid(row=0, column=8, padx=6)

        ctk.CTkButton(
            actions,
            text="Lock",
            fg_color=self.theme["danger"],
            hover_color="#B91C1C",
            command=self.on_lock,
        ).grid(row=0, column=9, padx=6)

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
        self.search_entry.bind("<KeyRelease>", lambda _e: self.refresh_cards())

        bulk = ctk.CTkFrame(bar, fg_color="transparent")
        bulk.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        bulk.grid_columnconfigure(9, weight=1)

        self.compact_switch = ctk.CTkSwitch(
            bulk,
            text="Compact cards",
            command=self._toggle_compact_cards,
        )
        if self._cards_compact:
            self.compact_switch.select()
        self.compact_switch.grid(row=0, column=0, padx=(0, 12))

        self.monitor_all_switch = ctk.CTkSwitch(
            bulk,
            text="All monitoring on",
            command=self._toggle_all_monitoring,
        )
        self.monitor_all_switch.grid(row=0, column=1, padx=(0, 12))

        ctk.CTkButton(
            bulk,
            text="Select All",
            width=90,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._select_all_cards,
        ).grid(row=0, column=2, padx=4)

        ctk.CTkButton(
            bulk,
            text="Clear",
            width=70,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._clear_card_selection,
        ).grid(row=0, column=3, padx=4)

        ctk.CTkButton(
            bulk,
            text="Monitor Checked",
            width=125,
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_soft"],
            command=lambda: self._set_checked_monitoring(True),
        ).grid(row=0, column=4, padx=4)

        ctk.CTkButton(
            bulk,
            text="Unmonitor Checked",
            width=135,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=lambda: self._set_checked_monitoring(False),
        ).grid(row=0, column=5, padx=4)

        ctk.CTkButton(
            bulk,
            text="Open Checked",
            width=110,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._open_checked_cards,
        ).grid(row=0, column=6, padx=4)

        ctk.CTkButton(
            bulk,
            text="Open All",
            width=90,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._open_all_visible_cards,
        ).grid(row=0, column=7, padx=4)

        ctk.CTkButton(
            bulk,
            text="Expand Checked",
            width=115,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._expand_checked_cards,
        ).grid(row=0, column=8, padx=4)

        ctk.CTkButton(
            bulk,
            text="Expand All",
            width=90,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=lambda: self._set_all_cards_collapsed(False),
        ).grid(row=0, column=9, padx=4)

        ctk.CTkButton(
            bulk,
            text="Collapse All",
            width=100,
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=lambda: self._set_all_cards_collapsed(True),
        ).grid(row=0, column=10, padx=4, sticky="w")

        self.selection_label = ctk.CTkLabel(
            bulk,
            text="0 selected",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=12),
        )
        self.selection_label.grid(row=0, column=11, padx=(12, 0), sticky="e")

    def _toggle_theme(self) -> None:
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.db.set_setting("theme", self.theme_name)
        if hasattr(self.master, "apply_theme"):
            self.master.apply_theme(self.theme_name)

    def apply_theme(self, theme_name: str) -> None:
        self.theme_name = theme_name
        self.theme = get_theme(theme_name)
        self.configure(fg_color=self.theme["bg"])
        if isinstance(self.master, ctk.CTk):
            self.master.configure(fg_color=self.theme["bg"])
        self.cards_frame.configure(fg_color=self.theme["surface"])
        self.theme_switch.configure(text="Light mode" if theme_name == "dark" else "Dark mode")
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

    def refresh_cards(self) -> None:
        if self._stats_timer:
            self.after_cancel(self._stats_timer)
            self._stats_timer = None
        if self._ssh_status_timer:
            self.after_cancel(self._ssh_status_timer)
            self._ssh_status_timer = None

        for widget in self.cards_frame.winfo_children():
            widget.destroy()
        self.card_widgets.clear()
        self._ssh_cards.clear()
        self._visible_cards.clear()

        cols = 4
        self._card_columns = cols
        for col in range(cols):
            self.cards_frame.grid_columnconfigure(col, weight=1)

        query = self.search_entry.get().strip().lower() if hasattr(self, "search_entry") else ""
        category = self.category_var.get() if hasattr(self, "category_var") else "All"
        cards = self.db.list_cards(None if category == "All" else category)

        filtered = [
            card
            for card in cards
            if not query
            or query in card.name.lower()
            or query in card.host.lower()
            or query in card.category.lower()
            or query in (getattr(card, "serial_number", "") or "").lower()
        ]

        can_reorder = category == "All" and not query
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
            return

        self._load_monitor_states()

        visible_ids = {card.id for card in filtered}
        self._expanded_card_ids &= visible_ids
        if not self._cards_compact and not self._expanded_card_ids and filtered:
            self._expanded_card_ids = visible_ids.copy()
            self._save_expanded_card_ids()

        for index, card in enumerate(filtered):
            row, col = divmod(index, cols)
            subtitle = self._card_subtitle(card)
            start_collapsed = card.id not in self._expanded_card_ids
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

        # SSH stats run only when Monitor is on and you click Refresh Stats.

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
            ensure_health_dashboard_registered(self.db, self.crypto_key)
            self._monitor_states = get_monitor_states()
        except Exception as exc:
            from launchpad.ssh_launcher import _log

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
        from launchpad.ssh_launcher import _log

        try:
            ensure_health_dashboard_registered(self.db, self.crypto_key)
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
        if enabled:
            self.status_label.configure(text=f"Monitoring on for {card.name} — refreshing stats...")
            self._probe_card_ssh_status(card.id)
            threading.Thread(target=self._fetch_ssh_stats_worker, args=(card,), daemon=True).start()
        else:
            self.status_label.configure(text=f"Monitoring off for {card.name} — no background SSH.")
            self._set_card_ssh_monitor_off(card.id)

    def _toggle_all_monitoring(self) -> None:
        enabled = bool(self.monitor_all_switch.get())
        try:
            ensure_health_dashboard_registered(self.db, self.crypto_key)
            set_all_monitor_enabled(enabled)
            for card in self._ssh_cards:
                self._monitor_states[card.id] = enabled
                widget = self._find_card_widget(card.id)
                if widget:
                    widget.set_monitor_enabled(enabled)
        except Exception as exc:
            self.status_label.configure(text=f"Monitor toggle failed: {exc}")
            self._sync_master_monitor_switch()
            return

        if enabled:
            self.status_label.configure(text="All monitoring on — refreshing stats for SSH cards...")
            self._fetch_all_ssh_stats()
        else:
            self.status_label.configure(text="All monitoring off — no background SSH.")
            for card in self._ssh_cards:
                self._set_card_ssh_monitor_off(card.id)

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
            ensure_health_dashboard_registered(self.db, self.crypto_key)
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

    def _open_health_dashboard_all(self) -> None:
        from launchpad.ssh_launcher import _log

        cards = self._health_ssh_cards()
        if not cards:
            self.status_label.configure(
                text="No SSH cards with credentials found. Add SSH Password or a key in Admin first.",
            )
            return

        entries: list[HealthDashboardEntry] = []
        for card in cards:
            auth = resolve_ssh_metrics_auth(card, self.crypto_key)
            entries.append(
                HealthDashboardEntry(
                    card_id=card.id,
                    name=card.name,
                    host=card.host,
                    port=card.port,
                    username=card.username,
                    auth=auth,
                    device_profile=card.device_profile,
                    custom_commands=card.custom_commands,
                    serial_number=getattr(card, "serial_number", "") or "",
                )
            )

        self.status_label.configure(
            text=f"Opening health dashboard for {len(entries)} SSH server(s)..."
        )
        self.update_idletasks()
        try:
            ensure_health_dashboard_registered(self.db, self.crypto_key)
        except Exception as exc:
            _log(f"Health dashboard register failed: {exc}")

        def worker() -> None:
            try:
                url, results = open_health_dashboard_for_cards(entries)
                summary = (
                    f"Health dashboard opened — {len(results)} site(s) loaded (monitoring off). "
                    "Turn on Monitor per site, or All monitoring on, to connect."
                )
                _log(f"{summary} ({url})")
                self.after(0, lambda u=url, s=summary: self._set_status(s, url=u))
            except Exception as exc:
                _log(f"Health dashboard failed: {exc}")
                self.after(
                    0,
                    lambda: self._set_status(f"Health dashboard failed: {exc}"),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _open_capacity_report_all(self) -> None:
        from launchpad.ssh_launcher import _log

        cards = self._health_ssh_cards()
        if not cards:
            self.status_label.configure(
                text="No SSH cards with credentials found. Add SSH Password or a key in Admin first.",
            )
            return

        entries: list[HealthDashboardEntry] = []
        for card in cards:
            auth = resolve_ssh_metrics_auth(card, self.crypto_key)
            entries.append(
                HealthDashboardEntry(
                    card_id=card.id,
                    name=card.name,
                    host=card.host,
                    port=card.port,
                    username=card.username,
                    auth=auth,
                    device_profile=card.device_profile,
                    custom_commands=card.custom_commands,
                    serial_number=getattr(card, "serial_number", "") or "",
                )
            )

        self.status_label.configure(
            text=f"Opening capacity report for {len(entries)} site(s)..."
        )
        self.update_idletasks()
        try:
            ensure_health_dashboard_registered(self.db, self.crypto_key)
        except Exception as exc:
            _log(f"Capacity report register failed: {exc}")

        def worker() -> None:
            try:
                url = open_capacity_report_for_cards(entries)
                summary = (
                    f"Capacity report opened — {len(entries)} site(s) loaded (monitoring off). "
                    "Turn on monitoring on the page, then Refresh On Sites."
                )
                _log(f"{summary} ({url})")
                self.after(0, lambda u=url, s=summary: self._set_status(s, url=u))
            except Exception as exc:
                _log(f"Capacity report failed: {exc}")
                self.after(
                    0,
                    lambda: self._set_status(f"Capacity report failed: {exc}"),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _open_fc_wwpn_report_all(self) -> None:
        from launchpad.ssh_launcher import _log

        cards = self._health_ssh_cards()
        if not cards:
            self.status_label.configure(
                text="No SSH cards with credentials found. Add SSH Password or a key in Admin first.",
            )
            return

        entries: list[HealthDashboardEntry] = []
        for card in cards:
            auth = resolve_ssh_metrics_auth(card, self.crypto_key)
            entries.append(
                HealthDashboardEntry(
                    card_id=card.id,
                    name=card.name,
                    host=card.host,
                    port=card.port,
                    username=card.username,
                    auth=auth,
                    device_profile=card.device_profile,
                    custom_commands=card.custom_commands,
                    serial_number=getattr(card, "serial_number", "") or "",
                    category=card.category or "",
                )
            )

        self.status_label.configure(text=f"Opening FC WWPN report for {len(entries)} site(s)...")
        self.update_idletasks()
        try:
            ensure_health_dashboard_registered(self.db, self.crypto_key)
        except Exception as exc:
            _log(f"FC WWPN report register failed: {exc}")

        def worker() -> None:
            try:
                url = open_fc_wwpn_report_for_cards(entries)
                summary = (
                    f"FC WWPN report opened — {len(entries)} site(s). "
                    "Turn on Monitor, refresh, then open Hosts & LUN Mappings."
                )
                _log(f"{summary} ({url})")
                self.after(0, lambda u=url, s=summary: self._set_status(s, url=u))
            except Exception as exc:
                _log(f"FC WWPN report failed: {exc}")
                self.after(
                    0,
                    lambda: self._set_status(f"FC WWPN report failed: {exc}"),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _open_contingency_groups(self) -> None:
        self.status_label.configure(text="Opening Consistency Groups…")
        self.update_idletasks()
        try:
            ensure_health_dashboard_registered(self.db, self.crypto_key)
        except Exception as exc:
            _log(f"Consistency Groups register failed: {exc}")

        def worker() -> None:
            try:
                server = get_health_server()
                server.sync_from_app()
                url = server.open_contingency_groups()
                summary = "Consistency Groups opened — reference library only; it does not modify arrays."
                _log(f"{summary} ({url})")
                self.after(0, lambda u=url, s=summary: self._set_status(s, url=u))
            except Exception as exc:
                _log(f"Consistency Groups failed: {exc}")
                self.after(
                    0,
                    lambda: self._set_status(f"Consistency Groups failed: {exc}"),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _open_lun_builder(self) -> None:
        self.status_label.configure(text="Opening LUN Builder…")
        self.update_idletasks()
        try:
            ensure_health_dashboard_registered(self.db, self.crypto_key)
        except Exception as exc:
            _log(f"LUN Builder register failed: {exc}")

        def worker() -> None:
            try:
                server = get_health_server()
                server.sync_from_app()
                url = server.open_lun_builder()
                summary = "LUN Builder opened — planning and CRUD are available."
                _log(f"{summary} ({url})")
                self.after(0, lambda u=url, s=summary: self._set_status(s, url=u))
            except Exception as exc:
                _log(f"LUN Builder failed: {exc}")
                self.after(
                    0,
                    lambda: self._set_status(f"LUN Builder failed: {exc}"),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _open_export_excel_menu(self) -> None:
        menu = Menu(self, tearoff=0)
        menu.add_command(label="Capacity", command=self._export_capacity_excel)
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
        from launchpad.ssh_launcher import _log

        cards = self._health_ssh_cards()
        if not cards:
            self.status_label.configure(
                text="No SSH cards with credentials found. Add SSH Password or a key in Admin first.",
            )
            return

        default_name = f"FC_WWPN_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        output_path = filedialog.asksaveasfilename(
            title="Save FC WWPN Excel report",
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=default_name,
        )
        if not output_path:
            return

        path = Path(output_path)
        self.status_label.configure(text=f"Exporting FC WWPN Excel for {len(cards)} site(s)...")
        self.update_idletasks()

        try:
            ensure_health_dashboard_registered(self.db, self.crypto_key)
        except Exception as exc:
            _log(f"Health dashboard register failed before FC export: {exc}")

        def progress(name: str, index: int, total: int) -> None:
            self.after(
                0,
                lambda: self.status_label.configure(
                    text=f"Exporting FC WWPN ({index}/{total}): {name}..."
                ),
            )

        def worker() -> None:
            try:
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
                    lambda: self.status_label.configure(text=f"FC Excel export failed: {exc}"),
                )
                self.after(
                    0,
                    lambda: messagebox.showerror("Export failed", str(exc)),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _export_snapshot_schedule_excel(self) -> None:
        from datetime import datetime

        from launchpad.capacity_export import open_exported_workbook
        from launchpad.snapshot_schedule_export import export_snapshot_schedule_excel
        from launchpad.ssh_launcher import _log

        cards = self._health_ssh_cards()
        if not cards:
            self.status_label.configure(
                text="No SSH cards with credentials found. Add SSH Password or a key in Admin first.",
            )
            return

        default_name = f"Snapshot_Schedule_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        output_path = filedialog.asksaveasfilename(
            title="Save Snapshot Schedule Excel report",
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=default_name,
        )
        if not output_path:
            return

        path = Path(output_path)
        self.status_label.configure(
            text=f"Exporting Snapshot Schedule Excel for {len(cards)} site(s)..."
        )
        self.update_idletasks()

        try:
            ensure_health_dashboard_registered(self.db, self.crypto_key)
        except Exception as exc:
            _log(f"Health dashboard register failed before snapshot export: {exc}")

        def progress(name: str, index: int, total: int) -> None:
            self.after(
                0,
                lambda: self.status_label.configure(
                    text=f"Exporting Snapshot Schedule ({index}/{total}): {name}..."
                ),
            )

        def worker() -> None:
            try:
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
                    lambda: self.status_label.configure(
                        text=f"Snapshot Excel export failed: {exc}"
                    ),
                )
                self.after(
                    0,
                    lambda: messagebox.showerror("Export failed", str(exc)),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _export_capacity_excel(self) -> None:
        from datetime import datetime
        from pathlib import Path

        from launchpad.capacity_export import export_storage_capacity_excel, open_exported_workbook
        from launchpad.ssh_launcher import _log

        cards = self._health_ssh_cards()
        if not cards:
            self.status_label.configure(
                text="No SSH cards with credentials found. Add SSH Password or a key in Admin first.",
            )
            return

        default_name = f"Storage_Capacity_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        output_path = filedialog.asksaveasfilename(
            title="Save capacity Excel report",
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=default_name,
        )
        if not output_path:
            return

        path = Path(output_path)
        self.status_label.configure(text=f"Exporting capacity to Excel for {len(cards)} site(s)...")
        self.update_idletasks()

        try:
            ensure_health_dashboard_registered(self.db, self.crypto_key)
        except Exception as exc:
            _log(f"Health dashboard register failed before export: {exc}")

        def progress(name: str, index: int, total: int) -> None:
            self.after(
                0,
                lambda: self.status_label.configure(
                    text=f"Exporting capacity ({index}/{total}): {name}..."
                ),
            )

        def worker() -> None:
            try:
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
                    lambda: self.status_label.configure(text=f"Excel export failed: {exc}"),
                )
                self.after(
                    0,
                    lambda: messagebox.showerror("Export failed", str(exc)),
                )

        threading.Thread(target=worker, daemon=True).start()

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
