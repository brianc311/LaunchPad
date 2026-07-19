# LUN Done Auto-Save Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist Done checkbox state (LUN Plan, Hosts/LUN specs, command checklist) so a page refresh keeps green rows and checkmarks without a separate Save click.

**Architecture:** Add a shared `persistCompletionState()` helper that always calls `saveLocal()` and, when persistence is unlocked and the build has a real id, schedules a debounced `POST /api/lun-builds` save. Wire that helper into the three Done change paths. Keep existing completion sync and UI unchanged.

**Tech Stack:** Existing LUN Builder HTML/JS in `launchpad/lun_builder.py`, pytest page contracts.

**Spec:** `docs/superpowers/specs/2026-07-19-lun-done-autosave-design.md`

## Global Constraints

- Immediate `saveLocal()` on every Done toggle
- Debounced server save (~400ms) only when `persisted === true`, build has non-empty `id`, and build is not a template
- Server path is existing `POST /api/lun-builds` with `{ build }`
- On server failure: keep local state; status message that completion was saved locally only
- Do not auto-save non-Done field edits
- Do not change Hosts/LUN specs “all volumes Done” rules, headings, Preview/Run gating, or schema
- Optional quiet status: `Completion saved.` / local-only message; no modals
- Bump `APP_VERSION` to `1.6.37` in the final task
- Commit when the task reaches its commit step (user requested implementation of this approved plan)

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/lun_builder.py` | `persistCompletionState` / debounce timer; call from Done handlers |
| `tests/test_lun_builder_page.py` | Page contracts for helper + Done-handler wiring |
| `launchpad/config.py` | `APP_VERSION = "1.6.37"` |

---

### Task 1: Persist completion state on Done toggles

**Files:**
- Modify: `launchpad/lun_builder.py`
- Test: `tests/test_lun_builder_page.py`

**Interfaces:**
- Consumes: `saveLocal()`, `activeBuild()`, `persisted`, `statusEl`, existing Save POST
- Produces: `persistCompletionState()`; optional internal `scheduleCompletionSave(build)` / timer variable

- [ ] **Step 1: Write the failing page-contract tests**

Add to `tests/test_lun_builder_page.py`:

```python
def test_lun_builder_persists_completion_state():
    for text in (
        "persistCompletionState",
        "scheduleCompletionSave",
        "Completion saved.",
        "Completion saved locally only",
    ):
        assert text in LUN_BUILDER_HTML


def test_done_handlers_call_persist_completion_state():
    plan_handler = LUN_BUILDER_HTML.split(
        'document.getElementById("plan-body").addEventListener("change"', 1
    )[1].split(
        'document.getElementById("cli-checklist").addEventListener("change"', 1
    )[0]
    update_field = LUN_BUILDER_HTML.split("function updateField(event)", 1)[1].split(
        "function refreshExpandedNames", 1
    )[0]
    cli_handler = LUN_BUILDER_HTML.split(
        'document.getElementById("cli-checklist").addEventListener("change"', 1
    )[1].split(
        'document.getElementById("cli-checklist").addEventListener("click"', 1
    )[0]

    assert "persistCompletionState()" in plan_handler
    assert "persistCompletionState()" in update_field
    assert 'target.dataset.key === "done"' in update_field
    assert update_field.index('target.dataset.key === "done"') < update_field.index(
        "persistCompletionState()"
    )
    assert "persistCompletionState()" in cli_handler
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_lun_builder_page.py::test_lun_builder_persists_completion_state tests/test_lun_builder_page.py::test_done_handlers_call_persist_completion_state -v
```

Expected: FAIL because helpers/strings are missing.

- [ ] **Step 3: Add debounce state and helpers near `saveLocal`**

In `launchpad/lun_builder.py` script section, after `saveLocal` (and near other top-level `let` state), add:

```javascript
    let completionSaveTimer = null;
    function scheduleCompletionSave(build) {
      if (completionSaveTimer) clearTimeout(completionSaveTimer);
      completionSaveTimer = setTimeout(async () => {
        completionSaveTimer = null;
        if (!persisted || !build || !build.id || build.is_template) return;
        build.updated_at = new Date().toISOString();
        try {
          const response = await fetch("/api/lun-builds", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ build }),
          });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          builds = (await response.json()).builds;
          saveLocal();
          statusEl.textContent = "Completion saved.";
        } catch (error) {
          statusEl.textContent = `Completion saved locally only: ${error.message || error}`;
        }
      }, 400);
    }
    function persistCompletionState() {
      const build = activeBuild();
      saveLocal();
      if (!persisted || !build.id || build.is_template) {
        statusEl.textContent = "Completion saved locally only.";
        return;
      }
      scheduleCompletionSave(build);
    }
```

Notes:
- `saveLocal()` is always immediate.
- Debounce is 400ms and only for the server POST.
- Do not invalidate Preview from these helpers.
- When not persisted / no id / template: set the local-only status and return (no server schedule).

- [ ] **Step 4: Wire Hosts / LUN specs Done path**

In `updateField`, inside the `target.dataset.key === "done"` branch, after `updateSectionHeadings(activeBuild());` and before `return;`, add:

```javascript
        persistCompletionState();
```

- [ ] **Step 5: Wire LUN Plan Done path**

In the `plan-body` change handler, after `syncCompletionFromPlan(build);` and `render();`, add:

```javascript
      persistCompletionState();
```

- [ ] **Step 6: Wire command checklist Done path**

In the `cli-checklist` change handler, after updating `commandDone` / row class / `updateCopyAllRemainingState()`, add:

```javascript
      persistCompletionState();
```

- [ ] **Step 7: Run page tests GREEN**

Run:

```powershell
python -m pytest tests/test_lun_builder_page.py -v
```

Expected: all page tests PASS.

- [ ] **Step 8: Commit**

```powershell
git add tests/test_lun_builder_page.py launchpad/lun_builder.py
git commit -m "Auto-save LUN Builder Done checkbox state."
```

---

### Task 2: Version bump and regression

**Files:**
- Modify: `launchpad/config.py`

**Interfaces:**
- Consumes: Task 1 auto-save behavior
- Produces: `APP_VERSION = "1.6.37"`

- [ ] **Step 1: Bump version**

In `launchpad/config.py`:

```python
APP_VERSION = "1.6.37"
```

- [ ] **Step 2: Run full suite**

Run:

```powershell
python -m pytest tests
```

Expected: all tests PASS (current total).

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.37 for Done auto-save."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Immediate `saveLocal` on Done toggles | Task 1 |
| Debounced server save when unlocked + id + not template | Task 1 |
| LUN Plan / Hosts / LUN specs / command checklist wired | Task 1 |
| Local-only / success status messages | Task 1 |
| No non-Done auto-save; no rule/heading/schema changes | Task 1 scope |
| Version `1.6.37` | Task 2 |
