# Dashboard Click Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop Connection Dashboard from going white / Not Responding on All monitoring on, Storage Inventory, and other header clicks by never decrypting or registering the SSH fleet on the Tk UI thread, shipping as **1.6.173**.

**Architecture:** `ensure_health_dashboard_registered` becomes single-flight (waiters reuse the in-flight result). All monitoring on flips card switches immediately, then persists flags and starts SSH on a worker. Header reports and Excel exports set status (and file dialogs) on the UI thread, then register/open on a worker. `build_health_dashboard_entries` is used from workers only.

**Tech Stack:** Python, CustomTkinter, existing Health server register helpers, pytest (unit + source-marker tests).

**Spec:** `docs/superpowers/specs/2026-08-14-dashboard-click-freeze-design.md`

## Global Constraints

- APP_VERSION bump to **1.6.173** only in the final version task. Do not bump in Tasks 1–3.
- Do not virtualize / recycle the card list, or rewrite GlowCard internals.
- Do not change Monitor on/off meaning, SSH command suites, or browser report page behavior.
- Do not speed up first GlowCard paint (`refresh_cards` stays as 1.6.172).
- Do not debounce Search (already filtered in place).
- Click handlers must start a `threading.Thread` (or return) before any `ensure_health_dashboard_registered` / fleet `resolve_ssh_metrics_auth` / `_health_ssh_cards`. Those calls may live in a nested worker in the same method.
- `filedialog.asksaveasfilename` stays on the UI thread.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch, `LaunchPad-Install/`, or install zips.
- Work from a feature branch off `main` (do not land unfinished work on `main` mid-plan).
- Place imports at the top of modules (no inline imports). `_log` is already imported at the top of `dashboard_view.py` — use that; do not add `from launchpad.ssh_launcher import _log` inside functions.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/monitor.py` | `RegisterSingleFlight` + wrap `ensure_health_dashboard_registered` |
| `launchpad/ui/dashboard_view.py` | All-monitoring / Monitor / header / export click paths off the Tk thread |
| `tests/test_monitor_register_single_flight.py` | Concurrent waiters do not double-run register |
| `tests/test_dashboard_ui_freeze.py` | Source markers for click handlers |
| `launchpad/config.py` + three version pins | `1.6.173` (Task 4 only) |

---

### Task 1: Single-flight Health register

**Files:**
- Modify: `launchpad/monitor.py`
- Create: `tests/test_monitor_register_single_flight.py`

**Interfaces:**
- Consumes: existing `ensure_health_dashboard_registered` body (`ensure_hadoop_linux_cards`, `build_health_dashboard_entries`, `get_health_server`, prune/register)
- Produces:
  - `RegisterSingleFlight.run(self, fn: Callable[[], int]) -> int`
  - `ensure_health_dashboard_registered(db, crypto_key: bytes) -> int` unchanged signature; overlapping calls wait and reuse the in-flight count (or raise the in-flight error)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_monitor_register_single_flight.py`:

```python
import threading
import time

from launchpad.monitor import RegisterSingleFlight


def test_overlapping_runs_share_one_call():
    flight = RegisterSingleFlight()
    started = threading.Event()
    releases = threading.Event()
    calls = {"n": 0}

    def fn() -> int:
        calls["n"] += 1
        started.set()
        assert releases.wait(timeout=2)
        return 7

    results: list[int] = []
    errors: list[BaseException] = []

    def caller() -> None:
        try:
            results.append(flight.run(fn))
        except BaseException as exc:
            errors.append(exc)

    t1 = threading.Thread(target=caller)
    t2 = threading.Thread(target=caller)
    t1.start()
    assert started.wait(timeout=2)
    t2.start()
    time.sleep(0.05)
    releases.set()
    t1.join(timeout=2)
    t2.join(timeout=2)
    assert errors == []
    assert results == [7, 7]
    assert calls["n"] == 1


def test_later_call_after_finish_runs_again():
    flight = RegisterSingleFlight()
    calls = {"n": 0}

    def fn() -> int:
        calls["n"] += 1
        return calls["n"]

    assert flight.run(fn) == 1
    assert flight.run(fn) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_monitor_register_single_flight.py -v`

Expected: FAIL (`RegisterSingleFlight` not defined)

