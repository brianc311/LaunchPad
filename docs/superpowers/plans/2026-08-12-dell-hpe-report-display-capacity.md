# Dell HPE Report Display Capacity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore HP Report / HP Forecast / HP Wkly rows when HPE cards have display capacity (raw/pools) while keeping weekly snapshots system-only (v**1.6.161**).

**Architecture:** `collect_dell_report_rows` dual-selects: `select_dell_capacity_summary` for whether to emit a row and for current-week GiB/util when no system snapshot; `select_dell_array_snapshot_summary` only for upserting the weekly store. Forecast and Wkly sheets need no separate collector — they already consume `hp_rows` / `ibm_rows`.

**Tech Stack:** Python, pytest, existing Dell Report modules.

**Spec:** `docs/superpowers/specs/2026-08-12-dell-hpe-report-display-capacity-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.160`; bump to `1.6.161` only in Task 2.
- Display selector: `select_dell_capacity_summary(..., include_pools=...)` — may use raw / pools / All CPGs per existing CPG rules.
- Snapshot selector: `select_dell_array_snapshot_summary` — never raw, never pool rollup.
- No system snapshot + display usable → emit row from display; **do not** upsert store.
- System usable → upsert `layer=system` then build row via `_row_from_snapshots` (unchanged growth gate).
- Forced-include blank rows unchanged.
- `maybe_upsert_dell_snapshot_for_card` stays system-only.
- Do not change Capacity Report UI, HPE SSH/parse, LED bands, or forecast projection math.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task’s commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch or install zips.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/dell_report_export.py` | Dual select in `collect_dell_report_rows`; `_row_from_display_summary` helper |
| `launchpad/dell_report_capacity.py` | Unchanged (both selectors already exist) |
| `tests/test_dell_report_collect.py` | Raw-only and All-CPGs+raw emit rows; no snapshot |
| `launchpad/config.py` | `APP_VERSION` → `1.6.161` |
| `tests/test_system_connectivity_version.py` | Version pin → `1.6.161` |
| `tests/test_hadoop_sudo_wire.py` | Version pin → `1.6.161` |
| `tests/test_capacity_unit_js.py` | Version pin → `1.6.161` |

---

### Task 1: Dual select in collect (display vs snapshot)

**Files:**
- Modify: `launchpad/dell_report_export.py`
- Modify: `tests/test_dell_report_collect.py`

**Interfaces:**
- Consumes:
  - `select_dell_capacity_summary(*, capacity_summary, raw_capacity_summary, pools, include_pools) -> dict | None`
  - `select_dell_array_snapshot_summary(*, capacity_summary) -> dict | None`
  - `_row_from_snapshots(prior, current) -> dict`
  - `resolve_dell_identity(...)`, `upsert_week_snapshot(...)`, `prior_and_current_for_card(...)`
- Produces:
  - `_row_from_display_summary(*, facility, array_name, model, total_bytes, used_bytes) -> dict` with prior/growth `None` and current GiB/util from display bytes
  - `collect_dell_report_rows` emits HP/IBM rows when display summary has `total_bytes > 0` even if snapshot summary is missing

- [ ] **Step 1: Update failing collect tests**

In `tests/test_dell_report_collect.py`, replace `test_collect_skips_when_only_raw_no_array_summary` with:

```python
def test_collect_emits_row_when_only_raw_no_array_snapshot():
    sites = [
        {
            "card_id": 5,
            "name": "Primera Remote",
            "device_profile": "hpe_primera_600",
            "capacity_summary": None,
            "raw_capacity_summary": {
                "name": "Vdiprimera101",
                "total_bytes": 200 * 1024**3,
                "used_bytes": 50 * 1024**3,
                "used_pct": 25.0,
            },
            "pools": [],
        }
    ]
    ibm, hp, store = collect_dell_report_rows(
        sites,
        snapshot_store={},
        include_pools=False,
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )
    assert ibm == []
    assert len(hp) == 1
    assert hp[0]["array_name"]  # identity resolved
    assert hp[0]["curr_usable_gib"] == pytest.approx(200.0)
    assert hp[0]["curr_used_gib"] == pytest.approx(50.0)
    assert hp[0]["curr_util"] == pytest.approx(0.25)
    assert hp[0]["prior_usable_gib"] is None
    assert hp[0]["weekly_growth"] is None
    assert store == {}
```

Replace `test_collect_skips_all_cpgs_even_when_raw_present` with:

```python
def test_collect_emits_raw_when_all_cpgs_and_raw_cpg_off():
    sites = [
        {
            "card_id": 5,
            "name": "HPE - VDIPRIMERA101 - WAG2",
            "device_profile": "hpe_primera_600",
            "capacity_summary": {
                "name": "All CPGs",
                "total_bytes": 10 * 1024**3,
                "used_bytes": 9 * 1024**3,
            },
            "raw_capacity_summary": {
                "name": "Vdiprimera101",
                "total_bytes": 200 * 1024**3,
                "used_bytes": 50 * 1024**3,
            },
            "pools": [],
        }
    ]
    ibm, hp, store = collect_dell_report_rows(
        sites,
        snapshot_store={},
        include_pools=False,
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )
    assert ibm == []
    assert len(hp) == 1
    assert hp[0]["curr_usable_gib"] == pytest.approx(200.0)
    assert hp[0]["curr_used_gib"] == pytest.approx(50.0)
    assert store == {}
```

Keep `test_collect_snapshots_array_not_raw_when_both_present` unchanged (system path).

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_dell_report_collect.py::test_collect_emits_row_when_only_raw_no_array_snapshot tests/test_dell_report_collect.py::test_collect_emits_raw_when_all_cpgs_and_raw_cpg_off -v
```

