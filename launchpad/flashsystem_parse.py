import html
import re
from typing import Any

_SIZE_RE = re.compile(
    r"^(-?\d+(?:\.\d+)?)\s*(TiB|TB|GB|MB|KB|PB|B)?$",
    re.IGNORECASE,
)


def _parse_size_bytes(value: str) -> float | None:
    raw = (value or "").strip().replace(",", "")
    if not raw:
        return None
    match = _SIZE_RE.match(raw)
    if not match:
        return None
    amount = float(match.group(1))
    unit = (match.group(2) or "B").upper()
    if unit == "TIB":
        unit = "TB"
    multipliers = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4,
        "PB": 1024**5,
    }
    return amount * multipliers.get(unit, 1)


def _format_bytes(num_bytes: float) -> str:
    if num_bytes <= 0:
        return "0 GB"
    units = ["GB", "TB", "PB"]
    value = num_bytes / (1024**3)
    unit = "GB"
    if value >= 1024:
        value /= 1024
        unit = "TB"
    if value >= 1024:
        value /= 1024
        unit = "PB"
    return f"{value:.1f} {unit}"


def _looks_like_header(line: str) -> bool:
    lowered = line.lower()
    if ":" in line and line.count(":") >= 3:
        return True
    tokens = line.split()
    if len(tokens) < 2:
        return False
    alpha_tokens = sum(1 for token in tokens if token.isalpha() or "_" in token)
    return alpha_tokens >= max(2, len(tokens) - 1)


def _looks_like_df_header(line: str) -> bool:
    lowered = line.lower()
    tokens = lowered.split()
    if "use%" in tokens or "pcent" in tokens:
        return True
    if lowered.startswith("filesystem") or lowered.startswith("mounted on"):
        return True
    return "size" in tokens and "used" in tokens and "avail" in tokens


def _parse_df_row(line: str) -> list[str]:
    line = line.strip()
    if not line:
        return []
    parts = re.split(r"\s+", line)
    if len(parts) >= 5 and parts[0].startswith("/"):
        return parts[:5]
    return parts


def _parse_df_table(output: str) -> tuple[list[str], list[list[str]]]:
    lines = [line.strip() for line in output.strip().splitlines() if line.strip()]
    if not lines:
        return [], []

    default_headers = ["Mounted on", "Use%", "Size", "Used", "Avail"]
    if _looks_like_df_header(lines[0]):
        header_tokens = lines[0].split()
        if (
            len(header_tokens) >= 2
            and header_tokens[0].lower() == "mounted"
            and header_tokens[1].lower() == "on"
        ):
            headers = ["Mounted on", *header_tokens[2:]]
        elif header_tokens and header_tokens[0].lower() == "filesystem":
            headers = ["Filesystem", *header_tokens[1:]]
        elif header_tokens and header_tokens[0].lower() == "target":
            headers = ["Target", *header_tokens[1:]]
        else:
            headers = header_tokens
        data_lines = lines[1:]
    else:
        headers = list(default_headers)
        data_lines = lines

    rows: list[list[str]] = []
    for line in data_lines:
        if _looks_like_df_header(line):
            continue
        row = _parse_df_row(line)
        if row:
            rows.append(row)
    if not rows:
        return [], []

    width = len(headers)
    normalized: list[list[str]] = []
    for row in rows:
        if len(row) < width:
            row = row + [""] * (width - len(row))
        elif len(row) > width:
            row = row[:width]
        normalized.append(row)
    return headers, normalized


def _parse_colon_table(output: str) -> tuple[list[str], list[list[str]]]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return [], []
    if len(lines) >= 2 and ":" in lines[0]:
        headers = lines[0].split(":")
        rows = [row.split(":") for row in lines[1:]]
        return headers, rows

    if len(lines) == 1 and lines[0].count(":") >= 2:
        parts = lines[0].split(":")
        if parts[0].strip().lower() == "id":
            for index in range(1, len(parts)):
                if parts[index].strip().isdigit():
                    headers = parts[:index]
                    rest = parts[index:]
                    row_size = len(headers)
                    if row_size and len(rest) % row_size == 0:
                        rows = [rest[offset : offset + row_size] for offset in range(0, len(rest), row_size)]
                        return headers, rows

    return [], []


