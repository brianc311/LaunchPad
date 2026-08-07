# Hadoop Host Power Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `hadoop_linux` SSH profile with editable Linux + sample Hadoop health/capacity presets and a native LaunchPad Host Power page (plus per-card shortcut) that Preview → Confirm → Runs ordered `Power -` stop-then-shutdown commands over Paramiko.

**Architecture:** Presets live in `storage_presets.py` like other device profiles. Pure ops helpers in `host_power_ops.py` extract `Power -` steps, gate confirm, and run per host with abort-remaining-on-step-failure. HealthServer serves `/host-power` and preview/run APIs using the existing card SSH runner. Dashboard opens the page and shows **Power off…** on Hadoop cards only. No Ansible / `plp5-dz5-nw`.

**Tech Stack:** Python, Paramiko (existing card runners), HealthServer HTML/JS pages, CustomTkinter dashboard cards, pytest.

**Spec:** `docs/superpowers/specs/2026-08-07-hadoop-host-power-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.131`; bump to `1.6.132` when shipping Host Power UI/version task.
- Native LaunchPad SSH only — do not call Ansible Pad or `plp5-dz5-nw` for this feature.
- Power-off command labels must use the exact prefix `Power -` (including the space after the hyphen).
- Mutating `/api/host-power/run` requires `confirm: true` or reject with a clear error.
- If any `Power -` step fails for a host, skip remaining `Power -` steps for that host (so a failed stop never reaches shutdown).
- Continue other selected hosts after one host fails.
- Health / sample Hadoop commands may use best-effort `|| true`; **Power -** stop/shutdown defaults must not swallow failures with `|| true`.
- Operator category for Hadoop cards is existing Admin UX — no new category code.
- Windows PowerShell commits (plain `-m` or here-string), no bash heredoc.
- Commit at each task’s commit step.
- Prefer TDD: failing test → implement → pass → commit.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/storage_presets.py` | `HADOOP_LINUX_COMMANDS`, `hadoop_linux` in `DEVICE_PROFILES` / `PROFILE_COMMANDS` / `PRESET_HEADERS` |
| `launchpad/host_power_ops.py` | `POWER_LABEL_PREFIX`, extract steps, preview dict, run orchestration |
| `launchpad/host_power.py` | `HOST_POWER_PATH`, `HOST_POWER_HTML` |
| `launchpad/health_server.py` | Page route + cards/preview/run APIs + `open_host_power` |
| `launchpad/monitor.py` | `open_host_power_for_cards(...)` |
| `launchpad/ui/dashboard_view.py` | **Host Power** tool button + open helper; wire per-card Power off |
| `launchpad/ui/card_widget.py` | Optional **Power off…** button when callback provided |
| `launchpad/config.py` | `APP_VERSION` → `1.6.132` |
| `tests/test_hadoop_presets.py` | Profile + preset content |
| `tests/test_host_power_ops.py` | Extract / confirm / abort-on-failure |
| `tests/test_host_power_api.py` | Handler-level API tests with mocks |
| `tests/test_host_power_page.py` | HTML markers + dashboard wiring smoke |

---

### Task 1: `hadoop_linux` profile presets

**Files:**
- Modify: `launchpad/storage_presets.py`
- Create: `tests/test_hadoop_presets.py`

**Interfaces:**
- Produces:
  - `HADOOP_LINUX_COMMANDS: list[tuple[str, str]]`
  - `DEVICE_PROFILES["hadoop_linux"] == "Hadoop / Linux SSH"`
  - `PROFILE_COMMANDS["hadoop_linux"]` → copy of `HADOOP_LINUX_COMMANDS`
  - `preset_commands_for_profile("hadoop_linux")` returns that list
  - Labels include `Health -`, `CPU -`, `Memory -`, `Capacity -`, sample Hadoop health, and ordered `Power -` entries ending with OS shutdown

- [ ] **Step 1: Write the failing test**

Create `tests/test_hadoop_presets.py`:

```python
from launchpad.storage_presets import (
    DEVICE_PROFILES,
    POWER_LABEL_PREFIX,  # may not exist yet — assert via string if Task 1 only uses literal
    preset_commands_for_profile,
)

