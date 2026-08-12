# LUN Builder Size Unit Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GB/TB dropdown beside the LUN Builder Size number so operators see the unit, while still storing one `size` string and creating volumes correctly (v**1.6.157**).

**Architecture:** Pure `split_lun_size_for_ui` / `join_lun_size` helpers (Python + mirrored JS) keep a single `lun.size` string. The Size cell renders amount + GB/TB select; create/export/templates stay on the existing `size` field and 1.6.154 `_size_gb` path.

**Tech Stack:** Python, embedded LUN Builder HTML/JS in `lun_builder.py`, pytest.

**Spec:** `docs/superpowers/specs/2026-08-12-lun-builder-size-unit-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.156`; bump to `1.6.157` only in the final version task.
- Units are **GB** and **TB** only; default **GB**.
- Layout: number + unit dropdown **in the Size cell**.
- Storage: one `size` string (`100GB` / `1TB`); no new JSON keys.
- Do not change Contingency `parse_capacity_to_gb` defaults; do not change FlashSystem `-unit gb` contract.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch or install zips.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/lun_builder_size.py` | Pure split/join helpers for Size UI |
| `tests/test_lun_builder_size.py` | Helper unit tests |
| `launchpad/lun_builder.py` | Size cell UI + JS sync into `lun.size` |
| `tests/test_lun_builder_page.py` | Markup / contract tests for unit select |
| `launchpad/config.py` + version pins | `1.6.157` |

---

### Task 1: Size split/join helpers

**Files:**
- Create: `launchpad/lun_builder_size.py`
- Create: `tests/test_lun_builder_size.py`

**Interfaces:**
- Produces:
  - `DEFAULT_LUN_SIZE_UNIT = "GB"`
  - `LUN_SIZE_UNITS = ("GB", "TB")`
  - `split_lun_size_for_ui(size: str) -> tuple[str, str]`  # (amount, unit) unit always `GB` or `TB`
  - `join_lun_size(amount: str, unit: str) -> str`  # empty amount → `""`; else `{amount}{UNIT}` uppercase unit

- [ ] **Step 1: Write failing tests**

```python
from launchpad.lun_builder_size import join_lun_size, split_lun_size_for_ui


def test_split_bare_defaults_to_gb():
    assert split_lun_size_for_ui("100") == ("100", "GB")


def test_split_gb_and_tb():
    assert split_lun_size_for_ui("100GB") == ("100", "GB")
    assert split_lun_size_for_ui("1.5tb") == ("1.5", "TB")


def test_split_other_suffix_shows_amount_with_gb_display():
    assert split_lun_size_for_ui("500MB") == ("500", "GB")


def test_join_and_paste_normalize():
    assert join_lun_size("100", "GB") == "100GB"
    assert join_lun_size("1", "TB") == "1TB"
    assert join_lun_size("", "GB") == ""
    assert join_lun_size("500GB", "TB") == "500GB"  # amount paste wins unit from amount
```

For `join_lun_size`: if `amount` itself matches `{number}{GB|TB}` (case-insensitive), prefer that parsed amount+unit over the separate `unit` argument (paste-normalize). Otherwise strip spaces and append uppercase `GB`/`TB` (invalid unit → `GB`).

- [ ] **Step 2: Run — expect FAIL**

```powershell
cd C:\Users\BrianColley\LaunchPad
python -m pytest tests/test_lun_builder_size.py -v
```

- [ ] **Step 3: Implement `lun_builder_size.py`**

Parse with a regex like `^(-?\d+(?:\.\d+)?)\s*(GB|TB|MB|KB|PB|B)?$` (case-insensitive).  
`split_lun_size_for_ui`: bare or missing/unknown UI unit → display unit `GB`; only `GB`/`TB` suffixes select those units (other suffixes: amount digits, display unit `GB`, no rewrite of stored value here).  
`join_lun_size`: empty/blank amount → `""`; if amount contains GB/TB suffix, use that; else `{amount}{unit}` with unit forced to `GB` or `TB`.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder_size.py tests/test_lun_builder_size.py
git commit -m "Add LUN Builder size amount/unit split helpers."
```

