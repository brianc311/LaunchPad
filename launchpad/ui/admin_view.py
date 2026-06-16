import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog, messagebox

from launchpad.backup import read_backup_file, write_backup_file
from launchpad.branding import (
    clear_logo,
    get_app_name,
    load_ctk_logo_large,
    logo_path,
    save_app_name,
    save_logo,
)
from launchpad.config import CARD_TYPES, DEFAULT_APP_NAME, DEFAULT_GLOW_COLOR
from launchpad.crypto import decrypt_text, encrypt_text, verify_password
from launchpad.icons import ICON_CHOICES, resolve_icon
from launchpad.ssh_utils import normalize_key_file_path
from launchpad.ui.colors import normalize_color
from launchpad.ui.theme import get_theme


class AdminView(ctk.CTkFrame):
    def __init__(self, master, db, crypto_key, on_back) -> None:
        super().__init__(master, fg_color="transparent")
        self.db = db
        self.crypto_key = crypto_key
        self.on_back = on_back
        self.theme = get_theme(self.db.get_setting("theme", "dark"))
        self.editing_id: int | None = None
        self._authenticated = False

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
            text="Admin Dashboard",
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

        self._build_card_list(connections_tab)
        self._build_card_form(connections_tab)
        self._build_branding_panel(branding_tab)
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
            ("Host", "host"),
            ("Port", "port"),
            ("Username", "username"),
            ("SSH Key File Path", "key_file_path"),
            ("SSH Key Passphrase", "password"),
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
            show = "*" if key == "password" else None
            entry = ctk.CTkEntry(scroll, show=show)
            entry.grid(row=row, column=1, padx=8, pady=6, sticky="ew")
            self.entries[key] = entry
            if key == "key_file_path":
                entry.configure(placeholder_text=str(Path.home() / ".ssh" / "wcelease_ed25519"))
            if key == "password":
                entry.configure(placeholder_text="Enter key passphrase — stored masked in vault")

        ctk.CTkLabel(
            scroll,
            text="Use key file path + passphrase, or paste private key above.",
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

        self.entries["glow_color"].insert(0, DEFAULT_GLOW_COLOR)
        self.entries["category"].insert(0, "General")
        self.entries["sort_order"].insert(0, "0")
        self._set_form_mode(editing=False)

    def _update_icon_preview(self, *_args) -> None:
        key = self.icon_var.get()
        self.icon_preview.configure(text=ICON_CHOICES.get(key, "●"))

    def refresh_list(self) -> None:
        if not hasattr(self, "list_box"):
            return
        for child in self.list_box.winfo_children():
            child.destroy()
        for card in self.db.list_cards():
            row = ctk.CTkFrame(self.list_box, fg_color=self.theme["surface_alt"], corner_radius=10)
            row.grid(sticky="ew", padx=4, pady=4)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row,
                text=resolve_icon(card.icon, card.card_type),
                font=ctk.CTkFont(size=20),
                width=32,
            ).grid(row=0, column=0, padx=(10, 4), pady=8)

            ctk.CTkLabel(
                row,
                text=f"{card.name}  [{card.card_type.upper()}]",
                text_color=self.theme["text"],
            ).grid(row=0, column=1, padx=4, pady=8, sticky="w")

            ctk.CTkButton(
                row,
                text="Edit",
                width=60,
                command=lambda cid=card.id: self._load_card(cid),
            ).grid(row=0, column=2, padx=(8, 4), pady=8)

            ctk.CTkButton(
                row,
                text="Delete",
                width=60,
                fg_color=self.theme["danger"],
                hover_color="#B91C1C",
                command=lambda cid=card.id, cname=card.name: self._delete_card_by_id(cid, cname),
            ).grid(row=0, column=3, padx=(4, 8), pady=8)

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
        if defaults:
            self.entries["glow_color"].insert(0, DEFAULT_GLOW_COLOR)
            self.entries["category"].insert(0, "General")
            self.entries["sort_order"].insert(0, "0")
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
        self.entries["host"].insert(0, card.host)
        if card.port is not None:
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
            self.entries["password"].insert(0, decrypt_text(self.crypto_key, card.encrypted_password))
        if card.encrypted_key:
            self.entries["ssh_key"].insert(0, decrypt_text(self.crypto_key, card.encrypted_key))

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
        port = int(port_raw) if port_raw else None
        sort_raw = self.entries["sort_order"].get().strip()
        sort_order = int(sort_raw) if sort_raw else 0

        password = self.entries["password"].get()
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
            "username": self.entries["username"].get().strip(),
            "encrypted_password": encrypt_text(self.crypto_key, password),
            "encrypted_key": encrypt_text(self.crypto_key, ssh_key),
            "url": url,
            "category": self.entries["category"].get().strip() or "General",
            "sort_order": sort_order,
            "glow_color": normalize_color(self.entries["glow_color"].get().strip(), DEFAULT_GLOW_COLOR),
            "icon": self.icon_var.get(),
            "key_file_path": key_path,
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
            write_backup_file(path, self.crypto_key, cards)
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
            count = self.db.import_cards(cards, mode=mode)
            self.refresh_list()
            messagebox.showinfo("Admin", f"Imported {count} card(s) successfully.")
        except Exception as exc:
            messagebox.showerror("Admin", f"Import failed: {exc}")

    def apply_theme(self, theme_name: str) -> None:
        self.theme = get_theme(theme_name)
