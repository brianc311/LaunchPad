import customtkinter as ctk

from launchpad.health_alert_art import resolve_health_alert_art
from launchpad.icons import resolve_icon
from launchpad.ui.colors import ctk_color, normalize_color
from launchpad.ui.health_alert_layout import (
    build_health_alert_surface,
    load_alert_art_image,
)

# CRIT/WARN hover tip: keep short-lived and never permanently topmost over other apps.
CAPACITY_ALERT_TIP_MAX_MS = 4000
CAPACITY_ALERT_TIP_WATCHDOG_MS = 200
CAPACITY_ALERT_TIP_LEAVE_GRACE_MS = 80


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
        on_power_off=None,
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
        show_dell_report_include: bool = False,
        dell_report_include: bool = False,
        on_dell_report_include_change=None,
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
        self.on_power_off = on_power_off
        self.on_snapshot = on_snapshot
        self.on_monitor_change = on_monitor_change
        self._monitor_enabled = monitor_enabled
        self.on_dell_report_include_change = on_dell_report_include_change
        self._dell_report_include = bool(dell_report_include)
        self.on_reorder = on_reorder
        self.on_selection_change = on_selection_change
        self.on_collapsed_change = on_collapsed_change
        self.name = name
        self.card_id = card_id
        self.draggable = draggable
        self.dashboard = dashboard
        self._hovering = False
        self._dragging = False
        self._collapsed: bool | None = None
        self._stats_left_lines: list[str] = []
        self._stats_right_lines: list[str] = []
        self._stats_error: str | None = None
        self._health_alert_overlay = None
        self._health_alert_art_image = None
        self._health_alert_signature: str | None = None

        self.grid_columnconfigure(0, weight=1)
        stats_row = 3 if show_stats else 2
        btn_row_idx = stats_row + 1
        self._stats_row = stats_row
        self._btn_row_idx = btn_row_idx
        next_row = btn_row_idx + 1
        self._monitor_row_idx = next_row if on_monitor_change else None
        if on_monitor_change:
            next_row += 1
        self._dell_report_row_idx = next_row if show_dell_report_include else None
        if show_dell_report_include:
            next_row += 1
        self._snapshot_row_idx = next_row
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

        self._capacity_alert_severity: str | None = None
        self._capacity_alert_tip = ""
        self._capacity_alert_tip_window = None
        self._capacity_alert_tip_after = None
        self._capacity_alert_tip_hide_after = None
        self._capacity_alert_tip_watchdog_after = None
        self.capacity_alert_badge = ctk.CTkLabel(
            top_row,
            text="",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#111111",
            fg_color=theme["surface"],
            corner_radius=8,
            width=44,
            height=20,
        )
        self.capacity_alert_badge.grid(row=0, column=4, sticky="e", padx=(4, 4))
        self.capacity_alert_badge.grid_remove()
        self.capacity_alert_badge.bind("<Enter>", self._on_capacity_alert_enter)
        self.capacity_alert_badge.bind("<Leave>", self._schedule_hide_capacity_alert_tip)
        self.bind("<Destroy>", lambda _e: self._hide_capacity_alert_tip(), add="+")
        try:
            self.winfo_toplevel().bind(
                "<FocusOut>", self._on_app_focus_out_hide_capacity_tip, add="+"
            )
        except Exception:
            pass

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
        self.type_badge.grid(row=0, column=5, sticky="e")

        if draggable:
            self.drag_handle = ctk.CTkLabel(
                top_row,
                text="::",
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=theme["muted"],
                width=20,
                cursor="hand2",
            )
            self.drag_handle.grid(row=0, column=6, sticky="e", padx=(6, 0))
            self.drag_handle.bind("<Button-1>", self._start_drag)
            self.drag_handle.bind("<B1-Motion>", self._on_drag)
            self.drag_handle.bind("<ButtonRelease-1>", self._end_drag)
            self.drag_handle.configure(cursor="fleur")

        self.compact_bottom_row = ctk.CTkFrame(self, fg_color="transparent")
        self.compact_bottom_row.grid_columnconfigure(0, weight=1)

        self.bottom_left = ctk.CTkFrame(self.compact_bottom_row, fg_color="transparent")
        self.bottom_left.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.bottom_left.grid_columnconfigure(2, weight=1)

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

        # Compact-layout CRIT/WARN badge (next to status LED; avoids name overlap)
        self.capacity_alert_badge_compact = ctk.CTkLabel(
            self.bottom_left,
            text="",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#111111",
            fg_color=theme["surface"],
            corner_radius=6,
            width=40,
            height=18,
        )
        self.capacity_alert_badge_compact.grid(row=0, column=1, padx=(0, 6), sticky="w")
        self.capacity_alert_badge_compact.grid_remove()
        self.capacity_alert_badge_compact.bind("<Enter>", self._on_capacity_alert_enter)
        self.capacity_alert_badge_compact.bind("<Leave>", self._schedule_hide_capacity_alert_tip)

        self.subtitle_label = ctk.CTkLabel(
            self.bottom_left,
            text=subtitle,
            font=ctk.CTkFont(size=11),
            text_color=theme["muted"],
            anchor="w",
        )
        self.subtitle_label.grid(row=0, column=2, sticky="ew")

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
        if on_power_off:
            btn_row.grid_columnconfigure(2 if on_health else 1, weight=1)

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

        if on_power_off:
            power_off_column = 2 if on_health else 1
            self.power_off_btn = ctk.CTkButton(
                btn_row,
                text="Power off…",
                fg_color=theme["surface"],
                hover_color=theme["border"],
                border_width=1,
                border_color=theme["danger"],
                text_color=theme["danger"],
                height=32,
                command=self._power_off,
            )
            self.power_off_btn.grid(row=0, column=power_off_column, sticky="ew", padx=(6, 0))

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
        self._alarm_on_btn = None

        if show_dell_report_include and self._dell_report_row_idx is not None:
            self.dell_report_row = ctk.CTkFrame(self, fg_color="transparent")
            self.dell_report_row.grid(
                row=self._dell_report_row_idx, column=0, padx=18, pady=(0, 6), sticky="ew"
            )
            self.dell_report_var = ctk.BooleanVar(value=self._dell_report_include)
            self.dell_report_check = ctk.CTkCheckBox(
                self.dell_report_row,
                text="Dell Report",
                variable=self.dell_report_var,
                command=self._on_dell_report_include_toggle,
                font=ctk.CTkFont(size=12),
            )
            self.dell_report_check.pack(side="left")
            self.dell_report_hint = ctk.CTkLabel(
                self.dell_report_row,
                text="Include even without SSH",
                font=ctk.CTkFont(size=11),
                text_color=theme["muted"],
            )
            self.dell_report_hint.pack(side="left", padx=(10, 0))
        else:
            self.dell_report_row = None
            self.dell_report_var = None
            self.dell_report_check = None
            self.dell_report_hint = None

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
        if self.dell_report_row:
            self._detail_widgets.append(self.dell_report_row)
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

    def _on_dell_report_include_toggle(self) -> None:
        if not self.dell_report_var or not self.on_dell_report_include_change:
            return
        enabled = bool(self.dell_report_var.get())
        self._dell_report_include = enabled
        self.on_dell_report_include_change(enabled)

    def set_dell_report_include(self, enabled: bool) -> None:
        self._dell_report_include = bool(enabled)
        if self.dell_report_var is not None:
            self.dell_report_var.set(self._dell_report_include)

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
        self.type_badge.grid(row=0, column=5, sticky="e")
        if hasattr(self, "drag_handle"):
            self.drag_handle.grid(row=0, column=6, sticky="e", padx=(6, 0))
        self._hide_capacity_alert_tip()
        self._place_capacity_alert_badges()

    def _layout_compact_header(self) -> None:
        self.capacity_alert_badge.grid_remove()
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
        self._hide_capacity_alert_tip()
        self._place_capacity_alert_badges()

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

    def _power_off(self) -> None:
        if self.on_power_off:
            self.on_power_off()

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

    def _capacity_alert_style(self, severity: str) -> tuple[str, str, str]:
        is_critical = severity == "critical"
        return (
            "CRIT" if is_critical else "WARN",
            "#ef4444" if is_critical else "#f59e0b",
            "#ffffff" if is_critical else "#111111",
        )

    def _place_capacity_alert_badges(self) -> None:
        """Show header badge when expanded; compact badge (by LED) when collapsed."""
        header = getattr(self, "capacity_alert_badge", None)
        compact = getattr(self, "capacity_alert_badge_compact", None)
        if not header or not compact:
            return
        if not self._capacity_alert_severity:
            header.grid_remove()
            compact.grid_remove()
            return
        text, fg, tc = self._capacity_alert_style(self._capacity_alert_severity)
        for badge in (header, compact):
            badge.configure(text=text, fg_color=fg, text_color=tc)
        if self._collapsed:
            header.grid_remove()
            compact.grid(row=0, column=1, padx=(0, 6), sticky="w")
        else:
            compact.grid_remove()
            header.grid(row=0, column=4, sticky="e", padx=(4, 4))

    def _visible_capacity_badge(self):
        compact = getattr(self, "capacity_alert_badge_compact", None)
        header = getattr(self, "capacity_alert_badge", None)
        if self._collapsed and compact is not None:
            return compact
        return header

    def set_capacity_alert(
        self,
        severity: str | None,
        messages: list[str] | None = None,
    ) -> None:
        if not hasattr(self, "capacity_alert_badge") or self.capacity_alert_badge is None:
            return
        if severity not in {"critical", "warn"}:
            self._capacity_alert_severity = None
            self.capacity_alert_badge.configure(text="")
            if getattr(self, "capacity_alert_badge_compact", None) is not None:
                self.capacity_alert_badge_compact.configure(text="")
            self._place_capacity_alert_badges()
            self._hide_capacity_alert_tip()
            return
        self._capacity_alert_severity = severity
        is_critical = severity == "critical"
        tip = "\n".join(m for m in (messages or []) if m).strip()
        if tip:
            self._capacity_alert_tip = tip
        else:
            self._capacity_alert_tip = (
                "Critical capacity on this site" if is_critical else "Capacity warning on this site"
            )
        self._place_capacity_alert_badges()

    def _pointer_over_capacity_tip_widgets(self) -> bool:
        """True when pointer is still over the CRIT/WARN badge or the tip window."""
        try:
            x = int(self.winfo_pointerx())
            y = int(self.winfo_pointery())
        except Exception:
            return False
        for widget in (self._visible_capacity_badge(), getattr(self, "_capacity_alert_tip_window", None)):
            if widget is None:
                continue
            try:
                if not widget.winfo_exists():
                    continue
                left = int(widget.winfo_rootx())
                top = int(widget.winfo_rooty())
                right = left + int(widget.winfo_width())
                bottom = top + int(widget.winfo_height())
                if left <= x < right and top <= y < bottom:
                    return True
            except Exception:
                continue
        return False

    def _cancel_scheduled_hide_capacity_alert_tip(self) -> None:
        hide_after = getattr(self, "_capacity_alert_tip_hide_after", None)
        if hide_after:
            try:
                self.after_cancel(hide_after)
            except Exception:
                pass
            self._capacity_alert_tip_hide_after = None

    def _cancel_capacity_alert_tip_watchdog(self) -> None:
        watchdog = getattr(self, "_capacity_alert_tip_watchdog_after", None)
        if watchdog:
            try:
                self.after_cancel(watchdog)
            except Exception:
                pass
            self._capacity_alert_tip_watchdog_after = None

    def _arm_capacity_alert_tip_watchdog(self) -> None:
        """Poll pointer while tip is open — Leave alone is unreliable on Windows."""
        self._cancel_capacity_alert_tip_watchdog()
        self._capacity_alert_tip_watchdog_after = self.after(
            CAPACITY_ALERT_TIP_WATCHDOG_MS, self._capacity_alert_tip_watchdog_tick
        )

    def _capacity_alert_tip_watchdog_tick(self) -> None:
        self._capacity_alert_tip_watchdog_after = None
        tip_window = getattr(self, "_capacity_alert_tip_window", None)
        if tip_window is None:
            return
        try:
            if not tip_window.winfo_exists():
                self._capacity_alert_tip_window = None
                return
        except Exception:
            self._capacity_alert_tip_window = None
            return
        if not self._pointer_over_capacity_tip_widgets():
            self._hide_capacity_alert_tip()
            return
        self._arm_capacity_alert_tip_watchdog()

    def _schedule_hide_capacity_alert_tip(self, _event=None) -> None:
        """Defer hide so pointer can move badge → tip without killing the tip."""
        self._cancel_scheduled_hide_capacity_alert_tip()
        self._capacity_alert_tip_hide_after = self.after(
            CAPACITY_ALERT_TIP_LEAVE_GRACE_MS, self._hide_capacity_alert_tip_if_away
        )

    def _hide_capacity_alert_tip_if_away(self) -> None:
        self._capacity_alert_tip_hide_after = None
        if self._pointer_over_capacity_tip_widgets():
            # Leave fired but pointer still over tip/badge — keep polling via watchdog.
            return
        self._hide_capacity_alert_tip()

    def _on_capacity_alert_enter(self, _event=None) -> None:
        self._cancel_scheduled_hide_capacity_alert_tip()
        tip = getattr(self, "_capacity_alert_tip", "")
        if tip:
            self._show_capacity_alert_tip(tip)

    def _show_capacity_alert_tip(self, text: str) -> None:
        badge = self._visible_capacity_badge()
        if not text or not badge or not badge.winfo_exists():
            return
        self._hide_capacity_alert_tip()
        self._capacity_alert_tip_window = ctk.CTkToplevel(self)
        tip_window = self._capacity_alert_tip_window
        tip_window.wm_overrideredirect(True)
        # Do not set -topmost: that leaves orphan tips stuck above browser/other apps.
        tip_window.transient(self.winfo_toplevel())
        x = badge.winfo_rootx()
        y = badge.winfo_rooty() + badge.winfo_height() + 4
        tip_window.geometry(f"+{x}+{y}")
        tip_label = ctk.CTkLabel(
            tip_window,
            text=text,
            font=ctk.CTkFont(size=11),
            text_color=self.theme["text"],
            fg_color=self.theme["surface"],
            corner_radius=6,
            padx=8,
            pady=4,
        )
        tip_label.pack()
        # Overrideredirect tips often miss Leave on Windows; defer + pointer
        # geometry check, bind Enter/Leave on tip and label, and poll.
        for widget in (tip_window, tip_label):
            widget.bind("<Enter>", lambda _e: self._cancel_scheduled_hide_capacity_alert_tip())
            widget.bind("<Leave>", self._schedule_hide_capacity_alert_tip)
            widget.bind("<Button-1>", lambda _e: self._hide_capacity_alert_tip())
        tip_window.bind("<FocusOut>", lambda _e: self._hide_capacity_alert_tip(), add="+")
        tip_window.bind("<Escape>", lambda _e: self._hide_capacity_alert_tip(), add="+")
        self._capacity_alert_tip_after = self.after(
            CAPACITY_ALERT_TIP_MAX_MS, self._hide_capacity_alert_tip
        )
        self._arm_capacity_alert_tip_watchdog()

    def _on_app_focus_out_hide_capacity_tip(self, _event=None) -> None:
        if getattr(self, "_capacity_alert_tip_window", None) is None:
            return
        self.after(0, self._hide_capacity_alert_tip)

    def _hide_capacity_alert_tip(self, _event=None) -> None:
        self._cancel_scheduled_hide_capacity_alert_tip()
        self._cancel_capacity_alert_tip_watchdog()
        if getattr(self, "_capacity_alert_tip_after", None):
            try:
                self.after_cancel(self._capacity_alert_tip_after)
            except Exception:
                pass
            self._capacity_alert_tip_after = None
        tip_window = getattr(self, "_capacity_alert_tip_window", None)
        if tip_window is not None:
            try:
                if tip_window.winfo_exists():
                    tip_window.destroy()
            except Exception:
                pass
            # Only drop the reference after destroy attempt so we never orphan
            # a live top-level without a handle.
            try:
                still = tip_window.winfo_exists()
            except Exception:
                still = False
            if not still:
                self._capacity_alert_tip_window = None
            else:
                # Last resort: withdraw so it cannot stay visible.
                try:
                    tip_window.withdraw()
                except Exception:
                    pass
                self._capacity_alert_tip_window = None

    def health_alert_overlay_signature(self, group: dict, *, alarm_muted: bool) -> str:
        issues = group.get("issues") or []
        parts = [str(group.get("card_id")), "1" if alarm_muted else "0"]
        parts.extend(
            str(issue.get("fingerprint") or issue.get("message") or "") for issue in issues
        )
        return "\x1f".join(parts)

    def clear_health_alert_overlay(self) -> None:
        overlay = self._health_alert_overlay
        self._health_alert_overlay = None
        self._health_alert_art_image = None
        self._health_alert_signature = None
        if overlay is not None:
            try:
                if overlay.winfo_exists():
                    overlay.destroy()
            except Exception:
                pass

    def set_health_alert_overlay(
        self,
        group: dict,
        *,
        on_acknowledge,
        on_pause,
        on_alarm_toggle,
        on_close,
        alarm_muted: bool = False,
    ) -> None:
        signature = self.health_alert_overlay_signature(group, alarm_muted=alarm_muted)
        if (
            self._health_alert_overlay is not None
            and self._health_alert_signature == signature
        ):
            # Rebuilding an unchanged overlay every poll flickers and re-decodes the PNG.
            return

        self.clear_health_alert_overlay()
        overlay = ctk.CTkFrame(
            self,
            fg_color=self.theme["surface"],
            border_width=2,
            border_color=self.theme["danger"],
            corner_radius=16,
        )
        self._health_alert_overlay = overlay
        self._health_alert_signature = signature
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()

        art_path = resolve_health_alert_art(str(group.get("card_name") or self.name))
        self._health_alert_art_image = load_alert_art_image(art_path, (360, 210))

        build_health_alert_surface(
            overlay,
            theme=self.theme,
            group=group,
            art_image=self._health_alert_art_image,
            on_acknowledge=on_acknowledge,
            on_pause=on_pause,
            on_alarm_toggle=on_alarm_toggle,
            on_close=on_close,
            alarm_muted=alarm_muted,
            title="ALERT",
            title_size=18,
            message_size=11,
            wraplength=300,
            button_height=24,
        )

    def set_health_alarm_muted(
        self,
        muted: bool,
        *,
        on_alarm_on=None,
    ) -> None:
        if self.monitor_row is None:
            return
        if muted:
            if self._alarm_on_btn is None:
                self._alarm_on_btn = ctk.CTkButton(
                    self.monitor_row,
                    text="Alarm on",
                    width=72,
                    height=24,
                    fg_color=self.theme["surface"],
                    hover_color=self.theme["border"],
                    font=ctk.CTkFont(size=11, weight="bold"),
                    command=on_alarm_on or (lambda: None),
                )
                self._alarm_on_btn.pack(side="right")
            elif on_alarm_on is not None:
                self._alarm_on_btn.configure(command=on_alarm_on)
            self.monitor_hint.configure(text="Alarm muted — no health popups")
        else:
            if self._alarm_on_btn is not None:
                self._alarm_on_btn.destroy()
                self._alarm_on_btn = None
            enabled = bool(self.monitor_var.get()) if self.monitor_var is not None else False
            self.monitor_hint.configure(
                text="Off — no background SSH" if not enabled else "On — stats refresh allowed"
            )

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
        if self._capacity_alert_severity:
            self._place_capacity_alert_badges()
