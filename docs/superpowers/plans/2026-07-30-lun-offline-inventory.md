# LUN Builder Offline Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist a last-known FlashSystem/SVC inventory snapshot on every successful Monitor refresh so LUN Builder can show Plan (editable) and Inventory (read-only offline copy) for all Monitor-on cards (v**1.6.90**).

**Architecture:** New settings key `lun_offline_inventory` stored via HealthServer get/set setting. Pure helpers in `lun_offline_inventory.py` parse `command_results` into LUN-Builder-shaped hosts + volume rows. Hook `refresh_card` and `update_card_live_data` to upsert (success) or record `last_error` (failure) without wiping a good snapshot. LUN Builder UI adds Plan | Inventory toggle, list badges, and inventory-only picker entries.

**Tech Stack:** Python, HealthServer, SQLite settings, pytest, existing `flashsystem_fc` / `inventory_sync` parsers.

**Spec:** `docs/superpowers/specs/2026-07-30-lun-offline-inventory-design.md`

## Global Constraints

- **Worktree:** `.worktrees/lun-offline-inventory` on `branch feature/lun-offline-inventory` from `feature/contingency-groups` tip (≥ `1.6.89` + this plan’s spec)
- Plan data in `lun_builds` is **never** overwritten by auto inventory refresh
- Scope = all Monitor-on SSH FlashSystem/SVC cards (`is_svc_fc_profile`)
- Failed refresh keeps prior hosts/volumes; only updates `last_error` / `last_error_at`
- Unlock required to **write**; GET APIs return stored snapshots when settings backend is available
- Do not change Sync Inventory / Pull FC / Export / Preview / Run Create behavior
- Bump `APP_VERSION` to **1.6.90** in the final task
- Commit per task; run from worktree
- Operator install folder note: `C:\Users\BrianColley\LaunchPad\LaunchPad-install`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/lun_offline_inventory.py` | Setting key, normalize, eligibility, parse `command_results` → snapshot, upsert/list helpers |
| `launchpad/health_server.py` | get/set persistence, hook refresh paths, GET `/api/lun-offline-inventory` |
| `launchpad/lun_builder.py` | Plan \| Inventory toggle, banner, badges, inventory-only picker entries |
| `launchpad/config.py` | `1.6.90` |
| `tests/test_lun_offline_inventory.py` | Pure helper + normalize/upsert tests |
| `tests/test_lun_offline_inventory_api.py` | HealthServer persistence, refresh hooks, API routes |
| `tests/test_lun_builder_page.py` (or new `tests/test_lun_builder_offline_ui.py`) | HTML/JS marker tests |

---

### Task 0: Confirm baseline

```powershell
cd C:\Users\BrianColley\LaunchPad
git worktree add .worktrees/lun-offline-inventory -b feature/lun-offline-inventory feature/contingency-groups
cd .worktrees\lun-offline-inventory
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-30-lun-offline-inventory-design.md
```

Expected: `1.6.89` (or higher), spec `True`. No feature commit.

---

### Task 1: Pure offline inventory module (TDD)

**Files:**
- Create: `launchpad/lun_offline_inventory.py`
- Create: `tests/test_lun_offline_inventory.py`

**Interfaces:**
- `LUN_OFFLINE_INVENTORY_SETTING = "lun_offline_inventory"`
- `is_lun_offline_inventory_eligible(card: dict | object, *, monitor_on: bool) -> bool`
  - `monitor_on` must be True
  - `device_profile` must pass `is_svc_fc_profile`
- `normalize_snapshot(raw: dict | None) -> dict | None`
- `normalize_store(raw: Any) -> dict[str, dict]` — keys are `str(card_id)`
- `upsert_snapshot(store: dict[str, dict], snapshot: dict) -> dict[str, dict]`
- `record_snapshot_error(store: dict[str, dict], *, card_id: int, error: str, site_name: str = "", host: str = "", device_profile: str = "") -> dict[str, dict]`
  - If no prior row: create stub with empty hosts/volumes + error fields
  - If prior row: keep hosts/volumes/updated_at; set `last_error` / `last_error_at`
- `snapshot_from_command_results(*, card_id: int, site_name: str, host: str, device_profile: str, command_results: list[dict] | None, updated_at: str | None = None) -> dict`
  - Extract outputs from results (skip items with `error`) matching `lshost` / `fc - hosts`, `lshostvdiskmap` / `host lun`, `lsvdisk` / `memory - volumes`, optional `lsfabric`
  - Parse with `parse_fc_hosts`, `parse_host_lun_maps`, `parse_lsvdisk_volumes`, `parse_fabric_logins` (from `flashsystem_fc`)
  - Shape hosts via `build_inventory_sync(..., allow_empty=True)` → use `result["hosts"]`
  - `volumes` = list of `{name, pool, capacity, status}` from `parse_lsvdisk_volumes` (dedupe by name)
  - Clear `last_error` / `last_error_at`; set `updated_at` (ISO UTC if not passed)
- `summarize_snapshot(snapshot: dict) -> dict` — card_id, site_name, host, updated_at, host_count, volume_count, last_error

- [ ] **Step 1: Write failing tests**

```python
# tests/test_lun_offline_inventory.py
from launchpad.lun_offline_inventory import (
    is_lun_offline_inventory_eligible,
    normalize_store,
    record_snapshot_error,
    snapshot_from_command_results,
    upsert_snapshot,
)


