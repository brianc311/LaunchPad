# Snapshot Schedule Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let operators set per-site Auto/Custom snapshot schedules (interval, start, time, hold, one-offs) on the Snapshot Schedule page, persist them like notes, and reflect them in calendars and Excel.

**Architecture:** Pure Python helpers normalize and apply overrides; health server stores JSON in settings key `snapshot_schedule_overrides`; the schedule page loads/saves via GET/POST APIs with localStorage fallback; export applies the same overrides so Excel matches the page. Still planning-only — no device SSH schedule commands.

**Tech Stack:** Python 3, openpyxl, local HTTP health server, embedded JS in `snapshot_schedule.py`, SQLite settings via existing `db.get_setting` / `db.set_setting`.

**Spec:** `docs/superpowers/specs/2026-07-17-snapshot-schedule-edit-design.md`

## Global Constraints

- Setting key must be exactly `snapshot_schedule_overrides`.
- Override shape: `mode` (`auto`|`custom`), `held` (bool), `interval_days` (int ≥ 2), `start_date` (`YYYY-MM-DD`), `time` (`HH:MM`), `one_offs` (list of `{date, time, label?}`).
- Switching Custom → Auto keeps dormant fields (`mode` only flips); do not delete the map entry unless user clears/resets.
- Hold works in both Auto and Custom; held sites show empty calendars.
- Times are local wall-clock; no timezone UI.
- Footer must keep planning-only wording (LaunchPad does not create snapshots automatically).
- Bump `APP_VERSION` to `1.6.18` in the final task.
- Prefer matching existing notes API patterns in `health_server.py`.
- Do not commit unless the user asked for commits in this session; skip commit steps or stop before them if unclear.

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/snapshot_schedule_overrides.py` | Normalize, validate, serialize overrides; format one-offs for Excel |
| `tests/test_snapshot_schedule_overrides.py` | Unit tests for normalize/apply helpers |
| `launchpad/snapshot_schedule_export.py` | Apply overrides in `build_schedule_rows`; new Excel columns |
| `launchpad/health_server.py` | GET/POST `/api/snapshot-schedule-overrides`; pass overrides into export |
| `launchpad/snapshot_schedule.py` | Page UI + JS: mode/hold/editors, calendars with times, persist |
| `launchpad/config.py` | Version `1.6.18` |
| `launchpad/app.py` | No change expected (settings backend already wired) |

---

### Task 1: Override helpers + unit tests

**Files:**
- Create: `launchpad/snapshot_schedule_overrides.py`
- Create: `tests/test_snapshot_schedule_overrides.py`

**Interfaces:**
- Produces:
  - `SNAPSHOT_OVERRIDES_SETTING = "snapshot_schedule_overrides"`
  - `DEFAULT_CUSTOM_TIME = "02:00"`
  - `normalize_override(raw: Any) -> dict[str, Any] | None`
  - `normalize_overrides_map(raw: Any) -> dict[str, dict[str, Any]]`
  - `format_one_offs_summary(one_offs: list[dict[str, Any]]) -> str`
  - `parse_time_hhmm(value: str) -> tuple[int, int] | None`
  - `parse_date_yyyy_mm_dd(value: str) -> date | None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_snapshot_schedule_overrides.py`:

```python
from datetime import date

from launchpad.snapshot_schedule_overrides import (
    DEFAULT_CUSTOM_TIME,
    format_one_offs_summary,
    normalize_override,
    normalize_overrides_map,
    parse_date_yyyy_mm_dd,
    parse_time_hhmm,
)


def test_normalize_override_defaults_and_cleans():
    out = normalize_override(
        {
            "mode": "CUSTOM",
            "held": 1,
            "interval_days": 7,
            "start_date": "2026-07-20",
            "time": "2:00",
            "one_offs": [
                {"date": "2026-08-01", "time": "14:30", "label": " Change window "},
                {"date": "bad", "time": "99:99"},
            ],
        }
    )
    assert out is not None
    assert out["mode"] == "custom"
    assert out["held"] is True
    assert out["interval_days"] == 7
    assert out["start_date"] == "2026-07-20"
    assert out["time"] == "02:00"
    assert out["one_offs"] == [
        {"date": "2026-08-01", "time": "14:30", "label": "Change window"}
    ]


