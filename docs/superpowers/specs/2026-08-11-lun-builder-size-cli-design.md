# LUN Builder FlashSystem size CLI

**Date:** 2026-08-11  
**Status:** Approved for implementation  
**App version target:** 1.6.154  
**Depends on:** `lun_builder_create.py`, `parse_capacity_to_gb` in `contingency_snap_create.py`  
**Approach:** LUN Builder only (Approach A)  
**Base branch:** `main` (tip at 1.6.153)

## Problem

Run Create for FlashSystem failed with:

```text
svctask mkvdisk -name pmtvvio03a_root_1 … -size 9.313225746154785e-08 -unit gb
ERROR: CMMVC5716E Non-numeric data was entered for the numeric field [-size].
```

Root cause: a bare size like `100` is parsed by shared `parse_capacity_to_gb` as **100 bytes** (default unit `B`). That becomes ~`9.31e-08` GB. Python’s default float formatting puts scientific notation into the CLI, which Spectrum Virtualize rejects.

Templates and the LUN Builder design already use values like `100GB`. Operators may still type a bare number and expect GB.

## Goals

- In LUN Builder, a size with **no unit** means **GB** (`100` → 100 GB).
- Explicit units keep today’s meaning (`100GB`, `1TB`, `50GB`, etc.).
- FlashSystem `mkvdisk -size` is always a plain numeric token (`100`, `1.5`), never scientific notation.
- Contingency snap create is unchanged (bare numbers stay bytes there).
- Bump `APP_VERSION` to **1.6.154**.

## Non-goals (v1)

- Changing shared `parse_capacity_to_gb` default unit.
- Active Issues empty cards / collapsible section.
- Health Excel / per-card CLI log export.
- Adding `GiB` to the size regex (existing capacity-units work stays display-only for create CLI).
- Changing DS8884 / XIV command shape (they still pass the typed size string).
- Changing HP `createvv` beyond using the same GB parse path (still `math.ceil` + `g`).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Bare number meaning (LUN Builder) | GB |
| Shared parser / Contingency | Unchanged (bare → bytes) |
| Scope | LUN Builder create path only |
| Scientific notation | Never in `mkvdisk -size` |

## Behavior

### Parse (LUN Builder)

`_size_gb` in `lun_builder_create.py`:

1. Trim the size string.
2. If it matches a bare number (digits with optional decimal, no unit suffix), append `GB` before calling `parse_capacity_to_gb`.
3. Otherwise call `parse_capacity_to_gb` as today.
4. Reject `None` or `<= 0` with `Invalid LUN size`.

Do **not** change `parse_capacity_to_gb` itself.

### Format (FlashSystem mkvdisk)

New helper formats the GB value for CLI:

- Whole numbers → integer string (`100`, not `100.0`)
- Fractions → fixed decimal without exponent (`1.5`, never `1.5e+0` or similar)

Command stays:

`svctask mkvdisk -name {name} -mdiskgrp {pool} -size {token} -unit gb`

### Other profiles

- HP 3PAR / Primera: still `f"{math.ceil(size_gb)}g"` after the updated parse.
- DS8884 / XIV: still pass the operator’s original size string through `cli_token`.

## Architecture

| Unit | Change |
|------|--------|
| `lun_builder_create._size_gb` | Bare number → treat as GB |
| `lun_builder_create` (new format helper) | Plain `-size` token for mkvdisk |
| `contingency_snap_create.parse_capacity_to_gb` | No change |
| `config.APP_VERSION` | `1.6.154` |

## Testing

- `100` and `100GB` both produce `-size 100 -unit gb` on FlashSystem steps.
- `1.5` / `1.5GB` produce `-size 1.5` (no `e` / `E` in the command).
- A value that previously became scientific notation must not contain `e`/`E` in `-size`.
- Contingency: `parse_capacity_to_gb("100")` still means bytes (~`9.31e-08` GB as float).
- Existing LUN create tests with `10GB` / `50GB` keep passing.
- Version pin tests expect `1.6.154`.

## Out of scope follow-ups

- Active Issues: empty `alert ·` text + collapsible section.
- Confirm whether Health Export Excel + Raw output already covers per-card CLI logs.
