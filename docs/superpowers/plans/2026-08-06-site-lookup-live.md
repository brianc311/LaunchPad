# Site Lookup Live (Tempe-style) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Tempe-style Site Lookup page at `/site-lookup` listing all LaunchPad SSH cards, with Live Refresh filling pools (A) and hosts/volumes/CGs (B).

**Architecture:** Pure helpers in `site_lookup_data.py` shape cache and live payloads (including pools). `parse_lsconsistgrp` in `flashsystem_fc.py`. HealthServer serves the page and `POST /api/site-lookup/refresh` (calls `refresh_card` then shapes inventory + CG fallback). UI in `site_lookup.py` (one-page Tempe layout). Dashboard button via `monitor.open_site_lookup_for_cards`.

**Tech Stack:** HealthServer embedded HTML/JS, `/api/cards`, `refresh_card` / `_lun_run_command`, Contingency Groups store, pytest.

**Spec:** `docs/superpowers/specs/2026-08-06-site-lookup-live-design.md`  
**Supersedes plan:** `docs/superpowers/plans/2026-07-22-site-lookup.md` (do not follow the old hub→new-tab / SVC-only / no-pools plan).

## Global Constraints

- Work on current feature branch tip (`feature/hpe-capacity-parse` or successor); APP_VERSION bump to next patch after tip when shipping (coordinate with jiggler plan if same release).
- Page: `/site-lookup` — **one page** with search/picker + in-place result (Tempe), not hub→new-tab.
- Site list: **all** SSH storage cards from `/api/cards` (not SVC-only).
- Tabs: Hosts · Volumes · Consistency Groups · Pools.
- Live Refresh = A (capacity/pools via `refresh_card`) + B (hosts/volumes/maps/CGs from results + `lsconsistgrp` when SVC).
- CG rule: live CGs if non-empty; else Contingency Groups match; else empty.
- Read-only; do not import Downloads HTML as data.
- Refresh failure: return `{ "error": "..." }` JSON; client keeps prior paint.
- Windows PowerShell commits (here-string).
- Commit at each task’s commit step.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/site_lookup_data.py` | Pure: card list filter, cache→payload, live→payload, CG match, pool/stats shape |
| `launchpad/flashsystem_fc.py` | Add `parse_lsconsistgrp` |
| `launchpad/site_lookup.py` | `SITE_LOOKUP_PATH`, Tempe-adapted `SITE_LOOKUP_HTML` |
| `launchpad/health_server.py` | GET page, POST refresh, `refresh_site_lookup`, `open_site_lookup` |
| `launchpad/monitor.py` | `open_site_lookup_for_cards` |
| `launchpad/ui/dashboard_view.py` | **Site Lookup** tool button |
| `launchpad/config.py` | Version bump (shared with jiggler if same ship) |
| `tests/test_site_lookup_data.py` | Pure helpers |
| `tests/test_site_lookup_api.py` | Refresh API (mocked) |
| `tests/test_site_lookup_page.py` | HTML/path/wiring smoke |

---

### Task 1: Pure data helpers (all cards, pools, CG fallback)

**Files:**
- Create: `launchpad/site_lookup_data.py`
- Create: `tests/test_site_lookup_data.py`

**Interfaces:**
- Consumes: card `to_api`-shaped dicts; Contingency Groups list; optional hosts/volumes/maps/consist_groups/pools lists
- Produces:
  - `filter_lookup_cards(cards: list[dict]) -> list[dict]` — keep cards with usable `id` + `name` (all SSH cards)
  - `match_contingency_groups(groups: list[dict], *, card_name: str) -> list[dict]`
  - `payload_from_card_cache(card: dict, *, contingency_groups: list[dict] | None = None) -> dict`
  - `payload_from_live(*, card: dict, hosts: list[dict], volumes: list[dict], maps: list[dict], consist_groups: list[dict], pools: list[dict] | None = None, contingency_groups: list[dict] | None = None, refreshed_at: str | None = None) -> dict`
  - Payload keys: `card`, `stats` (`hosts`, `volumes`, `pools`, `nodes`), `hosts`, `volumes`, `mappings`, `consistency_groups`, `pools`, `source`, `refreshed_at`, `error`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_site_lookup_data.py
from launchpad.site_lookup_data import (
    filter_lookup_cards,
    match_contingency_groups,
    payload_from_card_cache,
    payload_from_live,
)


def test_filter_lookup_cards_keeps_all_named_ssh_cards():
    cards = [
        {"id": 1, "name": "and", "device_profile": "flashsystem_7200"},
        {"id": 2, "name": "3par", "device_profile": "hp_3par_7200"},
        {"id": 3, "name": "", "device_profile": "flashsystem_5200"},
    ]
    out = filter_lookup_cards(cards)
    assert [c["id"] for c in out] == [1, 2]


def test_match_contingency_groups_by_name_or_hint():
    groups = [
        {"id": "a", "name": "Anderson", "location": "IN", "storage_hint": "v7kand-g3v1", "hosts": [], "volumes": [], "maps": []},
        {"id": "b", "name": "Other", "location": "X", "storage_hint": "other", "hosts": [], "volumes": [], "maps": []},
    ]
    matched = match_contingency_groups(groups, card_name="v7kand-g3v1")
    assert [g["id"] for g in matched] == ["a"]


def test_payload_from_card_cache_uses_fc_pools_and_cg_fallback():
    card = {
        "id": 9,
        "name": "v7kand-g3v1",
        "host": "10.0.0.1",
        "model": "IBM FlashSystem 7200",
        "device_profile": "flashsystem_7200",
        "fc_hosts": [{"host_name": "h1", "status": "online", "port_count": "2"}],
        "fc_mappings": [
            {"host_name": "h1", "vdisk_name": "vol1", "scsi_id": "0", "io_group_name": "io_grp0"}
        ],
        "pools": [{"name": "P0", "total_bytes": 1000, "used_bytes": 400, "free_bytes": 600, "used_pct": 40.0}],
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
    assert payload["stats"]["pools"] == 1
    assert payload["stats"]["cgs"] == 1 or payload["stats"].get("consistency_groups") == 1 or len(payload["consistency_groups"]) == 1
    assert payload["pools"][0]["name"] == "P0"
    assert payload["source"] == "cache"
    assert payload["error"] is None


def test_payload_from_live_prefers_live_cgs():
    card = {"id": 1, "name": "site", "host": "1.2.3.4", "model": "FS", "device_profile": "flashsystem_5200"}
    payload = payload_from_live(
        card=card,
        hosts=[{"host_name": "h1", "status": "online", "port_count": "2"}],
        volumes=[{"name": "v1", "uid": "U1", "capacity": "10GB", "pool": "P0", "status": "online"}],
        maps=[{"host_name": "h1", "vdisk_name": "v1", "scsi_id": "0", "io_group_name": "io_grp0"}],
        consist_groups=[{"id": "1", "name": "cg_live", "status": "empty"}],
        pools=[{"name": "P0", "total_bytes": 100, "used_bytes": 50, "free_bytes": 50, "used_pct": 50.0}],
        contingency_groups=[{"id": "x", "name": "site", "location": "", "storage_hint": "site", "hosts": [], "volumes": [], "maps": []}],
        refreshed_at="2026-08-06T12:00:00Z",
    )
    assert payload["source"] == "ssh"
    assert payload["consistency_groups"][0]["name"] == "cg_live"
    assert payload["stats"]["pools"] == 1
    assert payload["refreshed_at"] == "2026-08-06T12:00:00Z"


def test_payload_from_live_falls_back_to_contingency_groups():
    card = {"id": 1, "name": "site", "host": "1.2.3.4", "model": "FS", "device_profile": "flashsystem_5200"}
    payload = payload_from_live(
        card=card,
        hosts=[],
        volumes=[],
        maps=[],
        consist_groups=[],
        pools=[],
        contingency_groups=[{"id": "x", "name": "site", "location": "L", "storage_hint": "site", "hosts": [], "volumes": [], "maps": []}],
        refreshed_at="2026-08-06T12:00:00Z",
    )
    assert payload["source"] == "ssh+cg_fallback"
    assert len(payload["consistency_groups"]) == 1
```

