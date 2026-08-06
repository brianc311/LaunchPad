# Dell Report Walgreens Visual Fidelity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or subagent-driven-development. Steps use checkbox syntax.

**Goal:** Make Dell Report IBM/HP sheets and stub tabs match Walgreens June workbook layout (headers, wording, logos, tab order).

**Architecture:** Bundle logo PNGs under `launchpad/assets/dell_report/`. Rewrite sheet header/row writers in `dell_report_export.py` to use reference column offset (data from column B) and labels. Expand stub sheet list and order. Keep collect/LED logic.

**Tech Stack:** openpyxl, pytest.

**Spec:** `docs/superpowers/specs/2026-08-05-dell-report-walgreens-visual-design.md`

## Global Constraints

- Branch: `feature/hpe-capacity-parse`
- Live data: IBM/HP Report + Forecast only
- Output `.xlsx`; version **1.6.117**
- Missing logos must not fail export
- Update tests for column B facility

## Tasks

### Task 1: Assets + sheet order stubs
- Extract/commit `launchpad/assets/dell_report/logo_*.png`
- Expand `STUB_SHEET_NAMES` / ordered sheet list per spec
- Tests for sheet order

### Task 2: Report/Forecast layout + logos
- Rewrite headers/rows to Walgreens layout (Useable Capacity…, Date/Values, col B+)
- Embed logos when present
- Fix LED column indices
- Update export tests

### Task 3: Version 1.6.117 + full dell_report tests
