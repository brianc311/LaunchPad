import customtkinter as ctk
from datetime import datetime

from launchpad.ui.theme import get_theme


class StatsSnapshotDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        *,
        theme_name: str,
        card_name: str,
        subtitle: str,
        left_lines: list[str],
        right_lines: list[str],
        error: str | None = None,
        on_refresh=None,
    ) -> None:
        super().__init__(master)
        self.theme = get_theme(theme_name)
        self.on_refresh = on_refresh
        self._left_lines = left_lines
        self._right_lines = right_lines
        self._error = error

        self.title(f"{card_name} — Stats")
        self.configure(fg_color=self.theme["bg"])
        self.resizable(True, True)
        self.minsize(520, 320)
        self.attributes("-topmost", True)
        self.after(200, self.lift)

        pad = 24
        frame = ctk.CTkFrame(self, fg_color=self.theme["surface"], corner_radius=16)
        frame.pack(padx=pad, pady=pad, fill="both", expand=True)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 8))

        ctk.CTkLabel(
            header,
            text=card_name,
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=self.theme["accent"],
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            header,
            text=subtitle,
            font=ctk.CTkFont(size=13),
            text_color=self.theme["muted"],
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        self.timestamp_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=self.theme["muted"],
            anchor="w",
        )
        self.timestamp_label.pack(fill="x", pady=(6, 0))

        stats_box = ctk.CTkFrame(frame, fg_color=self.theme["surface_alt"], corner_radius=12)
        stats_box.pack(fill="both", expand=True, padx=20, pady=(8, 12))
        stats_box.grid_columnconfigure(0, weight=1)
        stats_box.grid_columnconfigure(1, weight=1)

        stat_font = ctk.CTkFont(family="Consolas", size=12)
        self.stats_left = ctk.CTkLabel(
            stats_box,
            text="",
            font=stat_font,
            text_color="#4ade80",
            anchor="nw",
            justify="left",
        )
        self.stats_left.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nw")

        self.stats_right = ctk.CTkLabel(
            stats_box,
            text="",
            font=stat_font,
            text_color="#4ade80",
            anchor="nw",
            justify="left",
        )
        self.stats_right.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nw")

        self._render_stats()

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(0, 20))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        if on_refresh:
            ctk.CTkButton(
                actions,
                text="Refresh",
                fg_color=self.theme["surface_alt"],
                hover_color=self.theme["border"],
                command=self._refresh,
            ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkButton(
            actions,
            text="Close",
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_soft"],
            command=self.destroy,
        ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

        self.update_idletasks()
        self.geometry(f"{max(640, self.winfo_reqwidth())}x{max(420, self.winfo_reqheight())}")

    def _render_stats(self) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.timestamp_label.configure(text=f"Captured: {stamp}")

        if self._error:
            self.stats_left.configure(text="Stats unavailable", text_color=self.theme["muted"])
            self.stats_right.configure(text=self._error[:120], text_color=self.theme["danger"])
            return

        if not self._left_lines and not self._right_lines:
            self.stats_left.configure(
                text="No stats loaded yet.\nClick Refresh to fetch.",
                text_color=self.theme["muted"],
            )
            self.stats_right.configure(text="")
            return

        self.stats_left.configure(text="\n".join(self._left_lines), text_color="#4ade80")
        self.stats_right.configure(text="\n".join(self._right_lines), text_color="#4ade80")

    def update_stats(self, left_lines: list[str], right_lines: list[str], error: str | None = None) -> None:
        self._left_lines = left_lines
        self._right_lines = right_lines
        self._error = error
        self._render_stats()

    def _refresh(self) -> None:
        if self.on_refresh:
            self.on_refresh(self)
