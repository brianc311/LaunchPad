# Site Lookup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Site Lookup hub + per-card detail pages so operators browse live hosts/volumes/mappings/CGs with search, cache-first paint, and SSH Refresh — without per-site HTML files.

**Architecture:** Pure helpers in `site_lookup_data.py` shape cache and SSH payloads; `parse_lsconsistgrp` extends FC parsers; `HealthServer` serves `/site-lookup` and `POST /api/site-lookup/refresh`; UI lives in `site_lookup.py` (hub + detail). Reuse SSH Inventory Sync parsers (`parse_fc_hosts`, `parse_lsvdisk_volumes`, `parse_host_lun_maps`, `_lun_run_command`).

**Tech Stack:** HealthServer embedded HTML, `/api/cards`, `run_remote_ssh_command`, Contingency Groups settings store, pytest.

**Spec:** `docs/superpowers/specs/2026-07-22-site-lookup-design.md`

## Global Constraints

- **Base branch:** `origin/feature/ssh-inventory-sync` (has `parse_lsvdisk_volumes` + `inventory_sync` / Sync Inventory). Do not base on bare `feature/contingency-groups` without that merge.
- New page `/site-lookup` only; hub opens detail in a **new tab** via `?card=<id>`
- Hybrid: cache from `/api/cards` first; Refresh = live SSH
- Tabs: Hosts | Volumes | Mappings | Consistency groups + four stat tiles
- CGs: live `lsconsistgrp` when non-empty; else Contingency Groups matched by card name / storage_hint / location
- Dropdown: all cards with `device_profile in SVC_PROFILES`
- Read-only; no import of Downloads HTML snapshots
- No System/Pools tab in v1
- Bump `APP_VERSION` to next patch after sync tip (`1.6.44` if tip is `1.6.43`)
- Commit at each task’s commit step

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/site_lookup_data.py` | Pure: SVC filter, cache→payload, SSH lists→payload, CG fallback match, stats |
| `launchpad/flashsystem_fc.py` | Add `parse_lsconsistgrp` |
| `launchpad/site_lookup.py` | `SITE_LOOKUP_PATH`, `SITE_LOOKUP_HTML` (hub + detail) |
| `launchpad/health_server.py` | GET page, `POST /api/site-lookup/refresh`, `open_site_lookup`, optional `serial_number` in `to_api` |
| `launchpad/monitor.py` | `open_site_lookup_for_cards` |
| `launchpad/ui/dashboard_view.py` | **Site Lookup** button |
| `launchpad/config.py` | Version bump |
| `tests/test_site_lookup_data.py` | Pure helpers |
| `tests/test_site_lookup_api.py` | Refresh API (mocked SSH) |
| `tests/test_site_lookup_page.py` | HTML path / wiring smoke |

---

### Task 0: Branch / worktree

**Files:** none (git only)

**Interfaces:**
- Consumes: `origin/feature/ssh-inventory-sync` (includes design + sync parsers)
- Produces: `feature/site-lookup` worktree

- [ ] **Step 1: Create worktree**

```powershell
git fetch origin
git -C "C:\Users\BrianColley\LaunchPad" worktree add .worktrees/site-lookup -b feature/site-lookup origin/feature/ssh-inventory-sync
cd C:\Users\BrianColley\LaunchPad\.worktrees\site-lookup
```

If `origin/feature/ssh-inventory-sync` is unavailable, use local `feature/ssh-inventory-sync` or the existing `.worktrees/ssh-inventory-sync` tip as the start point, then create `feature/site-lookup` from that commit.

- [ ] **Step 2: Confirm baseline**

```powershell
python -c "from launchpad.config import APP_VERSION; from launchpad.flashsystem_fc import parse_lsvdisk_volumes; print(APP_VERSION); print(callable(parse_lsvdisk_volumes))"
```

Expected: `1.6.43` (or sync tip) and `True`.

- [ ] **Step 3: Cherry-pick / ensure Site Lookup design is present**

If the design commit is only on `feature/contingency-groups`:

```powershell
git cherry-pick ea75196
```

Skip if `docs/superpowers/specs/2026-07-22-site-lookup-design.md` already exists on the branch.

- [ ] **Step 4: No feature commit** (cherry-pick only if needed)

---

### Task 1: Pure data helpers (filter, cache payload, CG fallback)

**Files:**
- Create: `launchpad/site_lookup_data.py`
- Create: `tests/test_site_lookup_data.py`

**Interfaces:**
- Consumes: `SVC_PROFILES`; card `to_api`-shaped dicts; Contingency Groups `normalize_group` shape
- Produces:
  - `is_svc_card(card: dict) -> bool`
  - `filter_svc_cards(cards: list[dict]) -> list[dict]`
  - `match_contingency_groups(groups: list[dict], *, card_name: str) -> list[dict]`
  - `payload_from_card_cache(card: dict, *, contingency_groups: list[dict] | None = None) -> dict`
  - `payload_from_ssh(*, card: dict, hosts: list[dict], volumes: list[dict], maps: list[dict], consist_groups: list[dict], contingency_groups: list[dict] | None = None, refreshed_at: str | None = None) -> dict`
  - Payload keys: `card`, `stats`, `hosts`, `volumes`, `mappings`, `consistency_groups`, `source`, `refreshed_at`, `error`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_site_lookup_data.py
from launchpad.site_lookup_data import (
    filter_svc_cards,
    match_contingency_groups,
    payload_from_card_cache,
    payload_from_ssh,
)


def test_filter_svc_cards_keeps_flashsystem_only():
    cards = [
        {"id": 1, "name": "and", "device_profile": "flashsystem_7200"},
        {"id": 2, "name": "3par", "device_profile": "hp_3par_7200"},
    ]
    out = filter_svc_cards(cards)
    assert [c["id"] for c in out] == [1]


def test_match_contingency_groups_by_name_or_hint():
    groups = [
        {"id": "a", "name": "Anderson", "location": "IN", "storage_hint": "v7kand-g3v1", "hosts": [], "volumes": [], "maps": []},
        {"id": "b", "name": "Other", "location": "X", "storage_hint": "other", "hosts": [], "volumes": [], "maps": []},
    ]
    matched = match_contingency_groups(groups, card_name="v7kand-g3v1")
    assert [g["id"] for g in matched] == ["a"]


def test_payload_from_card_cache_uses_fc_and_cg_fallback():
    card = {
        "id": 9,
        "name": "v7kand-g3v1",
        "host": "10.0.0.1",
        "model": "IBM FlashSystem 7200",
        "device_profile": "flashsystem_7200",
        "serial_number": "78E31NF",
        "fc_hosts": [{"host_name": "h1", "status": "online", "port_count": "2"}],
        "fc_mappings": [
            {"host_name": "h1", "vdisk_name": "vol1", "scsi_id": "0", "io_group_name": "io_grp0"}
        ],
    }
    groups = [
        {
            "id": "cg1",
            "name": "v7kand-g3v1",
            "location": "Anderson",
            "storage_hint": "v7kand-g3v1",
            "hosts": [],
            "volumes": [{"name": "vol1"}],
            "maps": [],
        }
    ]
    payload = payload_from_card_cache(card, contingency_groups=groups)
    assert payload["stats"]["hosts"] == 1
    assert payload["stats"]["mappings"] == 1
    assert payload["stats"]["cgs"] == 1
    assert payload["source"] == "cache"
    assert payload["volumes"]  # derived from mappings and/or CG volumes
    assert payload["error"] is None


def test_payload_from_ssh_prefers_live_cgs():
    card = {"id": 1, "name": "site", "host": "1.2.3.4", "model": "FS", "device_profile": "flashsystem_5200"}
    payload = payload_from_ssh(
        card=card,
        hosts=[{"host_name": "h1", "status": "online", "port_count": "2"}],
        volumes=[{"name": "v1", "uid": "U1", "capacity": "10GB", "pool": "P0", "status": "online"}],
        maps=[{"host_name": "h1", "vdisk_name": "v1", "scsi_id": "0", "io_group_name": "io_grp0"}],
        consist_groups=[{"id": "1", "name": "cg_live", "status": "empty"}],
        contingency_groups=[{"id": "x", "name": "site", "location": "", "storage_hint": "site", "hosts": [], "volumes": [], "maps": []}],
        refreshed_at="2026-07-22T12:00:00Z",
    )
    assert payload["source"] == "ssh"
    assert payload["stats"]["cgs"] == 1
    assert payload["consistency_groups"][0]["name"] == "cg_live"


def test_payload_from_ssh_falls_back_to_contingency_groups():
    card = {"id": 1, "name": "site", "host": "1.2.3.4", "model": "FS", "device_profile": "flashsystem_5200"}
    payload = payload_from_ssh(
        card=card,
        hosts=[],
        volumes=[],
        maps=[],
        consist_groups=[],
        contingency_groups=[{"id": "x", "name": "site", "location": "L", "storage_hint": "site", "hosts": [], "volumes": [], "maps": []}],
        refreshed_at="2026-07-22T12:00:00Z",
    )
    assert payload["source"] == "ssh+cg_fallback"
    assert payload["stats"]["cgs"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_site_lookup_data.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement `launchpad/site_lookup_data.py`**

```python
from __future__ import annotations