- [ ] **Step 3: Write minimal implementation**

At the top of `launchpad/monitor.py` add `import threading` and `from collections.abc import Callable`.

Add this class above `ensure_health_dashboard_registered`, then wrap the existing function body:

```python
class RegisterSingleFlight:
    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._in_progress = False
        self._last_count = 0
        self._last_error: BaseException | None = None

    def run(self, fn: Callable[[], int]) -> int:
        with self._cv:
            if self._in_progress:
                while self._in_progress:
                    self._cv.wait()
                if self._last_error is not None:
                    raise self._last_error
                return self._last_count
            self._in_progress = True
            self._last_error = None
        try:
            count = fn()
        except BaseException as exc:
            with self._cv:
                self._last_error = exc
                self._in_progress = False
                self._cv.notify_all()
            raise
        with self._cv:
            self._last_count = count
            self._last_error = None
            self._in_progress = False
            self._cv.notify_all()
        return count


_REGISTER_FLIGHT = RegisterSingleFlight()


def _register_health_dashboard(db, crypto_key: bytes) -> int:
    """Register all SSH cards with credentials so the browser page can list them."""
    ensure_hadoop_linux_cards(db)
    entries = build_health_dashboard_entries(db, crypto_key)
    server = get_health_server()
    server.ensure_running()
    active_ids = {entry.card_id for entry in entries}
    server.prune_cards(active_ids)
    if not entries:
        return 0
    for entry in entries:
        _register_entry(server, entry)
    return len(entries)


def ensure_health_dashboard_registered(db, crypto_key: bytes) -> int:
    """Register all SSH cards with credentials so the browser page can list them."""
    return _REGISTER_FLIGHT.run(lambda: _register_health_dashboard(db, crypto_key))
```

Move the current body of `ensure_health_dashboard_registered` into `_register_health_dashboard` (keep the `ensure_hadoop_linux_cards` comment). Do not change `build_health_dashboard_entries` or callers.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_monitor_register_single_flight.py tests/test_dashboard_ui_freeze.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/monitor.py tests/test_monitor_register_single_flight.py
git commit -m "Share one in-flight Health-card register instead of decrypting twice."
```

---

### Task 2: All monitoring on and Monitor clicks off the UI thread

**Files:**
- Modify: `launchpad/ui/dashboard_view.py`
- Modify: `tests/test_dashboard_ui_freeze.py`

**Interfaces:**
- Consumes: Task 1 `ensure_health_dashboard_registered`, `set_all_monitor_enabled`, `set_card_monitor_enabled`, `_probe_card_ssh_status`, `_fetch_ssh_stats_worker`, `_set_card_ssh_monitor_off`
- Produces:
  - `_toggle_all_monitoring` updates `_monitor_states` + widgets on the UI thread, then starts a daemon worker
  - Worker calls `ensure_health_dashboard_registered` then `set_all_monitor_enabled`; if on, starts SSH like Monitor Checked
  - `_toggle_all_monitoring` does **not** call `_fetch_all_ssh_stats`
  - `_set_checked_monitoring` and `_on_card_monitor_toggle` do not call `ensure_health_dashboard_registered` on the click stack (only after `threading.Thread` / not at all)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dashboard_ui_freeze.py`:

```python
def _assert_thread_before_register(body: str) -> None:
    assert "threading.Thread" in body
    thread_at = body.index("threading.Thread")
    if "ensure_health_dashboard_registered" in body:
        assert thread_at < body.index("ensure_health_dashboard_registered")
    if "resolve_ssh_metrics_auth" in body:
        assert thread_at < body.index("resolve_ssh_metrics_auth")
    if "_health_ssh_cards" in body:
        assert thread_at < body.index("_health_ssh_cards")


def test_toggle_all_monitoring_flips_widgets_then_registers_off_thread():
    body = _method("_toggle_all_monitoring")
    states_at = body.index("self._monitor_states")
    thread_at = body.index("threading.Thread")
    assert states_at < thread_at
    assert "set_monitor_enabled" in body
    assert "_fetch_all_ssh_stats" not in body
    _assert_thread_before_register(body)
    assert "set_all_monitor_enabled" in body
    assert "_fetch_ssh_stats_worker" in body
    assert "_probe_card_ssh_status" in body
    assert "_set_card_ssh_monitor_off" in body


def test_set_checked_monitoring_does_not_register_on_click_stack():
    body = _method("_set_checked_monitoring")
    if "ensure_health_dashboard_registered" in body:
        _assert_thread_before_register(body)
    else:
        assert "set_card_monitor_enabled" in body


def test_on_card_monitor_toggle_does_not_register_on_click_stack():
    body = _method("_on_card_monitor_toggle")
    if "ensure_health_dashboard_registered" in body:
        _assert_thread_before_register(body)
    else:
        assert "set_card_monitor_enabled" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dashboard_ui_freeze.py::test_toggle_all_monitoring_flips_widgets_then_registers_off_thread tests/test_dashboard_ui_freeze.py::test_set_checked_monitoring_does_not_register_on_click_stack tests/test_dashboard_ui_freeze.py::test_on_card_monitor_toggle_does_not_register_on_click_stack -v`