---

### Task 2: Size cell UI (number + GB/TB)

**Files:**
- Modify: `launchpad/lun_builder.py`
- Modify: `tests/test_lun_builder_page.py`

**Interfaces:**
- Consumes: same split/join rules as Task 1 (mirror in JS; keep Python helpers as source of truth for tests)
- Produces: Size cell markup with `data-key="size_amount"` input and `data-key="size_unit"` select (`GB`/`TB`); `updateField` writes `item.size` via join rules; no new persisted keys

- [ ] **Step 1: Failing page contract tests**

Add to `tests/test_lun_builder_page.py`:

```python
def test_lun_builder_size_cell_has_gb_tb_unit_select():
    assert 'data-key="size_amount"' in LUN_BUILDER_HTML
    assert 'data-key="size_unit"' in LUN_BUILDER_HTML
    assert "<option value=\"GB\">GB</option>" in LUN_BUILDER_HTML
    assert "<option value=\"TB\">TB</option>" in LUN_BUILDER_HTML
    assert "function splitLunSizeForUi" in LUN_BUILDER_HTML
    assert "function joinLunSize" in LUN_BUILDER_HTML
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_lun_builder_page.py::test_lun_builder_size_cell_has_gb_tb_unit_select -v
```

- [ ] **Step 3: Implement UI**

1. CSS: `.size-cell { display:flex; gap:6px; align-items:center; }` and `.size-cell input { flex:1; min-width:4rem; }` / `.size-cell select { width:4.5rem; }`.
2. JS helpers mirroring Task 1 (`splitLunSizeForUi`, `joinLunSize`).
3. Replace Size `<td>${input("size", ...)}</td>` with a size cell that:
   - calls `splitLunSizeForUi(lun.size)` for amount + selected unit
   - renders `<input data-key="size_amount" ...>` and `<select data-key="size_unit"><option GB><option TB></select>`
4. In `updateField`, when `data-key` is `size_amount` or `size_unit`:
   - read both controls from the row
   - set `item.size = joinLunSize(amount, unit)`
   - if paste-normalize changed the unit, update the select's displayed value without a full re-render if practical
   - then existing invalidatePreview / refreshExpandedNames path
5. Do **not** assign `item.size_amount` / `item.size_unit` as persisted fields.
6. New empty rows: amount blank, unit select **GB**, `size` stays `""` until amount entered.

- [ ] **Step 4: Run page + size helper tests — expect PASS**

```powershell
python -m pytest tests/test_lun_builder_size.py tests/test_lun_builder_page.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder.py tests/test_lun_builder_page.py
git commit -m "Add GB/TB unit select to LUN Builder Size cell."
```

---

### Task 3: Bump APP_VERSION to 1.6.157

**Files:**
- `launchpad/config.py`
- `tests/test_system_connectivity_version.py`
- `tests/test_capacity_unit_js.py`
- `tests/test_hadoop_sudo_wire.py` (`test_version_156` → `test_version_157`)

- [ ] **Step 1:** Update pins to `1.6.157` (fail).
- [ ] **Step 2:** Set `APP_VERSION = "1.6.157"`.
- [ ] **Step 3:** Run version + LUN size suites — PASS.
- [ ] **Step 4: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py
git commit -m "Bump version to 1.6.157 for LUN Builder size unit selector."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Size cell number + GB/TB dropdown | Task 2 |
| Default GB | Tasks 1–2 |
| Single stored `size` string | Tasks 1–2 |
| Load/split bare, GB, TB; other suffix display GB | Task 1 |
| Paste normalize into amount+unit | Tasks 1–2 |
| Create path unchanged (`_size_gb`) | (no change; covered by existing create tests) |
| Version 1.6.157 | Task 3 |