Use **one** stats key for CG count: prefer `stats["consistency_groups"]` (integer). Update the cache test assertion to `assert payload["stats"]["consistency_groups"] == 1` and implement that key (also set `stats["hosts"]`, `stats["volumes"]`, `stats["pools"]`, `stats["nodes"]` default 0).

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
pytest tests/test_site_lookup_data.py -v
```

Expected: ImportError / module missing.

- [ ] **Step 3: Implement `launchpad/site_lookup_data.py`**

```python
"""Pure helpers for Site Lookup payloads."""

from __future__ import annotations

from typing import Any


def filter_lookup_cards(cards: list[dict]) -> list[dict]:
    out: list[dict] = []
    for card in cards:
        if card.get("id") is None:
            continue
        name = str(card.get("name") or "").strip()
        if not name:
            continue
        out.append(card)
    return out


def match_contingency_groups(groups: list[dict], *, card_name: str) -> list[dict]:
    needle = (card_name or "").strip().lower()
    if not needle:
        return []
    matched: list[dict] = []
    for group in groups or []:
        hay = " ".join(
            [
                str(group.get("name") or ""),
                str(group.get("storage_hint") or ""),
                str(group.get("location") or ""),
            ]
        ).lower()
        if needle in hay or hay.find(needle) >= 0 or any(
            needle in str(group.get(k) or "").lower() for k in ("name", "storage_hint", "location")
        ):
            # Prefer exact-ish: storage_hint or name equals card, or card name contained in hint/name
            hint = str(group.get("storage_hint") or "").strip().lower()
            gname = str(group.get("name") or "").strip().lower()
            if needle == hint or needle == gname or needle in hint or needle in gname or hint in needle:
                matched.append(group)
    return matched