from typing import Any

from launchpad.storage_presets import SVC_PROFILES


def is_svc_card(card: dict[str, Any]) -> bool:
    return str(card.get("device_profile") or "").strip() in SVC_PROFILES


def filter_svc_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [card for card in cards if is_svc_card(card)]


def _norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def match_contingency_groups(
    groups: list[dict[str, Any]], *, card_name: str
) -> list[dict[str, Any]]:
    key = _norm(card_name)
    if not key:
        return []
    matched: list[dict[str, Any]] = []
    for group in groups:
        needles = (
            group.get("name"),
            group.get("location"),
            group.get("storage_hint"),
            group.get("id"),
        )
        if any(_norm(item) == key for item in needles):
            matched.append(group)
    return matched


def _card_meta(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": card.get("id"),
        "name": str(card.get("name") or ""),
        "host": str(card.get("host") or ""),
        "model": str(card.get("model") or ""),
        "serial": str(card.get("serial_number") or card.get("serial") or ""),
        "device_profile": str(card.get("device_profile") or ""),
    }


def _host_row(raw: dict[str, Any]) -> dict[str, Any]:
    name = str(raw.get("host_name") or raw.get("name") or "").strip()
    return {
        "name": name,
        "status": str(raw.get("status") or ""),
        "type": str(raw.get("type") or "Generic"),
        "ports": str(raw.get("port_count") or raw.get("ports") or ""),
        "protocol": str(raw.get("protocol") or ""),
    }


