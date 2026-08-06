# Capacity Report Per-Vendor Pool Toggles — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Capacity Report’s single “Include CPG / pools” View option with three display-only vendor checkboxes (IBM / HPE / Dell, default off) while always collecting pools on refresh and Excel / Dell Report export.

**Architecture:** Add a small `capacity_pool_family()` helper (ibm / hpe / dell / `""`) reused from Dell Report markers plus `dell_` profiles. Expose `pool_family` on card JSON. Capacity Report tags each `.site-block` with `data-pool-family` and toggles body classes `show-pools-ibm|hpe|dell`; CSS hides `.capacity-pools-wrap` unless the matching class is on. Drop master pool toggle; hardcode `include_pools=1` in page JS.

**Tech Stack:** Python (HealthServer / report HTML string), CSS/vanilla JS in `CAPACITY_REPORT_HTML`, pytest.

**Spec:** `docs/superpowers/specs/2026-08-06-capacity-pool-vendor-toggles-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.126`; bump to `1.6.127` when this feature ships (Task 3).
- Display / print only — never gate SSH or Excel / Dell Report on the new checkboxes.
- Capacity Report UI always requests `include_pools=1` (or omits the param relying on server default true).
- Defaults: all three vendor checkboxes **off**; ignore legacy `launchpad.capacityReport.showPools` (do not migrate it into the new keys).
- Pref keys: `launchpad.capacityReport.showPoolsIbm`, `…showPoolsHpe`, `…showPoolsDell` (`"1"` / `"0"`; missing ⇒ off).
- Windows PowerShell commits (here-string), no bash heredoc.
- Commit at each task’s commit step.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/capacity_pool_family.py` | Map `device_profile` (+ optional site name) → `"ibm"` \| `"hpe"` \| `"dell"` \| `""` |
| `tests/test_capacity_pool_family.py` | Unit tests for mapping |
| `launchpad/health_server.py` | Add `pool_family` on `HealthCard.to_api()` and list_cards error fallback |
| `launchpad/capacity_report.py` | Three toggles, CSS, JS prefs, `data-pool-family`, always `include_pools=1` |
| `tests/test_capacity_layers_ui.py` | Assert new toggles / prefs / always-on pools; drop master-toggle assertions |
| `launchpad/config.py` | `APP_VERSION` → `1.6.127` |

---

### Task 1: `capacity_pool_family` helper

**Files:**
- Create: `launchpad/capacity_pool_family.py`
- Create: `tests/test_capacity_pool_family.py`

**Interfaces:**
- Consumes: `launchpad.dell_report_family.dell_report_family_for_site` (returns `"ibm"` \| `"hp"` \| `None`)
- Produces: `capacity_pool_family(device_profile: str, *, site_name: str = "") -> str` returning `"ibm"` \| `"hpe"` \| `"dell"` \| `""`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_capacity_pool_family.py`:

```python
from launchpad.capacity_pool_family import capacity_pool_family


def test_ibm_flashsystem():
    assert capacity_pool_family("flashsystem_9200") == "ibm"


def test_hpe_maps_from_dell_report_hp():
    assert capacity_pool_family("hpe_primera_a670") == "hpe"
    assert capacity_pool_family("hp_3par_8200") == "hpe"


def test_dell_prefix():
    assert capacity_pool_family("dell_powermax_8000") == "dell"
    assert capacity_pool_family("dell_unity_650f") == "dell"


def test_unknown_empty():
    assert capacity_pool_family("netapp_aff") == ""
    assert capacity_pool_family("") == ""


def test_site_name_fallback_ibm():
    assert capacity_pool_family("", site_name="CHI FlashSystem 01") == "ibm"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capacity_pool_family.py -v`

Expected: FAIL (module / import not found)

- [ ] **Step 3: Implement helper**

Create `launchpad/capacity_pool_family.py`:

```python
"""Map a storage card to Capacity Report pool-display family."""

from __future__ import annotations

from launchpad.dell_report_family import dell_report_family_for_site


def capacity_pool_family(device_profile: str, *, site_name: str = "") -> str:
    """Return 'ibm' | 'hpe' | 'dell' | '' for Capacity Report pool visibility."""
    profile = (device_profile or "").strip()
    if profile.lower().startswith("dell_"):
        return "dell"
    family = dell_report_family_for_site(profile, site_name=site_name or "")
    if family == "ibm":
        return "ibm"
    if family == "hp":
        return "hpe"
    return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_capacity_pool_family.py -v`

