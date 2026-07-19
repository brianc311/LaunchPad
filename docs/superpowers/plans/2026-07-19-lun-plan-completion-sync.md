# LUN Plan Completion Synchronization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LUN Plan Done changes immediately synchronize source LUN specs, mapped Hosts, row colors, checkboxes, and collapsed heading counts.

**Architecture:** Add one pure JavaScript synchronization helper beside the existing LUN expansion helpers. The LUN Plan change handler updates `plan_done`, invokes the helper, then performs one full `render()`. Python tests extract and execute the actual JavaScript helper with Node, while a focused handler test verifies synchronization occurs before rendering.

**Tech Stack:** Existing embedded JavaScript in `launchpad/lun_builder.py`, pytest, Node.js used only by the focused JavaScript test (skipped when Node is unavailable).

**Spec:** `docs/superpowers/specs/2026-07-19-lun-plan-completion-sync-design.md`

## Global Constraints

- A LUN spec is Done only when every name from `expandLunBatch(lun)` is true in `build.plan_done`.
- A Host with mapped volumes is Done only when every expanded volume mapped to it is true in `build.plan_done`.
- Host matching trims whitespace and ignores case.
- A Host with no mapped volumes retains its existing manual `done` value.
- Synchronization is one-way from LUN Plan to Hosts and LUN specs.
- Manual Hosts and LUN specs Done checkboxes remain enabled.
- Synchronize only when a LUN Plan checkbox changes; do not synchronize during every render.
- Reuse `plan_done`, `luns[].done`, and `hosts[].done`; add no persisted fields.
- Do not change command checklist completion, volume naming, mapping generation, or LUN Plan summary counts.
- Bump `APP_VERSION` to `1.6.36` in the final task.

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/lun_builder.py` | Derive parent completion from LUN Plan and wire it into the plan checkbox handler |
| `tests/test_lun_builder_page.py` | Execute the actual JavaScript helper and verify handler ordering |
| `launchpad/config.py` | Set version `1.6.36` |

---

### Task 1: Synchronize parent completion from LUN Plan

**Files:**
- Modify: `launchpad/lun_builder.py`
- Test: `tests/test_lun_builder_page.py`

**Interfaces:**
- Consumes: `expandLunBatch(lun)`, `build.plan_done`, `build.luns`, `build.hosts`
- Produces: `syncCompletionFromPlan(build) -> void`; mutates existing `lun.done` and mapped `host.done`

- [ ] **Step 1: Add imports and the JavaScript execution helper**

Add these top-level imports to `tests/test_lun_builder_page.py`:

```python
import json
import shutil
import subprocess
from pathlib import Path

import pytest
```

Replace the existing standalone `from pathlib import Path` import rather than duplicating it.

Add this test helper below the imports:

```python
def _run_completion_sync(build: dict) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute the embedded JavaScript helper")

    helpers = LUN_BUILDER_HTML.split("const SITE_HOST_RE =", 1)[1].split(
        "function emptyBuild()", 1
    )[0]
    script = (
        "const SITE_HOST_RE ="
        + helpers
        + f"\nconst build = {json.dumps(build)};"
        + "\nsyncCompletionFromPlan(build);"
        + "\nprocess.stdout.write(JSON.stringify(build));"
    )
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)
```

This extracts and executes the production JavaScript from `SITE_HOST_RE`
through `syncCompletionFromPlan`, including its real naming/expansion
dependencies.

- [ ] **Step 2: Write failing behavior tests**

Add these tests to `tests/test_lun_builder_page.py`:

```python
def _completion_build() -> dict:
    return {
        "plan_done": {
            "pconsps_root_1": True,
            "pconsps_root_2": True,
            "pconsps_data": True,
        },
        "hosts": [
            {"lpar_name": "PCONSPS3", "done": False},
            {"lpar_name": "unmapped", "done": True},
        ],
        "luns": [
            {
                "purpose": "root",
                "count": 2,
                "shared": True,
                "cluster": "sps",
                "name_prefix": "pcon",
                "host_names": [" pconsps3 "],
                "done": False,
            },
            {
                "purpose": "data",
                "count": 1,
                "shared": True,
                "cluster": "sps",
                "name_prefix": "pcon",
                "host_names": ["PCONSPS3"],
                "done": False,
            },
        ],
    }


def test_completion_sync_marks_complete_luns_and_mapped_hosts_done():
    build = _run_completion_sync(_completion_build())

    assert [lun["done"] for lun in build["luns"]] == [True, True]
    assert build["hosts"][0]["done"] is True
    assert build["hosts"][1]["done"] is True


def test_completion_sync_reverses_lun_and_host_when_one_volume_is_incomplete():
    build = _completion_build()
    del build["plan_done"]["pconsps_root_2"]

    synced = _run_completion_sync(build)

    assert [lun["done"] for lun in synced["luns"]] == [False, True]
    assert synced["hosts"][0]["done"] is False
    assert synced["hosts"][1]["done"] is True


