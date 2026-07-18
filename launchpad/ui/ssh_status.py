"""Shared SSH connection status colors and labels for dashboard and admin LEDs."""

from __future__ import annotations

import customtkinter as ctk

SSH_STATUS_INTERVAL_MS = 90_000

SSH_STATUS_COLORS: dict[str, str] = {
    "unknown": "#6b7280",
    "off": "#6b7280",
    "checking": "#fbbf24",
    "ok": "#22c55e",
    "fail": "#ef4444",
    "nocreds": "#4b5563",
    "na": "#374151",
}

SSH_STATUS_TIPS: dict[str, str] = {
    "unknown": "SSH status not checked yet",
    "off": "Monitoring off — no background SSH",
    "checking": "Checking SSH login...",
    "ok": "SSH connected",
    "fail": "SSH disconnected",
    "nocreds": "Add SSH password or key",
    "na": "Not an SSH card",
}


def ssh_status_tip(state: str, message: str = "") -> str:
    if state == "fail" and message:
        return f"SSH disconnected: {message}"
    if state == "nocreds" and message:
        return message
    return SSH_STATUS_TIPS.get(state, "SSH status")


def _destroy_ssh_status_tooltip(led: ctk.CTkFrame) -> None:
    after_id = getattr(led, "_ssh_status_tooltip_after", None)
    if after_id:
        try:
            led.after_cancel(after_id)
        except Exception:
            pass
        led._ssh_status_tooltip_after = None  # type: ignore[attr-defined]
    tooltip = getattr(led, "_ssh_status_tooltip", None)
    if tooltip and tooltip.winfo_exists():
        tooltip.destroy()
    led._ssh_status_tooltip = None  # type: ignore[attr-defined]


def create_ssh_status_led(parent, theme: dict, *, state: str = "unknown") -> ctk.CTkFrame:
    led = ctk.CTkFrame(
        parent,
        width=10,
        height=10,
        corner_radius=5,
        fg_color=SSH_STATUS_COLORS.get(state, "#6b7280"),
    )
    led.grid_propagate(False)
    led._ssh_status_state = state  # type: ignore[attr-defined]
    led._ssh_status_tip = ssh_status_tip(state)  # type: ignore[attr-defined]
    led._ssh_status_tooltip = None  # type: ignore[attr-defined]
    led._ssh_status_tooltip_after = None  # type: ignore[attr-defined]

    def on_enter(_event=None) -> None:
        tip_text = getattr(led, "_ssh_status_tip", "")
        if not tip_text or not led.winfo_exists():
            return
        _destroy_ssh_status_tooltip(led)
        tooltip = ctk.CTkToplevel(led)
        tooltip.wm_overrideredirect(True)
        tooltip.attributes("-topmost", True)
        x = led.winfo_rootx()
        y = led.winfo_rooty() + led.winfo_height() + 4
        tooltip.geometry(f"+{x}+{y}")
        ctk.CTkLabel(
            tooltip,
            text=tip_text,
            font=ctk.CTkFont(size=11),
            text_color=theme["text"],
            fg_color=theme["surface"],
            corner_radius=6,
            padx=8,
            pady=4,
        ).pack()
        led._ssh_status_tooltip = tooltip  # type: ignore[attr-defined]
        tooltip.bind("<Leave>", lambda _e: _destroy_ssh_status_tooltip(led))
        tooltip.bind("<Button-1>", lambda _e: _destroy_ssh_status_tooltip(led))
        led._ssh_status_tooltip_after = led.after(  # type: ignore[attr-defined]
            5000, lambda: _destroy_ssh_status_tooltip(led)
        )

    def on_leave(_event=None) -> None:
        _destroy_ssh_status_tooltip(led)

    led.bind("<Enter>", on_enter)
    led.bind("<Leave>", on_leave)
    led.bind("<Destroy>", lambda _e: _destroy_ssh_status_tooltip(led), add="+")
    return led


def set_ssh_status_led(led: ctk.CTkFrame | None, state: str, message: str = "") -> None:
    if led is None or not led.winfo_exists():
        return
    _destroy_ssh_status_tooltip(led)
    led.configure(fg_color=SSH_STATUS_COLORS.get(state, "#6b7280"))
    led._ssh_status_state = state  # type: ignore[attr-defined]
    led._ssh_status_tip = ssh_status_tip(state, message)  # type: ignore[attr-defined]
