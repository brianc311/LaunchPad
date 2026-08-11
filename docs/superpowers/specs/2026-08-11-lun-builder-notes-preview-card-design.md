# LUN Builder notes, Preview gate, and Card hint dropdown

**Date:** 2026-08-11  
**Status:** Approved for implementation  
**App version target:** 1.6.153  
**Depends on:** LUN Builder page (`lun_builder.py`), preview/create session (`health_server.py` `_lun_build_content_hash` / `_lun_preview_session`), `/api/cards`  
**Approach:** Targeted fixes (Approach 1)  
**Base branch:** `main` (tip at 1.6.152)

## Problem

Three operator issues on LUN Builder:

1. **Notes do not save.** Build-details Name / Location / Notes live only in the DOM. `render()` (Add host, Add LUN, Done, Plan/Inventory, Preview) rewrites the textarea from `build.notes` without reading the form first, so typed comments vanish.
2. **Run Create always demands Preview again.** Preview persists the build (`updated_at` = now). Run Create persists again with a newer timestamp. `_lun_build_content_hash` hashes the full `normalize_build` dict, including `updated_at`, so the session never matches. Failed create clears the session, so Preview → Run loops forever.
3. **Card hint is free text.** Operators must type the SSH Health Card name (or a unique fragment). They want a dropdown of cards.

## Goals

- Typed Name, Location, and Notes survive `render()` and persist on Save / Preview / Run.
- After a successful runnable Preview, Run Create succeeds even if the next save only changes `updated_at`, `notes`, `plan_done`, or `command_done`.
- Changing hosts, LUN specs, storage profile, pool, or card hint still requires a new Preview.
- Build-details Card hint is a `<select>` of all SSH Health Cards; unmatched saved hints stay as an extra option until the operator picks a listed card.
- Bump `APP_VERSION` to **1.6.153**.

## Non-goals (v1)

- Per-row Card hint dropdown in the LUN table (header still fills every LUN row).
- Type-to-search combobox.
- Changing Preview expiry (300s) or `find_card_by_hint` matching rules.
- Auto-selecting a unique partial card match.
- Skipping persist on Run Create.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Card list | All SSH Health Cards from `/api/cards` |
| Unmatched saved hint | Keep as extra `<option>` until a listed card is chosen |
| Implementation | Approach 1: write-through notes + hash ignores metadata + header-only select |

## Behavior

### Notes

On `input` for `#build-name`, `#build-location`, and `#build-notes`, copy the value onto the in-memory build (`name` / `location` / `notes`). `render()` calls `readSummary()` before filling those fields so later redraws cannot wipe unsaved text.

Save, Preview, and Run still persist `notes` through `normalize_build`. Empty notes show the `Planning notes` placeholder.

### Preview session hash

`_lun_build_content_hash` hashes a normalized build after **omitting**:

- `updated_at`
- `notes`
- `plan_done`
- `command_done`
- `name`
- `location`

Remaining fields (id, is_template, default storage/pool/card, hosts, luns) still count. Renaming the build or editing notes does not require a new Preview.

Session rules unchanged: matching `build_id`, hash, `runnable is True`, `expires_at` in the future. Hash mismatch still clears `_lun_preview_session`.

### Card hint dropdown

Replace `#default-card-hint` `<input>` with a `<select>` keeping that id:

1. Empty option: `Select Health Card` (value `""`)
2. SSH cards from `healthCards` / `/api/cards`, sorted by name (option value = card `name`)
3. If `default_card_hint` is non-empty and not equal to any card name, add it as an extra option

`change` still runs `onBuildDefaultsChanged` (copy onto every LUN row). Per-row `card_hint` inputs stay text. Hint copy unchanged. Preview/Run still use `find_card_by_hint`.

Rebuild the select in `render()` from the current card list + saved hint.

## Architecture

| Unit | Change |
|------|--------|
| `launchpad/lun_builder.py` | Write-through + `readSummary` before `render`; Card hint `<select>` |
| `launchpad/health_server.py` | `_lun_build_content_hash` omits metadata keys |
| `launchpad/config.py` | `APP_VERSION` → `1.6.153` |
| Tests | Hash ignore metadata; page select + notes write-through; version pins |

## Testing

- Preview, then set `updated_at` / `notes` / `name` / `plan_done` / `command_done` and save → `create_lun_build(..., confirm=True)` succeeds.
- Preview, then change LUN `size` and save → create returns “Preview must be run again”.
- `LUN_BUILDER_HTML` contains `<select id="default-card-hint"` (not a text input with that id).
- `#build-notes` `input` writes `build.notes`; Add host / remove / plan-done call `readSummary` before `render()` (not inside `render()`, so first load and picker change cannot wipe the active build).
- Version pin `1.6.153`.

## Version

Bump `APP_VERSION` to **1.6.153** when the feature ships.
