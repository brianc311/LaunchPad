# ESX-snap Policy and Per-Site Volume Group Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new HealthServer page that creates IBM snapshot policy `ESX-snap` (daily, keep 7 days) and a per-site volume group with operator-picked volumes, for one or many FlashSystem/SVC arrays, shipping as **1.6.174**.

**Architecture:** Pure ops in `launchpad/esx_snap_policy_ops.py` parse inventory, sanitize names, and build Preview/Run steps. `launchpad/esx_snap_policy.py` is the page. `health_server.py` routes SSH I/O only. Dashboard opens the page with `_open_sync_browser_report` so the Tk thread never decrypts the fleet.

**Tech Stack:** Python, HealthServer HTML/JS, existing `run_remote_ssh_command` / `run_snap_steps` / `cli_token` / `SnapStep`, pytest.

**Spec:** `docs/superpowers/specs/2026-08-15-esx-snap-policy-vg-design.md`

## Global Constraints

- APP_VERSION bump to **1.6.174** only in the final version task. Do not bump in Tasks 1–4.
- Policy name is exactly `ESX-snap` (not editable). Daily, interval 1, retention 7 days. Start time default `02:00`.
- Volume group default `{sanitized card name}_ESX-snap`, editable per array, max 63 characters, keep `_ESX-snap` suffix when truncating.
- If `ESX-snap` or the chosen VG already exists, that array errors (do not skip, reuse, or attach). Other arrays still run.
- Add-volume command is always `svctask addvolumetovolumegroup` (not `chvdisk -volumegroup`).
- IBM `SVC_PROFILES` only. No HPE/Dell/NetApp. Snapshot Schedule stays planning-only except a cross-link.
- No safeguarded snapshots, no `mksnapshot`, no delete/update of existing policy/VG, no DB persistence of volume picks, no automatic rollback.
- `backupstarttime` uses LaunchPad PC local `datetime.now()` date plus the start-time field (`YYMMDDHHMM`). Do not read the array clock.
- Mutating SSH and fleet decrypt never run on the Tk UI thread. Header opener uses `_open_sync_browser_report`.
- Do not put CLI assembly in `health_server.py` beyond routing and SSH I/O.
- Place imports at the top of modules (no inline imports).
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch, `LaunchPad-Install/`, or install zips.
- Work from a feature branch off current `main` (do not land unfinished work on `main` mid-plan). Create an isolated worktree via using-git-worktrees at execution time. Branch name: `feature/esx-snap-policy-vg`.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/esx_snap_policy_ops.py` | Names, parsers, inventory collect, preview steps, hash, existence |
| `tests/test_esx_snap_policy_ops.py` | Unit tests for ops |
| `launchpad/health_server.py` | GET/POST routes, SSH I/O, `open_esx_snap_policy`, Health nav link |
| `tests/test_health_server_esx_snap_policy.py` | API tests with fake SSH |
| `launchpad/esx_snap_policy.py` | Page HTML/JS |
| `tests/test_esx_snap_policy_page.py` | Page contract tests |
| `launchpad/ui/dashboard_view.py` | Header button + opener |
| `tests/test_dashboard_ui_freeze.py` | Add `_open_esx_snap_policy` to `HEADER_OPENERS` |
| `launchpad/snapshot_schedule.py` | Cross-link to `/esx-snap-policy` |
| `launchpad/config.py` + version pins | `1.6.174` (Task 5 only) |

---

### Task 1: Ops — names, inventory parse, preview steps

**Files:**
- Create: `launchpad/esx_snap_policy_ops.py`
- Create: `tests/test_esx_snap_policy_ops.py`

**Interfaces:**
- Consumes: `cli_token`, `SnapStep` from `launchpad.contingency_snap_create`; `_get`, `_table_records` from `launchpad.flashsystem_fc`
- Produces:
  - `POLICY_NAME: str` = `"ESX-snap"`
  - `VG_SUFFIX: str` = `"_ESX-snap"`
  - `VG_MAX_LEN: int` = `63`
  - `FIRMWARE_MSG: str` = `"Snapshot policies need IBM Storage Virtualize 8.5.1 or later"`
  - `sanitize_site_token(card_name: str) -> str`
  - `default_vg_name(card_name: str) -> str`
  - `parse_hhmm(start_time: str) -> tuple[int, int] | None`
  - `backup_start_token(start_time: str, *, now: datetime | None = None) -> str`
  - `parse_named_objects(output: str) -> set[str]`
  - `parse_lsvdisk_membership(output: str) -> list[dict[str, str]]` with keys `name`, `capacity`, `volume_group`
  - `volume_group_of(volume: dict) -> str`
  - `preview_hash(start_time: str, arrays: list[dict]) -> str`
  - `collect_esx_snap_inventory(run_cmd: Callable[[str], str]) -> dict` with keys `ok`, `error`, `policies` (`set[str]`), `volume_groups` (`set[str]`), `volumes` (`list[dict]`)
  - `build_esx_snap_array_steps(*, vg_name: str, volume_names: list[str], start_time: str, policies: set[str], volume_groups: set[str], volumes: list[dict], now: datetime | None = None) -> tuple[list[SnapStep], list[str], bool]`
  - `steps_payload(steps: list[SnapStep]) -> list[dict]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_esx_snap_policy_ops.py`:

```python
from datetime import datetime

from launchpad.esx_snap_policy_ops import (
    POLICY_NAME,
    backup_start_token,
    build_esx_snap_array_steps,
    collect_esx_snap_inventory,
    default_vg_name,
    parse_lsvdisk_membership,
    parse_named_objects,
    preview_hash,
    sanitize_site_token,
)


POLICY_SAMPLE = """id:name:backup_unit:backup_interval:retention_days
0:other-policy:day:1:7
"""

VG_SAMPLE = """id:name:snapshot_policy_name
0:Other_VG:other-policy
"""

VDISK_SAMPLE = """id:name:capacity:volume_group
0:WIN_ESX_DS01:1.00TB:
1:WIN_ESX_DS02:2.00TB:Already_VG
2:WIN_NFS:500.00GB:
"""


def test_sanitize_and_default_vg_name():
    assert sanitize_site_token("Windsor FS9200") == "Windsor_FS9200"
    assert default_vg_name("Windsor") == "Windsor_ESX-snap"
    assert default_vg_name("  ") == "Site_ESX-snap"
    assert default_vg_name("Windsor FS9200") == "Windsor_FS9200_ESX-snap"
    long_name = "A" * 80
    vg = default_vg_name(long_name)
    assert len(vg) <= 63
    assert vg.endswith("_ESX-snap")


def test_backup_start_token_uses_local_date_and_hhmm():
    now = datetime(2026, 8, 15, 18, 0, 0)
    assert backup_start_token("02:00", now=now) == "2608150200"
    assert backup_start_token("2:00", now=now) == "2608150200"


def test_parse_named_objects_and_volume_membership():
    assert parse_named_objects(POLICY_SAMPLE) == {"other-policy"}
    vols = parse_lsvdisk_membership(VDISK_SAMPLE)
    by_name = {row["name"]: row for row in vols}
    assert by_name["WIN_ESX_DS01"]["volume_group"] == ""
    assert by_name["WIN_ESX_DS02"]["volume_group"] == "Already_VG"
    assert by_name["WIN_ESX_DS01"]["capacity"] == "1.00TB"


