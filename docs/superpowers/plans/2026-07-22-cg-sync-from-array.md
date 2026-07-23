# Contingency Groups Ensure Sites + Sync from Array — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure Contingency Group stubs for every monitored FlashSystem/SVC Health Card, and add **Sync from array** on the Contingency Groups page to SSH-refresh the selected group only (reuse Sync Inventory shaping; do not touch LUN builds).

**Architecture:** Pure `ensure_groups_for_cards` merges stubs into the CG list. HealthServer runs ensure on GET when unlocked, and exposes `POST /api/contingency-groups/sync-inventory` that reuses the same SSH suite + `build_inventory_sync` as LUN Sync Inventory but upserts only the selected Contingency Group. The CG page adds the Sync button and refreshes after ensure/sync.

**Tech Stack:** Existing HealthServer, `inventory_sync.build_inventory_sync`, Contingency Groups settings, pytest.

**Spec:** `docs/superpowers/specs/2026-07-22-cg-sync-from-array-design.md`

## Global Constraints

- Work in `C:\Users\BrianColley\LaunchPad\.worktrees\cg-sync-from-array` on `feature/cg-sync-from-array` (forked from `feature/sync-live-snaps-cg`, has inventory sync + live snaps).
- Dropdown “all sites” = every **monitored** card with `device_profile in SVC_PROFILES`.
- Sync = **selected group only**; do **not** modify LUN Builder builds.
- Button label exactly: `Sync from array`.
- Reuse Sync Inventory SSH + `build_inventory_sync` (including live snaps on this tip).
- Fail closed on SSH/card errors (no partial replace of the selected group).
- Do not rewrite git seed modules as the only source of truth; stubs live in settings via ensure/upsert.
- Bump `APP_VERSION` from `1.6.48` to `1.6.50` (1.6.49 claimed by FC WWPN search branch).
- Commit each task with PowerShell-safe `git commit -m "message"` (no bash heredoc).

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/contingency_groups_data.py` | `ensure_groups_for_cards`, match helpers |
| `launchpad/health_server.py` | Ensure on GET; `sync_contingency_inventory`; API route |
| `launchpad/contingency_groups.py` | Sync button + JS; reload after sync |
| `launchpad/config.py` | `1.6.50` |
| `tests/test_contingency_groups_data.py` | Ensure stub unit tests |
| `tests/test_health_server_contingency_groups.py` | Ensure + sync API tests |
| `tests/test_contingency_groups_page.py` | Button / endpoint wiring |

---

### Task 0: Confirm worktree baseline

**Files:** none

**Interfaces:**
- Consumes: branch with design doc + inventory sync
- Produces: confirmed version `1.6.48`

- [ ] **Step 1: Confirm**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\cg-sync-from-array
git branch --show-current
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION); from launchpad.inventory_sync import build_inventory_sync; print('sync_ok')"
```

Expected: `feature/cg-sync-from-array`, `1.6.48`, `sync_ok`.

- [ ] **Step 2: No commit**

---

### Task 1: `ensure_groups_for_cards` helper

**Files:**
- Modify: `launchpad/contingency_groups_data.py`
- Test: `tests/test_contingency_groups_data.py`

**Interfaces:**
- Consumes: `normalize_group`, `new_group_id`, `_slugify`
- Produces:
  - `group_matches_card(group: dict, card: dict) -> bool` — match if any of (case-insensitive trim): group `id` == slug of card name, group `name` == card name, group `location` == card name, group `storage_hint` == card name (also accept card `id` string forms if present)
  - `stub_group_for_card(card: dict, existing: list[dict]) -> dict` — normalized empty group with `name`/`location`/`storage_hint` = card name, `id` = `new_group_id(card_name, existing)`
  - `ensure_groups_for_cards(groups: list[dict], cards: list[dict]) -> list[dict]` — for each card dict with keys at least `name` (and optional `device_profile`), if no match append stub; never empty/wipe matched groups; return normalize_groups result

Card dict shape for tests (minimal):

```python
{"name": "Moreno Valley, CA", "device_profile": "flashsystem_7200", "id": 12}
```

- [ ] **Step 1: Write failing tests**

Append to `tests/test_contingency_groups_data.py`:

```python
from launchpad.contingency_groups_data import (
    ensure_groups_for_cards,
    group_matches_card,
    stub_group_for_card,
)


def test_group_matches_card_by_name_and_hint():
    group = {
        "id": "moreno-valley-ca",
        "name": "Moreno Valley, CA",
        "storage_hint": "v7kmv",
        "location": "Moreno Valley, CA",
    }
    assert group_matches_card(group, {"name": "Moreno Valley, CA"}) is True
    assert group_matches_card(group, {"name": "v7kmv"}) is True  # storage_hint
    assert group_matches_card(group, {"name": "Unrelated Site"}) is False


def test_ensure_groups_for_cards_adds_stubs_without_duping():
    existing = [
        {
            "id": "windsor",
            "name": "Windsor",
            "location": "Windsor",
            "storage_hint": "v5kwin-g3v1",
            "hosts": [{"name": "keep-me", "status": "Online", "host_type": "Generic", "port_count": 2, "protocol": "SCSI", "wwpns": []}],
            "volumes": [],
            "maps": [],
        }
    ]
    cards = [
        {"name": "Windsor", "device_profile": "flashsystem_7200"},
        {"name": "Moreno Valley, CA", "device_profile": "flashsystem_7200"},
        {"name": "Woodland Hills, CA", "device_profile": "flashsystem_7200"},
    ]
    out = ensure_groups_for_cards(existing, cards)
    names = {g["name"] for g in out}
    assert "Windsor" in names and "Moreno Valley, CA" in names and "Woodland Hills, CA" in names
    windsor = next(g for g in out if g["name"] == "Windsor")
    assert windsor["hosts"][0]["name"] == "keep-me"
    moreno = next(g for g in out if g["name"] == "Moreno Valley, CA")
    assert moreno["storage_hint"] == "Moreno Valley, CA"
    assert moreno["hosts"] == [] and moreno["volumes"] == []
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_contingency_groups_data.py::test_group_matches_card_by_name_and_hint tests/test_contingency_groups_data.py::test_ensure_groups_for_cards_adds_stubs_without_duping -v
```

Expected: FAIL (import / missing symbols).

- [ ] **Step 3: Implement helpers** in `contingency_groups_data.py`

Match rules (explicit):

```python
def group_matches_card(group: dict, card: dict) -> bool:
    card_name = str(card.get("name") or "").strip().lower()
    if not card_name:
        return False
    fields = [
        str(group.get("id") or "").strip().lower(),
        str(group.get("name") or "").strip().lower(),
        str(group.get("location") or "").strip().lower(),
        str(group.get("storage_hint") or "").strip().lower(),
        _slugify(str(group.get("name") or "")),
    ]
    return card_name in fields or _slugify(card_name) in fields
```

