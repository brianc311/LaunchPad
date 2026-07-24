# Volume Find Site IP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an editable Site IP column on Volume Find (Health Card host as `https://…`), persist host updates to the card DB when unlocked, and one-time rename WILLIAMSTON (ANDERSON) SC → Anderson, SC.

**Architecture:** Pure helpers for host normalize + Anderson match/rename decision. `find_volumes` matches gain `host`. HealthServer gets a card-patch callback (like settings backend), `POST /api/volume-find/card-host`, and rename-on-unlock. Volume Find page adds Site IP column with inline edit.

**Tech Stack:** Existing HealthServer HTML/JS, SQLite `Database.update_card`, pytest.

**Spec:** `docs/superpowers/specs/2026-07-23-volume-find-site-ip-design.md`

## Global Constraints

- **Worktree:** `.worktrees/volume-find-site-ip` on `feature/volume-find-site-ip` from `feature/contingency-groups` tip (`APP_VERSION=1.6.58`, includes site-ip design commit)
- Site IP = Health Card **host**; display as `https://{host}`
- Inline edit in Volume Find results; Save updates DB host only
- Unlock required for save and for Anderson rename
- One-time rename: WILLIAMSTON (ANDERSON) SC → Anderson, SC (flexible whitespace); set host `10.244.25.158` only if host empty; skip if `Anderson, SC` already exists on another card
- Bump `APP_VERSION` to **1.6.59**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\volume-find-site-ip`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/volume_find.py` | `normalize_site_host`, `site_ip_href`, Anderson name match/rename helpers; include `host` on match dicts |
| `launchpad/health_server.py` | Patch callback; `update_volume_find_card_host`; `ensure_anderson_card_rename`; POST route; put `host` on find matches |
| `launchpad/app.py` | Wire card-patch callback on unlock (clear on lock) |
| `launchpad/volume_find_page.py` | Site IP column + inline edit UI |
| `launchpad/config.py` | `1.6.59` |
| `tests/test_volume_find.py` | normalize / href / rename helpers; host on cache matches |
| `tests/test_volume_find_api.py` | host in API; POST card-host; unlock gate; Anderson rename |
| `tests/test_volume_find_page.py` | Site IP column / edit / POST URL contracts |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/volume-find-site-ip -b feature/volume-find-site-ip feature/contingency-groups
cd .worktrees/volume-find-site-ip
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-23-volume-find-site-ip-design.md
Test-Path docs\superpowers\plans\2026-07-23-volume-find-site-ip.md
```

Expected: `1.6.58` (or tip), both paths `True` after plan is committed on tip (if plan only on main checkout, copy or commit plan first on contingency-groups then recreate worktree).

- [ ] **Step 2: No feature commit**

---

### Task 1: Host normalize + Anderson helpers

**Files:**
- Modify: `launchpad/volume_find.py`
- Modify: `tests/test_volume_find.py`

**Interfaces:**
- Produces:
  - `normalize_site_host(raw: str) -> str` — strip; remove leading `http://`/`https://`; strip trailing `/`; return stripped host (may be empty)
  - `site_ip_href(host: str) -> str` — `https://{host}` if host non-empty else `""`
  - `ANDERSON_TARGET_NAME = "Anderson, SC"`
  - `ANDERSON_DEFAULT_HOST = "10.244.25.158"`
  - `is_williamston_anderson_name(name: str) -> bool` — case-insensitive; flexible whitespace around `(ANDERSON)` / words matching WILLIAMSTON … ANDERSON … SC
  - `anderson_rename_plan(cards: list[dict]) -> dict | None` — if a card matches Williamston name and no *other* card has name `Anderson, SC`, return `{ "card_id", "new_name": "Anderson, SC", "new_host": <existing or default if empty> }`; else `None`

- [ ] **Step 1: Failing tests**

