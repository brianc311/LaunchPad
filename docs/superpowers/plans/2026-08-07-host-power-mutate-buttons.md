# Host Power Mutate Buttons + Clear Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Host Power’s generic Run button with confirm-gated **Stop services then shutdown** and **Shutdown only**, keep Preview as a dry-run of both sequences, add **Clear log**, and stop precheck F from spinning silently.

**Architecture:** Reuse `POST /api/host-power/preview` and `POST /api/host-power/run`. Preview returns both `stop_then_shutdown` and `shutdown_only` step lists per host. Run requires `mode`. Shutdown-only picks the last `Power -` OS shutdown step. Precheck SSH timeout is 45s; mutate stays 120s. The page drops `id="run"` and adds the two mutate buttons plus Clear log.

**Tech Stack:** Python, existing Paramiko card SSH runner, HealthServer HTML/JS, pytest.

**Spec:** `docs/superpowers/specs/2026-08-07-host-power-mutate-buttons-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.144`; bump to `1.6.145` in the UI/version task.
- Native LaunchPad SSH only — do not call Ansible Pad.
- Mutate still requires `confirm: true`. A–F stay read-only (no confirm).
- `POST /api/host-power/run` requires `mode`: `"stop_then_shutdown"` or `"shutdown_only"`. Missing/invalid mode → HTTP 400.
- Keep `/api/host-power/run`; do not add new mutate endpoints.
- `Power -` card lines remain the only mutate source. Do not add new preset labels.
- Stop-then-shutdown: first failed step aborts remaining steps on that host only.
- Precheck SSH timeout **45s**; mutate SSH timeout **120s**.
- Host Power JS lives in a Python `"""` string: write JS newlines as `"\\n"`, never `"\n"`.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task’s commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch or install zips.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/host_power_ops.py` | Mode constants, shutdown-step picker, preview both sequences, filter steps by mode, timeout constants |
| `launchpad/health_server.py` | Preview payload (via ops), `/run` requires `mode`, precheck timeout 45s, mutate timeout 120s |
| `launchpad/host_power.py` | Remove Run button; add mutate buttons + Clear log; confirm label; F `Running…`; disable mutate until confirm |
| `launchpad/config.py` | `APP_VERSION` → `1.6.145` |
| `tests/test_host_power_ops.py` | Mode, shutdown picker, preview both lists |
| `tests/test_host_power_api.py` | Run `mode` 400, shutdown_only vs stop_then_shutdown, timeouts |
| `tests/test_host_power_page.py` | Page markers |
| `tests/test_system_connectivity_version.py` | Version pin `1.6.145` |
| `tests/test_hadoop_sudo_wire.py` | Version pin `1.6.145` |

---

### Task 1: Mode, shutdown step, preview both sequences

**Files:**
- Modify: `launchpad/host_power_ops.py`
- Modify: `tests/test_host_power_ops.py`

**Interfaces:**
- Consumes: existing `extract_power_steps`, `build_host_power_preview`, `_PRECHECK_MUTATE_RE`
- Produces:
  - `HOST_POWER_MODE_STOP_THEN_SHUTDOWN = "stop_then_shutdown"`
  - `HOST_POWER_MODE_SHUTDOWN_ONLY = "shutdown_only"`
  - `HOST_POWER_MODES = frozenset({HOST_POWER_MODE_STOP_THEN_SHUTDOWN, HOST_POWER_MODE_SHUTDOWN_ONLY})`
  - `HOST_POWER_PRECHECK_SSH_TIMEOUT = 45`
  - `HOST_POWER_MUTATE_SSH_TIMEOUT = 120`
  - `normalize_host_power_mode(mode: str) -> str` — strip/lower; raise `ValueError("Host Power mode must be stop_then_shutdown or shutdown_only")` if missing/invalid
  - `select_shutdown_power_step(steps: list[dict[str, str]]) -> dict[str, str] | None` — last step whose label is exactly `Power - OS Shutdown` **or** whose command matches `_PRECHECK_MUTATE_RE`
  - `steps_for_host_power_mode(steps: list[dict[str, str]], mode: str) -> list[dict[str, str]]` — all steps for stop-then-shutdown; `[shutdown_step]` or `[]` for shutdown-only
  - `build_host_power_preview` host entries include `steps` (unchanged, full `Power -` list), plus `stop_then_shutdown` (same list) and `shutdown_only` (0 or 1 step). Missing shutdown step adds warning `"{name}: no OS shutdown Power - step"`; preview `ok` stays False only for existing reasons (missing host / no `Power -` steps), not solely because shutdown-only is empty

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_host_power_ops.py`:

```python
from launchpad.host_power_ops import (
    HOST_POWER_MODE_SHUTDOWN_ONLY,
    HOST_POWER_MODE_STOP_THEN_SHUTDOWN,
    HOST_POWER_MUTATE_SSH_TIMEOUT,
    HOST_POWER_PRECHECK_SSH_TIMEOUT,
    HOST_POWER_MODES,
    normalize_host_power_mode,
    select_shutdown_power_step,
    steps_for_host_power_mode,
)


def test_host_power_mode_and_timeout_constants():
    assert HOST_POWER_MODE_STOP_THEN_SHUTDOWN == "stop_then_shutdown"
    assert HOST_POWER_MODE_SHUTDOWN_ONLY == "shutdown_only"
    assert HOST_POWER_MODES == {
        HOST_POWER_MODE_STOP_THEN_SHUTDOWN,
        HOST_POWER_MODE_SHUTDOWN_ONLY,
    }
    assert HOST_POWER_PRECHECK_SSH_TIMEOUT == 45
    assert HOST_POWER_MUTATE_SSH_TIMEOUT == 120


def test_normalize_host_power_mode():
    assert normalize_host_power_mode("stop_then_shutdown") == "stop_then_shutdown"
    assert normalize_host_power_mode(" SHUTDOWN_ONLY ") == "shutdown_only"
    with pytest.raises(ValueError, match="mode"):
        normalize_host_power_mode("")
    with pytest.raises(ValueError, match="mode"):
        normalize_host_power_mode("run")


def test_select_shutdown_power_step_prefers_last_match():
    steps = [
        {"label": "Power - Stop YARN", "command": "sudo systemctl stop yarn"},
        {"label": "Power - Halt extra", "command": "sudo halt"},
        {"label": "Power - OS Shutdown", "command": "sudo shutdown -h now"},
    ]
    assert select_shutdown_power_step(steps) == steps[2]
    assert select_shutdown_power_step(steps[:2]) == steps[1]
    assert select_shutdown_power_step(steps[:1]) is None


def test_steps_for_host_power_mode_filters():
    steps = [
        {"label": "Power - Stop YARN", "command": "sudo systemctl stop yarn"},
        {"label": "Power - OS Shutdown", "command": "sudo shutdown -h now"},
    ]
    assert steps_for_host_power_mode(steps, "stop_then_shutdown") == steps
    assert steps_for_host_power_mode(steps, "shutdown_only") == [steps[1]]
    assert steps_for_host_power_mode(steps[:1], "shutdown_only") == []


def test_preview_includes_both_step_lists_and_shutdown_warning():
    preview = build_host_power_preview(
        [
            {
                "id": 1,
                "name": "hn1",
                "host": "10.0.0.1",
                "commands": [
                    ("Power - Stop YARN", "sudo systemctl stop yarn"),
                    ("Power - OS Shutdown", "sudo shutdown -h now"),
                ],
            },
            {
                "id": 2,
                "name": "hn2",
                "host": "10.0.0.2",
                "commands": [("Power - Stop YARN", "sudo systemctl stop yarn")],
            },
        ]
    )
    assert preview["ok"] is True
    h1, h2 = preview["hosts"]
    assert h1["stop_then_shutdown"] == h1["steps"]
    assert h1["shutdown_only"] == [
        {"label": "Power - OS Shutdown", "command": "sudo shutdown -h now"}
    ]
    assert h2["shutdown_only"] == []
    assert any("hn2" in w and "shutdown" in w.lower() for w in preview["warnings"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_host_power_ops.py::test_host_power_mode_and_timeout_constants tests/test_host_power_ops.py::test_normalize_host_power_mode tests/test_host_power_ops.py::test_select_shutdown_power_step_prefers_last_match tests/test_host_power_ops.py::test_steps_for_host_power_mode_filters tests/test_host_power_ops.py::test_preview_includes_both_step_lists_and_shutdown_warning -q`