Expected: FAIL (HP empty / store assertions, or test names not found until renamed — after rename, assert `hp == []` style failure becomes length/gib mismatch if code still skips).

- [ ] **Step 3: Implement dual select + display row helper**

In `launchpad/dell_report_export.py`:

1. Change import:

```python
from launchpad.dell_report_capacity import (
    select_dell_array_snapshot_summary,
    select_dell_capacity_summary,
)
```

2. Add helper near `_row_from_snapshots`:

```python
def _row_from_display_summary(
    *,
    facility: str,
    array_name: str,
    model: str,
    total_bytes: float,
    used_bytes: float,
) -> dict:
    return {
        "facility": facility or "",
        "array_name": array_name or "",
        "model": model or "",
        "prior_usable_gib": None,
        "prior_used_gib": None,
        "prior_util": None,
        "curr_usable_gib": bytes_to_capacity_unit(total_bytes),
        "curr_used_gib": bytes_to_capacity_unit(used_bytes),
        "curr_util": _util_fraction(used_bytes, total_bytes),
        "weekly_growth": None,
    }
```

3. Replace the capacity selection / emit loop body in `collect_dell_report_rows` (keep signature, include_ids, family filtering) with this logic:

```python
        display = select_dell_capacity_summary(
            capacity_summary=_site_value(site, "capacity_summary"),
            raw_capacity_summary=_site_value(site, "raw_capacity_summary"),
            pools=_site_value(site, "pools") or [],
            include_pools=include_pools,
        )
        snap_summary = select_dell_array_snapshot_summary(
            capacity_summary=_site_value(site, "capacity_summary"),
        )
        display_total = float((display or {}).get("total_bytes") or 0)
        display_used = float((display or {}).get("used_bytes") or 0)

        if not display or display_total <= 0:
            if str(card_id) not in include_ids:
                continue
            ident = resolve_dell_identity(
                card_id=card_id,
                site_name=name,
                device_profile=device_profile,
                summary_name="",
                overrides=overrides,
            )
            blank = {
                "card_id": card_id,
                "facility": ident["facility"],
                "array_name": ident["array_name"],
                "model": ident["model"],
                "prior_usable_gib": None,
                "prior_used_gib": None,
                "prior_util": None,
                "curr_usable_gib": None,
                "curr_used_gib": None,
                "curr_util": None,
                "weekly_growth": None,
            }
            if family == "ibm":
                ibm_rows.append(blank)
            else:
                hp_rows.append(blank)
            continue

        ident = resolve_dell_identity(
            card_id=card_id,
            site_name=name,
            device_profile=device_profile,
            summary_name=str((display or {}).get("name") or ""),
            overrides=overrides,
        )
        facility = ident["facility"]
        model = ident["model"]
        array_name = ident["array_name"]

        if snap_summary and float(snap_summary.get("total_bytes") or 0) > 0:
            store = upsert_week_snapshot(
                store,
                card_id=card_id,
                week=week,
                usable_bytes=float(snap_summary.get("total_bytes") or 0),
                used_bytes=float(snap_summary.get("used_bytes") or 0),
                model=model,
                facility=facility,
                family=family,
                array_name=array_name,
                captured_at=captured_at,
            )
            prior, current = prior_and_current_for_card(
                store, card_id, current_week=week
            )
            if current is None:
                continue
            row = _row_from_snapshots(prior, current)
        else:
            row = _row_from_display_summary(
                facility=facility,
                array_name=array_name,
                model=model,
                total_bytes=display_total,
                used_bytes=display_used,
            )

        row["card_id"] = card_id
        if family == "ibm":
            ibm_rows.append(row)
        else:
            hp_rows.append(row)
```

Do **not** change `maybe_upsert_dell_snapshot_for_card` (still system-only).

- [ ] **Step 4: Run collect tests**

Run:

```powershell
pytest tests/test_dell_report_collect.py -v
```

Expected: PASS (all collect tests).

- [ ] **Step 5: Commit**

```powershell
git add launchpad/dell_report_export.py tests/test_dell_report_collect.py
git commit -m "Restore Dell HP rows from display capacity without raw snapshots."
```

---

### Task 2: Bump APP_VERSION to 1.6.161

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Modify: `tests/test_capacity_unit_js.py`

**Interfaces:**
- Produces: `APP_VERSION == "1.6.161"`

- [ ] **Step 1: Update version pins**

Set `APP_VERSION = "1.6.161"` in `launchpad/config.py`.

Update assertions to `"1.6.161"` in:

- `tests/test_system_connectivity_version.py`
- `tests/test_hadoop_sudo_wire.py`
- `tests/test_capacity_unit_js.py`

- [ ] **Step 2: Run version + collect smoke**

Run:

```powershell
pytest tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py tests/test_capacity_unit_js.py tests/test_dell_report_collect.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py tests/test_capacity_unit_js.py
git commit -m "Bump version to 1.6.161 for Dell HPE display capacity rows."
```

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Display via `select_dell_capacity_summary` | Task 1 |
| Snapshot via `select_dell_array_snapshot_summary` only | Task 1 |
| Emit row when display-only (raw/CPG) | Task 1 |
| No raw/pool upsert | Task 1 |
| HP Forecast / Wkly via same `hp_rows` | Task 1 (no sheet code) |
| Forced-include blank | Task 1 (unchanged path) |
| `maybe_upsert` system-only | Task 1 (no change) |
| Version 1.6.161 | Task 2 |

No placeholders. Types match existing Dell collect helpers.
