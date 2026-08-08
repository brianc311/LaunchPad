# Host Power A–F Prechecks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add clickable A–F read-only prechecks on Host Power so operators can run uptime/units/HDFS/YARN checks on selected Hadoop hosts and append output to the Run log without confirming shutdown.

**Architecture:** A fixed A–F catalog lives in `host_power_ops.py`. Card `Precheck - X …` lines override catalog commands; missing letters fall back to defaults. HealthServer exposes `GET /api/host-power/prechecks` (catalog) and `POST /api/host-power/precheck` (SSH, no confirm). The Host Power page renders A–F buttons and appends results. Promote merges missing `Precheck -` lines onto existing `hadoop_linux` cards. Preview/Run stay `Power -` only.

**Tech Stack:** Python, existing Paramiko card SSH runner, HealthServer HTML/JS, pytest.

**Spec:** `docs/superpowers/specs/2026-08-07-host-power-af-prechecks-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.142`; bump to `1.6.143` in the UI/version task.
- Native LaunchPad SSH only — do not call Ansible Pad.
- Precheck labels must use prefix `Precheck - ` then the letter (`Precheck - A …` through `Precheck - F …`).
- `POST /api/host-power/precheck` does **not** require `confirm`.
- Preview / Run remain `Power -` stop-then-shutdown and still require `confirm: true` on Run.
- A–F must not execute `shutdown`, `reboot`, `halt`, or `poweroff` (case-insensitive word match); reject that host without SSH.
- Precheck failure fails that host only; continue other selected hosts.
- Run log: **append** precheck output; Preview/Run may still replace the log.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task’s commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch or install zips.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/storage_presets.py` | Add `Precheck - A`…`F` to `HADOOP_LINUX_COMMANDS` before `Power -` |
| `launchpad/host_power_ops.py` | Catalog, letter normalize, resolve command, mutate-guard, run one precheck |
| `launchpad/hadoop_linux_promote.py` | Append missing A–F `Precheck -` lines on Hadoop cards |
| `launchpad/health_server.py` | `GET /api/host-power/prechecks`, `POST /api/host-power/precheck` |
| `launchpad/host_power.py` | A–F buttons, append Run log |
| `launchpad/config.py` | `APP_VERSION` → `1.6.143` |
| `tests/test_hadoop_presets.py` | Preset includes A–F before Power |
| `tests/test_host_power_ops.py` | Catalog, resolve, mutate-guard, run |
| `tests/test_hadoop_linux_promote.py` | Missing prechecks appended; custom letter kept |
| `tests/test_host_power_api.py` | GET catalog + POST precheck |
| `tests/test_host_power_page.py` | Page markers |
| `tests/test_system_connectivity_version.py` | Version pin `1.6.143` |
| `tests/test_hadoop_sudo_wire.py` | Version pin `1.6.143` |

---

### Task 1: A–F catalog + `hadoop_linux` preset lines

**Files:**
- Modify: `launchpad/storage_presets.py`
- Modify: `launchpad/host_power_ops.py`
- Modify: `tests/test_hadoop_presets.py`
- Modify: `tests/test_host_power_ops.py`

**Interfaces:**
- Produces:
  - `PRECHECK_LABEL_PREFIX = "Precheck -"`
  - `PRECHECK_LETTERS = ("A", "B", "C", "D", "E", "F")`
  - `@dataclass(frozen=True) class HostPowerPrecheck` with `letter: str`, `hint: str`, `label: str`, `command: str`
  - `host_power_precheck_catalog() -> list[HostPowerPrecheck]`
  - `host_power_precheck_catalog_payload() -> list[dict[str, str]]` — `{letter, label, hint}` only
  - `HADOOP_LINUX_COMMANDS` includes all six `Precheck -` labels **before** any `Power -` line
  - Catalog commands match the spec table exactly

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_hadoop_presets.py`:

