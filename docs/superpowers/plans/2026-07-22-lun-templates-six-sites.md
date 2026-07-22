# Six Missing LUN Builder Site Templates — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add six built-in LUN Builder templates (Perrysburg, Moreno Valley, Nazareth, Valparaiso, Waxahachie, Woodland Hills) seeded from Storage Site Lookup HTML — blank WWPNs, one `exact_name` LUN per mapped volume — without duplicating existing templates.

**Architecture:** Port `exact_name` support into tip `lun_builder_data.py` (already on Anderson). Keep large inventory seeds in `launchpad/lun_templates_six_sites.py` and append them from `seed_lun_builder_templates()`. Implementers extract hosts/volumes/maps from the canonical Downloads HTML files during Task 2 (do not paste multi-hundred volume tables into this plan).

**Tech Stack:** Python seed data, existing `_lun_batch` / `normalize_build` / `expand_lun_batch`, pytest.

**Spec:** `docs/superpowers/specs/2026-07-22-lun-templates-six-sites-design.md`

## Global Constraints

- **Base branch:** `feature/contingency-groups` tip (includes this design commit). Do **not** overwrite Hartford / Jupiter / Pendergrass / Mount Vernon / Windsor. Anderson is optional if already merged; this work does not require it beyond copying the `exact_name` pattern.
- Six templates only — ids and defaults **exactly** as in the spec table
- Blank `wwpn1` / `wwpn2` on every new host row; `type=Generic`
- One LUN row per non-snap mapped volume: `exact_name=True`, `count=1`
- Skip snap-like volume names (`*_snap` / `*_Snap*` — reuse Sync Inventory heuristic if `inventory_sync.is_flashcopy_target_name` exists on tip; otherwise copy the same regex)
- Canonical HTML sources (no `_1`/`_2` suffix) under `C:\Users\BrianColley\Downloads\`
- Bump `APP_VERSION` to next patch after tip (if tip is `1.6.41`, use `1.6.42` unless parallel PRs already claimed higher — prefer `1.6.45` if Sync=`1.6.43` and Site Lookup=`1.6.44` are expected to land first; **confirm tip version at Task 0** and pick unused next patch)
- Commit at each task’s commit step

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/lun_builder_data.py` | `exact_name` on normalize / `_lun_batch` / `expand_lun_batch`; import + append six templates |
| `launchpad/lun_templates_six_sites.py` | Build the six template dicts from transcribed inventory |
| `launchpad/config.py` | Version bump |
| `tests/test_lun_builder_data.py` | `len==5` → `11`; six-site contract tests |
| `tests/test_health_server_lun_builder.py` | API template id set includes six new ids |
| `tests/test_lun_templates_six_sites.py` | Optional focused file if `test_lun_builder_data.py` is too large |

---

### Task 0: Branch / worktree

**Files:** none (git only)

**Interfaces:**
- Consumes: `feature/contingency-groups` with six-sites design doc
- Produces: `feature/lun-templates-six-sites` worktree

- [ ] **Step 1: Create worktree**

```powershell
git fetch origin
git -C "C:\Users\BrianColley\LaunchPad" worktree add .worktrees/lun-templates-six-sites -b feature/lun-templates-six-sites feature/contingency-groups
cd C:\Users\BrianColley\LaunchPad\.worktrees\lun-templates-six-sites
```

- [ ] **Step 2: Confirm baseline**

```powershell
python -c "from launchpad.config import APP_VERSION; from launchpad.lun_builder_data import seed_lun_builder_templates; print(APP_VERSION); print([t['id'] for t in seed_lun_builder_templates()])"
```

Expected: tip version printed; ids include the five existing templates (`template-hartford-ct` … `template-windsor-wi`); **no** six new ids yet.

Record chosen next `APP_VERSION` in the progress ledger (e.g. `1.6.42` or `1.6.45`).

- [ ] **Step 3: No commit**

---

### Task 1: `exact_name` plumbing (required on tip)

**Files:**
- Modify: `launchpad/lun_builder_data.py` (`normalize_lun` / `_lun_batch` / `expand_lun_batch`)
- Modify: `tests/test_lun_builder_data.py` (add exact_name expand test)

**Interfaces:**
- Consumes: existing expand helpers
- Produces: `_lun_batch(..., exact_name: bool = False)` stores `"exact_name"`; `normalize_*` preserves it; `expand_lun_batch` when `exact_name` → single volume name = `purpose` (or dedicated name field) with `count=1` semantics matching Anderson

- [ ] **Step 1: Write failing test**