Expected: PASS (all 5)

- [ ] **Step 5: Commit**

```powershell
git add launchpad/capacity_pool_family.py tests/test_capacity_pool_family.py
git commit -m @"
Add capacity_pool_family helper for IBM/HPE/Dell pool display tagging.
"@
```

---

### Task 2: Expose `pool_family` on card API

**Files:**
- Modify: `launchpad/health_server.py` (`HealthCard.to_api`, and the `list_cards` exception fallback dict)
- Test: extend `tests/test_capacity_pool_family.py` or add a thin API assertion in a small new test — prefer adding `tests/test_health_card_pool_family.py`

**Interfaces:**
- Consumes: `capacity_pool_family(device_profile, site_name=name) -> str`
- Produces: card JSON field `"pool_family": str` (`"ibm"` \| `"hpe"` \| `"dell"` \| `""`)

- [ ] **Step 1: Write the failing test**

Create `tests/test_health_card_pool_family.py`:

```python
from launchpad.health_server import HealthCard


def test_to_api_includes_pool_family_ibm():
    card = HealthCard(
        card_id=1,
        name="FS1",
        host="10.0.0.1",
        port=22,
        username="user",
        key_path="",
        device_profile="flashsystem_9200",
    )
    api = card.to_api()
    assert api["pool_family"] == "ibm"


def test_to_api_includes_pool_family_dell():
    card = HealthCard(
        card_id=2,
        name="PM1",
        host="10.0.0.2",
        port=22,
        username="user",
        key_path="",
        device_profile="dell_powermax_8000",
    )
    api = card.to_api()
    assert api["pool_family"] == "dell"
```

