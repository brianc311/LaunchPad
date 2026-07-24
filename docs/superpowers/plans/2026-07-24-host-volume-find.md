# Host / Volume Find Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Volume Find into Host / Volume Find with a Volume|Host toggle so operators can locate where a host is defined (card, Site IP, WWPNs) using the same cache-then-live flow.

**Architecture:** Reuse eligibility and hybrid Find/live. Add host parsers + `find_hosts_in_cards` in `volume_find.py`. Extend `GET /api/volume-find` with `type=volume|host` (default volume). Page toggle switches columns/placeholder. Add HPE `showhost` to presets. Reuse `parse_fc_hosts` / card `fc_hosts` for IBM cache WWPNs when present.

**Tech Stack:** Embedded HTML/JS, HealthServer SSH, `flashsystem_fc.parse_fc_hosts`, pytest.

**Spec:** `docs/superpowers/specs/2026-07-24-host-volume-find-design.md`

## Global Constraints

- **Worktree:** `.worktrees/host-volume-find` on `feature/host-volume-find` from `feature/contingency-groups` tip (includes design commit if merged, or cherry-pick / include design file)
- Path stays `/volume-find`; UI title **Host / Volume Find**
- Host result shape A: card + Site IP + vendor + host_name + wwpns + source
- Match: case-insensitive substring on host name
- Eligible: same as Volume Find (monitor-on SSH IBM SVC-family or HPE shell)
- Live unlock required; cache Find no SSH
- Add HPE `showhost` to 3PAR and Primera command lists
- Bump `APP_VERSION` to **1.6.64**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\host-volume-find`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/volume_find.py` | Host match alias, `parse_showhost_hosts`, `hosts_from_command_results` / `fc_hosts`, `find_hosts_in_cards` |
| `launchpad/health_server.py` | `find_volumes(..., find_type=)` or `find_inventory`; route `type=` query; live host SSH |
| `launchpad/volume_find_page.py` | Toggle, dual columns, title/blurb, `type=` on fetch |
| `launchpad/storage_presets.py` | `showhost` on HPE 3PAR + Primera lists |
| `launchpad/ui/dashboard_view.py` | Button label Host / Volume Find |
| `launchpad/fc_wwpn_report.py`, `capacity_report.py`, `contingency_groups.py` | Nav link text (prefer full name where space allows) |
| `launchpad/config.py` | `1.6.64` |
| `tests/test_volume_find.py` | Host helpers |
| `tests/test_volume_find_api.py` | `type=host` cache/live |
| `tests/test_volume_find_page.py` | Toggle / title / columns |
| `tests/test_storage_presets_hpe_hosts.py` or extend existing preset tests | `showhost` present |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/host-volume-find -b feature/host-volume-find feature/contingency-groups
cd .worktrees/host-volume-find
# Ensure design spec is present (merge/cherry-pick docs/host-volume-find-design if needed)
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-24-host-volume-find-design.md
Test-Path docs\superpowers\plans\2026-07-24-host-volume-find.md
```

Expected: tip version (e.g. `1.6.63`), both paths `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Host find helpers (TDD)

**Files:**
- Modify: `launchpad/volume_find.py`
- Modify: `tests/test_volume_find.py`

**Interfaces:**
- Consumes: `is_volume_find_eligible`, `vendor_for_profile`, `volume_name_matches` (reuse for host names), `parse_fc_hosts` from `flashsystem_fc`
- Produces:
  - `host_name_matches(name: str, query: str) -> bool` — may be alias of `volume_name_matches`
  - `parse_showhost_hosts(output: str) -> list[dict[str, str]]` — keys: `host_name`, `wwpns` (wwpns may be `""`)
  - `hosts_from_card(card: dict) -> list[dict[str, str]]` — IBM: prefer `fc_hosts` list if present with `host_name`/`wwpns`; else parse `lshost` / `fc - hosts` from `command_results`; HPE: parse `showhost` from `command_results`
  - `find_hosts_in_cards(cards, query, *, monitor_enabled, source) -> list[dict]` — keys: `card_id`, `card_name`, `profile`, `vendor`, `host_name`, `wwpns`, `source`, `host` (card SSH host)