Expected: FAIL (import / attribute errors)

- [ ] **Step 3: Write minimal implementation**

In `launchpad/host_power_ops.py` add (near existing constants):

```python
HOST_POWER_MODE_STOP_THEN_SHUTDOWN = "stop_then_shutdown"
HOST_POWER_MODE_SHUTDOWN_ONLY = "shutdown_only"
HOST_POWER_MODES = frozenset(
    {HOST_POWER_MODE_STOP_THEN_SHUTDOWN, HOST_POWER_MODE_SHUTDOWN_ONLY}
)
HOST_POWER_PRECHECK_SSH_TIMEOUT = 45
HOST_POWER_MUTATE_SSH_TIMEOUT = 120
OS_SHUTDOWN_POWER_LABEL = "Power - OS Shutdown"


def normalize_host_power_mode(mode: str) -> str:
    value = str(mode or "").strip().lower()
    if value not in HOST_POWER_MODES:
        raise ValueError(
            "Host Power mode must be stop_then_shutdown or shutdown_only"
        )
    return value


def select_shutdown_power_step(steps: list[dict[str, str]]) -> dict[str, str] | None:
    matched: dict[str, str] | None = None
    for step in steps:
        label = str(step.get("label") or "")
        command = str(step.get("command") or "")
        if label == OS_SHUTDOWN_POWER_LABEL or _PRECHECK_MUTATE_RE.search(command):
            matched = step
    return matched


def steps_for_host_power_mode(
    steps: list[dict[str, str]],
    mode: str,
) -> list[dict[str, str]]:
    mode_n = normalize_host_power_mode(mode)
    if mode_n == HOST_POWER_MODE_STOP_THEN_SHUTDOWN:
        return list(steps)
    shutdown = select_shutdown_power_step(steps)
    return [shutdown] if shutdown else []
```

Update `build_host_power_preview` so each `host_entry` also sets:

```python
        shutdown_steps = steps_for_host_power_mode(
            steps, HOST_POWER_MODE_SHUTDOWN_ONLY
        )
        host_entry: dict[str, Any] = {
            "card_id": card_id,
            "name": name,
            "host": host,
            "steps": steps,
            "stop_then_shutdown": steps,
            "shutdown_only": shutdown_steps,
        }
        if steps and not shutdown_steps:
            msg = f"{name}: no OS shutdown Power - step"
            host_warnings.append(msg)
            warnings.append(msg)
```