def test_eligible_requires_monitor_and_svc_profile():
    assert is_lun_offline_inventory_eligible(
        {"device_profile": "flashsystem_7200"}, monitor_on=True
    )
    assert not is_lun_offline_inventory_eligible(
        {"device_profile": "flashsystem_7200"}, monitor_on=False
    )
    assert not is_lun_offline_inventory_eligible(
        {"device_profile": "hpe_3par_8200"}, monitor_on=True
    )


def test_snapshot_from_command_results_parses_hosts_and_volumes():
    results = [
        {
            "label": "FC - Hosts",
            "command": "svcinfo lshost -delim :",
            "output": "id:name:port_count:iogrp_count:status:WWPN\n0:esx01:1:1:online:AABBCCDDEEFF0011",
        },
        {
            "label": "Memory - Volumes %",
            "command": "svcinfo lsvdisk -delim :",
            "output": "id:name:IO_group_id:IO_group_name:status:mdisk_grp_name:capacity\n0:vol1:0:io_grp0:online:Pool1:10.00GB",
        },
    ]
    snap = snapshot_from_command_results(
        card_id=7,
        site_name="Pendergrass, GA",
        host="10.0.0.7",
        device_profile="flashsystem_5200",
        command_results=results,
        updated_at="2026-07-30T12:00:00+00:00",
    )
    assert snap["card_id"] == 7
    assert snap["site_name"] == "Pendergrass, GA"
    assert snap["updated_at"] == "2026-07-30T12:00:00+00:00"
    assert snap["last_error"] in (None, "")
    assert any(h.get("lpar_name") == "esx01" for h in snap["hosts"])
    assert any(v.get("name") == "vol1" for v in snap["volumes"])


def test_failed_refresh_keeps_prior_hosts():
    store = upsert_snapshot(
        {},
        {
            "card_id": 1,
            "site_name": "Hartford, CT",
            "host": "10.0.0.1",
            "device_profile": "flashsystem_7200",
            "updated_at": "2026-07-30T10:00:00+00:00",
            "hosts": [{"lpar_name": "keepme", "wwpn1": "", "wwpn2": ""}],
            "volumes": [{"name": "v1", "pool": "P", "capacity": "1GB", "status": "online"}],
            "last_error": None,
            "last_error_at": None,
        },
    )
    store = record_snapshot_error(
        store, card_id=1, error="SSH timed out", site_name="Hartford, CT"
    )
    row = store["1"]
    assert row["hosts"][0]["lpar_name"] == "keepme"
    assert row["volumes"][0]["name"] == "v1"
    assert row["updated_at"] == "2026-07-30T10:00:00+00:00"
    assert "timed out" in row["last_error"].lower()
    assert row["last_error_at"]


def test_upsert_replaces_same_card():
    store = upsert_snapshot({}, {"card_id": 2, "site_name": "A", "hosts": [], "volumes": []})
    store = upsert_snapshot(
        store,
        {
            "card_id": 2,
            "site_name": "Windsor, WI",
            "hosts": [{"lpar_name": "h1"}],
            "volumes": [],
            "updated_at": "2026-07-30T11:00:00+00:00",
        },
    )
    assert list(store.keys()) == ["2"]
    assert store["2"]["site_name"] == "Windsor, WI"
    assert store["2"]["hosts"][0]["lpar_name"] == "h1"