def test_steps_daily_seven_day_policy_and_add_volume():
    now = datetime(2026, 8, 15, 9, 0, 0)
    volumes = parse_lsvdisk_membership(VDISK_SAMPLE)
    steps, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_ESX-snap",
        volume_names=["WIN_ESX_DS01", "WIN_NFS"],
        start_time="02:00",
        policies=set(),
        volume_groups=set(),
        volumes=volumes,
        now=now,
    )
    assert runnable is True
    assert warnings == []
    cmds = [step.cmd for step in steps]
    assert cmds[0] == (
        "svctask mksnapshotpolicy -backupunit day -backupinterval 1 "
        "-backupstarttime 2608150200 -retentiondays 7 -name ESX-snap"
    )
    assert cmds[1] == (
        "svctask mkvolumegroup -snapshotpolicy ESX-snap -name Windsor_ESX-snap"
    )
    assert cmds[2] == (
        "svctask addvolumetovolumegroup -volumegroup Windsor_ESX-snap WIN_ESX_DS01"
    )
    assert cmds[3] == (
        "svctask addvolumetovolumegroup -volumegroup Windsor_ESX-snap WIN_NFS"
    )
    assert POLICY_NAME == "ESX-snap"


def test_existence_and_membership_block_array():
    volumes = parse_lsvdisk_membership(VDISK_SAMPLE)
    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_ESX-snap",
        volume_names=["WIN_ESX_DS01"],
        start_time="02:00",
        policies={"ESX-snap"},
        volume_groups=set(),
        volumes=volumes,
    )
    assert runnable is False
    assert any("ESX-snap" in w for w in warnings)

    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_ESX-snap",
        volume_names=["WIN_ESX_DS01"],
        start_time="02:00",
        policies=set(),
        volume_groups={"Windsor_ESX-snap"},
        volumes=volumes,
    )
    assert runnable is False
    assert any("Windsor_ESX-snap" in w for w in warnings)

    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_ESX-snap",
        volume_names=["WIN_ESX_DS02"],
        start_time="02:00",
        policies=set(),
        volume_groups=set(),
        volumes=volumes,
    )
    assert runnable is False
    assert any("volume group" in w.lower() or "Already_VG" in w for w in warnings)

    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_ESX-snap",
        volume_names=[],
        start_time="02:00",
        policies=set(),
        volume_groups=set(),
        volumes=volumes,
    )
    assert runnable is False


def test_preview_hash_stable_and_order_independent():
    a = preview_hash(
        "02:00",
        [
            {"card_id": 2, "vg_name": "B_ESX-snap", "volume_names": ["v2", "v1"]},
            {"card_id": 1, "vg_name": "A_ESX-snap", "volume_names": ["v0"]},
        ],
    )
    b = preview_hash(
        "02:00",
        [
            {"card_id": 1, "vg_name": "A_ESX-snap", "volume_names": ["v0"]},
            {"card_id": 2, "vg_name": "B_ESX-snap", "volume_names": ["v1", "v2"]},
        ],
    )
    assert a == b
    c = preview_hash(
        "03:00",
        [
            {"card_id": 1, "vg_name": "A_ESX-snap", "volume_names": ["v0"]},
            {"card_id": 2, "vg_name": "B_ESX-snap", "volume_names": ["v1", "v2"]},
        ],
    )
    assert a != c