- [ ] **Step 1: Write failing tests** (append to `tests/test_volume_find.py`)

```python
from launchpad.volume_find import (
    find_hosts_in_cards,
    host_name_matches,
    hosts_from_card,
    parse_showhost_hosts,
)


def test_host_name_matches_substring_case_insensitive():
    assert host_name_matches("woo_esx_cluster", "ESX") is True
    assert host_name_matches("woo_esx_cluster", "nope") is False


def test_parse_showhost_hosts_basic():
    output = (
        "Id,Name,Persona,Port_WWN\n"
        "0,woo_esx_cluster,Generic,-,\n"
        "1,other_host,Generic,100000109BEE31E2,\n"
    )
    rows = parse_showhost_hosts(output)
    names = {r["host_name"] for r in rows}
    assert "woo_esx_cluster" in names
    assert "other_host" in names


def test_hosts_from_card_ibm_fc_hosts():
    card = {
        "id": 1,
        "name": "Woodland Hills, CA",
        "card_type": "ssh",
        "device_profile": "flashsystem_9500",
        "host": "10.244.66.227",
        "fc_hosts": [
            {"host_name": "woo_esx_cluster", "wwpns": "100000109BEE31E2"},
        ],
        "command_results": [],
    }
    hosts = hosts_from_card(card)
    assert hosts[0]["host_name"] == "woo_esx_cluster"
    assert "100000109BEE31E2" in hosts[0]["wwpns"]


def test_find_hosts_in_cards_sorted():
    cards = [
        {
            "id": 2,
            "name": "Zebra",
            "card_type": "ssh",
            "device_profile": "flashsystem_7200",
            "host": "1.1.1.1",
            "fc_hosts": [{"host_name": "b_host", "wwpns": ""}],
        },
        {
            "id": 1,
            "name": "Alpha",
            "card_type": "ssh",
            "device_profile": "flashsystem_7200",
            "host": "2.2.2.2",
            "fc_hosts": [{"host_name": "a_host", "wwpns": ""}],
        },
    ]
    monitor = {1: True, 2: True}
    found = find_hosts_in_cards(cards, "host", monitor_enabled=monitor, source="cache")
    assert [m["card_name"] for m in found] == ["Alpha", "Zebra"]
    assert found[0]["host_name"] == "a_host"
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\host-volume-find
python -m pytest tests/test_volume_find.py::test_host_name_matches_substring_case_insensitive tests/test_volume_find.py::test_parse_showhost_hosts_basic tests/test_volume_find.py::test_hosts_from_card_ibm_fc_hosts tests/test_volume_find.py::test_find_hosts_in_cards_sorted -v
```

Expected: FAIL (import / not defined).

- [ ] **Step 3: Implement helpers in `launchpad/volume_find.py`**

