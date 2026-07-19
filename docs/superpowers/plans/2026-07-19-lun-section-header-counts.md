# LUN Section Header Counts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show live Done progress in Hosts and LUN specs section headings as `Hosts (3/5 done)` and `LUN specs (2/4 done)`.

**Architecture:** Derived counts only — no new persisted fields. During `render()`, count `done` booleans on `build.hosts` / `build.luns` and set the `h2` text for each section. Existing LUN Plan summary bar is unchanged.

**Tech Stack:** Existing LUN Builder HTML/JS in `launchpad/lun_builder.py`, pytest page contracts.

**Spec:** `docs/superpowers/specs/2026-07-19-lun-section-header-counts-design.md`

## Global Constraints

- Format is always `(done/total done)`, including zeros: `Hosts (0/0 done)`
- Counts are derived from existing row `done` flags — do not add new build fields
- Do not change LUN Plan summary behavior
- Bump `APP_VERSION` to `1.6.35` in the final task
- Do not commit unless the user asked for commits in this session
- Keep Add host / Add LUN spec buttons in the section summaries

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/lun_builder.py` | Heading ids + `render()` updates for Hosts / LUN specs counts |
| `tests/test_lun_builder_page.py` | HTML/JS contract strings for heading ids and update helper |
| `launchpad/config.py` | `APP_VERSION = "1.6.35"` |

---

### Task 1: Section heading progress counts

**Files:**
- Modify: `launchpad/lun_builder.py`
- Test: `tests/test_lun_builder_page.py`

**Interfaces:**
- Consumes: existing `render()`, `build.hosts[].done`, `build.luns[].done`
- Produces: `id="hosts-heading"` and `id="luns-heading"` updated each render to `Hosts (N/M done)` / `LUN specs (N/M done)`

- [ ] **Step 1: Write the failing page-contract test**

Add to `tests/test_lun_builder_page.py`:

```python
def test_lun_builder_section_header_counts():
    for text in (
        'id="hosts-heading"',
        'id="luns-heading"',
        "Hosts (0/0 done)",
        "LUN specs (0/0 done)",
        "updateSectionHeadings",
    ):
        assert text in LUN_BUILDER_HTML
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lun_builder_page.py::test_lun_builder_section_header_counts -v`

Expected: FAIL because those strings are not in `LUN_BUILDER_HTML` yet

- [ ] **Step 3: Add heading ids in the HTML summaries**

In `launchpad/lun_builder.py`, change the Hosts and LUN specs summaries to:

```html
<summary class="section-head"><h2 id="hosts-heading">Hosts (0/0 done)</h2><button type="button" class="secondary" id="add-host-btn">Add host</button></summary>
```

```html
<summary class="section-head"><h2 id="luns-heading">LUN specs (0/0 done)</h2><button type="button" class="secondary" id="add-lun-btn">Add LUN spec</button></summary>
```

Leave LUN Plan heading unchanged (`<h2>LUN Plan</h2>`).

- [ ] **Step 4: Add `updateSectionHeadings` and call it from `render()`**

Inside the page `<script>` in `launchpad/lun_builder.py`, add this function near `renderPlanSummary` (or just above `render`):

```javascript
function updateSectionHeadings(build) {
  const hosts = build.hosts || [];
  const luns = build.luns || [];
  const hostsDone = hosts.filter((host) => host.done).length;
  const lunsDone = luns.filter((lun) => lun.done).length;
  const hostsHeading = document.getElementById("hosts-heading");
  const lunsHeading = document.getElementById("luns-heading");
  if (hostsHeading) hostsHeading.textContent = `Hosts (${hostsDone}/${hosts.length} done)`;
  if (lunsHeading) lunsHeading.textContent = `LUN specs (${lunsDone}/${luns.length} done)`;
}
```

At the end of `render()`, after `renderPlanTable(build);` (or alongside other render side-effects), call:

```javascript
updateSectionHeadings(build);
```

Use `textContent` (not `innerHTML`) so titles stay plain text.

- [ ] **Step 5: Run page tests**

Run: `pytest tests/test_lun_builder_page.py -v`

Expected: PASS, including `test_lun_builder_section_header_counts` and existing contracts that still match substring `"Hosts"` / `"LUN specs"`

- [ ] **Step 6: Commit (only if the user asked)**

```bash
git add tests/test_lun_builder_page.py launchpad/lun_builder.py
git commit -m "Show Done progress on Hosts and LUN specs headings."
```

---

### Task 2: Version bump and regression

**Files:**
- Modify: `launchpad/config.py`

**Interfaces:**
- Consumes: Task 1 heading behavior
- Produces: `APP_VERSION = "1.6.35"`

- [ ] **Step 1: Bump version**

In `launchpad/config.py`:

```python
APP_VERSION = "1.6.35"
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests`

Expected: all tests PASS (136 or current total)

- [ ] **Step 3: Commit (only if the user asked)**

```bash
git add launchpad/config.py
git commit -m "Bump version to 1.6.35 for section header counts."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| `Hosts (N/M done)` / `LUN specs (N/M done)` | Task 1 |
| Zero state `(0/0 done)` | Task 1 |
| Live update on add/remove/Done | Task 1 (`render` path) |
| No new persisted fields | Task 1 (derived only) |
| LUN Plan summary unchanged | Task 1 (no edits there) |
| Version `1.6.35` | Task 2 |