Expected: FAIL (`_toggle_all_monitoring` still calls `ensure_health_dashboard_registered` / `_fetch_all_ssh_stats` before a thread)

- [ ] **Step 3: Write minimal implementation**

Replace `_on_card_monitor_toggle` (remove the inline `_log` import) with:

```python
    def _on_card_monitor_toggle(self, card: Card, enabled: bool) -> None:
        try:
            set_card_monitor_enabled(card.id, enabled)
            self._monitor_states[card.id] = enabled
        except Exception as exc:
            _log(f"Monitor toggle failed for {card.name}: {exc}")
            self.status_label.configure(text=f"Monitor toggle failed: {exc}")
            widget = self._find_card_widget(card.id)
            if widget:
                widget.set_monitor_enabled(not enabled)
            return

        widget = self._find_card_widget(card.id)
        if widget:
            widget.set_monitor_enabled(enabled)
        self._sync_master_monitor_switch()
        self._refresh_capacity_alerts()
        if enabled:
            self.status_label.configure(text=f"Monitoring on for {card.name} — refreshing stats...")
            self._probe_card_ssh_status(card.id)
            threading.Thread(target=self._fetch_ssh_stats_worker, args=(card,), daemon=True).start()
        else:
            self.status_label.configure(text=f"Monitoring off for {card.name} — no background SSH.")
            self._set_card_ssh_monitor_off(card.id)
```

Replace `_toggle_all_monitoring` with:

```python
    def _toggle_all_monitoring(self) -> None:
        enabled = bool(self.monitor_all_switch.get())
        ssh_cards = list(self._ssh_cards)
        for card in ssh_cards:
            self._monitor_states[card.id] = enabled
            widget = self._find_card_widget(card.id)
            if widget:
                widget.set_monitor_enabled(enabled)
        self._refresh_capacity_alerts()
        if enabled:
            self.status_label.configure(text="All monitoring on — refreshing stats for SSH cards...")
        else:
            self.status_label.configure(text="All monitoring off — no background SSH.")
            for card in ssh_cards:
                self._set_card_ssh_monitor_off(card.id)

        def worker() -> None:
            try:
                ensure_health_dashboard_registered(self.db, self.crypto_key)
                set_all_monitor_enabled(enabled)
            except Exception as exc:
                self.after(0, lambda: self.status_label.configure(text=f"Monitor toggle failed: {exc}"))
                self.after(0, self._sync_master_monitor_switch)
                return
            if not enabled:
                return
            for card in ssh_cards:
                self.after(0, lambda c=card: self._probe_card_ssh_status(c.id))
                if card.id not in self._stats_in_flight:
                    threading.Thread(
                        target=self._fetch_ssh_stats_worker,
                        args=(card,),
                        daemon=True,
                    ).start()

        threading.Thread(target=worker, daemon=True).start()
```

