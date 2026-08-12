# Dell HP Report Wkly Display Fallback — Design

**Date:** 2026-08-12  
**Status:** Approved  
**App version target:** 1.6.162  
**Extends:** `docs/superpowers/specs/2026-08-12-dell-hpe-report-display-capacity-design.md`

## Problem

After 1.6.161, **HP Report** / **HP Forecast** fill from display capacity, but **HP Report - Wkly** shows Facility / Array / Model with **blank** Usable / Used / Utilization. Wkly cells are read only from the weekly snapshot store; display-only HPE rows never upsert system snapshots.

## Decision

In `_build_report_wkly_sheet`, when a card has no snapshot dict for a week column that is the **current report ISO week**, fall back to the row’s `curr_usable_gib` / `curr_used_gib` / `curr_util`. Do not write raw/pool into the snapshot store. Other weeks stay blank unless a real snapshot exists.

## Non-goals

- Storing display/raw capacity as weekly snapshots
- Changing Forecast-Wkly projection math (already uses row util)
- Capacity Report UI / HPE parse

## Success

- [ ] HP Report - Wkly shows current-week capacity for display-only HPE rows
- [ ] Snapshot store unchanged for those cards
- [ ] System-snapshot weeks still prefer store bytes