```python
from launchpad.volume_find import (
    ANDERSON_DEFAULT_HOST,
    ANDERSON_TARGET_NAME,
    anderson_rename_plan,
    is_williamston_anderson_name,
    normalize_site_host,
    site_ip_href,
)


def test_normalize_site_host():
    assert normalize_site_host("  https://10.244.25.158/  ") == "10.244.25.158"
    assert normalize_site_host("http://host.example") == "host.example"
    assert normalize_site_host("10.1.2.3") == "10.1.2.3"
    assert normalize_site_host("   ") == ""


def test_site_ip_href():
    assert site_ip_href("10.244.25.158") == "https://10.244.25.158"
    assert site_ip_href("") == ""


def test_williamston_anderson_name_match():
    assert is_williamston_anderson_name("WILLIAMSTON (ANDERSON) SC") is True
    assert is_williamston_anderson_name("WILLIAMSTON  (ANDERSON)  SC") is True
    assert is_williamston_anderson_name("Anderson, SC") is False


def test_anderson_rename_plan_sets_default_host_when_empty():
    plan = anderson_rename_plan(
        [{"id": 11, "name": "WILLIAMSTON (ANDERSON) SC", "host": ""}]
    )
    assert plan == {
        "card_id": 11,
        "new_name": ANDERSON_TARGET_NAME,
        "new_host": ANDERSON_DEFAULT_HOST,
    }


def test_anderson_rename_plan_keeps_host_and_skips_conflict():
    assert anderson_rename_plan(
        [{"id": 11, "name": "WILLIAMSTON (ANDERSON) SC", "host": "10.9.9.9"}]
    )["new_host"] == "10.9.9.9"
    assert (
        anderson_rename_plan(
            [
                {"id": 1, "name": "Anderson, SC", "host": "1.1.1.1"},
                {"id": 11, "name": "WILLIAMSTON (ANDERSON) SC", "host": ""},
            ]
        )
        is None
    )
    assert anderson_rename_plan([{"id": 11, "name": "Anderson, SC", "host": "x"}]) is None
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\volume-find-site-ip
python -m pytest tests/test_volume_find.py -k "normalize or site_ip or williamston or anderson_rename" -v
```

- [ ] **Step 3: Implement helpers in `volume_find.py`**

Use `urllib.parse` only if needed; simple string strip is enough. Matching: normalize spaces, casefold, check contains `williamston` and `anderson` and ends with / contains `sc` — or regex `williamston\s*\(\s*anderson\s*\)\s*sc`. Prefer explicit regex for the known label.

- [ ] **Step 4: PASS + commit**

```powershell
git add launchpad/volume_find.py tests/test_volume_find.py
git commit -m "Add Volume Find site-host normalize and Anderson rename helpers."
```

---

### Task 2: Include `host` on find matches

**Files:**
- Modify: `launchpad/volume_find.py` (`find_volumes_in_cards`)
- Modify: `launchpad/health_server.py` (`find_volumes` live branch)
- Modify: `tests/test_volume_find.py`, `tests/test_volume_find_api.py`

**Interfaces:**
- Produces: every match dict includes `"host": str` from `card.get("host")` (cache) or `card.host` (live)

- [ ] **Step 1: Failing tests**

Extend cache find test to assert `"host"` on matches. Add/adjust API cache test so HealthCard has a host and response includes it.

- [ ] **Step 2: FAIL → implement**

In `find_volumes_in_cards` match append, add `"host": str(card.get("host") or "")`.  
In live match append, add `"host": str(card.host or "")`.  
Ensure `list_cards` / `to_api` already exposes `host` (it does).

- [ ] **Step 3: PASS + commit**

```powershell
git add launchpad/volume_find.py launchpad/health_server.py tests/test_volume_find.py tests/test_volume_find_api.py
git commit -m "Include Health Card host on Volume Find match results."
```

---

### Task 3: Card-host API + Anderson rename + app wire

**Files:**
- Modify: `launchpad/health_server.py`
- Modify: `launchpad/app.py`
- Modify: `tests/test_volume_find_api.py`

**Interfaces:**
- Produces:
  - `HealthServer.set_card_patcher(patcher: Callable[..., dict] | None)`  
    Signature of patcher: `(card_id: int, *, host: str | None = None, name: str | None = None) -> dict` returning `{card_id, host, name}` after DB update + re-register into HealthServer (or HealthServer updates `_cards` after patcher returns).
  - `HealthServer.update_volume_find_card_host(card_id: int, host: str) -> dict` — unlock required; normalize; reject empty; call patcher; update in-memory `HealthCard.host`
  - `HealthServer.ensure_anderson_card_rename() -> dict | None` — unlock required; `anderson_rename_plan` over `list_cards`; if plan, call patcher with name (+ host if needed); update in-memory card; return applied plan or `None`
  - `POST /api/volume-find/card-host` JSON body `{card_id, host}` → update; also call `ensure_anderson_card_rename()` best-effort before/after (or on GET volume-find when unlocked — prefer call rename from POST and from `find_volumes` when unlocked so open/search triggers rename)
  - App `_wire_health_sync`: set patcher that `get_card` → build update dict from Card fields → apply host/name → `update_card` → `register_card` / sync so HealthServer sees new values; clear patcher on lock

- [ ] **Step 1: Failing API tests**