def _volume_row(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(raw.get("name") or raw.get("vdisk_name") or "").strip(),
        "uid": str(raw.get("uid") or raw.get("vdisk_UID") or ""),
        "capacity": str(raw.get("capacity") or ""),
        "pool": str(raw.get("pool") or raw.get("mdisk_grp_name") or ""),
        "status": str(raw.get("status") or ""),
    }


def _map_row(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "host": str(raw.get("host_name") or raw.get("host") or "").strip(),
        "volume": str(raw.get("vdisk_name") or raw.get("volume") or raw.get("name") or "").strip(),
        "scsi_id": str(raw.get("scsi_id") or raw.get("SCSI_id") or ""),
        "io_group": str(raw.get("io_group_name") or raw.get("io_group") or ""),
    }


def _cg_row_from_live(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(raw.get("id") or ""),
        "name": str(raw.get("name") or "").strip(),
        "status": str(raw.get("status") or ""),
        "type": str(raw.get("type") or ""),
    }


def _cg_row_from_group(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(group.get("id") or ""),
        "name": str(group.get("name") or "").strip(),
        "status": "LaunchPad",
        "type": "contingency_group",
        "location": str(group.get("location") or ""),
        "volume_count": len(group.get("volumes") or []),
        "host_count": len(group.get("hosts") or []),
        "map_count": len(group.get("maps") or []),
    }