```python
def test_hadoop_linux_presets_include_precheck_a_through_f_before_power():
    cmds = preset_commands_for_profile("hadoop_linux")
    labels = [label for label, _ in cmds]
    letters = []
    for label in labels:
        if label.startswith("Precheck - ") and len(label) >= 12:
            letter = label[11]
            if letter in "ABCDEF" and letter not in letters:
                letters.append(letter)
    assert letters == ["A", "B", "C", "D", "E", "F"]
    first_power = next(i for i, label in enumerate(labels) if label.startswith("Power -"))
    last_precheck = max(i for i, label in enumerate(labels) if label.startswith("Precheck - "))
    assert last_precheck < first_power
```

Add to `tests/test_host_power_ops.py`:

```python
from launchpad.host_power_ops import (
    PRECHECK_LETTERS,
    host_power_precheck_catalog,
    host_power_precheck_catalog_payload,
)


def test_precheck_catalog_is_a_through_f():
    catalog = host_power_precheck_catalog()
    assert [item.letter for item in catalog] == list(PRECHECK_LETTERS)
    by_letter = {item.letter: item for item in catalog}
    assert by_letter["A"].hint == "Uptime / load"
    assert by_letter["A"].command == "uptime; cat /proc/loadavg"
    assert by_letter["B"].command == "systemctl --failed --no-pager 2>/dev/null || true"
    assert by_letter["C"].command == (
        "systemctl list-units 'hadoop*' 'hdfs*' 'yarn*' --no-pager 2>/dev/null || true"
    )
    assert by_letter["D"].command == "hdfs dfsadmin -report 2>/dev/null | head -n 40 || true"
    assert by_letter["E"].command == "yarn node -list 2>/dev/null || true"
    assert by_letter["F"].command == "yarn application -list 2>/dev/null || true"
    assert by_letter["A"].label.startswith("Precheck - A")
    payload = host_power_precheck_catalog_payload()
    assert payload[0] == {
        "letter": "A",
        "label": by_letter["A"].label,
        "hint": "Uptime / load",
    }
    assert "command" not in payload[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_hadoop_presets.py::test_hadoop_linux_presets_include_precheck_a_through_f_before_power tests/test_host_power_ops.py::test_precheck_catalog_is_a_through_f -q`

Expected: FAIL (import or assertion — catalog / Precheck labels missing)

- [ ] **Step 3: Implement catalog + presets**

In `launchpad/host_power_ops.py` add:

```python
from dataclasses import dataclass

PRECHECK_LABEL_PREFIX = "Precheck -"
PRECHECK_LETTERS = ("A", "B", "C", "D", "E", "F")


@dataclass(frozen=True)
class HostPowerPrecheck:
    letter: str
    hint: str
    label: str
    command: str


def host_power_precheck_catalog() -> list[HostPowerPrecheck]:
    rows = (
        ("A", "Uptime / load", "uptime; cat /proc/loadavg"),
        ("B", "Failed systemd units", "systemctl --failed --no-pager 2>/dev/null || true"),
        (
            "C",
            "Hadoop / HDFS / YARN units",
            "systemctl list-units 'hadoop*' 'hdfs*' 'yarn*' --no-pager 2>/dev/null || true",
        ),
        (
            "D",
            "HDFS dfsadmin report",
            "hdfs dfsadmin -report 2>/dev/null | head -n 40 || true",
        ),
        ("E", "YARN node list", "yarn node -list 2>/dev/null || true"),
        ("F", "YARN running apps", "yarn application -list 2>/dev/null || true"),
    )
    return [
        HostPowerPrecheck(
            letter=letter,
            hint=hint,
            label=f"Precheck - {letter} {hint}",
            command=command,
        )
        for letter, hint, command in rows
    ]


def host_power_precheck_catalog_payload() -> list[dict[str, str]]:
    return [
        {"letter": item.letter, "label": item.label, "hint": item.hint}
        for item in host_power_precheck_catalog()
    ]
```

