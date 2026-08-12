"""Desktop critical health alert popup for Connection Dashboard."""

from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from launchpad.health_alert_art import resolve_health_alert_art
from launchpad.ui.health_alert_layout import (
    build_health_alert_surface,
    load_alert_art_image,
)
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
        self._art_image = None

        card_name = str(group.get("card_name") or f"Card {group.get('card_id')}")
        self.title("Critical Health Alert")
        self.configure(fg_color=self.theme["bg"])
        self.resizable(True, True)
        self.minsize(420, 280)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", lambda: self._on_close(True))
        self.bind("<Escape>", lambda _e: self._on_close(True))
        self.after(200, self.lift)

        art_path = resolve_health_alert_art(card_name)
        self._art_image = load_alert_art_image(art_path, (640, 360))

        build_health_alert_surface(
            self,
            theme=self.theme,
            group=group,
            art_image=self._art_image,
            on_acknowledge=self._on_acknowledge,
            on_pause=self._on_pause,
            on_alarm_toggle=self._on_alarm_toggle,
            on_close=lambda: self._on_close(True),
            alarm_muted=alarm_muted,
            title="Critical Health Alert" if self._art_image is not None else "ALERT",
            title_size=22,
            message_size=14,
            wraplength=520,
            button_height=32,
        )

        self.update_idletasks()
        self.geometry(f"{max(520, self.winfo_reqwidth())}x{max(360, self.winfo_reqheight())}")

    @property
    def group(self) -> dict[str, Any]:
        return self._group
