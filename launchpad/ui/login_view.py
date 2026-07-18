import customtkinter as ctk

from launchpad.branding import get_app_name, load_ctk_logo_large
from launchpad.config import APP_VERSION
from launchpad.crypto import generate_salt, hash_password
from launchpad.ui.theme import get_theme


class LoginView(ctk.CTkFrame):
    def __init__(self, master, db, on_success, on_setup) -> None:
        super().__init__(master, fg_color="transparent")
        self.db = db
        self.on_success = on_success
        self.on_setup = on_setup
        self.theme = get_theme(self.db.get_setting("theme", "dark"))
        self._logo_image = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        panel = ctk.CTkFrame(self, fg_color=self.theme["surface"], corner_radius=20)
        panel.grid(row=0, column=0, padx=40, pady=40, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)

        brand_row = ctk.CTkFrame(panel, fg_color="transparent")
        brand_row.grid(row=0, column=0, padx=32, pady=(32, 8))

        self._logo_image = load_ctk_logo_large(self.db, max_height=56)
        if self._logo_image:
            ctk.CTkLabel(brand_row, text="", image=self._logo_image).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            brand_row,
            text=get_app_name(self.db),
            font=ctk.CTkFont(size=34, weight="bold"),
            text_color=self.theme["accent"],
        ).pack(side="left")

        ctk.CTkLabel(
            panel,
            text=f"Secure connection dashboard  ·  v{APP_VERSION}",
            font=ctk.CTkFont(size=14),
            text_color=self.theme["muted"],
        ).grid(row=1, column=0, padx=32, pady=(0, 24))

        if not self.db.is_initialized():
            self._build_setup_form(panel)
        else:
            self._build_login_form(panel)

    def _build_login_form(self, panel) -> None:
        self.password_entry = ctk.CTkEntry(
            panel,
            placeholder_text="Master password",
            show="*",
            width=320,
            height=42,
        )
        self.password_entry.grid(row=2, column=0, padx=32, pady=(0, 12))
        self.password_entry.bind("<Return>", lambda _e: self._login())

        self.error_label = ctk.CTkLabel(panel, text="", text_color=self.theme["danger"])
        self.error_label.grid(row=3, column=0, padx=32, pady=(0, 8))

        ctk.CTkButton(
            panel,
            text="Unlock Dashboard",
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_soft"],
            height=42,
            command=self._login,
        ).grid(row=4, column=0, padx=32, pady=(0, 32), sticky="ew")

    def _build_setup_form(self, panel) -> None:
        ctk.CTkLabel(
            panel,
            text="First-time setup",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.theme["text"],
        ).grid(row=2, column=0, padx=32, pady=(0, 12))

        self.master_entry = ctk.CTkEntry(panel, placeholder_text="Master password", show="*", width=320, height=40)
        self.master_entry.grid(row=3, column=0, padx=32, pady=4)

        self.master_confirm = ctk.CTkEntry(panel, placeholder_text="Confirm master password", show="*", width=320, height=40)
        self.master_confirm.grid(row=4, column=0, padx=32, pady=4)

        self.admin_entry = ctk.CTkEntry(panel, placeholder_text="Admin password", show="*", width=320, height=40)
        self.admin_entry.grid(row=5, column=0, padx=32, pady=4)

        self.admin_confirm = ctk.CTkEntry(panel, placeholder_text="Confirm admin password", show="*", width=320, height=40)
        self.admin_confirm.grid(row=6, column=0, padx=32, pady=4)

        self.error_label = ctk.CTkLabel(panel, text="", text_color=self.theme["danger"])
        self.error_label.grid(row=7, column=0, padx=32, pady=(8, 8))

        ctk.CTkButton(
            panel,
            text="Create Vault",
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_soft"],
            height=42,
            command=self._create_vault,
        ).grid(row=8, column=0, padx=32, pady=(0, 32), sticky="ew")

    def _login(self) -> None:
        from launchpad.crypto import verify_password, derive_key

        password = self.password_entry.get()
        salt = self.db.get_setting("master_salt")
        stored_hash = self.db.get_setting("master_hash")
        if not verify_password(password, salt, stored_hash):
            self.error_label.configure(text="Incorrect master password.")
            return
        self.on_success(derive_key(password, salt))

    def _create_vault(self) -> None:
        master = self.master_entry.get()
        master_confirm = self.master_confirm.get()
        admin = self.admin_entry.get()
        admin_confirm = self.admin_confirm.get()

        if len(master) < 8:
            self.error_label.configure(text="Master password must be at least 8 characters.")
            return
        if master != master_confirm:
            self.error_label.configure(text="Master passwords do not match.")
            return
        if len(admin) < 8:
            self.error_label.configure(text="Admin password must be at least 8 characters.")
            return
        if admin != admin_confirm:
            self.error_label.configure(text="Admin passwords do not match.")
            return

        master_salt = generate_salt()
        admin_salt = generate_salt()
        self.db.set_setting("master_salt", master_salt)
        self.db.set_setting("master_hash", hash_password(master, master_salt))
        self.db.set_setting("admin_salt", admin_salt)
        self.db.set_setting("admin_hash", hash_password(admin, admin_salt))
        self.db.set_setting("theme", "dark")
        self.db.set_setting("initialized", "true")
        self.on_setup()