```python
def test_exact_name_expand_uses_purpose_as_volume_name():
    from launchpad.lun_builder_data import expand_lun_batch
    rows = expand_lun_batch(
        {
            "purpose": "WOO_ESX_DataStore_1",
            "count": 1,
            "size": "1TB",
            "shared": True,
            "host_names": ["a", "b"],
            "exact_name": True,
            "name_prefix": "",
            "storage_profile": "flashsystem_5200",
            "pool_or_cpg": "WOO_Pool1",
            "card_hint": "Woodland Hills, CA",
            "scsi_or_lun_id": "0",
            "cluster": "",
        }
    )
    assert len(rows) == 1
    assert rows[0]["name"] == "WOO_ESX_DataStore_1"
```

If tip already expands purpose-as-name for `count==1` without `exact_name`, still add the flag and assert normalize round-trips `exact_name=True` (copy Anderson behavior: when `exact_name`, do not apply `name_prefix` stem rewriting).

- [ ] **Step 2: Run — expect FAIL** (or adjust if expand already matches; then test normalize persistence)

```powershell
pytest tests/test_lun_builder_data.py::test_exact_name_expand_uses_purpose_as_volume_name -v
```

- [ ] **Step 3: Implement** — mirror Anderson:

```python
# _lun_batch: add exact_name: bool = False → key in returned dict
# normalize_lun (or equivalent): "exact_name": _as_bool(raw.get("exact_name"))
# expand_lun_batch: if _as_bool(lun.get("exact_name")): name = purpose (count forced to 1); skip prefix-based base
```

Read Anderson worktree `launchpad/lun_builder_data.py` around `exact_name` for the exact expand branch if unsure.

- [ ] **Step 4: Tests PASS** for the new test + existing lun_builder_data suite green for prior templates

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder_data.py tests/test_lun_builder_data.py
git commit -m "Add exact_name LUN batch support for site templates."
```

---

### Task 2: Six-site inventory module + contract tests (TDD shell)

**Files:**
- Create: `launchpad/lun_templates_six_sites.py`
- Create: `tests/test_lun_templates_six_sites.py`
- Modify: `launchpad/lun_builder_data.py` (`seed_lun_builder_templates` append)
- Modify: `tests/test_lun_builder_data.py` (`len(templates) == 11`)
- Modify: `tests/test_health_server_lun_builder.py` (id set)

**Interfaces:**
- Consumes: `_lun_batch` with `exact_name`, Generic blank-WWPN host helper
- Produces: `build_six_site_templates() -> list[dict]` with the six ids from the spec

**HTML sources (read-only at implement time):**

| Id | File |
|----|------|
| `template-perrysburg-oh` | `C:\Users\BrianColley\Downloads\storage_site_lookup_perrysburg.html` |
| `template-moreno-valley-ca` | `...\storage_site_lookup_morenovalley.html` |
| `template-nazareth-pa` | `...\storage_site_lookup_nazareth.html` |
| `template-valparaiso-in` | `...\storage_site_lookup_valparaiso.html` |
| `template-waxahachie-tx` | `...\storage_site_lookup_waxahachie.html` |
| `template-woodland-hills-ca` | `...\storage_site_lookup_woodlandhills.html` |

**Extraction rules (implementer must follow):**

1. Parse `SITE_DATA` / `siteData` / embedded site object for the primary site key.
2. Hosts: every host `name` → Generic row, blank WWPNs.
3. Volumes + maps: for each mapped volume name, skip if snap heuristic matches; else one `_lun_batch(purpose=volume_name, count=1, size=..., shared=(len(hosts)>=2), host_names=..., exact_name=True, name_prefix="", storage_profile=..., pool_or_cpg=..., card_hint=..., scsi_or_lun_id=consistent_or_blank)`.
4. Defaults per spec table (profile / pool / card hint).
5. Notes: mention HTML seed, blank WWPNs, Sync Inventory can refresh.

- [ ] **Step 1: Write failing contract tests**

```python
# tests/test_lun_templates_six_sites.py
from launchpad.lun_builder_data import seed_lun_builder_templates, normalize_build, expand_lun_batch

EXPECTED = {
    "template-perrysburg-oh": ("Perrysburg, OH", "flashsystem_7200", "G3_PER_Pool", "Perrysburg, OH"),
    "template-moreno-valley-ca": ("Moreno Valley, CA", "flashsystem_5200", "MOR_G3_Pool", "Moreno Valley, CA"),
    "template-nazareth-pa": ("Nazareth, PA", "flashsystem_5200", "V5kNAZ_Pool1", "Nazareth, PA"),
    "template-valparaiso-in": ("Valparaiso, IN", "flashsystem_7300", "VAL_POOL", "Valparaiso, IN"),
    "template-waxahachie-tx": ("Waxahachie, TX", "flashsystem_5200", "Wax_Pool1", "Waxahachie, TX"),
    "template-woodland-hills-ca": ("Woodland Hills, CA", "flashsystem_5200", "WOO_Pool1", "Woodland Hills, CA"),
}