```python
def test_update_card_host_requires_unlock(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(server, "is_unlocked", lambda: False)
    try:
        server.update_volume_find_card_host(1, "10.1.1.1")
        assert False
    except RuntimeError as exc:
        assert "unlock" in str(exc).lower()


def test_update_card_host_normalizes_and_patches():
    server = HealthServer()
    # unlock + patcher
    applied = {}

    def patcher(card_id, *, host=None, name=None):
        applied["card_id"] = card_id
        applied["host"] = host
        applied["name"] = name
        return {"card_id": card_id, "host": host or "", "name": name or "Site"}

    server.set_card_patcher(patcher)
    monkeypatch_unlock(server)  # or set_settings_backend dummies
    # ensure card exists in _cards with old host
    ...
    result = server.update_volume_find_card_host(1, "https://10.244.25.158/")
    assert result["host"] == "10.244.25.158"
    assert applied["host"] == "10.244.25.158"


def test_ensure_anderson_rename_idempotent():
    ...


def test_api_volume_find_card_host_route_declared():
    import inspect
    from launchpad.health_server import _HealthHandler
    src = inspect.getsource(_HealthHandler.do_POST)  # or do_GET if placed oddly — use do_POST
    assert "/api/volume-find/card-host" in src
```

Adapt to real HealthCard construction and unlock pattern from existing API tests.

- [ ] **Step 2: Implement**

Sketch app patcher:

```python
def patch_card(card_id: int, *, host: str | None = None, name: str | None = None) -> dict:
    card = db.get_card(card_id)
    if card is None:
        raise ValueError(f"Unknown card id {card_id}")
    data = {
        "name": name if name is not None else card.name,
        "card_type": card.card_type,
        "host": host if host is not None else card.host,
        # ... all other Card fields for update_card ...
    }
    db.update_card(card_id, data)
    server = get_health_server()
    # update in-memory if present
    with server._lock:
        hc = server._cards.get(card_id)
        if hc is not None:
            if host is not None:
                hc.host = data["host"]
            if name is not None:
                hc.name = data["name"]
    return {"card_id": card_id, "host": data["host"], "name": data["name"]}
```

Prefer updating memory inside HealthServer methods after patcher returns so app patcher only touches DB; then HealthServer sets `card.host` / `card.name`.

Call `ensure_anderson_card_rename()` at start of `find_volumes` when `is_unlocked()` so opening Find after unlock renames without a separate click.

POST handler: parse JSON, call `update_volume_find_card_host`, return JSON; 403/400 as appropriate.

- [ ] **Step 3: PASS**

```powershell
python -m pytest tests/test_volume_find_api.py tests/test_volume_find.py -q
```

- [ ] **Step 4: Commit**

```powershell
git add launchpad/health_server.py launchpad/app.py tests/test_volume_find_api.py
git commit -m "Add Volume Find card-host save API and Anderson rename."
```

---

### Task 4: Volume Find page Site IP UI

**Files:**
- Modify: `launchpad/volume_find_page.py`
- Modify: `tests/test_volume_find_page.py`

**Interfaces:**
- Produces: table header **Site IP**; cells with link or `—`; inline edit + Save/Cancel; `POST /api/volume-find/card-host`; colspan updates to 6

- [ ] **Step 1: Contract tests**

```python
def test_volume_find_site_ip_ui():
    html = VOLUME_FIND_HTML
    for text in (
        "Site IP",
        "/api/volume-find/card-host",
        "https://",
        "colspan=\"6\"",
    ):
        assert text in html
```

(Adjust strings to match actual markup you implement — e.g. `site-ip`, `save-host` ids.)

- [ ] **Step 2: Implement UI**

- Add `<th>Site IP</th>` after Card
- `renderMatches`: Site IP cell with `data-card-id`, link via `https://` + host, or em dash; include Edit control
- Edit mode: input + Save/Cancel; Save POSTs JSON; on ok, update all rows with that card_id; on 403 show status unlock message
- Keep XSS escaping for displayed text; for `href` only allow after normalize (host from API already trusted; still escape attribute)

- [ ] **Step 3: PASS + commit**

```powershell
python -m pytest tests/test_volume_find_page.py tests/test_volume_find.py tests/test_volume_find_api.py -q
git add launchpad/volume_find_page.py tests/test_volume_find_page.py
git commit -m "Add editable Site IP column to Volume Find page."
```

---

### Task 5: Version bump 1.6.59

**Files:**
- Modify: `launchpad/config.py`

- [ ] **Step 1:** `APP_VERSION = "1.6.59"`

- [ ] **Step 2: Smoke**

```powershell
python -c "from launchpad.config import APP_VERSION; from launchpad.volume_find_page import VOLUME_FIND_HTML; assert APP_VERSION=='1.6.59'; assert 'Site IP' in VOLUME_FIND_HTML; print('ok')"
python -m pytest tests/test_volume_find.py tests/test_volume_find_api.py tests/test_volume_find_page.py -q
```

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.59 for Volume Find Site IP."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| normalize / href / Anderson helpers | 1 |
| `host` on matches | 2 |
| POST card-host + unlock + DB patch + rename | 3 |
| Site IP column + inline edit | 4 |
| Version 1.6.59 | 5 |

## Self-review notes

- Do not store a second IP field — host only.
- Patcher must preserve encrypted credential fields when calling `update_card`.
- Rename is idempotent and conflict-safe per spec.
