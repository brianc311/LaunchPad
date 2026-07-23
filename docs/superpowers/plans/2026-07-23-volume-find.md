# Volume Find (IBM + HPE Hybrid) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Volume Find page that searches volume names across monitor-on IBM and HPE SSH Health Cards — cache first, then live SSH — and reports which array/card owns each match.

**Architecture:** Pure helpers in `volume_find.py` (eligibility, match, parse cache/live). `GET /api/volume-find?q=&mode=cache|live` on HealthServer. Browser page `/volume-find`. Add HPE `showvv` to 3PAR/Primera presets. Dashboard + nav links.

**Tech Stack:** Embedded HTML/JS, HealthServer SSH (`run_remote_ssh_command`), existing `parse_lsvdisk_volumes`, pytest.

**Spec:** `docs/superpowers/specs/2026-07-23-volume-find-design.md`

## Global Constraints

- **Worktree:** `.worktrees/volume-find` on `feature/volume-find` from `feature/contingency-groups` tip (`APP_VERSION=1.6.56`, includes volume-find design commit)
- Hybrid: **Find** = cache; **Search live** = SSH
- Eligible: monitor-enabled SSH cards with IBM SVC/FlashSystem/Storwize **or** HPE 3PAR/Primera profiles
- Match: case-insensitive substring on volume name
- Live unlock required; cache Find works from existing card data
- Add HPE volume inventory command `showvv` to presets
- Bump `APP_VERSION` to **1.6.57**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\volume-find`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/volume_find.py` | Eligibility, match, cache extraction, HPE `showvv` parse, result sorting |
| `launchpad/volume_find_page.py` | `VOLUME_FIND_PATH`, `VOLUME_FIND_HTML` |
| `launchpad/storage_presets.py` | Add `showvv` to 3PAR/Primera command lists |
| `launchpad/health_server.py` | Serve page; `GET /api/volume-find`; live SSH orchestration; URL opener |
| `launchpad/ui/dashboard_view.py` | Volume Find button |
| `launchpad/fc_wwpn_report.py`, `capacity_report.py`, `contingency_groups.py` | Nav link to `/volume-find` (best-effort where hero actions exist) |
| `launchpad/config.py` | `1.6.57` |
| `tests/test_volume_find.py` | Helpers + parsers |
| `tests/test_volume_find_api.py` | API / server method tests |
| `tests/test_volume_find_page.py` | Page + nav contracts |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/volume-find -b feature/volume-find feature/contingency-groups
cd .worktrees/volume-find
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-23-volume-find-design.md
Test-Path docs\superpowers\plans\2026-07-23-volume-find.md
```

Expected: `1.6.56` (or tip), both paths `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Pure volume-find helpers

**Files:**
- Create: `launchpad/volume_find.py`
- Create: `tests/test_volume_find.py`

**Interfaces:**
- Produces:
  - `VOLUME_FIND_IBM_PROFILES` / use `is_svc_fc_profile` + `HPE_SHELL_PROFILES`
  - `is_volume_find_eligible(card: dict, *, monitor_on: bool) -> bool`
  - `volume_name_matches(name: str, query: str) -> bool`
  - `vendor_for_profile(profile: str) -> str`  # `"ibm"` | `"hpe"` | `"unknown"`
  - `parse_showvv_volumes(output: str) -> list[dict]`  # keys: name, pool_or_cpg
  - `volumes_from_command_results(command_results: list[dict] | None, profile: str) -> list[dict]`
  - `find_volumes_in_cards(cards: list[dict], query: str, *, monitor_enabled: dict[str|int, bool], source: str) -> list[dict]`
  - Match result dict keys: `card_id`, `card_name`, `profile`, `vendor`, `volume`, `pool_or_cpg`, `source`

- [ ] **Step 1: Write failing tests**