def _card_meta(card: dict) -> dict[str, Any]:
    return {
        "id": card.get("id"),
        "name": card.get("name") or "",
        "host": card.get("host") or "",
        "model": card.get("model") or "",
        "device_profile": card.get("device_profile") or "",
        "serial": card.get("serial_number") or card.get("serial") or "",
    }


def _shape_pools(pools: list[dict] | None) -> list[dict[str, Any]]:
    shaped: list[dict[str, Any]] = []
    for pool in pools or []:
        if not isinstance(pool, dict):
            continue
        name = str(pool.get("name") or "").strip()
        if not name:
            continue
        shaped.append(
            {
                "name": name,
                "total_bytes": pool.get("total_bytes"),
                "used_bytes": pool.get("used_bytes"),
                "free_bytes": pool.get("free_bytes"),
                "used_pct": pool.get("used_pct"),
            }
        )
    return shaped


def _volumes_from_maps_and_cgs(maps: list[dict], cgs: list[dict]) -> list[dict]:
    names: dict[str, dict] = {}
    for row in maps or []:
        vname = str(row.get("vdisk_name") or "").strip()
        if vname and vname not in names:
            names[vname] = {"name": vname, "uid": "", "capacity": "", "pool": "", "status": ""}
    for group in cgs or []:
        for vol in group.get("volumes") or []:
            if isinstance(vol, dict):
                vname = str(vol.get("name") or "").strip()
            else:
                vname = str(vol or "").strip()
            if vname and vname not in names:
                names[vname] = {"name": vname, "uid": "", "capacity": "", "pool": "", "status": ""}
    return list(names.values())


def _normalize_cgs(groups: list[dict]) -> list[dict]:
    out: list[dict] = []
    for group in groups or []:
        out.append(
            {
                "id": str(group.get("id") or ""),
                "name": str(group.get("name") or ""),
                "status": str(group.get("status") or ""),
                "location": str(group.get("location") or ""),
                "volumes": group.get("volumes") or [],
                "maps": group.get("maps") or [],
            }
        )
    return out


def _build_payload(
    *,
    card: dict,
    hosts: list[dict],
    volumes: list[dict],
    maps: list[dict],
    consistency_groups: list[dict],
    pools: list[dict],
    source: str,
    refreshed_at: str | None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "card": _card_meta(card),
        "stats": {
            "hosts": len(hosts),
            "volumes": len(volumes),
            "pools": len(pools),
            "nodes": int(card.get("node_count") or 0),
            "consistency_groups": len(consistency_groups),
        },
        "hosts": hosts,
        "volumes": volumes,
        "mappings": maps,
        "consistency_groups": consistency_groups,
        "pools": pools,
        "source": source,
        "refreshed_at": refreshed_at,
        "error": error,
    }


def payload_from_card_cache(
    card: dict,
    *,
    contingency_groups: list[dict] | None = None,
) -> dict[str, Any]:
    hosts = list(card.get("fc_hosts") or [])
    maps = list(card.get("fc_mappings") or [])
    pools = _shape_pools(card.get("pools") if isinstance(card.get("pools"), list) else [])
    live_cgs: list[dict] = []
    matched = match_contingency_groups(contingency_groups or [], card_name=str(card.get("name") or ""))
    cgs = _normalize_cgs(matched)
    volumes = _volumes_from_maps_and_cgs(maps, matched)
    return _build_payload(
        card=card,
        hosts=hosts,
        volumes=volumes,
        maps=maps,
        consistency_groups=cgs,
        pools=pools,
        source="cache",
        refreshed_at=None,
    )


