# HPE System + Raw via `showsys -space` — Design

**Date:** 2026-08-05  
**Status:** Approved (chat); pending file review  
**App version target:** 1.6.116+  
**Extends:** `docs/superpowers/specs/2026-08-05-capacity-layers-array-pools-raw-design.md`  
**Problem context:** Capacity Report HPE cards show “All CPGs” as System utilization and omit Raw; IBM FlashSystem cards correctly show System + Raw. SSMC Raw Capacity (Total / Allocated / Free) matches `showsys -space`.

## Problem

1. **Stale CPG merge:** Capacity refresh with **Include CPG / pools** off still merges prior `showcpg` into `command_results`, so CRITICAL pool lines and CPG-derived HTML keep appearing.
2. **Wrong System source:** When `showsys -d` is missing/unparseable, LaunchPad falls back to **All CPGs** rollup and labels it as System utilization. The pools toggle only hides `.capacity-pools-wrap`, not that rollup.
3. **Missing HPE Raw:** Raw was only parsed from optional KV fields on `showsys -d`. Many 3PAR/Primera arrays expose SSMC-style raw via **`showsys -space`** (Total / Allocated / Free / Failed in MB), which we do not collect today.

## Goals

- HPE Capacity Report matches IBM layout: **System utilization** + **Raw utilization** (when Raw toggle on and data present).
- **System** always from array CLI (`showsys -d`), not from CPG sum when pools are off.
- **Raw** from `showsys -space` Total row (all drive types) — same numbers as SSMC System → Capacity → Raw Capacity Total.
- With **Include CPG / pools** off: no CPG blocks, no pool CRIT from stale `showcpg`, no “All CPGs” as the primary System bar.
- With pools **on**: keep per-CPG bars and pool alerts as today; System still prefers `showsys -d`.

## Non-goals (this pass)

- Per-media Raw bars (`showsys -space -devtype SSD|FC|NL`).
- `showpd` / CSV size sums.
- Changing IBM `lssystem` physical parsing.
- Raw-based alerts.
- Auto SSH when only toggling checkboxes (Refresh still required for new commands).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| System (HPE) | `showsys -d` → Total / Allocated / Free Capacity |
| Raw (HPE) | `showsys -space` → system Total Capacity / Allocated / Free (MB) |
| CPG | `showcpg` only when Include CPG / pools is on |
| Stale pools | When `include_pools=0` on capacity refresh, **remove** prior pool/CPG results before analyze |
| CPG-as-System fallback | Allowed only when pools are **on** (or when building alerts from available pool data); **do not** present All CPGs as System HTML when pools are off |
| Raw UI | Existing **Show raw capacity** toggle; hide via `capacity-raw-wrap` |
| Extra SSH | Add `showsys -space` to HPE 3PAR/Primera presets and capacity-focus keep list |

## Command / data map

| Layer | Command | Parse |
|-------|---------|--------|
| System | `showsys -d` | Existing `parse_capacity_summary` (allocated preferred) |
| Raw | `showsys -space` | New/extended parse → `raw_capacity_summary` (Total / Allocated / Free in MB) |
| CPG | `showcpg` | Existing pool rows |

Label suggestion for the new command: **`Capacity - Raw`** / `showsys -space` (so capacity-focus filter keeps it via “capacity” + `showsys`).

`showsys -space -devtype SSD` is **not** required for v1; Total from unfiltered `showsys -space` matches SSMC “Total” row.

## Behavior

### 1) Presets

- Insert `("Capacity - Raw", "showsys -space")` after Capacity - System on `HP_3PAR_COMMANDS` and `HPE_PRIMERA_COMMANDS`.
- `normalize_hpe_capacity_commands` (or equivalent): ensure `showsys -space` is present for HPE profiles; do not rewrite it to `showsys -d`.

### 2) Parse

- Prefer parsing Raw from the **Capacity - Raw** / `showsys -space` result when present.
- Fall back to existing `parse_raw_capacity_summary` on `showsys -d` output if `-space` is absent (older cards / partial refresh).
- `showsys -space` sample shape (MB): Total Capacity, Allocated Capacity, Free Capacity, Failed Capacity under a capacity/space section — treat like system capacity keys but assign to **raw** summary only (do not overwrite System from `-d`).

### 3) Capacity refresh merge

When `focus=capacity` and `include_pools=False`:

1. Run filtered commands (no `showcpg`).
2. Merge into prior results **but drop** any prior items that are pool/CPG capacity commands (`_is_pool_capacity_command`).
3. Re-run `analyze_health` on the cleaned list.

When `include_pools=True`, keep current merge behavior (update overlapping keys; preserve other health cmds).

### 4) UI / analyze_health

- System block: `system_capacity` from `showsys -d` only when parse succeeds.
- If System missing and pools off: no All-CPGs System bar; optional short empty/error state; pool alerts from leftover data should not appear after merge fix.
- If System missing and pools on: existing All-CPGs rollup fallback OK (labeled All CPGs).
- Raw block: from `raw_capacity_summary` via existing `format_capacity_report_html` + Show raw toggle.

### 5) Excel / exports

- Prefer same summaries already on the card (`capacity_summary`, `raw_capacity_summary`).
- No new Excel columns required beyond existing raw flags from capacity-layers work.

## Testing

- Parse fixture for `showsys -space` MB Total/Allocated/Free → raw summary + used_pct.
- analyze_health: `-d` system + `-space` raw both in popup; System utilization and Raw utilization present.
- Capacity merge: prior `showcpg` removed when `include_pools=0`; popup has no pool wrap / no Pool CRIT from CPG; no “All CPGs” when `-d` missing and pools off.
- Preset lists include `showsys -space` for 3PAR and Primera.
- Regression: IBM physical raw path unchanged.

## Success criteria

- After Refresh with Raw on: HPE card shows System (from `-d`) and Raw (from `-space`) like IBM Anderson/Carolina.
- With CPG/pools off: no All CPGs System bar, no per-CPG blocks, no stale Pool CRITICAL lines from `showcpg`.
- Numbers align with SSMC Raw Capacity Total for the same array (within unit rounding).