def test_normalize_store_accepts_list_or_map():
    assert normalize_store({"3": {"card_id": 3, "hosts": [], "volumes": []}})["3"]["card_id"] == 3
    assert normalize_store([{"card_id": 4, "hosts": [], "volumes": []}])["4"]["card_id"] == 4
```

Adjust sample CLI table headers if existing parsers require different columns — match whatever `parse_fc_hosts` / `parse_lsvdisk_volumes` already accept in other tests (prefer copying a minimal fixture from `tests/test_inventory_sync.py` or FC parse tests).

- [ ] **Step 2: Run tests to verify they fail**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\lun-offline-inventory
python -m pytest tests/test_lun_offline_inventory.py -v
```

Expected: FAIL (module missing / import error).

- [ ] **Step 3: Implement `launchpad/lun_offline_inventory.py`**

Implement the interfaces above. Keep imports at module top. Reuse:

```python
from launchpad.flashsystem_fc import (
    parse_fabric_logins,
    parse_fc_hosts,
    parse_host_lun_maps,
    parse_lsvdisk_volumes,
)
from launchpad.inventory_sync import build_inventory_sync
from launchpad.storage_presets import is_svc_fc_profile
```

Helper to pick command output:

```python
def _outputs_for(command_results, *needles: str) -> str:
    for item in command_results or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        blob = f"{item.get('label') or ''} {item.get('command') or ''}".lower()
        if any(n in blob for n in needles):
            return str(item.get("output") or "")
    return ""
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/test_lun_offline_inventory.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_offline_inventory.py tests/test_lun_offline_inventory.py
git commit -m "Add LUN offline inventory snapshot helpers."
```

---

### Task 2: HealthServer persistence, refresh hooks, GET API

**Files:**
- Modify: `launchpad/health_server.py`
- Create: `tests/test_lun_offline_inventory_api.py`

**Interfaces:**
- `HealthServer.get_lun_offline_inventory() -> dict[str, dict]`
- `HealthServer.set_lun_offline_inventory(store: dict[str, dict]) -> dict[str, dict]`
  - Raises `RuntimeError` if settings backend missing (same message style as LUN builds)
- `HealthServer.upsert_lun_offline_inventory_from_card(card: HealthCard, *, monitor_on: bool | None = None, success: bool | None = None) -> None`
  - Resolve `monitor_on` via `is_monitor_enabled(card.card_id)` when None
  - Skip if not eligible
  - If settings backend missing: return quietly (no raise from refresh path)
  - `success` default: `command_results` present and not every item errored, and `card.error` is None **or** partial results still parseable — **locked rule:** treat as success when `command_results` is a non-empty list and at least one item has no `error`; else failure
  - Success → `snapshot_from_command_results` + `upsert_snapshot` + `set_lun_offline_inventory`
  - Failure → `record_snapshot_error` + set
- Call `upsert_lun_offline_inventory_from_card(card)` at end of `refresh_card` (after updating card fields) and at end of successful `update_card_live_data` when `command_results is not None`
- GET handler:
  - `/api/lun-offline-inventory` → `{ "ok": true, "snapshots": [summarize...] }`
  - `/api/lun-offline-inventory?card_id=N` → if missing/invalid int: 400; if unknown: `{ "ok": false, "snapshot": null, "error": "…" }` HTTP 200; else `{ "ok": true, "snapshot": full }`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_lun_offline_inventory_api.py
import inspect
import json

from launchpad.health_server import HealthCard, HealthServer, _HealthHandler


def _unlock(server: HealthServer) -> None:
    store: dict[str, str] = {}

    def get_setting(key: str, default: str = "") -> str:
        return store.get(key, default)

    def set_setting(key: str, value: str) -> None:
        store[key] = value

    server.set_settings_backend(get_setting, set_setting)


def _card(**kwargs) -> HealthCard:
    base = dict(
        card_id=1,
        name="Pendergrass, GA",
        host="10.0.0.9",
        port=22,
        username="user",
        key_path="/tmp/key",
        device_profile="flashsystem_5200",
    )
    base.update(kwargs)
    return HealthCard(**base)


def test_upsert_persists_and_replaces(monkeypatch):
    server = HealthServer()
    _unlock(server)
    server._cards[1] = _card()
    server.set_monitor_enabled(card_id=1, enabled=True)
    card = server._cards[1]
    card.command_results = [
        {
            "label": "FC - Hosts",
            "command": "svcinfo lshost -delim :",
            "output": "id:name:WWPN\n0:esx01:AA",
        }
    ]
    card.error = None
    server.upsert_lun_offline_inventory_from_card(card)
    store = server.get_lun_offline_inventory()
    assert "1" in store
    assert store["1"]["site_name"] == "Pendergrass, GA"