In `launchpad/storage_presets.py`, insert these tuples into `HADOOP_LINUX_COMMANDS` **immediately before** the existing `Power - Stop YARN NodeManager` entry:

```python
    ("Precheck - A Uptime / load", "uptime; cat /proc/loadavg"),
    (
        "Precheck - B Failed systemd units",
        "systemctl --failed --no-pager 2>/dev/null || true",
    ),
    (
        "Precheck - C Hadoop / HDFS / YARN units",
        "systemctl list-units 'hadoop*' 'hdfs*' 'yarn*' --no-pager 2>/dev/null || true",
    ),
    (
        "Precheck - D HDFS dfsadmin report",
        "hdfs dfsadmin -report 2>/dev/null | head -n 40 || true",
    ),
    ("Precheck - E YARN node list", "yarn node -list 2>/dev/null || true"),
    (
        "Precheck - F YARN running apps",
        "yarn application -list 2>/dev/null || true",
    ),
```

Update `PRESET_HEADERS["hadoop_linux"]` to mention Precheck A–F plus Power stop-then-shutdown.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_hadoop_presets.py tests/test_host_power_ops.py -q`

Expected: PASS (including existing Power extract/confirm/abort tests)

- [ ] **Step 5: Commit**

```powershell
git add launchpad/storage_presets.py launchpad/host_power_ops.py tests/test_hadoop_presets.py tests/test_host_power_ops.py
git commit -m "Add Host Power A-F precheck catalog and Hadoop presets."
```

---

### Task 2: Resolve letter, mutate-guard, run one precheck

**Files:**
- Modify: `launchpad/host_power_ops.py`
- Modify: `tests/test_host_power_ops.py`

**Interfaces:**
- Consumes: `host_power_precheck_catalog()`, `PRECHECK_LETTERS`
- Produces:
  - `normalize_precheck_letter(letter: str) -> str` — uppercases; raises `ValueError` if not A–F
  - `resolve_precheck_command(commands: list[tuple[str, str]], letter: str) -> str` — card override else catalog
  - `precheck_command_is_mutating(command: str) -> bool` — word match `\b(shutdown|reboot|halt|poweroff)\b` ignore case
  - `run_host_power_precheck_for_card(*, letter: str, commands: list[tuple[str, str]], run_command: Callable[[str], str]) -> dict[str, Any]` with keys `ok`, `letter`, `label`, `command`, and either `output` or `error`

Label match rule: a card label counts as letter `X` when it equals `Precheck - X` or starts with `Precheck - X ` (letter then space). `Precheck - AA` must **not** match A.

If mutating, return `ok: False` with error `"Precheck commands cannot include shutdown/reboot/halt/poweroff"` and **do not** call `run_command`.

If `run_command` raises or returns a string starting with `ERROR:`, `ok` is False.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_host_power_ops.py`:

```python
from launchpad.host_power_ops import (
    normalize_precheck_letter,
    precheck_command_is_mutating,
    resolve_precheck_command,
    run_host_power_precheck_for_card,
)


def test_normalize_precheck_letter_accepts_a_through_f():
    assert normalize_precheck_letter("e") == "E"
    assert normalize_precheck_letter("A") == "A"
    with pytest.raises(ValueError):
        normalize_precheck_letter("G")
    with pytest.raises(ValueError):
        normalize_precheck_letter("")


def test_resolve_precheck_command_prefers_card_override():
    cmds = [
        ("Health - Uptime", "uptime"),
        ("Precheck - E YARN node list", "yarn node -list -showDetails"),
    ]
    assert resolve_precheck_command(cmds, "E") == "yarn node -list -showDetails"
    assert resolve_precheck_command(cmds, "A") == "uptime; cat /proc/loadavg"


def test_resolve_precheck_command_does_not_match_aa_as_a():
    cmds = [("Precheck - AA custom", "echo aa")]
    assert resolve_precheck_command(cmds, "A") == "uptime; cat /proc/loadavg"


def test_precheck_command_is_mutating_word_match():
    assert precheck_command_is_mutating("sudo shutdown -h now") is True
    assert precheck_command_is_mutating("yarn node -list") is False
    assert precheck_command_is_mutating("echo noshutdownhere") is False


def test_run_precheck_rejects_mutating_without_calling_runner():
    calls: list[str] = []

    def run_command(cmd: str) -> str:
        calls.append(cmd)
        return "ok"

    result = run_host_power_precheck_for_card(
        letter="A",
        commands=[("Precheck - A Uptime / load", "sudo shutdown -h now")],
        run_command=run_command,
    )
    assert result["ok"] is False
    assert "shutdown" in result["error"].lower()
    assert calls == []


def test_run_precheck_records_output_and_error_prefix():
    result_ok = run_host_power_precheck_for_card(
        letter="E",
        commands=[],
        run_command=lambda cmd: "node1 RUNNING",
    )
    assert result_ok["ok"] is True
    assert result_ok["letter"] == "E"
    assert result_ok["output"] == "node1 RUNNING"

    result_err = run_host_power_precheck_for_card(
        letter="E",
        commands=[],
        run_command=lambda cmd: "ERROR: yarn not in PATH",
    )
    assert result_err["ok"] is False
    assert result_err["error"] == "ERROR: yarn not in PATH"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_host_power_ops.py::test_normalize_precheck_letter_accepts_a_through_f tests/test_host_power_ops.py::test_resolve_precheck_command_prefers_card_override tests/test_host_power_ops.py::test_run_precheck_rejects_mutating_without_calling_runner -q`

Expected: FAIL (functions not defined)

- [ ] **Step 3: Implement resolve / guard / run**

In `launchpad/host_power_ops.py`:

```python
import re

_PRECHECK_MUTATE_RE = re.compile(r"\b(shutdown|reboot|halt|poweroff)\b", re.IGNORECASE)


def normalize_precheck_letter(letter: str) -> str:
    value = str(letter or "").strip().upper()
    if value not in PRECHECK_LETTERS:
        raise ValueError("Precheck letter must be A–F")
    return value


def _label_matches_precheck_letter(label: str, letter: str) -> bool:
    prefix = f"{PRECHECK_LABEL_PREFIX} {letter}"
    text = str(label or "")
    return text == prefix or text.startswith(prefix + " ")


def resolve_precheck_command(commands: list[tuple[str, str]], letter: str) -> str:
    letter_n = normalize_precheck_letter(letter)
    for label, command in commands:
        command_s = str(command or "").strip()
        if command_s and _label_matches_precheck_letter(label, letter_n):
            return command_s
    catalog = {item.letter: item for item in host_power_precheck_catalog()}
    return catalog[letter_n].command


def precheck_command_is_mutating(command: str) -> bool:
    return bool(_PRECHECK_MUTATE_RE.search(str(command or "")))


def run_host_power_precheck_for_card(
    *,
    letter: str,
    commands: list[tuple[str, str]],
    run_command: Callable[[str], str],
) -> dict[str, Any]:
    letter_n = normalize_precheck_letter(letter)
    catalog = {item.letter: item for item in host_power_precheck_catalog()}
    item = catalog[letter_n]
    command = resolve_precheck_command(commands, letter_n)
    label = next(
        (
            lbl
            for lbl, cmd in commands
            if str(cmd or "").strip() == command and _label_matches_precheck_letter(lbl, letter_n)
        ),
        item.label,
    )
    if precheck_command_is_mutating(command):
        return {
            "ok": False,
            "letter": letter_n,
            "label": label,
            "command": command,
            "error": "Precheck commands cannot include shutdown/reboot/halt/poweroff",
        }
    try:
        output = run_command(command)
    except Exception as exc:
        return {
            "ok": False,
            "letter": letter_n,
            "label": label,
            "command": command,
            "error": str(exc),
        }
    if str(output).startswith("ERROR:"):
        return {
            "ok": False,
            "letter": letter_n,
            "label": label,
            "command": command,
            "error": str(output),
        }
    return {
        "ok": True,
        "letter": letter_n,
        "label": label,
        "command": command,
        "output": output,
    }
```