POWER_PREFIX = "Power -"


def test_hadoop_linux_profile_label():
    assert DEVICE_PROFILES.get("hadoop_linux") == "Hadoop / Linux SSH"


def test_hadoop_linux_presets_include_os_hadoop_and_power():
    cmds = preset_commands_for_profile("hadoop_linux")
    assert cmds, "expected non-empty preset list"
    labels = [label for label, _ in cmds]
    joined = "\n".join(labels).lower()

    assert any(label.startswith("Health -") for label in labels)
    assert any(label.startswith("CPU -") for label in labels)
    assert any(label.startswith("Memory -") for label in labels)
    assert any(label.startswith("Capacity -") for label in labels)
    assert "hdfs" in joined or "yarn" in joined or "hadoop" in joined

    power = [(label, cmd) for label, cmd in cmds if label.startswith(POWER_PREFIX)]
    assert len(power) >= 2
    assert any("shutdown" in cmd.lower() or "poweroff" in cmd.lower() for _, cmd in power)
    assert power[-1][0].startswith(POWER_PREFIX)
    # Power defaults must not swallow failures
    for label, cmd in power:
        assert "|| true" not in cmd, f"{label} must not use || true"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hadoop_presets.py -v`

Expected: FAIL (`hadoop_linux` missing from `DEVICE_PROFILES` / empty presets)

- [ ] **Step 3: Write minimal implementation**

In `launchpad/storage_presets.py`:

1. After `VULTR_VPS_COMMANDS`, add:

```python
HADOOP_LINUX_COMMANDS: list[tuple[str, str]] = [
    ("Health - Uptime", "uptime"),
    ("Health - Failed Units", "systemctl --failed --no-pager 2>/dev/null || true"),
    ("CPU - Load Average", "cat /proc/loadavg"),
    (
        "CPU - Usage %",
        "vmstat 1 2 | tail -1 | awk '{printf \"%.1f%% busy (idle %.1f%%)\\n\", 100-$15, $15}'",
    ),
    (
        "Memory - Usage %",
        "free -m | awk '/Mem:/ {printf \"%.1f%% used (%d MB / %d MB)\\n\", $3/$2*100, $3, $2}'",
    ),
    ("Memory - Detailed", "free -h"),
    (
        "Capacity - Root Disk %",
        "df -h / | awk 'NR==2 {print $5\" used (\"$3\" / \"$2\")\"}'",
    ),
    (
        "Capacity - All Filesystems",
        "df -h --output=target,pcent,size,used,avail 2>/dev/null || df -h",
    ),
    (
        "Health - HDFS dfsadmin",
        "hdfs dfsadmin -report 2>/dev/null | head -n 40 || true",
    ),
    ("Health - YARN nodes", "yarn node -list 2>/dev/null || true"),
    (
        "Health - Hadoop systemd units",
        "systemctl list-units 'hadoop*' 'hdfs*' 'yarn*' --no-pager 2>/dev/null || true",
    ),
    (
        "Power - Stop YARN NodeManager",
        "sudo systemctl stop hadoop-yarn-nodemanager",
    ),
    (
        "Power - Stop HDFS DataNode",
        "sudo systemctl stop hadoop-hdfs-datanode",
    ),
    ("Power - OS Shutdown", "sudo shutdown -h now"),
]
```

2. Add to `DEVICE_PROFILES` (near Vultr / Linux entries):

```python
"hadoop_linux": "Hadoop / Linux SSH",
```

3. Add `PRESET_HEADERS` entry:

```python
"hadoop_linux": (
    "# Hadoop Linux SSH - OS health/capacity, sample HDFS/YARN status, "
    "and Power - stop-then-shutdown (edit to match your units).\n"
),
```

4. Wire `PROFILE_COMMANDS`:

```python
"hadoop_linux": list(HADOOP_LINUX_COMMANDS),
```

Do **not** export `POWER_LABEL_PREFIX` from this module unless convenient; Task 2 owns the constant in `host_power_ops.py`. Adjust the test to use the literal `"Power -"` only (remove the unused import shown above).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_hadoop_presets.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/storage_presets.py tests/test_hadoop_presets.py
git commit -m "Add hadoop_linux profile with health, capacity, and power presets."
```

