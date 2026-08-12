# LUN Builder FlashSystem Size CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Treat bare LUN Builder sizes as GB and format FlashSystem `mkvdisk -size` without scientific notation so Run Create no longer fails with CMMVC5716E (v**1.6.154**).

**Architecture:** Keep shared `parse_capacity_to_gb` unchanged (bare → bytes for Contingency). In `lun_builder_create.py`, `_size_gb` appends `GB` when the size has no unit, and a new `_format_size_gb_cli` helper emits plain numeric tokens for `svctask mkvdisk -size`.

**Tech Stack:** Python, pytest, Spectrum Virtualize CLI tokens.

**Spec:** `docs/superpowers/specs/2026-08-11-lun-builder-size-cli-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.153`; bump to `1.6.154` only in Task 2. Do not bump earlier.
- Do **not** change `parse_capacity_to_gb` default unit (bare numbers stay bytes for Contingency).
- LUN Builder bare number → GB. Explicit units (`GB`, `TB`, `MB`, etc.) keep today’s meaning via the shared parser.
- FlashSystem `-size` must never contain `e` or `E` (no scientific notation).
- HP `createvv` still uses `math.ceil(size_gb)` + `g`. DS8884 / XIV still pass the typed size string through `cli_token`.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task’s commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch or install zips.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/lun_builder_create.py` | Bare→GB parse; plain `-size` CLI format |
| `tests/test_lun_builder_create.py` | Bare / fractional / no-scientific-notation cases |
| `tests/test_contingency_snap_create.py` | Assert bare `"100"` still means bytes |
| `launchpad/config.py` | `APP_VERSION` → `1.6.154` |
| `tests/test_system_connectivity_version.py` | Version pin → `1.6.154` |
| `tests/test_hadoop_sudo_wire.py` | Version pin → `1.6.154` |
| `tests/test_capacity_unit_js.py` | Version pin → `1.6.154` |

---

### Task 1: Bare GB parse and plain mkvdisk size token

**Files:**
- Modify: `launchpad/lun_builder_create.py`
- Modify: `tests/test_lun_builder_create.py`
- Modify: `tests/test_contingency_snap_create.py`

**Interfaces:**
- Consumes: `parse_capacity_to_gb(capacity: str) -> float | None` (unchanged)
- Produces: `_size_gb(value: str) -> int | float` (bare → GB); `_format_size_gb_cli(size_gb: int | float) -> str` (plain token); FlashSystem steps use `_format_size_gb_cli` in `-size`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lun_builder_create.py`:

```python
def test_svc_bare_size_means_gb():
    steps = build_lun_steps(
        _build(
            {
                "purpose": "vol",
                "count": 1,
                "size": "100",
                "pool_or_cpg": "MtVerno_Pool1",
                "storage_profile": "flashsystem_5200",
                "card_hint": "cardA",
            }
        ),
        inventory_by_card=None,
    )
    assert "-size 100 -unit gb" in steps[0]["cmd"]
    assert "e-" not in steps[0]["cmd"].lower()
    assert "e+" not in steps[0]["cmd"].lower()


def test_svc_explicit_gb_unchanged():
    steps = build_lun_steps(
        _build(
            {
                "purpose": "vol",
                "count": 1,
                "size": "100GB",
                "pool_or_cpg": "Pool0",
                "storage_profile": "flashsystem_5200",
                "card_hint": "cardA",
            }
        ),
        inventory_by_card=None,
    )
    assert "-size 100 -unit gb" in steps[0]["cmd"]


def test_svc_fractional_size_has_no_scientific_notation():
    steps = build_lun_steps(
        _build(
            {
                "purpose": "vol",
                "count": 1,
                "size": "1.5",
                "pool_or_cpg": "Pool0",
                "storage_profile": "flashsystem_5200",
                "card_hint": "cardA",
            }
        ),
        inventory_by_card=None,
    )
    cmd = steps[0]["cmd"]
    assert "-size 1.5 -unit gb" in cmd
    size_token = cmd.split("-size", 1)[1].split("-unit", 1)[0]
    assert "e" not in size_token.lower()
```

Primary assertion is the `-size` token (volume naming may use `name_prefix` / host rules).

Also append to `tests/test_contingency_snap_create.py` next to `test_parse_capacity_tib`:

```python
def test_parse_capacity_bare_number_still_bytes():
    # LUN Builder treats bare numbers as GB; Contingency must keep bytes.
    assert parse_capacity_to_gb("100") == pytest.approx(100 / (1024**3))
```

Add `import pytest` at the top of `test_contingency_snap_create.py` if missing.

- [ ] **Step 2: Run tests to verify they fail**

