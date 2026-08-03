# Connection Dashboard Array Rail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collapsible left array rail on the Connection Dashboard that lists the same filtered cards as the grid and opens each array’s web GUI on click (v**1.6.92**).

**Architecture:** Pure helpers in `launchpad/dashboard_array_rail.py` (filter sync, GUI URL via `resolve_gui_url`, open helper, collapse setting key). `dashboard_view.py` adds a left rail beside the card scroll area, rebuilds rows whenever Category/search rebuild the grid, and persists collapse state.

**Tech Stack:** Python, CustomTkinter, pytest, existing `resolve_gui_url` / `webbrowser`.

**Spec:** `docs/superpowers/specs/2026-08-03-dashboard-array-rail-design.md`

## Global Constraints

- **Worktree:** `.worktrees/dashboard-array-rail` on `feature/dashboard-array-rail` from `feature/contingency-groups` tip (≥ `1.6.91` + this plan’s spec)
- Connection Dashboard only (CustomTkinter) — no FlashCopy CGs / Health browser rail
- Click = **Open GUI only** (not SSH Connect, not card select)
- Rail list = **same Category + search filter** as the card grid
- Setting key: `dashboard_array_rail_collapsed` (bool string `"true"` / `"false"`, default expanded)
- Use `resolve_gui_url(url, host)` — URL preferred, else `https://{host}`
- Do not change Monitor / Connect / selection behavior
- Bump `APP_VERSION` to **1.6.92** in the final task
- Commit per task; run from worktree
- Operator install folder note: `C:\Users\BrianColley\LaunchPad\LaunchPad-install`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/dashboard_array_rail.py` | Setting key, filter helper, GUI target, open helper, row label |
| `launchpad/ui/dashboard_view.py` | Left rail UI, collapse toggle, rebuild with cards, wire click |
| `launchpad/config.py` | `1.6.92` |
| `tests/test_dashboard_array_rail.py` | Pure helper tests |
| `tests/test_dashboard_array_rail_ui.py` | Source markers / collapse setting usage in dashboard_view |
| `tests/test_system_connectivity_version.py` | Version assert |

---

### Task 0: Confirm baseline

```powershell
cd C:\Users\BrianColley\LaunchPad
git worktree add .worktrees/dashboard-array-rail -b feature/dashboard-array-rail feature/contingency-groups
cd .worktrees\dashboard-array-rail
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-08-03-dashboard-array-rail-design.md
```

Expected: `1.6.91` (or higher), spec `True`. No feature commit.

---

### Task 1: Pure array-rail helpers (TDD)

**Files:**
- Create: `launchpad/dashboard_array_rail.py`
- Create: `tests/test_dashboard_array_rail.py`

**Interfaces:**
- `SETTING_ARRAY_RAIL_COLLAPSED = "dashboard_array_rail_collapsed"`
- `filter_dashboard_cards(cards: list, *, category: str, query: str) -> list`
  - If `category` is not `"All"` / empty, keep cards whose `category` equals that value (same as `db.list_cards(category)` behavior: callers may pass already category-filtered cards — **locked:** helper assumes `cards` is the category-scoped list from the DB call, and only applies **search query** matching name/host/category/serial case-insensitive). Simpler locked rule:
  - **Locked:** `filter_dashboard_cards` applies **search only** on the provided list (name, host, category, serial_number). Category filtering stays in the view via `db.list_cards(...)`. This mirrors current `_rebuild` logic.
- `rail_gui_url(card: object) -> str` → `resolve_gui_url(url, host)`
- `can_open_rail_gui(card: object) -> bool` → bool(rail_gui_url)
- `rail_row_title(card: object) -> str` → card name
- `rail_row_subtitle(card: object) -> str` → host (or url if no host)
- `open_rail_gui(card: object) -> str`
  - Raises `ValueError` with message containing `Host or URL` when no target
  - Else `webbrowser.open(url)` and return `"Opened GUI"`
- `collapsed_from_setting(raw: str | None) -> bool` — `"true"` → True, else False
- `setting_from_collapsed(collapsed: bool) -> str` — `"true"` / `"false"`

- [ ] **Step 1: Failing tests**

```python
# tests/test_dashboard_array_rail.py
from types import SimpleNamespace

from launchpad.dashboard_array_rail import (
    SETTING_ARRAY_RAIL_COLLAPSED,
    can_open_rail_gui,
    collapsed_from_setting,
    filter_dashboard_cards,
    open_rail_gui,
    rail_gui_url,
    rail_row_subtitle,
    rail_row_title,
    setting_from_collapsed,
)


def test_setting_key():
    assert SETTING_ARRAY_RAIL_COLLAPSED == "dashboard_array_rail_collapsed"