def payload_from_live(
    *,
    card: dict,
    hosts: list[dict],
    volumes: list[dict],
    maps: list[dict],
    consist_groups: list[dict],
    pools: list[dict] | None = None,
    contingency_groups: list[dict] | None = None,
    refreshed_at: str | None = None,
) -> dict[str, Any]:
    shaped_pools = _shape_pools(pools if pools is not None else card.get("pools"))
    if consist_groups:
        cgs = _normalize_cgs(consist_groups)
        source = "ssh"
    else:
        matched = match_contingency_groups(
            contingency_groups or [], card_name=str(card.get("name") or "")
        )
        cgs = _normalize_cgs(matched)
        source = "ssh+cg_fallback" if cgs else "ssh"
    vols = list(volumes) if volumes else _volumes_from_maps_and_cgs(maps, cgs)
    return _build_payload(
        card=card,
        hosts=list(hosts or []),
        volumes=vols,
        maps=list(maps or []),
        consistency_groups=cgs,
        pools=shaped_pools,
        source=source,
        refreshed_at=refreshed_at,
    )
```

Tighten `match_contingency_groups` if the first test is flaky: match when `needle` equals `storage_hint` or `name`, or is a substring of either (and vice versa for hint in card name). The implementation above is intentionally inclusive for `v7kand-g3v1` vs hint.

- [ ] **Step 4: Run tests — expect PASS**

```powershell
pytest tests/test_site_lookup_data.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/site_lookup_data.py tests/test_site_lookup_data.py
git commit -m @"
Add Site Lookup payload helpers for all cards, pools, and CG fallback.
"@
```

---

### Task 2: `parse_lsconsistgrp`

**Files:**
- Modify: `launchpad/flashsystem_fc.py`
- Modify: `tests/test_site_lookup_data.py` (add parser test) **or** create assertion in `tests/test_flashsystem_fc.py` if that module already exists for FC parsers

**Interfaces:**
- Consumes: colon/space table output via existing `_table_records` / `_get`
- Produces: `parse_lsconsistgrp(output: str) -> list[dict[str, str]]` with keys `id`, `name`, `status` (and optional empty fields)

- [ ] **Step 1: Failing test**

```python
from launchpad.flashsystem_fc import parse_lsconsistgrp

def test_parse_lsconsistgrp_colon_table():
    out = "id:name:status\n1:cg_live:empty\n2:cg_b:stopped\n"
    rows = parse_lsconsistgrp(out)
    assert [r["name"] for r in rows] == ["cg_live", "cg_b"]
    assert rows[0]["status"] == "empty"
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
pytest tests/test_site_lookup_data.py::test_parse_lsconsistgrp_colon_table -v
```

(If the test lives in another file, adjust the path.)

- [ ] **Step 3: Implement**

Add to `launchpad/flashsystem_fc.py`:

```python
def parse_lsconsistgrp(output: str) -> list[dict[str, str]]:
    """Parse svcinfo lsconsistgrp summary rows."""
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
            }
        )
    return groups
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/flashsystem_fc.py tests/test_site_lookup_data.py
git commit -m @"
Add lsconsistgrp parser for Site Lookup consistency groups.
"@
```

---

### Task 3: Refresh API + open helpers

**Files:**
- Modify: `launchpad/health_server.py`
- Modify: `launchpad/monitor.py`
- Create: `tests/test_site_lookup_api.py`
- Create stub: `launchpad/site_lookup.py` with `SITE_LOOKUP_PATH = "/site-lookup"` and minimal HTML if Task 4 not done yet

**Interfaces:**
- Consumes: `payload_from_live`, `payload_from_card_cache`, `parse_fc_hosts`, `parse_host_lun_maps`, `parse_lsvdisk_volumes`, `parse_lsconsistgrp`, `pool_capacity_from_commands` / `card.to_api()["pools"]`, `SVC_PROFILES` (for optional CG SSH only), `_lun_run_command`, `refresh_card`, `get_contingency_groups`
- Produces:
  - `HealthServer.refresh_site_lookup(card_id: int) -> dict`
  - `POST /api/site-lookup/refresh` body `{ "card_id": <int|str> }`
  - `HealthServer.open_site_lookup() -> str`
  - `monitor.open_site_lookup_for_cards(entries) -> str`
  - Optional: add `serial_number` to `HealthCard.to_api()` if missing

- [ ] **Step 1: Write failing API tests**

```python
# tests/test_site_lookup_api.py
from launchpad.health_server import HealthCard, HealthServer