```python
from launchpad.flashsystem_fc import parse_fc_hosts, parse_lsvdisk_volumes  # parse_lsvdisk already used

def host_name_matches(name: str, query: str) -> bool:
    return volume_name_matches(name, query)


def parse_showhost_hosts(output: str) -> list[dict[str, str]]:
    """Parse HPE showhost CSV/table for Name (+ optional Port_WWN / WWN columns)."""
    # Mirror parse_showvv_volumes style: detect header, map Name -> host_name,
    # join WWPN-like columns into wwpns string; skip empty names.


def hosts_from_card(card: dict[str, Any]) -> list[dict[str, str]]:
    profile = str(card.get("device_profile") or "")
    out: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(host_name: str, wwpns: str = "") -> None:
        name = str(host_name or "").strip()
        if not name or name in seen:
            return
        seen.add(name)
        out.append({"host_name": name, "wwpns": str(wwpns or "").strip()})

    if vendor_for_profile(profile) == "ibm":
        fc_hosts = card.get("fc_hosts")
        if isinstance(fc_hosts, list) and fc_hosts:
            for h in fc_hosts:
                if isinstance(h, dict):
                    add(h.get("host_name") or h.get("name") or "", h.get("wwpns") or "")
            return out
        for item in card.get("command_results") or []:
            if not isinstance(item, dict) or item.get("error"):
                continue
            cmd = f"{item.get('label') or ''} {item.get('command') or ''}".lower()
            if "lshostvdiskmap" in cmd or "lsvdiskhostmap" in cmd or "host lun" in cmd:
                continue
            if "lshost" in cmd or "fc - hosts" in cmd:
                for row in parse_fc_hosts(str(item.get("output") or "")):
                    add(row.get("host_name") or "", row.get("wwpns") or "")
        return out

    # HPE
    for item in card.get("command_results") or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        cmd = f"{item.get('label') or ''} {item.get('command') or ''}".lower()
        if "showhost" in cmd:
            for row in parse_showhost_hosts(str(item.get("output") or "")):
                add(row.get("host_name") or "", row.get("wwpns") or "")
    return out


def find_hosts_in_cards(
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
        monitor_on = bool(
            monitor_enabled.get(card_id, monitor_enabled.get(str(card_id), False))
        )
        if not is_volume_find_eligible(card, monitor_on=monitor_on):
            continue
        profile = str(card.get("device_profile") or "")
        for host_row in hosts_from_card(card):
            if not host_name_matches(host_row["host_name"], query):
                continue
            matches.append(
                {
                    "card_id": card_id,
                    "card_name": str(card.get("name") or card_id or ""),
                    "profile": profile,
                    "vendor": vendor_for_profile(profile),
                    "host_name": host_row["host_name"],
                    "wwpns": host_row.get("wwpns") or "",
                    "source": source,
                    "host": str(card.get("host") or ""),
                }
            )
    return sorted(
        matches,
        key=lambda m: (
            str(m.get("card_name") or "").lower(),
            str(m.get("host_name") or "").lower(),
        ),
    )
```

Implement `parse_showhost_hosts` robustly (header Name/WWN columns or whitespace tables). Prefer reusing patterns from `parse_showvv_volumes`.

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/test_volume_find.py -q
```

Expected: PASS (all existing + new).

- [ ] **Step 5: Commit**

```powershell
git add launchpad/volume_find.py tests/test_volume_find.py
git commit -m "Add Host Find helpers for cache host lookup."
```

---

### Task 2: HPE `showhost` preset

**Files:**
- Modify: `launchpad/storage_presets.py` (`HP_3PAR_COMMANDS`, `HPE_PRIMERA_COMMANDS`)
- Test: add assert in existing preset test file if one covers HPE commands; else create `tests/test_hpe_showhost_preset.py`

**Interfaces:**
- Produces: both HPE lists include `("Hosts - host list", "showhost")` (or identical label)

- [ ] **Step 1: Failing test**

```python
from launchpad.storage_presets import HP_3PAR_COMMANDS, HPE_PRIMERA_COMMANDS