Keep existing `extract_power_steps` unchanged so Preview still ignores `Precheck -` lines.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_host_power_ops.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/host_power_ops.py tests/test_host_power_ops.py
git commit -m "Resolve Host Power prechecks with mutate guard."
```

---

### Task 3: Promote missing A–F lines onto Hadoop cards

**Files:**
- Modify: `launchpad/hadoop_linux_promote.py`
- Modify: `tests/test_hadoop_linux_promote.py`

**Interfaces:**
- Consumes: `host_power_precheck_catalog()` (or `HADOOP_LINUX_COMMANDS` Precheck lines)
- Produces: `ensure_hadoop_linux_cards(db)` also appends missing `Precheck - A`…`F` lines on `hadoop_linux` cards (and on newly promoted cards) without rewriting an existing custom letter

A letter is present when any parsed label matches `_label_matches_precheck_letter` for that letter (same rule as Task 2). Duplicate the small matcher in promote **or** import `_label_matches_precheck_letter` / a public `precheck_letter_from_label(label) -> str | None` from `host_power_ops`. Prefer exporting:

```python
def precheck_letter_from_label(label: str) -> str | None:
```

from `host_power_ops.py` (returns `"A"`…`"F"` or `None`) and use it in promote.

If a `hadoop_linux` card already has `Power -` but is missing any A–F letter, `ensure_hadoop_linux_cards` must still update it (today it skips when Power exists).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_hadoop_linux_promote.py`:

```python
def test_ensure_hadoop_linux_cards_appends_missing_prechecks(tmp_path):
    db = Database(tmp_path / "launchpad.db")
    card_id = _ssh_card(
        db,
        name="Hadoop node",
        device_profile="hadoop_linux",
        custom_commands=(
            "Health - Uptime|uptime\n"
            "Precheck - D HDFS dfsadmin report|hdfs dfsadmin -report | head -n 5\n"
            "Power - OS Shutdown|sudo shutdown -h now"
        ),
    )

    assert ensure_hadoop_linux_cards(db) == 1
    card = db.get_card(card_id)
    labels = [label for label, _ in parse_command_lines(card.custom_commands)]
    letters = {
        label[11]
        for label in labels
        if label.startswith("Precheck - ") and len(label) >= 12 and label[11] in "ABCDEF"
    }
    assert letters == {"A", "B", "C", "D", "E", "F"}
    d_cmd = next(
        cmd
        for label, cmd in parse_command_lines(card.custom_commands)
        if label.startswith("Precheck - D")
    )
    assert d_cmd == "hdfs dfsadmin -report | head -n 5"
    assert "Health - Uptime" in labels
    assert any(label.startswith("Power -") for label in labels)


def test_ensure_hadoop_linux_cards_noop_when_prechecks_and_power_present(tmp_path):
    db = Database(tmp_path / "launchpad.db")
    from launchpad.storage_presets import preset_command_text

    card_id = _ssh_card(
        db,
        name="Hadoop node",
        device_profile="hadoop_linux",
        custom_commands=preset_command_text("hadoop_linux"),
    )
    assert ensure_hadoop_linux_cards(db) == 0
    assert db.get_card(card_id).device_profile == "hadoop_linux"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_hadoop_linux_promote.py::test_ensure_hadoop_linux_cards_appends_missing_prechecks -q`

Expected: FAIL (`ensure_hadoop_linux_cards` returns 0 because Power already exists)

- [ ] **Step 3: Implement precheck merge in promote**

Export `precheck_letter_from_label` from `host_power_ops.py`:

```python
def precheck_letter_from_label(label: str) -> str | None:
    text = str(label or "")
    for letter in PRECHECK_LETTERS:
        if _label_matches_precheck_letter(text, letter):
            return letter
    return None
```