(If `HealthCard` constructor args differ, match an existing test that builds `HealthCard` in this repo.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_health_card_pool_family.py -v`

Expected: FAIL (`KeyError: 'pool_family'` or assertion)

- [ ] **Step 3: Wire `pool_family` into `to_api` and fallback**

In `launchpad/health_server.py`:

1. Add import (top of file with other launchpad imports):

```python
from launchpad.capacity_pool_family import capacity_pool_family
```

2. In `HealthCard.to_api()`, next to `dell_report_family`, add:

```python
"pool_family": capacity_pool_family(
    self.device_profile, site_name=self.name
),
```

3. In `list_cards` exception fallback dict, add:

```python
"pool_family": capacity_pool_family(
    card.device_profile, site_name=card.name
),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_health_card_pool_family.py tests/test_capacity_pool_family.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_health_card_pool_family.py
git commit -m @"
Expose pool_family on HealthCard API for Capacity Report vendor toggles.
"@
```

---

### Task 3: Capacity Report UI — three vendor toggles + always collect pools

**Files:**
- Modify: `launchpad/capacity_report.py`
- Modify: `tests/test_capacity_layers_ui.py`
- Modify: `launchpad/config.py` (`APP_VERSION` `"1.6.126"` → `"1.6.127"`)

**Interfaces:**
- Consumes: `card.pool_family` from `/api/cards` (`"ibm"` \| `"hpe"` \| `"dell"` \| `""`)
- Produces: View options checkboxes `show-pools-ibm-toggle`, `show-pools-hpe-toggle`, `show-pools-dell-toggle`; body classes `show-pools-ibm`, `show-pools-hpe`, `show-pools-dell`; site attribute `data-pool-family`; refresh/export URLs with `include_pools=1`

- [ ] **Step 1: Update failing UI tests first**

Replace pool-toggle assertions in `tests/test_capacity_layers_ui.py`:

```python
def test_capacity_report_has_pool_and_raw_toggles():
    html = CAPACITY_REPORT_HTML
    assert 'id="show-pools-toggle"' not in html
    assert "Include CPG / pools" not in html
    assert 'id="show-pools-ibm-toggle"' in html
    assert 'id="show-pools-hpe-toggle"' in html
    assert 'id="show-pools-dell-toggle"' in html
    assert "Show IBM pools" in html
    assert "Show HPE CPGs / pools" in html
    assert "Show Dell pools" in html
    assert "launchpad.capacityReport.showPoolsIbm" in html
    assert "launchpad.capacityReport.showPoolsHpe" in html
    assert "launchpad.capacityReport.showPoolsDell" in html
    assert "show-pools-ibm" in html
    assert "data-pool-family" in html
    assert 'id="show-raw-toggle"' in html
    assert "Show raw capacity" in html
    assert "launchpad.capacityReport.showRaw" in html
    assert "hide-raw-capacity" in html
    assert "include_pools=" in html
    assert "show_raw=" in html


def test_capacity_report_refresh_and_export_pass_include_pools():
    html = CAPACITY_REPORT_HTML
    assert "showPoolsToggle" not in html
    assert "include_pools=1" in html or "include_pools=${1" in html
    # Prefer exact always-on form used in implementation, e.g. include_pools=1
    assert html.count("include_pools=1") >= 2 or (
        "include_pools=1" in html and "/api/capacity-export" in html
    )
    assert "/api/capacity-export" in html
    assert "show_raw=" in html
```

Tighten the second test after implementing so it matches the exact JS strings (e.g. `` `&include_pools=1` `` appears for excel, dell, and refresh).

- [ ] **Step 2: Run UI tests — expect fail**

Run: `python -m pytest tests/test_capacity_layers_ui.py::test_capacity_report_has_pool_and_raw_toggles tests/test_capacity_layers_ui.py::test_capacity_report_refresh_and_export_pass_include_pools -v`

Expected: FAIL (old master toggle still present / new ids missing)

- [ ] **Step 3: Replace CSS for vendor visibility**

In `launchpad/capacity_report.py`, remove:

```css
body.hide-pool-storage .capacity-pools-wrap {
  display: none;
}
```

Add:

```css
.capacity-pools-wrap {
  display: none;
}
body.show-pools-ibm .site-block[data-pool-family="ibm"] .capacity-pools-wrap,
body.show-pools-hpe .site-block[data-pool-family="hpe"] .capacity-pools-wrap,
body.show-pools-dell .site-block[data-pool-family="dell"] .capacity-pools-wrap {
  display: block;
}
```

Keep the existing `.capacity-pools-wrap { margin-top: 8px; }` rule by merging `margin-top` into the default (hidden) rule or a second rule that still applies when shown — e.g. keep margin on `.capacity-pools-wrap` and only toggle `display`.

Also remove any other references to `hide-pool-storage`.

- [ ] **Step 4: Replace View options HTML**

Replace the master pools label with:

```html
<label class="toggle-row" for="show-pools-ibm-toggle" title="Show IBM mdiskgrp / pool blocks on this page and print.">
  <input type="checkbox" id="show-pools-ibm-toggle">
  Show IBM pools
</label>
<label class="toggle-row" for="show-pools-hpe-toggle" title="Show HPE CPG / pool blocks on this page and print.">
  <input type="checkbox" id="show-pools-hpe-toggle">
  Show HPE CPGs / pools
</label>
<label class="toggle-row" for="show-pools-dell-toggle" title="Show Dell pool blocks on this page and print.">
  <input type="checkbox" id="show-pools-dell-toggle">
  Show Dell pools
</label>
```

(No `checked` attribute — default off.)

- [ ] **Step 5: Update JS — prefs, apply, init, renderSite, include_pools**

1. Replace `showPoolsToggle` / `POOLS_PREF_KEY` with:

```javascript
const showPoolsIbmToggle = document.getElementById("show-pools-ibm-toggle");
const showPoolsHpeToggle = document.getElementById("show-pools-hpe-toggle");
const showPoolsDellToggle = document.getElementById("show-pools-dell-toggle");
const POOLS_IBM_PREF_KEY = "launchpad.capacityReport.showPoolsIbm";
const POOLS_HPE_PREF_KEY = "launchpad.capacityReport.showPoolsHpe";
const POOLS_DELL_PREF_KEY = "launchpad.capacityReport.showPoolsDell";
```

2. Replace `applyPoolStorageVisibility` / `initPoolStorageToggle` with:

```javascript
function applyVendorPoolVisibility() {
  const ibm = showPoolsIbmToggle ? showPoolsIbmToggle.checked : false;
  const hpe = showPoolsHpeToggle ? showPoolsHpeToggle.checked : false;
  const dell = showPoolsDellToggle ? showPoolsDellToggle.checked : false;
  document.body.classList.toggle("show-pools-ibm", ibm);
  document.body.classList.toggle("show-pools-hpe", hpe);
  document.body.classList.toggle("show-pools-dell", dell);
  try {
    localStorage.setItem(POOLS_IBM_PREF_KEY, ibm ? "1" : "0");
    localStorage.setItem(POOLS_HPE_PREF_KEY, hpe ? "1" : "0");
    localStorage.setItem(POOLS_DELL_PREF_KEY, dell ? "1" : "0");
  } catch (_err) {
    /* ignore storage errors */
  }
  updateViewOptionsButton();
}

function initVendorPoolToggles() {
  const load = (key) => {
    try {
      return localStorage.getItem(key) === "1";
    } catch (_err) {
      return false;
    }
  };
  if (showPoolsIbmToggle) showPoolsIbmToggle.checked = load(POOLS_IBM_PREF_KEY);
  if (showPoolsHpeToggle) showPoolsHpeToggle.checked = load(POOLS_HPE_PREF_KEY);
  if (showPoolsDellToggle) showPoolsDellToggle.checked = load(POOLS_DELL_PREF_KEY);
  applyVendorPoolVisibility();
  [showPoolsIbmToggle, showPoolsHpeToggle, showPoolsDellToggle].forEach((el) => {
    if (el) el.addEventListener("change", applyVendorPoolVisibility);
  });
}
```

3. Call `initVendorPoolToggles()` where `initPoolStorageToggle()` was called.

4. In `renderSite`, set family on the section:

```javascript
const poolFamily = String(card.pool_family || "").toLowerCase();
// ...
<section class="site-block..." data-id="${card.id}" data-pool-family="${escapeHtml(poolFamily)}">
```

5. In `downloadExcel`, Dell Report export, and per-site / refresh-all capacity refresh URL builders: remove `showPoolsToggle` / `includePools` variables; hardcode `include_pools=1`, e.g.:

```javascript
`&include_pools=1` +
```

and

```javascript
`/api/refresh/${cardId}?focus=capacity&include_pools=1`,
```

Search the HTML string for `showPoolsToggle`, `POOLS_PREF_KEY`, `includePools`, `hide-pool-storage`, and `initPoolStorageToggle` — none should remain.

- [ ] **Step 6: Bump version**

In `launchpad/config.py`:

```python
APP_VERSION = "1.6.127"
```

- [ ] **Step 7: Run tests**

Run:

```powershell
python -m pytest tests/test_capacity_layers_ui.py tests/test_capacity_pool_family.py tests/test_health_card_pool_family.py -q
```

Expected: PASS

Also grep the report HTML for leftovers:

```powershell
python -c "from launchpad.capacity_report import CAPACITY_REPORT_HTML as h; assert 'showPoolsToggle' not in h; assert 'Include CPG / pools' not in h; assert h.count('include_pools=1') >= 2; print('ok')"
```

Expected: `ok`

- [ ] **Step 8: Commit**

```powershell
git add launchpad/capacity_report.py launchpad/config.py tests/test_capacity_layers_ui.py
git commit -m @"
Add per-vendor Capacity Report pool display toggles (1.6.127).
"@
```

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Three View options checkboxes; master removed | Task 3 |
| Defaults off; localStorage keys | Task 3 |
| Display/print via CSS + `data-pool-family` | Task 3 |
| Always `include_pools=1` on refresh/export | Task 3 |
| Vendor mapping ibm/hpe/dell/`""` | Task 1 |
| Expose family without duplicating markers in JS | Task 2 |
| Unknown sites stay hidden | Task 3 CSS (no body class match) |
| Ignore legacy `showPools` key | Task 3 (not read) |
| Tests updated; version bump | Task 3 |
| No Site Lookup / parse changes | — out of scope |

**Placeholder scan:** none.  
**Type consistency:** `pool_family` string values `"ibm"` \| `"hpe"` \| `"dell"` \| `""` match helper, API, and `data-pool-family`.