```python
from launchpad.volume_find import (
    find_volumes_in_cards,
    is_volume_find_eligible,
    parse_showvv_volumes,
    vendor_for_profile,
    volume_name_matches,
    volumes_from_command_results,
)


def test_volume_name_matches_substring_case_insensitive():
    assert volume_name_matches("pconsps_archvg_1", "ARCHVG") is True
    assert volume_name_matches("pconsps_archvg_1", "nope") is False
    assert volume_name_matches("", "x") is False


def test_eligibility_requires_monitor_ssh_and_profile():
    ibm = {"id": 1, "card_type": "ssh", "device_profile": "flashsystem_7200", "name": "Hartford"}
    assert is_volume_find_eligible(ibm, monitor_on=True) is True
    assert is_volume_find_eligible(ibm, monitor_on=False) is False
    hpe = {"id": 2, "card_type": "ssh", "device_profile": "hpe_3par_8450", "name": "3PAR"}
    assert is_volume_find_eligible(hpe, monitor_on=True) is True
    web = {"id": 3, "card_type": "web", "device_profile": "flashsystem_7200", "name": "Web"}
    assert is_volume_find_eligible(web, monitor_on=True) is False


def test_vendor_for_profile():
    assert vendor_for_profile("flashsystem_7200") == "ibm"
    assert vendor_for_profile("hpe_3par_8450") == "hpe"
    assert vendor_for_profile("hpe_primera_600") == "hpe"


def test_parse_showvv_volumes_basic():
    # Minimal fixture: header + rows (Name + CPG). Adjust if parser uses different layout.
    output = (
        "Id,Name,Rd,Mstr,HostDisp,VV_WWN,Prov,Type,CopyOf,BsId,UsrCPG,SnpCPG\n"
        "0,vv_data_1,----,normal,0,5000ABCD,full,base,--,0,SSD_r5,-\n"
        "1,vv_data_2,----,normal,0,5000ABCE,full,base,--,0,FC_r1,-\n"
    )
    vols = parse_showvv_volumes(output)
    names = {v["name"] for v in vols}
    assert "vv_data_1" in names
    assert "vv_data_2" in names
    assert any(v.get("pool_or_cpg") == "SSD_r5" for v in vols if v["name"] == "vv_data_1")


def test_volumes_from_command_results_ibm_lsvdisk():
    results = [
        {
            "label": "Memory - Volumes %",
            "command": "svcinfo lsvdisk -delim :",
            "output": "id:name:IO_group_id:IO_group_name:status:mdisk_grp_id:mdisk_grp_name:capacity\n"
            "0:pconsps_archvg_1:0:io_grp0:online:0:Pool0:200.00GB\n",
        }
    ]
    vols = volumes_from_command_results(results, "flashsystem_7200")
    assert any(v["name"] == "pconsps_archvg_1" for v in vols)


def test_find_volumes_in_cards_sorted():
    cards = [
        {
            "id": 2,
            "name": "Zebra",
            "card_type": "ssh",
            "device_profile": "flashsystem_7200",
            "command_results": [
                {
                    "command": "svcinfo lsvdisk -delim :",
                    "output": "id:name:mdisk_grp_name\n0:vol_b:Pool0\n1:vol_a:Pool0\n",
                }
            ],
        },
        {
            "id": 1,
            "name": "Alpha",
            "card_type": "ssh",
            "device_profile": "flashsystem_7200",
            "command_results": [
                {
                    "command": "svcinfo lsvdisk -delim :",
                    "output": "id:name:mdisk_grp_name\n0:vol_a:Pool1\n",
                }
            ],
        },
    ]
    monitor = {1: True, 2: True}
    found = find_volumes_in_cards(cards, "vol_", monitor_enabled=monitor, source="cache")
    assert [(m["card_name"], m["volume"]) for m in found] == [
        ("Alpha", "vol_a"),
        ("Zebra", "vol_a"),
        ("Zebra", "vol_b"),
    ]
```

