# LUN Builder Hartford Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a built-in Hartford, CT template to LUN Builder so operators can pick the Connecticut hosts + SPS/MFS/BT LUN plan instead of starting from a blank build.

**Architecture:** `seed_lun_builder_templates()` returns read-only template builds (`is_template: true`, ids `template-*`). `GET /api/lun-builds` returns saved `builds` plus `templates`. UI picker groups Templates vs Saved builds; Save on a template becomes Save as new; Delete is disabled for templates. Templates are never stored in `lun_builds` settings.

**Tech Stack:** Existing LUN Builder page/data/API patterns, pytest.

**Spec:** `docs/superpowers/specs/2026-07-18-lun-builder-hartford-template-design.md`

## Global Constraints

- Template id: `template-hartford-ct`
- Template name: `Hartford, CT (Template)`
- Approach B: built-in catalog; not “seed only when empty”
- `storage_profile` and `pool_or_cpg` blank on all seeded LUN rows
- Hosts + full SPS/MFS/BT LUN plan
- Templates not written to `lun_builds` unless Save as new
- Upsert/delete reject `template-*` / `is_template` ids
- Bump `APP_VERSION` to `1.6.23` in the final task
- Do not commit unless the user asked for commits in this session
- Do not change Preview/Run safety rules

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/lun_builder_data.py` | `seed_lun_builder_templates()`, preserve `is_template` in normalize |
| `tests/test_lun_builder_data.py` | Seed content contracts |
| `launchpad/health_server.py` | GET returns templates; reject template mutate |
| `tests/test_health_server_lun_builder.py` | API contracts |
| `launchpad/lun_builder.py` | Picker groups, banner, Save/Delete guards |
| `tests/test_lun_builder_page.py` | UI contract strings |
| `launchpad/config.py` | `1.6.23` |

**Host/WWPN source for Task 1:** Transcribe from the operator Connecticut sheet screenshot(s) already used in design (6 LPARs × 4 paths). If `Connecticut_NewHosts_WWNS.xlsx` is readable in the workspace during implementation, prefer importing it; otherwise screenshot transcription is authoritative. Lock counts and a few golden WWPN rows in tests.

---

### Task 1: Seed Hartford template data

**Files:**
- Modify: `launchpad/lun_builder_data.py`
- Modify: `tests/test_lun_builder_data.py`

**Interfaces:**
- `seed_lun_builder_templates() -> list[dict]`
- Each template: `id`, `name`, `location`, `notes`, `hosts`, `luns`, `is_template: True`
- `normalize_build` must preserve `is_template` when present (default `False`)
- Helper ok: `_hartford_host(...)`, `_lun_batch(...)` for readability

**LUN rows (exact):**
- SPS: for each of `pconsps3`, `pconsps4` → `{purpose:"root", count:3, size:"50GB", shared:False, host_names:[lpar], cluster:"SPS", storage_profile:"", pool_or_cpg:""}`
- SPS shared on both: ora1vg 7×100GB; archvg 2×200GB; sps1redovg1 1×100GB; sps1redovg2 1×100GB; caavg_private 1×10GB (`shared:True`)
- MFS: same pattern for `pconmfs3`/`pconmfs4` with mfs1redovg1/2; archvg **1×200GB**
- BT: same for `pconbt3`/`pconbt4` with btfs1redovg1, btfs2redovg2; ora1vg **14×100GB**; archvg **2×100GB**

**Host rows:** 24 rows (6 LPARs × 4 paths). Include full Hartford columns.

- [ ] **Step 1: Write failing tests**

```python
from launchpad.lun_builder_data import seed_lun_builder_templates


def test_hartford_template_identity():
    templates = seed_lun_builder_templates()
    assert len(templates) == 1
    hartford = templates[0]
    assert hartford["id"] == "template-hartford-ct"
    assert hartford["name"] == "Hartford, CT (Template)"
    assert hartford["is_template"] is True
    assert hartford["location"] == "Hartford, CT"


def test_hartford_hosts_cover_six_lpars():
    hartford = seed_lun_builder_templates()[0]
    names = {h["lpar_name"] for h in hartford["hosts"]}
    assert names == {
        "pconsps3",
        "pconsps4",
        "pconmfs3",
        "pconmfs4",
        "pconbt3",
        "pconbt4",
    }
    assert len(hartford["hosts"]) == 24
    first = next(h for h in hartford["hosts"] if h["lpar_name"] == "pconsps3")
    assert first["wwpn1"].lower().startswith("c05076")
    assert first["remote_lpar"].startswith("pconvio")


