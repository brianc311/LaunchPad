import customtkinter as ctk

from launchpad.icons import resolve_icon
from launchpad.ui.colors import ctk_color, normalize_color


class GlowCard(ctk.CTkFrame):
    def __init__(
        self,
        master,
        theme: dict,
        name: str,
        card_type: str,
        subtitle: str,
        glow_color: str,
        icon: str,
        card_id: int,
        on_click,
        on_health=None,
        on_snapshot=None,
        show_stats: bool = False,
        on_reorder=None,
        draggable: bool = False,
        dashboard=None,
        **kwargs,
    ) -> None:
        self.glow_color = normalize_color(glow_color)
        glow = ctk_color(self.glow_color)
        super().__init__(
            master,
            fg_color=theme["surface_alt"],
            corner_radius=16,
            border_width=2,
            border_color=theme["border"],
            **kwargs,
        )
        self.theme = theme
        self.on_click = on_click
        self.on_health = on_health
        self.on_snapshot = on_snapshot
        self.on_reorder = on_reorder
        self.card_id = card_id
        self.draggable = draggable
        self.dashboard = dashboard
        self._hovering = False
        self._dragging = False
        self._stats_left_lines: list[str] = []
        self._stats_right_lines: list[str] = []
        self._stats_error: str | None = None

        self.grid_columnconfigure(0, weight=1)
        stats_row = 3 if show_stats else 2
        btn_row_idx = stats_row + 1
        self.grid_rowconfigure(stats_row, weight=1)

        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.grid(row=0, column=0, padx=18, pady=(18, 4), sticky="ew")
        top_row.grid_columnconfigure(1, weight=1)

        icon_text = resolve_icon(icon, card_type)
        self.icon_label = ctk.CTkLabel(
            top_row,
            text=icon_text,
            font=ctk.CTkFont(size=28),
            text_color=glow,
            width=36,
        )
        self.icon_label.grid(row=0, column=0, sticky="w")

        self.type_badge = ctk.CTkLabel(
            top_row,
            text=card_type.upper(),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme["bg"],
            fg_color=glow,
            corner_radius=8,
            width=52,
            height=22,
        )
        self.type_badge.grid(row=0, column=2, sticky="e")

        if draggable:
            self.drag_handle = ctk.CTkLabel(
                top_row,
                text="::",
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=theme["muted"],
                width=24,
                cursor="hand2",
            )
            self.drag_handle.grid(row=0, column=1, sticky="e", padx=(8, 8))
            self.drag_handle.bind("<Button-1>", self._start_drag)
            self.drag_handle.bind("<B1-Motion>", self._on_drag)
            self.drag_handle.bind("<ButtonRelease-1>", self._end_drag)

        self.name_label = ctk.CTkLabel(
            self,
            text=name,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme["text"],
            anchor="w",
        )
        self.name_label.grid(row=1, column=0, padx=18, pady=(0, 4), sticky="ew")

        self.subtitle_label = ctk.CTkLabel(
            self,
            text=subtitle,
            font=ctk.CTkFont(size=12),
            text_color=theme["muted"],
            anchor="w",
        )
        self.subtitle_label.grid(row=2, column=0, padx=18, pady=(0, 4), sticky="ew")

        self.show_stats = show_stats
        if show_stats:
            self.stats_frame = ctk.CTkFrame(self, fg_color=theme["surface"], corner_radius=10)
            self.stats_frame.grid(row=stats_row, column=0, padx=14, pady=(0, 8), sticky="ew")
            self.stats_frame.grid_columnconfigure(0, weight=1)
            self.stats_frame.grid_columnconfigure(1, weight=1)

            stat_font = ctk.CTkFont(family="Consolas", size=10)
            self.stats_left = ctk.CTkLabel(
                self.stats_frame,
                text="Stats not loaded yet",
                font=stat_font,
                text_color=theme["muted"],
                anchor="nw",
                justify="left",
            )
            self.stats_left.grid(row=0, column=0, padx=(10, 6), pady=8, sticky="nw")

            self.stats_right = ctk.CTkLabel(
                self.stats_frame,
                text="",
                font=stat_font,
                text_color=theme["text"],
                anchor="nw",
                justify="left",
            )
            self.stats_right.grid(row=0, column=1, padx=(6, 10), pady=8, sticky="nw")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=btn_row_idx, column=0, padx=18, pady=(0, 8), sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)
        if on_health:
            btn_row.grid_columnconfigure(1, weight=1)

        self.connect_btn = ctk.CTkButton(
            btn_row,
            text="Connect",
            fg_color=self.glow_color,
            hover_color=theme["accent_soft"],
            height=32,
            command=self._connect,
        )
        self.connect_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6 if on_health else 0))

        if on_health:
            self.health_btn = ctk.CTkButton(
                btn_row,
                text="Health",
                fg_color=theme["surface"],
                hover_color=theme["border"],
                border_width=1,
                border_color=self.glow_color,
                text_color=self.glow_color,
                height=32,
                command=self._health,
            )
            self.health_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        if on_snapshot:
            self.snapshot_btn = ctk.CTkButton(
                self,
                text="Stats Snapshot",
                fg_color=theme["surface"],
                hover_color=theme["border"],
                border_width=1,
                border_color=theme["muted"],
                text_color=theme["text"],
                height=28,
                command=self._snapshot,
            )
            self.snapshot_btn.grid(row=btn_row_idx + 1, column=0, padx=18, pady=(0, 14), sticky="ew")

        interactive = [self, top_row, self.icon_label, self.name_label, self.subtitle_label]
        if show_stats:
            interactive.extend([self.stats_frame, self.stats_left, self.stats_right])
        for widget in interactive:
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            widget.bind("<ButtonRelease-1>", self._handle_click)
            try:
                widget.configure(cursor="hand2")
            except Exception:
                pass

        self.type_badge.bind("<ButtonRelease-1>", self._handle_click)
        try:
            self.type_badge.configure(cursor="hand2")
        except Exception:
            pass

        if hasattr(self, "drag_handle"):
            self.drag_handle.configure(cursor="fleur")

    def _board(self):
        return self.dashboard

    def _start_drag(self, event) -> str:
        if not self.draggable:
            return "break"
        self._dragging = True
        self.configure(border_color=ctk_color(self.glow_color), border_width=4)
        return "break"

    def _on_drag(self, event) -> str:
        if not self._dragging:
            return "break"
        target = self._find_drop_target(event.x_root, event.y_root)
        board = self._board()
        if board and hasattr(board, "highlight_drop_target"):
            board.highlight_drop_target(target)
        return "break"

    def _end_drag(self, event) -> str:
        if not self._dragging:
            return "break"
        self._dragging = False
        target = self._find_drop_target(event.x_root, event.y_root)
        board = self._board()
        if board and hasattr(board, "clear_drop_highlights"):
            board.clear_drop_highlights()
        if target and target.card_id != self.card_id and self.on_reorder:
            self.on_reorder(self.card_id, target.card_id)
        elif not self._hovering:
            self.configure(border_color=self.theme["border"], border_width=2)
        return "break"

    def _find_drop_target(self, x_root: int, y_root: int):
        board = self._board()
        if not board or not hasattr(board, "card_widgets"):
            return None
        for widget in board.card_widgets:
            if widget is self or not widget.winfo_exists():
                continue
            x1 = widget.winfo_rootx()
            y1 = widget.winfo_rooty()
            x2 = x1 + widget.winfo_width()
            y2 = y1 + widget.winfo_height()
            if x1 <= x_root <= x2 and y1 <= y_root <= y2:
                return widget
        return None

    def _on_enter(self, _event=None) -> None:
        if self._dragging:
            return
        self._hovering = True
        self.configure(border_color=ctk_color(self.glow_color), border_width=3)

    def _on_leave(self, _event=None) -> None:
        if self._dragging:
            return
        self._hovering = False
        self.configure(border_color=self.theme["border"], border_width=2)

    def _connect(self) -> None:
        self.configure(border_color=ctk_color(self.glow_color), border_width=4)
        self.after(120, lambda: self.configure(border_width=3 if self._hovering else 2))
        self.on_click()

    def _health(self) -> None:
        if self.on_health:
            self.on_health()

    def _snapshot(self) -> None:
        if self.on_snapshot:
            self.on_snapshot()

    def get_stats_snapshot(self) -> tuple[list[str], list[str], str | None]:
        return self._stats_left_lines, self._stats_right_lines, self._stats_error

    def _handle_click(self, event=None) -> None:
        if self._dragging:
            return
        if event and getattr(event, "widget", None) is getattr(self, "drag_handle", None):
            return
        self.configure(border_color=ctk_color(self.glow_color), border_width=4)
        self.after(120, lambda: self.configure(border_width=3 if self._hovering else 2))
        self.on_click()

    def set_drop_highlight(self, active: bool) -> None:
        if active:
            self.configure(border_color=ctk_color(self.glow_color), border_width=4)
        elif not self._hovering and not self._dragging:
            self.configure(border_color=self.theme["border"], border_width=2)

    def set_stats_loading(self) -> None:
        if not self.show_stats:
            return
        self.stats_left.configure(text="Refreshing stats...", text_color=self.theme["muted"])
        self.stats_right.configure(text="")

    def set_stats_prompt(self, message: str) -> None:
        if not self.show_stats:
            return
        self.stats_left.configure(text=message, text_color=self.theme["muted"])
        self.stats_right.configure(text="")

    def set_stats(self, left_lines: list[str], right_lines: list[str]) -> None:
        if not self.show_stats:
            return
        self._stats_left_lines = left_lines
        self._stats_right_lines = right_lines
        self._stats_error = None
        self.stats_left.configure(text="\n".join(left_lines), text_color="#4ade80")
        self.stats_right.configure(text="\n".join(right_lines), text_color="#4ade80")

    def set_stats_error(self, message: str) -> None:
        if not self.show_stats:
            return
        self._stats_error = message
        self._stats_left_lines = []
        self._stats_right_lines = []
        short = message.splitlines()[0][:48]
        self.stats_left.configure(text="Stats unavailable", text_color=self.theme["muted"])
        self.stats_right.configure(text=short, text_color=self.theme["danger"])

    def apply_theme(self, theme: dict) -> None:
        self.theme = theme
        self.configure(fg_color=theme["surface_alt"], border_color=theme["border"])
        self.name_label.configure(text_color=theme["text"])
        self.subtitle_label.configure(text_color=theme["muted"])
        self.type_badge.configure(text_color=theme["bg"])
        if hasattr(self, "drag_handle"):
            self.drag_handle.configure(text_color=theme["muted"])
        if self.show_stats:
            self.stats_frame.configure(fg_color=theme["surface"])
