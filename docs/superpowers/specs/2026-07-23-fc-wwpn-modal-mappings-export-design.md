# FC WWPN Modal — Hosts & LUN Mappings Export (Excel / CSV / PDF)

**Date:** 2026-07-23  
**Status:** Approved for implementation  
**App version target:** next patch on the implementation branch  
**Depends on:** FC WWPN Report modal (`fc_wwpn_report.py`); Site picker / `card_id` export filter (`feature/fc-wwpn-site-picker`)  
**Approach:** Server Excel/CSV + modal Print for PDF (Approach 1)  
**Base branch:** `feature/fc-wwpn-site-picker` (or tip that includes Site picker + `card_id` export)

## Problem

The **Hosts & LUN Mappings** modal (Hosts & WWPNs, LUN Mappings, Fabric Logins) is view-only. Operators need to export that data for a given site for offline review, tickets, or archives. Page-level **Export Excel** covers Ports / Hosts / LUN Mappings across site(s) but does not include Fabric Logins and is not scoped from the modal UI.

## Goals

- From the Hosts & LUN Mappings modal for **any** site, export **all three** tabs in one action:
  - **Excel** — one workbook, three sheets
  - **CSV** — one ZIP with three CSV files
  - **PDF** — browser Print / Save as PDF of all three sections
- Keep page-level Export Excel and Print unchanged.

## Non-goals (v1)

- Generating a real `.pdf` file server-side
- Exporting only the active tab
- Changing page-level FC WWPN Export Excel contents (Ports / Hosts / Maps)
- One-click export of every site’s mappings from the modal
- WAG / Contingency-group filtering inside this modal export

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Content | **A** — always all three tabs (Hosts, LUN Mappings, Fabric Logins) |
| PDF | **A** — browser Print / Save as PDF |
| CSV packaging | **A** — ZIP with `hosts.csv`, `lun_mappings.csv`, `fabric_logins.csv` |
| Implementation | Approach 1 — server Excel/CSV; modal Print for PDF |

## Behavior

### Modal controls

- Add beside **Close**: **Export Excel**, **Export CSV**, **Print / Save PDF**.
- Enabled when a site card is open in the modal (`activeCard` set).
- Exports always use the **open site** only (not the page Site picker filter, except that the open card is whichever site the operator opened).

### Excel

- Filename: `FC_Mappings_{safe_site_name}_{stamp}.xlsx`
- Sheets: **Hosts**, **LUN Mappings**, **Fabric Logins**
- Columns match the modal tables:
  - Hosts: ID, Host, Status, Protocol, WWPN count, Host WWPNs
  - LUN Mappings: Host, Volume / VDisk, SCSI / LUN ID, VDisk ID, Host WWPNs
  - Fabric Logins: Node, Local WWPN, Remote WWPN, Host, State, Local port
- Optional site metadata columns (Location / Site / IP) may be included for consistency with page-level export if low cost; otherwise modal columns only are fine.
- Optional `open=1` to open after download (same pattern as existing FC export).

### CSV

- Filename: `FC_Mappings_{safe_site_name}_{stamp}.zip`
- Contents: `hosts.csv`, `lun_mappings.csv`, `fabric_logins.csv` with the same columns as the Excel sheets.

### PDF

- **Print / Save PDF** renders (or temporarily shows) **all three** sections for the open site, then calls `window.print()`.
- Operator chooses “Save as PDF” (or equivalent) in the browser print dialog.
- Print CSS should hide chrome (tabs, export buttons) and show all three tables; restore UI after print if a temporary layout was used.

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `launchpad/fc_wwpn_export.py` | Fabric row helper; `build_fc_mappings_workbook(cards)`; `export_fc_mappings_csv_zip(cards)` |
| `launchpad/health_server.py` | `GET /api/fc-wwpn-mappings-export?card_id=…&format=xlsx\|csv` (`card_id` required); filter to that card; return workbook or ZIP |
| `launchpad/fc_wwpn_report.py` | Modal buttons; fetch Excel/CSV; print-all-sections for PDF |
| Tests | Row/workbook/zip helpers; API requires `card_id` + format; page wires three actions |

### API sketch

```
GET /api/fc-wwpn-mappings-export?card_id=<id>&format=xlsx|csv&open=0|1
```

- Missing / unknown `card_id` → `400` with JSON error (do not export all cards from this endpoint).
- `format` must be `xlsx` or `csv`.

## Testing

- Helper builds three sheets / three CSV members with expected headers for a fixture card that includes hosts, mappings, and fabric.
- API: `card_id` required; `format=csv` returns zip content-type; `format=xlsx` returns spreadsheet content-type.
- Page HTML/JS: modal export/print controls present; Excel/CSV fetch includes `card_id` and `format`; print path includes all three section titles.

## Out of scope follow-ups

- Server-generated PDF
- Active-tab-only export toggle
- Bulk “export all sites’ mappings” from the hero bar
