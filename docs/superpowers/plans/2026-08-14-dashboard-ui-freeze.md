# Dashboard UI Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop Connection Dashboard from going Not Responding on Search and card rebuilds by filtering widgets in place and moving Health-card registration off the UI thread, shipping as **1.6.172**.

**Architecture:** Search `KeyRelease` calls `_filter_visible_cards` which `grid` / `grid_remove` existing GlowCards and rebuilds the array rail. `refresh_cards` still rebuilds on category / initial load / reorder, but `_load_monitor_states` only reads `get_monitor_states()`. Startup `ensure_health_dashboard_registered` runs on a daemon thread. Refresh Stats Monitor-on gate stays as today.

**Tech Stack:** Python, CustomTkinter, existing `filter_dashboard_cards`, pytest source-marker tests.

**Spec:** `docs/superpowers/specs/2026-08-14-dashboard-ui-freeze-design.md`

## Global Constraints

- APP_VERSION bump to **1.6.172** only in the final version task. Do not bump in Tasks 1–2.
- Do not virtualize / recycle the card list.
- Do not debounce a full `refresh_cards` as the search solution (filter in place instead).
- Do not change Monitor semantics, SSH command suites, or browser report progress bars.
- Do not rewrite GlowCard internals.
- Reuse `filter_dashboard_cards` (no match-rule change).
- Category change still uses `refresh_cards()`.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch, `LaunchPad-Install/`, or install zips.
- Work from a feature branch off `main` (do not land unfinished work on `main` mid-plan).
- Place imports at the top of modules (no inline imports). `_log` is already imported at the top of `dashboard_view.py` — use that; do not add `from launchpad.ssh_launcher import _log` inside functions.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/ui/dashboard_view.py` | In-place search; `_load_monitor_states` without register; threaded startup register |
| `tests/test_dashboard_ui_freeze.py` | Source markers for search / register / Refresh Stats |
| `launchpad/config.py` + three version pins | `1.6.172` (Task 3 only) |

---

### Task 1: Filter Search in place

**Files:**
- Modify: `launchpad/ui/dashboard_view.py`
- Create: `tests/test_dashboard_ui_freeze.py`

**Interfaces:**
- Consumes: existing `filter_dashboard_cards`, `self.card_widgets`, `self._visible_cards`, `_rebuild_array_rail`, `_update_selection_status`, `_card_columns`
- Produces:
  - `DashboardView._filter_visible_cards(self) -> None`
  - Search `<KeyRelease>` bound to `_filter_visible_cards`, **not** `refresh_cards`

**Filter rules:**
- Read `self.search_entry.get()`.
- Build the card list from `self.card_widgets` in widget order via `self._visible_cards`.
- `filtered = filter_dashboard_cards(cards, query=query)`.
- For each widget: if `card_id` in filtered ids, `grid` at next 4-column slot (`divmod(index, self._card_columns)`, padx=10, pady=10, sticky=`nsew`); else `grid_remove()`.
- `_rebuild_array_rail(filtered)` then `_update_selection_status()`.
- Empty query shows all built widgets (current category set from last `refresh_cards`).
- Do not destroy widgets, decrypt keys, or call `ensure_health_dashboard_registered`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dashboard_ui_freeze.py`:

```python
from pathlib import Path

SOURCE = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")


def _method(name: str) -> str:
    marker = f"    def {name}"
    rest = SOURCE.split(marker, 1)[1]
    nxt = rest.find("\n    def ")
    return rest if nxt < 0 else rest[:nxt]


def test_search_keyrelease_filters_in_place_not_refresh_cards():
    bind = SOURCE.split('self.search_entry.bind("<KeyRelease>"', 1)[1].split("\n", 1)[0]
    assert "refresh_cards" not in bind
    assert "_filter_visible_cards" in bind
    assert "def _filter_visible_cards" in SOURCE
    body = _method("_filter_visible_cards")
    assert "filter_dashboard_cards" in body
    assert "grid_remove" in body
    assert "_rebuild_array_rail" in body
    assert "_update_selection_status" in body
    assert "ensure_health_dashboard_registered" not in body
    assert "refresh_cards()" not in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dashboard_ui_freeze.py::test_search_keyrelease_filters_in_place_not_refresh_cards -v`

Expected: FAIL (`_filter_visible_cards` not in source / bind still `refresh_cards`)

- [ ] **Step 3: Write minimal implementation**

In `launchpad/ui/dashboard_view.py`, change the Search bind from:

```python
        self.search_entry.bind("<KeyRelease>", lambda _e: self.refresh_cards())
```

to:

```python
        self.search_entry.bind("<KeyRelease>", lambda _e: self._filter_visible_cards())
```

Add this method near `refresh_cards` (before or after it):

```python
    def _filter_visible_cards(self) -> None:
        query = self.search_entry.get() if hasattr(self, "search_entry") else ""
        cards = [
            self._visible_cards[widget.card_id]
            for widget in self.card_widgets
            if widget.card_id in self._visible_cards
        ]
        filtered = filter_dashboard_cards(cards, query=query)
        match_ids = {card.id for card in filtered}
        index = 0
        cols = self._card_columns
        for widget in self.card_widgets:
            if widget.card_id in match_ids:
                row, col = divmod(index, cols)
                widget.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
                index += 1
            else:
                widget.grid_remove()
        self._rebuild_array_rail(filtered)
        self._update_selection_status()
```