def test_filter_dashboard_cards_by_query():
    cards = [
        SimpleNamespace(name="Hartford, CT", host="10.1.1.1", category="Remote", serial_number=""),
        SimpleNamespace(name="Tempe, AZ", host="10.2.2.2", category="Remote", serial_number="SN1"),
    ]
    assert [c.name for c in filter_dashboard_cards(cards, query="tempe")] == ["Tempe, AZ"]
    assert [c.name for c in filter_dashboard_cards(cards, query="10.1")] == ["Hartford, CT"]
    assert [c.name for c in filter_dashboard_cards(cards, query="sn1")] == ["Tempe, AZ"]
    assert len(filter_dashboard_cards(cards, query="")) == 2


def test_rail_gui_url_prefers_url_then_host():
    assert rail_gui_url(SimpleNamespace(url="https://gui", host="10.0.0.1")) == "https://gui"
    assert rail_gui_url(SimpleNamespace(url="", host="10.245.16.56")) == "https://10.245.16.56"
    assert rail_gui_url(SimpleNamespace(url="", host="")) == ""
    assert can_open_rail_gui(SimpleNamespace(url="", host="10.0.0.1")) is True
    assert can_open_rail_gui(SimpleNamespace(url="", host="")) is False


def test_rail_row_labels():
    card = SimpleNamespace(name="Anderson, SC", host="10.3.3.3", url="")
    assert rail_row_title(card) == "Anderson, SC"
    assert rail_row_subtitle(card) == "10.3.3.3"


def test_collapse_setting_roundtrip():
    assert collapsed_from_setting("true") is True
    assert collapsed_from_setting("false") is False
    assert collapsed_from_setting(None) is False
    assert setting_from_collapsed(True) == "true"
    assert setting_from_collapsed(False) == "false"


def test_open_rail_gui_opens_browser(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(
        "launchpad.dashboard_array_rail.webbrowser.open",
        lambda url: opened.append(url),
    )
    msg = open_rail_gui(SimpleNamespace(url="", host="10.9.9.9", name="X"))
    assert msg == "Opened GUI"
    assert opened == ["https://10.9.9.9"]


def test_open_rail_gui_requires_target():
    try:
        open_rail_gui(SimpleNamespace(url="", host="", name="X"))
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "host" in str(exc).lower() or "url" in str(exc).lower()
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\dashboard-array-rail
python -m pytest tests/test_dashboard_array_rail.py -v
```

- [ ] **Step 3: Implement `launchpad/dashboard_array_rail.py`**

```python
"""Connection Dashboard collapsible array rail helpers."""

from __future__ import annotations

import webbrowser
from typing import Any

from launchpad.host_volume_health import resolve_gui_url

SETTING_ARRAY_RAIL_COLLAPSED = "dashboard_array_rail_collapsed"


def filter_dashboard_cards(cards: list[Any], *, query: str = "") -> list[Any]:
    q = str(query or "").strip().lower()
    if not q:
        return list(cards)
    out: list[Any] = []
    for card in cards:
        blob = " ".join(
            [
                str(getattr(card, "name", "") or ""),
                str(getattr(card, "host", "") or ""),
                str(getattr(card, "category", "") or ""),
                str(getattr(card, "serial_number", "") or ""),
            ]
        ).lower()
        if q in blob or any(
            q in str(getattr(card, field, "") or "").lower()
            for field in ("name", "host", "category", "serial_number")
        ):
            out.append(card)
    return out


def rail_gui_url(card: Any) -> str:
    return resolve_gui_url(
        str(getattr(card, "url", "") or ""),
        str(getattr(card, "host", "") or ""),
    )


def can_open_rail_gui(card: Any) -> bool:
    return bool(rail_gui_url(card))


def rail_row_title(card: Any) -> str:
    return str(getattr(card, "name", "") or "").strip() or "Unnamed"


def rail_row_subtitle(card: Any) -> str:
    host = str(getattr(card, "host", "") or "").strip()
    if host:
        return host
    return str(getattr(card, "url", "") or "").strip()


def open_rail_gui(card: Any) -> str:
    url = rail_gui_url(card)
    if not url:
        raise ValueError("No Host or URL on this card — set Host or URL in Admin.")
    webbrowser.open(url)
    return "Opened GUI"


def collapsed_from_setting(raw: str | None) -> bool:
    return str(raw or "").strip().lower() == "true"


def setting_from_collapsed(collapsed: bool) -> str:
    return "true" if collapsed else "false"
```

Refine `filter_dashboard_cards` to match existing dashboard logic exactly:

```python
query = query.strip().lower()
filtered = [
    card for card in cards
    if not query
    or query in card.name.lower()
    or query in card.host.lower()
    or query in card.category.lower()
    or query in (getattr(card, "serial_number", "") or "").lower()
]
```

- [ ] **Step 4: Run — expect PASS**

```powershell
python -m pytest tests/test_dashboard_array_rail.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/dashboard_array_rail.py tests/test_dashboard_array_rail.py
git commit -m "Add Connection Dashboard array rail helpers."
```

---

### Task 2: Wire collapsible rail into `dashboard_view.py`

**Files:**
- Modify: `launchpad/ui/dashboard_view.py`
- Create: `tests/test_dashboard_array_rail_ui.py`

**UI requirements:**
- After filters row, main body is a horizontal split: `body_frame` with `rail_frame` (col 0) + `cards_frame` (col 1, weight=1).
- Rail header: label “Arrays” + collapse button (`id` not HTML — use `self.array_rail_toggle` attribute).
- Expanded: `CTkScrollableFrame` of buttons/rows; each enabled row calls `open_rail_gui(card)` and `_set_status(...)`; disabled/muted when `not can_open_rail_gui`.
- Empty list: label “No arrays match.”
- Collapse: hide scroll list / set rail width narrow; save `SETTING_ARRAY_RAIL_COLLAPSED` via `setting_from_collapsed`.
- On `_rebuild` (or equivalent card refresh): after computing `filtered`, call `_rebuild_array_rail(filtered)`.
- Prefer reusing `filter_dashboard_cards` for the search step so rail and grid stay aligned — refactor `_rebuild` to use the helper for the query filter.

**Sketch (adapt to existing grid rows):**

```python
# In __init__ after filters, instead of cards_frame alone on row 2:
self.body_frame = ctk.CTkFrame(self, fg_color="transparent")
self.body_frame.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 16))
self.body_frame.grid_columnconfigure(1, weight=1)
self.body_frame.grid_rowconfigure(0, weight=1)