def test_failed_refresh_preserves_hosts():
    server = HealthServer()
    _unlock(server)
    server._cards[1] = _card()
    server.set_monitor_enabled(card_id=1, enabled=True)
    card = server._cards[1]
    card.command_results = [
        {"label": "FC - Hosts", "command": "svcinfo lshost -delim :", "output": "id:name:WWPN\n0:keep:AA"}
    ]
    card.error = None
    server.upsert_lun_offline_inventory_from_card(card)
    card.command_results = None
    card.error = "SSH failed"
    server.upsert_lun_offline_inventory_from_card(card)
    row = server.get_lun_offline_inventory()["1"]
    assert any(h.get("lpar_name") == "keep" for h in row["hosts"])
    assert "ssh" in (row.get("last_error") or "").lower()


def test_skips_monitor_off():
    server = HealthServer()
    _unlock(server)
    server._cards[1] = _card()
    server.set_monitor_enabled(card_id=1, enabled=False)
    card = server._cards[1]
    card.command_results = [{"label": "FC - Hosts", "command": "svcinfo lshost", "output": "x"}]
    server.upsert_lun_offline_inventory_from_card(card)
    assert server.get_lun_offline_inventory() == {}


def test_api_route_declared():
    assert "/api/lun-offline-inventory" in inspect.getsource(_HealthHandler.do_GET)


def test_refresh_card_calls_upsert(monkeypatch):
    server = HealthServer()
    _unlock(server)
    called = {}

    def fake_upsert(card, **kwargs):
        called["id"] = card.card_id

    monkeypatch.setattr(server, "upsert_lun_offline_inventory_from_card", fake_upsert)
    monkeypatch.setattr(
        "launchpad.health_server.run_remote_command_suite",
        lambda *a, **k: [{"label": "FC - Hosts", "command": "svcinfo lshost", "output": "id:name\n0:h1"}],
    )
    monkeypatch.setattr(
        "launchpad.health_server.resolve_card_commands",
        lambda *a, **k: [("FC - Hosts", "svcinfo lshost -delim :")],
    )
    server._cards[1] = _card()
    server.set_monitor_enabled(card_id=1, enabled=True)
    server.refresh_card(1)
    assert called.get("id") == 1
```

Tune `run_remote_command_suite` / `resolve_card_commands` patch targets to match actual import sites in `health_server.py`.

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
python -m pytest tests/test_lun_offline_inventory_api.py -v
```

- [ ] **Step 3: Implement HealthServer + GET route**

Place persistence methods near `get_lun_builds` / `set_lun_builds`. Import helpers from `launchpad.lun_offline_inventory`. Wire GET next to other LUN routes.

- [ ] **Step 4: Run tests — expect PASS**

```powershell
python -m pytest tests/test_lun_offline_inventory.py tests/test_lun_offline_inventory_api.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_lun_offline_inventory_api.py
git commit -m "Persist LUN offline inventory on Monitor refresh."
```

---

### Task 3: LUN Builder Plan | Inventory UI

**Files:**
- Modify: `launchpad/lun_builder.py`
- Create: `tests/test_lun_builder_offline_ui.py`

**UI requirements (markers must appear in HTML string):**
- Toggle control: `id="view-mode-plan"` and `id="view-mode-inventory"` (or a single `id="view-mode"` select with values `plan` / `inventory`) — prefer two buttons: `id="view-mode-plan"` / `id="view-mode-inventory"`
- Banner: `id="inventory-banner"`
- Text markers: `Online · last updated`, `Offline copy · last updated`, `Inventory · Updated`
- Fetch: `/api/lun-offline-inventory`
- When Inventory mode: render read-only hosts + volumes tables from snapshot; disable plan edit actions (Save / Add host / Add LUN / Sync / Pull / Import / Preview / Run) or leave them but do not mutate inventory store from UI
- Build picker: for each snapshot, if no build name matches `site_name` (case-insensitive), add option `value="inventory:<card_id>"` labeled `{site_name} (inventory only)`
- Matching: when selected build’s `name` or `default_card_hint` or `location` equals snapshot `site_name`, show inventory badge in status/picker

