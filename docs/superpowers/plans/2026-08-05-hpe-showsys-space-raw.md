# HPE `showsys -space` Raw + Stale CPG Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collect HPE Raw from `showsys -space` (SSMC Total/Allocated/Free), keep System on `showsys -d`, and stop stale `showcpg` from surviving capacity refresh when Include CPG/pools is off.

**Architecture:** Add `Capacity - Raw` / `showsys -space` to HPE presets; parse that output into `raw_capacity_summary` (prefer over `-d` raw keys). Exclude `-space` from System lookup. When `include_pools=False`, strip pool/CPG results from the capacity-focus merge before `analyze_health`. Do not render All-CPGs as System when no pool results remain.

**Tech Stack:** Python 3, pytest, existing Capacity Report HTML/toggles.

**Spec:** `docs/superpowers/specs/2026-08-05-hpe-showsys-space-raw-design.md`

## Global Constraints

- Branch: `feature/hpe-capacity-parse`
- System = `showsys -d`; Raw = `showsys -space` Total row; CPG = `showcpg` when pools on
- Never use `showsys -space` as System capacity
- When `include_pools=0`, drop prior pool/CPG command results on merge
- No All-CPGs System bar when pools are absent / off after merge
- No per-media `-devtype` in v1; no raw alerts; IBM path unchanged
- Bump `APP_VERSION` to **1.6.116** in the final task
- Imports at module top; commit per task; cwd `C:\Users\BrianColley\LaunchPad`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/storage_presets.py` | Add `showsys -space`; ensure helper inserts it without replacing `-d` |
| `launchpad/flashsystem_parse.py` | Parse `-space` MB totals into raw summary (reuse helpers) |
| `launchpad/flashsystem_health.py` | Prefer `-space` for raw; exclude `-space` from system find; no All-CPGs System when no pools |
| `launchpad/command_format.py` | Export `_is_pool_capacity_command` or add `drop_pool_capacity_results` |
| `launchpad/health_server.py` | Merge: drop pool results when `include_pools=False` |
| `tests/test_*.py` | Presets, parse, analyze, merge |
| `launchpad/config.py` | `1.6.116` |

---

### Task 1: Presets — add `showsys -space`

**Files:**
- Modify: `launchpad/storage_presets.py`
- Test: `tests/test_hpe_capacity_commands.py`

**Interfaces:**
- Produces: `("Capacity - Raw", "showsys -space")` on `HP_3PAR_COMMANDS` and `HPE_PRIMERA_COMMANDS` immediately after Capacity - System; `ensure_hpe_capacity_commands` inserts Raw if missing without treating `-space` as satisfying System.

- [ ] **Step 1: Write failing tests**

```python
def test_hpe_presets_include_showsys_space_raw():
    assert ("Capacity - Raw", "showsys -space") in HP_3PAR_COMMANDS
    assert ("Capacity - Raw", "showsys -space") in HPE_PRIMERA_COMMANDS
    assert HP_3PAR_COMMANDS.index(("Capacity - System", "showsys -d")) < HP_3PAR_COMMANDS.index(
        ("Capacity - Raw", "showsys -space")
    )

def test_ensure_hpe_inserts_showsys_space_and_keeps_showsys_d():
    from launchpad.storage_presets import ensure_hpe_capacity_commands
    cmds = ensure_hpe_capacity_commands("hpe_primera", [("Health - Alerts", "showalert")])
    assert ("Capacity - System", "showsys -d") in cmds
    assert ("Capacity - Raw", "showsys -space") in cmds
    # -space alone must not skip inserting -d
    cmds2 = ensure_hpe_capacity_commands(
        "hpe_primera",
        [("Capacity - Raw", "showsys -space"), ("Health - Alerts", "showalert")],
    )
    assert ("Capacity - System", "showsys -d") in cmds2
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python -m pytest tests/test_hpe_capacity_commands.py::test_hpe_presets_include_showsys_space_raw tests/test_hpe_capacity_commands.py::test_ensure_hpe_inserts_showsys_space_and_keeps_showsys_d -v`

- [ ] **Step 3: Implement presets + ensure helper**

In `HP_3PAR_COMMANDS` / `HPE_PRIMERA_COMMANDS`, after System:

```python
("Capacity - System", "showsys -d"),
("Capacity - Raw", "showsys -space"),
("Capacity - CPG %", "showcpg"),
```

In `ensure_hpe_capacity_commands`:

- Detect System with `"showsys -d"` or (`"showsys"` in command and `"-space" not in command`).
- Detect Raw with `"showsys -space"`.
- If System missing, insert `("Capacity - System", "showsys -d")` at front of capacity block.
- If Raw missing, insert `("Capacity - Raw", "showsys -space")` after System.
- Do **not** rewrite `showsys -space` to `showsys -d`. Bare `showspace` rewrite stays as today.

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```text
Add Capacity - Raw (showsys -space) to HPE presets.
```

---

### Task 2: Parse `showsys -space` as raw

**Files:**
- Modify: `launchpad/flashsystem_parse.py`
- Test: `tests/test_capacity_layers_parse.py`

**Interfaces:**
- Produces: `parse_showsys_space_raw(output: str) -> dict[str, Any] | None` — Total/Allocated/Free Capacity in MB; same shape as `parse_raw_capacity_summary`.

Distinguishing System vs Raw uses **which command result** is parsed (same key names on `-d` and `-space`).

- [ ] **Step 1: Failing test**

```python
SHOWSYS_SPACE = """---------System Capacity---------
Total Capacity     :   57184000
Allocated Capacity :   41181000
Free Capacity      :   16003000
Failed Capacity    :          0
"""