def _card(**kwargs):
    defaults = dict(
        card_id=1,
        name="site-a",
        host="10.0.0.1",
        port=22,
        username="user",
        password="x",
        key_path="",
        key_passphrase="",
        device_profile="flashsystem_5200",
        custom_commands="",
        serial_number="",
        category="",
    )
    defaults.update(kwargs)
    return HealthCard(**defaults)  # HealthCard is a @dataclass; custom_commands is str


def test_refresh_site_lookup_success(monkeypatch):
    server = HealthServer(port=0)
    server._cards[1] = _card()

    def fake_refresh(self, card_id, **kwargs):
        card = self._cards[card_id]
        card.command_results = [
            {
                "label": "FC - Hosts",
                "command": "svcinfo lshost -delim :",
                "output": "id:name:status:port_count\n1:h1:online:2\n",
                "error": None,
            },
            {
                "label": "Memory - Volumes %",
                "command": "svcinfo lsvdisk -delim :",
                "output": "id:name:capacity:mdisk_grp_name:vdisk_UID:status\n1:v1:10GB:P0:U1:online\n",
                "error": None,
            },
            {
                "label": "FC - Host LUN Maps",
                "command": "svcinfo lshostvdiskmap -delim :",
                "output": "id:name:SCSI_id:host_id:host_name:vdisk_UID\n0:v1:0:1:h1:U1\n",
                "error": None,
            },
            {
                "label": "Capacity - Pools %",
                "command": "svcinfo lsmdiskgrp -delim :",
                "output": "id:name:capacity:free_capacity:used_capacity\n0:P0:100:50:50\n",
                "error": None,
            },
        ]
        card.error = None
        return card

    monkeypatch.setattr(HealthServer, "refresh_card", fake_refresh)

    def fake_run(card):
        def _run(command: str) -> str:
            if "lsconsistgrp" in command:
                return "id:name:status\n1:cg_live:empty\n"
            raise AssertionError(f"unexpected command {command}")
        return _run

    monkeypatch.setattr(HealthServer, "_lun_run_command", staticmethod(fake_run))
    monkeypatch.setattr(server, "get_contingency_groups", lambda: [])

    payload = server.refresh_site_lookup(1)
    assert payload["error"] is None
    assert payload["stats"]["hosts"] >= 1
    assert payload["stats"]["pools"] >= 1
    assert payload["consistency_groups"][0]["name"] == "cg_live"
    assert payload["source"] == "ssh"


def test_refresh_site_lookup_missing_card():
    server = HealthServer(port=0)
    try:
        server.refresh_site_lookup(999)
        assert False, "expected KeyError"
    except KeyError:
        pass