If `parse_lsvdisk` fixtures need extra columns, mirror real `parse_lsvdisk_volumes` delimiter format from `tests` that already use it.

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\volume-find
python -m pytest tests/test_volume_find.py -v
```

- [ ] **Step 3: Implement `launchpad/volume_find.py`**

```python
"""Volume Find helpers — eligibility, match, cache/live parsers."""

from __future__ import annotations

from typing import Any

from launchpad.flashsystem_fc import parse_lsvdisk_volumes
from launchpad.storage_presets import HPE_SHELL_PROFILES, is_svc_fc_profile


def volume_name_matches(name: str, query: str) -> bool:
    q = str(query or "").strip().lower()
    if not q:
        return False
    return q in str(name or "").strip().lower()


def vendor_for_profile(profile: str) -> str:
    key = (profile or "").strip().lower()
    if key in HPE_SHELL_PROFILES or key.startswith("hpe_"):
        return "hpe"
    if is_svc_fc_profile(profile):
        return "ibm"
    return "unknown"


def is_volume_find_eligible(card: dict[str, Any], *, monitor_on: bool) -> bool:
    if not monitor_on:
        return False
    if str(card.get("card_type") or "").lower() != "ssh":
        return False
    profile = str(card.get("device_profile") or "")
    if is_svc_fc_profile(profile):
        return True
    if profile.strip().lower() in HPE_SHELL_PROFILES:
        return True
    return False


def parse_showvv_volumes(output: str) -> list[dict[str, str]]:
    """Parse HPE showvv CSV/delimited or whitespace table for Name + CPG."""
    text = str(output or "").strip()
    if not text:
        return []
    # Prefer comma/colon delimited header containing Name
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    header = lines[0]
    delim = "," if "," in header else (":" if ":" in header else None)
    volumes: list[dict[str, str]] = []
    if delim:
        cols = [c.strip() for c in header.split(delim)]
        name_i = next((i for i, c in enumerate(cols) if c.lower() in {"name", "vvname", "vv_name"}), None)
        cpg_i = next(
            (i for i, c in enumerate(cols) if c.lower() in {"usrcpg", "cpg", "snpcpg", "usr_cpg"}),
            None,
        )
        if name_i is None:
            return []
        for line in lines[1:]:
            parts = [p.strip() for p in line.split(delim)]
            if len(parts) <= name_i:
                continue
            name = parts[name_i]
            if not name or name.lower() == "name":
                continue
            pool = parts[cpg_i] if cpg_i is not None and len(parts) > cpg_i else ""
            if pool in {"-", "--"}:
                pool = ""
            volumes.append({"name": name, "pool_or_cpg": pool})
        return volumes
    # Fallback: whitespace — look for tokens; keep YAGNI simple
    return volumes


