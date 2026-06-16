import customtkinter as ctk

from launchpad.branding import window_title
from launchpad.database import Database
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

        self.title(window_title(self.db))
        self.geometry("1200x780")
        self.minsize(960, 640)

        theme_name = self.db.get_setting("theme", "dark")
        self.apply_theme(theme_name)
        self._show_login()

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
        self._show_dashboard()

    def _show_dashboard(self) -> None:
        self._clear_view()
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