def test_parse_showsys_space_raw_matches_ssmc_total_row():
    from launchpad.flashsystem_parse import parse_showsys_space_raw
    raw = parse_showsys_space_raw(SHOWSYS_SPACE)
    assert raw is not None
    assert raw["total_bytes"] == 57184000 * 1024**2
    assert raw["used_bytes"] == 41181000 * 1024**2
    assert raw["free_bytes"] == 16003000 * 1024**2
    assert raw["used_pct"] == round(41181000 / 57184000 * 100, 1)
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `parse_showsys_space_raw` in `flashsystem_parse.py`**

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit** — `Parse showsys -space into raw capacity summary.`

---

### Task 3: analyze_health — wire `-space` raw; exclude from System

**Files:**
- Modify: `launchpad/flashsystem_health.py`
- Test: `tests/test_capacity_layers_health.py`

**Interfaces:**
- Consumes: `parse_showsys_space_raw`
- System find: skip items whose command contains `showsys -space` or label contains `capacity - raw`
- Prefer `parse_showsys_space_raw` from Capacity - Raw / `showsys -space`; else `parse_raw_capacity_summary(system_output)`
- Popup System: `system_capacity` if present; else capacity rollup **only if pools exist**

```python
display_system = system_capacity
if display_system is None and pools:
    display_system = capacity
popup_html = format_capacity_report_html(display_system, pools_output, raw_capacity=...)
```

- [ ] **Step 1: Failing tests** (see plan body in repo; System 27% + Raw from SPACE fixture; no All CPGs when system unparseable and no pools)

- [ ] **Step 2–4: Implement + PASS**

- [ ] **Step 5: Commit** — `Prefer showsys -space for HPE raw; skip All-CPGs System without pools.`

---

### Task 4: Drop stale pool results when `include_pools=False`

**Files:**
- Modify: `launchpad/command_format.py`
- Modify: `launchpad/health_server.py` `refresh_card` merge
- Test: `tests/test_capacity_layers_filter.py`

**Interfaces:**

```python
def drop_pool_capacity_results(results: list[dict]) -> list[dict]:
    return [
        item for item in results
        if not _is_pool_capacity_command(
            str(item.get("label") or ""),
            str(item.get("command") or ""),
        )
    ]
```

After merge in `refresh_card`, when `include_pools` is False: `command_results = drop_pool_capacity_results(...)`.

- [ ] **Step 1: Failing test** — prior showcpg + refresh include_pools=False → no showcpg in results; no Pool CRIT; no All CPGs when `-d` OK

- [ ] **Step 2–4: Implement + PASS**

- [ ] **Step 5: Commit** — `Drop stale showcpg on capacity refresh when pools off.`

---

### Task 5: Version 1.6.116 + verify

**Files:**
- Modify: `launchpad/config.py`

- [ ] Set `APP_VERSION = "1.6.116"`
- [ ] Run related pytest suite — all pass
- [ ] Commit — `Bump app version to 1.6.116 for HPE showsys -space raw.`

---

## Spec coverage check

| Spec item | Task |
|-----------|------|
| Preset Capacity - Raw | 1 |
| ensure inserts -space, keeps -d | 1 |
| Parse -space MB → raw | 2 |
| Prefer -space raw; fallback -d raw keys | 3 |
| Exclude -space from System | 3 |
| No All-CPGs System when pools off/absent | 3 |
| Merge drop stale showcpg | 4 |
| Version 1.6.116 | 5 |