def test_collect_inventory_parses_and_flags_missing_policy_cli():
    calls: list[str] = []

    def run_cmd(command: str) -> str:
        calls.append(command)
        if "lssnapshotpolicy" in command:
            return POLICY_SAMPLE
        if "lsvolumegroup" in command:
            return VG_SAMPLE
        if "lsvdisk" in command:
            return VDISK_SAMPLE
        raise AssertionError(command)

    result = collect_esx_snap_inventory(run_cmd)
    assert result["ok"] is True
    assert "other-policy" in result["policies"]
    assert "Other_VG" in result["volume_groups"]
    assert {row["name"] for row in result["volumes"]} == {
        "WIN_ESX_DS01",
        "WIN_ESX_DS02",
        "WIN_NFS",
    }

    def reject(command: str) -> str:
        if "lssnapshotpolicy" in command:
            raise RuntimeError("not a valid command")
        return ""

    bad = collect_esx_snap_inventory(reject)
    assert bad["ok"] is False
    assert "8.5.1" in bad["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_esx_snap_policy_ops.py -v`

Expected: FAIL (`ModuleNotFoundError: launchpad.esx_snap_policy_ops`)

- [ ] **Step 3: Write minimal implementation**

Create `launchpad/esx_snap_policy_ops.py`:

```python
"""IBM ESX-snap snapshot policy + volume group preview/run helpers."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime

from launchpad.contingency_snap_create import SnapStep, cli_token
from launchpad.flashsystem_fc import _get, _table_records

POLICY_NAME = "ESX-snap"
VG_SUFFIX = "_ESX-snap"
VG_MAX_LEN = 63
FIRMWARE_MSG = "Snapshot policies need IBM Storage Virtualize 8.5.1 or later"

_UNSAFE = re.compile(r"[^A-Za-z0-9_]+")
_HHMM = re.compile(r"^(\d{1,2}):(\d{2})$")


def sanitize_site_token(card_name: str) -> str:
    text = _UNSAFE.sub("_", str(card_name or "").strip())
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "Site"


def default_vg_name(card_name: str) -> str:
    site = sanitize_site_token(card_name)
    max_site = VG_MAX_LEN - len(VG_SUFFIX)
    if len(site) > max_site:
        site = site[:max_site].rstrip("_") or "Site"
        if len(site) > max_site:
            site = site[:max_site]
    return f"{site}{VG_SUFFIX}"


def parse_hhmm(start_time: str) -> tuple[int, int] | None:
    match = _HHMM.fullmatch(str(start_time or "").strip())
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def backup_start_token(start_time: str, *, now: datetime | None = None) -> str:
    parsed = parse_hhmm(start_time)
    if parsed is None:
        raise ValueError("start_time must be HH:MM")
    hour, minute = parsed
    stamp = now or datetime.now()
    return f"{stamp.year % 100:02d}{stamp.month:02d}{stamp.day:02d}{hour:02d}{minute:02d}"


def parse_named_objects(output: str) -> set[str]:
    names: set[str] = set()
    for record in _table_records(output):
        name = _get(record, "name")
        if name:
            names.add(name)
    return names


def parse_lsvdisk_membership(output: str) -> list[dict[str, str]]:
    volumes: list[dict[str, str]] = []
    for record in _table_records(output):
        name = _get(record, "name", "vdisk_name", "volume_name")
        if not name:
            continue
        volumes.append(
            {
                "name": name,
                "capacity": _get(record, "capacity"),
                "volume_group": _get(
                    record, "volume_group", "volume_group_name", "volumegroup"
                ),
            }
        )
    return volumes


def volume_group_of(volume: dict) -> str:
    return str(volume.get("volume_group") or "").strip()


def _canonical_preview_payload(start_time: str, arrays: list[dict]) -> dict:
    canon = []
    for item in arrays:
        names = [str(name) for name in (item.get("volume_names") or [])]
        canon.append(
            {
                "card_id": int(item["card_id"]),
                "vg_name": str(item.get("vg_name") or ""),
                "volume_names": sorted(names),
            }
        )
    canon.sort(key=lambda row: row["card_id"])
    return {"start_time": str(start_time or "").strip(), "arrays": canon}


def preview_hash(start_time: str, arrays: list[dict]) -> str:
    blob = json.dumps(
        _canonical_preview_payload(start_time, arrays),
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def steps_payload(steps: list[SnapStep]) -> list[dict]:
    return [
        {
            "kind": step.kind,
            "purpose": step.purpose,
            "cmd": step.cmd,
            "skip": step.skip,
            "reason": step.reason,
        }
        for step in steps
    ]


def collect_esx_snap_inventory(run_cmd: Callable[[str], str]) -> dict:
    try:
        policy_out = run_cmd("svcinfo lssnapshotpolicy -delim :")
        if not str(policy_out or "").strip():
            policy_out = run_cmd("svcinfo lssnapshotpolicy")
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{FIRMWARE_MSG} ({exc})",
            "policies": set(),
            "volume_groups": set(),
            "volumes": [],
        }
    text = str(policy_out or "").lower()
    if "not a valid command" in text:
        return {
            "ok": False,
            "error": FIRMWARE_MSG,
            "policies": set(),
            "volume_groups": set(),
            "volumes": [],
        }
    vg_out = run_cmd("svcinfo lsvolumegroup -delim :")
    if not str(vg_out or "").strip():
        vg_out = run_cmd("svcinfo lsvolumegroup")
    vols_out = run_cmd("svcinfo lsvdisk -delim :")
    if not str(vols_out or "").strip():
        vols_out = run_cmd("svcinfo lsvdisk")
    return {
        "ok": True,
        "error": "",
        "policies": parse_named_objects(policy_out),
        "volume_groups": parse_named_objects(vg_out),
        "volumes": parse_lsvdisk_membership(vols_out),
    }


def build_esx_snap_array_steps(
    *,
    vg_name: str,
    volume_names: list[str],
    start_time: str,
    policies: set[str],
    volume_groups: set[str],
    volumes: list[dict],
    now: datetime | None = None,
) -> tuple[list[SnapStep], list[str], bool]:
    warnings: list[str] = []
    steps: list[SnapStep] = []
    try:
        policy = cli_token(POLICY_NAME)
        vg = cli_token(str(vg_name or "").strip())
    except ValueError as exc:
        warnings.append(f"ERROR: {exc}")
        return steps, warnings, False
    try:
        start = backup_start_token(start_time, now=now)
    except ValueError as exc:
        warnings.append(f"ERROR: {exc}")
        return steps, warnings, False
    if POLICY_NAME in policies:
        warnings.append(f"ERROR: snapshot policy {POLICY_NAME} already exists")
    if vg in volume_groups:
        warnings.append(f"ERROR: volume group {vg} already exists")
    chosen = [str(name).strip() for name in volume_names if str(name).strip()]
    if not chosen:
        warnings.append("ERROR: select at least one volume")
    by_name = {str(row.get("name") or ""): row for row in volumes}
    safe_vols: list[str] = []
    for name in chosen:
        try:
            token = cli_token(name)
        except ValueError as exc:
            warnings.append(f"ERROR: {exc}")
            continue
        live = by_name.get(name)
        if live is None:
            warnings.append(f"ERROR: volume {name} not found on array")
            continue
        existing = volume_group_of(live)
        if existing:
            warnings.append(
                f"ERROR: volume {name} already belongs to volume group {existing}"
            )
            continue
        safe_vols.append(token)
    if any(item.startswith("ERROR:") for item in warnings):
        return steps, warnings, False
    steps.append(
        SnapStep(
            kind="mksnapshotpolicy",
            purpose="create ESX-snap policy (daily, retain 7 days)",
            cmd=(
                "svctask mksnapshotpolicy -backupunit day -backupinterval 1 "
                f"-backupstarttime {start} -retentiondays 7 -name {policy}"
            ),
        )
    )
    steps.append(
        SnapStep(
            kind="mkvolumegroup",
            purpose="create volume group with ESX-snap policy",
            cmd=f"svctask mkvolumegroup -snapshotpolicy {policy} -name {vg}",
        )
    )
    for token in safe_vols:
        steps.append(
            SnapStep(
                kind="addvolumetovolumegroup",
                purpose=f"add volume {token}",
                cmd=f"svctask addvolumetovolumegroup -volumegroup {vg} {token}",
            )
        )
    return steps, warnings, True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_esx_snap_policy_ops.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add -- launchpad/esx_snap_policy_ops.py tests/test_esx_snap_policy_ops.py
git commit -m "Add ESX-snap policy ops for names, inventory, and preview steps."
```

---

### Task 2: HealthServer APIs — cards, volumes, preview, run

**Files:**
- Modify: `launchpad/health_server.py`
- Create: `tests/test_health_server_esx_snap_policy.py`

**Interfaces:**
- Consumes: Task 1 ops; `SVC_PROFILES`; `_snap_run_command`; `run_snap_steps`; `HealthCard`
- Produces:
  - `HealthServer.esx_snap_policy_cards(self) -> list[dict]`
  - `HealthServer.esx_snap_policy_volumes(self, card_id: int) -> dict`
  - `HealthServer.preview_esx_snap_policy(self, payload: dict) -> dict`
  - `HealthServer.run_esx_snap_policy(self, payload: dict, *, confirm: bool) -> dict`
  - GET `/api/esx-snap-policy/cards`
  - POST `/api/esx-snap-policy/volumes`
  - POST `/api/esx-snap-policy/preview`
  - POST `/api/esx-snap-policy/run`
  - Card dict: `{ id, name, host, device_profile, default_vg_name }`
  - Volumes dict: `{ ok, volumes, policies, volume_groups, error }`
  - Preview dict: `{ ok, arrays: [{ card_id, name, vg_name, runnable, warnings, steps }], preview_hash }`
  - Run dict: `{ ok, arrays: [{ card_id, name, ok, warnings, log }] }`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_health_server_esx_snap_policy.py`:

```python
from launchpad.health_server import HealthServer
from launchpad.esx_snap_policy_ops import preview_hash

POLICY_SAMPLE = """id:name
0:keep-me
"""
VG_SAMPLE = """id:name
0:Other_VG
"""
VDISK_SAMPLE = """id:name:capacity:volume_group
0:VOL_A:1.00TB:
1:VOL_B:2.00TB:
"""
EXISTING_POLICY = """id:name
0:ESX-snap
"""


def _server_two_cards() -> HealthServer:
    server = HealthServer()
    server.register_card(
        card_id=1,
        name="Windsor",
        host="win.example",
        port=22,
        username="admin",
        key_path="/dev/null",
        device_profile="flashsystem_9200",
    )
    server.register_card(
        card_id=2,
        name="Hartford",
        host="hart.example",
        port=22,
        username="admin",
        key_path="/dev/null",
        device_profile="flashsystem_9200",
    )
    server.register_card(
        card_id=3,
        name="HPE box",
        host="hpe.example",
        port=22,
        username="3paradm",
        key_path="/dev/null",
        device_profile="hpe_3par_8450",
    )
    return server


def test_cards_are_ibm_only_with_default_vg():
    server = _server_two_cards()
    cards = server.esx_snap_policy_cards()
    names = {row["name"] for row in cards}
    assert names == {"Windsor", "Hartford"}
    windsor = next(row for row in cards if row["name"] == "Windsor")
    assert windsor["default_vg_name"] == "Windsor_ESX-snap"


def test_run_without_confirm_or_bad_hash_does_not_mutate(monkeypatch):
    server = _server_two_cards()
    calls: list[str] = []

    def bind_host(card, **kwargs):
        def run_cmd(command: str) -> str:
            calls.append(command)
            return ""
        return run_cmd

    monkeypatch.setattr(HealthServer, "_snap_run_command", staticmethod(bind_host))
    payload = {
        "start_time": "02:00",
        "arrays": [
            {"card_id": 2, "vg_name": "Hartford_ESX-snap", "volume_names": ["VOL_A"]},
        ],
        "preview_hash": "deadbeef",
    }
    denied = server.run_esx_snap_policy(payload, confirm=False)
    assert denied["ok"] is False
    assert calls == []
    denied_hash = server.run_esx_snap_policy(payload, confirm=True)
    assert denied_hash["ok"] is False
    assert calls == []
```

Preview/run must call `self._esx_snap_inventory(card)` so tests patch that method. Add:

```python
def test_preview_many_one_blocked_still_ok(monkeypatch):
    server = _server_two_cards()
    from launchpad.esx_snap_policy_ops import (
        parse_lsvdisk_membership,
        parse_named_objects,
    )

    def inventory(self, card):
        if card.card_id == 1:
            return {
                "ok": True,
                "error": "",
                "policies": parse_named_objects(EXISTING_POLICY),
                "volume_groups": set(),
                "volumes": parse_lsvdisk_membership(VDISK_SAMPLE),
            }
        return {
            "ok": True,
            "error": "",
            "policies": parse_named_objects(POLICY_SAMPLE),
            "volume_groups": parse_named_objects(VG_SAMPLE),
            "volumes": parse_lsvdisk_membership(VDISK_SAMPLE),
        }

    monkeypatch.setattr(HealthServer, "_esx_snap_inventory", inventory)
    payload = {
        "start_time": "02:00",
        "arrays": [
            {"card_id": 1, "vg_name": "Windsor_ESX-snap", "volume_names": ["VOL_A"]},
            {"card_id": 2, "vg_name": "Hartford_ESX-snap", "volume_names": ["VOL_B"]},
        ],
    }
    result = server.preview_esx_snap_policy(payload)
    assert result["ok"] is True
    by_id = {row["card_id"]: row for row in result["arrays"]}
    assert by_id[1]["runnable"] is False
    assert by_id[2]["runnable"] is True
```

Also add:

```python
def test_run_recheck_skips_mutate_when_policy_appears(monkeypatch):
    server = _server_two_cards()
    from launchpad.esx_snap_policy_ops import (
        parse_lsvdisk_membership,
        parse_named_objects,
    )
    mutate_cmds: list[str] = []

    def inventory(self, card):
        return {
            "ok": True,
            "error": "",
            "policies": {"ESX-snap"},
            "volume_groups": set(),
            "volumes": parse_lsvdisk_membership(VDISK_SAMPLE),
        }

    def bind_host(card, **kwargs):
        def run_cmd(command: str) -> str:
            mutate_cmds.append(command)
            return "ok"
        return run_cmd

    monkeypatch.setattr(HealthServer, "_esx_snap_inventory", inventory)
    monkeypatch.setattr(HealthServer, "_snap_run_command", staticmethod(bind_host))
    arrays = [
        {"card_id": 2, "vg_name": "Hartford_ESX-snap", "volume_names": ["VOL_A"]},
    ]
    payload = {
        "start_time": "02:00",
        "arrays": arrays,
        "preview_hash": preview_hash("02:00", arrays),
    }
    result = server.run_esx_snap_policy(payload, confirm=True)
    assert result["ok"] is False
    assert mutate_cmds == []
    assert any(not row["ok"] for row in result["arrays"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_health_server_esx_snap_policy.py -v`

Expected: FAIL (`esx_snap_policy_cards` not defined)

- [ ] **Step 3: Write minimal implementation**

At the top of `launchpad/health_server.py` add only the ops import (do not import the page module yet; `SVC_PROFILES` is already imported from `launchpad.storage_presets`):

```python
from launchpad.esx_snap_policy_ops import (
    POLICY_NAME,
    build_esx_snap_array_steps,
    collect_esx_snap_inventory,
    default_vg_name,
    preview_hash,
    steps_payload,
)
```

Add methods on `HealthServer` next to `fc_consistgrp_cards` / `preview_fc_consistgrp`:

```python
    def _esx_snap_card_by_id(self, card_id: int) -> HealthCard | None:
        with self._lock:
            return self._cards.get(card_id)

    def _esx_snap_eligible(self, card: HealthCard) -> bool:
        return (
            str(card.device_profile or "") in SVC_PROFILES
            and str(card.host or "").strip() != ""
        )

    def esx_snap_policy_cards(self) -> list[dict[str, Any]]:
        with self._lock:
            stored = list(sorted(self._cards.values(), key=lambda card: card.card_id))
        return [
            {
                "id": card.card_id,
                "name": card.name,
                "host": card.host,
                "device_profile": card.device_profile or "",
                "default_vg_name": default_vg_name(card.name),
            }
            for card in stored
            if self._esx_snap_eligible(card)
        ]

    def _esx_snap_inventory(self, card: HealthCard) -> dict[str, Any]:
        return collect_esx_snap_inventory(self._snap_run_command(card))

    def esx_snap_policy_volumes(self, card_id: int) -> dict[str, Any]:
        card = self._esx_snap_card_by_id(card_id)
        if card is None or not self._esx_snap_eligible(card):
            return {
                "ok": False,
                "error": f"Unknown or ineligible Health Card id {card_id}",
                "volumes": [],
                "policies": [],
                "volume_groups": [],
            }
        inventory = self._esx_snap_inventory(card)
        if not inventory.get("ok"):
            return {
                "ok": False,
                "error": inventory.get("error") or "Unable to collect inventory",
                "volumes": [],
                "policies": [],
                "volume_groups": [],
            }
        return {
            "ok": True,
            "error": "",
            "volumes": inventory["volumes"],
            "policies": sorted(inventory["policies"]),
            "volume_groups": sorted(inventory["volume_groups"]),
        }

    def preview_esx_snap_policy(self, payload: dict) -> dict[str, Any]:
        start_time = str(payload.get("start_time") or "02:00")
        raw_arrays = payload.get("arrays") or []
        if not isinstance(raw_arrays, list) or not raw_arrays:
            return {
                "ok": False,
                "arrays": [],
                "preview_hash": "",
                "warnings": ["ERROR: select at least one array"],
            }
        arrays_out: list[dict[str, Any]] = []
        for item in raw_arrays:
            if not isinstance(item, dict):
                continue
            try:
                card_id = int(item.get("card_id"))
            except (TypeError, ValueError):
                arrays_out.append(
                    {
                        "card_id": item.get("card_id"),
                        "name": "",
                        "vg_name": str(item.get("vg_name") or ""),
                        "runnable": False,
                        "warnings": ["ERROR: card_id is required"],
                        "steps": [],
                    }
                )
                continue
            card = self._esx_snap_card_by_id(card_id)
            vg_name = str(item.get("vg_name") or "") or (
                default_vg_name(card.name) if card is not None else ""
            )
            volume_names = [
                str(name) for name in (item.get("volume_names") or []) if str(name).strip()
            ]
            if card is None or not self._esx_snap_eligible(card):
                arrays_out.append(
                    {
                        "card_id": card_id,
                        "name": "",
                        "vg_name": vg_name,
                        "runnable": False,
                        "warnings": [f"ERROR: Unknown or ineligible Health Card id {card_id}"],
                        "steps": [],
                    }
                )
                continue
            inventory = self._esx_snap_inventory(card)
            if not inventory.get("ok"):
                arrays_out.append(
                    {
                        "card_id": card_id,
                        "name": card.name,
                        "vg_name": vg_name,
                        "runnable": False,
                        "warnings": [f"ERROR: {inventory.get('error') or 'inventory failed'}"],
                        "steps": [],
                    }
                )
                continue
            steps, warnings, runnable = build_esx_snap_array_steps(
                vg_name=vg_name,
                volume_names=volume_names,
                start_time=start_time,
                policies=set(inventory["policies"]),
                volume_groups=set(inventory["volume_groups"]),
                volumes=list(inventory["volumes"]),
            )
            arrays_out.append(
                {
                    "card_id": card_id,
                    "name": card.name,
                    "vg_name": vg_name,
                    "runnable": runnable,
                    "warnings": warnings,
                    "steps": steps_payload(steps),
                }
            )
        ok = any(row.get("runnable") for row in arrays_out)
        return {
            "ok": ok,
            "arrays": arrays_out,
            "preview_hash": preview_hash(start_time, list(raw_arrays)),
        }

    def run_esx_snap_policy(self, payload: dict, *, confirm: bool) -> dict[str, Any]:
        if confirm is not True:
            return {
                "ok": False,
                "arrays": [],
                "warnings": ["confirm must be true before creating policy or volume group"],
            }
        start_time = str(payload.get("start_time") or "02:00")
        raw_arrays = payload.get("arrays") or []
        expected = preview_hash(start_time, list(raw_arrays) if isinstance(raw_arrays, list) else [])
        given = str(payload.get("preview_hash") or "")
        if not given or given != expected:
            return {
                "ok": False,
                "arrays": [],
                "warnings": ["Preview must be run again before creating policy or volume group."],
            }
        preview = self.preview_esx_snap_policy(payload)
        results: list[dict[str, Any]] = []
        for row in preview.get("arrays") or []:
            if not row.get("runnable"):
                results.append(
                    {
                        "card_id": row.get("card_id"),
                        "name": row.get("name") or "",
                        "ok": False,
                        "warnings": row.get("warnings") or [],
                        "log": [],
                    }
                )
                continue
            card_id = int(row["card_id"])
            card = self._esx_snap_card_by_id(card_id)
            live = self._esx_snap_inventory(card)
            vg_name = str(row.get("vg_name") or "")
            if not live.get("ok"):
                results.append(
                    {
                        "card_id": card_id,
                        "name": card.name if card else "",
                        "ok": False,
                        "warnings": [f"ERROR: {live.get('error')}"],
                        "log": [],
                    }
                )
                continue
            if POLICY_NAME in set(live["policies"]) or vg_name in set(live["volume_groups"]):
                results.append(
                    {
                        "card_id": card_id,
                        "name": card.name if card else "",
                        "ok": False,
                        "warnings": [
                            f"ERROR: {POLICY_NAME} or {vg_name} already exists; "
                            "no commands were run. If a previous Run created the policy, "
                            "delete ESX-snap on the array before retrying."
                        ],
                        "log": [],
                    }
                )
                continue
            steps = [
                SnapStep(
                    kind=step["kind"],
                    purpose=step["purpose"],
                    cmd=step["cmd"],
                    skip=step.get("skip") or False,
                    reason=step.get("reason") or "",
                )
                for step in row.get("steps") or []
            ]
            executed = run_snap_steps(steps, self._snap_run_command(card))
            if not executed.get("ok"):
                executed.setdefault("warnings", [])
                executed["warnings"].append(
                    "No automatic rollback. If ESX-snap was created, delete it on the array before retrying."
                )
            results.append(
                {
                    "card_id": card_id,
                    "name": card.name if card else "",
                    "ok": bool(executed.get("ok")),
                    "warnings": executed.get("warnings") or [],
                    "log": executed.get("log") or [],
                }
            )
        overall_ok = any(row.get("ok") for row in results)
        return {"ok": overall_ok, "arrays": results}
```

`ok` is `True` when at least one array completed mutate steps successfully. Existence-blocked arrays are `ok: False` with empty `log`. If every array failed or was blocked, `ok` is `False`. Use the existing top-of-file `SnapStep` and `run_snap_steps` imports.

In `HealthHandler.do_GET`, next to `/api/fc-consistgrp/cards`:

```python
        if path == "/api/esx-snap-policy/cards":
            self._send_json({"cards": server.esx_snap_policy_cards()})
            return
```

In `HealthHandler.do_POST`, next to fc-consistgrp preview/run:

```python
        if path in {
            "/api/esx-snap-policy/volumes",
            "/api/esx-snap-policy/preview",
            "/api/esx-snap-policy/run",
        }:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json({"ok": False, "error": "Invalid JSON"}, status=400)
                return
            if not isinstance(payload, dict):
                self._send_json({"ok": False, "error": "JSON object required"}, status=400)
                return
            if path == "/api/esx-snap-policy/volumes":
                try:
                    card_id = int(payload.get("card_id"))
                except (TypeError, ValueError):
                    self._send_json(
                        {"ok": False, "error": "card_id is required"},
                        status=400,
                    )
                    return
                result = server.esx_snap_policy_volumes(card_id)
                self._send_json(result, status=200 if result.get("ok") else 400)
                return
            if path == "/api/esx-snap-policy/preview":
                result = server.preview_esx_snap_policy(payload)
                self._send_json(result, status=200 if result.get("ok") else 400)
                return
            result = server.run_esx_snap_policy(
                payload, confirm=payload.get("confirm") is True
            )
            self._send_json(result, status=200 if result.get("ok") else 400)
            return
```

Do not SSH in `esx_snap_policy_cards`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_health_server_esx_snap_policy.py tests/test_esx_snap_policy_ops.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add -- launchpad/health_server.py tests/test_health_server_esx_snap_policy.py
git commit -m "Add ESX-snap policy HealthServer preview and run APIs."
```

---

### Task 3: ESX-snap Policy page

**Files:**
- Create: `launchpad/esx_snap_policy.py`
- Create: `tests/test_esx_snap_policy_page.py`

**Interfaces:**
- Consumes: APIs from Task 2 (`/api/esx-snap-policy/cards|volumes|preview|run`)
- Produces: `ESX_SNAP_POLICY_PATH = "/esx-snap-policy"`; `ESX_SNAP_POLICY_HTML` string

- [ ] **Step 1: Write the failing tests**

Create `tests/test_esx_snap_policy_page.py`:

```python
from launchpad.esx_snap_policy import ESX_SNAP_POLICY_HTML, ESX_SNAP_POLICY_PATH


def test_path_and_title():
    assert ESX_SNAP_POLICY_PATH == "/esx-snap-policy"
    assert "ESX-snap Policy" in ESX_SNAP_POLICY_HTML


def test_preview_run_and_api_paths():
    html = ESX_SNAP_POLICY_HTML
    assert "Preview / Dry-run" in html
    assert "Run Create" in html
    assert "/api/esx-snap-policy/cards" in html
    assert "/api/esx-snap-policy/volumes" in html
    assert "/api/esx-snap-policy/preview" in html
    assert "/api/esx-snap-policy/run" in html
    assert 'id="run-btn"' in html
    assert "disabled" in html


def test_policy_copy_and_volume_picker():
    html = ESX_SNAP_POLICY_HTML
    assert "ESX-snap" in html
    assert "02:00" in html
    assert "Select all" in html
    assert "Select none" in html
    assert "Load volumes" in html
    assert "operator-initiated" in html.lower() or "does not create snapshots immediately" in html.lower()


def test_invalidate_preview_and_confirm():
    html = ESX_SNAP_POLICY_HTML
    assert "invalidatePreview" in html
    assert "confirm" in html
    assert "preview_hash" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_esx_snap_policy_page.py -v`

Expected: FAIL (`ModuleNotFoundError: launchpad.esx_snap_policy`)

- [ ] **Step 3: Write the page**

Create `launchpad/esx_snap_policy.py`:

```python
"""ESX-snap snapshot policy and per-site volume group page."""

ESX_SNAP_POLICY_PATH = "/esx-snap-policy"

ESX_SNAP_POLICY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad ESX-snap Policy</title>
  <style>
    :root { --bg:#0b0f14; --panel:#121821; --text:#e8edf5; --muted:#8b98ab; --accent:#ff6b00; --accent2:#ff8533; --ok:#4ade80; --border:#2a3444; --card:#151c27; --danger:#f87171; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; color:var(--text); font-family:Segoe UI,Inter,Arial,sans-serif; background:radial-gradient(circle at top,#172033 0%,var(--bg) 45%); }
    .wrap { max-width:1280px; margin:0 auto; padding:28px 20px 48px; }
    .hero, .section { background:var(--card); border:1px solid var(--border); border-radius:16px; padding:20px; margin-bottom:18px; }
    .hero { background:linear-gradient(135deg,#1a2230 0%,#101722 100%); }
    h1 { margin:0 0 8px; color:var(--accent); font-size:1.85rem; }
    h2 { margin:0 0 10px; color:var(--accent2); font-size:1.05rem; }
    p, .lede, .hint, .footer { color:var(--muted); line-height:1.45; }
    a:not(.btn) { color:#9ec1ff; text-decoration:underline; text-underline-offset:2px; }
    a:not(.btn):hover { color:#c5d9ff; }
    .actions { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:14px; }
    button, .btn { min-height:34px; padding:0 14px; border:0; border-radius:10px; background:var(--accent); color:#111; font:inherit; font-weight:600; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; justify-content:center; }
    button.secondary, .btn.secondary { color:var(--text); background:#0f141d; border:1px solid var(--border); }
    button.danger { color:#fff; background:#b91c1c; }
    button:disabled { cursor:not-allowed; opacity:.6; }
    input { color:var(--text); background:#0f141d; border:1px solid var(--border); border-radius:8px; padding:6px 9px; font:inherit; }
    label { color:var(--muted); font-size:.85rem; font-weight:600; }
    .array { border:1px solid var(--border); border-radius:12px; padding:12px; margin-top:10px; background:#0f141d; }
    .array-head { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
    table { width:100%; border-collapse:collapse; margin-top:8px; }
    th, td { padding:6px; text-align:left; border:1px solid var(--border); }
    th { color:var(--muted); font-size:.78rem; }
    .modal-backdrop { position:fixed; inset:0; z-index:10; display:grid; place-items:center; padding:20px; background:rgba(0,0,0,.72); }
    .modal-backdrop[hidden] { display:none !important; }
    .modal { width:min(900px,100%); max-height:85vh; overflow:auto; padding:20px; border:1px solid var(--border); border-radius:14px; background:var(--panel); }
    pre { margin:0; padding:12px; overflow:auto; border:1px solid var(--border); border-radius:8px; background:#0b0f14; color:#d8e3f2; white-space:pre-wrap; }
    .warning { margin:8px 0; padding:9px 10px; border-left:3px solid var(--danger); background:#32151a; color:#fecaca; }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <h1>ESX-snap Policy</h1>
      <p class="lede">Create IBM snapshot policy ESX-snap (daily, keep 7 days) and a per-site volume group. Preview / Dry-run first. Run Create mutates selected arrays. Creating objects is operator-initiated. The policy schedules snapshots; Run does not create snapshots immediately.</p>
      <div class="actions">
        <a class="btn secondary" href="/">Health Dashboard</a>
        <a class="btn secondary" href="/snapshot-schedule">Snapshot Schedule</a>
        <a class="btn secondary" href="/fc-consistgrp">FlashCopy CGs</a>
      </div>
    </section>
    <section class="section">
      <h2>Policy</h2>
      <p>Name <strong>ESX-snap</strong> · daily · keep 7 days · start
        <input id="start-time" value="02:00" size="6" aria-label="Start time">
      </p>
      <div class="actions">
        <button type="button" class="secondary" id="select-all-btn">Select all</button>
        <button type="button" class="secondary" id="select-none-btn">Select none</button>
        <button type="button" class="secondary" id="preview-btn">Preview / Dry-run</button>
        <button type="button" class="danger" id="run-btn" disabled>Run Create</button>
        <span class="hint" id="status"></span>
      </div>
      <div id="arrays"><p class="hint">Loading arrays…</p></div>
    </section>
  </main>
  <div class="modal-backdrop" id="modal" hidden>
    <div class="modal">
      <h2 id="modal-title">Preview</h2>
      <pre id="modal-body"></pre>
      <div class="actions"><button type="button" class="secondary" id="modal-close">Close</button></div>
    </div>
  </div>
  <p class="footer wrap">LaunchPad {{APP_VERSION}}</p>
  <script>
    const arraysEl = document.getElementById("arrays");
    const statusEl = document.getElementById("status");
    const startEl = document.getElementById("start-time");
    const runBtn = document.getElementById("run-btn");
    const modal = document.getElementById("modal");
    const modalBody = document.getElementById("modal-body");
    const modalTitle = document.getElementById("modal-title");
    let cards = [];
    window.__esxPreviewOk = false;
    window.__esxPreviewHash = "";

    function invalidatePreview() {
      window.__esxPreviewOk = false;
      window.__esxPreviewHash = "";
      runBtn.disabled = true;
    }

    function showModal(title, text) {
      modalTitle.textContent = title;
      modalBody.textContent = text;
      modal.hidden = false;
    }

    async function loadCards() {
      const res = await fetch("/api/esx-snap-policy/cards");
      const data = await res.json();
      cards = data.cards || [];
      render();
    }

    function selectedIds() {
      return [...document.querySelectorAll(".array-check:checked")].map((el) => Number(el.dataset.cardId));
    }

    function arrayPayload() {
      return selectedIds().map((id) => {
        const vg = document.getElementById("vg-" + id);
        const names = [...document.querySelectorAll(".vol-" + id + ":checked")].map((el) => el.dataset.name);
        return { card_id: id, vg_name: vg ? vg.value : "", volume_names: names };
      });
    }

    function render() {
      if (!cards.length) {
        arraysEl.innerHTML = '<p class="hint">No IBM FlashSystem / SVC SSH cards.</p>';
        return;
      }
      arraysEl.innerHTML = cards.map((card) => {
        const checked = document.querySelector('.array-check[data-card-id="' + card.id + '"]');
        const on = checked ? checked.checked : false;
        const panel = on ? (
          '<div class="actions">' +
          '<label>Volume group <input id="vg-' + card.id + '" value="' + (card.default_vg_name || "") + '"></label>' +
          '<button type="button" class="secondary load-vols" data-card-id="' + card.id + '">Load volumes</button>' +
          '<input class="vol-search" data-card-id="' + card.id + '" placeholder="Search volumes">' +
          '</div><div id="vols-' + card.id + '"><p class="hint">Load volumes for this array.</p></div>'
        ) : "";
        return '<div class="array"><label class="array-head"><input class="array-check" type="checkbox" data-card-id="' + card.id + '"' + (on ? " checked" : "") + '> <strong>' + card.name + '</strong> <span class="hint">' + (card.host || "") + '</span></label>' + panel + '</div>';
      }).join("");
      arraysEl.querySelectorAll(".array-check, .load-vols, .vol-search").forEach((el) => {
        el.addEventListener("change", () => { if (el.classList.contains("array-check")) { render(); } invalidatePreview(); });
        el.addEventListener("input", invalidatePreview);
      });
      arraysEl.querySelectorAll(".load-vols").forEach((btn) => btn.addEventListener("click", () => loadVolumes(Number(btn.dataset.cardId))));
    }

    async function loadVolumes(cardId) {
      invalidatePreview();
      const box = document.getElementById("vols-" + cardId);
      box.innerHTML = '<p class="hint">Loading volumes…</p>';
      const res = await fetch("/api/esx-snap-policy/volumes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ card_id: cardId }) });
      const data = await res.json();
      if (!data.ok) { box.innerHTML = '<p class="warning">' + (data.error || "Load failed") + '</p>'; return; }
      const rows = (data.volumes || []).map((vol) => {
        const grouped = !!(vol.volume_group || "").trim();
        return '<tr data-name="' + vol.name + '"><td><input class="vol-' + cardId + '" type="checkbox" data-name="' + vol.name + '"' + (grouped ? " disabled" : "") + '></td><td>' + vol.name + '</td><td>' + (vol.capacity || "") + '</td><td>' + (vol.volume_group || "") + '</td></tr>';
      }).join("");
      box.innerHTML = '<table><thead><tr><th></th><th>Name</th><th>Capacity</th><th>Volume group</th></tr></thead><tbody>' + rows + '</tbody></table>';
      box.querySelectorAll("input").forEach((el) => el.addEventListener("change", invalidatePreview));
      const search = document.querySelector('.vol-search[data-card-id="' + cardId + '"]');
      if (search) {
        search.oninput = () => {
          const q = search.value.toLowerCase();
          box.querySelectorAll("tbody tr").forEach((tr) => {
            tr.style.display = (tr.dataset.name || "").toLowerCase().includes(q) ? "" : "none";
          });
        };
      }
    }

    document.getElementById("select-all-btn").onclick = () => {
      document.querySelectorAll(".array-check").forEach((el) => { el.checked = true; });
      render(); invalidatePreview();
    };
    document.getElementById("select-none-btn").onclick = () => {
      document.querySelectorAll(".array-check").forEach((el) => { el.checked = false; });
      render(); invalidatePreview();
    };
    startEl.addEventListener("input", invalidatePreview);
    document.getElementById("modal-close").onclick = () => { modal.hidden = true; };

    document.getElementById("preview-btn").onclick = async () => {
      invalidatePreview();
      statusEl.textContent = "Preview…";
      const body = { start_time: startEl.value, arrays: arrayPayload() };
      const res = await fetch("/api/esx-snap-policy/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await res.json();
      const lines = [];
      (data.arrays || []).forEach((row) => {
        lines.push("# " + (row.name || row.card_id) + " vg=" + (row.vg_name || "") + " runnable=" + row.runnable);
        (row.warnings || []).forEach((w) => lines.push(w));
        (row.steps || []).forEach((s) => lines.push(s.cmd));
        lines.push("");
      });
      showModal("Preview / Dry-run", lines.join("\\n") || JSON.stringify(data, null, 2));
      window.__esxPreviewOk = !!data.ok;
      window.__esxPreviewHash = data.preview_hash || "";
      runBtn.disabled = !window.__esxPreviewOk;
      statusEl.textContent = data.ok ? "Preview succeeded; Run Create is enabled." : "Preview found blocking errors.";
    };

    document.getElementById("run-btn").onclick = async () => {
      if (!window.__esxPreviewOk) return;
      if (!confirm("Create ESX-snap policy and volume groups on the listed arrays? This mutates the arrays.")) return;
      const body = { start_time: startEl.value, arrays: arrayPayload(), confirm: true, preview_hash: window.__esxPreviewHash };
      const res = await fetch("/api/esx-snap-policy/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await res.json();
      showModal("Run Create", JSON.stringify(data, null, 2));
      invalidatePreview();
      statusEl.textContent = data.ok ? "Run finished." : "Run failed or blocked.";
    };

    loadCards();
  </script>
</body>
</html>
"""
```

Preserve VG input values and loaded volume tables across `render()`: keep `const volumesByCard = {}` and `const vgByCard = {}`, write them before rebuilding innerHTML, and redraw stored volume rows after rebuild so Select all does not wipe Load volumes.

Note: in the Python triple-quoted HTML, the Preview join must be `lines.join("\\n")` so the emitted JavaScript is `lines.join("\n")`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_esx_snap_policy_page.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add -- launchpad/esx_snap_policy.py tests/test_esx_snap_policy_page.py
git commit -m "Add ESX-snap Policy page with volume picker and Preview/Run."
```

---

### Task 4: Wire page, dashboard button, nav links

**Files:**
- Modify: `launchpad/health_server.py` (imports, GET page, URL property, `open_esx_snap_policy`, Health Dashboard nav `<a>`)
- Modify: `launchpad/ui/dashboard_view.py` (`tool_specs` + `_open_esx_snap_policy`)
- Modify: `launchpad/snapshot_schedule.py` (hero-actions link)
- Modify: `tests/test_esx_snap_policy_page.py` (dashboard / Health nav / Snapshot Schedule href asserts)
- Modify: `tests/test_dashboard_ui_freeze.py` (`HEADER_OPENERS`)

**Interfaces:**
- Consumes: `ESX_SNAP_POLICY_HTML`, `ESX_SNAP_POLICY_PATH`; `_open_sync_browser_report`
- Produces:
  - `HealthServer.esx_snap_policy_url` → `http://127.0.0.1:{port}/esx-snap-policy`
  - `HealthServer.open_esx_snap_policy(self) -> str`
  - Dashboard label **ESX-snap Policy**
  - `_open_esx_snap_policy` uses `_open_sync_browser_report` then `threading.Thread`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dashboard_ui_freeze.py` in `HEADER_OPENERS`:

```python
    "_open_esx_snap_policy",
```

Add to `tests/test_esx_snap_policy_page.py`:

```python
from pathlib import Path
from launchpad.snapshot_schedule import SNAPSHOT_SCHEDULE_HTML


def test_dashboard_tool_specs_includes_esx_snap_policy():
    source = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")
    assert '"ESX-snap Policy"' in source or "'ESX-snap Policy'" in source
    assert "_open_esx_snap_policy" in source


def test_snapshot_schedule_links_here():
    assert "/esx-snap-policy" in SNAPSHOT_SCHEDULE_HTML
```

Add a source test that Health Dashboard HTML contains the nav link. The hero-actions block lives in `launchpad/health_server.py`:

```python
def test_health_dashboard_nav_includes_esx_snap_policy():
    source = Path("launchpad/health_server.py").read_text(encoding="utf-8")
    assert 'href="/esx-snap-policy"' in source
```

`test_header_openers_register_off_ui_thread` will fail until `_open_esx_snap_policy` exists.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dashboard_ui_freeze.py::test_header_openers_register_off_ui_thread tests/test_esx_snap_policy_page.py -v`

Expected: FAIL (`_open_esx_snap_policy` missing and/or href missing)

- [ ] **Step 3: Wire it**

`health_server.py` top imports (now that the page module exists):

```python
from launchpad.esx_snap_policy import ESX_SNAP_POLICY_HTML, ESX_SNAP_POLICY_PATH
```

GET handler next to `FC_CONSISTGRP_PATH`:

```python
        if path == ESX_SNAP_POLICY_PATH:
            self._send_html(_fill_page(ESX_SNAP_POLICY_HTML))
            return
```

URL property next to `fc_consistgrp_url`:

```python
    @property
    def esx_snap_policy_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{ESX_SNAP_POLICY_PATH}"
```

Open method next to `open_fc_consistgrp`:

```python
    def open_esx_snap_policy(self) -> str:
        """Open the ESX-snap policy page in the default browser."""
        self.ensure_running()
        webbrowser.open(self.esx_snap_policy_url)
        _log(f"Opened ESX-snap Policy in browser: {self.esx_snap_policy_url}")
        return self.esx_snap_policy_url
```

In the Health Dashboard `hero-actions` block, add immediately after the Snapshot Schedule `<a>`:

```html
        <a class="btn secondary" href="/esx-snap-policy" style="font:inherit;border-radius:10px;height:34px;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;padding:0 14px;font-weight:600;background:#0f141d;color:var(--text);border:1px solid var(--border);">ESX-snap Policy</a>
```

In `dashboard_view.py` `tool_specs`, insert after FlashCopy CGs:

```python
            ("ESX-snap Policy", self._open_esx_snap_policy, None),
```

Add method next to `_open_fc_consistgrp`:

```python
    def _open_esx_snap_policy(self) -> None:
        worker = self._open_sync_browser_report(
            status="Opening ESX-snap Policy…",
            fail_log="ESX-snap Policy failed",
            open_url=lambda server: server.open_esx_snap_policy(),
            summary="ESX-snap Policy opened — Preview then Run Create mutates the selected arrays.",
        )
        threading.Thread(target=worker, daemon=True).start()
```

In `snapshot_schedule.py` hero-actions, add:

```html
        <a class="btn secondary" href="/esx-snap-policy">ESX-snap Policy</a>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dashboard_ui_freeze.py tests/test_esx_snap_policy_page.py tests/test_health_server_esx_snap_policy.py tests/test_esx_snap_policy_ops.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add -- launchpad/health_server.py launchpad/ui/dashboard_view.py launchpad/snapshot_schedule.py tests/test_dashboard_ui_freeze.py tests/test_esx_snap_policy_page.py
git commit -m "Wire ESX-snap Policy into the dashboard and Health nav."
```

---

### Task 5: Bump APP_VERSION to 1.6.174

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_capacity_unit_js.py` (pin `1.6.174`)
- Modify: `tests/test_hadoop_sudo_wire.py` (pin `1.6.174`)
- Modify: `tests/test_system_connectivity_version.py` (pin `1.6.174`)
- Modify any other `assert APP_VERSION == "1.6.173"` that fails after the bump (grep before committing)

**Interfaces:**
- Consumes: none
- Produces: `APP_VERSION = "1.6.174"`

- [ ] **Step 1: Write / update the failing pins**

Change those three test files from `"1.6.173"` to `"1.6.174"`. Leave `launchpad/config.py` at 1.6.173 for the red run.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py -v`

Expected: FAIL (assert `1.6.173` != `1.6.174` or config still 1.6.173 vs tests expecting 1.6.174)

- [ ] **Step 3: Bump version**

In `launchpad/config.py`:

```python
APP_VERSION = "1.6.174"
```

Grep `1.6.173` under `tests/` and `launchpad/` and update remaining version pins that assert equality with `APP_VERSION`. Do not bump comments in old specs/plans.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_esx_snap_policy_ops.py tests/test_esx_snap_policy_page.py tests/test_health_server_esx_snap_policy.py tests/test_dashboard_ui_freeze.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add -- launchpad/config.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py
git commit -m "Bump version to 1.6.174 for ESX-snap policy and volume groups."
```

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| New page `/esx-snap-policy` | 3, 4 |
| Dashboard **ESX-snap Policy** + worker opener | 4 |
| Health nav + Snapshot Schedule cross-link | 4 |
| Policy `ESX-snap` daily / 7 days / `02:00` / `backupstarttime` | 1 |
| VG `{CardName}_ESX-snap` sanitize + 63 + suffix | 1 |
| Pick volumes search/check; disable if already in VG | 3 |
| Existence = error, not skip | 1, 2 |
| Many: blocked array does not block others | 1, 2 |
| Preview then confirm Run; hash gate | 2, 3 |
| Sequential inventory SSH; no SSH on page open | 2, 3 |
| `addvolumetovolumegroup` | 1 |
| No rollback message on partial failure | 2 |
| IBM `SVC_PROFILES` only | 2 |
| No Tk decrypt/register | 4 |
| Version 1.6.174 | 5 |
| Firmware 8.5.1 message | 1 |