`ensure_groups_for_cards`: copy groups list; for each card with non-empty name, if no match, append `stub_group_for_card`; return `normalize_groups(...)`.

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_contingency_groups_data.py -v
```

Expected: PASS (including existing tests).

- [ ] **Step 5: Commit**

```powershell
git add launchpad/contingency_groups_data.py tests/test_contingency_groups_data.py
git commit -m "Ensure Contingency Group stubs for monitored SVC cards."
```

---

### Task 2: HealthServer ensure + Sync from array API

**Files:**
- Modify: `launchpad/health_server.py`
- Test: `tests/test_health_server_contingency_groups.py` (extend)

**Interfaces:**
- Consumes: Task 1 helpers; `build_inventory_sync`; parsers used by `sync_inventory`; `SVC_PROFILES`; `is_monitor_enabled`; `find_card_by_hint`; `_lun_run_command`
- Produces:
  - `HealthServer.monitored_svc_card_dicts(self) -> list[dict]` — cards where monitor on and profile in `SVC_PROFILES`, each `{"id", "name", "device_profile"}`
  - `HealthServer.ensure_contingency_groups_from_cards(self) -> list[dict]` — get groups, ensure, persist via `set_contingency_groups` when backend available
  - `HealthServer.sync_contingency_inventory(self, group_id: str, *, card_name: str = "") -> dict` — SSH + shape + upsert **selected group only**; return `{group, groups, pulled, warnings}`
  - GET `/api/contingency-groups` calls ensure when `persisted` (unlocked) before returning groups
  - POST path `/api/contingency-groups/sync-inventory` body `{group_id, card_name?}`

**Sync algorithm (critical):**

1. Load group by id; 404/ValueError if missing.
2. Resolve card: `card_name` arg, else `storage_hint`, else `name`; `find_card_by_hint`; error if missing.
3. Require `card.device_profile in SVC_PROFILES`.
4. Same SSH commands as `sync_inventory`.
5. `build_inventory_sync(..., card_name=card.name, storage_hint=card.name, group_id=existing["id"], ...)`.
6. Merge into existing group:
   - Keep `id`, `name`, `location`, `notes` from existing (do not rename the user’s group to the card unless name was empty).
   - Set `storage_hint` to `card.name`.
   - Replace `hosts`, `volumes`, `maps` from shaped `result["group"]`.
7. `upsert_contingency_group(merged)`.
8. **Do not** call `upsert_lun_build`.
9. Return pulled/warnings from `result`.

Wire POST like other contingency snap routes (see `/api/contingency-groups/generate-snaps`).

**Ensure on GET:** In the GET handler that returns groups, when `contingency_groups_persist_available()`, call `ensure_contingency_groups_from_cards()` and return that list.

- [ ] **Step 1: Write failing tests**

In `tests/test_health_server_contingency_groups.py`, mirror the monkeypatch style from `test_sync_inventory_replaces_build_and_upserts_cg`:

```python
def test_ensure_contingency_groups_from_monitored_svc_cards():
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    # seed three defaults via get
    server.get_contingency_groups()
    server.register_card(1, "Moreno Valley, CA", "10.0.0.1", 22, "u", "", device_profile="flashsystem_7200")
    server.register_card(2, "Other SSH", "10.0.0.2", 22, "u", "", device_profile="generic_ssh")
    server.set_monitor_enabled(card_id=1, enabled=True)
    server.set_monitor_enabled(card_id=2, enabled=True)
    groups = server.ensure_contingency_groups_from_cards()
    names = {g["name"] for g in groups}
    assert "Moreno Valley, CA" in names
    assert "Other SSH" not in names  # not SVC


def test_sync_contingency_inventory_updates_group_not_lun_build(monkeypatch):
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    server.set_contingency_groups([{
        "id": "lab-1",
        "name": "Lab Site",
        "location": "Lab Site",
        "storage_hint": "Storage A",
        "notes": "keep-notes",
        "hosts": [],
        "volumes": [{"name": "stale", "role": "source"}],
        "maps": [],
    }])
    server.set_lun_builds([{
        "id": "b1",
        "name": "Build",
        "hosts": [{"lpar_name": "untouched"}],
        "luns": [],
    }])
    server.register_card(1, "Storage A", "array.example", 22, "operator", "", device_profile="flashsystem_5200")
    outputs = {
        "svcinfo lshost -delim :": "id:name:status:port_count\n0:host1:online:2\n",
        "svcinfo lshostvdiskmap -delim :": "host_name:vdisk_name:SCSI_id\nhost1:vol1:3\n",
        "svcinfo lsvdisk -delim :": (
            "id:name:status:mdisk_grp_name:capacity:vdisk_UID\n"
            "0:vol1:online:Pool0:10.00 GiB:UID1\n"
        ),
        "svcinfo lsfabric -delim :": "name:local_wwpn:remote_wwpn\nhost1:AA:BB\n",
    }
    monkeypatch.setattr(server, "_lun_run_command", lambda _card: lambda command: outputs[command])
    result = server.sync_contingency_inventory("lab-1")
    assert result["group"]["id"] == "lab-1"
    assert result["group"]["name"] == "Lab Site"
    assert result["group"]["notes"] == "keep-notes"
    assert result["group"]["storage_hint"] == "Storage A"
    assert "vol1" in {v["name"] for v in result["group"]["volumes"]}
    assert "stale" not in {v["name"] for v in result["group"]["volumes"]}
    builds = server.get_lun_builds()
    assert builds[0]["hosts"][0]["lpar_name"] == "untouched"
