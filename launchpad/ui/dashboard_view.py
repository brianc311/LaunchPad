import customtkinter as ctk
import threading
from pathlib import Path
from tkinter import messagebox

from launchpad.branding import get_app_name, load_ctk_logo
from launchpad.crypto import decrypt_text
from launchpad.database import Card
from launchpad.health_format import card_stats_columns
from launchpad.health_metrics import run_remote_metrics
from launchpad.launchers import launch_card
from launchpad.monitor import open_health_dashboard
from launchpad.ssh_utils import resolve_ssh_key
from launchpad.ui.card_widget import GlowCard
from launchpad.ui.stats_snapshot_dialog import StatsSnapshotDialog
from launchpad.ui.colors import normalize_color
from launchpad.ui.theme import get_theme


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

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_filters()
        self.cards_frame = ctk.CTkScrollableFrame(self, fg_color=self.theme["surface"])
        self.cards_frame.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 16))
        for col in range(4):
            self.cards_frame.grid_columnconfigure(col, weight=1)

        self.status_label = ctk.CTkLabel(self, text="", text_color=self.theme["muted"])
        self.status_label.grid(row=3, column=0, sticky="w", padx=28, pady=(0, 12))

        self.hint_label = ctk.CTkLabel(
            self,
            text="",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=11),
        )
        self.hint_label.grid(row=4, column=0, sticky="w", padx=28, pady=(0, 8))

        self.refresh_cards()

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
            text="Refresh Stats",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._fetch_all_ssh_stats,
        ).grid(row=0, column=0, padx=6)

        self.theme_switch = ctk.CTkSwitch(
            actions,
            text="Light mode" if self.theme_name == "dark" else "Dark mode",
            command=self._toggle_theme,
        )
        self.theme_switch.grid(row=0, column=1, padx=6)

        ctk.CTkButton(
            actions,
            text="Admin",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self.on_admin,
        ).grid(row=0, column=2, padx=6)

        ctk.CTkButton(
            actions,
            text="Lock",
            fg_color=self.theme["danger"],
            hover_color="#B91C1C",
            command=self.on_lock,
        ).grid(row=0, column=3, padx=6)

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
        self.status_label.configure(text_color=self.theme["muted"])
        for card in self.card_widgets:
            card.apply_theme(self.theme)
        self.refresh_cards()

    def refresh_cards(self) -> None:
        if self._stats_timer:
            self.after_cancel(self._stats_timer)
            self._stats_timer = None

        for widget in self.cards_frame.winfo_children():
            widget.destroy()
        self.card_widgets.clear()
        self._ssh_cards.clear()

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
        ]

        can_reorder = category == "All" and not query
        self.hint_label.configure(
            text="Drag ⋮⋮ to reorder cards" if can_reorder and filtered else ""
        )

        if not filtered:
            ctk.CTkLabel(
                self.cards_frame,
                text="No cards yet. Open Admin to add SSH, RDP, or Web connections.",
                text_color=self.theme["muted"],
                font=ctk.CTkFont(size=14),
            ).grid(row=0, column=0, columnspan=4, padx=12, pady=24, sticky="w")
            return

        for index, card in enumerate(filtered):
            row, col = divmod(index, 4)
            subtitle = self._card_subtitle(card)
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
                    show_stats=card.card_type == "ssh",
                    on_reorder=self._reorder_cards if can_reorder else None,
                    draggable=can_reorder,
                    dashboard=self,
                    width=260,
                    height=320 if card.card_type == "ssh" else 180,
                )
            except Exception as exc:
                self.status_label.configure(text=f"Could not render card '{card.name}': {exc}")
                continue
            widget.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            self.card_widgets.append(widget)
            if card.card_type == "ssh":
                self._ssh_cards.append(card)

        if self._ssh_cards:
            self.after(400, self._fetch_all_ssh_stats)

    def _ssh_stats_prereq(self, card: Card) -> str | None:
        try:
            key_path = resolve_ssh_key(card, self.crypto_key)
        except OSError as exc:
            return f"SSH key error:\n{exc}"

        if not key_path:
            return "Add SSH key in Admin\nto view stats"

        try:
            key_content = Path(key_path).read_text(encoding="utf-8")
        except OSError as exc:
            return f"Cannot read SSH key:\n{exc}"

        if "ENCRYPTED" in key_content and not self._ssh_key_passphrase(card):
            return "Add SSH key passphrase\nin Admin to view stats"

        return None

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
            if widget:
                widget.set_stats_loading()
            fetchable.append(card)

        if not fetchable:
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
            return decrypt_text(self.crypto_key, card.encrypted_password)
        except ValueError:
            return ""

    def _fetch_ssh_stats_worker(self, card: Card) -> None:
        try:
            reason = self._ssh_stats_prereq(card)
            if reason:
                raise ValueError(reason.replace("\n", " "))
            key_path = resolve_ssh_key(card, self.crypto_key)
            if not key_path:
                raise ValueError("No SSH key configured")
            metrics = run_remote_metrics(
                card.host,
                card.port,
                card.username,
                key_path,
                self._ssh_key_passphrase(card),
            )
            left, right = card_stats_columns(metrics)
            self.after(0, lambda cid=card.id, l=left, r=right: self._apply_card_stats(cid, l, r, None))
        except Exception as exc:
            message = str(exc)
            self.after(0, lambda cid=card.id, msg=message: self._apply_card_stats(cid, [], [], msg))

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
        else:
            widget.set_stats(left, right)

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

    @staticmethod
    def _card_subtitle(card: Card) -> str:
        if card.card_type == "web":
            return card.url or card.host
        port = f":{card.port}" if card.port else ""
        return f"{card.host}{port}"

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

    def _refresh_snapshot(self, card: Card, dialog: StatsSnapshotDialog) -> None:
        dialog.update_stats([], [], "Refreshing...")
        threading.Thread(
            target=self._fetch_snapshot_worker,
            args=(card, dialog),
            daemon=True,
        ).start()

    def _fetch_snapshot_worker(self, card: Card, dialog: StatsSnapshotDialog) -> None:
        try:
            reason = self._ssh_stats_prereq(card)
            if reason:
                raise ValueError(reason.replace("\n", " "))
            key_path = resolve_ssh_key(card, self.crypto_key)
            if not key_path:
                raise ValueError("No SSH key configured")
            metrics = run_remote_metrics(
                card.host,
                card.port,
                card.username,
                key_path,
                self._ssh_key_passphrase(card),
            )
            left, right = card_stats_columns(metrics)
            widget = self._find_card_widget(card.id)
            if widget:
                self.after(0, lambda: widget.set_stats(left, right))
            self.after(0, lambda: dialog.update_stats(left, right, None))
        except Exception as exc:
            self.after(0, lambda msg=str(exc): dialog.update_stats([], [], msg))

    def _monitor_card(self, card: Card) -> None:
        from launchpad.ssh_launcher import _log

        _log(f"Health clicked for card '{card.name}' (id={card.id})")
        try:
            key_path = resolve_ssh_key(card, self.crypto_key)
        except ValueError as exc:
            self.status_label.configure(text=f"Health check failed: {exc}")
            return

        if not key_path:
            self.status_label.configure(text="Health check failed: no SSH key configured.")
            return

        self.status_label.configure(text=f"Fetching health metrics for {card.name}...")
        self.update_idletasks()

        try:
            output = open_health_dashboard(
                card.id,
                card.name,
                card.host,
                card.port,
                card.username,
                key_path,
                self._ssh_key_passphrase(card),
            )
        except Exception as exc:
            _log(f"Health check failed: {exc}")
            self.status_label.configure(text=f"Health check failed for {card.name}: {exc}")
            return

        self.status_label.configure(
            text=f"Added {card.name} to health dashboard. Open {output} or keep the existing tab."
        )
        threading.Thread(target=self._fetch_ssh_stats_worker, args=(card,), daemon=True).start()

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

        if card.card_type == "ssh" and not key_path and not key_passphrase and not password:
            _log("No SSH key or password available")
            self.status_label.configure(
                text="Connect failed: set SSH Key File Path and Passphrase in Admin.",
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
                key_path,
                card.url,
                card.name,
                key_passphrase,
            )
            _log(f"Launch result: {message}")
        except Exception as exc:
            _log(f"Launch exception: {exc}")
            self.status_label.configure(text=f"Connect failed: {exc}")
            return

        if card.card_type == "ssh" and password and not key_path:
            self.clipboard_clear()
            self.clipboard_append(password)
            message = "SSH opened — password copied to clipboard."

        self.status_label.configure(text=message)
        self.update_idletasks()