def test_plan_done_handler_synchronizes_before_rendering():
    handler = LUN_BUILDER_HTML.split(
        'document.getElementById("plan-body").addEventListener("change"', 1
    )[1].split(
        'document.getElementById("cli-checklist").addEventListener("change"', 1
    )[0]

    assert "syncCompletionFromPlan(build);" in handler
    assert "render();" in handler
    assert handler.index("syncCompletionFromPlan(build);") < handler.index("render();")
```

The first test covers all-expanded Done, case-insensitive/trimmed Host
matching, and preservation of an unmapped Host's manual state. The second
covers reversal when one expanded volume is unchecked. The third verifies
event ordering.

- [ ] **Step 3: Run focused tests to verify RED**

Run:

```powershell
python -m pytest tests/test_lun_builder_page.py -k "completion_sync or plan_done_handler" -v
```

Expected: FAIL because `syncCompletionFromPlan` and the handler call do not
exist.

- [ ] **Step 4: Implement the synchronization helper**

In `launchpad/lun_builder.py`, add this immediately after
`expandLunBatch(lun)` and before `emptyBuild()`:

```javascript
    function normalizeHostName(value) {
      return String(value || "").trim().toLowerCase();
    }
    function syncCompletionFromPlan(build) {
      const planDone = build.plan_done && typeof build.plan_done === "object"
        ? build.plan_done
        : {};
      const luns = Array.isArray(build.luns) ? build.luns : [];
      const hosts = Array.isArray(build.hosts) ? build.hosts : [];
      const volumeNamesByLun = luns.map((lun) => expandLunBatch(lun));

      luns.forEach((lun, index) => {
        lun.done = volumeNamesByLun[index].every((name) => Boolean(planDone[name]));
      });

      hosts.forEach((host) => {
        const hostName = normalizeHostName(host.lpar_name);
        if (!hostName) return;
        const mappedNames = [];
        luns.forEach((lun, index) => {
          const hostNames = Array.isArray(lun.host_names) ? lun.host_names : [];
          if (hostNames.some((name) => normalizeHostName(name) === hostName)) {
            mappedNames.push(...volumeNamesByLun[index]);
          }
        });
        if (mappedNames.length) {
          host.done = mappedNames.every((name) => Boolean(planDone[name]));
        }
      });
    }
```

Do not add fields to `emptyBuild()` or build normalization.

- [ ] **Step 5: Wire the LUN Plan handler**

Replace the row-only styling at the end of the LUN Plan change handler:

```javascript
      const row = target.closest("tr");
      if (row) row.classList.toggle("row-done", target.checked);
```

with:

```javascript
      syncCompletionFromPlan(build);
      render();
```

The single render refreshes the plan row, Hosts, LUN specs, Done checkboxes,
and both section headings. Do not invalidate Preview or change Run gating.

- [ ] **Step 6: Run focused and page tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_lun_builder_page.py -v
```

Expected: all page tests PASS, including the three new tests.

- [ ] **Step 7: Commit**

```powershell
git add tests/test_lun_builder_page.py launchpad/lun_builder.py
git commit -m "Sync completion from the LUN Plan."
```

---

### Task 2: Version bump and regression

**Files:**
- Modify: `launchpad/config.py`

**Interfaces:**
- Consumes: Task 1 synchronization behavior
- Produces: `APP_VERSION = "1.6.36"`

- [ ] **Step 1: Bump the application version**

In `launchpad/config.py`, replace:

```python
APP_VERSION = "1.6.35"
```

with:

```python
APP_VERSION = "1.6.36"
```

- [ ] **Step 2: Run the complete test suite**

Run:

```powershell
python -m pytest tests
```

Expected: all tests PASS (140 or current total). If Node is unavailable, the
two JavaScript behavior tests may be reported as skipped; all other tests
must pass.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.36 for completion synchronization."
```

---

## Spec coverage checklist

| Requirement | Task |
|-------------|------|
| All expanded volumes determine LUN spec Done | Task 1 executable tests/helper |
| All mapped volumes determine Host Done | Task 1 executable tests/helper |
| Trimmed, case-insensitive Host matching | Task 1 executable test/helper |
| Unmapped Host retains manual state | Task 1 executable test/helper |
| Unchecking reverses affected completion | Task 1 executable test/helper |
| Immediate green rows, checkboxes, and heading counts | Task 1 handler calls `render()` |
| Manual parent checkboxes remain enabled | Task 1 does not modify them |
| One-way synchronization only | Task 1 wires only the plan handler |
| No new persisted fields | Task 1 mutates existing `done` fields only |
| Existing LUN Plan summary unchanged | Task 1 does not modify summary logic |
| Version `1.6.36` | Task 2 |
