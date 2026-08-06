# Site Lookup Offline Snapshots (+ LUN fallback) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist successful Site Lookup Live Refresh payloads to disk and fall back to that store (then LUN offline inventory) when in-memory card inventory is empty.

**Architecture:** New `site_lookup_offline` settings store mirrors LUN offline patterns. `refresh_site_lookup` upserts on success only. `site_lookup_cache` prefers memory → Site Lookup offline → LUN offline → empty. UI badges distinguish `offline` vs `offline_lun`.

**Tech Stack:** Python settings JSON via HealthServer `_get_setting`/`_set_setting`, existing `site_lookup_data` payload builders, pytest.

**Spec:** `docs/superpowers/specs/2026-08-06-site-lookup-offline-snapshots-design.md`

## Global Constraints

- APP_VERSION currently `1.6.129`; bump to `1.6.130` when shipping.
- Setting key: `site_lookup_offline_inventory`.
- Do not change LUN offline schema/eligibility; only read it as tertiary fallback.
- Failed Live Refresh must not overwrite Site Lookup snapshots.
- Windows PowerShell commits (here-string).

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/site_lookup_offline.py` | Normalize/upsert/load Site Lookup offline store |
| `launchpad/site_lookup_data.py` | `payload_has_inventory`, `payload_from_offline_snapshot`, `payload_from_lun_offline` |
| `launchpad/health_server.py` | Persist + cache fallback chain |
| `launchpad/site_lookup.py` | Offline badges/status |
| `tests/test_site_lookup_offline.py` | Store + data helper tests |
| `tests/test_site_lookup_api.py` | API persist/fallback/no-clobber |
| `launchpad/config.py` | `1.6.130` |

---

### Task 1: Offline store + payload helpers

**Files:**
- Create: `launchpad/site_lookup_offline.py`
- Modify: `launchpad/site_lookup_data.py`
- Create: `tests/test_site_lookup_offline.py`

**Interfaces:**
- `SITE_LOOKUP_OFFLINE_SETTING = "site_lookup_offline_inventory"`
- `normalize_store(raw) -> dict[str, dict]`
- `upsert_snapshot(store, snapshot) -> dict`
- `snapshot_from_live_payload(payload: dict) -> dict | None`
- `payload_has_inventory(payload: dict) -> bool`
- `payload_from_offline_snapshot(snapshot: dict) -> dict` (`source="offline"`)
- `payload_from_lun_offline(snapshot: dict, *, card: dict) -> dict` (`source="offline_lun"`)

- [ ] **Step 1: Write failing tests** in `tests/test_site_lookup_offline.py` covering normalize/upsert, `payload_has_inventory`, offline + lun payload sources.

- [ ] **Step 2: Implement helpers** (minimal).

- [ ] **Step 3: Run** `python -m pytest tests/test_site_lookup_offline.py -q` — PASS

- [ ] **Step 4: Commit**

---

### Task 2: Wire HealthServer persist + cache fallback

**Files:**
- Modify: `launchpad/health_server.py`
- Modify: `tests/test_site_lookup_api.py`

- [ ] **Step 1: Tests** — successful refresh persists; after clearing `command_results`, cache returns offline; failed refresh does not clobber; LUN-only fallback returns `offline_lun`.

- [ ] **Step 2: Implement** `get/set_site_lookup_offline_inventory`, upsert after successful `refresh_site_lookup`, extend `site_lookup_cache` fallback chain.

- [ ] **Step 3: Run** focused API + offline tests — PASS

- [ ] **Step 4: Commit**

---

### Task 3: UI badges + version

**Files:**
- Modify: `launchpad/site_lookup.py`
- Modify: `tests/test_site_lookup_page.py` (assert offline badge strings)
- Modify: `launchpad/config.py` → `1.6.130`

- [ ] **Step 1: Failing page test** for Offline / Offline LUN badge text in HTML/JS.

- [ ] **Step 2: Update** `renderPayload` / status helpers for `offline` and `offline_lun`.

- [ ] **Step 3: Bump version; run** site lookup + offline tests — PASS

- [ ] **Step 4: Commit**

---

## Spec coverage

| Requirement | Task |
|-------------|------|
| Persist on successful Live Refresh | 2 |
| Memory → offline → LUN → empty | 1–2 |
| No clobber on failure | 2 |
| LUN schema unchanged | 2 (read-only) |
| UI badges | 3 |
| Version bump | 3 |
