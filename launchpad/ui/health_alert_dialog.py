"""Desktop critical health alert popup for Connection Dashboard."""

from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from launchpad.ui.theme import get_theme

HEALTH_ALERT_POLL_MS = 30_000

PauseHandler = Callable[[int], None]
CloseHandler = Callable[[bool], None]
AlarmToggleHandler = Callable[[], None]


def group_health_alerts(alerts: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for alert in alerts or []:
        card_id = alert.get("card_id")
        key = str(card_id)
        if key not in groups:
            groups[key] = {
                "card_id": card_id,
                "card_name": alert.get("card_name") or f"Card {card_id}",
                "issues": [],
            }
        groups[key]["issues"].append(alert)
    return sorted(
        groups.values(),
        key=lambda group: (
            str(group.get("card_name") or ""),
            int(group.get("card_id") or 0),
        ),
    )


def play_health_alert_beep() -> None:
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONHAND)
    except Exception:
        pass


class HealthAlertDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        *,
        theme_name: str,
        group: dict[str, Any],
        on_acknowledge: Callable[[], None],
        on_pause: PauseHandler,
        on_alarm_toggle: AlarmToggleHandler,
        on_close: CloseHandler,
        *,
        alarm_muted: bool = False,
    ) -> None:
        super().__init__(master)
        self.theme = get_theme(theme_name)
        self._group = group
        self._on_acknowledge = on_acknowledge
        self._on_pause = on_pause
        self._on_alarm_toggle = on_alarm_toggle
        self._on_close = on_close
        self._alarm_muted = alarm_muted

        card_name = str(group.get("card_name") or f"Card {group.get('card_id')}")
        self.title("Critical Health Alert")
        self.configure(fg_color=self.theme["bg"])
        self.resizable(True, True)
        self.minsize(420, 280)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", lambda: self._on_close(True))
        self.bind("<Escape>", lambda _e: self._on_close(True))
        self.after(200, self.lift)

        pad = 20
        frame = ctk.CTkFrame(self, fg_color=self.theme["surface"], corner_radius=16)
        frame.pack(padx=pad, pady=pad, fill="both", expand=True)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 8))

        ctk.CTkLabel(
            header,
            text="Critical Health Alert",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=self.theme["danger"],
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            header,
            text=card_name,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.theme["accent"],
            anchor="w",
        ).pack(fill="x", pady=(8, 0))

        issues_box = ctk.CTkScrollableFrame(
            frame,
            fg_color=self.theme["surface_alt"],
            corner_radius=12,
            height=160,
        )
        issues_box.pack(fill="both", expand=True, padx=20, pady=(8, 12))

        for issue in group.get("issues") or []:
            category = str(issue.get("category") or "")
            message = str(issue.get("message") or "")
            severity = str(issue.get("severity") or "critical")
            prefix = f"{category} · " if category else ""
            text_color = self.theme["danger"] if severity == "critical" else self.theme["text"]
            ctk.CTkLabel(
                issues_box,
                text=f"{prefix}{message}",
                font=ctk.CTkFont(size=13),
                text_color=text_color,
                anchor="w",
                justify="left",
                wraplength=460,
            ).pack(fill="x", padx=12, pady=4)

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(0, 12))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            actions,
            text="Acknowledge",
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_soft"],
            command=self._on_acknowledge,
        ).grid(row=0, column=0, padx=(0, 6), pady=(0, 6), sticky="ew")

        ctk.CTkButton(
            actions,
            text="Alarm on" if alarm_muted else "Alarm off",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=self._on_alarm_toggle,
        ).grid(row=0, column=1, padx=(6, 0), pady=(0, 6), sticky="ew")

        pause_row = ctk.CTkFrame(frame, fg_color="transparent")
        pause_row.pack(fill="x", padx=20, pady=(0, 12))
        for col in range(5):
            pause_row.grid_columnconfigure(col, weight=1)

        ctk.CTkLabel(
            pause_row,
            text="Pause:",
            font=ctk.CTkFont(size=12),
            text_color=self.theme["muted"],
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")

        for index, minutes in enumerate((5, 10, 15, 20), start=1):
            ctk.CTkButton(
                pause_row,
                text=f"Pause {minutes} min",
                height=28,
                fg_color=self.theme["surface_alt"],
                hover_color=self.theme["border"],
                command=lambda m=minutes: self._on_pause(m),
            ).grid(row=0, column=index, padx=4, sticky="ew")

        ctk.CTkButton(
            frame,
            text="Close",
            fg_color=self.theme["surface_alt"],
            hover_color=self.theme["border"],
            command=lambda: self._on_close(True),
        ).pack(fill="x", padx=20, pady=(0, 20))

        self.update_idletasks()
        self.geometry(f"{max(520, self.winfo_reqwidth())}x{max(360, self.winfo_reqheight())}")

    @property
    def group(self) -> dict[str, Any]:
        return self._group