```

Adjust `HealthCard(...)` constructor kwargs to match the real dataclass/signature in `health_server.py` (read `class HealthCard` before writing the test).

- [ ] **Step 2: Run — expect FAIL**

```powershell
pytest tests/test_site_lookup_api.py -v
```

- [ ] **Step 3: Implement `refresh_site_lookup` + routes + monitor helper**

```python
def refresh_site_lookup(self, card_id: int) -> dict:
    from datetime import datetime, timezone
    from launchpad.flashsystem_fc import (
        parse_fc_hosts,
        parse_host_lun_maps,
        parse_lsconsistgrp,
        parse_lsvdisk_volumes,
    )
    from launchpad.flashsystem_health import pool_capacity_from_commands
    from launchpad.site_lookup_data import payload_from_live
    from launchpad.storage_presets import SVC_PROFILES

    cid = int(card_id)
    with self._lock:
        if cid not in self._cards:
            raise KeyError(cid)

    card = self.refresh_card(cid)
    meta = card.to_api()
    results = card.command_results or []

    hosts = list(meta.get("fc_hosts") or [])
    maps = list(meta.get("fc_mappings") or [])
    pools = list(meta.get("pools") or []) or pool_capacity_from_commands(results)

    volumes: list[dict] = []
    for item in results:
        cmd = str(item.get("command") or "")
        out = str(item.get("output") or "")
        if "lsvdisk" in cmd and "hostmap" not in cmd and "sevdisk" not in cmd:
            volumes = parse_lsvdisk_volumes(out)
            break
    if not hosts:
        for item in results:
            if "lshost" in str(item.get("command") or "") and "vdisk" not in str(item.get("command") or ""):
                hosts = parse_fc_hosts(str(item.get("output") or ""))
                break
    if not maps:
        for item in results:
            if "lshostvdiskmap" in str(item.get("command") or "") or "lsvdiskhostmap" in str(item.get("command") or ""):
                maps = parse_host_lun_maps(str(item.get("output") or ""))
                break

    consist_groups: list[dict] = []
    if card.device_profile in SVC_PROFILES:
        try:
            cg_out = self._lun_run_command(card)("svcinfo lsconsistgrp -delim :")
            consist_groups = parse_lsconsistgrp(cg_out)
        except Exception:
            consist_groups = []

    return payload_from_live(
        card=meta,
        hosts=hosts,
        volumes=volumes,
        maps=maps,
        consist_groups=consist_groups,
        pools=pools,
        contingency_groups=self.get_contingency_groups(),
        refreshed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
```

If `refresh_card` raises / card.error is total failure, catch and re-raise as `RuntimeError(str)` so the POST handler returns 502 `{ "error": "..." }` without a successful payload.

Wire POST near other API handlers:

```python
if path == "/api/site-lookup/refresh":
    # read JSON card_id; call refresh_site_lookup; _send_json(payload)
    # KeyError -> 404; RuntimeError/OSError -> 502 {"error": ...}
```

```python
def open_site_lookup(self) -> str:
    self.ensure_running()
    return f"http://127.0.0.1:{self._port}{SITE_LOOKUP_PATH}"
```

In `monitor.py`:

```python
def open_site_lookup_for_cards(entries: list[HealthDashboardEntry]) -> str:
    if not entries:
        raise ValueError("No SSH cards with credentials to monitor.")
    server = get_health_server()
    server.ensure_running()
    for entry in entries:
        _register_entry(server, entry)
    return server.open_site_lookup()
```

Ensure GET `SITE_LOOKUP_PATH` returns stub HTML until Task 4 (minimal page containing the string `Site Lookup`).

- [ ] **Step 4: Run — expect PASS**

```powershell
pytest tests/test_site_lookup_api.py tests/test_site_lookup_data.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py launchpad/monitor.py launchpad/site_lookup.py tests/test_site_lookup_api.py
git commit -m @"
Add Site Lookup refresh API and browser open helpers.
"@
```

---

### Task 4: Tempe-style page HTML/JS

**Files:**
- Modify: `launchpad/site_lookup.py` (full `SITE_LOOKUP_HTML`)
- Create: `tests/test_site_lookup_page.py`

**Interfaces:**
- Consumes: `/api/cards`, `POST /api/site-lookup/refresh`, `filter_lookup_cards` client-side (or filter in JS)
- Produces: page with search/suggest, Live Refresh, tabs Hosts/Volumes/Consistency Groups/Pools, last-updated status

- [ ] **Step 1: Page contract tests**

```python
# tests/test_site_lookup_page.py
from launchpad.site_lookup import SITE_LOOKUP_HTML, SITE_LOOKUP_PATH


def test_site_lookup_path_and_markers():
    assert SITE_LOOKUP_PATH == "/site-lookup"
    html = SITE_LOOKUP_HTML
    assert "Site Lookup" in html
    assert "/api/site-lookup/refresh" in html
    assert "Live Refresh" in html or ">Refresh<" in html
    for label in ("Hosts", "Volumes", "Consistency Groups", "Pools"):
        assert label in html
```

- [ ] **Step 2: Run — expect FAIL** (missing markers)

- [ ] **Step 3: Implement Tempe-adapted HTML**

Build `SITE_LOOKUP_HTML` as a single Python string in `launchpad/site_lookup.py`:

1. Copy visual structure/CSS variables from `C:/Users/BrianColley/Downloads/storage_site_lookup_tempe_2.html` (dark panels, header-card, tabs, pool-card, searchbar).
2. Replace static `siteData` with:
   - `GET /api/cards` → populate suggest/dropdown (`filter`: every card with id+name).
   - Selecting a card: optional immediate paint via client-built cache payload from card fields (`fc_hosts`, `fc_mappings`, `pools`) **or** empty header + prompt to Refresh.
   - Prefer: on select, `POST /api/site-lookup/refresh` automatically **or** show cache paint then require Live Refresh — **locked:** select paints from card JSON cache fields if present; **Live Refresh** always POSTs for full A+B.
3. JS must:
   - Disable Refresh while in-flight.
   - On error response: show banner; **do not** clear existing tables.
   - Set status `Last updated: …` from `refreshed_at`.
   - Tabs switch Hosts / Volumes / Consistency Groups / Pools tables/cards.
   - Case-insensitive filter over host + volume names (and CG/mapping rows that reference them).
4. Include `{{APP_VERSION}}` placeholder replaced by health_server like other pages.
5. Empty tab copy: `Not available for this profile` or `No rows` when lists empty after refresh.

Keep the HTML file focused; do not embed the entire Tempe sample dataset.

- [ ] **Step 4: Wire GET in `health_server.py` if not already**

```python
from launchpad.site_lookup import SITE_LOOKUP_HTML, SITE_LOOKUP_PATH
# ...
if path == SITE_LOOKUP_PATH:
    self._send_html(SITE_LOOKUP_HTML.replace("{{APP_VERSION}}", APP_VERSION))
```

- [ ] **Step 5: Run page + prior tests**

```powershell
pytest tests/test_site_lookup_page.py tests/test_site_lookup_api.py tests/test_site_lookup_data.py -v
```

- [ ] **Step 6: Commit**

```powershell
git add launchpad/site_lookup.py launchpad/health_server.py tests/test_site_lookup_page.py
git commit -m @"
Add Tempe-style Site Lookup page with Live Refresh wiring.
"@
```

---

### Task 5: Dashboard button + version bump

**Files:**
- Modify: `launchpad/ui/dashboard_view.py`
- Modify: `launchpad/monitor.py` (import already added in Task 3)
- Modify: `launchpad/config.py`
- Modify: `tests/test_site_lookup_page.py` (optional: assert tool label if tested via source read — skip if no pattern)

**Interfaces:**
- Consumes: `open_site_lookup_for_cards`, `_health_ssh_cards`, `HealthDashboardEntry`, `resolve_ssh_metrics_auth`
- Produces: tool button **Site Lookup**; `APP_VERSION` next patch

- [ ] **Step 1: Add tool button**

In `tool_specs` in `dashboard_view.py`, add after FC WWPN (or Host / Volume Find):

```python
("Site Lookup", self._open_site_lookup_all, None),
```

Implement `_open_site_lookup_all` mirroring `_open_fc_wwpn_report_all`, calling `open_site_lookup_for_cards(entries)`.

Import `open_site_lookup_for_cards` at the top with other monitor imports.

- [ ] **Step 2: Bump `APP_VERSION`** in `launchpad/config.py` to the next patch after current tip (one bump covering Site Lookup and jiggler if both ship together).

- [ ] **Step 3: Run focused suite**

```powershell
pytest tests/test_site_lookup_data.py tests/test_site_lookup_api.py tests/test_site_lookup_page.py tests/test_mouse_jiggler.py -v
```

Expected: PASS (jiggler tests pass if that plan already landed).

- [ ] **Step 4: Commit**

```powershell
git add launchpad/ui/dashboard_view.py launchpad/config.py launchpad/monitor.py
git commit -m @"
Add Site Lookup dashboard button and bump version.
"@
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| `/site-lookup` Tempe layout | Task 4 |
| All SSH cards in picker | Tasks 1, 4 |
| Tabs Hosts/Volumes/CGs/Pools | Task 4 |
| Live Refresh A pools/capacity | Task 3 (`refresh_card` + pools) |
| Live Refresh B hosts/volumes/CGs | Tasks 2–3 |
| CG Contingency fallback | Task 1, 3 |
| Empty unsupported tabs | Task 4 |
| Refresh failure keeps paint | Task 3 (API error) + Task 4 (JS) |
| Dashboard button | Task 5 |
| Read-only / no Downloads HTML data | All tasks |
| Version bump | Task 5 |

## Manual smoke (after tasks)

1. Launch LaunchPad → **Site Lookup** → browser opens.
2. Pick an SVC site → Live Refresh → Hosts/Volumes/Pools populate.
3. Pick an HPE site → Pools may populate; empty Hosts/Volumes/CGs with explanation OK.
4. Kill SSH mid-refresh → prior tables remain; error banner shows.