def _parse_csv_table(output: str) -> tuple[list[str], list[list[str]]]:
    """Parse simple CSV tables (e.g. HPE ``setclienv csvtable 1`` output)."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) < 2:
        return [], []
    if "," not in lines[0] or lines[0].count(",") < 2:
        return [], []
    headers = [part.strip() for part in lines[0].split(",")]
    if len(headers) < 2:
        return [], []
    rows: list[list[str]] = []
    for line in lines[1:]:
        if "," not in line:
            continue
        cells = [part.strip() for part in line.split(",")]
        if len(cells) < 2:
            continue
        if len(cells) < len(headers):
            cells = cells + [""] * (len(headers) - len(cells))
        elif len(cells) > len(headers):
            cells = cells[: len(headers)]
        rows.append(cells)
    return headers, rows


def _parse_space_table(output: str) -> tuple[list[str], list[list[str]]]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) < 2:
        return [], []
    headers = lines[0].split()
    rows = [line.split() for line in lines[1:] if line.split()]
    return headers, rows


def _parse_any_table(output: str) -> tuple[list[str], list[list[str]]]:
    headers, rows = _parse_csv_table(output)
    if rows:
        return headers, rows
    headers, rows = _parse_colon_table(output)
    if rows:
        return headers, rows
    return _parse_space_table(output)


def _record_get(record: dict[str, str], *keys: str) -> str:
    lowered = {key.lower(): value for key, value in record.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _record_find_header(record: dict[str, str], *keys: str) -> str | None:
    lowered = {key.lower(): key for key in record}
    for key in keys:
        header = lowered.get(key.lower())
        if header is not None:
            return header
    return None


def _parse_sized_field(record: dict[str, str], *keys: str) -> float | None:
    """Parse a size cell; headers ending in ``_MB`` are treated as megabytes."""
    for key in keys:
        header = _record_find_header(record, key)
        if header is None:
            continue
        value = str(record.get(header, "")).strip()
        if not value:
            continue
        header_lower = header.lower()
        if header_lower.endswith("_mb") or header_lower.endswith("(mb)"):
            parsed = _parse_size_bytes(f"{value}MB")
        else:
            parsed = _parse_size_bytes(value)
        if parsed is not None:
            return parsed
    return None


def _parse_key_values(output: str) -> dict[str, str]:
    """Parse key/value CLI output (space-separated or colon-delimited)."""
    values: dict[str, str] = {}
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return values

    if len(lines) == 1 and lines[0].count(":") >= 2:
        pairs = _parse_colon_pairs(lines[0])
        if pairs:
            return pairs

    for line in lines:
        if _looks_like_df_header(line):
            continue
        if ":" in line:
            # First colon only so values like times with ":" still parse.
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key and value:
                values[key] = value
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            values[parts[0]] = parts[1]
    return values


def _count_status(rows: list[list[str]], headers: list[str], status_field: str = "status") -> str:
    if not rows:
        return "no data rows"
    try:
        idx = headers.index(status_field)
    except ValueError:
        return f"{len(rows)} item(s)"
    counts: dict[str, int] = {}
    for row in rows:
        if idx < len(row):
            status = row[idx].lower()
            counts[status] = counts.get(status, 0) + 1
    if not counts:
        return f"{len(rows)} item(s)"
    parts = [f"{count} {status}" for status, count in sorted(counts.items())]
    return ", ".join(parts)


def _parse_colon_pairs(line: str) -> dict[str, str]:
    parts = line.split(":")
    if len(parts) < 2:
        return {}
    if len(parts) % 2 == 0:
        keys = parts[0::2]
        values = parts[1::2]
        return dict(zip(keys, values, strict=False))
    return {}


def _summarize_showspace(output: str) -> str:
    capacity = parse_capacity_summary(output)
    if capacity:
        used = capacity["used_bytes"]
        total = capacity["total_bytes"]
        pct = capacity["used_pct"]
        name = capacity.get("name", "System")
        return (
            f"{name}: {_format_bytes(used)} used / {_format_bytes(total)} "
            f"({pct:.1f}% used, {_format_bytes(capacity['free_bytes'])} free)"
        )
    pool_summary = _summarize_mdisk_pools(output)
    if pool_summary and not pool_summary.lower().startswith("no "):
        return pool_summary
    return _summarize_table("Capacity", output, "CPG(s)")


def _summarize_statcpu(output: str) -> str:
    headers, rows = _parse_space_table(output)
    if not headers and ":" in output:
        headers, rows = _parse_colon_table(output)
    pct_columns = [
        idx
        for idx, header in enumerate(headers)
        if "pct" in header.lower() or "percent" in header.lower() or "%" in header
    ]
    if rows and pct_columns:
        values: list[float] = []
        for row in rows:
            for idx in pct_columns:
                if idx < len(row):
                    raw = row[idx].strip().replace("%", "")
                    try:
                        values.append(float(raw))
                    except ValueError:
                        continue
        if values:
            peak = max(values)
            avg = sum(values) / len(values)
            return f"CPU {avg:.1f}% avg, {peak:.1f}% peak across {len(rows)} sample(s)"
    lines = [line for line in output.splitlines() if line.strip()]
    if lines:
        return lines[-1][:72]
    return "CPU stats returned"


def _summarize_statcache(output: str) -> str:
    headers, rows = _parse_space_table(output)
    hit_columns = [
        idx
        for idx, header in enumerate(headers)
        if "hit" in header.lower() or "cache" in header.lower()
    ]
    if rows and hit_columns:
        for row in rows:
            for idx in hit_columns:
                if idx < len(row) and row[idx].strip():
                    return f"Cache: {row[idx].strip()}"
    return _summarize_table("Memory", output, "cache stat(s)")


def _summarize_comp_list(output: str) -> str:
    headers, rows = _parse_space_table(output)
    if not rows:
        headers, rows = _parse_colon_table(output)
    if rows:
        return f"{len(rows)} component(s), {_count_status(rows, headers)}"
    lines = [line for line in output.splitlines() if line.strip() and not line.startswith("-")]
    return f"{len(lines)} component line(s)" if lines else "no components listed"


def _summarize_space_show(output: str) -> str:
    capacity = parse_capacity_summary(output)
    if capacity:
        return (
            f"{capacity.get('name', 'System')}: {capacity['used_pct']:.1f}% used "
            f"({_format_bytes(capacity['used_bytes'])} / {_format_bytes(capacity['total_bytes'])})"
        )
    return _summarize_table("Capacity", output, "space row(s)")


def _summarize_lssi(output: str) -> str:
    capacity = parse_capacity_summary(output)
    if capacity:
        return (
            f"{capacity.get('name', 'DS8000')}: {capacity['used_pct']:.1f}% used "
            f"({_format_bytes(capacity['used_bytes'])} / {_format_bytes(capacity['total_bytes'])})"
        )
    kv = _parse_key_values(output)
    name = kv.get("id") or kv.get("name") or kv.get("storage_image_id", "")
    if name:
        return f"system {name}"
    return "DS8000 system info returned"


def parse_capacity_summary(output: str) -> dict[str, Any] | None:
    """Best-effort capacity parse for SVC, 3PAR, XIV, and DS8000 CLI output."""
    text = (output or "").strip()
    if not text:
        return None

    kv = _parse_key_values(text)
    lowered = {key.lower().replace(" ", "_"): value for key, value in kv.items()}
    # showsys -d labels capacities as MB without a unit suffix on each value.
    mb_keys = {
        "total_capacity",
        "allocated_capacity",
        "free_capacity",
        "failed_capacity",
    }
    text_lower = text.lower()
    default_unit = ""
    if "(mb)" in text_lower or "capacity (mb)" in text_lower:
        default_unit = "MB"
    elif "(mib)" in text_lower or "estimated(mib)" in text_lower:
        default_unit = "MB"

    def pick_size(*keys: str) -> float | None:
        for key in keys:
            for candidate, value in lowered.items():
                if key in candidate:
                    raw = str(value).strip()
                    if not raw:
                        continue
                    unit_hint = default_unit
                    if candidate in mb_keys or candidate.endswith("_mb"):
                        unit_hint = "MB"
                    if unit_hint and not re.search(r"[A-Za-z]", raw):
                        parsed = _parse_size_bytes(f"{raw}{unit_hint}")
                    else:
                        parsed = _parse_size_bytes(raw)
                    if parsed is not None:
                        return parsed
        return None

    total = pick_size(
        "physical_capacity",
        "total_capacity",
        "total_mdisk_capacity",
        "total_usable",
        "total",
    )
    free = pick_size(
        "physical_free_capacity",
        "free_capacity",
        "total_free_space",
        "rawfree",
        "usablefree",
        "free",
    )

    if total and free is not None:
        used = max(0.0, total - free)
        # Prefer allocated when both free and allocated are present (showsys -d).
        allocated = pick_size("allocated_capacity", "allocated")
        if allocated is not None and total:
            used = allocated
            free = max(0.0, total - used)
    else:
        used = pick_size(
            "used_capacity_after_reduction",
            "used_capacity",
            "total_used",
            "allocated_capacity",
            "allocated",
        )
        if total and used is None and free is not None:
            used = max(0.0, total - free)
        elif total and free is None and used is not None:
            free = max(0.0, total - used)
        elif used is not None and free is not None and not total:
            total = used + free

    headers, rows = _parse_any_table(text)
    if not rows:
        headers, rows = _parse_space_table(text)
        if not rows:
            headers, rows = _parse_colon_table(text)

    name = kv.get("name") or kv.get("System Name") or kv.get("id") or "System"
    if rows and headers and (not total or free is None):
        pct_idx = next(
            (idx for idx, header in enumerate(headers) if "usedpct" in header.lower().replace(" ", "")),
            None,
        )
        if pct_idx is None:
            pct_idx = next(
                (idx for idx, header in enumerate(headers) if "used" in header.lower() and "%" in header),
                None,
            )
        total_idx = next(
            (
                idx
                for idx, header in enumerate(headers)
                if header.lower() in {"total", "capacity", "totalcapacity", "usr_total_mb"}
            ),
            None,
        )
        used_idx = next(
            (
                idx
                for idx, header in enumerate(headers)
                if header.lower() in {"used", "usedcapacity", "allocated", "usr_used_mb"}
            ),
            None,
        )
        free_idx = next(
            (
                idx
                for idx, header in enumerate(headers)
                if header.lower() in {"free", "rawfree", "usablefree", "free_capacity"}
            ),
            None,
        )
        if rows and (total_idx is not None or free_idx is not None or used_idx is not None):
            best_row = rows[0]
            def cell_size(idx: int | None) -> float | None:
                if idx is None or idx >= len(best_row):
                    return None
                raw = best_row[idx].strip()
                header = headers[idx] if idx < len(headers) else ""
                if header.lower().endswith("_mb") or "(mib)" in text_lower or default_unit == "MB":
                    if raw and not re.search(r"[A-Za-z]", raw):
                        return _parse_size_bytes(f"{raw}MB")
                return _parse_size_bytes(raw)

            row_total = cell_size(total_idx)
            row_used = cell_size(used_idx)
            row_free = cell_size(free_idx)
            if row_total and row_free is not None and used is None:
                total = total or row_total
                free = free if free is not None else row_free
                used = max(0.0, total - free)
            elif row_total and row_used is not None:
                total = total or row_total
                used = used if used is not None else row_used
                free = free if free is not None else max(0.0, total - used)
            elif row_free is not None and row_total:
                total = total or row_total
                free = free if free is not None else row_free
                used = used if used is not None else max(0.0, total - free)

            if pct_idx is not None and used is None and total:
                try:
                    pct = float(best_row[pct_idx].replace("%", "").strip())
                    used = total * (pct / 100.0)
                    free = max(0.0, total - used)
                except ValueError:
                    pass

    if not total or used is None or free is None:
        return None

    used_pct = (used / total * 100.0) if total else 0.0
    return {
        "name": name,
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "used_pct": round(used_pct, 1),
        "raw": kv,
    }


def _summarize_lssystem(output: str) -> str:
    kv = _parse_key_values(output)
    capacity = parse_capacity_summary(output)
    total_raw = kv.get("physical_capacity") or kv.get("total_mdisk_capacity") or ""
    free_raw = kv.get("physical_free_capacity") or kv.get("total_free_space") or ""
    if capacity and (total_raw or free_raw):
        used_pct = capacity["used_pct"]
        parts = []
        if total_raw:
            parts.append(f"Cap: {total_raw}")
        if free_raw:
            parts.append(f"Free: {free_raw}")
        parts.append(f"Used: {used_pct:.1f}%")
        return ", ".join(parts)
    if capacity:
        return (
            f"{capacity.get('name', 'System')}: {_format_bytes(capacity['used_bytes'])} used / "
            f"{_format_bytes(capacity['total_bytes'])} ({capacity['used_pct']:.1f}% used, "
            f"{_format_bytes(capacity['free_bytes'])} free)"
        )
    return "system info returned"


def _pool_capacity_lines(headers: list[str], rows: list[list[str]]) -> list[str]:
    if not headers or not rows:
        return []

    def col_idx(*names: str) -> int | None:
        lowered = [header.lower() for header in headers]
        for name in names:
            target = name.lower()
            for idx, header in enumerate(lowered):
                if header == target:
                    return idx
        return None

    name_idx = col_idx("name")
    cap_idx = col_idx("capacity")
    free_idx = col_idx("free_capacity", "free")
    used_idx = col_idx("used_capacity")

    lines: list[str] = []
    for row in rows:
        name = row[name_idx] if name_idx is not None and name_idx < len(row) else "Pool"
        cap_bytes = (
            _parse_size_bytes(row[cap_idx]) if cap_idx is not None and cap_idx < len(row) else None
        )
        free_bytes = (
            _parse_size_bytes(row[free_idx]) if free_idx is not None and free_idx < len(row) else None
        )
        used_bytes = (
            _parse_size_bytes(row[used_idx]) if used_idx is not None and used_idx < len(row) else None
        )
        if cap_bytes and free_bytes is not None:
            used_bytes = used_bytes if used_bytes is not None else max(0.0, cap_bytes - free_bytes)
            pct = used_bytes / cap_bytes * 100.0 if cap_bytes else 0.0
            cap_label = row[cap_idx] if cap_idx is not None and cap_idx < len(row) else _format_bytes(cap_bytes)
            free_label = row[free_idx] if free_idx is not None and free_idx < len(row) else _format_bytes(free_bytes)
            lines.append(f"{name}: {pct:.1f}% used, {free_label} free of {cap_label}")
        elif cap_bytes:
            cap_label = row[cap_idx] if cap_idx is not None and cap_idx < len(row) else _format_bytes(cap_bytes)
            lines.append(f"{name}: {cap_label}")
    return lines


def parse_pool_capacity_rows(output: str) -> list[dict[str, Any]]:
    """Parse lsmdiskgrp / pool / HPE CPG table output into capacity dicts."""
    headers, rows = _parse_any_table(output)
    if not headers or not rows:
        return []

    pools: list[dict[str, Any]] = []
    for row in rows:
        record: dict[str, str] = {}
        for index, header in enumerate(headers):
            record[header] = row[index] if index < len(row) else ""

        name = (
            _record_get(record, "name", "CPG", "PoolName", "Name")
            or "Pool"
        )
        cap_bytes = _parse_sized_field(
            record,
            "capacity",
            "Total",
            "Usr_Total_MB",
            "total_mb",
            "Size",
        )
        free_bytes = _parse_sized_field(
            record,
            "free_capacity",
            "Free",
            "Usr_Free_MB",
            "free_mb",
        )
        used_bytes = _parse_sized_field(
            record,
            "used_capacity",
            "Usr_Used_MB",
            "used_mb",
            "Used",
        )

        if cap_bytes and free_bytes is not None:
            used_bytes = used_bytes if used_bytes is not None else max(0.0, cap_bytes - free_bytes)
        elif cap_bytes and used_bytes is not None:
            free_bytes = max(0.0, cap_bytes - used_bytes)
        elif not cap_bytes:
            continue

        if cap_bytes is None or free_bytes is None or used_bytes is None:
            continue

        used_pct = (used_bytes / cap_bytes * 100.0) if cap_bytes else 0.0
        pct_raw = _record_get(record, "Usr_Used_Perc", "Used%", "use%", "used_pct")
        if pct_raw:
            try:
                used_pct = float(pct_raw.replace("%", "").strip())
            except ValueError:
                pass
        pools.append(
            {
                "name": name,
                "total_bytes": cap_bytes,
                "used_bytes": used_bytes,
                "free_bytes": free_bytes,
                "used_pct": round(used_pct, 1),
                "raw": record,
            }
        )
    return pools


def _summarize_mdisk_pools(output: str) -> str:
    pools = parse_pool_capacity_rows(output)
    if pools:
        if len(pools) == 1:
            pool = pools[0]
            raw = pool.get("raw", {})
            cap = raw.get("capacity") or _format_bytes(pool["total_bytes"])
            free = raw.get("free_capacity") or _format_bytes(pool["free_bytes"])
            return f"Cap: {cap}, Free: {free}, Used: {pool['used_pct']:.1f}%"

        summaries: list[str] = []
        for pool in pools[:3]:
            raw = pool.get("raw", {})
            name = pool["name"]
            cap = raw.get("capacity") or _format_bytes(pool["total_bytes"])
            free = raw.get("free_capacity") or _format_bytes(pool["free_bytes"])
            summaries.append(f"{name}: Cap {cap}, Free {free}, Used {pool['used_pct']:.1f}%")
        result = "; ".join(summaries)
        if len(pools) > 3:
            result += f" (+{len(pools) - 3} more)"
        return result

    headers, rows = _parse_colon_table(output)
    if not rows:
        headers, rows = _parse_space_table(output)
    lines = _pool_capacity_lines(headers, rows)
    if lines:
        if len(lines) == 1:
            return lines[0]
        preview = "; ".join(lines[:3])
        if len(lines) > 3:
            preview += f" (+{len(lines) - 3} more)"
        return preview
    return _summarize_table("Capacity", output, "pool(s)")


def _parse_node_table(output: str) -> tuple[list[str], list[list[str]]]:
    headers, rows = _parse_colon_table(output)
    if rows:
        return headers, rows
    headers, rows = _parse_space_table(output)
    if rows:
        return headers, rows

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    parsed_rows: list[list[str]] = []
    for line in lines:
        if line.count(":") < 3:
            continue
        parts = line.split(":")
        if parts and parts[0].strip().isdigit():
            parsed_rows.append(parts)
            continue
        if _looks_like_header(line):
            continue
        if parts:
            parsed_rows.append(parts)

    if not parsed_rows:
        return [], []

    width = max(len(row) for row in parsed_rows)
    headers = [f"field_{index}" for index in range(width)]
    for index, name in enumerate(
        ("id", "name", "label", "WWNN", "status", "config_node", "IO_group_id", "IO_group_name")
    ):
        if index < len(headers):
            headers[index] = name
    return headers, parsed_rows


def _summarize_nodes(output: str) -> str:
    headers, rows = _parse_node_table(output)
    if rows:
        return f"{len(rows)} node(s), {_count_status(rows, headers)}"
    if output.strip().lower() in {"ok", ""}:
        return "OK"
    return "no node rows returned"


def _summarize_controllers(output: str, *, command: str = "") -> str:
    text = (output or "").strip()
    if not text:
        if "lscontroller" in command.lower():
            return "0 external controllers (none attached)"
        return "no controller data returned"
    headers, rows = _parse_colon_table(text)
    if not rows:
        headers, rows = _parse_space_table(text)
    if rows:
        return f"{len(rows)} controller(s), {_count_status(rows, headers)}"
    if text.lower() == "ok":
        return "OK"
    if _looks_like_header(text.splitlines()[0]):
        return "0 controller(s)"
    return text.splitlines()[0][:60]


def _summarize_alerts(output: str) -> str:
    headers, rows = _parse_colon_table(output)
    if not rows:
        lines = [line for line in output.splitlines() if line.strip()]
        data_lines = [line for line in lines if not _looks_like_header(line)]
        count = len(data_lines)
    else:
        count = len(rows)
    if count == 0:
        return "0 active alerts"
    return f"{count} active alert(s)"


def _summarize_table(label: str, output: str, item_name: str) -> str:
    headers, rows = _parse_any_table(output)
    if rows:
        return f"{len(rows)} {item_name}, {_count_status(rows, headers)}"
    first = output.splitlines()[0].strip() if output else ""
    if first and not _looks_like_header(first):
        return first[:60]
    return f"no {item_name} rows"


def _summarize_systemctl_failed(output: str) -> str:
    text = (output or "").strip()
    if not text:
        return "No systemd failed-unit data"
    lower = text.lower()
    if "0 loaded units listed" in lower:
        return "No failed systemd units"
    units: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("UNIT"):
            continue
        if "loaded units listed" in stripped.lower():
            continue
        if "failed" in stripped.lower():
            units.append(stripped.split()[0] if stripped.split() else stripped[:40])
    if units:
        if len(units) == 1:
            return f"1 failed unit: {units[0]}"
        preview = ", ".join(units[:3])
        if len(units) > 3:
            preview += f" (+{len(units) - 3} more)"
        return f"{len(units)} failed units: {preview}"
    return text.splitlines()[0][:72] if text.splitlines() else "systemctl output returned"


def _summarize_linux_memory(output: str) -> str:
    for line in output.splitlines():
        if line.lower().startswith("mem:"):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    total = float(parts[1].replace("Mi", "").replace("Gi", ""))
                    used = float(parts[2].replace("Mi", "").replace("Gi", ""))
                    if total > 0:
                        return f"Memory {used / total * 100:.1f}% used ({used:.0f} / {total:.0f})"
                except ValueError:
                    pass
            return line.strip()[:72]
    return output.splitlines()[0][:72] if output.strip() else "memory info returned"


def _summarize_linux_disk(output: str) -> str:
    headers, rows = _parse_df_table(output)
    if rows:
        if len(rows) == 1:
            row = rows[0]
            mount = row[0] if row else "disk"
            use_pct = row[1] if len(row) > 1 else ""
            return f"{mount} {use_pct}".strip()
        return f"{len(rows)} filesystem(s)"
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for line in lines:
        if line.startswith("/") or " / " in line or line.endswith("%"):
            return line[:72]
    return lines[0][:72] if lines else "disk info returned"


def summarize_command_output(label: str, command: str, output: str) -> str:
    text = (output or "").strip()
    label_lower = label.lower()
    command_lower = command.lower()

    if not text:
        if "health - controllers" in label_lower:
            if "lscontroller" in command_lower:
                return "0 external controllers (none attached)"
            return "No controller data returned"
        return "no output"

    if "lssystem" in command_lower or "capacity - system" in label_lower:
        return _summarize_lssystem(text)
    if "lsmdiskgrp" in command_lower or "capacity - pools" in label_lower:
        return _summarize_mdisk_pools(text)
    if "pool_list" in command_lower or "lsextpool" in command_lower:
        return _summarize_mdisk_pools(text)
    if "showspace" in command_lower or "showsys" in command_lower:
        return _summarize_showspace(text)
    if "showcpg" in command_lower or "capacity - cpg" in label_lower:
        return _summarize_mdisk_pools(text)
    if "lsnode" in command_lower and (
        "health - nodes" in label_lower
        or "health - controllers" in label_lower
        or "cpu - node" in label_lower
    ):
        return _summarize_nodes(text)
    if "statcpu" in command_lower or ("cpu -" in label_lower and "lsnode" not in command_lower):
        return _summarize_statcpu(text)
    if "statcache" in command_lower or "memory - cache" in label_lower:
        return _summarize_statcache(text)
    if "comp_list" in command_lower or "health - components" in label_lower:
        return _summarize_comp_list(text)
    if "space_show" in command_lower:
        return _summarize_space_show(text)
    if "lssi" in command_lower or "dscli lssi" in command_lower:
        return _summarize_lssi(text)
    if "checkhealth" in command_lower or "health - overall" in label_lower:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return "checkhealth returned"
        summary = lines[0]
        if len(lines) > 1:
            summary += f" (+{len(lines) - 1} more)"
        return summary[:72]
    if "shownode" in command_lower or "health - nodes" in label_lower:
        return _summarize_nodes(text)
    if "showalert" in command_lower or "health - alerts" in label_lower:
        return _summarize_alerts(text)
    if "showpd" in command_lower or "health - disks" in label_lower:
        return _summarize_table(label, text, "disk(s)")
    if "showbattery" in command_lower or "health - battery" in label_lower:
        return _summarize_table(label, text, "battery row(s)")
    if "systemctl" in command_lower and "failed" in command_lower:
        return _summarize_systemctl_failed(text)
    if "health - failed units" in label_lower:
        return _summarize_systemctl_failed(text)
    if "vultr-cli instance" in command_lower or "health - instance" in label_lower:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return lines[0][:72] if lines else "instance info returned"
    if command_lower.startswith("free") or "memory -" in label_lower and "mem:" in text.lower():
        return _summarize_linux_memory(text)
    if command_lower.startswith("df") or "capacity -" in label_lower and "disk" in label_lower:
        return _summarize_linux_disk(text)
    if "capacity - all filesystems" in label_lower:
        return _summarize_linux_disk(text)
    if "vol_list" in command_lower or "capacity - volumes" in label_lower:
        return _summarize_table(label, text, "volume(s)")
    if "event_list" in command_lower or "health - events" in label_lower:
        return _summarize_alerts(text)
    if "xiv_top" in command_lower:
        return _summarize_statcpu(text)
    if "lsextpool" in command_lower or "capacity - ext pools" in label_lower:
        return _summarize_table(label, text, "pool(s)")
    if "lsnodecanister" in command_lower or "health - controllers" in label_lower:
        return _summarize_nodes(text)
    if "lscontroller" in command_lower:
        return _summarize_controllers(text, command=command)
    if "lsnode" in command_lower or "health - nodes" in label_lower:
        return _summarize_nodes(text)
    if "lseventlog" in command_lower or "health - alerts" in label_lower:
        return _summarize_alerts(text)
    if "lsmdisk" in command_lower or "capacity - mdisk" in label_lower:
        return _summarize_table(label, text, "mdisk(s)")
    if "lsvdisk" in command_lower or "memory - volumes" in label_lower:
        return _summarize_table(label, text, "volume(s)")
    if "lssevdiskcopy" in command_lower or "memory - copies" in label_lower:
        return _summarize_table(label, text, "copy record(s)")

    lines = [line for line in text.splitlines() if line.strip()]
    data_lines = [line for line in lines if not _looks_like_header(line)]
    if data_lines:
        summary = data_lines[0]
        if len(data_lines) > 1:
            summary += f" (+{len(data_lines) - 1} more)"
        if len(summary) > 72:
            summary = summary[:69] + "..."
        return summary

    first = lines[0] if lines else "OK"
    if len(first) > 72:
        first = first[:69] + "..."
    return first


_PRIORITY_FIELDS: dict[str, list[str]] = {
    "lssystem": [
        "name",
        "id",
        "code_level",
        "physical_capacity",
        "physical_free_capacity",
        "used_capacity_after_reduction",
        "used_capacity_before_reduction",
        "total_mdisk_capacity",
        "total_free_space",
        "total_used_capacity",
        "total_vdiskcopy_capacity",
        "compression_active",
    ],
    "lsnode": ["id", "name", "status", "config_node", "IO_group_name", "WWNN"],
    "lsnodecanister": ["id", "name", "status", "config_node", "IO_group_name", "WWNN"],
    "lscontroller": ["id", "name", "status", "WWNN", "node_id", "node_name"],
    "lseventlog": ["last_timestamp", "object_type", "object_name", "message", "status"],
    "lsmdisk": ["id", "name", "status", "mode", "capacity", "mdisk_grp_name"],
    "lsmdiskgrp": [
        "id",
        "name",
        "status",
        "mdisk_count",
        "vdisk_count",
        "capacity",
        "free_capacity",
        "used_capacity",
    ],
    "lsvdisk": ["id", "name", "status", "capacity", "used_capacity", "IO_group_name", "mdisk_grp_name"],
    "lssevdiskcopy": ["vdisk_id", "vdisk_name", "copy_id", "status", "used_capacity", "real_capacity"],
}


def _command_family(command: str) -> str:
    command_lower = command.lower()
    for family in _PRIORITY_FIELDS:
        if family in command_lower:
            return family
    return ""


def _pick_columns(headers: list[str], family: str) -> list[str]:
    if not family or family not in _PRIORITY_FIELDS:
        return headers
    preferred = _PRIORITY_FIELDS[family]
    picked = [column for column in preferred if column in headers]
    if picked:
        return picked
    return headers[: min(8, len(headers))]


def _html_table(
    headers: list[str],
    rows: list[list[str]],
    family: str = "",
    *,
    table_class: str = "data-table",
) -> str:
    columns = _pick_columns(headers, family)
    index_map = [headers.index(column) for column in columns]
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = []
        for idx in index_map:
            value = row[idx] if idx < len(row) else ""
            cells.append(f"<td>{html.escape(value)}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        f'<div class="table-wrap"><table class="{table_class}"><thead><tr>'
        f"{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>"
    )


def _html_key_value_table(values: dict[str, str], family: str = "") -> str:
    if family == "lssystem":
        keys = [key for key in _PRIORITY_FIELDS["lssystem"] if key in values]
        extra = [key for key in values if key not in keys]
        ordered = keys + extra
    else:
        ordered = list(values.keys())
    rows = "".join(
        f"<tr><th>{html.escape(key)}</th><td>{html.escape(values[key])}</td></tr>"
        for key in ordered
        if values.get(key, "") != ""
    )
    return (
        '<div class="table-wrap"><table class="data-table kv-table"><tbody>'
        f"{rows}</tbody></table></div>"
    )


def format_command_output_html(label: str, command: str, output: str) -> str:
    text = (output or "").strip()
    if not text:
        return '<p class="sub">(no output)</p>'

    summary = summarize_command_output(label, command, text)
    summary_html = f'<p class="cmd-summary">{html.escape(summary)}</p>'
    family = _command_family(command)
    label_lower = label.lower()
    command_lower = command.lower()
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if command_lower.startswith("df") or "capacity - all filesystems" in label_lower:
        headers, rows = _parse_df_table(text)
        if headers and rows:
            return summary_html + _html_table(headers, rows, family="", table_class="data-table df-table")

    kv = _parse_key_values(text)
    if kv and len(kv) >= 2 and family in {"", "lssystem"}:
        return summary_html + _html_key_value_table(kv, family or "lssystem")

    if len(lines) == 1 and lines[0].count(":") >= 3:
        pair_kv = _parse_colon_pairs(lines[0])
        if pair_kv:
            return summary_html + _html_key_value_table(pair_kv, family)

    headers, rows = _parse_colon_table(text)
    if headers and rows:
        normalized_rows = []
        for row in rows:
            if len(row) < len(headers):
                row = row + [""] * (len(headers) - len(row))
            elif len(row) > len(headers):
                row = row[: len(headers)]
            normalized_rows.append(row)
        return summary_html + _html_table(headers, normalized_rows, family)

    headers, rows = _parse_space_table(text)
    if headers and rows:
        return summary_html + _html_table(headers, rows, family)

    if kv:
        return summary_html + _html_key_value_table(kv, family)

    return summary_html + f'<pre class="raw-output">{html.escape(text)}</pre>'