In `_set_checked_monitoring`, delete the `ensure_health_dashboard_registered(self.db, self.crypto_key)` line. Keep `set_card_monitor_enabled`, widget updates, `_probe_card_ssh_status`, and `_fetch_ssh_stats_worker` as they are today.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dashboard_ui_freeze.py tests/test_monitor_register_single_flight.py tests/test_dashboard_health_alerts.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/dashboard_view.py tests/test_dashboard_ui_freeze.py
git commit -m "Turn All monitoring on without blocking the dashboard UI thread."
```

---

### Task 3: Header reports and Excel exports off the UI thread

**Files:**
- Modify: `launchpad/ui/dashboard_view.py`
- Modify: `tests/test_dashboard_ui_freeze.py`

**Interfaces:**
- Consumes: `build_health_dashboard_entries`, `get_health_server`, existing `open_*_for_cards` / `server.open_*` / Excel export helpers
- Produces:
  - `_open_sync_browser_report` and `_open_entries_browser_report` helpers
  - Header openers and Excel exports no longer call `_health_ssh_cards`, fleet `resolve_ssh_metrics_auth`, or `ensure_health_dashboard_registered` before `threading.Thread`

Add `build_health_dashboard_entries` to the existing `from launchpad.monitor import (` block at the top of `dashboard_view.py`.

**NO_CREDENTIALS** status string (reuse everywhere an opener currently shows it):

`No SSH cards with credentials found. Add SSH Password or a key in Admin first.`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dashboard_ui_freeze.py`:

```python
HEADER_OPENERS = (
    "_open_storage_inventory",
    "_open_health_dashboard_all",
    "_open_capacity_report_all",
    "_open_fc_wwpn_report_all",
    "_open_site_lookup_all",
    "_open_ansible_pad",
    "_open_host_power",
    "_open_contingency_groups",
    "_open_fc_consistgrp",
    "_open_lun_builder",
    "_open_volume_find",
    "_open_host_volume_health",
    "_open_system_connectivity",
)

EXCEL_EXPORTERS = (
    "_export_fc_wwpn_excel",
    "_export_snapshot_schedule_excel",
    "_export_capacity_excel",
    "_export_dell_report_excel",
)


def test_header_openers_register_off_ui_thread():
    for name in HEADER_OPENERS:
        _assert_thread_before_register(_method(name))


def test_excel_exporters_register_off_ui_thread():
    for name in EXCEL_EXPORTERS:
        body = _method(name)
        assert "asksaveasfilename" in body
        _assert_thread_before_register(body)
        assert body.index("asksaveasfilename") < body.index("threading.Thread")
```

The four Excel methods above are the ones that currently call `ensure_health_dashboard_registered` after a file dialog.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dashboard_ui_freeze.py::test_header_openers_register_off_ui_thread tests/test_dashboard_ui_freeze.py::test_excel_exporters_register_off_ui_thread -v`

Expected: FAIL (`ensure_health_dashboard_registered` / `_health_ssh_cards` still before `threading.Thread`)

- [ ] **Step 3: Write minimal implementation**

Add these helpers near the header openers (before `_open_health_dashboard_all`). Use module-top `_log`.

```python
    def _open_sync_browser_report(
        self,
        *,
        status: str,
        fail_log: str,
        open_url,
        summary: str,
    ) -> None:
        self.status_label.configure(text=status)
        self.update_idletasks()

        def worker() -> None:
            try:
                server = get_health_server()
                server.sync_from_app()
                url = open_url(server)
                _log(f"{summary} ({url})")
                self.after(0, lambda u=url, s=summary: self._set_status(s, url=u))
            except Exception as exc:
                _log(f"{fail_log}: {exc}")
                self.after(0, lambda: self._set_status(f"{fail_log}: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def _open_entries_browser_report(
        self,
        *,
        status: str,
        fail_log: str,
        opener,
        summary_for,
        after_success=None,
    ) -> None:
        self.status_label.configure(text=status)
        self.update_idletasks()

        def worker() -> None:
            try:
                entries = build_health_dashboard_entries(self.db, self.crypto_key)
                if not entries:
                    self.after(
                        0,
                        lambda: self.status_label.configure(
                            text="No SSH cards with credentials found. Add SSH Password or a key in Admin first."
                        ),
                    )
                    return
                result = opener(entries)
                if isinstance(result, tuple):
                    url, extra = result
                    summary = summary_for(entries, extra)
                else:
                    url = result
                    summary = summary_for(entries)
                _log(f"{summary} ({url})")
                self.after(0, lambda u=url, s=summary: self._set_status(s, url=u))
                if after_success is not None:
                    self.after(0, after_success)
            except Exception as exc:
                _log(f"{fail_log}: {exc}")
                self.after(0, lambda: self._set_status(f"{fail_log}: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
```

Replace the sync-style openers (delete the UI-thread `ensure_health_dashboard_registered` try/except and the nested worker) with:

```python
    def _open_storage_inventory(self) -> None:
        self._open_sync_browser_report(
            status="Opening Storage Inventory…",
            fail_log="Storage Inventory failed",
            open_url=lambda server: server.open_storage_inventory(),
            summary="Storage Inventory opened — refresh live for fleet device inventory.",
        )

    def _open_contingency_groups(self) -> None:
        self._open_sync_browser_report(
            status="Opening Consistency Groups…",
            fail_log="Consistency Groups failed",
            open_url=lambda server: server.open_contingency_groups(),
            summary="Consistency Groups opened — reference library only; it does not modify arrays.",
        )

    def _open_fc_consistgrp(self) -> None:
        self._open_sync_browser_report(
            status="Opening FlashCopy CGs…",
            fail_log="FlashCopy CGs failed",
            open_url=lambda server: server.open_fc_consistgrp(),
            summary="FlashCopy CGs opened — confirmed actions mutate arrays on the linked array.",
        )

    def _open_lun_builder(self) -> None:
        self._open_sync_browser_report(
            status="Opening LUN Builder…",
            fail_log="LUN Builder failed",
            open_url=lambda server: server.open_lun_builder(),
            summary="LUN Builder opened — planning and CRUD are available.",
        )

    def _open_volume_find(self) -> None:
        self._open_sync_browser_report(
            status="Opening Volume Find…",
            fail_log="Volume Find failed",
            open_url=lambda server: server.open_volume_find(),
            summary="Volume Find opened — cache and live search are available.",
        )

    def _open_host_volume_health(self) -> None:
        self._open_sync_browser_report(
            status="Opening Hosts & Volumes Health…",
            fail_log="Hosts & Volumes Health failed",
            open_url=lambda server: server.open_host_volume_health(),
            summary="Hosts & Volumes Health opened — refresh live for offline/degraded rows.",
        )

    def _open_system_connectivity(self) -> None:
        self._open_sync_browser_report(
            status="Opening System Connectivity…",
            fail_log="System Connectivity failed",
            open_url=lambda server: server.open_system_connectivity(),
            summary="System Connectivity opened — refresh live for Call Home/DNS/SNMP/NTP.",
        )
```

Replace entry-style openers. Remove UI-thread `_health_ssh_cards` / `resolve_ssh_metrics_auth` loops and `ensure_health_dashboard_registered`. Example for Health Dashboard:

```python
    def _open_health_dashboard_all(self) -> None:
        self._open_entries_browser_report(
            status="Opening health dashboard...",
            fail_log="Health dashboard failed",
            opener=open_health_dashboard_for_cards,
            summary_for=lambda entries, results: (
                f"Health dashboard opened — {len(results)} site(s) loaded (monitoring off). "
                "Turn on Monitor per site, or All monitoring on, to connect."
            ),
            after_success=self._refresh_capacity_alerts,
        )
```

`open_health_dashboard_for_cards` returns `(url, results)`. Other `open_*_for_cards` return a URL string. For those:

```python
    def _open_capacity_report_all(self) -> None:
        self._open_entries_browser_report(
            status="Opening capacity report...",
            fail_log="Capacity report failed",
            opener=open_capacity_report_for_cards,
            summary_for=lambda entries: (
                f"Capacity report opened — {len(entries)} site(s) loaded (monitoring off). "
                "Turn on monitoring on the page, then Refresh On Sites."
            ),
            after_success=self._refresh_capacity_alerts,
        )

    def _open_fc_wwpn_report_all(self) -> None:
        self._open_entries_browser_report(
            status="Opening FC WWPN report...",
            fail_log="FC WWPN report failed",
            opener=open_fc_wwpn_report_for_cards,
            summary_for=lambda entries: (
                f"FC WWPN report opened — {len(entries)} site(s). "
                "Turn on Monitor, refresh, then open Hosts & LUN Mappings."
            ),
        )

    def _open_site_lookup_all(self) -> None:
        self._open_entries_browser_report(
            status="Opening Site Lookup...",
            fail_log="Site Lookup failed",
            opener=open_site_lookup_for_cards,
            summary_for=lambda entries: (
                f"Site Lookup opened — {len(entries)} site(s). "
                "Pick a site, then Live Refresh to load hosts, volumes, and pools."
            ),
        )

    def _open_ansible_pad(self) -> None:
        self._open_entries_browser_report(
            status="Opening Ansible Pad…",
            fail_log="Ansible Pad failed",
            opener=open_ansible_pad_for_cards,
            summary_for=lambda entries: (
                f"Ansible Pad opened — {len(entries)} site(s) are available for package export."
            ),
        )

    def _open_host_power(self, card_id: int | None = None) -> None:
        self._open_entries_browser_report(
            status="Opening Host Power…",
            fail_log="Host Power failed",
            opener=lambda entries: open_host_power_for_cards(entries, card_id=card_id),
            summary_for=lambda entries: (
                "Host Power opened — select a Hadoop host and confirm before powering it off."
            ),
        )
```

Keep each opener’s existing status punctuation (ellipsis vs `...`) as in the snippets above.

**Excel:** keep `filedialog.asksaveasfilename` on the UI thread. Remove `_health_ssh_cards()` before the dialog (do not decrypt to decide whether to show the dialog). Remove the UI-thread `ensure_health_dashboard_registered` try/except. Move that call into the existing export `worker()` as the first line (before `export_*` / `server.export_*`). Example for FC WWPN — apply the same to Snapshot, Capacity, and Dell:

```python
        def worker() -> None:
            try:
                ensure_health_dashboard_registered(self.db, self.crypto_key)
                result = export_fc_wwpn_excel(
                    self.db,
                    self.crypto_key,
                    path,
                    progress=progress,
                )
```

If an exporter currently bails when `_health_ssh_cards()` is empty, let the worker fail with the existing error path, or after the dialog check `any(card.card_type == "ssh" for card in self.db.list_cards())` with **no** `ssh_stats_prereq_message` / `resolve_ssh_metrics_auth`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dashboard_ui_freeze.py tests/test_monitor_register_single_flight.py tests/test_dashboard_header_wrap.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/dashboard_view.py tests/test_dashboard_ui_freeze.py
git commit -m "Open dashboard reports without decrypting SSH cards on the UI thread."
```

---

### Task 4: Bump APP_VERSION to 1.6.173

**Files:**
- Modify: `launchpad/config.py` (`APP_VERSION = "1.6.173"`)
- Modify: `tests/test_system_connectivity_version.py` (assert `1.6.173`; rename to `test_app_version_16173` if you touch the name)
- Modify: `tests/test_capacity_unit_js.py` (`test_app_version_153` assertion → `1.6.173`)
- Modify: `tests/test_hadoop_sudo_wire.py` (assertion → `1.6.173`; rename to `test_version_173` if you touch the name)

**Interfaces:**
- Consumes: Tasks 1–3 complete
- Produces: `APP_VERSION == "1.6.173"`

On this branch `APP_VERSION` is `1.6.172`. Set **1.6.173**.

- [ ] **Step 1: Write the failing assertion change**

Set the three test assertions to `"1.6.173"`. Do not change `config.py` yet.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_system_connectivity_version.py tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py -k version -v`

Expected: FAIL (`1.6.172` != `1.6.173`)

- [ ] **Step 3: Bump version**

In `launchpad/config.py`: `APP_VERSION = "1.6.173"`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_system_connectivity_version.py tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py tests/test_dashboard_ui_freeze.py tests/test_monitor_register_single_flight.py -k "version or freeze or register or monitoring or header or excel" -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py
git commit -m "Bump version to 1.6.173 for dashboard click freeze fix."
```

---

## Spec coverage

| Spec requirement | Task |
|------------------|------|
| Single-flight `ensure_health_dashboard_registered` | 1 |
| All monitoring on flips switches immediately; persist + SSH on worker | 2 |
| All monitoring on does not call `_fetch_all_ssh_stats` on UI thread | 2 |
| Monitor Checked / per-card Monitor do not register on UI thread | 2 |
| Header reports status then worker register/open | 3 |
| No fleet `resolve_ssh_metrics_auth` / `_health_ssh_cards` on Tk click stack | 3 |
| Excel: file dialog on UI; register/export on worker | 3 |
| APP_VERSION 1.6.173 | 4 |
