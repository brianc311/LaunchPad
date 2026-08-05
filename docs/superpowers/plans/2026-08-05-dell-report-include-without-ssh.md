# Dell Report Include-Without-SSH — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let operators check **Dell Report** on any IBM/HPE card so unreachable sites appear on Dell sheets with identity filled and capacity blank.

**Architecture:** Extend `dell_report_settings` with `include_card_ids`. Collect emits forced blank rows when include is set and capacity is missing. Export merges include IDs into the Dell card set even if Monitor is off. Card widget shows a Dell Report checkbox for IBM/HPE profiles only.

**Tech Stack:** Python, CustomTkinter card widget, existing Dell Report collect/export, pytest.

**Spec:** `docs/superpowers/specs/2026-08-05-dell-report-include-without-ssh-design.md`

## Global Constraints

- Branch: `feature/hpe-capacity-parse`
- App version: **1.6.121**
- Capacity for forced rows: **blank** (not zeros, not last snapshot)
- Do **not** upsert weekly snapshots for forced blank rows
- IBM/HPE profiles only (`dell_report_family` in `{ibm, hp}`)
- Windows PowerShell commits (here-string)

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/dell_report_settings.py` | Normalize/load/save `include_card_ids` |
| `launchpad/dell_report_export.py` | Forced blank rows in `collect_dell_report_rows` |
| `launchpad/health_server.py` | Merge include IDs into Dell export set; pass include set to collect |
| `launchpad/ui/card_widget.py` | Dell Report checkbox for IBM/HPE |
| `launchpad/ui/dashboard_view.py` | Wire toggle ↔ settings |
| `launchpad/config.py` | `APP_VERSION = "1.6.121"` |
| `tests/test_dell_report_*.py` | Settings + collect + export coverage |

---

### Task 1: Settings `include_card_ids` + collect forced blank rows

**Files:**
- Modify: `launchpad/dell_report_settings.py`
- Modify: `launchpad/dell_report_export.py` (`collect_dell_report_rows`)
- Modify: `tests/test_dell_report_settings.py`
- Modify: `tests/test_dell_report_collect.py`

**Interfaces:**
- Produces: `normalize_dell_report_settings` → adds `"include_card_ids": list[str]` (deduped string card ids)
- Produces: helpers `is_dell_report_include_card(settings, card_id) -> bool` (optional) or check `str(card_id) in settings["include_card_ids"]`
- Produces: `collect_dell_report_rows(..., include_card_ids: set[str] | list | None = None)`

- [ ] **Step 1: Failing settings tests**

```python
def test_normalize_include_card_ids():
    out = normalize_dell_report_settings(
        {"enabled": True, "include_card_ids": [12, "12", "34", "", None]}
    )
    assert out["include_card_ids"] == ["12", "34"]


def test_normalize_default_include_empty():
    assert normalize_dell_report_settings({})["include_card_ids"] == []
```

Update existing equality assertions to include `"include_card_ids": []`.

- [ ] **Step 2: Implement normalize for include_card_ids**

```python
def _normalize_include_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if item is None or item == "":
            continue
        key = str(item).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out
```

Merge into `normalize_dell_report_settings` return dict. Keep `card_overrides` as today.

- [ ] **Step 3: Failing collect test for forced blank**

```python
def test_collect_forced_include_blank_capacity_no_snapshot():
    sites = [
        {
            "card_id": 99,
            "name": "IBM - SVCPVCW1 - WAG1",
            "device_profile": "ibm_svc_2145",
            "capacity_summary": None,
            "raw_capacity_summary": None,
            "pools": [],
        }
    ]
    ibm, hp, store = collect_dell_report_rows(
        sites,
        snapshot_store={},
        include_pools=False,
        include_card_ids={"99"},
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )
    assert hp == []
    assert len(ibm) == 1
    row = ibm[0]
    assert row["facility"] == "Data center -WAG1"
    assert row["array_name"] == "IBM - SVCPVCW1 - WAG1"
    assert row["curr_usable_gib"] is None
    assert row["curr_used_gib"] is None
    assert row["curr_util"] is None
    assert row["weekly_growth"] is None
    assert "99" not in store  # no fake snapshot


def test_collect_skips_unreachable_without_include():
    sites = [{"card_id": 99, "name": "IBM - SVCPVCW1 - WAG1",
              "device_profile": "ibm_svc_2145",
              "capacity_summary": None, "raw_capacity_summary": None, "pools": []}]
    ibm, hp, store = collect_dell_report_rows(
        sites, snapshot_store={}, include_card_ids=set(), now=datetime(2026, 8, 5, tzinfo=timezone.utc)
    )
    assert ibm == [] and hp == [] and store == {}
```

- [ ] **Step 4: Implement forced blank path in collect**

After `select_dell_capacity_summary` fails / `total_bytes <= 0`:

```python
include_ids = {str(x) for x in (include_card_ids or [])}
...
if not summary or total_bytes <= 0:
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
    (ibm_rows if family == "ibm" else hp_rows).append(blank)
    continue
```

Do not upsert snapshot on this path. Ensure Excel writers already leave `None` blank (verify Report/Forecast writers).

- [ ] **Step 5: Run Task 1 tests — PASS**

`python -m pytest tests/test_dell_report_settings.py tests/test_dell_report_collect.py -q`

- [ ] **Step 6: Commit**

```powershell
git add launchpad/dell_report_settings.py launchpad/dell_report_export.py tests/test_dell_report_settings.py tests/test_dell_report_collect.py
git commit -m @"
Add Dell Report include_card_ids and forced blank collect rows.