self.array_rail_collapsed = collapsed_from_setting(
    self.db.get_setting(SETTING_ARRAY_RAIL_COLLAPSED, "false")
)
self.rail_frame = ctk.CTkFrame(self.body_frame, fg_color=self.theme["surface"], width=220)
self.rail_frame.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
# toggle + scrollable list inside rail_frame

self.cards_frame = ctk.CTkScrollableFrame(self.body_frame, fg_color=self.theme["surface"])
self.cards_frame.grid(row=0, column=1, sticky="nsew")
```

```python
def _rebuild_array_rail(self, filtered: list[Card]) -> None:
    # clear list children; if collapsed return after updating toggle text
    # else add a CTkButton per card: text=f"{title}\n{subtitle}", command=partial(self._open_array_gui, card)
    # state=disabled if not can_open_rail_gui(card)

def _open_array_gui(self, card: Card) -> None:
    try:
        message = open_rail_gui(card)
        self._set_status(f"{card.name}: {message}")
    except ValueError as exc:
        self._set_status(str(exc))

def _toggle_array_rail(self) -> None:
    self.array_rail_collapsed = not self.array_rail_collapsed
    self.db.set_setting(
        SETTING_ARRAY_RAIL_COLLAPSED,
        setting_from_collapsed(self.array_rail_collapsed),
    )
    self._apply_array_rail_collapsed()
```

- [ ] **Step 1: Marker tests**

```python
# tests/test_dashboard_array_rail_ui.py
from pathlib import Path

SOURCE = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")


def test_dashboard_array_rail_markers():
    assert "SETTING_ARRAY_RAIL_COLLAPSED" in SOURCE
    assert "open_rail_gui" in SOURCE
    assert "_rebuild_array_rail" in SOURCE
    assert "_toggle_array_rail" in SOURCE
    assert "No arrays match." in SOURCE
    assert "Arrays" in SOURCE
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_dashboard_array_rail_ui.py -v
```

- [ ] **Step 3: Implement UI wiring**

Keep imports at module top. Do not change `_launch_card` SSH behavior.

- [ ] **Step 4: Run helpers + UI markers**

```powershell
python -m pytest tests/test_dashboard_array_rail.py tests/test_dashboard_array_rail_ui.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/dashboard_view.py tests/test_dashboard_array_rail_ui.py
git commit -m "Add collapsible Arrays rail to Connection Dashboard."
```

---

### Task 3: Version bump 1.6.92

**Files:**
- Modify: `launchpad/config.py` → `APP_VERSION = "1.6.92"`
- Modify: `tests/test_system_connectivity_version.py` → assert `"1.6.92"` (rename test fn if it embeds old version)

- [ ] **Step 1: Bump + update version test**

- [ ] **Step 2: Run**

```powershell
python -m pytest tests/test_dashboard_array_rail.py tests/test_dashboard_array_rail_ui.py tests/test_system_connectivity_version.py -v
python -c "from launchpad.config import APP_VERSION; assert APP_VERSION == '1.6.92'"
```

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py
git commit -m "Bump LaunchPad to 1.6.92 for dashboard array rail."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Collapsible left rail on Connection Dashboard | 2 |
| Click → Open GUI only via `resolve_gui_url` | 1–2 |
| Same Category + search as grid | 1 filter + 2 rebuild |
| Persist collapsed state | 1 setting helpers + 2 |
| Empty / no host-or-url messaging | 1–2 |
| No browser-page rail; no Connect from rail | (no edits there) |
| Version 1.6.92 | 3 |

## Self-review notes

- No TBD placeholders.
- `filter_dashboard_cards` search-only keeps DB category call in the view (matches current `_rebuild`).
- Dashboard file is large; rail logic stays thin by using the helper module.