Keep existing missing-host / no-`Power -` warning + `ok = False` logic.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_host_power_ops.py -q`

Expected: PASS (including existing preview / run abort tests)

- [ ] **Step 5: Commit**

```powershell
git add launchpad/host_power_ops.py tests/test_host_power_ops.py
git commit -m "Add Host Power mutate modes and shutdown-only preview steps."
```

---

### Task 2: HealthServer run mode + precheck timeout

**Files:**
- Modify: `launchpad/health_server.py`
- Modify: `tests/test_host_power_api.py`

**Interfaces:**
- Consumes: `normalize_host_power_mode`, `steps_for_host_power_mode`, `extract_power_steps`, `HOST_POWER_PRECHECK_SSH_TIMEOUT`, `HOST_POWER_MUTATE_SSH_TIMEOUT`, `HOST_POWER_MODE_STOP_THEN_SHUTDOWN`
- Produces:
  - `_snap_run_command(card, *, timeout: int = HOST_POWER_MUTATE_SSH_TIMEOUT)`
  - `HealthServer.host_power_run(card_ids, *, confirm: bool, mode: str)` — `require_host_power_confirm` then `normalize_host_power_mode`; per host `steps = steps_for_host_power_mode(extract_power_steps(...), mode)`; if `mode` is shutdown-only and `steps` is empty, that host is `{ok: False, error: "No OS shutdown Power - step", results: [], aborted: False}` with **no** `run_command` call; otherwise `run_host_power_for_card`
  - `HealthServer.host_power_precheck` uses `_snap_run_command(card, timeout=HOST_POWER_PRECHECK_SSH_TIMEOUT)`
  - `do_POST` `/api/host-power/run` reads `mode` and passes it; missing/invalid → 400 via `ValueError`

- [ ] **Step 1: Write the failing tests**

Update every existing `server.host_power_run(..., confirm=True)` call in `tests/test_host_power_api.py` to also pass `mode="stop_then_shutdown"`.

Update `_post("/api/host-power/run", {"card_ids": [], "confirm": True}, ...)` in `test_host_power_api_empty_selection_not_ok` to include `"mode": "stop_then_shutdown"`.

Update `test_host_power_run_requires_confirm` body to include `"mode": "stop_then_shutdown"` so confirm is still the failure.

Add:

```python
def test_host_power_run_requires_mode(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card(1)
    response = _post(
        "/api/host-power/run",
        {"card_ids": [1], "confirm": True},
        monkeypatch,
        server,
    )
    assert response["status"] == 400
    assert "mode" in response["payload"]["error"].lower()


def test_host_power_run_rejects_invalid_mode(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card(1)
    response = _post(
        "/api/host-power/run",
        {"card_ids": [1], "confirm": True, "mode": "reboot"},
        monkeypatch,
        server,
    )
    assert response["status"] == 400
    assert "mode" in response["payload"]["error"].lower()


def test_host_power_run_shutdown_only_skips_stop_steps(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card(
        1,
        custom_commands=(
            "Power - Stop Hadoop|sudo systemctl stop hadoop\n"
            "Power - OS Shutdown|sudo shutdown -h now"
        ),
    )
    commands: list[str] = []

    def run_command(command: str) -> str:
        commands.append(command)
        return "ok"

    monkeypatch.setattr(
        HealthServer,
        "_snap_run_command",
        staticmethod(lambda _card, **_kwargs: run_command),
    )
    result = server.host_power_run(
        [1], confirm=True, mode="shutdown_only"
    )
    assert result["ok"] is True
    assert commands == ["sudo shutdown -h now"]


def test_host_power_run_shutdown_only_fails_without_shutdown_step(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card(
        1,
        custom_commands="Power - Stop Hadoop|sudo systemctl stop hadoop",
    )
    commands: list[str] = []

    def run_command(command: str) -> str:
        commands.append(command)
        return "ok"

    monkeypatch.setattr(
        HealthServer,
        "_snap_run_command",
        staticmethod(lambda _card, **_kwargs: run_command),
    )
    result = server.host_power_run(
        [1], confirm=True, mode="shutdown_only"
    )
    assert result["ok"] is False
    assert commands == []
    assert "shutdown" in result["hosts"][0]["error"].lower()


def test_host_power_run_stop_then_shutdown_still_runs_all_steps(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card(
        1,
        custom_commands=(
            "Power - Stop Hadoop|sudo systemctl stop hadoop\n"
            "Power - OS Shutdown|sudo shutdown -h now"
        ),
    )
    commands: list[str] = []

    def run_command(command: str) -> str:
        commands.append(command)
        return "ok"

    monkeypatch.setattr(
        HealthServer,
        "_snap_run_command",
        staticmethod(lambda _card, **_kwargs: run_command),
    )
    result = server.host_power_run(
        [1], confirm=True, mode="stop_then_shutdown"
    )
    assert result["ok"] is True
    assert commands == [
        "sudo systemctl stop hadoop",
        "sudo shutdown -h now",
    ]


def test_snap_run_command_timeouts():
    from launchpad.host_power_ops import (
        HOST_POWER_MUTATE_SSH_TIMEOUT,
        HOST_POWER_PRECHECK_SSH_TIMEOUT,
    )
    from launchpad.health_server import HealthServer

    assert HOST_POWER_PRECHECK_SSH_TIMEOUT == 45
    assert HOST_POWER_MUTATE_SSH_TIMEOUT == 120
    source = HealthServer._snap_run_command.__code__.co_varnames
    assert "timeout" in source
```

Also update existing monkeypatches of `_snap_run_command` that use `staticmethod(lambda _card: run_command)` to `staticmethod(lambda _card, **_kwargs: run_command)` so a new `timeout=` kwarg does not break them. That includes:

- `test_host_power_run_skips_shutdown_after_stop_failure`
- `test_host_power_run_continues_after_other_host_fails`
- `test_host_power_run_coerces_string_ids`
- `test_host_power_precheck_runs_without_confirm`
- `test_host_power_precheck_continues_after_one_host_fails`

And `test_host_power_run_skips_shutdown_after_stop_failure` / continues / coerces / empty / unmatched must pass `mode="stop_then_shutdown"`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_host_power_api.py::test_host_power_run_requires_mode tests/test_host_power_api.py::test_host_power_run_shutdown_only_skips_stop_steps tests/test_host_power_api.py::test_host_power_run_shutdown_only_fails_without_shutdown_step -q`

Expected: FAIL (TypeError: unexpected keyword `mode`, or 200 instead of 400)

- [ ] **Step 3: Write minimal implementation**

In `launchpad/health_server.py` imports from `launchpad.host_power_ops`, add:

```python
    HOST_POWER_MUTATE_SSH_TIMEOUT,
    HOST_POWER_PRECHECK_SSH_TIMEOUT,
    normalize_host_power_mode,
    steps_for_host_power_mode,
```

Change `_snap_run_command` to:

```python
    @staticmethod
    def _snap_run_command(
        card: HealthCard,
        *,
        timeout: int = HOST_POWER_MUTATE_SSH_TIMEOUT,
    ) -> Callable[[str], str]:
        return lambda command: run_remote_ssh_command(
            card.host,
            card.port,
            card.username,
            command,
            key_path=card.key_path,
            key_passphrase=card.key_passphrase,
            password=card.password,
            timeout=timeout,
            device_profile=card.device_profile,
            sudo_password=card.sudo_password if card.device_profile == "hadoop_linux" else "",
        )
```

In `do_POST` for `/api/host-power/run` (the `else` branch next to preview):

```python
                else:
                    mode = normalize_host_power_mode(payload.get("mode"))
                    result = server.host_power_run(
                        card_ids,
                        confirm=payload.get("confirm") is True,
                        mode=mode,
                    )
```

Replace `host_power_run` with:

```python
    def host_power_run(
        self,
        card_ids: list[Any],
        *,
        confirm: bool,
        mode: str,
    ) -> dict[str, Any]:
        require_host_power_confirm(confirm)
        mode_n = normalize_host_power_mode(mode)
        cards, selection_warnings = self._host_power_selection(card_ids)
        if not cards:
            return {"ok": False, "warnings": selection_warnings, "hosts": []}
        hosts: list[dict[str, Any]] = []
        for card in cards:
            payload = self._host_power_card_payload(card)
            steps = steps_for_host_power_mode(
                extract_power_steps(payload["commands"]),
                mode_n,
            )
            if mode_n == "shutdown_only" and not steps:
                hosts.append(
                    {
                        "card_id": card.card_id,
                        "name": card.name,
                        "host": card.host,
                        "ok": False,
                        "error": "No OS shutdown Power - step",
                        "results": [],
                        "aborted": False,
                    }
                )
                continue
            result = run_host_power_for_card(
                steps=steps,
                run_command=self._snap_run_command(
                    card, timeout=HOST_POWER_MUTATE_SSH_TIMEOUT
                ),
            )
            hosts.append(
                {
                    "card_id": card.card_id,
                    "name": card.name,
                    "host": card.host,
                    **result,
                }
            )
        response: dict[str, Any] = {
            "ok": all(host["ok"] for host in hosts),
            "hosts": hosts,
        }
        if selection_warnings:
            response["warnings"] = selection_warnings
        return response
```

In `host_power_precheck`, change the runner to:

```python
                run_command=self._snap_run_command(
                    card, timeout=HOST_POWER_PRECHECK_SSH_TIMEOUT
                ),
```

Do not change other `_snap_run_command(card)` callers (snap / FC / inventory); default timeout stays 120.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_host_power_api.py tests/test_host_power_ops.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_host_power_api.py
git commit -m "Require Host Power run mode and shorten precheck SSH timeout."
```

---

### Task 3: Host Power UI + version 1.6.145

**Files:**
- Modify: `launchpad/host_power.py`
- Modify: `launchpad/config.py`
- Modify: `tests/test_host_power_page.py`
- Modify: `tests/test_system_connectivity_version.py`
- Modify: `tests/test_hadoop_sudo_wire.py`

**Interfaces:**
- Consumes: `/api/host-power/preview`, `/api/host-power/run` with `mode`, `/api/host-power/precheck`
- Produces: page with Preview, **Stop services then shutdown**, **Shutdown only**, **Clear log**; no `id="run"` button; confirm label covers both; mutate buttons disabled until confirm; A–F append `Running…` immediately; Clear log resets hint; Preview/mutate still **replace** the log; in-flight lock disables Preview, mutate, and A–F but not Clear log

- [ ] **Step 1: Write the failing page/version tests**

Add to `tests/test_host_power_page.py`:

```python
def test_host_power_mutate_button_markers():
    assert "Stop services then shutdown" in HOST_POWER_HTML
    assert "Shutdown only" in HOST_POWER_HTML
    assert "Clear log" in HOST_POWER_HTML
    assert 'id="stop-then-shutdown"' in HOST_POWER_HTML
    assert 'id="shutdown-only"' in HOST_POWER_HTML
    assert 'id="clear-log"' in HOST_POWER_HTML
    assert 'id="run"' not in HOST_POWER_HTML
    assert "stop Hadoop and/or shut down" in HOST_POWER_HTML
    assert 'mode: "stop_then_shutdown"' in HOST_POWER_HTML or "stop_then_shutdown" in HOST_POWER_HTML
    assert "shutdown_only" in HOST_POWER_HTML
    assert "Running…" in HOST_POWER_HTML or "Running..." in HOST_POWER_HTML
    assert "Choose one or more hosts, then preview." in HOST_POWER_HTML
```

Keep `test_host_power_markers` asserting `/api/host-power/run` (API path in JS). Keep `test_host_power_script_js_strings_do_not_span_lines`.

Update version pins to `1.6.145` in `tests/test_system_connectivity_version.py` and `tests/test_hadoop_sudo_wire.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_host_power_page.py::test_host_power_mutate_button_markers tests/test_system_connectivity_version.py -q`

Expected: FAIL (markers missing / version still 1.6.144)

- [ ] **Step 3: Implement page + bump version**

In `launchpad/config.py` set `APP_VERSION = "1.6.145"`.

In `launchpad/host_power.py`:

1. Confirm label:

```html
        <label><input id="confirm-mutate" type="checkbox"> I confirm this will stop Hadoop and/or shut down the selected hosts</label>
```

2. Replace the Preview/Run action row:

```html
      <div class="actions">
        <button id="preview" class="secondary" type="button">Preview</button>
        <button id="stop-then-shutdown" type="button" disabled>Stop services then shutdown</button>
        <button id="shutdown-only" type="button" disabled>Shutdown only</button>
        <button id="clear-log" class="secondary" type="button">Clear log</button>
      </div>
```

3. JS: remove `runBtn` / `run()`. Add:

```javascript
    const previewBtn = document.getElementById("preview");
    const stopThenShutdownBtn = document.getElementById("stop-then-shutdown");
    const shutdownOnlyBtn = document.getElementById("shutdown-only");
    const confirmEl = document.getElementById("confirm-mutate");
    let requestInFlight = false;

    function syncMutateEnabled() {
      const ready = confirmEl.checked && !requestInFlight;
      stopThenShutdownBtn.disabled = !ready;
      shutdownOnlyBtn.disabled = !ready;
    }

    async function withButtonsLocked(action) {
      if (requestInFlight) return;
      requestInFlight = true;
      previewBtn.disabled = true;
      stopThenShutdownBtn.disabled = true;
      shutdownOnlyBtn.disabled = true;
      document.querySelectorAll(".precheck-btn").forEach((btn) => { btn.disabled = true; });
      try {
        await action();
      } finally {
        requestInFlight = false;
        previewBtn.disabled = false;
        document.querySelectorAll(".precheck-btn").forEach((btn) => { btn.disabled = false; });
        syncMutateEnabled();
      }
    }
```

4. `runPrecheck`: after the separator line, `appendLog("Running…");` then POST as today. Keep using `"\\n"` in `appendLog` (already escaped).

5. Mutate runner (replace `run()`):

```javascript
    async function runMutate(mode) {
      if (!confirmEl.checked) {
        writeLog("Confirm the checkbox before running stop or shutdown.");
        return;
      }
      await withButtonsLocked(async () => {
        try {
          writeLog("Running host power steps…");
          writeLog(await requestJson("/api/host-power/run", {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
              card_ids: selectedIds(),
              confirm: confirmEl.checked,
              mode: mode,
            }),
          }));
        } catch (error) {
          writeLog(`Run failed: ${error.message}`);
        }
      });
    }
```

6. Wire events:

```javascript
    document.getElementById("preview").addEventListener("click", preview);
    stopThenShutdownBtn.addEventListener("click", () => runMutate("stop_then_shutdown"));
    shutdownOnlyBtn.addEventListener("click", () => runMutate("shutdown_only"));
    document.getElementById("clear-log").addEventListener("click", () => {
      log.textContent = "Choose one or more hosts, then preview.";
    });
    confirmEl.addEventListener("change", syncMutateEnabled);
    syncMutateEnabled();
```

Do **not** lock Clear log inside `withButtonsLocked`. Preview still uses `writeLog` (replace). A–F still `appendLog`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_host_power_page.py tests/test_host_power_api.py tests/test_host_power_ops.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/host_power.py launchpad/config.py tests/test_host_power_page.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py
git commit -m "Add Host Power stop/shutdown buttons and clear log (1.6.145)."
```

---

## Spec coverage

| Spec requirement | Task |
|------------------|------|
| Preview lists both sequences | 1 |
| Remove page Run; add stop-then-shutdown + shutdown-only | 3 |
| One confirm checkbox covering both | 3 |
| Clear log client-only | 3 |
| `/run` requires `mode` | 2 |
| Missing/invalid mode → 400 | 2 |
| Confirm still required | 2 (existing + updated) |
| `stop_then_shutdown` runs all `Power -` steps | 2 |
| `shutdown_only` runs only shutdown step | 1 + 2 |
| No shutdown step → preview warning; run fails host, no SSH | 1 + 2 |
| Stop failure skips remaining steps on that host | 2 (existing test, still `stop_then_shutdown`) |
| F / prechecks write `Running…` immediately | 3 |
| Precheck SSH timeout 45s; mutate 120s | 1 constants + 2 wiring |
| A–F still append; Preview/mutate replace | 3 |
| No new preset labels / no new endpoints | all |
| Version 1.6.145 | 3 |
| JS `"\\n"` not `"\n"` | 3 (existing span-line test) |