---

### Task 2: Host Power ops helpers

**Files:**
- Create: `launchpad/host_power_ops.py`
- Create: `tests/test_host_power_ops.py`

**Interfaces:**
- Consumes: card dicts with `id`, `name`, `host`, and `commands: list[tuple[str, str]]` (or parallel `labels`/`commands` — pick one and stick to it)
- Produces:
  - `POWER_LABEL_PREFIX = "Power -"`
  - `extract_power_steps(commands: list[tuple[str, str]]) -> list[dict]`  
    Each dict: `{"label": str, "command": str}` preserving order of `Power -` labels only
  - `build_host_power_preview(cards: list[dict]) -> dict`  
    Returns `{"ok": bool, "warnings": list[str], "hosts": list[dict]}` where each host has `card_id`, `name`, `host`, `steps`, and optional per-host warnings. `ok` is False when any selected host has zero power steps or missing host address.
  - `require_host_power_confirm(confirm: bool) -> None` — raises `ValueError` if not confirm
  - `run_host_power_for_card(*, steps: list[dict], run_command: Callable[[str], str]) -> dict`  
    Runs steps in order; on exception/failure for a step, stop remaining steps; return `{"ok": bool, "results": [{"label", "command", "ok", "output"|"error"}], "aborted": bool}`

Define step failure as: `run_command` raises, **or** returns a string starting with `ERROR:` (match existing LaunchPad SSH helper conventions if present; otherwise treat only exceptions as failure and document that in the module docstring). Prefer: catch exceptions → mark step failed → abort remaining.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_host_power_ops.py`:

```python
import pytest

from launchpad.host_power_ops import (
    POWER_LABEL_PREFIX,
    build_host_power_preview,
    extract_power_steps,
    require_host_power_confirm,
    run_host_power_for_card,
)


def test_extract_power_steps_filters_and_orders():
    cmds = [
        ("Health - Uptime", "uptime"),
        ("Power - Stop YARN", "sudo systemctl stop yarn"),
        ("Capacity - Root", "df -h /"),
        ("Power - OS Shutdown", "sudo shutdown -h now"),
    ]
    steps = extract_power_steps(cmds)
    assert [s["label"] for s in steps] == [
        "Power - Stop YARN",
        "Power - OS Shutdown",
    ]
    assert all(s["label"].startswith(POWER_LABEL_PREFIX) for s in steps)


def test_preview_blocks_when_no_power_steps():
    preview = build_host_power_preview(
        [
            {
                "id": 1,
                "name": "hn1",
                "host": "10.0.0.1",
                "commands": [("Health - Uptime", "uptime")],
            }
        ]
    )
    assert preview["ok"] is False
    assert preview["warnings"]


def test_require_confirm():
    with pytest.raises(ValueError, match="confirm"):
        require_host_power_confirm(False)
    require_host_power_confirm(True)


def test_run_aborts_remaining_after_stop_failure():
    calls: list[str] = []

    def run_command(cmd: str) -> str:
        calls.append(cmd)
        if "stop" in cmd:
            raise RuntimeError("unit not found")
        return "ok"

    result = run_host_power_for_card(
        steps=[
            {"label": "Power - Stop YARN", "command": "sudo systemctl stop yarn"},
            {"label": "Power - OS Shutdown", "command": "sudo shutdown -h now"},
        ],
        run_command=run_command,
    )
    assert result["ok"] is False
    assert result["aborted"] is True
    assert calls == ["sudo systemctl stop yarn"]
    assert "shutdown" not in "".join(calls)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_host_power_ops.py -v`

Expected: FAIL (module missing)

- [ ] **Step 3: Write minimal implementation**

Create `launchpad/host_power_ops.py` implementing the interfaces above. Keep it dependency-free (no HealthServer imports).

Suggested shapes:

```python
POWER_LABEL_PREFIX = "Power -"