def volumes_from_command_results(
    command_results: list[dict[str, Any]] | None,
    profile: str,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in command_results or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        cmd = f"{item.get('label') or ''} {item.get('command') or ''}".lower()
        output = str(item.get("output") or "")
        parsed: list[dict[str, str]] = []
        if "lsvdisk" in cmd or "memory - volumes" in cmd:
            for row in parse_lsvdisk_volumes(output):
                parsed.append(
                    {"name": row.get("name") or "", "pool_or_cpg": row.get("pool") or ""}
                )
        elif "showvv" in cmd:
            parsed = parse_showvv_volumes(output)
        for row in parsed:
            name = str(row.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            out.append({"name": name, "pool_or_cpg": str(row.get("pool_or_cpg") or "")})
    return out


def find_volumes_in_cards(
    cards: list[dict[str, Any]],
    query: str,
    *,
    monitor_enabled: dict[Any, bool],
    source: str,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        card_id = card.get("id")
        monitor_on = bool(monitor_enabled.get(card_id, monitor_enabled.get(str(card_id), False)))
        if not is_volume_find_eligible(card, monitor_on=monitor_on):
            continue
        profile = str(card.get("device_profile") or "")
        for vol in volumes_from_command_results(card.get("command_results"), profile):
            if not volume_name_matches(vol["name"], query):
                continue
            matches.append(
                {
                    "card_id": card_id,
                    "card_name": str(card.get("name") or card_id or ""),
                    "profile": profile,
                    "vendor": vendor_for_profile(profile),
                    "volume": vol["name"],
                    "pool_or_cpg": vol.get("pool_or_cpg") or "",
                    "source": source,
                }
            )
    return sorted(
        matches,
        key=lambda m: (str(m.get("card_name") or "").lower(), str(m.get("volume") or "").lower()),
    )
```

Tune `parse_showvv_volumes` / fixtures until tests pass; keep parser resilient.

- [ ] **Step 4: Run tests — expect PASS**

```powershell
python -m pytest tests/test_volume_find.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/volume_find.py tests/test_volume_find.py
git commit -m "Add Volume Find match helpers and IBM/HPE volume parsers."
```

---

### Task 2: HPE preset `showvv`

**Files:**
- Modify: `launchpad/storage_presets.py`
- Test: extend `tests/test_volume_find.py` or add assertion in existing preset tests if present

**Interfaces:**
- Produces: `("Volumes - VV list", "showvv")` (or `showvv -showcols Id,Name,UsrCPG`) in `HP_3PAR_COMMANDS` and `HPE_PRIMERA_COMMANDS`

- [ ] **Step 1: Failing test**

```python
from launchpad.storage_presets import HP_3PAR_COMMANDS, HPE_PRIMERA_COMMANDS, preset_commands_for_profile


def test_hpe_presets_include_showvv():
    assert any("showvv" in cmd for _, cmd in HP_3PAR_COMMANDS)
    assert any("showvv" in cmd for _, cmd in HPE_PRIMERA_COMMANDS)
    cmds = preset_commands_for_profile("hpe_3par_8450")
    assert any("showvv" in cmd for _, cmd in cmds)
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Add command**

```python
("Volumes - VV list", "showvv"),
```

Append to both `HP_3PAR_COMMANDS` and `HPE_PRIMERA_COMMANDS` (near capacity commands is fine).

- [ ] **Step 4: PASS + commit**

```powershell
git add launchpad/storage_presets.py tests/test_volume_find.py
git commit -m "Add showvv volume inventory command to HPE 3PAR/Primera presets."
```

---

### Task 3: HealthServer `GET /api/volume-find`

**Files:**
- Modify: `launchpad/health_server.py`
- Create: `tests/test_volume_find_api.py`

**Interfaces:**
- Produces:
  - `HealthServer.find_volumes(query: str, *, mode: str) -> dict` with `matches` + `errors`
  - `mode=cache`: no SSH; uses `list_cards` + `is_monitor_enabled` + `find_volumes_in_cards(..., source="cache")`
  - `mode=live`: requires unlocked app (raise RuntimeError if locked, same style as other gates); SSH eligible cards; IBM `svcinfo lsvdisk -delim :`; HPE `showvv`; build matches with `source="live"`; collect per-card errors
  - Handler: `GET /api/volume-find?q=&mode=cache|live`

- [ ] **Step 1: Failing API tests**

```python
from launchpad.health_server import HealthServer, HealthCard


def test_find_volumes_cache_uses_command_results(monkeypatch):
    server = HealthServer()
    card = HealthCard(
        card_id=1,
        name="Hartford",
        card_type="ssh",
        host="10.0.0.1",
        device_profile="flashsystem_7200",
        command_results=[
            {
                "command": "svcinfo lsvdisk -delim :",
                "output": "id:name:mdisk_grp_name\n0:pconsps_archvg_1:Pool0\n",
            }
        ],
    )
    server._cards[1] = card
    server.set_monitor_enabled(card_id=1, enabled=True)
    # Prevent sync/app noise if needed
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    result = server.find_volumes("archvg", mode="cache")
    assert result["matches"]
    assert result["matches"][0]["volume"] == "pconsps_archvg_1"
    assert result["matches"][0]["source"] == "cache"


def test_find_volumes_live_requires_unlock(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(server, "is_unlocked", lambda: False)
    try:
        server.find_volumes("x", mode="live")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "unlock" in str(exc).lower()


def test_api_volume_find_route_declared():
    import inspect
    from launchpad.health_server import _HealthHandler
    src = inspect.getsource(_HealthHandler.do_GET)
    assert "/api/volume-find" in src
```

Adapt `HealthCard` constructor args to match the real dataclass/fields in this repo. Use `is_unlocked` / `_app_unlocked` / whatever the server already exposes for unlock checks (grep `must be unlocked` and mirror that gate).

- [ ] **Step 2: FAIL then implement `find_volumes` + route**

Sketch:

```python
def find_volumes(self, query: str, *, mode: str = "cache") -> dict:
    q = str(query or "").strip()
    if not q:
        return {"matches": [], "errors": []}
    mode_key = str(mode or "cache").strip().lower()
    if mode_key not in {"cache", "live"}:
        raise ValueError("mode must be cache or live")
    self.sync_from_app()
    cards = self.list_cards(allow_sync=False)
    monitor = {c["id"]: self.is_monitor_enabled(int(c["id"])) for c in cards if c.get("id") is not None}
    if mode_key == "cache":
        return {
            "matches": find_volumes_in_cards(cards, q, monitor_enabled=monitor, source="cache"),
            "errors": [],
        }
    if not self.<unlocked_predicate>():
        raise RuntimeError("LaunchPad must be unlocked to search volumes live.")
    matches = []
    errors = []
    for card_dict in cards:
        if not is_volume_find_eligible(card_dict, monitor_on=monitor.get(card_dict.get("id"), False)):
            continue
        card = self._cards.get(int(card_dict["id"]))
        if card is None:
            continue
        profile = str(card.device_profile or "")
        try:
            run = self._lun_run_command(card)  # or equivalent SSH runner already used for sync
            if vendor_for_profile(profile) == "hpe":
                output = run("showvv")
                vols = parse_showvv_volumes(output)
            else:
                output = run("svcinfo lsvdisk -delim :")
                vols = [
                    {"name": r["name"], "pool_or_cpg": r.get("pool") or ""}
                    for r in parse_lsvdisk_volumes(output)
                ]
            for vol in vols:
                if volume_name_matches(vol["name"], q):
                    matches.append({... source: "live" ...})
        except Exception as exc:
            errors.append({"card_id": card.card_id, "card_name": card.name, "error": str(exc)})
    matches.sort(...)
    return {"matches": matches, "errors": errors}
```

Wire in `do_GET`:

```python
if path == "/api/volume-find":
    query = parse_qs(parsed.query)
    q = (query.get("q") or [""])[0]
    mode = (query.get("mode") or ["cache"])[0]
    try:
        payload = server.find_volumes(q, mode=mode)
    except ValueError as exc:
        self._send_json({"error": str(exc)}, status=400)
        return
    except RuntimeError as exc:
        self._send_json({"error": str(exc)}, status=403)
        return
    self._send_json(payload)
    return
```

- [ ] **Step 4: PASS**

```powershell
python -m pytest tests/test_volume_find_api.py tests/test_volume_find.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_volume_find_api.py
git commit -m "Add Volume Find API with cache and live SSH modes."
```

---

### Task 4: Volume Find page + nav + dashboard

**Files:**
- Create: `launchpad/volume_find_page.py`
- Modify: `launchpad/health_server.py` (serve HTML, `volume_find_url`, `open_volume_find`)
- Modify: `launchpad/ui/dashboard_view.py` (button)
- Modify: `launchpad/fc_wwpn_report.py`, `launchpad/capacity_report.py`, `launchpad/contingency_groups.py` (nav links)
- Create: `tests/test_volume_find_page.py`

**Interfaces:**
- `VOLUME_FIND_PATH = "/volume-find"`
- Page calls `GET /api/volume-find?q=&mode=cache` and `mode=live`
- Status text: cache hits / “No cache matches — try Search live” / live results + errors

- [ ] **Step 1: Page contract tests**

```python
from launchpad.volume_find_page import VOLUME_FIND_HTML, VOLUME_FIND_PATH
from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML


def test_volume_find_path_and_controls():
    assert VOLUME_FIND_PATH == "/volume-find"
    for text in (
        "Volume Find",
        'id="volume-search"',
        'id="volume-find-btn"',
        'id="volume-live-btn"',
        "/api/volume-find",
        "mode=cache",
        "mode=live",
        "Search live",
        "No cache matches — try Search live",
    ):
        assert text in VOLUME_FIND_HTML


def test_fc_wwpn_links_to_volume_find():
    assert 'href="/volume-find">Volume Find</a>' in FC_WWPN_REPORT_HTML
```

- [ ] **Step 2: FAIL → implement page**

Create a compact page styled like FC WWPN / Capacity hero (dark theme, accent orange). Include:

- Find + Search live buttons
- Results `<table>` with columns Card, Vendor, Volume, Pool / CPG, Source
- JS: `runVolumeFind(mode)` fetch JSON and render rows; show errors list

Serve in `_HealthHandler.do_GET` like LUN Builder:

```python
if path == VOLUME_FIND_PATH:
    html = VOLUME_FIND_HTML.replace("{{APP_VERSION}}", APP_VERSION)
    self._send_html(html)  # use existing HTML send helper
    return
```

Add `volume_find_url` + `open_volume_find()` mirroring `open_lun_builder`.

Dashboard: button `Volume Find` near LUN Builder calling `_open_volume_find` (thread + `server.open_volume_find()`).

Nav: add `<a class="btn secondary" href="/volume-find">Volume Find</a>` on FC WWPN, Capacity, Consistency Groups heroes.

- [ ] **Step 3: PASS**

```powershell
python -m pytest tests/test_volume_find_page.py tests/test_volume_find.py tests/test_volume_find_api.py -q
```

- [ ] **Step 4: Commit**

```powershell
git add launchpad/volume_find_page.py launchpad/health_server.py launchpad/ui/dashboard_view.py launchpad/fc_wwpn_report.py launchpad/capacity_report.py launchpad/contingency_groups.py tests/test_volume_find_page.py
git commit -m "Add Volume Find page, dashboard button, and nav links."
```

---

### Task 5: Version bump 1.6.57

**Files:**
- Modify: `launchpad/config.py`

- [ ] **Step 1:** Set `APP_VERSION = "1.6.57"`

- [ ] **Step 2: Smoke**

```powershell
python -c "from launchpad.config import APP_VERSION; from launchpad.volume_find_page import VOLUME_FIND_HTML; assert APP_VERSION=='1.6.57'; assert 'volume-search' in VOLUME_FIND_HTML; print('ok')"
python -m pytest tests/test_volume_find.py tests/test_volume_find_api.py tests/test_volume_find_page.py -q
```

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.57 for Volume Find."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Helpers / match / eligibility | 1 |
| HPE `showvv` preset | 2 |
| Cache + live API | 3 |
| Page + nav + dashboard | 4 |
| Version 1.6.57 | 5 |

## Self-review notes

- Reuse `_lun_run_command` / existing SSH runner — do not invent a second auth path.
- Unlock gate for live must match existing HealthServer patterns (find the real method name).
- `parse_showvv_volumes` fixtures may need adjustment to real `showvv` columns; keep delimiter detection.
- Cache Find should not call `refresh_card` (no SSH).