In `launchpad/hadoop_linux_promote.py`, import catalog + `precheck_letter_from_label`. Change merge so that after ensuring Power lines, append any missing catalog `Precheck -` tuples. For `hadoop_linux` cards, update whenever the merged text differs from current custom_commands (or when any letter/power was missing).

Keep promoting General SSH Hadoop-named cards as today (full preset or merge). Existing tests that expect Power lines must still pass.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_hadoop_linux_promote.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/hadoop_linux_promote.py launchpad/host_power_ops.py tests/test_hadoop_linux_promote.py
git commit -m "Promote missing Host Power A-F precheck commands."
```

---

### Task 4: HealthServer precheck APIs

**Files:**
- Modify: `launchpad/health_server.py`
- Modify: `tests/test_host_power_api.py`

**Interfaces:**
- Consumes: `host_power_precheck_catalog_payload`, `normalize_precheck_letter`, `run_host_power_precheck_for_card`, existing `_host_power_selection` / `_host_power_card_payload` / `_snap_run_command`
- Produces:
  - `GET /api/host-power/prechecks` → `{ "prechecks": [ {letter, label, hint}, ... ] }`
  - `HealthServer.host_power_precheck(card_ids: list[Any], *, letter: str) -> dict[str, Any]`
  - `POST /api/host-power/precheck` body `{ card_ids, letter }` → `{ ok, letter, warnings?, hosts: [{card_id, name, host, ok, letter, label, command, output?, error?}] }`
  - Invalid letter → HTTP 400 via `ValueError`
  - Empty / unmatched selection → `ok: False`, `hosts: []`, warnings (same strings as preview/run), **no SSH**
  - No `confirm` field required

- [ ] **Step 1: Write the failing tests**

Add a GET helper next to `_post` in `tests/test_host_power_api.py`:

```python
def _get(path: str, monkeypatch, server: HealthServer) -> dict:
    handler = object.__new__(_HealthHandler)
    handler.path = path
    sent: dict = {}

    def _send_json(response, status=200):
        sent.update(payload=response, status=status)

    handler._send_json = _send_json
    monkeypatch.setattr(health_server_module, "get_health_server", lambda: server)
    handler.do_GET()
    return sent
```

Add tests:

```python
def test_host_power_prechecks_catalog_get(monkeypatch):
    server = HealthServer()
    response = _get("/api/host-power/prechecks", monkeypatch, server)
    assert response["status"] == 200
    letters = [row["letter"] for row in response["payload"]["prechecks"]]
    assert letters == ["A", "B", "C", "D", "E", "F"]
    assert "command" not in response["payload"]["prechecks"][0]