"@
```

---

### Task 2: Export merges include IDs (ignore monitor for those cards)

**Files:**
- Modify: `launchpad/health_server.py` (`export_dell_report_excel_bytes`)
- Modify: `tests/test_dell_report_api.py` (or new focused test)

**Interfaces:**
- Consumes: `load_dell_report_settings` → `include_card_ids`
- After building monitored `included_ids`, union IBM/HPE card IDs that appear in `include_card_ids` (even if monitor off)
- Pass `include_card_ids` into `collect_dell_report_rows`
- For include-only cards: still attempt refresh; on failure/empty capacity, collect emits blank row

- [ ] **Step 1: Failing test** — export path includes monitor-off card when in include list

Prefer a unit-level test of the ID-merge helper if extracting one; else monkeypatch `export_dell_report_excel_bytes` internals:

```python
def test_dell_export_includes_forced_card_when_monitor_off(monkeypatch):
    # Register IBM card, monitor off, include_card_ids contains that id,
    # refresh returns empty capacity; assert workbook IBM Report has identity row.
```

If API test is heavy, extract:

```python
def merge_dell_export_card_ids(monitored_ids: list[int], include_card_ids: list[str], cards_by_id: dict) -> list[int]:
    ...
```

in `dell_report_export.py` or `health_server` and test that pure function.

- [ ] **Step 2: Implement merge + wire collect kwargs**

```python
settings = load_dell_report_settings(settings_view) if settings_view else normalize...({})
include_ids = settings.get("include_card_ids") or []
# after monitored filter:
for cid_str in include_ids:
    try:
        cid = int(cid_str)
    except ValueError:
        continue
    card = self._cards.get(cid)
    if card and dell_report_family(card.device_profile) in {"ibm", "hp"}:
        if cid not in ibm_hp_ids:
            ibm_hp_ids.append(cid)
```

Pass `include_card_ids=include_ids` to collect. Update API settings assertions for `include_card_ids: []`.

- [ ] **Step 3: Tests PASS + commit**

```powershell
git commit -m @"
Include Dell Report forced cards in export even when Monitor is off.

"@
```

---

### Task 3: Card widget + dashboard toggle UI

**Files:**
- Modify: `launchpad/ui/card_widget.py`
- Modify: `launchpad/ui/dashboard_view.py`
- Modify: `tests/test_capacity_report_dell_button.py` or new `tests/test_dell_report_card_include.py` (source asserts)

**Interfaces:**
- `CardWidget(..., dell_report_include: bool = False, on_dell_report_include_change=None)`
- Show CTkCheckBox **Dell Report** only when `dell_report_family(device_profile) in {"ibm","hp"}`
- Dashboard loads include set from `load_dell_report_settings`; on toggle, update `include_card_ids` and `save_dell_report_settings`

- [ ] **Step 1: Source/UI tests**

```python
def test_card_widget_has_dell_report_include_hook():
    source = Path("launchpad/ui/card_widget.py").read_text(encoding="utf-8")
    assert "Dell Report" in source
    assert "dell_report_include" in source or "on_dell_report_include" in source


def test_dashboard_wires_dell_report_include():
    source = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")
    assert "include_card_ids" in source
    assert "dell_report" in source.lower()
```

- [ ] **Step 2: Implement checkbox on card**

Place near Monitor switch. Label: `Dell Report`. Hint optional: `Include even without SSH`.

Only create widgets when family is ibm/hp.

- [ ] **Step 3: Dashboard wire-up**

On card build:

```python
settings = load_dell_report_settings(self.db)
include_ids = set(settings.get("include_card_ids") or [])
...
dell_report_include=(str(card.id) in include_ids),
on_dell_report_include_change=lambda enabled, cid=card.id: self._set_dell_report_include(cid, enabled),
```

```python
def _set_dell_report_include(self, card_id: int, enabled: bool) -> None:
    settings = load_dell_report_settings(self.db)
    ids = list(settings.get("include_card_ids") or [])
    key = str(card_id)
    if enabled and key not in ids:
        ids.append(key)
    if not enabled:
        ids = [x for x in ids if x != key]
    settings["include_card_ids"] = ids
    save_dell_report_settings(self.db, settings)
```

- [ ] **Step 4: Tests PASS + commit**

```powershell
git commit -m @"
Add per-card Dell Report include checkbox for IBM/HPE.

"@
```

---

### Task 4: Version 1.6.121 + regression

**Files:**
- Modify: `launchpad/config.py` → `APP_VERSION = "1.6.121"`
- Modify: spec status → Approved
- Run full Dell Report suite

- [ ] **Step 1: Bump version**

- [ ] **Step 2: Regression**

```powershell
python -m pytest tests/test_dell_report_export.py tests/test_dell_report_helpers.py tests/test_dell_report_api.py tests/test_dell_report_collect.py tests/test_dell_report_capacity.py tests/test_dell_report_identity.py tests/test_dell_report_settings.py tests/test_dell_report_snapshots.py tests/test_capacity_report_dell_button.py -q
```

Expected: all PASS

- [ ] **Step 3: Commit + push**

```powershell
git commit -m @"
Ship Dell Report include-without-SSH as 1.6.121.

"@
git push origin HEAD
```

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| include_card_ids persistence | 1, 3 |
| Forced blank capacity rows | 1 |
| No snapshot upsert for blanks | 1 |
| Identity from name/overrides | 1 |
| Export regardless of monitor | 2 |
| Card checkbox IBM/HPE only | 3 |
| Version 1.6.121 | 4 |