def extract_power_steps(commands: list[tuple[str, str]]) -> list[dict]:
    steps = []
    for label, command in commands:
        label_s = str(label or "")
        command_s = str(command or "").strip()
        if label_s.startswith(POWER_LABEL_PREFIX) and command_s:
            steps.append({"label": label_s, "command": command_s})
    return steps
```

`build_host_power_preview` loops cards, extracts steps, appends warnings like `"{name}: no Power - commands configured"` or `"{name}: missing host"`, sets top-level `ok` False if any blocking warning exists.

`run_host_power_for_card` loops steps; on success append `{..., "ok": True, "output": text}`; on exception append `{..., "ok": False, "error": str(exc)}`, set `aborted=True`, break.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_host_power_ops.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/host_power_ops.py tests/test_host_power_ops.py
git commit -m "Add Host Power preview and run helpers with abort-on-failure."
```

---

### Task 3: HealthServer APIs + Host Power page

**Files:**
- Create: `launchpad/host_power.py`
- Modify: `launchpad/health_server.py` (imports, GET page, GET cards, POST preview/run, `open_host_power` method)
- Create: `tests/test_host_power_api.py`
- Create: `tests/test_host_power_page.py` (markers only in this task; dashboard assert in Task 4)

**Interfaces:**
- Consumes: `extract_power_steps`, `build_host_power_preview`, `require_host_power_confirm`, `run_host_power_for_card`; existing `_snap_run_command` / `_lun_run_command` style card SSH runner (reuse the same Paramiko runner used for Contingency snaps)
- Produces:
  - `HOST_POWER_PATH = "/host-power"`
  - `HOST_POWER_HTML` with markers: `Host Power`, `/api/host-power/cards`, `/api/host-power/preview`, `/api/host-power/run`, `confirm`, `card_id` query support, `{{APP_VERSION}}`
  - `HealthServer.host_power_cards() -> list[dict]` — only `device_profile == "hadoop_linux"` with non-empty host
  - `HealthServer.host_power_preview(card_ids: list[int]) -> dict`
  - `HealthServer.host_power_run(card_ids: list[int], *, confirm: bool) -> dict`
  - `HealthServer.open_host_power(card_id: int | None = None) -> str` — opens browser to `/host-power` or `/host-power?card_id=N`

Card command source for preview/run: parse the card’s stored custom command text the same way other features do (reuse existing parse helper for `custom_commands` → `list[tuple[str,str]]` if one exists; otherwise call `preset_commands_for_profile(card.device_profile)` when custom list empty). Prefer: if card has custom commands, use those; else presets for profile.

- [ ] **Step 1: Write failing page + API tests**

`tests/test_host_power_page.py`:

```python
from launchpad.host_power import HOST_POWER_HTML, HOST_POWER_PATH


def test_host_power_markers():
    assert HOST_POWER_PATH == "/host-power"
    assert "Host Power" in HOST_POWER_HTML
    assert "/api/host-power/cards" in HOST_POWER_HTML
    assert "/api/host-power/preview" in HOST_POWER_HTML
    assert "/api/host-power/run" in HOST_POWER_HTML
    assert "confirm" in HOST_POWER_HTML
    assert "card_id" in HOST_POWER_HTML
    assert "{{APP_VERSION}}" in HOST_POWER_HTML
```

`tests/test_host_power_api.py` — follow `tests/test_ansible_pad_api.py` / FC consistgrp handler patterns: construct handler or call `HealthServer` methods with a fake card registered. Minimal method-level tests are acceptable if HTTP harness is heavy:

```python
def test_host_power_cards_filters_profile(monkeypatch):
    # Register one hadoop_linux and one flashsystem card; assert only hadoop returned
    ...


def test_host_power_run_requires_confirm():
    # Expect ValueError or result warnings / HTTP 400 path
    ...


def test_host_power_run_skips_shutdown_after_stop_failure(monkeypatch):
    # Inject run_command that fails on stop; assert shutdown not called
    ...
```

Implement these against `HealthServer` methods with monkeypatched `_snap_run_command` (or the shared runner used).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_host_power_page.py tests/test_host_power_api.py -v`

Expected: FAIL (missing module / methods)

- [ ] **Step 3: Implement page HTML**

Create `launchpad/host_power.py` modeled on `launchpad/ansible_pad.py` styling:

- Hero: **Host Power** — stop Hadoop then OS shutdown via native SSH (not Ansible).
- Host list from `GET /api/host-power/cards` (checkboxes; pre-check `card_id` from `URLSearchParams`).
- Confirm checkbox required for Run.
- Buttons: Preview, Run.
- `<pre id="log">` for preview steps and run output.
- Footer: `LaunchPad {{APP_VERSION}}`.

JS sketch:

```javascript
async function loadCards() {
  const res = await fetch("/api/host-power/cards");
  const data = await res.json();
  // render checkboxes; preselect URL card_id
}
async function preview() {
  const card_ids = selectedIds();
  const res = await fetch("/api/host-power/preview", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({card_ids}),
  });
  // write log
}
async function run() {
  const confirm = document.getElementById("confirm-mutate").checked;
  const res = await fetch("/api/host-power/run", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({card_ids: selectedIds(), confirm}),
  });
  // write log
}
```

- [ ] **Step 4: Wire HealthServer**

In `health_server.py`:

1. Import `HOST_POWER_HTML`, `HOST_POWER_PATH`, and ops helpers.
2. GET `HOST_POWER_PATH` → send HTML with `APP_VERSION` substitution (same as Ansible Pad).
3. GET `/api/host-power/cards` → `host_power_cards()`.
4. POST `/api/host-power/preview` and `/api/host-power/run` — parse JSON `card_ids`, call methods; map `ValueError` for missing confirm to HTTP 400 JSON.
5. Implement methods:
   - Filter `hadoop_linux`
   - Resolve commands from card
   - Preview via `build_host_power_preview`
   - Run: `require_host_power_confirm`, then for each card `run_host_power_for_card` with `_snap_run_command(card)` (or equivalent)
6. `open_host_power(self, card_id=None)` → `webbrowser.open` server URL + path (+ query).

Look at `open_ansible_pad` for the open-browser pattern and mirror it.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_host_power_page.py tests/test_host_power_api.py tests/test_host_power_ops.py tests/test_hadoop_presets.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```powershell
git add launchpad/host_power.py launchpad/health_server.py tests/test_host_power_page.py tests/test_host_power_api.py
git commit -m "Expose Host Power page and preview/run APIs on HealthServer."
```

---

### Task 4: Dashboard entry, per-card Power off, version bump

**Files:**
- Modify: `launchpad/monitor.py` — add `open_host_power_for_cards(entries, card_id: int | None = None) -> str`
- Modify: `launchpad/ui/dashboard_view.py` — tool button **Host Power**; `_open_host_power`; optional card_id
- Modify: `launchpad/ui/card_widget.py` — optional `on_power_off` callback → **Power off…** button (expanded and/or compact row)
- Modify: `launchpad/config.py` — `APP_VERSION = "1.6.132"`
- Modify: `tests/test_host_power_page.py` — assert dashboard lists Host Power; assert card_widget has Power off hook markers if practical
- Modify: any existing `APP_VERSION` assertion tests that pin `1.6.131` → `1.6.132`

**Interfaces:**
- Consumes: `HealthServer.open_host_power`
- Produces: dashboard opens `/host-power`; Hadoop cards call open with their `card_id`

- [ ] **Step 1: Write / extend failing wiring tests**

Add to `tests/test_host_power_page.py`:

```python
from pathlib import Path


