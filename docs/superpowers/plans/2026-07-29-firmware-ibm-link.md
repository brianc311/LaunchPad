# Firmware Tab IBM Upgrade Matrix Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Firmware-panel hint link to IBM’s FlashSystem software upgrade matrix and bump LaunchPad to 1.6.77.

**Architecture:** Static HTML in `SYSTEM_CONNECTIVITY_HTML` under the Firmware heading: keep the existing catalog hint, add a second `<p class="hint">` with an `<a>` to the locked IBM URL (`target="_blank"` + `rel="noopener noreferrer"`). No collector, Admin, or export changes.

**Tech Stack:** Python string HTML page, pytest.

**Spec:** `docs/superpowers/specs/2026-07-29-firmware-ibm-link-design.md`

## Global Constraints

- **Worktree:** `.worktrees/firmware-ibm-link` on `feature/firmware-ibm-link` from `feature/contingency-groups` tip (include design commit `567fe37` or later)
- Link text exactly: `IBM FlashSystem software upgrade matrix`
- URL exactly: `https://www.ibm.com/support/pages/node/5692850`
- Firmware panel only; no Excel/CSV/Admin/collector changes
- Bump `APP_VERSION` to **1.6.77**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\firmware-ibm-link`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/system_connectivity_page.py` | Firmware panel hint + IBM link HTML |
| `launchpad/config.py` | `APP_VERSION = "1.6.77"` |
| `tests/test_system_connectivity_page.py` | Assert URL + link attributes/text in Firmware HTML |
| `tests/test_system_connectivity_version.py` | Version `1.6.77` |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git worktree add .worktrees/firmware-ibm-link -b feature/firmware-ibm-link feature/contingency-groups
cd .worktrees\firmware-ibm-link
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-29-firmware-ibm-link-design.md
```

Expected: tip `1.6.76` (or later), spec `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Failing test for IBM link in Firmware HTML (TDD)

**Files:**
- Modify: `tests/test_system_connectivity_page.py`

**Interfaces:**
- Consumes: `SYSTEM_CONNECTIVITY_HTML` from `launchpad.system_connectivity_page`
- Produces: failing assertion until Task 2 adds the link

- [ ] **Step 1: Write the failing test**

Add (or extend an existing Firmware panel test):

```python
def test_firmware_panel_includes_ibm_upgrade_matrix_link():
    from launchpad.system_connectivity_page import SYSTEM_CONNECTIVITY_HTML

    html = SYSTEM_CONNECTIVITY_HTML
    assert 'id="sc-panel-firmware"' in html
    assert 'href="https://www.ibm.com/support/pages/node/5692850"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "IBM FlashSystem software upgrade matrix" in html
```

If `target="_blank"` / `rel=` might match other links later, prefer asserting a single contiguous snippet:

```python
    assert (
        '<a href="https://www.ibm.com/support/pages/node/5692850" '
        'target="_blank" rel="noopener noreferrer">'
        "IBM FlashSystem software upgrade matrix</a>"
    ) in html
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
python -m pytest tests/test_system_connectivity_page.py::test_firmware_panel_includes_ibm_upgrade_matrix_link -v
```

Expected: FAIL (URL / link text missing).

- [ ] **Step 3: Commit test only**

```powershell
git add tests/test_system_connectivity_page.py
git commit -m "Add failing test for Firmware IBM upgrade matrix link."
```

---

### Task 2: Add Firmware hint link

**Files:**
- Modify: `launchpad/system_connectivity_page.py` (Firmware panel block near `id="sc-panel-firmware"`)

**Interfaces:**
- Produces: static HTML matching the contiguous `<a>` snippet from Task 1

- [ ] **Step 1: Insert second hint under Firmware heading**

Locate:

```html
    <div class="section" id="sc-panel-firmware" data-panel="firmware" hidden>
      <h2>Firmware</h2>
      <p class="hint">Versions behind uses the Admin Firmware catalog for this device profile. If Current is not in the catalog, behind shows unknown.</p>
```

Immediately after that existing hint paragraph, add:

```html
      <p class="hint"><a href="https://www.ibm.com/support/pages/node/5692850" target="_blank" rel="noopener noreferrer">IBM FlashSystem software upgrade matrix</a></p>
```

Do not change collectors, tabs list, Excel, or other panels.

- [ ] **Step 2: Run tests**

```powershell
python -m pytest tests/test_system_connectivity_page.py::test_firmware_panel_includes_ibm_upgrade_matrix_link tests/test_system_connectivity_page.py -q --tb=short
```

Expected: PASS (including the new test).

- [ ] **Step 3: Commit**

```powershell
git add launchpad/system_connectivity_page.py
git commit -m "Add IBM FlashSystem upgrade matrix link on Firmware tab."
```

---

### Task 3: Version bump to 1.6.77

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py`

**Interfaces:**
- Produces: `APP_VERSION == "1.6.77"`

- [ ] **Step 1: Update version assertion to fail first (optional TDD)**

In `tests/test_system_connectivity_version.py`:

```python
from launchpad.config import APP_VERSION


def test_app_version_is_1_6_77():
    assert APP_VERSION == "1.6.77"
```

(or change the existing assert from `1.6.76` to `1.6.77`)

- [ ] **Step 2: Run to confirm fail, then bump config**

```powershell
python -m pytest tests/test_system_connectivity_version.py -v
```

Expected: FAIL until `launchpad/config.py` has:

```python
APP_VERSION = "1.6.77"
```

- [ ] **Step 3: Re-run related tests**

```powershell
python -m pytest tests/test_system_connectivity_version.py tests/test_system_connectivity_page.py tests/test_system_connectivity_nav.py -q --tb=short
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py
git commit -m "Bump LaunchPad to 1.6.77 for Firmware IBM upgrade matrix link."
```

---

### Task 4: Final verification

**Files:** none (verify only)

- [ ] **Step 1: Full related suite**

```powershell
python -m pytest tests/test_system_connectivity_page.py tests/test_system_connectivity_version.py tests/test_system_connectivity_nav.py -q --tb=short
```

Expected: PASS.

- [ ] **Step 2: Confirm HTML snippet once**

```powershell
python -c "from launchpad.system_connectivity_page import SYSTEM_CONNECTIVITY_HTML as h; assert '5692850' in h; print('ok', __import__('launchpad.config', fromlist=['APP_VERSION']).APP_VERSION)"
```

Expected: `ok 1.6.77`.

- [ ] **Step 3: No extra commit unless fixes needed**

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Firmware-only hint link | 2 |
| Exact link text + URL + `target`/`rel` | 1–2 |
| Keep existing catalog hint | 2 |
| No collectors/Admin/export | Global + 2 |
| Version 1.6.77 | 3 |
| Page/version tests | 1, 3 |