def test_hartford_lun_batches_and_blank_profile_pool():
    hartford = seed_lun_builder_templates()[0]
    luns = hartford["luns"]
    assert len(luns) == 21  # 6 root batches + 15 shared batches
    assert all(not str(lun.get("storage_profile") or "").strip() for lun in luns)
    assert all(not str(lun.get("pool_or_cpg") or "").strip() for lun in luns)
    ora = [lun for lun in luns if lun["purpose"] == "ora1vg"]
    assert {lun["cluster"]: lun["count"] for lun in ora} == {
        "SPS": 7,
        "MFS": 7,
        "BT": 14,
    }
```

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
python -m pytest tests/test_lun_builder_data.py::test_hartford_template_identity tests/test_lun_builder_data.py::test_hartford_hosts_cover_six_lpars tests/test_lun_builder_data.py::test_hartford_lun_batches_and_blank_profile_pool -q
```

- [ ] **Step 3: Implement seed + normalize `is_template`; tests PASS**

- [ ] **Step 4: Commit only if user asked**

---

### Task 2: API returns templates; reject template mutate

**Files:**
- Modify: `launchpad/health_server.py`
- Modify: `tests/test_health_server_lun_builder.py`

**Behavior:**
- `GET /api/lun-builds` → `{ "builds": [...], "templates": seed_lun_builder_templates(), "persisted": bool }`
- `POST` with `build` whose `id` starts with `template-` or `is_template` true → 400 `"Cannot overwrite a built-in template; use Save as new."`
- `POST` with `delete_id` starting with `template-` → 400 `"Cannot delete a built-in template."`
- `set_lun_builds` / upsert path should also strip or reject any template ids sneaking into the saved list

- [ ] **Step 1: Failing API tests**

```python
def test_get_lun_builds_includes_templates(server_with_settings):
    # use existing HealthServer settings fixture pattern from this file
    payload = server_with_settings.get_lun_builds_payload()  # or HTTP GET helper already used
    # Prefer mirroring existing test style in test_health_server_lun_builder.py:
    # call server method or request handler as other tests do.
```

Implement tests in the same style as existing `test_health_server_lun_builder.py` GET/POST tests:

```python
def test_api_get_includes_hartford_template():
    # After constructing HealthServer with settings backend:
    # GET /api/lun-builds JSON has templates[0].id == "template-hartford-ct"
    # and builds does not contain that id by default


def test_api_rejects_delete_template():
    # POST {"delete_id": "template-hartford-ct"} → error status / message


def test_api_rejects_upsert_template_id():
    # POST {"build": {"id": "template-hartford-ct", "name": "X", ...}} → error
```

- [ ] **Step 2: Implement GET/templates + guards; tests PASS**

- [ ] **Step 3: Commit only if user asked**

---

### Task 3: UI picker + Save as new + version 1.6.23

**Files:**
- Modify: `launchpad/lun_builder.py`
- Modify: `tests/test_lun_builder_page.py`
- Modify: `launchpad/config.py` → `APP_VERSION = "1.6.23"`
- Optional: mark Hartford template design Status Implemented

**UI behavior:**
- Keep `templates = []` separate from `builds`
- On load: `builds = data.builds`; `templates = data.templates || []`
- Picker HTML:
  - `<optgroup label="Templates">` for each template
  - `<optgroup label="Saved builds">` for saved builds (or “New build” empty option when none)
- `activeBuild()`: find in builds first, else templates
- Banner `#template-banner` visible when active build `is_template`
- Copy: `Template — use Save as new to keep an editable copy.`
- `delete-btn.disabled` when template selected OR no id
- Save click: if template, call Save-as-new flow (strip `(Template)` from name, new id via `makeId`, `is_template: false`, POST upsert)
- Save as new: same stripping for template names
- Do not put templates into `localStorage` `launchpad.lunBuilds` (only saved builds)

- [ ] **Step 1: Page contract tests**

```python
def test_lun_builder_exposes_template_picker_ux():
    for text in (
        "Templates",
        "Saved builds",
        "template-banner",
        "Save as new",
        "is_template",
        "templates",
    ):
        assert text in LUN_BUILDER_HTML
```

- [ ] **Step 2: Implement UI + bump version**

```powershell
python -m pytest tests/test_lun_builder_data.py tests/test_lun_builder_page.py tests/test_health_server_lun_builder.py -q
python -c "from launchpad.config import APP_VERSION; assert APP_VERSION=='1.6.23'"
```

- [ ] **Step 3: Commit only if user asked**

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| `seed_lun_builder_templates` Hartford content | 1 |
| Blank profile/pool | 1 |
| GET returns templates | 2 |
| Reject template delete/overwrite | 2 |
| Picker Templates / Saved builds | 3 |
| Banner + Save as new + Delete disabled | 3 |
| Version 1.6.23 | 3 |

## Placeholder / consistency self-review

- Host WWPN transcription is Task 1 responsibility; tests lock structure + golden WWPN prefix.
- No Preview/Run changes.
- Commit steps optional per session rules.