def test_dashboard_lists_host_power_tool():
    path = Path(__file__).parents[1] / "launchpad" / "ui" / "dashboard_view.py"
    text = path.read_text(encoding="utf-8")
    assert '"Host Power"' in text
    assert "_open_host_power" in text


def test_card_widget_supports_power_off_callback():
    path = Path(__file__).parents[1] / "launchpad" / "ui" / "card_widget.py"
    text = path.read_text(encoding="utf-8")
    assert "on_power_off" in text
    assert "Power off" in text
```

Update version tests if present:

```powershell
rg -n "1\.6\.131" tests launchpad/config.py
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_host_power_page.py -v`

Expected: FAIL on dashboard / card_widget asserts

- [ ] **Step 3: Implement monitor + dashboard open**

In `monitor.py` (mirror Ansible Pad):

```python
def open_host_power_for_cards(
    entries: list[HealthDashboardEntry],
    card_id: int | None = None,
) -> str:
    server = get_health_server()
    server.ensure_running()
    for entry in entries:
        _register_entry(server, entry)
    return server.open_host_power(card_id=card_id)
```

In `dashboard_view.py`:

- Add `("Host Power", self._open_host_power, None)` near Ansible Pad.
- Implement `_open_host_power(self, card_id: int | None = None)` like `_open_ansible_pad`, calling `open_host_power_for_cards(entries, card_id=card_id)`.

When building card widgets, if `card.device_profile == "hadoop_linux"`, pass:

```python
on_power_off=lambda cid=card.id: self._open_host_power(card_id=cid)
```

- [ ] **Step 4: Implement card_widget Power off button**

Add optional `on_power_off=None` to `CardWidget.__init__`. When set, add a secondary button **Power off…** in `btn_row` (and compact row if space allows). Keep Connect/Health behavior unchanged.

- [ ] **Step 5: Bump version**

Set `launchpad/config.py` `APP_VERSION = "1.6.132"` and fix any pinned version tests.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
python -m pytest tests/test_hadoop_presets.py tests/test_host_power_ops.py tests/test_host_power_api.py tests/test_host_power_page.py -q
```

Expected: all PASS

Also run any version assertion test that exists for `APP_VERSION`.

- [ ] **Step 7: Commit**

```powershell
git add launchpad/monitor.py launchpad/ui/dashboard_view.py launchpad/ui/card_widget.py launchpad/config.py tests/test_host_power_page.py
# include any version test files touched
git commit -m "Add Host Power dashboard entry and Hadoop card shortcut (1.6.132)."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| `hadoop_linux` profile + editable presets (OS health/capacity) | 1 |
| Sample Hadoop CLI defaults | 1 |
| Ordered `Power -` stop then shutdown defaults | 1 |
| Extract only `Power -` for Preview/Run | 2 |
| Confirm required | 2, 3 |
| Abort remaining steps on failure (no shutdown after failed stop) | 2, 3 |
| Continue other hosts after one fails | 3 |
| `/host-power` page multi-select Preview → Run | 3 |
| Deep-link `card_id` | 3, 4 |
| Dashboard Host Power button | 4 |
| Per-card Power off shortcut | 4 |
| Native SSH only / no Ansible | all (no Ansible wiring) |
| Category via existing Admin | no code (documented) |
| Capacity Report Excel parity | out of scope (no task) |
| Version bump | 4 → 1.6.132 |

## Placeholder / consistency self-review

- Prefix locked to `Power -` everywhere (presets, extract, tests).
- APIs named `/api/host-power/*` consistently.
- Version target `1.6.132` (post-1.6.131 tip).
- No TBD/TODO left in task steps.
- Runner reuse: Contingency-style `_snap_run_command` (or shared equivalent) — implementer must use the same callable already used for SSH command execution on HealthCards.
