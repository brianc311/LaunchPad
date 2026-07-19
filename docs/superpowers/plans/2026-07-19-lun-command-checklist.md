# LUN Command Checklist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn LUN Builder Preview dry-run output into a per-volume command checklist with Copy / Copy All Remaining and Done checkboxes for manual SSH paste workflows.

**Architecture:** Preview steps gain an explicit `volume_name`. A pure grouping helper clusters ordered steps by that field. The CLI panel becomes a checklist UI that copies only executable `cmd` values, shows warnings separately, and persists completion under `command_done` keyed by a signature of volume name + commands.

**Tech Stack:** Existing LUN Builder page/data/create modules, Clipboard API in the browser, pytest.

**Spec:** `docs/superpowers/specs/2026-07-19-lun-command-checklist-design.md`

## Global Constraints

- One checklist row per volume (create + all maps for that volume)
- Copy buttons include only non-empty `cmd` strings — never warnings, labels, `[ready]`, output, or errors
- Done state is informational only; does not change Preview/Run Create gating
- `command_done` keys are signatures: `"{volume_name}\n" + "\n".join(commands)`
- Browser renders checklist; modal may keep diagnostic text
- Bump `APP_VERSION` to `1.6.33` in the final task
- Do not commit unless the user asked for commits in this session
- Do not change Preview/Run safety rules beyond adding `volume_name` on steps

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/lun_builder_create.py` | Add `volume_name` to `_step`; add `group_lun_steps_by_volume` + `command_group_signature` |
| `tests/test_lun_builder_create.py` | Assert `volume_name` on steps; grouping + signature contracts |
| `launchpad/lun_builder_data.py` | Normalize/persist `command_done` on builds |
| `tests/test_lun_builder_data.py` | `command_done` normalize contracts |
| `launchpad/lun_builder.py` | Checklist UI, copy actions, Done checkboxes, wire preview fill |
| `tests/test_lun_builder_page.py` | HTML/JS contract strings for checklist |
| `tests/test_health_server_lun_builder.py` | Expect `command_done: {}` in normalize fixtures if needed |
| `launchpad/config.py` | `1.6.33` |

---

### Task 1: Add `volume_name` to generated steps

**Files:**
- Modify: `launchpad/lun_builder_create.py`
- Test: `tests/test_lun_builder_create.py`

**Interfaces:**
- Consumes: existing `build_lun_steps`, `_step`
- Produces: every step dict includes `"volume_name": str` (volume token used in that step's create/map)

- [ ] **Step 1: Write the failing assertions**

Add to `test_svc_steps_include_create_and_host_map` (after building steps):

```python
assert all(step.get("volume_name") == "host1_vol" for step in steps)
```

Add to `test_threepar_steps_use_auto_incrementing_lun_ids_per_host`:

```python
assert {step["volume_name"] for step in steps} == {"host1_data_1", "host1_data_2"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lun_builder_create.py::test_svc_steps_include_create_and_host_map tests/test_lun_builder_create.py::test_threepar_steps_use_auto_incrementing_lun_ids_per_host -v`

Expected: FAIL because `volume_name` is missing

- [ ] **Step 3: Extend `_step` and all call sites**

Update `_step` in `launchpad/lun_builder_create.py`:

```python
def _step(
    *,
    kind: str,
    label: str,
    cmd: str,
    card_hint: str,
    profile: str,
    live: bool,
    skip: bool = False,
    reason: str = "",
    volume_name: str = "",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "label": label,
        "cmd": cmd,
        "card_hint": card_hint,
        "profile": profile,
        "live": live,
        "skip": skip,
        "reason": reason,
        "volume_name": str(volume_name or "").strip(),
    }
```

Pass `volume_name=name` into every `_step(...)` call in `build_lun_steps` (SVC create/map, 3PAR create/map, DS/XIV plan).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_lun_builder_create.py -v`

Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add launchpad/lun_builder_create.py tests/test_lun_builder_create.py
git commit -m "Add volume_name to LUN Builder preview steps."
```

---

### Task 2: Grouping helper and command-group signature

**Files:**
- Modify: `launchpad/lun_builder_create.py`
- Test: `tests/test_lun_builder_create.py`

**Interfaces:**
- Consumes: ordered step dicts with `volume_name` and `cmd`
- Produces:
  - `command_group_signature(volume_name: str, commands: list[str]) -> str`
  - `group_lun_steps_by_volume(steps: list[dict]) -> list[dict]` where each group is:
    `{"volume_name": str, "commands": list[str], "steps": list[dict], "signature": str}`

- [ ] **Step 1: Write the failing tests**

```python
from launchpad.lun_builder_create import (
    command_group_signature,
    group_lun_steps_by_volume,
)


def test_command_group_signature_joins_volume_and_commands():
    assert command_group_signature(
        "pconsps3_root_1",
        [
            "svctask mkvdisk -name pconsps3_root_1 -mdiskgrp pcon_pool1 -size 50 -unit gb",
            "svctask mkvdiskhostmap -host pconsps3 -scsi 0 pconsps3_root_1",
        ],
    ) == (
        "pconsps3_root_1\n"
        "svctask mkvdisk -name pconsps3_root_1 -mdiskgrp pcon_pool1 -size 50 -unit gb\n"
        "svctask mkvdiskhostmap -host pconsps3 -scsi 0 pconsps3_root_1"
    )


def test_group_lun_steps_by_volume_keeps_create_and_maps_together():
    steps = [
        {"volume_name": "vol_a", "cmd": "create a", "kind": "mkvdisk"},
        {"volume_name": "vol_a", "cmd": "map a1", "kind": "mkvdiskhostmap"},
        {"volume_name": "vol_a", "cmd": "map a2", "kind": "mkvdiskhostmap"},
        {"volume_name": "vol_b", "cmd": "create b", "kind": "mkvdisk"},
        {"volume_name": "vol_b", "cmd": "map b1", "kind": "mkvdiskhostmap"},
        {"volume_name": "", "cmd": "orphan", "kind": "plan"},
        {"volume_name": "", "cmd": "orphan2", "kind": "plan"},
    ]
    groups = group_lun_steps_by_volume(steps)
    assert [g["volume_name"] for g in groups] == ["vol_a", "vol_b", "", ""]
    assert groups[0]["commands"] == ["create a", "map a1", "map a2"]
    assert groups[1]["commands"] == ["create b", "map b1"]
    assert groups[2]["commands"] == ["orphan"]
    assert groups[3]["commands"] == ["orphan2"]
    assert groups[0]["signature"] == command_group_signature(
        "vol_a", ["create a", "map a1", "map a2"]
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lun_builder_create.py::test_command_group_signature_joins_volume_and_commands tests/test_lun_builder_create.py::test_group_lun_steps_by_volume_keeps_create_and_maps_together -v`

Expected: FAIL with import / not defined errors

- [ ] **Step 3: Implement helpers**

Add to `launchpad/lun_builder_create.py`:

```python
def command_group_signature(volume_name: str, commands: list[str]) -> str:
    name = str(volume_name or "").strip()
    cmds = [str(cmd).strip() for cmd in commands if str(cmd or "").strip()]
    return name + ("\n" if name or cmds else "") + "\n".join(cmds)


def group_lun_steps_by_volume(steps: list[dict]) -> list[dict]:
    groups: list[dict] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        volume_name = str(step.get("volume_name") or "").strip()
        cmd = str(step.get("cmd") or "").strip()
        solo = not volume_name
        if (
            not solo
            and groups
            and groups[-1]["volume_name"] == volume_name
        ):
            group = groups[-1]
        else:
            group = {
                "volume_name": volume_name,
                "commands": [],
                "steps": [],
                "signature": "",
            }
            groups.append(group)
        group["steps"].append(step)
        if cmd:
            group["commands"].append(cmd)
        group["signature"] = command_group_signature(
            group["volume_name"], group["commands"]
        )
    return groups
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_lun_builder_create.py -v`

Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add launchpad/lun_builder_create.py tests/test_lun_builder_create.py
git commit -m "Add LUN step grouping helpers for command checklist."
```

---

### Task 3: Persist `command_done` on builds

**Files:**
- Modify: `launchpad/lun_builder_data.py`
- Modify: `tests/test_lun_builder_data.py`
- Modify: `tests/test_health_server_lun_builder.py` (fixture expectation for empty builds)

**Interfaces:**
- Consumes: `_as_bool`, existing `normalize_build`
- Produces: `normalize_build` includes `"command_done": dict[str, bool]` (true entries only, non-empty keys)

- [ ] **Step 1: Write the failing test**

```python
def test_normalize_keeps_command_done_map():
    build = normalize_build(
        {
            "id": "lab",
            "name": "Lab",
            "hosts": [],
            "luns": [],
            "command_done": {
                "vol_a\ncmd1\ncmd2": True,
                "stale\ncmd": False,
                "": True,
            },
        }
    )
    assert build["command_done"] == {"vol_a\ncmd1\ncmd2": True}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lun_builder_data.py::test_normalize_keeps_command_done_map -v`

Expected: FAIL with KeyError `command_done`

- [ ] **Step 3: Implement normalize**

Reuse the same pattern as `plan_done`:

```python
def _normalize_command_done(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): True
        for key, value in raw.items()
        if str(key) and _as_bool(value)
    }
```

In `normalize_build` return dict, add:

```python
"command_done": _normalize_command_done(raw.get("command_done")),
```

Update `test_lun_builds_replace_upsert_and_delete_persist` expected empty build to include `"command_done": {}` next to `"plan_done": {}`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_lun_builder_data.py tests/test_health_server_lun_builder.py::test_lun_builds_replace_upsert_and_delete_persist -v`

Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add launchpad/lun_builder_data.py tests/test_lun_builder_data.py tests/test_health_server_lun_builder.py
git commit -m "Persist command_done checklist state on LUN builds."
```

---

### Task 4: Command checklist UI with Copy and Done

**Files:**
- Modify: `launchpad/lun_builder.py`
- Test: `tests/test_lun_builder_page.py`

**Interfaces:**
- Consumes: preview `data.steps`, `data.warnings`; build.`command_done`; JS mirrors of `group_lun_steps_by_volume` / `command_group_signature`
- Produces: checklist DOM; clipboard of commands only; persisted `command_done` on toggle

- [ ] **Step 1: Write failing page-contract assertions**

Extend `test_lun_builder_page_contract` (or add `test_lun_builder_command_checklist`) to require:

```python
for text in (
    "Command checklist",
    "Copy All Remaining",
    'id="cli-checklist"',
    'id="cli-warnings"',
    'id="copy-all-remaining-btn"',
    "command_done",
    "groupLunStepsByVolume",
    "commandGroupSignature",
    "fillCliChecklist",
):
    assert text in LUN_BUILDER_HTML
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lun_builder_page.py -k checklist -v`

Expected: FAIL on missing strings

- [ ] **Step 3: Replace CLI panel markup**

Replace the current `#cli-panel` body so it includes:

```html
<details class="cli-panel" id="cli-panel">
  <summary>Command checklist (Preview)</summary>
  <p class="cli-empty" id="cli-empty">Run Preview / Dry-run to fill this checklist.</p>
  <div id="cli-checklist-wrap" hidden>
    <div class="cli-toolbar">
      <button type="button" class="secondary" id="copy-all-remaining-btn">Copy All Remaining</button>
      <span class="status" id="cli-copy-status" aria-live="polite"></span>
    </div>
    <div id="cli-warnings" class="cli-warnings"></div>
    <div class="table-wrap">
      <table class="cli-table">
        <thead>
          <tr>
            <th>Done</th>
            <th>Volume</th>
            <th>Commands</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="cli-checklist"></tbody>
      </table>
    </div>
  </div>
  <pre id="cli-commands" hidden></pre>
</details>
```

Add CSS so `.cli-table tr.row-done` uses the same green treatment as Hosts / LUN Plan / LUN specs.

- [ ] **Step 4: Implement JS helpers and fill path**

Mirror Python helpers in the page script:

```javascript
function commandGroupSignature(volumeName, commands) {
  const name = String(volumeName || "").trim();
  const cmds = (commands || []).map((cmd) => String(cmd || "").trim()).filter(Boolean);
  return name + ((name || cmds.length) ? "\n" : "") + cmds.join("\n");
}

function groupLunStepsByVolume(steps) {
  const groups = [];
  for (const step of steps || []) {
    const volumeName = String(step.volume_name || "").trim();
    const cmd = String(step.cmd || "").trim();
    const solo = !volumeName;
    let group;
    if (!solo && groups.length && groups[groups.length - 1].volume_name === volumeName) {
      group = groups[groups.length - 1];
    } else {
      group = { volume_name: volumeName, commands: [], steps: [], signature: "" };
      groups.push(group);
    }
    group.steps.push(step);
    if (cmd) group.commands.push(cmd);
    group.signature = commandGroupSignature(group.volume_name, group.commands);
  }
  return groups;
}
```

Implement `fillCliChecklist(data)` that:

1. Shows warnings in `#cli-warnings` as plain text lines prefixed with `WARNING: ` (never in copy buffers)
2. Builds groups from `data.steps` (or `data.log` after Run Create — prefer steps for checklist; if only log exists, map log entries the same way using `volume_name`/`cmd`)
3. Renders one row per group with Done checkbox, volume name, `<pre>` of commands, and a Copy button
4. Marks row green when `build.command_done[signature]` is true
5. Disables Copy All Remaining when no unfinished groups have commands

Wire Preview / Run Create to call `fillCliChecklist(data)` instead of (or in addition to) dumping the full diagnostic text into `#cli-commands`. Keep `showModal(..., formatLunResult(data))` for diagnostics.

Copy handlers:

```javascript
async function copyText(text, statusMessage) {
  try {
    await navigator.clipboard.writeText(text);
    document.getElementById("cli-copy-status").textContent = statusMessage;
  } catch (_err) {
    document.getElementById("cli-copy-status").textContent = "Copy failed — select commands manually.";
  }
}
```

- Row Copy: join that group's `commands` with `\n`
- Copy All Remaining: join commands from groups whose signature is not in `command_done`

Done checkbox: toggle `build.command_done[signature] = true` or delete key; do not invalidate preview.

Ensure `emptyBuild()` includes `command_done: {}` and saves persist it (already covered by normalize once Task 3 is done).

- [ ] **Step 5: Run page + LUN tests**

Run: `pytest tests/test_lun_builder_page.py tests/test_lun_builder_create.py tests/test_lun_builder_data.py -v`

Expected: PASS

- [ ] **Step 6: Commit (only if user asked)**

```bash
git add launchpad/lun_builder.py tests/test_lun_builder_page.py
git commit -m "Add copyable LUN command checklist with Done tracking."
```

---

### Task 5: Version bump and regression

**Files:**
- Modify: `launchpad/config.py`
- Test: full LUN suite

- [ ] **Step 1: Bump version**

```python
APP_VERSION = "1.6.33"
```

- [ ] **Step 2: Run full LUN-related suite**

Run: `pytest tests/ -q -k "lun" --tb=short`

Expected: all selected tests PASS

- [ ] **Step 3: Manual smoke checklist**

1. Open `/lun-builder`, load Hartford copy, Preview
2. Confirm checklist rows are per volume with create + maps
3. Copy one row into a text editor — only commands, no warnings/`[ready]`
4. Mark Done — row turns green; Save; reload; Done persists
5. Change a pool name, Preview again — changed row is not Done; unchanged signatures stay Done
6. Copy All Remaining excludes Done rows

- [ ] **Step 4: Commit (only if user asked)**

```bash
git add launchpad/config.py
git commit -m "Bump version to 1.6.33 for LUN command checklist."
```

---

## Spec coverage self-review

| Spec requirement | Task |
|------------------|------|
| Per-volume checklist rows with create + maps | 2, 4 |
| Copy / Copy All Remaining (commands only) | 4 |
| Done checkbox greens row | 4 |
| Warnings separate, never copied | 4 |
| `volume_name` on steps | 1 |
| Browser groups by `volume_name` | 2 (algorithm), 4 (JS) |
| Completion keyed by volume+commands signature | 2, 3, 4 |
| Informational only vs Preview/Run | 4 |
| Existing Preview/Run tests still pass | 1, 5 |

## Placeholder / consistency scan

- No TBD/TODO placeholders
- Signature format identical in Python and JS: `name + "\n" + commands.join("\n")`
- Field name is `command_done` (distinct from existing LUN Plan `plan_done`)