```powershell
cd C:\Users\BrianColley\LaunchPad
python -m pytest tests/test_lun_builder_create.py::test_svc_bare_size_means_gb tests/test_lun_builder_create.py::test_svc_explicit_gb_unchanged tests/test_lun_builder_create.py::test_svc_fractional_size_has_no_scientific_notation tests/test_contingency_snap_create.py::test_parse_capacity_bare_number_still_bytes -v
```

Expected: LUN Builder bare-size / fractional tests FAIL (current bare `100` → scientific / tiny size). Contingency bare-bytes test should already PASS (documents lock-in); if it fails, stop and report — do not “fix” by changing the shared parser.

- [ ] **Step 3: Implement parse + format in `lun_builder_create.py`**

Near the top of `launchpad/lun_builder_create.py`, add `import re` if not present, then replace `_size_gb` and add helpers:

```python
_BARE_SIZE_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def _size_gb(value: str) -> int | float:
    raw = str(value or "").strip()
    if _BARE_SIZE_RE.fullmatch(raw):
        raw = f"{raw}GB"
    size_gb = parse_capacity_to_gb(raw)
    if size_gb is None or size_gb <= 0:
        raise ValueError(f"Invalid LUN size: {value!r}")
    return int(size_gb) if size_gb == int(size_gb) else size_gb


def _format_size_gb_cli(size_gb: int | float) -> str:
    if isinstance(size_gb, int) or size_gb == int(size_gb):
        return str(int(size_gb))
    text = f"{float(size_gb):.10f}".rstrip("0").rstrip(".")
    if not text or "e" in text.lower():
        raise ValueError(f"Cannot format LUN size for CLI: {size_gb!r}")
    return text
```

In the FlashSystem `mkvdisk` command builder, change:

```python
f"-size {size_gb} -unit gb"
```

to:

```python
f"-size {_format_size_gb_cli(size_gb)} -unit gb"
```

Do not change HP / DS8884 / XIV branches beyond the shared `_size_gb` path.

- [ ] **Step 4: Run tests to verify they pass**

```powershell
cd C:\Users\BrianColley\LaunchPad
python -m pytest tests/test_lun_builder_create.py tests/test_contingency_snap_create.py::test_parse_capacity_tib tests/test_contingency_snap_create.py::test_parse_capacity_bare_number_still_bytes -v
```

Expected: PASS (all LUN create tests + both capacity parse tests).

- [ ] **Step 5: Commit**

```powershell
cd C:\Users\BrianColley\LaunchPad
git add launchpad/lun_builder_create.py tests/test_lun_builder_create.py tests/test_contingency_snap_create.py
git commit -m "Treat bare LUN sizes as GB and format mkvdisk -size without exponents."
```

---

### Task 2: Bump APP_VERSION to 1.6.154

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Modify: `tests/test_capacity_unit_js.py`

**Interfaces:**
- Consumes: Task 1 complete
- Produces: `APP_VERSION = "1.6.154"` and matching pins

- [ ] **Step 1: Update version pins (failing until config bump)**

In these three files, change `"1.6.153"` → `"1.6.154"`:

- `tests/test_system_connectivity_version.py`
- `tests/test_capacity_unit_js.py`
- `tests/test_hadoop_sudo_wire.py` — rename `test_version_153` → `test_version_154` and assert `"1.6.154"`

- [ ] **Step 2: Run version tests to verify they fail**

```powershell
cd C:\Users\BrianColley\LaunchPad
python -m pytest tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py::test_version_154 tests/test_capacity_unit_js.py -v
```

Expected: FAIL asserting `1.6.154` vs current `1.6.153`.

- [ ] **Step 3: Bump config**

In `launchpad/config.py`:

```python
APP_VERSION = "1.6.154"
```

- [ ] **Step 4: Run version + LUN create regression**

```powershell
cd C:\Users\BrianColley\LaunchPad
python -m pytest tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py::test_version_154 tests/test_capacity_unit_js.py tests/test_lun_builder_create.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
cd C:\Users\BrianColley\LaunchPad
git add launchpad/config.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py tests/test_capacity_unit_js.py
git commit -m "Bump version to 1.6.154 for LUN Builder size CLI fix."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Bare number → GB in LUN Builder | Task 1 |
| Explicit units unchanged | Task 1 |
| Plain `-size` token / no scientific notation | Task 1 |
| Contingency / shared parser unchanged | Task 1 (lock-in test) |
| HP / DS8884 / XIV non-goals respected | Task 1 (no branch changes beyond parse) |
| APP_VERSION 1.6.154 | Task 2 |
| Active Issues / Excel out of scope | — (not planned) |
