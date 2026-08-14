# Hosts & Volumes, Volume Find, and Capacity Live Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the Storage Inventory orange progress bar and `done / total arrays · current site` on Hosts & Volumes Refresh live, Volume Find Find/Search live, and Capacity Refresh On Sites, plus a Loading servers bar on Capacity first load, shipping as **1.6.171**.

**Architecture:** Reuse `StorageInventoryProgress` as three separate HealthServer instances so Storage Inventory, Hosts & Volumes, and Volume Find never share a snapshot. HV and Volume Find keep one HTTP live/find request and poll a progress GET (~400ms). Capacity drives the bar from the existing sequential `POST /api/refresh/{id}` loop and from `loadCards` (no new progress API).

**Tech Stack:** Python, ThreadingHTTPServer, existing report HTML/JS, pytest.

**Spec:** `docs/superpowers/specs/2026-08-14-hv-find-capacity-progress-design.md`

## Global Constraints

- APP_VERSION bump to **1.6.171** only in the final version task. Do not bump in Tasks 1–3.
- Do not change Storage Inventory progress behavior or `/api/storage-inventory/progress`.
- Do not change Excel/CSV export, Find match rules, Capacity formulas, or Monitor toggles.
- Do not add per-array live HTTP from Hosts & Volumes or Volume Find (those stay one request).
- Do not invent fake N/M during Capacity card-list load.
- Do not add progress to other pages (System Connectivity, FlashCopy CGs, etc.).
- Quote JS HTML with single-quoted `class="..."`. Never `"<div class="` / `"<tr class="` in JS strings.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch, `LaunchPad-Install/`, or install zips.
- Work from a feature branch off `main` (do not land unfinished work on `main` mid-plan).
- Reuse class `StorageInventoryProgress` from `launchpad/storage_inventory.py` (do not rename it). Instantiate separately.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/health_server.py` | Extra `StorageInventoryProgress` instances; publish during HV live and `find_volumes`; `GET /api/host-volume-health/progress` and `GET /api/volume-find/progress` |
| `launchpad/host_volume_health_page.py` | Bar + poll + hide guards on Refresh live |
| `tests/test_host_volume_health_api.py` | Idle/after-scan snapshot, `card_id` total 1, progress route no unlock |
| `tests/test_host_volume_health_page.py` | Page markers + `progressActive` hide guard |
| `launchpad/volume_find_page.py` | Bar + poll on Find and Search live |
| `tests/test_volume_find_api.py` | Cache and live progress counts |
| `tests/test_volume_find_page.py` | Page markers + hide guard |
| `launchpad/capacity_report.py` | Client bar in `refreshAllSequential` and first `loadCards` |
| `tests/test_capacity_report_site.py` | Capacity bar markers |
| `launchpad/config.py` + three version pins | `1.6.171` (Task 4 only) |

---

### Task 1: Hosts & Volumes live progress

**Files:**
- Modify: `launchpad/health_server.py`
- Modify: `launchpad/host_volume_health_page.py`
- Modify: `tests/test_host_volume_health_api.py`
- Modify: `tests/test_host_volume_health_page.py`

**Interfaces:**
- Consumes: `StorageInventoryProgress` (already imported in `health_server.py`); existing `scan_host_volume_health_live(card_id=)`; existing `GET /api/host-volume-health/live`
- Produces:
  - `HealthServer._host_volume_health_progress: StorageInventoryProgress` (separate from `_storage_inventory_progress`)
  - `HealthServer.host_volume_health_progress_snapshot(self) -> dict` with keys `running: bool`, `done: int`, `total: int`, `current: str`
  - `HealthServer._eligible_volume_find_card_dicts(self, cards: list[dict], monitor: dict, *, card_id: int | None = None) -> list[dict]` — eligibility helper used again in Task 2
  - `GET /api/host-volume-health/progress` → snapshot JSON, **no unlock required**
  - Page polls that URL ~400ms during Refresh live; hide on finish / error / 403; `progressActive` false in `hideProgress`

**Scan loop:** Collect eligible cards first (same `is_volume_find_eligible` + `card_id` filter as today). `begin(len(eligible))`. Per card: `start_card(name)`, existing SSH/parse, `finish_card()`. `end()` in `finally`. Site filter `card_id` → total 1.

Idle snapshot: `{"running": False, "done": 0, "total": 0, "current": ""}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_host_volume_health_api.py`:

```python
def test_host_volume_health_progress_idle_and_after_scan(monkeypatch):
    server = HealthServer()
    _unlock(server)
    idle = server.host_volume_health_progress_snapshot()
    assert idle == {"running": False, "done": 0, "total": 0, "current": ""}
    card = HealthCard(
        card_id=1,
        name="Hartford",
        host="10.0.0.1",
        port=22,
        username="user",
        key_path="/tmp/key",
        device_profile="flashsystem_7200",
    )
    server._cards[1] = card
    server.set_monitor_enabled(card_id=1, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    monkeypatch.setattr(
        server,
        "_lun_run_command",
        lambda _card: (lambda command: "id:name:status\n0:h:online\n" if "lshost" in command else "id:name:mdisk_grp_name:status\n0:v:Pool0:online\n"),
    )
    server.scan_host_volume_health_live()
    done = server.host_volume_health_progress_snapshot()
    assert done["running"] is False
    assert done["done"] == 1
    assert done["total"] == 1


def test_host_volume_health_progress_card_id_total_one(monkeypatch):
    server = HealthServer()
    _unlock(server)
    for card_id, name in ((1, "SiteA"), (2, "SiteB")):
        server._cards[card_id] = HealthCard(
            card_id=card_id,
            name=name,
            host="10.0.0.1",
            port=22,
            username="user",
            key_path="/tmp/key",
            device_profile="flashsystem_7200",
        )
        server.set_monitor_enabled(card_id=card_id, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    monkeypatch.setattr(
        server,
        "_lun_run_command",
        lambda card: (
            lambda command: (
                f"id:name:status\n0:{card.name}_host:offline\n"
                if "lshost" in command
                else ""
            )
        ),
    )
    server.scan_host_volume_health_live(card_id=2)
    snap = server.host_volume_health_progress_snapshot()
    assert snap["total"] == 1
    assert snap["done"] == 1
    assert snap["running"] is False


def test_host_volume_health_progress_route_no_unlock():
    source = inspect.getsource(_HealthHandler.do_GET)
    assert "/api/host-volume-health/progress" in source
    chunk = source.split('if path == "/api/host-volume-health/progress"')[1].split("if path ==")[0]
    assert "is_unlocked" not in chunk
    assert "host_volume_health_progress_snapshot" in chunk
```

Append to `tests/test_host_volume_health_page.py`:

```python
def test_host_volume_health_progress_markers():
    html = HOST_VOLUME_HEALTH_HTML
    script = html.split("<script>", 1)[1]
    assert 'id="hv-progress-wrap"' in html
    assert 'id="hv-progress-bar"' in html
    assert "/api/host-volume-health/progress" in script
    assert "progressActive" in script
    assert '"<div class="' not in script


def test_host_volume_health_progress_ignores_polls_after_hide():
    script = HOST_VOLUME_HEALTH_HTML.split("<script>", 1)[1]
    hide_fn = script.split("function hideProgress()", 1)[1].split("function applyProgress", 1)[0]
    apply_fn = script.split("function applyProgress(data)", 1)[1].split("async function pollProgress", 1)[0]
    poll_fn = script.split("async function pollProgress()", 1)[1].split("async function refreshLive", 1)[0]
    refresh_fn = script.split("async function refreshLive()", 1)[1].split("function exportUrl", 1)[0]
    assert "progressActive = false" in hide_fn
    assert "if (!progressActive)" in apply_fn
    assert poll_fn.count("if (!progressActive)") >= 2
    assert "progressActive = true" in refresh_fn
    assert "hideProgress()" in refresh_fn
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_host_volume_health_api.py::test_host_volume_health_progress_idle_and_after_scan tests/test_host_volume_health_api.py::test_host_volume_health_progress_card_id_total_one tests/test_host_volume_health_api.py::test_host_volume_health_progress_route_no_unlock tests/test_host_volume_health_page.py::test_host_volume_health_progress_markers tests/test_host_volume_health_page.py::test_host_volume_health_progress_ignores_polls_after_hide -v`

Expected: FAIL (`host_volume_health_progress_snapshot` not defined)

- [ ] **Step 3: Write minimal implementation**

In `HealthServer.__init__` next to `self._storage_inventory_progress = StorageInventoryProgress()` add:

```python
        self._host_volume_health_progress = StorageInventoryProgress()
```

Add these methods on `HealthServer` (near `storage_inventory_progress_snapshot`):

```python
    def host_volume_health_progress_snapshot(self) -> dict:
        return self._host_volume_health_progress.snapshot()

    def _eligible_volume_find_card_dicts(
        self,
        cards: list[dict[str, Any]],
        monitor: dict,
        *,
        card_id: int | None = None,
    ) -> list[dict[str, Any]]:
        eligible: list[dict[str, Any]] = []
        for card_dict in cards:
            current_id = card_dict.get("id")
            if current_id is None:
                continue
            if card_id is not None and int(current_id) != int(card_id):
                continue
            monitor_on = bool(
                monitor.get(current_id, monitor.get(str(current_id), False))
            )
            if not is_volume_find_eligible(card_dict, monitor_on=monitor_on):
                continue
            eligible.append(card_dict)
        return eligible
```

In `scan_host_volume_health_live`, after building `cards` and `monitor`, replace the `for card_dict in cards:` loop (the inner `current_id` / eligibility / `continue` checks go away — the helper already did them) with:

```python
        eligible_dicts = self._eligible_volume_find_card_dicts(
            cards, monitor, card_id=card_id
        )
        eligible_cards: list[HealthCard] = []
        for card_dict in eligible_dicts:
            card = self._cards.get(int(card_dict["id"]))
            if card is not None:
                eligible_cards.append(card)
        self._host_volume_health_progress.begin(len(eligible_cards))
        try:
            for card in eligible_cards:
                self._host_volume_health_progress.start_card(str(card.name or ""))
                profile = str(card.device_profile or "")
                vendor = vendor_for_profile(profile)
                card_host = str(card.host or "")
                try:
                    if vendor == "hpe":
                        host_output, vv_output = run_ssh_auth_hpe_commands(
                            card.host,
                            card.port,
                            card.username,
                            ["showhost", "showvv"],
                            password=card.password,
                            key_path=card.key_path,
                            key_passphrase=card.key_passphrase,
                        )
                        host_rows = parse_showhost_hosts(host_output or "")
                        vol_rows = parse_showvv_volumes(vv_output or "")
                    else:
                        run = self._lun_run_command(card)
                        host_rows = parse_fc_hosts(run("svcinfo lshost -delim :"))
                        vol_rows = parse_lsvdisk_volumes(run("svcinfo lsvdisk -delim :"))
                    hosts.extend(
                        filter_problem_hosts(
                            host_rows,
                            card_name=card.name,
                            host=card_host,
                            vendor=vendor,
                            card_id=card.card_id,
                        )
                    )
                    volumes.extend(
                        filter_problem_volumes(
                            vol_rows,
                            card_name=card.name,
                            host=card_host,
                            vendor=vendor,
                            card_id=card.card_id,
                        )
                    )
                except Exception as exc:
                    errors.append(
                        {
                            "card_id": card.card_id,
                            "card_name": card.name,
                            "error": str(exc),
                        }
                    )
                self._host_volume_health_progress.finish_card()
        finally:
            self._host_volume_health_progress.end()
```

Keep the existing `hosts.sort` / `volumes.sort` / cache write after the `try/finally`. Do not change match/filter rules.

In `_HealthHandler.do_GET`, immediately before `if path == "/api/host-volume-health/live":`:

```python
        if path == "/api/host-volume-health/progress":
            self._send_json(server.host_volume_health_progress_snapshot())
            return
```

No unlock check.

In `launchpad/host_volume_health_page.py` CSS (with the other rules):

```css
    #hv-progress-wrap { margin-top: 12px; max-width: 420px; }
    #hv-progress-wrap[hidden] { display: none; }
    .hv-progress-track {
      height: 8px; border-radius: 999px; background: #0f141d; border: 1px solid var(--border);
      overflow: hidden;
    }
    #hv-progress-bar { height: 100%; width: 0; background: var(--accent); }
```

In the hero, after `.hero-actions` and before `<div class="status" id="hv-status">`:

```html
      <div id="hv-progress-wrap" hidden>
        <div class="hv-progress-track"><div id="hv-progress-bar"></div></div>
      </div>
```

In the script, after the `volumesBodyEl` consts, add progress helpers and change `refreshLive` to match Storage Inventory (poll `/api/host-volume-health/progress`):

```javascript
    const progressWrap = document.getElementById("hv-progress-wrap");
    const progressBar = document.getElementById("hv-progress-bar");
    let progressTimer = null;
    let progressActive = false;

    function hideProgress() {
      progressActive = false;
      if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
      }
      progressWrap.hidden = true;
      progressBar.style.width = "0%";
    }

    function applyProgress(data) {
      if (!progressActive) {
        return;
      }
      const total = Number(data && data.total) || 0;
      const done = Number(data && data.done) || 0;
      const current = String((data && data.current) || "").trim();
      progressWrap.hidden = false;
      const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
      progressBar.style.width = pct + "%";
      let label = "Scanning live…";
      if (total > 0) {
        label = done + " / " + total + " arrays";
        if (current) {
          label += " · " + current;
        }
      }
      statusEl.textContent = label;
    }

    async function pollProgress() {
      try {
        const res = await fetch("/api/host-volume-health/progress");
        if (!progressActive) {
          return;
        }
        const data = await res.json().catch(() => ({}));
        if (!progressActive) {
          return;
        }
        applyProgress(data);
      } catch (_err) {
        /* ignore poll errors while live request is in flight */
      }
    }
```

Replace `refreshLive` so it sets `progressActive = true`, `applyProgress({done:0,total:0,current:""})`, `setInterval(pollProgress, 400)`, `pollProgress()`, then fetches live. On 403: `hideProgress()` then unlock text. `finally { hideProgress(); refreshBtn.disabled = false; }`. Keep existing render/export enable logic on success.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_host_volume_health_api.py tests/test_host_volume_health_page.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py launchpad/host_volume_health_page.py tests/test_host_volume_health_api.py tests/test_host_volume_health_page.py
git commit -m "Add Hosts and Volumes live scan progress bar."
```

---

### Task 2: Volume Find Find and Search live progress

**Files:**
- Modify: `launchpad/health_server.py`
- Modify: `launchpad/volume_find_page.py`
- Modify: `tests/test_volume_find_api.py`
- Modify: `tests/test_volume_find_page.py`

**Interfaces:**
- Consumes: Task 1 `_eligible_volume_find_card_dicts`; `find_volumes_in_cards` / `find_hosts_in_cards`; existing `GET /api/volume-find`
- Produces:
  - `HealthServer._volume_find_progress: StorageInventoryProgress` (third instance; not shared with SI or HV)
  - `HealthServer.volume_find_progress_snapshot(self) -> dict` same shape as HV
  - `GET /api/volume-find/progress` → snapshot JSON, **no unlock required**
  - `find_volumes` walks eligible cards with `begin` / `start_card` / `finish_card` / `end` for **cache and live**, volume and host
  - Live still raises unlock `RuntimeError` **before** `begin`
  - Empty query still returns `{"matches": [], "errors": []}` without touching progress
  - Page polls during Find and Search live; empty query does not start the bar

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_volume_find_api.py`:

```python
import inspect

from launchpad.health_server import _HealthHandler


def test_volume_find_progress_idle_and_after_cache(monkeypatch):
    server = HealthServer()
    idle = server.volume_find_progress_snapshot()
    assert idle == {"running": False, "done": 0, "total": 0, "current": ""}
    card = HealthCard(
        card_id=1,
        name="Hartford",
        host="10.0.0.1",
        port=22,
        username="user",
        key_path="/tmp/key",
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
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    result = server.find_volumes("archvg", mode="cache")
    assert result["matches"]
    done = server.volume_find_progress_snapshot()
    assert done["running"] is False
    assert done["done"] == 1
    assert done["total"] == 1


def test_volume_find_progress_live_counts_cards(monkeypatch):
    server = HealthServer()
    _unlock(server)
    card = HealthCard(
        card_id=1,
        name="Hartford",
        host="10.0.0.1",
        port=22,
        username="user",
        key_path="/tmp/key",
        device_profile="flashsystem_7200",
    )
    server._cards[1] = card
    server.set_monitor_enabled(card_id=1, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    monkeypatch.setattr(
        server,
        "_lun_run_command",
        lambda _card: (lambda command: "id:name:mdisk_grp_name\n0:archvg_1:Pool0\n"),
    )
    server.find_volumes("archvg", mode="live")
    done = server.volume_find_progress_snapshot()
    assert done["running"] is False
    assert done["done"] == 1
    assert done["total"] == 1


def test_volume_find_empty_query_does_not_start_progress():
    server = HealthServer()
    server.find_volumes("", mode="cache")
    assert server.volume_find_progress_snapshot() == {
        "running": False,
        "done": 0,
        "total": 0,
        "current": "",
    }


def test_volume_find_progress_route_no_unlock():
    source = inspect.getsource(_HealthHandler.do_GET)
    assert "/api/volume-find/progress" in source
    chunk = source.split('if path == "/api/volume-find/progress"')[1].split("if path ==")[0]
    assert "is_unlocked" not in chunk
    assert "volume_find_progress_snapshot" in chunk
```

If `inspect` / `_HealthHandler` are already imported in that file, extend the existing import instead of duplicating.

Append to `tests/test_volume_find_page.py`:

```python
def test_volume_find_progress_markers():
    html = VOLUME_FIND_HTML
    script = html.split("<script>", 1)[1]
    assert 'id="vf-progress-wrap"' in html
    assert 'id="vf-progress-bar"' in html
    assert "/api/volume-find/progress" in script
    assert "progressActive" in script
    assert '"<div class="' not in script
    assert '"<tr class="' not in script


def test_volume_find_progress_ignores_polls_after_hide():
    script = VOLUME_FIND_HTML.split("<script>", 1)[1]
    hide_fn = script.split("function hideProgress()", 1)[1].split("function applyProgress", 1)[0]
    apply_fn = script.split("function applyProgress(data)", 1)[1].split("async function pollProgress", 1)[0]
    poll_fn = script.split("async function pollProgress()", 1)[1].split("async function runSearch", 1)[0]
    search_fn = script.split("async function runSearch(mode)", 1)[1].split("bodyEl.addEventListener", 1)[0]
    assert "progressActive = false" in hide_fn
    assert "if (!progressActive)" in apply_fn
    assert poll_fn.count("if (!progressActive)") >= 2
    assert "progressActive = true" in search_fn
    assert "hideProgress()" in search_fn
    assert 'if (!q)' in search_fn
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_volume_find_api.py::test_volume_find_progress_idle_and_after_cache tests/test_volume_find_api.py::test_volume_find_progress_live_counts_cards tests/test_volume_find_api.py::test_volume_find_empty_query_does_not_start_progress tests/test_volume_find_api.py::test_volume_find_progress_route_no_unlock tests/test_volume_find_page.py::test_volume_find_progress_markers tests/test_volume_find_page.py::test_volume_find_progress_ignores_polls_after_hide -v`

Expected: FAIL (`volume_find_progress_snapshot` not defined)

- [ ] **Step 3: Write minimal implementation**

In `HealthServer.__init__`:

```python
        self._volume_find_progress = StorageInventoryProgress()
```

Add:

```python
    def volume_find_progress_snapshot(self) -> dict:
        return self._volume_find_progress.snapshot()
```

In `_HealthHandler.do_GET`, immediately before `if path == "/api/volume-find":` (keep the existing volume-find handler unlock/400 behavior):

```python
        if path == "/api/volume-find/progress":
            self._send_json(server.volume_find_progress_snapshot())
            return
```

The existing handler is exact `if path == "/api/volume-find":`. Put the progress `if` **immediately before** that branch.

In `find_volumes`, after `sync_from_app` / Anderson rename / `cards` / `monitor`: live unlock checks **before** `begin`. Empty query still returns at the top unchanged. Replace the host and volume branches with:

```python
        if type_key == "host":
            if mode_key == "live" and not self.is_unlocked():
                raise RuntimeError("LaunchPad must be unlocked to search hosts live.")
            eligible = self._eligible_volume_find_card_dicts(cards, monitor)
            self._volume_find_progress.begin(len(eligible))
            try:
                if mode_key == "cache":
                    matches: list[dict[str, Any]] = []
                    for card_dict in eligible:
                        self._volume_find_progress.start_card(
                            str(card_dict.get("name") or "")
                        )
                        matches.extend(
                            find_hosts_in_cards(
                                [card_dict],
                                q,
                                monitor_enabled=monitor,
                                source="cache",
                            )
                        )
                        self._volume_find_progress.finish_card()
                    matches.sort(
                        key=lambda m: (
                            str(m.get("card_name") or "").lower(),
                            str(m.get("host_name") or "").lower(),
                        )
                    )
                    return {"matches": matches, "errors": []}
                matches = []
                errors: list[dict[str, Any]] = []
                for card_dict in eligible:
                    self._volume_find_progress.start_card(
                        str(card_dict.get("name") or "")
                    )
                    card = self._cards.get(int(card_dict["id"]))
                    if card is None:
                        self._volume_find_progress.finish_card()
                        continue
                    profile = str(card.device_profile or "")
                    try:
                        if vendor_for_profile(profile) == "hpe":
                            outputs = run_ssh_auth_hpe_commands(
                                card.host,
                                card.port,
                                card.username,
                                ["showhost"],
                                password=card.password,
                                key_path=card.key_path,
                                key_passphrase=card.key_passphrase,
                            )
                            output = outputs[0] if outputs else ""
                            host_rows = parse_showhost_hosts(output)
                        else:
                            run = self._lun_run_command(card)
                            output = run("svcinfo lshost -delim :")
                            host_rows = parse_fc_hosts(output)
                        for host_row in host_rows:
                            host_name = host_row.get("host_name") or ""
                            if not host_name_matches(host_name, q):
                                continue
                            matches.append(
                                {
                                    "card_id": card.card_id,
                                    "card_name": card.name,
                                    "profile": profile,
                                    "vendor": vendor_for_profile(profile),
                                    "host_name": host_name,
                                    "wwpns": host_row.get("wwpns") or "",
                                    "source": "live",
                                    "host": str(card.host or ""),
                                }
                            )
                    except Exception as exc:
                        errors.append(
                            {
                                "card_id": card.card_id,
                                "card_name": card.name,
                                "error": str(exc),
                            }
                        )
                    self._volume_find_progress.finish_card()
                matches.sort(
                    key=lambda m: (
                        str(m.get("card_name") or "").lower(),
                        str(m.get("host_name") or "").lower(),
                    )
                )
                return {"matches": matches, "errors": errors}
            finally:
                self._volume_find_progress.end()
        if mode_key == "live" and not self.is_unlocked():
            raise RuntimeError("LaunchPad must be unlocked to search volumes live.")
        eligible = self._eligible_volume_find_card_dicts(cards, monitor)
        self._volume_find_progress.begin(len(eligible))
        try:
            if mode_key == "cache":
                matches = []
                for card_dict in eligible:
                    self._volume_find_progress.start_card(
                        str(card_dict.get("name") or "")
                    )
                    matches.extend(
                        find_volumes_in_cards(
                            [card_dict],
                            q,
                            monitor_enabled=monitor,
                            source="cache",
                        )
                    )
                    self._volume_find_progress.finish_card()
                matches.sort(
                    key=lambda m: (
                        str(m.get("card_name") or "").lower(),
                        str(m.get("volume") or "").lower(),
                    )
                )
                return {"matches": matches, "errors": []}
            matches = []
            errors = []
            for card_dict in eligible:
                self._volume_find_progress.start_card(
                    str(card_dict.get("name") or "")
                )
                card = self._cards.get(int(card_dict["id"]))
                if card is None:
                    self._volume_find_progress.finish_card()
                    continue
                profile = str(card.device_profile or "")
                try:
                    if vendor_for_profile(profile) == "hpe":
                        outputs = run_ssh_auth_hpe_commands(
                            card.host,
                            card.port,
                            card.username,
                            ["showvv"],
                            password=card.password,
                            key_path=card.key_path,
                            key_passphrase=card.key_passphrase,
                        )
                        output = outputs[0] if outputs else ""
                        vols = parse_showvv_volumes(output)
                    else:
                        run = self._lun_run_command(card)
                        output = run("svcinfo lsvdisk -delim :")
                        vols = [
                            {
                                "name": r["name"],
                                "pool_or_cpg": r.get("pool") or "",
                            }
                            for r in parse_lsvdisk_volumes(output)
                        ]
                    for vol in vols:
                        if volume_name_matches(vol["name"], q):
                            matches.append(
                                {
                                    "card_id": card.card_id,
                                    "card_name": card.name,
                                    "profile": profile,
                                    "vendor": vendor_for_profile(profile),
                                    "volume": vol["name"],
                                    "pool_or_cpg": vol.get("pool_or_cpg") or "",
                                    "source": "live",
                                    "host": str(card.host or ""),
                                }
                            )
                except Exception as exc:
                    errors.append(
                        {
                            "card_id": card.card_id,
                            "card_name": card.name,
                            "error": str(exc),
                        }
                    )
                self._volume_find_progress.finish_card()
            matches.sort(
                key=lambda m: (
                    str(m.get("card_name") or "").lower(),
                    str(m.get("volume") or "").lower(),
                )
            )
            return {"matches": matches, "errors": errors}
        finally:
            self._volume_find_progress.end()
```

Keep `volume_name_matches` / `host_name_matches` unchanged. Do not call `begin` if live unlock raises.

In `launchpad/volume_find_page.py` CSS:

```css
    #vf-progress-wrap { margin-top: 12px; max-width: 420px; }
    #vf-progress-wrap[hidden] { display: none; }
    .vf-progress-track {
      height: 8px; border-radius: 999px; background: #0f141d; border: 1px solid var(--border);
      overflow: hidden;
    }
    #vf-progress-bar { height: 100%; width: 0; background: var(--accent); }
```

After the `hero-actions` `</div>` (status span stays inside hero-actions):

```html
      <div id="vf-progress-wrap" hidden>
        <div class="vf-progress-track"><div id="vf-progress-bar"></div></div>
      </div>
```

Add the same `hideProgress` / `applyProgress` / `pollProgress` helpers as Task 1, polling `/api/volume-find/progress`. Default `applyProgress` label when `total` is 0: use the current search text already set (`Searching cache…` / `Searching live…`) — set status **before** `applyProgress` so a total-0 poll does not overwrite with **Scanning live…**. Implement `applyProgress` as:

```javascript
    function applyProgress(data) {
      if (!progressActive) {
        return;
      }
      const total = Number(data && data.total) || 0;
      const done = Number(data && data.done) || 0;
      const current = String((data && data.current) || "").trim();
      progressWrap.hidden = false;
      const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
      progressBar.style.width = pct + "%";
      if (total > 0) {
        let label = done + " / " + total + " arrays";
        if (current) {
          label += " · " + current;
        }
        statusEl.textContent = label;
      }
    }
```

In `runSearch`: if `!q`, return **before** `setBusy` / progress (unchanged). After `setBusy(true)` and setting Searching cache/live text: `progressActive = true`, `applyProgress({done:0,total:0,current:""})`, start 400ms poll. On `res.status === 403`: `hideProgress()` then unlock/error text. `finally { hideProgress(); setBusy(false); }`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_volume_find_api.py tests/test_volume_find_page.py tests/test_host_volume_health_api.py tests/test_host_volume_health_page.py -v`

Expected: PASS (existing find tests must still pass)

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py launchpad/volume_find_page.py tests/test_volume_find_api.py tests/test_volume_find_page.py
git commit -m "Add Volume Find cache and live search progress bar."
```

---

### Task 3: Capacity Report client progress bar

**Files:**
- Modify: `launchpad/capacity_report.py`
- Modify: `tests/test_capacity_report_site.py`

**Interfaces:**
- Consumes: existing `refreshAllSequential`, `loadCards`, `refreshAllRunning`, `#refresh-status`
- Produces: client-only bar; **no** new progress API
  - Refresh On Sites: as each site **starts**, `done = index` (finished count), `total = cards.length`, `current = card.name` → status `{done} / {total} arrays · {current}`
  - After last site: hide bar, status **Refresh complete.**
  - Loading servers: show bar at 0% and **Loading servers…** only when `!cardsCache.length` and not already in Refresh On Sites / export; hide on success or failure (failure still **Could not load servers**)
  - 15s `setInterval(loadCards)` must **not** resurrect the bar after the first list render

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_capacity_report_site.py`:

```python
def test_capacity_report_progress_markers():
    html = CAPACITY_REPORT_HTML
    script = html.split("<script>", 1)[1]
    assert 'id="cap-progress-wrap"' in html
    assert 'id="cap-progress-bar"' in html
    assert "function hideProgress()" in script
    assert "progressActive" in script
    assert "Loading servers…" in script or "Loading servers..." in script
    assert " / " in script and " arrays" in script
    assert "refreshAllSequential" in script
    assert "loadCards" in script
    assert '"<div class="' not in script


def test_capacity_refresh_updates_bar_as_site_starts():
    script = CAPACITY_REPORT_HTML.split("<script>", 1)[1]
    refresh_fn = script.split("async function refreshAllSequential()", 1)[1].split(
        "function updatePrintMeta", 1
    )[0]
    assert "progressActive = true" in refresh_fn
    assert "hideProgress()" in refresh_fn
    assert "Refresh complete." in refresh_fn
    assert "card.name" in refresh_fn
    assert "index" in refresh_fn


def test_capacity_load_cards_bar_only_when_cache_empty():
    script = CAPACITY_REPORT_HTML.split("<script>", 1)[1]
    load_fn = script.split("async function loadCards()", 1)[1].split(
        "if (printBtn)", 1
    )[0]
    assert "cardsCache.length" in load_fn
    assert "hideProgress()" in load_fn
    assert "Could not load servers" in load_fn
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capacity_report_site.py::test_capacity_report_progress_markers tests/test_capacity_report_site.py::test_capacity_refresh_updates_bar_as_site_starts tests/test_capacity_report_site.py::test_capacity_load_cards_bar_only_when_cache_empty -v`

Expected: FAIL (`cap-progress-wrap` not in HTML)

- [ ] **Step 3: Write minimal implementation**

In `launchpad/capacity_report.py` CSS (near `.refresh-status`):

```css
    #cap-progress-wrap { margin-top: 12px; max-width: 420px; }
    #cap-progress-wrap[hidden] { display: none; }
    .cap-progress-track {
      height: 8px; border-radius: 999px; background: #0f141d; border: 1px solid var(--border);
      overflow: hidden;
    }
    #cap-progress-bar { height: 100%; width: 0; background: var(--accent); }
```

After the hero-actions `</div>` (the one that contains `#refresh-status`), before `<p id="print-meta"`:

```html
      <div id="cap-progress-wrap" hidden>
        <div class="cap-progress-track"><div id="cap-progress-bar"></div></div>
      </div>
```

In the script, after `const refreshStatusEl = document.getElementById("refresh-status");` (or near other consts):

```javascript
    const progressWrap = document.getElementById("cap-progress-wrap");
    const progressBar = document.getElementById("cap-progress-bar");
    let progressActive = false;

    function hideProgress() {
      progressActive = false;
      if (progressWrap) progressWrap.hidden = true;
      if (progressBar) progressBar.style.width = "0%";
    }

    function applyProgress(done, total, current) {
      if (!progressActive) {
        return;
      }
      if (progressWrap) progressWrap.hidden = false;
      const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
      if (progressBar) progressBar.style.width = pct + "%";
      let label = done + " / " + total + " arrays";
      const name = String(current || "").trim();
      if (name) {
        label += " · " + name;
      }
      if (refreshStatusEl) refreshStatusEl.textContent = label;
    }
```

In `refreshAllSequential`, after the empty-cards early return, before the `for` loop:

```javascript
        progressActive = true;
        applyProgress(0, cards.length, cards[0] ? cards[0].name : "");
```

Inside the loop, **before** `await refreshCard(card.id)`:

```javascript
          applyProgress(index, cards.length, card.name);
```

After `renderAll` / **Refresh complete.**, and in the existing `finally`, call `hideProgress()` (set **Refresh complete.** after hide so hide does not clear that text — `hideProgress` must not touch `refreshStatusEl`).

If the empty-cards path returns early, do not show the bar.

In `loadCards`:

```javascript
        const exportBusy =
          (excelBtn && excelBtn.disabled) || (dellReportBtn && dellReportBtn.disabled);
        const showLoadBar =
          !refreshAllRunning && !exportBusy && !cardsCache.length;
        if (showLoadBar) {
          progressActive = true;
          if (progressWrap) progressWrap.hidden = false;
          if (progressBar) progressBar.style.width = "0%";
          if (refreshStatusEl) refreshStatusEl.textContent = "Loading servers…";
        } else if (refreshStatusEl && !refreshAllRunning && !exportBusy) {
          refreshStatusEl.textContent = "Loading servers from LaunchPad...";
        }
```

Keep the existing `sitesEl` empty-state when `!cardsCache.length`. After `renderAll` / success path: `if (showLoadBar) hideProgress();`. In the `catch`: `if (showLoadBar) hideProgress();` then existing **Could not load servers**.

Declare `showLoadBar` with `let` at the start of `loadCards` so catch can see it (`let showLoadBar = false;` then set it in try).

Do not add a progress GET for Capacity.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_capacity_report_site.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/capacity_report.py tests/test_capacity_report_site.py
git commit -m "Add Capacity Report refresh and loading progress bar."
```

---

### Task 4: Bump APP_VERSION to 1.6.171

**Files:**
- Modify: `launchpad/config.py` (`APP_VERSION = "1.6.171"`)
- Modify: `tests/test_system_connectivity_version.py` (assert `1.6.171`; rename to `test_app_version_16171` if you touch the name)
- Modify: `tests/test_capacity_unit_js.py` (`test_app_version_153` assertion → `1.6.171`)
- Modify: `tests/test_hadoop_sudo_wire.py` (assertion → `1.6.171`; rename to `test_version_171` if you touch the name)

**Interfaces:**
- Consumes: Tasks 1–3 complete
- Produces: `APP_VERSION == "1.6.171"`

On this branch `APP_VERSION` is `1.6.170`. Set **1.6.171**.

- [ ] **Step 1: Write the failing assertion change**

Set the three test assertions to `"1.6.171"`. Do not change `config.py` yet.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_system_connectivity_version.py tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py -k version -v`

Expected: FAIL (`1.6.170` != `1.6.171`)

- [ ] **Step 3: Bump version**

In `launchpad/config.py`: `APP_VERSION = "1.6.171"`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_system_connectivity_version.py tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py tests/test_host_volume_health_page.py tests/test_volume_find_page.py tests/test_capacity_report_site.py -k "version or progress" -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py
git commit -m "Bump version to 1.6.171 for report live progress bars."
```

---

## Spec coverage

| Spec requirement | Task |
|------------------|------|
| HV Refresh live bar + poll | 1 |
| HV `card_id` total 1 | 1 |
| `GET /api/host-volume-health/progress` no unlock | 1 |
| Live still unlock-gated | 1 (unchanged live) |
| `progressActive` hide / no resurrect | 1, 2, 3 |
| Volume Find Find (cache) and Search live | 2 |
| `GET /api/volume-find/progress` no unlock | 2 |
| Cache mode real N/M | 2 |
| Empty query no bar | 2 |
| Capacity Refresh On Sites client bar, start_card semantics | 3 |
| Capacity Loading servers bar, no fake N/M | 3 |
| Interval load must not resurrect bar | 3 |
| Storage Inventory unchanged | global |
| JS class-quote safety | 1, 2, 3 |
| APP_VERSION 1.6.171 | 4 |
