import customtkinter as ctk
import webbrowser

from launchpad.branding import window_title
from launchpad.crypto import decrypt_text
from launchpad.database import Database
from launchpad.host_volume_health import resolve_gui_url
from launchpad.launchers import launch_card
from launchpad.mouse_jiggler import (
    SETTING_MOUSE_JIGGLER,
    MouseJiggler,
    setting_to_enabled,
)
from launchpad.ssh_utils import resolve_ssh_key
from launchpad.ui.admin_view import AdminView
from launchpad.ui.dashboard_view import DashboardView
from launchpad.ui.login_view import LoginView
from launchpad.ui.theme import get_theme


class LaunchPadApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.db = Database()
        self.crypto_key: bytes | None = None
        self.current_view = None
        self._mouse_jiggler = MouseJiggler()

        self.title(window_title(self.db))
        self.geometry("1200x780")
        self.minsize(960, 640)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        theme_name = self.db.get_setting("theme", "dark")
        self.apply_theme(theme_name)
        self._sync_mouse_jiggler_from_db()
        self._show_login()

    def _sync_mouse_jiggler_from_db(self) -> None:
        enabled = setting_to_enabled(self.db.get_setting(SETTING_MOUSE_JIGGLER, ""))
        self._mouse_jiggler.set_enabled(enabled)

    def set_mouse_jiggler_enabled(self, enabled: bool) -> None:
        self._mouse_jiggler.set_enabled(enabled)

    def _on_close(self) -> None:
        self.destroy()

    def destroy(self) -> None:
        self._mouse_jiggler.stop()
        super().destroy()

    def apply_theme(self, theme_name: str) -> None:
        theme = get_theme(theme_name)
        ctk.set_appearance_mode(theme["mode"])
        ctk.set_default_color_theme("dark-blue")
        self.configure(fg_color=theme["bg"])
        if isinstance(self.current_view, (DashboardView, AdminView)):
            self.current_view.apply_theme(theme_name)

    def _clear_view(self) -> None:
        if self.current_view:
            self.current_view.destroy()
            self.current_view = None

    def _show_login(self) -> None:
        self._clear_view()
        self.crypto_key = None
        self._wire_health_sync()
        self.current_view = LoginView(
            self,
            self.db,
            on_success=self._on_unlock,
            on_setup=self._show_login,
        )
        self.current_view.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def _on_unlock(self, crypto_key: bytes) -> None:
        self.crypto_key = crypto_key
        self._wire_health_sync()
        self._show_dashboard()

    def _wire_health_sync(self) -> None:
        from launchpad.health_server import get_health_server
        from launchpad.monitor import ensure_health_dashboard_registered

        if not self.crypto_key:
            get_health_server().set_sync_provider(None)
            get_health_server().set_settings_backend(None, None)
            get_health_server().set_card_patcher(None)
            get_health_server().set_card_launch_backend(None, None)
            get_health_server().clear_cards()
            return

        crypto_key = self.crypto_key
        db = self.db

        def provider() -> int:
            return ensure_health_dashboard_registered(db, crypto_key)

        def connect_card(card_id: int) -> str:
            card = db.get_card(card_id)
            if card is None:
                raise ValueError(f"Unknown card id {card_id}")
            try:
                password = decrypt_text(crypto_key, card.encrypted_password)
                decrypt_text(crypto_key, card.encrypted_key)
            except ValueError as exc:
                raise ValueError(f"Connect failed: {exc}") from exc
            try:
                key_path = resolve_ssh_key(card, crypto_key) if card.card_type == "ssh" else ""
            except OSError as exc:
                raise ValueError(f"Connect failed: {exc}") from exc
            key_passphrase = ""
            if card.card_type == "ssh":
                try:
                    key_passphrase = decrypt_text(crypto_key, card.encrypted_key_passphrase)
                except ValueError:
                    key_passphrase = ""
            if card.card_type == "ssh" and not key_path and not password:
                raise ValueError("Connect failed: set SSH Password or a key in Admin.")
            return launch_card(
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

        def open_card_gui(card_id: int) -> str:
            card = db.get_card(card_id)
            if card is None:
                raise ValueError(f"Unknown card id {card_id}")
            url = resolve_gui_url(card.url, card.host, card.device_profile)
            if not url:
                raise ValueError(
                    "No GUI URL or host on this card — set URL or Host in Admin."
                )
            webbrowser.open(url)
            return "Opened GUI"

        def patch_card(
            card_id: int, *, host: str | None = None, name: str | None = None
        ) -> dict:
            card = db.get_card(card_id)
            if card is None:
                raise ValueError(f"Unknown card id {card_id}")
            data = {
                "name": name if name is not None else card.name,
                "card_type": card.card_type,
                "host": host if host is not None else card.host,
                "port": card.port,
                "serial_number": card.serial_number,
                "username": card.username,
                "encrypted_password": card.encrypted_password,
                "encrypted_key_passphrase": card.encrypted_key_passphrase,
                "encrypted_key": card.encrypted_key,
                "url": card.url,
                "icon": card.icon,
                "category": card.category,
                "sort_order": card.sort_order,
                "glow_color": card.glow_color,
                "key_file_path": card.key_file_path,
                "device_profile": card.device_profile,
                "custom_commands": card.custom_commands,
            }
            db.update_card(card_id, data)
            return {
                "card_id": card_id,
                "host": data["host"],
                "name": data["name"],
            }

        get_health_server().set_sync_provider(provider)
        get_health_server().set_settings_backend(
            db.get_setting, db.set_setting, crypto_key=crypto_key
        )
        get_health_server().set_card_patcher(patch_card)
        get_health_server().set_card_launch_backend(connect_card, open_card_gui)

    def _show_dashboard(self) -> None:
        self._clear_view()
        self._sync_mouse_jiggler_from_db()
        self.title(window_title(self.db))
        try:
            self.current_view = DashboardView(
                self,
                self.db,
                self.crypto_key,
                on_admin=self._show_admin,
                on_lock=self._show_login,
            )
            self.current_view.grid(row=0, column=0, sticky="nsew")
            self.update_idletasks()
        except Exception as exc:
            from tkinter import messagebox

            messagebox.showerror("LaunchPad", f"Failed to open dashboard:\n{exc}")
            self._show_login()

    def _show_admin(self) -> None:
        self._clear_view()
        self.current_view = AdminView(
            self,
            self.db,
            self.crypto_key,
            on_back=self._show_dashboard,
        )
        self.current_view.grid(row=0, column=0, sticky="nsew")