def test_hpe_presets_include_showhost():
    assert ("Hosts - host list", "showhost") in HP_3PAR_COMMANDS
    assert ("Hosts - host list", "showhost") in HPE_PRIMERA_COMMANDS
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_hpe_showhost_preset.py -v
```

- [ ] **Step 3: Add command after `showvv` in both lists**

```python
("Volumes - VV list", "showvv"),
("Hosts - host list", "showhost"),
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/storage_presets.py tests/test_hpe_showhost_preset.py
git commit -m "Add HPE showhost to 3PAR and Primera presets."
```

---

### Task 3: API `type=host` on find

**Files:**
- Modify: `launchpad/health_server.py` (`find_volumes` + GET `/api/volume-find` handler)
- Modify: `tests/test_volume_find_api.py`

**Interfaces:**
- Consumes: `find_hosts_in_cards`, `parse_showhost_hosts`, `parse_fc_hosts`, `host_name_matches`
- Produces: `find_volumes(self, query, *, mode="cache", find_type="volume")` — `find_type` in `{"volume","host"}`; host live IBM uses `svcinfo lshost -delim :`; host live HPE uses `showhost` via `run_ssh_auth_hpe_commands`

- [ ] **Step 1: Write failing API tests**

```python
def test_find_hosts_cache_uses_fc_hosts(monkeypatch):
    # Build HealthServer stub like existing cache volume test, with fc_hosts
    # result = server.find_volumes("woo", mode="cache", find_type="host")
    # assert matches include host_name, wwpns, host


def test_find_hosts_live_requires_unlock(monkeypatch):
    # same pattern as volume live unlock test with find_type="host"


def test_find_hosts_live_ibm_happy_path(monkeypatch):
    # mock _lun_run_command to return lshost delimited output
    # assert host_name match; wwpns may be ""


def test_find_volumes_default_type_unchanged(monkeypatch):
    # existing cache volume call without find_type still returns volumes
```

Wire GET handler:

```python
find_type = (query.get("type") or ["volume"])[0]
payload = server.find_volumes(q, mode=mode, find_type=find_type)
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_volume_find_api.py -v
```

- [ ] **Step 3: Implement**

In `find_volumes`:

```python
def find_volumes(
    self, query: str, *, mode: str = "cache", find_type: str = "volume"
) -> dict[str, Any]:
    type_key = str(find_type or "volume").strip().lower()
    if type_key not in {"volume", "host"}:
        raise ValueError("type must be volume or host")
    # ... existing empty/mode/sync/anderson/cards/monitor ...
    if type_key == "host":
        if mode_key == "cache":
            return {
                "matches": find_hosts_in_cards(
                    cards, q, monitor_enabled=monitor, source="cache"
                ),
                "errors": [],
            }
        if not self.is_unlocked():
            raise RuntimeError("LaunchPad must be unlocked to search hosts live.")
        matches, errors = [], []
        for card_dict in cards:
            # eligibility same as volume live loop
            # IBM: run("svcinfo lshost -delim :") -> parse_fc_hosts
            # HPE: run_ssh_auth_hpe_commands(..., ["showhost"]) -> parse_showhost_hosts
            # match host_name_matches; append host-shaped dict; wwpns from parse or ""
        # sort by card_name, host_name
        return {"matches": matches, "errors": errors}
    # existing volume branch unchanged
```

Import new helpers at top of health_server where volume_find imports live.

- [ ] **Step 4: Run — expect PASS**

```powershell
python -m pytest tests/test_volume_find_api.py tests/test_volume_find.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_volume_find_api.py
git commit -m "Support type=host on volume-find API cache and live."
```

---

### Task 4: Page UI — toggle + host columns

**Files:**
- Modify: `launchpad/volume_find_page.py`
- Modify: `tests/test_volume_find_page.py`
- Modify nav labels in: `launchpad/ui/dashboard_view.py`, `launchpad/fc_wwpn_report.py`, `launchpad/capacity_report.py`, `launchpad/contingency_groups.py` (and Health Dashboard HTML in `health_server.py` if it hardcodes “Volume Find”)

**Interfaces:**
- Produces: title `Host / Volume Find`; radio/buttons `Volume`|`Host`; fetch includes `&type=volume|host`; host table headers Host + WWPNs; placeholder switch

- [ ] **Step 1: Page contract tests**

```python
def test_host_volume_find_page_chrome():
    html = VOLUME_FIND_HTML
    assert "Host / Volume Find" in html
    assert 'name="find-type"' in html or 'id="find-type-host"' in html
    assert "host_name" in html or "WWPNs" in html
    assert "type=" in html
    assert "Search host name" in html or "Search host" in html
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Update HTML/JS**

