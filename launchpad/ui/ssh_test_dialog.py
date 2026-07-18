import customtkinter as ctk

from launchpad.ui.theme import get_theme


class SshTestDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        *,
        theme_name: str,
        card_name: str,
        target_label: str,
        success: bool,
        message: str,
        on_return_admin,
        on_return_dashboard,
    ) -> None:
        super().__init__(master)
        self.theme = get_theme(theme_name)
        self._on_return_admin = on_return_admin
        self._on_return_dashboard = on_return_dashboard

        title = "SSH Login OK" if success else "SSH Login Failed"
        self.title(f"{card_name} — {title}")
        self.configure(fg_color=self.theme["bg"])
        self.resizable(True, True)
        self.minsize(480, 320)
        self.attributes("-topmost", True)
        self.transient(master)
        self.after(200, self.lift)
        self.after(250, self.focus_force)
        self.protocol("WM_DELETE_WINDOW", self._close_admin)

        pad = 24
        frame = ctk.CTkFrame(self, fg_color=self.theme["surface"], corner_radius=16)
        frame.pack(padx=pad, pady=pad, fill="both", expand=True)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        status_color = "#4ade80" if success else self.theme["danger"]
        status_text = "SSH login successful" if success else "SSH login failed"

        ctk.CTkLabel(
            frame,
            text=status_text,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=status_color,
        ).grid(row=0, column=0, padx=20, pady=(20, 6), sticky="w")

        ctk.CTkLabel(
            frame,
            text=f"{card_name}  ·  {target_label}",
            font=ctk.CTkFont(size=13),
            text_color=self.theme["muted"],
            anchor="w",
        ).grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")

        body = ctk.CTkTextbox(
            frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=self.theme["surface_alt"],
            text_color=self.theme["text"],
            wrap="word",
        )
        body.grid(row=2, column=0, padx=20, pady=(0, 12), sticky="nsew")
        body.insert("1.0", message)
        body.configure(state="disabled")

        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")
        buttons.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            buttons,
            text="Return to Admin",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._close_admin,
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkButton(
            buttons,
            text="Return to Dashboard",
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_soft"],
            command=self._go_dashboard,
        ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

        self.update_idletasks()
        width = max(520, self.winfo_reqwidth())
        height = max(360, self.winfo_reqheight())
        x = master.winfo_rootx() + (master.winfo_width() - width) // 2
        y = master.winfo_rooty() + (master.winfo_height() - height) // 2
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    def _close_admin(self) -> None:
        try:
            self.attributes("-topmost", False)
        except Exception:
            pass
        self.destroy()
        if self._on_return_admin:
            self._on_return_admin()

    def _go_dashboard(self) -> None:
        try:
            self.attributes("-topmost", False)
        except Exception:
            pass
        self.destroy()
        if self._on_return_dashboard:
            self._on_return_dashboard()