def test_six_site_templates_present_with_defaults():
    by_id = {t["id"]: t for t in seed_lun_builder_templates()}
    for tid, (location, profile, pool, hint) in EXPECTED.items():
        t = by_id[tid]
        assert t["location"] == location
        assert t["is_template"] is True
        assert t["default_storage_profile"] == profile
        assert t["default_pool_or_cpg"] == pool
        assert t["default_card_hint"] == hint
        assert len(t["hosts"]) >= 1
        assert len(t["luns"]) >= 1
        assert all(not (h.get("wwpn1") or h.get("wwpn2")) for h in t["hosts"])
        assert normalize_build(t)["is_template"] is True

def test_six_site_luns_are_exact_name_singletons():
    by_id = {t["id"]: t for t in seed_lun_builder_templates()}
    for tid in EXPECTED:
        for lun in by_id[tid]["luns"]:
            assert lun.get("exact_name") is True
            assert int(lun.get("count") or 1) == 1
            rows = expand_lun_batch(lun)
            assert len(rows) == 1
            assert rows[0]["name"] == lun["purpose"]
```

Also update `test_lun_builder_data.py`:

```python
assert len(templates) == 11
```

And health-server expected template id frozenset/list to include the six new ids.

- [ ] **Step 2: Run — expect FAIL** (module / ids missing)

```powershell
pytest tests/test_lun_templates_six_sites.py tests/test_lun_builder_data.py::test_hartford_template_identity -v
```

- [ ] **Step 3: Implement `lun_templates_six_sites.py`**

Suggested shape:

```python
def _generic_host(name: str) -> dict: ...  # blank WWPNs

def _exact_lun(volume_name, size, hosts, *, shared, scsi, profile, pool, hint) -> dict:
    return _lun_batch(
        volume_name, 1, size, shared, hosts, "",
        name_prefix="", exact_name=True,
        storage_profile=profile, pool_or_cpg=pool, card_hint=hint,
        # set scsi_or_lun_id after if _lun_batch does not take it — mutate dict
    )

def build_six_site_templates() -> list[dict]:
    return [perrysburg(), moreno(), nazareth(), valparaiso(), waxahachie(), woodland()]
```

Import `_lun_batch` from `lun_builder_data` **carefully** to avoid circular imports: prefer defining `_generic_host` / calling a small shared helper in `lun_templates_six_sites.py` that duplicates the Generic host dict (YAGNI: duplicate 15-line host dict rather than circular import). Or move `_lun_batch` usage by importing only after functions are defined — if circular, inline a local `_exact_lun_batch` dict literal matching `_lun_batch` keys.

Wire:

```python
# seed_lun_builder_templates() return [...existing five..., *build_six_site_templates()]
```

- [ ] **Step 4: Run full focused tests — PASS**

```powershell
pytest tests/test_lun_templates_six_sites.py tests/test_lun_builder_data.py tests/test_health_server_lun_builder.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_templates_six_sites.py launchpad/lun_builder_data.py tests/test_lun_templates_six_sites.py tests/test_lun_builder_data.py tests/test_health_server_lun_builder.py
git commit -m "Add six FlashSystem LUN Builder site templates from lookup HTML."
```

---

### Task 3: Version bump + smoke

**Files:**
- Modify: `launchpad/config.py`

- [ ] **Step 1: Set `APP_VERSION`** to the version recorded in Task 0

- [ ] **Step 2: Smoke**

```powershell
python -c "from launchpad.config import APP_VERSION; from launchpad.lun_builder_data import seed_lun_builder_templates; ids=[t['id'] for t in seed_lun_builder_templates()]; print(APP_VERSION, len(ids)); assert len(ids)==11"
pytest tests/test_lun_templates_six_sites.py tests/test_lun_builder_data.py -q
```

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version for six LUN Builder site templates."
```

---

## Self-review (plan vs spec)

| Spec item | Task |
|-----------|------|
| Six sites only / no overwrite of existing | 2 |
| Blank WWPNs | 2 |
| exact_name per-volume LUNs | 1, 2 |
| Defaults table | 2 |
| Snap skip | 2 extraction rules |
| Tests | 1–3 |
| Version bump | 3 |
| No CG / Site Lookup / Sync changes | honored |

No TBD placeholders. Inventory volume lists are intentionally extracted at implement time from the named HTML files (too large to embed in the plan).