def _volumes_from_maps(maps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in maps:
        name = str(row.get("volume") or "").strip()
        if name and name not in seen:
            seen[name] = {"name": name, "uid": "", "capacity": "", "pool": "", "status": ""}
    return list(seen.values())


def _stats(hosts, volumes, mappings, cgs) -> dict[str, int]:
    return {
        "hosts": len(hosts),
        "volumes": len(volumes),
        "mappings": len(mappings),
        "cgs": len(cgs),
    }


def payload_from_card_cache(
    card: dict[str, Any],
    *,
    contingency_groups: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    hosts = [_host_row(h) for h in (card.get("fc_hosts") or []) if _host_row(h)["name"]]
    mappings = [_map_row(m) for m in (card.get("fc_mappings") or []) if _map_row(m)["host"] or _map_row(m)["volume"]]
    volumes = _volumes_from_maps(mappings)
    for vol in card.get("fc_volumes") or []:
        row = _volume_row(vol)
        if row["name"] and row["name"] not in {v["name"] for v in volumes}:
            volumes.append(row)
    matched = match_contingency_groups(
        contingency_groups or [], card_name=str(card.get("name") or "")
    )
    for group in matched:
        for vol in group.get("volumes") or []:
            row = _volume_row(vol if isinstance(vol, dict) else {"name": vol})
            if row["name"] and row["name"] not in {v["name"] for v in volumes}:
                volumes.append(row)
    cgs = [_cg_row_from_group(g) for g in matched]
    return {
        "card": _card_meta(card),
        "stats": _stats(hosts, volumes, mappings, cgs),
        "hosts": hosts,
        "volumes": volumes,
        "mappings": mappings,
        "consistency_groups": cgs,
        "source": "cache",
        "refreshed_at": None,
        "error": None,
    }


def payload_from_ssh(
    *,
    card: dict[str, Any],
    hosts: list[dict[str, Any]],
    volumes: list[dict[str, Any]],
    maps: list[dict[str, Any]],
    consist_groups: list[dict[str, Any]],
    contingency_groups: list[dict[str, Any]] | None = None,
    refreshed_at: str | None = None,
) -> dict[str, Any]:
    host_rows = [_host_row(h) for h in hosts if _host_row(h)["name"]]
    volume_rows = [_volume_row(v) for v in volumes if _volume_row(v)["name"]]
    map_rows = [_map_row(m) for m in maps if _map_row(m)["host"] or _map_row(m)["volume"]]
    live_cgs = [_cg_row_from_live(g) for g in consist_groups if str(g.get("name") or "").strip()]
    if live_cgs:
        cgs = live_cgs
        source = "ssh"
    else:
        matched = match_contingency_groups(
            contingency_groups or [], card_name=str(card.get("name") or "")
        )
        cgs = [_cg_row_from_group(g) for g in matched]
        source = "ssh+cg_fallback"
    return {
        "card": _card_meta(card),
        "stats": _stats(host_rows, volume_rows, map_rows, cgs),
        "hosts": host_rows,
        "volumes": volume_rows,
        "mappings": map_rows,
        "consistency_groups": cgs,
        "source": source,
        "refreshed_at": refreshed_at,
        "error": None,
    }
```

Keep helpers DRY; adjust `_map_row` double-call in cache if needed (compute once). Fix any test failures without weakening asserts.

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_site_lookup_data.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/site_lookup_data.py tests/test_site_lookup_data.py
git commit -m "Add Site Lookup payload helpers and CG fallback matching."
```

---

### Task 2: Parse `lsconsistgrp`

**Files:**
- Modify: `launchpad/flashsystem_fc.py`
- Modify: `tests/test_site_lookup_data.py` (or `tests/test_flashsystem_fc_consistgrp.py`)

**Interfaces:**
- Consumes: `_table_records`, `_get`
- Produces: `parse_lsconsistgrp(output: str) -> list[dict[str, str]]` with keys `id`, `name`, `status`, `type`

- [ ] **Step 1: Write the failing test**

```python
from launchpad.flashsystem_fc import parse_lsconsistgrp

SAMPLE = """id:name:type:status
0:cg_app:flash:empty
1:cg_db:flash:empty
"""

def test_parse_lsconsistgrp():
    rows = parse_lsconsistgrp(SAMPLE)
    assert [r["name"] for r in rows] == ["cg_app", "cg_db"]
    assert rows[0]["status"] == "empty"
```

- [ ] **Step 2: Run test — expect FAIL**

```powershell
pytest tests/test_site_lookup_data.py::test_parse_lsconsistgrp -v
```

(or the new test file path)

- [ ] **Step 3: Implement parser next to `parse_lsvdisk_volumes`**

```python
def parse_lsconsistgrp(output: str) -> list[dict[str, str]]:
    groups: list[dict[str, str]] = []
    for record in _table_records(output):
        name = _get(record, "name")
        if not name:
            continue
        groups.append(
            {
                "id": _get(record, "id"),
                "name": name,
                "status": _get(record, "status", "state"),
                "type": _get(record, "type"),
            }
        )
    return groups
```

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/flashsystem_fc.py tests/test_site_lookup_data.py
git commit -m "Parse FlashSystem consistency groups for Site Lookup."
```

---

### Task 3: HealthServer refresh API + open helpers

**Files:**
- Modify: `launchpad/health_server.py`
- Create: `tests/test_site_lookup_api.py`
- Modify: `launchpad/monitor.py`

**Interfaces:**
- Consumes: `payload_from_ssh`, parsers, `_lun_run_command` (or equivalent), `get_contingency_groups`, `SVC_PROFILES`
- Produces:
  - `HealthServer.refresh_site_lookup(card_id: int) -> dict`
  - `POST /api/site-lookup/refresh` body `{ "card_id": int }` → JSON payload or `{ "error": "..." }` with HTTP 400/404/502 as appropriate
  - On SSH failure: return JSON with `error` set and **empty lists only if no prior client state** — server returns `{ ok: false, error, card? }`; client keeps prior paint
  - `HealthServer.open_site_lookup() -> str`
  - `site_lookup_url` property
  - `monitor.open_site_lookup_for_cards(entries) -> str`
  - Expose `serial_number` on `HealthCard.to_api()`

- [ ] **Step 1: Write failing API tests** (mock `_lun_run_command` / SSH)

Pattern after existing health server lun-builder tests: construct `HealthServer`, register a fake `HealthCard` in `SVC_PROFILES`, stub run to return delimiter tables, assert payload stats and `source`.

```python
def test_refresh_site_lookup_success(monkeypatch):
    # register card id=1 profile flashsystem_5200
    # monkeypatch HealthServer._lun_run_command to return canned outputs per command
    # result = server.refresh_site_lookup(1)
    # assert result["stats"]["hosts"] >= 1
    # assert result["source"] in ("ssh", "ssh+cg_fallback")
    # assert result["error"] is None

def test_refresh_site_lookup_bad_card():
    # expect ValueError or KeyError → API 404

def test_refresh_site_lookup_ssh_failure(monkeypatch):
    # stub run to raise
    # API returns error string; do not require wiping semantics server-side beyond error field
```

Implement concrete fixtures with minimal `lshost` / `lsvdisk` / `lshostvdiskmap` / `lsconsistgrp` tables.

- [ ] **Step 2: Run — expect FAIL**

```powershell
pytest tests/test_site_lookup_api.py -v
```

- [ ] **Step 3: Implement `refresh_site_lookup`**

```python
def refresh_site_lookup(self, card_id: int) -> dict:
    with self._lock:
        card = self._cards.get(int(card_id))
    if card is None:
        raise KeyError(card_id)
    if card.device_profile not in SVC_PROFILES:
        raise ValueError("Site Lookup requires a FlashSystem / SVC card profile.")
    run = self._lun_run_command(card)
    hosts_out = run("svcinfo lshost -delim :")
    maps_out = run("svcinfo lshostvdiskmap -delim :")
    volumes_out = run("svcinfo lsvdisk -delim :")
    try:
        cg_out = run("svcinfo lsconsistgrp -delim :")
    except Exception:
        cg_out = ""
    from datetime import datetime, timezone
    from launchpad.flashsystem_fc import (
        parse_fc_hosts,
        parse_host_lun_maps,
        parse_lsconsistgrp,
        parse_lsvdisk_volumes,
    )
    from launchpad.site_lookup_data import payload_from_ssh
    meta = card.to_api()
    return payload_from_ssh(
        card=meta,
        hosts=parse_fc_hosts(hosts_out),
        volumes=parse_lsvdisk_volumes(volumes_out),
        maps=parse_host_lun_maps(maps_out),
        consist_groups=parse_lsconsistgrp(cg_out),
        contingency_groups=self.get_contingency_groups(),
        refreshed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
```

Wire POST handler: parse JSON `card_id`; on `KeyError` → 404; `ValueError` → 400; SSH/`RuntimeError` → 502 with `{"error": str(exc)}` (no inventory wipe on server).

Add `serial_number` to `to_api()` return dict.

Add `SITE_LOOKUP_PATH` import placeholder if page not yet present — either stub HTML in this task or land page in Task 4 first. Prefer implementing open URL + route stub that returns minimal HTML, then flesh out in Task 4.

- [ ] **Step 4: Add `open_site_lookup_for_cards` in `monitor.py`** (mirror FC WWPN: register entries, `open_site_lookup()`).

- [ ] **Step 5: Tests PASS**

- [ ] **Step 6: Commit**

```powershell
git add launchpad/health_server.py launchpad/monitor.py tests/test_site_lookup_api.py
git commit -m "Add Site Lookup refresh API and browser open helpers."
```

---

### Task 4: Site Lookup HTML (hub + detail)

**Files:**
- Create: `launchpad/site_lookup.py`
- Modify: `launchpad/health_server.py` (GET `SITE_LOOKUP_PATH`, import HTML)
- Create: `tests/test_site_lookup_page.py`

**Interfaces:**
- Consumes: `/api/cards`, `POST /api/site-lookup/refresh`, `payload_from_card_cache` logic in JS (client-side from cards + optional `GET /api/contingency-groups`)
- Produces: hub UI + detail UI; search filter; Refresh button

- [ ] **Step 1: Failing page smoke test**

```python
from launchpad.site_lookup import SITE_LOOKUP_HTML, SITE_LOOKUP_PATH

def test_site_lookup_path_and_markers():
    assert SITE_LOOKUP_PATH == "/site-lookup"
    assert "Site Lookup" in SITE_LOOKUP_HTML
    assert "/api/site-lookup/refresh" in SITE_LOOKUP_HTML
    assert "filterHostsVolumes" in SITE_LOOKUP_HTML or "id=\"q\"" in SITE_LOOKUP_HTML
```

- [ ] **Step 2: Implement `site_lookup.py`**

Follow Perrysburg/Anderson structure (dark theme, nameplate, 4 stats, tabs). Keep CSS self-contained in the HTML string (same pattern as `fc_wwpn_report.py`).

**Hub mode** (`!card` query param):
- Fetch `/api/cards`, filter `device_profile` against a JS list mirrored from known SVC keys **or** filter client-side by model/profile substring — prefer calling a tiny `GET /api/site-lookup/cards` that returns `filter_svc_cards` result to avoid duplicating profile sets. If adding that endpoint, keep it thin:

```python
# GET /api/site-lookup/cards → filter_svc_cards([c.to_api() for c in cards])
```

- `<select id="siteSelect">` + Open button → `window.open('/site-lookup?card=' + id)`

**Detail mode** (`card=<id>`):
- Load card from `/api/cards` + groups from `/api/contingency-groups`
- Build cache payload in JS **or** add `GET /api/site-lookup/detail?card=<id>` that returns `payload_from_card_cache`. Prefer server endpoint for one source of truth:

```python
# GET /api/site-lookup/detail?card=<id>
# → payload_from_card_cache(card.to_api(), contingency_groups=self.get_contingency_groups())
```

- Render nameplate, stats, tabs, tables
- Search input filters hosts/volumes tables and mappings by host or volume substring (case-insensitive)
- Refresh → POST refresh → replace state; on error show banner and keep prior rows
- Links: Hub, Health `/`, Capacity, FC WWPN

- [ ] **Step 3: Wire GET handlers in `health_server.py`**

```python
if path == SITE_LOOKUP_PATH:
    self._send_html(SITE_LOOKUP_HTML.replace("{{APP_VERSION}}", APP_VERSION))
```

Plus `/api/site-lookup/cards` and `/api/site-lookup/detail` as above.

- [ ] **Step 4: Tests PASS**

```powershell
pytest tests/test_site_lookup_page.py tests/test_site_lookup_api.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/site_lookup.py launchpad/health_server.py tests/test_site_lookup_page.py
git commit -m "Add Site Lookup hub and detail UI."
```

---

### Task 5: Dashboard button + cross-links + version

**Files:**
- Modify: `launchpad/ui/dashboard_view.py`
- Modify: `launchpad/capacity_report.py` and/or `launchpad/fc_wwpn_report.py` (add Site Lookup secondary link in hero actions — match existing secondary btn pattern)
- Modify: `launchpad/config.py`
- Modify tests if they assert `APP_VERSION` or button labels

**Interfaces:**
- Consumes: `open_site_lookup_for_cards`
- Produces: dashboard **Site Lookup** button; version `1.6.44`

- [ ] **Step 1: Add dashboard button** next to FC WWPN / Contingency Groups (shift grid columns as needed). Handler mirrors `_open_fc_wwpn_report_all` but calls `open_site_lookup_for_cards(entries)`.

- [ ] **Step 2: Add header link** `href="/site-lookup"` on Capacity and FC WWPN hero action rows.

- [ ] **Step 3: Bump version**

```python
APP_VERSION = "1.6.44"
```

- [ ] **Step 4: Run focused suite**

```powershell
pytest tests/test_site_lookup_data.py tests/test_site_lookup_api.py tests/test_site_lookup_page.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/dashboard_view.py launchpad/capacity_report.py launchpad/fc_wwpn_report.py launchpad/config.py
git commit -m "Expose Site Lookup in dashboard and bump to 1.6.44."
```

---

### Task 6: Manual smoke checklist (no commit required unless fixes)

- [ ] **Step 1:** From worktree, run LaunchPad (or `python -m launchpad` / usual entry), click **Site Lookup**
- [ ] **Step 2:** Hub lists SVC cards only; Open opens new tab with nameplate
- [ ] **Step 3:** Cache paint shows hosts/maps if monitor data present
- [ ] **Step 4:** Refresh against a reachable array updates stats; kill SSH / bad password → banner, tables remain
- [ ] **Step 5:** Search filters host and volume names
- [ ] **Step 6:** If issues, fix + commit `Fix Site Lookup smoke findings.`

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| `/site-lookup` hub + detail new tab | 4, 5 |
| All SVC cards in dropdown | 1, 4 |
| Hybrid cache + SSH Refresh | 1, 3, 4 |
| Hosts/Volumes/Mappings/CGs + stats | 1, 4 |
| CG live then Contingency Groups fallback | 1, 2, 3 |
| Search host + volume names | 4 |
| Error handling keep cache | 3, 4 |
| Dashboard button | 5 |
| Tests | 1–4 |
| No HTML snapshot import | honored (non-goal) |
| No System/Pools v1 | honored |

No TBD placeholders remain. Payload field names are consistent across tasks (`stats.hosts|volumes|mappings|cgs`, `source`, `refreshed_at`, `error`).