`filter_dashboard_cards` is already imported from `launchpad.dashboard_array_rail`. Do not change match rules. Category menu stays `command=lambda _v: self.refresh_cards()`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dashboard_ui_freeze.py tests/test_dashboard_array_rail.py tests/test_dashboard_array_rail_ui.py tests/test_dashboard_header_wrap.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/dashboard_view.py tests/test_dashboard_ui_freeze.py
git commit -m "Filter dashboard Search in place instead of rebuilding cards."
```

---

### Task 2: Register Health cards off the UI thread

**Files:**
- Modify: `launchpad/ui/dashboard_view.py`
- Modify: `tests/test_dashboard_ui_freeze.py`

**Interfaces:**
- Consumes: `get_monitor_states`, `ensure_health_dashboard_registered`, existing `after(200, self._register_health_cards_main_thread)`
- Produces:
  - `_load_monitor_states` calls `get_monitor_states()` only (no `ensure_health_dashboard_registered`)
  - `_register_health_cards_main_thread` starts a `threading.Thread(daemon=True)` whose target calls `ensure_health_dashboard_registered`
  - Failures `_log` as today; do not freeze the dashboard
  - Refresh Stats still skips Monitor-off cards; **Refreshing SSH card stats...** only after a non-empty `fetchable` list

`_log` is already imported at module top — use it in the worker. Do not add inline `from launchpad.ssh_launcher import _log`. If you update `status_label` from the worker, marshal with `self.after(0, ...)`. Logging does not need a status line.

Keep `ensure_health_dashboard_registered` on Monitor Checked / All monitoring / opening reports (those paths already call it).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dashboard_ui_freeze.py`:

```python
def test_load_monitor_states_does_not_register_health_cards():
    body = _method("_load_monitor_states")
    assert "get_monitor_states" in body
    assert "ensure_health_dashboard_registered" not in body


def test_startup_health_register_runs_on_worker_thread():
    body = _method("_register_health_cards_main_thread")
    assert "ensure_health_dashboard_registered" in body
    assert "threading.Thread" in body
    assert "daemon=True" in body


def test_refresh_stats_skips_monitor_off_before_ssh_status():
    body = _method("_fetch_all_ssh_stats")
    assert "_is_monitor_on" in body
    assert "Refreshing SSH card stats..." in body
    assert "No sites monitoring." in body
    fetch_status_at = body.index("Refreshing SSH card stats...")
    fetchable_return_at = body.index("if not fetchable:")
    assert fetchable_return_at < fetch_status_at
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dashboard_ui_freeze.py -v`

Expected: FAIL (`ensure_health_dashboard_registered` still in `_load_monitor_states`; no `threading.Thread` in register hook)

- [ ] **Step 3: Write minimal implementation**

Replace `_load_monitor_states` with:

```python
    def _load_monitor_states(self) -> None:
        try:
            self._monitor_states = get_monitor_states()
        except Exception as exc:
            _log(f"Could not load monitor states: {exc}")
            self._monitor_states = {}
```

Remove the `from launchpad.ssh_launcher import _log` inside that method if present.

Replace `_register_health_cards_main_thread` with:

```python
    def _register_health_cards_main_thread(self) -> None:
        def worker() -> None:
            try:
                count = ensure_health_dashboard_registered(self.db, self.crypto_key)
                if count:
                    _log(f"Health dashboard pre-registered {count} SSH card(s)")
            except Exception as exc:
                _log(f"Health dashboard pre-register failed: {exc}")

        threading.Thread(target=worker, daemon=True).start()
```

Leave `self.after(200, self._register_health_cards_main_thread)` as the schedule from `__init__`. Do not change `_fetch_all_ssh_stats` unless a test fails (the Monitor-off gate and status placement already match the spec).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dashboard_ui_freeze.py tests/test_dashboard_header_wrap.py tests/test_dashboard_health_alerts.py tests/test_storage_inventory_dashboard.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/dashboard_view.py tests/test_dashboard_ui_freeze.py
git commit -m "Register Health cards off the UI thread after dashboard load."
```

---

### Task 3: Bump APP_VERSION to 1.6.172

**Files:**
- Modify: `launchpad/config.py` (`APP_VERSION = "1.6.172"`)
- Modify: `tests/test_system_connectivity_version.py` (assert `1.6.172`; rename to `test_app_version_16172` if you touch the name)
- Modify: `tests/test_capacity_unit_js.py` (`test_app_version_153` assertion → `1.6.172`)
- Modify: `tests/test_hadoop_sudo_wire.py` (assertion → `1.6.172`; rename to `test_version_172` if you touch the name)

**Interfaces:**
- Consumes: Tasks 1–2 complete
- Produces: `APP_VERSION == "1.6.172"`

On this branch `APP_VERSION` is `1.6.171`. Set **1.6.172**.

- [ ] **Step 1: Write the failing assertion change**

Set the three test assertions to `"1.6.172"`. Do not change `config.py` yet.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_system_connectivity_version.py tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py -k version -v`

Expected: FAIL (`1.6.171` != `1.6.172`)

- [ ] **Step 3: Bump version**

In `launchpad/config.py`: `APP_VERSION = "1.6.172"`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_system_connectivity_version.py tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py tests/test_dashboard_ui_freeze.py -k "version or freeze or filter or register or refresh_stats" -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py
git commit -m "Bump version to 1.6.172 for dashboard UI freeze fix."
```

---

## Spec coverage

| Spec requirement | Task |
|------------------|------|
| Search does not call `refresh_cards` | 1 |
| In-place `grid` / `grid_remove` + array rail | 1 |
| Empty query shows all built cards | 1 |
| `_load_monitor_states` does not register | 2 |
| Startup register on daemon thread | 2 |
| Refresh Stats Monitor-on only; status after fetchable | 2 |
| Category still `refresh_cards` | 1 (unchanged bind) |
| APP_VERSION 1.6.172 | 3 |