```

Adapt fabric/WWPN keys if `parse_fabric_logins` expects different sample — copy working sample from `test_sync_inventory_replaces_build_and_upserts_cg`.

Also add failure test: monkeypatch run to raise → group volumes still `stale`.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_health_server_contingency_groups.py -v
```

Expected: new tests FAIL.

- [ ] **Step 3: Implement server methods + routes**

Follow existing `sync_inventory` for SSH/parse. Register POST `/api/contingency-groups/sync-inventory` beside other contingency POST routes.

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_health_server_contingency_groups.py tests/test_contingency_groups_data.py tests/test_health_server_lun_builder.py -k "sync_inventory or contingency" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_health_server_contingency_groups.py
git commit -m "Add Contingency Groups ensure-from-cards and Sync from array API."
```

---

### Task 3: Contingency Groups UI

**Files:**
- Modify: `launchpad/contingency_groups.py`
- Test: `tests/test_contingency_groups_page.py`

**Interfaces:**
- Consumes: GET ensure (server-side) + `POST /api/contingency-groups/sync-inventory`
- Produces: button `Sync from array` (`id="sync-array-btn"`); JS `syncFromArray()` prompts for card name defaulting to `storage_hint` or group name; updates groups/status from response

UI: place button in `.actions` next to Export / Open in FC WWPN:

```html
<button type="button" id="sync-array-btn" class="secondary">Sync from array</button>
```

JS sketch:

```javascript
async function syncFromArray() {
  if (!currentId) { statusEl.textContent = "Select a group to sync."; return; }
  if (!persisted) { statusEl.textContent = "Unlock LaunchPad before syncing from the array."; return; }
  const group = activeGroup();
  const cardName = window.prompt(
    "Storage card name (required):",
    (group.storage_hint || group.name || "").trim()
  );
  if (cardName === null) return;
  if (!cardName.trim()) { statusEl.textContent = "Card name is required for Sync from array."; return; }
  statusEl.textContent = "Syncing Contingency Group via SSH…";
  try {
    const response = await fetch("/api/contingency-groups/sync-inventory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ group_id: currentId, card_name: cardName.trim() }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    groups = Array.isArray(data.groups) ? data.groups : groups;
    saveLocal();
    render();
    const p = data.pulled || {};
    statusEl.textContent =
      `Synced hosts=${p.hosts||0} volumes=${p.volumes||0} maps=${p.maps||0}` +
      ` skipped_snaps=${p.skipped_snaps||0} live_snaps=${p.live_snaps||0}. CG updated.`;
  } catch (error) {
    statusEl.textContent = `Sync from array failed: ${error.message || error}`;
  }
}
```

Wire click listener. After `loadGroups` success, picker should show ensured stubs automatically because GET ensure runs server-side.

- [ ] **Step 1: Failing page tests**

```python
def test_contingency_groups_page_has_sync_from_array():
    assert "Sync from array" in CONTINGENCY_GROUPS_HTML
    assert 'id="sync-array-btn"' in CONTINGENCY_GROUPS_HTML
    assert "/api/contingency-groups/sync-inventory" in CONTINGENCY_GROUPS_HTML
```

- [ ] **Step 2: RED** then **Step 3: implement** then **Step 4: GREEN**

```powershell
python -m pytest tests/test_contingency_groups_page.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/contingency_groups.py tests/test_contingency_groups_page.py
git commit -m "Add Sync from array button to Contingency Groups."
```

---

### Task 4: Version bump + verification

**Files:**
- Modify: `launchpad/config.py` → `APP_VERSION = "1.6.50"`

- [ ] **Step 1: Bump version**
- [ ] **Step 2: Run suite**

```powershell
python -m pytest tests/test_contingency_groups_data.py tests/test_health_server_contingency_groups.py tests/test_contingency_groups_page.py tests/test_inventory_sync.py -v
python -c "from launchpad.config import APP_VERSION; assert APP_VERSION == '1.6.50'"
```

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.50 for Contingency Groups Sync from array."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Ensure stubs for monitored SVC cards | 1–2 |
| Persist ensure when unlocked | 2 |
| Sync selected only | 2–3 |
| Reuse inventory sync + live snaps | 2 |
| No LUN build mutation | 2 |
| Sync from array button + status | 3 |
| Version bump | 4 |
| Fail closed | 2 |