- `<h1>Host / Volume Find</h1>` and title/footer.
- Blurb mentions volume and host.
- Toggle (two buttons or radios) default Volume; on change update placeholder and clear/re-run optional.
- `runSearch(mode)` builds URL:

```javascript
const findType = document.querySelector('input[name="find-type"]:checked')?.value
  || (hostToggleActive ? "host" : "volume");
const url = "/api/volume-find?q=" + encodeURIComponent(q)
  + "&mode=" + mode + "&type=" + encodeURIComponent(findType);
```

- `renderResults`: if host mode, columns Card | Site IP | Vendor | Host | WWPNs | Source using `m.host_name`, `m.wwpns`; else existing volume columns.
- Site IP edit unchanged (uses `m.host` / `card_id`).

- [ ] **Step 4: Update nav labels** to `Host / Volume Find` on dashboard primary control and peer page links (href stays `/volume-find`).

- [ ] **Step 5: Run page + related tests**

```powershell
python -m pytest tests/test_volume_find_page.py -q
```

- [ ] **Step 6: Commit**

```powershell
git add launchpad/volume_find_page.py launchpad/ui/dashboard_view.py launchpad/fc_wwpn_report.py launchpad/capacity_report.py launchpad/contingency_groups.py launchpad/health_server.py tests/test_volume_find_page.py
git commit -m "Add Host/Volume Find toggle and host result columns."
```

---

### Task 5: Version bump 1.6.64

**Files:**
- Modify: `launchpad/config.py`

- [ ] **Step 1: Set `APP_VERSION = "1.6.64"`**

- [ ] **Step 2: Verify**

```powershell
python -c "from launchpad.config import APP_VERSION; assert APP_VERSION == '1.6.64'"
python -m pytest tests/test_volume_find.py tests/test_volume_find_api.py tests/test_volume_find_page.py tests/test_hpe_showhost_preset.py -q
```

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.64 for Host / Volume Find."
```

---

### Task 6: Final review + PR

- [ ] **Step 1: Full related suite**

```powershell
python -m pytest tests/test_volume_find.py tests/test_volume_find_api.py tests/test_volume_find_page.py tests/test_hpe_showhost_preset.py -q
```

- [ ] **Step 2: Spec checklist**
  - Toggle Volume|Host ✓
  - Host columns + Site IP ✓
  - Cache + live host ✓
  - HPE showhost preset ✓
  - Path `/volume-find` ✓
  - Volume mode regression ✓
  - Version 1.6.64 ✓

- [ ] **Step 3: Open PR into `feature/contingency-groups`**

```powershell
git push -u origin HEAD
gh pr create --base feature/contingency-groups --title "Host / Volume Find (v1.6.64)" --body "## Summary
- Volume|Host toggle on /volume-find
- Host cache/live find (IBM lshost, HPE showhost)
- HPE showhost preset; version 1.6.64

## Test plan
- [ ] pytest volume-find + showhost tests
- [ ] UI: Host mode Find returns hosts; Site IP edit still works
- [ ] Volume mode unchanged
"
```

---

## Spec coverage (self-review)

| Spec item | Task |
|-----------|------|
| Rename UI Host / Volume Find | 4 |
| Path `/volume-find` | 4 (unchanged) |
| Volume\|Host toggle | 4 |
| Host columns + WWPNs | 1, 3, 4 |
| Hybrid cache/live | 1, 3 |
| Eligibility unchanged | 1 (reuse) |
| Substring match | 1 |
| HPE showhost preset | 2 |
| API `type=` | 3 |
| Nav labels | 4 |
| Version 1.6.64 | 5 |
| Non-goal: LUN maps | not implemented |

**Placeholder scan:** none intentional.  
**Type consistency:** `host_name`, `wwpns`, `find_type` / query `type`, `source` cache|live.