**Banner logic (JS):**
- Load `/api/cards` (or use snapshot only): if matching card has `error` or missing live results → `Offline copy · last updated {local timestamp}`
- Else → `Online · last updated {local timestamp}`
- Always use snapshot `updated_at` for the timestamp display

- [ ] **Step 1: Failing marker test**

```python
# tests/test_lun_builder_offline_ui.py
from launchpad.lun_builder import LUN_BUILDER_HTML


def test_lun_builder_offline_inventory_markers():
    assert 'id="view-mode-plan"' in LUN_BUILDER_HTML
    assert 'id="view-mode-inventory"' in LUN_BUILDER_HTML
    assert 'id="inventory-banner"' in LUN_BUILDER_HTML
    assert "/api/lun-offline-inventory" in LUN_BUILDER_HTML
    assert "Offline copy · last updated" in LUN_BUILDER_HTML
    assert "Online · last updated" in LUN_BUILDER_HTML
    assert "Inventory · Updated" in LUN_BUILDER_HTML
    assert "inventory only" in LUN_BUILDER_HTML
```

Confirm the HTML constant name (`LUN_BUILDER_HTML` vs similar) by reading `lun_builder.py` exports.

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_lun_builder_offline_ui.py -v
```

- [ ] **Step 3: Implement UI in `lun_builder.py`**

Minimal JS sketch to place near existing build load:

```javascript
let viewMode = "plan"; // "plan" | "inventory"
let offlineSnapshots = {}; // card_id -> snapshot

async function loadOfflineInventory() {
  const res = await fetch("/api/lun-offline-inventory");
  const data = await res.json().catch(() => ({}));
  offlineSnapshots = {};
  for (const row of (data.snapshots || [])) {
    offlineSnapshots[String(row.card_id)] = row;
  }
  // also fetch full snapshots on demand when entering inventory mode
}

function setViewMode(mode) {
  viewMode = mode;
  document.getElementById("view-mode-plan").classList.toggle("active", mode === "plan");
  document.getElementById("view-mode-inventory").classList.toggle("active", mode === "inventory");
  const banner = document.getElementById("inventory-banner");
  // show banner only in inventory mode; render read-only tables or plan tables
  renderCurrent();
}
```

Keep CSS consistent with existing dark LUN Builder styling (small toggle buttons near the build picker).

- [ ] **Step 4: Run markers + prior tests**

```powershell
python -m pytest tests/test_lun_builder_offline_ui.py tests/test_lun_offline_inventory.py tests/test_lun_offline_inventory_api.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder.py tests/test_lun_builder_offline_ui.py
git commit -m "Add LUN Builder Plan/Inventory offline view."
```

---

### Task 4: Version bump + smoke

**Files:**
- Modify: `launchpad/config.py` → `APP_VERSION = "1.6.90"`
- Modify: existing version assertion test if present (search `1.6.89` / `APP_VERSION` in tests)

- [ ] **Step 1: Bump version**

```python
APP_VERSION = "1.6.90"
```

- [ ] **Step 2: Run focused + any version test**

```powershell
python -m pytest tests/test_lun_offline_inventory.py tests/test_lun_offline_inventory_api.py tests/test_lun_builder_offline_ui.py -v
python -c "from launchpad.config import APP_VERSION; assert APP_VERSION == '1.6.90'"
```

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump LaunchPad to 1.6.90 for LUN offline inventory."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| `lun_offline_inventory` settings key | 1–2 |
| Auto upsert on successful Monitor refresh | 2 (`refresh_card` + `update_card_live_data`) |
| All Monitor-on FlashSystem/SVC cards | 1 eligibility + 2 |
| Failed refresh keeps prior snapshot | 1 + 2 |
| Plan never overwritten by auto refresh | 2 (writes only new store) |
| GET list + by card_id | 2 |
| Unknown card_id soft failure | 2 |
| Plan \| Inventory UI + banner + badges | 3 |
| Inventory-only sites without a plan build | 3 |
| Version 1.6.90 | 4 |
| Sync/Pull/Export unchanged | (no edits to those paths) |

## Self-review notes

- No TBD placeholders.
- Snapshot host shaping uses `build_inventory_sync` so Inventory view matches LUN Builder host columns (`lpar_name`, `wwpn1`, `wwpn2`).
- Desktop live pushes go through `update_card_live_data` — both hooks required or offline copy would miss GUI refreshes.