def test_normalize_override_rejects_garbage():
    assert normalize_override(None) is None
    assert normalize_override("nope") is None


def test_normalize_overrides_map_keys_as_strings():
    mapping = normalize_overrides_map({42: {"mode": "auto", "held": False}})
    assert "42" in mapping
    assert mapping["42"]["mode"] == "auto"


def test_parse_helpers():
    assert parse_time_hhmm("02:00") == (2, 0)
    assert parse_time_hhmm("2:5") == (2, 5)
    assert parse_time_hhmm("25:00") is None
    assert parse_date_yyyy_mm_dd("2026-07-20") == date(2026, 7, 20)
    assert parse_date_yyyy_mm_dd("2026-13-01") is None


def test_format_one_offs_summary():
    text = format_one_offs_summary(
        [
            {"date": "2026-08-01", "time": "14:30", "label": "Window"},
            {"date": "2026-08-02", "time": "09:00"},
        ]
    )
    assert "2026-08-01 14:30 Window" in text
    assert "2026-08-02 09:00" in text
    assert DEFAULT_CUSTOM_TIME == "02:00"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_snapshot_schedule_overrides.py -v`

Expected: FAIL with `ModuleNotFoundError` or import error for `launchpad.snapshot_schedule_overrides`.

- [ ] **Step 3: Implement helpers**

Create `launchpad/snapshot_schedule_overrides.py`:

```python
"""Normalize and format Snapshot Schedule per-card overrides."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

SNAPSHOT_OVERRIDES_SETTING = "snapshot_schedule_overrides"
DEFAULT_CUSTOM_TIME = "02:00"

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def parse_time_hhmm(value: str) -> tuple[int, int] | None:
    text = str(value or "").strip()
    match = _TIME_RE.match(text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def format_time_hhmm(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def parse_date_yyyy_mm_dd(value: str) -> date | None:
    text = str(value or "").strip()
    if not _DATE_RE.match(text):
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _normalize_one_off(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    parsed_date = parse_date_yyyy_mm_dd(str(raw.get("date") or ""))
    parsed_time = parse_time_hhmm(str(raw.get("time") or ""))
    if not parsed_date or not parsed_time:
        return None
    label = str(raw.get("label") or "").strip()
    item = {
        "date": parsed_date.isoformat(),
        "time": format_time_hhmm(*parsed_time),
    }
    if label:
        item["label"] = label
    return item


def normalize_override(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    mode = str(raw.get("mode") or "auto").strip().lower()
    if mode not in {"auto", "custom"}:
        mode = "auto"
    held = bool(raw.get("held"))
    try:
        interval_days = int(raw.get("interval_days") or 7)
    except (TypeError, ValueError):
        interval_days = 7
    interval_days = max(2, min(365, interval_days))
    start_raw = str(raw.get("start_date") or "").strip()
    start_date = parse_date_yyyy_mm_dd(start_raw)
    time_raw = str(raw.get("time") or DEFAULT_CUSTOM_TIME).strip()
    parsed_time = parse_time_hhmm(time_raw) or parse_time_hhmm(DEFAULT_CUSTOM_TIME)
    assert parsed_time is not None
    one_offs_raw = raw.get("one_offs") or []
    one_offs: list[dict[str, str]] = []
    if isinstance(one_offs_raw, list):
        for item in one_offs_raw:
            cleaned = _normalize_one_off(item)
            if cleaned:
                one_offs.append(cleaned)
    return {
        "mode": mode,
        "held": held,
        "interval_days": interval_days,
        "start_date": start_date.isoformat() if start_date else "",
        "time": format_time_hhmm(*parsed_time),
        "one_offs": one_offs,
    }


def normalize_overrides_map(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        cleaned = normalize_override(value)
        if cleaned is not None:
            out[str(key)] = cleaned
    return out


def format_one_offs_summary(one_offs: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in one_offs or []:
        date_s = str(item.get("date") or "").strip()
        time_s = str(item.get("time") or "").strip()
        label = str(item.get("label") or "").strip()
        if not date_s or not time_s:
            continue
        chunk = f"{date_s} {time_s}"
        if label:
            chunk = f"{chunk} {label}"
        parts.append(chunk)
    return "; ".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_snapshot_schedule_overrides.py -v`

Expected: all PASS. If pytest is missing: `pip install pytest` then re-run.

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add launchpad/snapshot_schedule_overrides.py tests/test_snapshot_schedule_overrides.py
git commit -m "Add snapshot schedule override normalize helpers"
```

---

### Task 2: Apply overrides in Excel row builder

**Files:**
- Modify: `launchpad/snapshot_schedule_export.py`
- Modify: `tests/test_snapshot_schedule_overrides.py` (add export apply tests) OR create `tests/test_snapshot_schedule_export.py`

**Interfaces:**
- Consumes: `normalize_overrides_map`, `format_one_offs_summary`, `parse_date_yyyy_mm_dd` from Task 1
- Produces: `build_schedule_rows(..., overrides: dict[str, dict] | None = None)` with extra columns Mode, Time, Held, One-offs

- [ ] **Step 1: Write failing export tests**

Add to `tests/test_snapshot_schedule_export.py`:

```python
from launchpad.snapshot_schedule_export import SCHEDULE_HEADERS, build_schedule_rows


def _card(card_id: int, used_pct: float = 40.0) -> dict:
    return {
        "id": card_id,
        "name": f"Site{card_id}",
        "category": "Lab",
        "host": "10.0.0.1",
        "device_profile": "ibm_flashsystem",
        "model": "FS7300",
        "pools": [
            {
                "name": "Pool0",
                "used_pct": used_pct,
                "free_bytes": 1000,
            }
        ],
    }


def test_headers_include_override_columns():
    assert "Mode" in SCHEDULE_HEADERS
    assert "Time" in SCHEDULE_HEADERS
    assert "Held" in SCHEDULE_HEADERS
    assert "One-offs" in SCHEDULE_HEADERS


def test_custom_override_controls_frequency_and_starts():
    cards = [_card(1, used_pct=40.0)]
    overrides = {
        "1": {
            "mode": "custom",
            "held": False,
            "interval_days": 7,
            "start_date": "2026-07-20",
            "time": "02:00",
            "one_offs": [{"date": "2026-08-01", "time": "14:30", "label": "Window"}],
        }
    }
    rows = build_schedule_rows(cards, {}, threshold=80.0, overrides=overrides)
    assert len(rows) == 1
    row = rows[0]
    # Column indices follow SCHEDULE_HEADERS order
    headers = list(SCHEDULE_HEADERS)
    assert row[headers.index("Frequency")] == "WEEKLY"
    assert row[headers.index("Interval Days")] == 7
    assert "Jul 20, 2026" in str(row[headers.index("Starts")])
    assert row[headers.index("Mode")] == "custom"
    assert row[headers.index("Time")] == "02:00"
    assert row[headers.index("Held")] == "No"
    assert "2026-08-01 14:30 Window" in str(row[headers.index("One-offs")])


def test_manual_hold_overrides_capacity_hold():
    cards = [_card(1, used_pct=40.0)]
    overrides = {
        "1": {
            "mode": "auto",
            "held": True,
            "interval_days": 7,
            "start_date": "",
            "time": "02:00",
            "one_offs": [],
        }
    }
    rows = build_schedule_rows(cards, {}, threshold=80.0, overrides=overrides)
    assert rows[0][list(SCHEDULE_HEADERS).index("Status")] == "Flagged / Hold"
    assert rows[0][list(SCHEDULE_HEADERS).index("Held")] == "Yes"
```

- [ ] **Step 2: Run tests — expect FAIL** (headers / kwargs missing)

Run: `python -m pytest tests/test_snapshot_schedule_export.py -v`

- [ ] **Step 3: Update `SCHEDULE_HEADERS` and `build_schedule_rows`**

Replace headers with:

```python
SCHEDULE_HEADERS = (
    "Status",
    "Site",
    "Location",
    "Model",
    "IP",
    "Pool",
    "Used %",
    "Free",
    "Frequency",
    "Interval Days",
    "Starts",
    "Mode",
    "Time",
    "Held",
    "One-offs",
    "Notes",
)
```

Update signature:

```python
def build_schedule_rows(
    cards: list[dict[str, Any]],
    notes: dict[str, str],
    *,
    threshold: float = 80.0,
    groups: set[str] | None = None,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> list[tuple[Any, ...]]:
```

Inside the loop after computing auto `held` / `days` / `start`, apply override for `str(card.get("id"))`:

```python
from launchpad.snapshot_schedule_overrides import (
    format_one_offs_summary,
    normalize_override,
    parse_date_yyyy_mm_dd,
)

# after auto held/days computed, before building frequency:
ov_raw = (overrides or {}).get(str(card.get("id")))
ov = normalize_override(ov_raw) if ov_raw else None
mode = "auto"
time_out = ""
one_offs_text = ""
manual_held = False
if ov:
    mode = ov["mode"]
    manual_held = bool(ov["held"])
    if manual_held:
        held = True
        days = None
    elif mode == "custom":
        held = False
        days = int(ov["interval_days"])
        parsed_start = parse_date_yyyy_mm_dd(ov.get("start_date") or "")
        if parsed_start:
            start = datetime.combine(parsed_start, datetime.min.time()).astimezone().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            # Prefer local midnight from date — simpler:
            start = datetime(
                parsed_start.year, parsed_start.month, parsed_start.day
            )
        time_out = str(ov.get("time") or "")
        one_offs_text = format_one_offs_summary(list(ov.get("one_offs") or []))
```

Effective hold rules (Custom owns the schedule when not manually held):

```python
if ov and ov["held"]:
    held = True
    days = None
elif ov and ov["mode"] == "custom":
    held = False
    days = int(ov["interval_days"])
    # set start from start_date if valid; else keep auto stagger start
else:
    # existing auto held/days from capacity vs threshold
    pass
```

When appending the row tuple, add Mode / Time / Held / One-offs before Notes:

- `mode` = `ov["mode"]` if ov else `"auto"`
- `time_out` = recurring time when custom (else `""`)
- Held column = `"Yes"` if effective `held` else `"No"`
- `one_offs_text` = `format_one_offs_summary(...)` when custom

Also update `build_snapshot_schedule_workbook` and `export_snapshot_schedule_excel` to accept `overrides` and pass through.

- [ ] **Step 4: Run export tests — expect PASS**

Run: `python -m pytest tests/test_snapshot_schedule_export.py tests/test_snapshot_schedule_overrides.py -v`

- [ ] **Step 5: Commit (only if user asked)**

---

### Task 3: Health server GET/POST overrides + export wiring

**Files:**
- Modify: `launchpad/health_server.py` (notes handlers ~1690–1837, `HealthServer` ~1873–1946, export ~1693–1738)

**Interfaces:**
- Consumes: `SNAPSHOT_OVERRIDES_SETTING`, `normalize_override`, `normalize_overrides_map`
- Produces:
  - `HealthServer.get_snapshot_overrides() -> dict[str, dict]`
  - `HealthServer.set_snapshot_override(card_id, override) -> dict`
  - `HealthServer.set_snapshot_overrides(overrides) -> dict`
  - GET `/api/snapshot-schedule-overrides` → `{ overrides, persisted: True }`
  - POST same path → single or bulk
  - Export endpoint passes `overrides=server.get_snapshot_overrides()`

- [ ] **Step 1: Add HealthServer methods** (mirror notes)

After `SNAPSHOT_NOTES_SETTING = "snapshot_schedule_notes"`:

```python
from launchpad.snapshot_schedule_overrides import (
    SNAPSHOT_OVERRIDES_SETTING,
    normalize_override,
    normalize_overrides_map,
)
```

(Keep import near methods or top of file — follow file style; prefer top-level if other launchpad imports are top-level. If circular risk, lazy-import inside methods like export does.)

```python
def get_snapshot_overrides(self) -> dict[str, dict]:
    with self._lock:
        getter = self._get_setting
    if not getter:
        return {}
    raw = getter(SNAPSHOT_OVERRIDES_SETTING, "{}") or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return normalize_overrides_map(data)

def set_snapshot_override(self, card_id: int | str, override: dict) -> dict[str, dict]:
    with self._lock:
        getter = self._get_setting
        setter = self._set_setting
    if not getter or not setter:
        raise RuntimeError("LaunchPad must be unlocked to save schedule overrides.")
    cleaned = normalize_override(override)
    if cleaned is None:
        raise ValueError("Invalid schedule override")
    mapping = self.get_snapshot_overrides()
    mapping[str(card_id)] = cleaned
    setter(SNAPSHOT_OVERRIDES_SETTING, json.dumps(mapping))
    return mapping

def set_snapshot_overrides(self, overrides: dict) -> dict[str, dict]:
    with self._lock:
        setter = self._set_setting
    if not setter:
        raise RuntimeError("LaunchPad must be unlocked to save schedule overrides.")
    cleaned = normalize_overrides_map(overrides)
    setter(SNAPSHOT_OVERRIDES_SETTING, json.dumps(cleaned))
    return cleaned
```

- [ ] **Step 2: Wire GET/POST** next to snapshot-notes handlers

GET:

```python
if path == "/api/snapshot-schedule-overrides":
    self._send_json(
        {"overrides": server.get_snapshot_overrides(), "persisted": True}
    )
    return
```

POST (in `do_POST`):

```python
if path == "/api/snapshot-schedule-overrides":
    length = int(self.headers.get("Content-Length") or 0)
    raw = self.rfile.read(length) if length else b"{}"
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        self._send_json({"error": "Invalid JSON"}, status=400)
        return
    try:
        if "overrides" in payload and isinstance(payload["overrides"], dict):
            overrides = server.set_snapshot_overrides(payload["overrides"])
        else:
            card_id = payload.get("card_id")
            if card_id is None:
                self._send_json({"error": "card_id required"}, status=400)
                return
            overrides = server.set_snapshot_override(
                card_id, payload.get("override") or {}
            )
    except RuntimeError as exc:
        self._send_json({"error": str(exc)}, status=503)
        return
    except ValueError as exc:
        self._send_json({"error": str(exc)}, status=400)
        return
    self._send_json({"overrides": overrides, "persisted": True})
    return
```

- [ ] **Step 3: Pass overrides into workbook export**

In `/api/snapshot-schedule-export` handler, after notes:

```python
overrides = server.get_snapshot_overrides()
wb = build_snapshot_schedule_workbook(
    cards,
    notes,
    threshold=threshold,
    groups=groups,
    overrides=overrides,
)
```

Update `build_snapshot_schedule_workbook` signature accordingly. Update desktop `export_snapshot_schedule_excel` to load overrides the same way (via temporary HealthServer or settings — match how notes are loaded today at ~311).

- [ ] **Step 4: Smoke-check imports**

Run:

```powershell
python -c "from launchpad.health_server import HealthServer; s=HealthServer(); assert s.get_snapshot_overrides()=={}"
python -m pytest tests/test_snapshot_schedule_export.py tests/test_snapshot_schedule_overrides.py -v
```

Expected: PASS / empty overrides.

- [ ] **Step 5: Commit (only if user asked)**

---

### Task 4: Snapshot Schedule page UI + client logic

**Files:**
- Modify: `launchpad/snapshot_schedule.py`

**Interfaces:**
- Consumes: `/api/snapshot-schedule-overrides`
- Produces: Auto/Custom toggle, Hold checkbox, custom editors, calendars with times/one-offs, localStorage `launchpad.snapshotSchedule.overrides`

- [ ] **Step 1: Add CSS for badges and custom controls**

Near existing card styles, add:

```css
.badge-custom { background: #1d4ed8; color: #fff; }
.badge-hold { background: #c2410c; color: #fff; }
.sched-edit { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; align-items: end; }
.sched-edit label { display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: var(--muted); }
.sched-edit input { background: #0f172a; border: 1px solid #334155; color: #e2e8f0; border-radius: 6px; padding: 4px 6px; }
.oneoff-list { margin-top: 6px; font-size: 12px; }
.oneoff-list li { display: flex; gap: 8px; align-items: center; }
.cal-day.oneoff { outline: 2px solid #38bdf8; }
.mode-toggle button.active { background: #2563eb; color: #fff; }
```

- [ ] **Step 2: Add override state + load/save (mirror notes ~765–816)**

```javascript
const OVERRIDES_KEY = "launchpad.snapshotSchedule.overrides";
let overridesCache = {};
let overridesPersistTimer = null;
let overridesDbAvailable = false;

function loadOverridesLocal() {
  try {
    overridesCache = JSON.parse(localStorage.getItem(OVERRIDES_KEY) || "{}") || {};
  } catch (_e) {
    overridesCache = {};
  }
}

function saveOverridesLocal() {
  localStorage.setItem(OVERRIDES_KEY, JSON.stringify(overridesCache));
}

async function loadOverridesFromDb() {
  try {
    const res = await fetch("/api/snapshot-schedule-overrides");
    if (!res.ok) throw new Error("unavailable");
    const data = await res.json();
    overridesDbAvailable = Boolean(data.persisted);
    if (data.overrides && typeof data.overrides === "object") {
      overridesCache = { ...overridesCache, ...data.overrides };
      saveOverridesLocal();
    }
  } catch (_e) {
    overridesDbAvailable = false;
  }
}

function persistOverride(cardId) {
  saveOverridesLocal();
  if (!overridesDbAvailable) return;
  clearTimeout(overridesPersistTimer);
  overridesPersistTimer = setTimeout(async () => {
    try {
      await fetch("/api/snapshot-schedule-overrides", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          card_id: cardId,
          override: overridesCache[String(cardId)] || {
            mode: "auto",
            held: false,
            interval_days: 7,
            start_date: "",
            time: "02:00",
            one_offs: [],
          },
        }),
      });
    } catch (_e) { /* keep local */ }
  }, 400);
}

function getOverride(cardId) {
  return overridesCache[String(cardId)] || null;
}

function ensureOverride(cardId) {
  const key = String(cardId);
  if (!overridesCache[key]) {
    overridesCache[key] = {
      mode: "auto",
      held: false,
      interval_days: 7,
      start_date: "",
      time: "02:00",
      one_offs: [],
    };
  }
  return overridesCache[key];
}
```

Call `loadOverridesLocal()` at startup and `await loadOverridesFromDb()` inside `loadCards` alongside notes.

- [ ] **Step 3: Apply overrides inside `buildRows`**

After computing auto `held` / `days` for a card with capacity:

```javascript
const ov = getOverride(card.id);
let mode = "auto";
let timeOfDay = "";
let oneOffs = [];
let manualHeld = false;
if (ov) {
  mode = ov.mode === "custom" ? "custom" : "auto";
  manualHeld = Boolean(ov.held);
  if (manualHeld) {
    held = true;
    days = null;
  } else if (mode === "custom") {
    held = false;
    days = Math.max(2, Number(ov.interval_days) || 7);
  }
}
// after sort / colorIndex assignment:
if (ov && !manualHeld && mode === "custom" && ov.start_date) {
  const parts = String(ov.start_date).split("-").map(Number);
  if (parts.length === 3 && parts.every((n) => Number.isFinite(n))) {
    row.startDate = startOfDay(new Date(parts[0], parts[1] - 1, parts[2]));
  }
}
row.mode = mode;
row.timeOfDay = (ov && ov.time) || "";
row.oneOffs = (ov && Array.isArray(ov.one_offs) ? ov.one_offs : []);
row.manualHeld = manualHeld;
row.frequency = held
  ? "HOLD — EXPAND FIRST"
  : mode === "custom"
    ? formatFrequency(days)
    : row.frequency;
```

- [ ] **Step 4: Extend calendar helpers for times and one-offs**

Change `snapshotDatesInRange` usage so card calendars build event objects `{ date, time, kind: "recurring"|"oneoff", label }`.

For auto mode: `{ date, time: "", kind: "recurring" }`.  
For custom: recurring with `row.timeOfDay`; merge one-offs by date (one-off wins tooltip).

Tooltip / title on day cells: include time and label when present. Add class `oneoff` for one-off days.

Overall month view: same event list aggregation.

- [ ] **Step 5: Render edit controls on each card**

In the card HTML builder (where notes textarea is), add:

- Mode buttons Auto | Custom
- Hold checkbox
- When `mode === "custom" && !held`: inputs for interval, start date, time; one-off add form; list with remove
- Badges `CUSTOM` / `HOLD`
- Inline error span for validation

On change:

```javascript
function setMode(cardId, mode) {
  const ov = ensureOverride(cardId);
  ov.mode = mode === "custom" ? "custom" : "auto";
  if (mode === "custom") {
    if (!ov.time) ov.time = "02:00";
    if (!ov.interval_days) ov.interval_days = 7;
    if (!ov.start_date) {
      const d = new Date();
      d.setDate(d.getDate() + 1);
      ov.start_date = dateKey(startOfDay(d));
    }
  }
  persistOverride(cardId);
  render(); // existing full re-render
}
```

Validate time with `/^\d{1,2}:\d{2}$/` and hour/minute bounds before persist; show error and skip save if invalid.

- [ ] **Step 6: Manual UI check**

Run LaunchPad unlocked, open Snapshot Schedule:

1. Switch site to Custom → set weekly + time → calendar updates  
2. Add one-off → distinct marker  
3. Hold → empty calendar  
4. Custom → Auto → Custom restores fields  
5. Reload page → values persist  
6. Export Excel → Mode/Time/Held/One-offs populated  

- [ ] **Step 7: Commit (only if user asked)**

---

### Task 5: Desktop export + version bump

**Files:**
- Modify: `launchpad/ui/dashboard_view.py` `_export_snapshot_schedule_excel` if it constructs workbook without overrides (ensure `export_snapshot_schedule_excel` loads overrides)
- Modify: `launchpad/config.py` — `APP_VERSION = "1.6.18"`
- Modify: `docs/superpowers/specs/2026-07-17-snapshot-schedule-edit-design.md` — set Status to `Implemented` when done (optional)

- [ ] **Step 1: Verify desktop export path**

In `export_snapshot_schedule_excel`, after `notes = server.get_snapshot_notes()`:

```python
overrides = server.get_snapshot_overrides()
wb = build_snapshot_schedule_workbook(
    cards,
    notes,
    threshold=threshold,
    groups=groups,
    overrides=overrides,
)
```

- [ ] **Step 2: Bump version**

```python
APP_VERSION = "1.6.18"
```

- [ ] **Step 3: Full regression commands**

```powershell
python -m pytest tests/test_snapshot_schedule_overrides.py tests/test_snapshot_schedule_export.py -v
python -c "from launchpad.config import APP_VERSION; assert APP_VERSION=='1.6.18'"
```

Expected: PASS.

- [ ] **Step 4: Commit (only if user asked)**

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Auto/Custom mode | 4 |
| Hold both modes | 2, 4 |
| Recurring interval/start/time | 2, 4 |
| One-offs | 2, 4 |
| DB persist + local fallback | 3, 4 |
| Excel columns + effective schedule | 2, 3, 5 |
| Dormant fields on mode switch | 4 (`setMode` only flips `mode`) |
| Planning-only footer | 4 (keep existing footer) |
| Version bump | 5 |

## Placeholder / consistency self-review

- No TBD steps; function names consistent (`get_snapshot_overrides`, `normalize_override`, `OVERRIDES_KEY`).
- Held column / effective hold rules defined in Task 2.
- Commit steps optional per session user rules.