def test_host_power_precheck_runs_without_confirm(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card(1)
    commands: list[str] = []

    def run_command(command: str) -> str:
        commands.append(command)
        return " 12:00:01 up 1 day"

    monkeypatch.setattr(
        HealthServer,
        "_snap_run_command",
        staticmethod(lambda _card: run_command),
    )
    result = server.host_power_precheck([1], letter="a")
    assert result["ok"] is True
    assert result["letter"] == "A"
    assert result["hosts"][0]["ok"] is True
    assert commands == ["uptime; cat /proc/loadavg"]


def test_host_power_precheck_invalid_letter_is_400(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card(1)
    response = _post(
        "/api/host-power/precheck",
        {"card_ids": [1], "letter": "Z"},
        monkeypatch,
        server,
    )
    assert response["status"] == 400
    assert "A" in response["payload"]["error"] or "letter" in response["payload"]["error"].lower()


def test_host_power_precheck_empty_selection_not_ok():
    server = HealthServer()
    result = server.host_power_precheck([], letter="A")
    assert result["ok"] is False
    assert result["hosts"] == []
    assert "No hosts selected" in result["warnings"]


def test_host_power_precheck_continues_after_one_host_fails(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card(1, name="Failed host")
    server._cards[2] = _card(2, name="Healthy host", host="10.0.0.2")

    def runner_for(card: HealthCard):
        def run_command(command: str) -> str:
            return "ERROR: refused" if card.card_id == 1 else "ok"

        return run_command

    monkeypatch.setattr(
        HealthServer,
        "_snap_run_command",
        staticmethod(runner_for),
    )
    result = server.host_power_precheck([1, 2], letter="E")
    assert result["ok"] is False
    assert [host["card_id"] for host in result["hosts"]] == [1, 2]
    assert result["hosts"][0]["ok"] is False
    assert result["hosts"][1]["ok"] is True


def test_host_power_run_still_requires_confirm(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card(1)
    response = _post(
        "/api/host-power/run",
        {"card_ids": [1], "confirm": False},
        monkeypatch,
        server,
    )
    assert response["status"] == 400
```

(`test_host_power_run_still_requires_confirm` may already exist as `test_host_power_run_requires_confirm` — do not duplicate; keep the existing confirm test.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_host_power_api.py::test_host_power_prechecks_catalog_get tests/test_host_power_api.py::test_host_power_precheck_runs_without_confirm tests/test_host_power_api.py::test_host_power_precheck_invalid_letter_is_400 -q`

Expected: FAIL (route / method missing)

- [ ] **Step 3: Implement server methods + routes**

Import from `host_power_ops`: `host_power_precheck_catalog_payload`, `normalize_precheck_letter`, `run_host_power_precheck_for_card`.

Add `HealthServer.host_power_precheck`:

```python
    def host_power_precheck(self, card_ids: list[Any], *, letter: str) -> dict[str, Any]:
        letter_n = normalize_precheck_letter(letter)
        cards, selection_warnings = self._host_power_selection(card_ids)
        if not cards:
            return {
                "ok": False,
                "letter": letter_n,
                "warnings": selection_warnings,
                "hosts": [],
            }
        hosts: list[dict[str, Any]] = []
        for card in cards:
            payload = self._host_power_card_payload(card)
            result = run_host_power_precheck_for_card(
                letter=letter_n,
                commands=payload["commands"],
                run_command=self._snap_run_command(card),
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
            "letter": letter_n,
            "hosts": hosts,
        }
        if selection_warnings:
            response["warnings"] = selection_warnings
        return response
```

In `_HealthHandler.do_GET`, next to `/api/host-power/cards`:

```python
        if path == "/api/host-power/prechecks":
            self._send_json({"prechecks": host_power_precheck_catalog_payload()})
            return
```

In `do_POST`, add `/api/host-power/precheck` (same JSON parse pattern as preview/run): read `card_ids` list + `letter`; call `server.host_power_precheck`; map `ValueError` → 400.

Do **not** require confirm on this path.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_host_power_api.py -q`

Expected: PASS (including existing preview/run confirm tests)

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_host_power_api.py
git commit -m "Add Host Power precheck APIs without confirm."
```

---

### Task 5: Host Power A–F UI + version 1.6.143

**Files:**
- Modify: `launchpad/host_power.py`
- Modify: `launchpad/config.py`
- Modify: `tests/test_host_power_page.py`
- Modify: `tests/test_system_connectivity_version.py` (`APP_VERSION == "1.6.143"`)
- Modify: `tests/test_hadoop_sudo_wire.py` (same version pin)

**Interfaces:**
- Consumes: `/api/host-power/prechecks`, `/api/host-power/precheck`
- Produces: Host Power page with six A–F buttons; click runs precheck on checked hosts and **appends** to `#log`; Preview/Run still replace the log; in-flight lock disables A–F + Preview + Run

- [ ] **Step 1: Write the failing page/version tests**

Update `tests/test_host_power_page.py` `test_host_power_markers` (or add `test_host_power_precheck_markers`):

```python
def test_host_power_precheck_markers():
    assert "/api/host-power/prechecks" in HOST_POWER_HTML
    assert "/api/host-power/precheck" in HOST_POWER_HTML
    assert 'id="prechecks"' in HOST_POWER_HTML
    assert 'data-letter="A"' in HOST_POWER_HTML
    assert 'data-letter="F"' in HOST_POWER_HTML
    assert "read-only" in HOST_POWER_HTML.lower() or "Precheck" in HOST_POWER_HTML
```

Update version pins:

```python
assert APP_VERSION == "1.6.143"
```

in `tests/test_system_connectivity_version.py` and `tests/test_hadoop_sudo_wire.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_host_power_page.py::test_host_power_precheck_markers tests/test_system_connectivity_version.py -q`

Expected: FAIL (markers missing / version still 1.6.142)

- [ ] **Step 3: Implement page + bump version**

In `launchpad/config.py` set `APP_VERSION = "1.6.143"`.

In `launchpad/host_power.py` HTML:

- Add a Prechecks block above Preview/Run:

```html
      <h3 style="margin:14px 0 8px;color:#ff9a56;font-size:1rem;">Prechecks</h3>
      <p class="hint">Read-only. Check one or more hosts, then click A–F. Does not stop services or shut down.</p>
      <div id="prechecks" class="actions"></div>
```

- On `loadCards` success (or `DOMContentLoaded`), `GET /api/host-power/prechecks` and render buttons:

```javascript
    function renderPrechecks(rows) {
      const wrap = document.getElementById("prechecks");
      wrap.replaceChildren();
      (rows || []).forEach((row) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "secondary precheck-btn";
        btn.dataset.letter = row.letter;
        btn.textContent = row.letter + " " + (row.hint || "");
        btn.addEventListener("click", () => runPrecheck(row.letter));
        wrap.append(btn);
      });
    }
```

- Append log helper:

```javascript
    function appendLog(value) {
      const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
      const existing = log.textContent || "";
      log.textContent = existing ? existing + "\n" + text : text;
    }
```

- `runPrecheck(letter)`:
  - if `selectedIds()` is empty: `appendLog("Select one or more hosts before running a precheck.")` and return (no fetch)
  - else `withButtonsLocked`: `appendLog("--- Precheck " + letter + " @ " + new Date().toLocaleString() + " ---")` then POST `/api/host-power/precheck` with `{card_ids, letter}` and `appendLog` the JSON
- Extend `withButtonsLocked` to disable `.precheck-btn` as well as Preview/Run.
- Keep Preview/Run using `writeLog` (replace).

Fallback if catalog GET fails: still render A–F from a local `["A","B","C","D","E","F"]` hint list matching the spec so buttons exist.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_host_power_page.py tests/test_host_power_api.py tests/test_host_power_ops.py tests/test_hadoop_presets.py tests/test_hadoop_linux_promote.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/host_power.py launchpad/config.py tests/test_host_power_page.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py
git commit -m "Add Host Power A-F precheck buttons (1.6.143)."
```

---

## Spec coverage

| Spec requirement | Task |
|------------------|------|
| A–F clickable buttons | 5 |
| Click runs SSH on selected hosts | 4 + 5 |
| Append Run log; Preview/Run may replace | 5 |
| No confirm for prechecks | 4 |
| Preview/Run still `Power -` + confirm | 2 (unchanged extract) + 4 regression |
| Preset `Precheck - A`…`F` before Power | 1 |
| Catalog fallback when card line missing | 2 |
| Promote missing letters; keep custom D | 3 |
| Mutate-guard shutdown/reboot/halt/poweroff | 2 |
| `GET /api/host-power/prechecks` | 4 |
| `POST /api/host-power/precheck` | 4 |
| Invalid letter 400 | 4 |
| Empty selection: log/API warning, no SSH | 4 + 5 |
| Version 1.6.143 | 5 |
| No editable Run log / no auto-run on Run | out of scope (not implemented) |
