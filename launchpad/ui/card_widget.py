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
        on_monitor_change=None,
        monitor_enabled: bool = False,
        show_stats: bool = False,
        on_reorder=None,
        draggable: bool = False,
        dashboard=None,
        collapsed: bool = True,
        on_selection_change=None,
        on_collapsed_change=None,
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
        self.on_monitor_change = on_monitor_change
        self._monitor_enabled = monitor_enabled
        self.on_reorder = on_reorder
        self.on_selection_change = on_selection_change
        self.on_collapsed_change = on_collapsed_change
        self.card_id = card_id
        self.draggable = draggable
        self.dashboard = dashboard
        self._hovering = False
        self._dragging = False
        self._collapsed: bool | None = None
        self._stats_left_lines: list[str] = []
        self._stats_right_lines: list[str] = []
        self._stats_error: str | None = None

        self.grid_columnconfigure(0, weight=1)
        stats_row = 3 if show_stats else 2
        btn_row_idx = stats_row + 1
        self._stats_row = stats_row
        self._btn_row_idx = btn_row_idx
        self._monitor_row_idx = btn_row_idx + 1 if on_monitor_change else None
        self._snapshot_row_idx = btn_row_idx + (2 if on_monitor_change else 1)
        self.grid_rowconfigure(stats_row, weight=1)

        self.top_row = ctk.CTkFrame(self, fg_color="transparent")
        self.top_row.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        self.top_row.grid_columnconfigure(2, weight=1)
        top_row = self.top_row

        self.select_var = ctk.BooleanVar(value=False)
        self.select_cb = ctk.CTkCheckBox(
            top_row,
            text="",
            variable=self.select_var,
            width=24,
            checkbox_width=20,
            checkbox_height=20,
            command=self._notify_selection,
        )
        self.select_cb.grid(row=0, column=0, sticky="w", padx=(0, 6))

        icon_text = resolve_icon(icon, card_type)
        self.icon_label = ctk.CTkLabel(
            top_row,
            text=icon_text,
            font=ctk.CTkFont(size=22),
            text_color=glow,
            width=30,
        )
        self.icon_label.grid(row=0, column=1, sticky="w")

        self.name_label = ctk.CTkLabel(
            top_row,
            text=name,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme["text"],
            anchor="w",
            justify="left",
            wraplength=280,
        )
        self.name_label.grid(row=0, column=2, sticky="ew", padx=(6, 0))

        self.expand_btn = ctk.CTkButton(
            top_row,
            text="▼",
            width=30,
            height=28,
            fg_color=theme["surface"],
            hover_color=theme["border"],
            text_color=theme["muted"],
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.toggle_collapsed,
        )
        self.expand_btn.grid(row=0, column=3, sticky="e", padx=(4, 4))

        self.type_badge = ctk.CTkLabel(
            top_row,
            text=card_type.upper(),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=theme["bg"],
            fg_color=glow,
            corner_radius=8,
            width=48,
            height=20,
        )
        self.type_badge.grid(row=0, column=4, sticky="e")

        if draggable:
            self.drag_handle = ctk.CTkLabel(
                top_row,
                text="::",
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=theme["muted"],
                width=20,
                cursor="hand2",
            )
            self.drag_handle.grid(row=0, column=5, sticky="e", padx=(6, 0))
            self.drag_handle.bind("<Button-1>", self._start_drag)
            self.drag_handle.bind("<B1-Motion>", self._on_drag)
            self.drag_handle.bind("<ButtonRelease-1>", self._end_drag)
            self.drag_handle.configure(cursor="fleur")

        self.compact_bottom_row = ctk.CTkFrame(self, fg_color="transparent")
        self.compact_bottom_row.grid_columnconfigure(0, weight=1)

        self.bottom_left = ctk.CTkFrame(self.compact_bottom_row, fg_color="transparent")
        self.bottom_left.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.bottom_left.grid_columnconfigure(1, weight=1)

        if show_stats:
            self.status_led = ctk.CTkFrame(
                self.bottom_left,
                width=10,
                height=10,
                corner_radius=5,
                fg_color="#6b7280",
            )
            self.status_led.grid(row=0, column=0, padx=(0, 6), pady=3, sticky="w")
            self.status_led.grid_propagate(False)
            self._ssh_status = "unknown"
            self._ssh_status_tip = "SSH status not checked yet"
            self._status_tip = None
            self._status_tip_after = None
            self.status_led.bind("<Enter>", self._on_status_led_enter)
            self.status_led.bind("<Leave>", self._hide_status_tip)
            self.bind("<Destroy>", lambda _e: self._hide_status_tip(), add="+")
        else:
            self.status_led = None
            self._ssh_status = ""
            self._ssh_status_tip = ""

        self.subtitle_label = ctk.CTkLabel(
            self.bottom_left,
            text=subtitle,
            font=ctk.CTkFont(size=11),
            text_color=theme["muted"],
            anchor="w",
        )
        self.subtitle_label.grid(row=0, column=1, sticky="ew")

        self.compact_expand_btn = ctk.CTkButton(
            self.compact_bottom_row,
            text="▶",
            width=30,
            height=26,
            fg_color=theme["surface"],
            hover_color=theme["border"],
            text_color=theme["muted"],
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.toggle_collapsed,
        )
        self.compact_expand_btn.grid(row=0, column=1, sticky="e", padx=(0, 6))

        self.compact_connect_btn = ctk.CTkButton(
            self.compact_bottom_row,
            text="Connect",
            width=76,
            height=26,
            fg_color=self.glow_color,
            hover_color=theme["accent_soft"],
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._connect,
        )
        self.compact_connect_btn.grid(row=0, column=2, sticky="e")

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
        self.btn_row = btn_row
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

        if on_monitor_change:
            self.monitor_row = ctk.CTkFrame(self, fg_color="transparent")
            self.monitor_row.grid(row=self._monitor_row_idx, column=0, padx=18, pady=(0, 6), sticky="ew")
            self.monitor_var = ctk.BooleanVar(value=monitor_enabled)
            self.monitor_switch = ctk.CTkSwitch(
                self.monitor_row,
                text="Monitor SSH",
                variable=self.monitor_var,
                command=self._on_monitor_toggle,
                font=ctk.CTkFont(size=12),
            )
            self.monitor_switch.pack(side="left")
            self.monitor_hint = ctk.CTkLabel(
                self.monitor_row,
                text="Off — no background SSH" if not monitor_enabled else "On — stats refresh allowed",
                font=ctk.CTkFont(size=11),
                text_color=theme["muted"],
            )
            self.monitor_hint.pack(side="left", padx=(10, 0))
        else:
            self.monitor_row = None
            self.monitor_var = None
            self.monitor_switch = None
            self.monitor_hint = None

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
            self.snapshot_btn.grid(row=self._snapshot_row_idx, column=0, padx=18, pady=(0, 14), sticky="ew")
        else:
            self.snapshot_btn = None

        self._detail_widgets = [self.compact_bottom_row, self.btn_row]
        if self.monitor_row:
            self._detail_widgets.append(self.monitor_row)
        if show_stats:
            self._detail_widgets.insert(1, self.stats_frame)
        if self.snapshot_btn:
            self._detail_widgets.append(self.snapshot_btn)

        hover_widgets = [self, top_row, self.icon_label, self.name_label]
        for widget in hover_widgets:
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            try:
                widget.configure(cursor="hand2")
            except Exception:
                pass

        self.name_label.bind("<Button-1>", self._toggle_on_name_click)
        self.set_collapsed(collapsed, animate=False, notify=False)
        self._apply_monitor_visual(monitor_enabled)

    def _on_monitor_toggle(self) -> None:
        if not self.monitor_var or not self.on_monitor_change:
            return
        enabled = bool(self.monitor_var.get())
        self._monitor_enabled = enabled
        self._apply_monitor_visual(enabled)
        self.on_monitor_change(enabled)

    def _toggle_on_name_click(self, _event=None) -> str:
        if self._collapsed:
            self.set_collapsed(False)
        return "break"

    def _notify_selection(self) -> None:
        if self.on_selection_change:
            self.on_selection_change()

    def is_selected(self) -> bool:
        return bool(self.select_var.get())

    def is_collapsed(self) -> bool:
        return bool(self._collapsed)

    def set_selected(self, selected: bool) -> None:
        self.select_var.set(selected)

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def _layout_expanded_header(self) -> None:
        self.compact_expand_btn.grid_remove()
        self.select_cb.grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.icon_label.grid(row=0, column=1, sticky="w")
        self.name_label.grid(row=0, column=2, sticky="ew", padx=(6, 6))
        self.name_label.configure(wraplength=0)
        self.expand_btn.grid(row=0, column=3, sticky="e", padx=(4, 4))
        self.type_badge.grid(row=0, column=4, sticky="e")
        if hasattr(self, "drag_handle"):
            self.drag_handle.grid(row=0, column=5, sticky="e", padx=(6, 0))

    def _layout_compact_header(self) -> None:
        self.type_badge.grid_remove()
        if hasattr(self, "drag_handle"):
            self.drag_handle.grid_remove()
        self.expand_btn.grid_remove()
        self.select_cb.grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.icon_label.grid(row=0, column=1, sticky="nw")
        self.name_label.grid(row=0, column=2, columnspan=3, sticky="ew", padx=(6, 0))
        self.name_label.configure(wraplength=0)
        self.bottom_left.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.compact_expand_btn.grid(row=0, column=1, sticky="e", padx=(0, 6))
        self.compact_connect_btn.grid(row=0, column=2, sticky="e")

    def set_collapsed(self, collapsed: bool, *, animate: bool = True, notify: bool = True) -> None:
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self.expand_btn.configure(text="▶" if collapsed else "▼")
        self.compact_expand_btn.configure(text="▶" if collapsed else "▼")
        if collapsed:
            for widget in self._detail_widgets:
                widget.grid_remove()
            self._layout_compact_header()
            self.compact_bottom_row.grid(row=1, column=0, padx=12, pady=(2, 10), sticky="ew")
            self.configure(height=0)
        else:
            self.compact_bottom_row.grid_remove()
            self._layout_expanded_header()
            self.compact_expand_btn.grid_remove()
            self.compact_connect_btn.grid_remove()
            self.bottom_left.grid(row=0, column=0, padx=(0, 6), sticky="ew")
            self.compact_bottom_row.grid(row=1, column=0, padx=18, pady=(0, 4), sticky="ew")
            if self.show_stats:
                self.stats_frame.grid(row=self._stats_row, column=0, padx=14, pady=(0, 8), sticky="ew")
            self.btn_row.grid(row=self._btn_row_idx, column=0, padx=18, pady=(0, 8), sticky="ew")
            if self.monitor_row:
                self.monitor_row.grid(
                    row=self._monitor_row_idx, column=0, padx=18, pady=(0, 6), sticky="ew"
                )
            if self.snapshot_btn:
                self.snapshot_btn.grid(
                    row=self._snapshot_row_idx, column=0, padx=18, pady=(0, 14), sticky="ew"
                )
            self.configure(height=0)
        if notify and self.on_collapsed_change:
            self.on_collapsed_change(self.card_id, collapsed)

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

    def set_monitor_enabled(self, enabled: bool) -> None:
        self._monitor_enabled = enabled
        if self.monitor_var is not None:
            self.monitor_var.set(enabled)
        self._apply_monitor_visual(enabled)

    def _apply_monitor_visual(self, enabled: bool) -> None:
        if self.monitor_hint:
            self.monitor_hint.configure(
                text="On — stats refresh allowed" if enabled else "Off — no background SSH"
            )
        if not self.show_stats:
            return
        if enabled:
            if (
                not self._stats_left_lines
                and not self._stats_right_lines
                and not self._stats_error
            ):
                self.set_stats_prompt("Stats not loaded yet — click Refresh Stats or turn on Monitor.")
        else:
            self.set_stats_prompt("Monitoring off — turn on Monitor to refresh SSH stats.")

    def get_stats_snapshot(self) -> tuple[list[str], list[str], str | None]:
        return self._stats_left_lines, self._stats_right_lines, self._stats_error

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

    def set_ssh_status(self, state: str, message: str = "") -> None:
        if not self.status_led:
            return
        self._ssh_status = state
        colors = {
            "unknown": "#6b7280",
            "off": "#6b7280",
            "checking": "#fbbf24",
            "ok": "#22c55e",
            "fail": "#ef4444",
            "nocreds": "#4b5563",
        }
        self.status_led.configure(fg_color=colors.get(state, "#6b7280"))
        self._ssh_status_tip = {
            "unknown": "SSH status not checked yet",
            "off": message or "Monitoring off — no background SSH",
            "checking": "Checking SSH login...",
            "ok": message or "SSH login OK",
            "fail": f"SSH login failed: {message}" if message else "SSH login failed",
            "nocreds": message or "Add SSH password or key in Admin",
        }.get(state, "SSH status")
        self._hide_status_tip()

    def _on_status_led_enter(self, _event=None) -> None:
        self._show_status_tip(self._ssh_status_tip)

    def _show_status_tip(self, text: str) -> None:
        if not text or not self.status_led or not self.status_led.winfo_exists():
            return
        self._hide_status_tip()
        self._status_tip = ctk.CTkToplevel(self)
        self._status_tip.wm_overrideredirect(True)
        self._status_tip.attributes("-topmost", True)
        x = self.status_led.winfo_rootx()
        y = self.status_led.winfo_rooty() + self.status_led.winfo_height() + 4
        self._status_tip.geometry(f"+{x}+{y}")
        ctk.CTkLabel(
            self._status_tip,
            text=text,
            font=ctk.CTkFont(size=11),
            text_color=self.theme["text"],
            fg_color=self.theme["surface"],
            corner_radius=6,
            padx=8,
            pady=4,
        ).pack()
        self._status_tip.bind("<Leave>", lambda _e: self._hide_status_tip())
        self._status_tip.bind("<Button-1>", lambda _e: self._hide_status_tip())
        self._status_tip_after = self.after(5000, self._hide_status_tip)

    def _hide_status_tip(self) -> None:
        if getattr(self, "_status_tip_after", None):
            try:
                self.after_cancel(self._status_tip_after)
            except Exception:
                pass
            self._status_tip_after = None
        if hasattr(self, "_status_tip") and self._status_tip and self._status_tip.winfo_exists():
            self._status_tip.destroy()
            self._status_tip = None

    def apply_theme(self, theme: dict) -> None:
        self.theme = theme
        self.configure(fg_color=theme["surface_alt"], border_color=theme["border"])
        self.name_label.configure(text_color=theme["text"])
        self.subtitle_label.configure(text_color=theme["muted"])
        self.type_badge.configure(text_color=theme["bg"])
        self.expand_btn.configure(fg_color=theme["surface"], hover_color=theme["border"], text_color=theme["muted"])
        self.compact_expand_btn.configure(
            fg_color=theme["surface"], hover_color=theme["border"], text_color=theme["muted"]
        )
        if hasattr(self, "drag_handle"):
            self.drag_handle.configure(text_color=theme["muted"])
        if self.show_stats:
            self.stats_frame.configure(fg_color=theme["surface"])
        if self.status_led and self._ssh_status:
            self.set_ssh_status(self._ssh_status)
