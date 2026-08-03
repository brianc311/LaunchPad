import html
import re
from typing import Any

from launchpad.flashsystem_parse import (
    _command_family,
    _format_bytes,
    _html_key_value_table,
    _html_table,
    _parse_colon_pairs,
    _parse_colon_table,
    _parse_df_table,
    _parse_key_values,
    _parse_size_bytes,
    _parse_space_table,
    format_command_output_html,
    parse_capacity_summary,
    parse_pool_capacity_rows,
)

_GOOD_STATUS = frozenset({"online", "ok", "normal", "active", "yes"})
_BAD_STATUS = frozenset(
    {"offline", "degraded", "failed", "error", "down", "missing", "inactive", "fault"}
)


def _status_issue(
    category: str,
    name: str,
    item_name: str,
    status: str,
    *,
    server: str,
) -> dict[str, Any] | None:
    lowered = (status or "").lower()
    if not lowered or lowered in _GOOD_STATUS:
        return None
    severity = "critical" if lowered in _BAD_STATUS else "warn"
    return {
        "severity": severity,
        "category": category,
        "message": f"{item_name} {name} is {status}",
        "server": server,
    }


def _find_result(
    command_results: list[dict[str, Any]] | None, *needles: str
) -> dict[str, Any] | None:
    if not command_results:
        return None
    for item in command_results:
        haystack = f"{item.get('label', '')} {item.get('command', '')}".lower()
        if any(needle in haystack for needle in needles):
            return item
    return None


def _looks_like_hpe_checkhealth(output: str) -> bool:
    lines = [line.strip() for line in (output or "").splitlines() if line.strip()]
    if not lines:
        return False
    checking = sum(1 for line in lines if line.lower().startswith("checking "))
    if checking == 0:
        return False
    if any(
        token in (output or "").lower()
        for token in ("total capacity", "usr_total", ",name,", "free capacity")
    ):
        return False
    return checking >= 1 and len(lines) <= 12


def _result_output(item: dict[str, Any] | None) -> str:
    if not item or item.get("error"):
        return ""
    return (item.get("output") or "").strip()


def _capacity_result_output(item: dict[str, Any] | None) -> str:
    """Like ``_result_output`` but drops checkhealth bleed mistaken for capacity."""
    text = _result_output(item)
    if text and _looks_like_hpe_checkhealth(text):
        return ""
    return text


def _find_pool_capacity_result(
    command_results: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Prefer CPG/pool commands over generic showspace system estimates."""
    if not command_results:
        return None
    for needles in (
        ("showcpg",),
        ("showspace -cpg", "capacity - cpg"),
        ("lsmdiskgrp", "capacity - pools"),
        ("lsextpool", "pool_list", "capacity - ext pools"),
        (
            "storage aggregate",
            "isi storagepool",
            "storage_container",
            "stor/prov/pool",
            "storagepool -list",
            "symcfg list -pool",
            "capacity - usage",
            "ud-ssd-space",
        ),
        ("showspace",),
    ):
        item = _find_result(command_results, *needles)
        if _result_output(item):
            return item
    return None


def capacity_summary_from_pools(
    pools: list[dict[str, Any]] | None,
    *,
    name: str = "All CPGs",
) -> dict[str, Any] | None:
    """Roll CPG/pool rows into one system capacity summary for Excel/UI."""
    if not pools:
        return None
    total = 0.0
    used = 0.0
    free = 0.0
    for pool in pools:
        pool_name = str(pool.get("name") or "").strip().lower()
        if pool_name in {"total", "totals", "sum"}:
            continue
        total += float(pool.get("total_bytes") or 0)
        used += float(pool.get("used_bytes") or 0)
        free += float(pool.get("free_bytes") or 0)
    if total <= 0:
        return None
    if free <= 0 and used <= total:
        free = max(0.0, total - used)
    used_pct = (used / total * 100.0) if total else 0.0
    return {
        "name": name,
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "used_pct": round(used_pct, 1),
        "raw": {},
    }


def pool_capacity_from_commands(
    command_results: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Parsed pool rows from SSH command output (lsmdiskgrp, capacity - pools, etc.)."""
    pools_output = _capacity_result_output(_find_pool_capacity_result(command_results))
    return parse_pool_capacity_rows(pools_output)


def _table_rows(output: str) -> tuple[list[str], list[list[str]]]:
    headers, rows = _parse_colon_table(output)
    if rows:
        return headers, rows
    return _parse_space_table(output)


def _row_map(headers: list[str], row: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for index, header in enumerate(headers):
        values[header] = row[index] if index < len(row) else ""
    return values


def _parse_system_capacity(output: str) -> dict[str, Any] | None:
    return parse_capacity_summary(output)


def _bar_html(label: str, pct: float, subtitle: str) -> str:
    tone = "#ff6b00"
    if pct >= 90:
        tone = "#ef4444"
    elif pct >= 80:
        tone = "#f59e0b"
    clamped = max(0.0, min(100.0, pct))
    return (
        f'<div class="metric"><div class="metric-head"><span>{html.escape(label)}</span>'
        f"<span>{clamped:.1f}%</span></div>"
        f'<div class="bar"><div class="fill" style="width:{clamped:.1f}%;background:{tone};"></div></div>'
        f'<div class="sub">{html.escape(subtitle)}</div></div>'
    )


def _capacity_detail_rows(raw: dict[str, str]) -> str:
    skip = frozenset({"capacity", "free_capacity", "used_capacity", "name"})
    return "".join(
        f"<tr><th>{html.escape(key)}</th><td>{html.escape(str(value))}</td></tr>"
        for key, value in raw.items()
        if str(value).strip() and key.lower() not in skip
    )


def _format_capacity_block(
    capacity: dict[str, Any],
    *,
    summary_suffix: str = "storage capacity",
    bar_label: str = "Storage utilization",
    section_class: str = "capacity-section",
) -> str:
    used = capacity["used_bytes"]
    total = capacity["total_bytes"]
    free = capacity["free_bytes"]
    pct = capacity["used_pct"]
    raw = capacity.get("raw", {})
    kv_rows = _capacity_detail_rows(raw) if isinstance(raw, dict) else ""
    detail_html = ""
    if kv_rows:
        detail_html = (
            '<div class="capacity-detail-section">'
            '<div class="table-wrap"><table class="data-table kv-table"><tbody>'
            f"{kv_rows}</tbody></table></div>"
            "</div>"
        )
    return (
        f'<section class="{section_class}">'
        f'<p class="cmd-summary">{html.escape(capacity["name"])} {summary_suffix}</p>'
        f'{_bar_html(bar_label, pct, f"{_format_bytes(used)} used of {_format_bytes(total)}")}'
        '<div class="capacity-grid">'
        f'<article class="card"><h3>Total</h3><div class="stat">{html.escape(_format_bytes(total))}</div></article>'
        f'<article class="card"><h3>Used</h3><div class="stat">{html.escape(_format_bytes(used))}</div>'
        f'<div class="stat-label">{pct:.1f}%</div></article>'
        f'<article class="card"><h3>Free</h3><div class="stat">{html.escape(_format_bytes(free))}</div>'
        f'<div class="stat-label">{(100 - pct):.1f}% available</div></article>'
        "</div>"
        f"{detail_html}"
        "</section>"
    )


def format_capacity_popup_html(capacity: dict[str, Any]) -> str:
    return _format_capacity_block(
        capacity,
        bar_label="System utilization",
        section_class="capacity-section capacity-system-block",
    )


def format_pools_capacity_html(pools: list[dict[str, Any]]) -> str:
    if not pools:
        return ""
    blocks = [
        _format_capacity_block(
            pool,
            bar_label="Pool utilization",
            section_class="capacity-section capacity-pool-block",
        )
        for pool in pools
    ]
    return '<div class="capacity-pools-wrap">' + "".join(blocks) + "</div>"


def format_capacity_report_html(
    system_capacity: dict[str, Any] | None,
    pools_output: str = "",
) -> str:
    parts: list[str] = []
    if system_capacity:
        parts.append(format_capacity_popup_html(system_capacity))
    pools = parse_pool_capacity_rows(pools_output) if pools_output.strip() else []
    if pools:
        parts.append(format_pools_capacity_html(pools))
    return "".join(parts)


def _parse_root_disk_capacity(output: str) -> dict[str, Any] | None:
    text = (output or "").strip()
    if not text:
        return None
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*%\s*used\s*\(([^/]+?)\s*/\s*([^)]+)\)",
        text,
        re.IGNORECASE,
    )
    if match:
        pct = float(match.group(1))
        used_label = match.group(2).strip()
        total_label = match.group(3).strip()

        def human_bytes(label: str) -> int:
            parsed = _parse_size_bytes(label)
            if parsed:
                return int(parsed)
            short = re.match(r"(\d+(?:\.\d+)?)\s*([TGMK])", label.strip(), re.IGNORECASE)
            if not short:
                return 0
            amount = float(short.group(1))
            unit = short.group(2).upper()
            multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
            return int(amount * multipliers.get(unit, 1))

        used = human_bytes(used_label)
        total = human_bytes(total_label)
        if not total and used and pct:
            total = int(round(used / (pct / 100.0)))
        if not total:
            return {
                "name": "Root disk",
                "used_bytes": used,
                "total_bytes": 0,
                "free_bytes": 0,
                "used_pct": pct,
                "raw": {"used": used_label, "total": total_label},
            }
        if not used:
            used = int(round(total * pct / 100.0))
        free = max(0, total - used)
        return {
            "name": "Root disk",
            "used_bytes": used,
            "total_bytes": total,
            "free_bytes": free,
            "used_pct": pct,
            "raw": {"used": used_label, "total": total_label},
        }

    simple = re.search(r"(?im)^(\d+(?:\.\d+)?)\s*%\s*(?:used)?\b", text)
    if simple:
        return {
            "name": "Root disk",
            "used_bytes": 0,
            "total_bytes": 0,
            "free_bytes": 0,
            "used_pct": float(simple.group(1)),
            "raw": {},
        }

    headers, rows = _parse_df_table(text)
    if not headers or not rows:
        return None

    lowered = [h.lower() for h in headers]

    def col_exact(*names: str) -> int | None:
        for name in names:
            for index, header in enumerate(lowered):
                if header == name:
                    return index
        return None

    def col_contains(*names: str) -> int | None:
        for name in names:
            for index, header in enumerate(lowered):
                if name in header:
                    return index
        return None

    mount_idx = col_exact("mounted on", "target") or col_contains("mounted", "target")
    # Prefer Use% / pcent — never the "Used" size column.
    pct_idx = None
    for index, header in enumerate(lowered):
        compact = header.replace(" ", "")
        if compact in {"use%", "pcent", "capacity"} or compact.endswith("use%"):
            pct_idx = index
            break
    size_idx = col_exact("size") or col_contains("size")
    used_idx = None
    for index, header in enumerate(lowered):
        if header == "used" or (header.startswith("used") and "%" not in header):
            used_idx = index
            break
    avail_idx = col_exact("avail", "available", "free") or col_contains(
        "avail", "available", "free"
    )

    chosen: list[str] | None = None
    for row in rows:
        mount = (row[mount_idx] if mount_idx is not None and mount_idx < len(row) else "").strip()
        if mount in {"/", "/root"}:
            chosen = row
            break
    if chosen is None:
        chosen = rows[0]

    pct_text = chosen[pct_idx] if pct_idx is not None and pct_idx < len(chosen) else ""
    pct_match = re.search(r"(\d+(?:\.\d+)?)", pct_text or "")
    if not pct_match:
        return None
    pct = float(pct_match.group(1))

    def size_at(index: int | None) -> int:
        if index is None or index >= len(chosen):
            return 0
        parsed = _parse_size_bytes(chosen[index])
        if parsed:
            return int(parsed)
        short = re.match(r"(\d+(?:\.\d+)?)\s*([TGMK])B?", chosen[index].strip(), re.IGNORECASE)
        if not short:
            return 0
        amount = float(short.group(1))
        unit = short.group(2).upper()
        multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
        return int(amount * multipliers.get(unit, 1))

    total = size_at(size_idx)
    used = size_at(used_idx)
    free = size_at(avail_idx)
    if not total and used and pct:
        total = int(round(used / (pct / 100.0)))
    if not used and total:
        used = int(round(total * pct / 100.0))
    if not free and total:
        free = max(0, total - used)
    return {
        "name": "Root disk",
        "used_bytes": used,
        "total_bytes": total,
        "free_bytes": free,
        "used_pct": pct,
        "raw": {},
    }


def _capacity_from_metrics(metrics: dict[str, Any]) -> dict[str, Any] | None:
    total = int(metrics.get("disk_total") or 0)
    used = int(metrics.get("disk_used") or 0)
    if total <= 0:
        return None
    free = int(metrics.get("disk_free") or max(0, total - used))
    pct = used / total * 100.0 if total else 0.0
    return {
        "name": metrics.get("hostname") or "Root disk",
        "used_bytes": used,
        "total_bytes": total,
        "free_bytes": free,
        "used_pct": pct,
        "raw": {},
    }


def _parse_pct_from_text(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _analyze_linux_command_thresholds(
    issues: list[dict[str, Any]],
    *,
    server: str,
    command_results: list[dict[str, Any]],
) -> None:
    cpu_output = _result_output(_find_result(command_results, "cpu - usage"))
    if cpu_output:
        cpu_pct = _parse_pct_from_text(cpu_output)
        if cpu_pct is not None and cpu_pct >= 80:
            issues.append(
                {
                    "severity": "critical" if cpu_pct >= 90 else "warn",
                    "category": "cpu",
                    "message": f"CPU high at {cpu_pct:.1f}%",
                    "server": server,
                }
            )

    mem_output = _result_output(_find_result(command_results, "memory - usage"))
    if mem_output:
        mem_pct = _parse_pct_from_text(mem_output)
        if mem_pct is not None and mem_pct >= 80:
            issues.append(
                {
                    "severity": "critical" if mem_pct >= 90 else "warn",
                    "category": "memory",
                    "message": f"Memory use at {mem_pct:.1f}%",
                    "server": server,
                }
            )

    disk_output = _result_output(
        _find_result(command_results, "capacity - root disk", "df -h /")
    )
    if disk_output:
        disk_cap = _parse_root_disk_capacity(disk_output)
        if disk_cap and disk_cap["used_pct"] >= 80:
            issues.append(
                {
                    "severity": "critical" if disk_cap["used_pct"] >= 90 else "warn",
                    "category": "capacity",
                    "message": (
                        f"Root disk at {disk_cap['used_pct']:.1f}% "
                        f"({_format_bytes(disk_cap['used_bytes'])} used / "
                        f"{_format_bytes(disk_cap['total_bytes'])})"
                    ),
                    "server": server,
                }
            )

    failed_output = _result_output(
        _find_result(command_results, "health - failed units", "systemctl")
    )
    if failed_output and "0 loaded units listed" not in failed_output.lower():
        failed_units: list[str] = []
        for line in failed_output.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("UNIT"):
                continue
            if "loaded units listed" in stripped.lower():
                continue
            if "failed" in stripped.lower():
                token = stripped.split()[0]
                failed_units.append(token)
        if failed_units:
            preview = ", ".join(failed_units[:3])
            if len(failed_units) > 3:
                preview += f" (+{len(failed_units) - 3} more)"
            issues.append(
                {
                    "severity": "critical",
                    "category": "health",
                    "message": f"{len(failed_units)} failed systemd unit(s): {preview}",
                    "server": server,
                }
            )


def format_preset_capacity_fallback_html(
    command_results: list[dict[str, Any]] | None,
) -> str:
    if not command_results:
        return ""
    parts: list[str] = []
    for item in command_results:
        label = (item.get("label") or "").lower()
        if item.get("error"):
            continue
        if not any(
            token in label
            for token in ("capacity", "bandwidth", "block storage", "snapshot", "instance")
        ):
            continue
        output = (item.get("output") or "").strip()
        if not output:
            continue
        if _looks_like_hpe_checkhealth(output):
            continue
        body = item.get("output_html") or format_command_output_html(
            item.get("label", ""),
            item.get("command", ""),
            output,
        )
        parts.append(f'<section class="capacity-section">{body}</section>')
    return "".join(parts)


def _linux_summary_lines(command_results: list[dict[str, Any]] | None) -> list[str]:
    if not command_results:
        return []
    labels = (
        "health - uptime",
        "cpu - usage",
        "memory - usage",
        "capacity - root disk",
    )
    lines: list[str] = []
    for item in command_results:
        label = (item.get("label") or "").lower()
        if item.get("error") or not any(token in label for token in labels):
            continue
        output = (item.get("output") or "").strip()
        if not output:
            continue
        first = output.splitlines()[0].strip()
        lines.append(f"{item.get('label', 'Metric')}: {first}")
    return lines[:6]


def format_linux_host_capacity_html(
    command_results: list[dict[str, Any]] | None,
    metrics: dict[str, Any] | None,
    server_name: str = "",
) -> str:
    capacity: dict[str, Any] | None = None
    root_item = _find_result(
        command_results,
        "capacity - root disk",
        "df -h /",
    )
    capacity = _parse_root_disk_capacity(_result_output(root_item))
    if not capacity and metrics:
        capacity = _capacity_from_metrics(metrics)
    if not capacity:
        return ""

    parts = [
        _format_capacity_block(
            capacity,
            summary_suffix="disk usage",
            bar_label="Root disk utilization",
            section_class="capacity-section capacity-system-block",
        )
    ]

    fs_item = _find_result(
        command_results,
        "capacity - all filesystems",
        "df -h",
    )
    fs_output = _result_output(fs_item)
    if fs_output:
        headers, rows = _parse_df_table(fs_output)
        if not rows:
            headers, rows = _table_rows(fs_output)
        if headers and rows:
            normalized = []
            for row in rows:
                if len(row) < len(headers):
                    row = row + [""] * (len(headers) - len(row))
                elif len(row) > len(headers):
                    row = row[: len(headers)]
                normalized.append(row)
            parts.append(
                '<section class="capacity-section capacity-detail-section">'
                '<p class="cmd-summary">Filesystem usage</p>'
                + _html_table(headers, normalized, family="", table_class="data-table df-table")
                + "</section>"
            )

    summary_lines = _linux_summary_lines(command_results)
    if summary_lines:
        parts.append(
            '<section class="capacity-section capacity-detail-section">'
            '<p class="cmd-summary">System summary</p>'
            '<pre class="raw-output">'
            + html.escape("\n".join(summary_lines))
            + "</pre></section>"
        )
    elif metrics:
        cpu = float(metrics.get("cpu_percent") or 0)
        mem_total = int(metrics.get("mem_total_kb") or 0) * 1024
        mem_avail = int(metrics.get("mem_avail_kb") or 0) * 1024
        if mem_total:
            mem_used = max(0, mem_total - mem_avail)
            mem_pct = mem_used / mem_total * 100.0
            parts.append(
                '<section class="capacity-section capacity-detail-section">'
                '<p class="cmd-summary">System summary</p>'
                '<pre class="raw-output">'
                + html.escape(
                    f"CPU: {cpu:.1f}%\nMemory: {mem_pct:.1f}% used ({_format_bytes(mem_used)} / {_format_bytes(mem_total)})"
                )
                + "</pre></section>"
            )

    return "".join(parts)


def format_command_detail_html(label: str, command: str, output: str) -> str:
    text = (output or "").strip()
    if not text:
        return '<p class="sub">(no output)</p>'

    family = _command_family(command)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if family == "lsmdiskgrp" or "capacity - pools" in label.lower():
        pools = parse_pool_capacity_rows(text)
        if pools:
            return format_pools_capacity_html(pools)

    summary_block = format_command_output_html(label, command, text).split("</p>", 1)[0] + "</p>"

    kv = _parse_key_values(text)
    if kv and len(kv) >= 2 and family in {"", "lssystem"}:
        return summary_block + _html_key_value_table(kv, family or "lssystem")

    if len(lines) == 1 and lines[0].count(":") >= 3:
        pair_kv = _parse_colon_pairs(lines[0])
        if pair_kv:
            return summary_block + _html_key_value_table(pair_kv, family)

    headers, rows = _table_rows(text)
    if headers and rows:
        normalized = []
        for row in rows:
            if len(row) < len(headers):
                row = row + [""] * (len(headers) - len(row))
            elif len(row) > len(headers):
                row = row[: len(headers)]
            normalized.append(row)
        return summary_block + _html_table(headers, normalized, family="")

    if kv:
        return summary_block + _html_key_value_table(kv, family)

    return summary_block + f'<pre class="raw-output">{html.escape(text)}</pre>'


def _analyze_status_table(
    issues: list[dict[str, Any]],
    *,
    server: str,
    output: str,
    category: str,
    item_label: str,
    name_fields: tuple[str, ...] = ("name",),
    status_field: str = "status",
) -> None:
    if not output.strip():
        return
    headers, rows = _table_rows(output)
    if not headers or not rows:
        return
    for row in rows:
        record = _row_map(headers, row)
        name = next((record.get(field, "") for field in name_fields if record.get(field)), item_label)
        status = record.get(status_field, "")
        if not status:
            continue
        issue = _status_issue(category, name, item_label, status, server=server)
        if issue:
            issues.append(issue)


def _analyze_alerts(issues: list[dict[str, Any]], *, server: str, output: str) -> None:
    headers, rows = _table_rows(output)
    if not rows:
        return
    for row in rows:
        record = _row_map(headers, row)
        message = record.get("message", "") or record.get("object_name", "Alert")
        lowered = message.lower()
        severity = "warn"
        category = "alert"
        if any(token in lowered for token in ("nvme", "drive", "ssd", "module")):
            category = "nvme"
            severity = "critical"
        elif any(token in lowered for token in ("cpu", "processor", "overheat")):
            category = "cpu"
        elif any(token in lowered for token in ("memory", "ram")):
            category = "memory"
        issues.append(
            {
                "severity": severity,
                "category": category,
                "message": message[:140],
                "server": server,
            }
        )


def _analyze_volume_capacity(issues: list[dict[str, Any]], *, server: str, output: str) -> None:
    headers, rows = _table_rows(output)
    if not headers or not rows:
        return
    for row in rows:
        record = _row_map(headers, row)
        name = record.get("name") or record.get("vdisk_name") or "volume"
        capacity = _parse_size_bytes(record.get("capacity", ""))
        used = _parse_size_bytes(record.get("used_capacity", "") or record.get("real_capacity", ""))
        if capacity and used is not None:
            pct = used / capacity * 100.0
            if pct >= 80:
                issues.append(
                    {
                        "severity": "critical" if pct >= 90 else "warn",
                        "category": "capacity",
                        "message": f"Volume {name} is {pct:.1f}% full",
                        "server": server,
                    }
                )
        status = record.get("status", "")
        issue = _status_issue("lun", name, "Volume", status, server=server)
        if issue:
            issues.append(issue)


def _analyze_nvme(issues: list[dict[str, Any]], *, server: str, output: str) -> None:
    headers, rows = _table_rows(output)
    if not headers or not rows:
        return
    for row in rows:
        record = _row_map(headers, row)
        label = " ".join(record.values()).lower()
        if "nvme" not in label and record.get("tech_type", "").lower() != "nvme":
            continue
        name = record.get("name") or record.get("id") or "NVMe drive"
        status = record.get("status", "")
        issue = _status_issue("nvme", name, "NVMe drive", status, server=server)
        if issue:
            issues.append(issue)


def analyze_health(
    server_name: str,
    command_results: list[dict[str, Any]] | None,
    metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    capacity: dict[str, Any] | None = None
    pools_output = ""

    if command_results:
        for item in command_results:
            if item.get("error"):
                issues.append(
                    {
                        "severity": "critical",
                        "category": "command",
                        "message": f"{item.get('label', 'Command')} failed",
                        "server": server_name,
                    }
                )

        system_item = None
        system_output = ""
        for needles in (
            ("lssystem", "capacity - system"),
            ("showsys", "capacity - system"),
            ("showspace", "capacity - system"),
            ("lssi", "capacity - system"),
            ("space_show", "capacity - system"),
        ):
            system_item = _find_result(command_results, *needles)
            system_output = _capacity_result_output(system_item)
            if system_output:
                break
        if system_output:
            capacity = _parse_system_capacity(system_output)
            if capacity and capacity["used_pct"] >= 80:
                issues.append(
                    {
                        "severity": "critical" if capacity["used_pct"] >= 90 else "warn",
                        "category": "capacity",
                        "message": (
                            f"Running at {capacity['used_pct']:.1f}% capacity "
                            f"({_format_bytes(capacity['used_bytes'])} used / "
                            f"{_format_bytes(capacity['total_bytes'])})"
                        ),
                        "server": server_name,
                    }
                )

        pools_item = _find_pool_capacity_result(command_results)
        pools_output = _capacity_result_output(pools_item)
        if pools_output:
            headers, rows = _table_rows(pools_output)
            for row in rows:
                record = _row_map(headers, row)
                pool_name = record.get("name") or record.get("CPG") or record.get("PoolName") or "pool"
                cap = _parse_size_bytes(record.get("capacity", "") or record.get("Total", ""))
                free = _parse_size_bytes(record.get("free_capacity", "") or record.get("Free", ""))
                used_pct_raw = record.get("UsedPct") or record.get("Used%") or record.get("used_pct", "")
                used_pct: float | None = None
                if used_pct_raw:
                    try:
                        used_pct = float(str(used_pct_raw).replace("%", "").strip())
                    except ValueError:
                        used_pct = None
                if used_pct is None and cap and free is not None:
                    used_pct = (cap - free) / cap * 100.0
                if used_pct is not None and used_pct >= 80:
                    issues.append(
                        {
                            "severity": "critical" if used_pct >= 90 else "warn",
                            "category": "capacity",
                            "message": f"Pool {pool_name} is {used_pct:.1f}% full",
                            "server": server_name,
                        }
                    )

        node_output = _result_output(_find_result(command_results, "lsnode", "health - nodes", "shownode"))
        _analyze_status_table(
            issues,
            server=server_name,
            output=node_output,
            category="node",
            item_label="Node",
        )
        if node_output and "State" in node_output:
            _analyze_status_table(
                issues,
                server=server_name,
                output=node_output,
                category="node",
                item_label="Node",
                status_field="State",
            )
        _analyze_status_table(
            issues,
            server=server_name,
            output=_result_output(
                _find_result(
                    command_results,
                    "lsnodecanister",
                    "lscontroller",
                    "health - controllers",
                )
            ),
            category="controller",
            item_label="Controller",
        )
        _analyze_status_table(
            issues,
            server=server_name,
            output=_result_output(_find_result(command_results, "lsmdisk", "capacity - mdisk", "showpd")),
            category="mdisk",
            item_label="MDisk",
        )
        _analyze_status_table(
            issues,
            server=server_name,
            output=_result_output(_find_result(command_results, "showpd", "health - disks")),
            category="disk",
            item_label="Disk",
            status_field="State",
        )
        _analyze_status_table(
            issues,
            server=server_name,
            output=_result_output(_find_result(command_results, "comp_list", "health - components")),
            category="component",
            item_label="Component",
            status_field="status",
        )
        _analyze_nvme(
            issues,
            server=server_name,
            output=_result_output(_find_result(command_results, "lsmdisk", "capacity - mdisk")),
        )
        _analyze_volume_capacity(
            issues,
            server=server_name,
            output=_result_output(_find_result(command_results, "lsvdisk", "memory - volumes")),
        )
        _analyze_alerts(
            issues,
            server=server_name,
            output=_result_output(
                _find_result(command_results, "lseventlog", "health - alerts", "showalert", "event_list")
            ),
        )
        check_output = _result_output(_find_result(command_results, "checkhealth", "health - overall"))
        if check_output:
            lower = check_output.lower()
            if any(token in lower for token in ("degraded", "failed", "critical", "not ok", "not healthy")):
                issues.append(
                    {
                        "severity": "critical",
                        "category": "health",
                        "message": check_output.splitlines()[0][:140],
                        "server": server_name,
                    }
                )
        _analyze_status_table(
            issues,
            server=server_name,
            output=_result_output(_find_result(command_results, "showbattery", "health - battery")),
            category="battery",
            item_label="Battery",
            status_field="State",
        )

        _analyze_linux_command_thresholds(
            issues,
            server=server_name,
            command_results=command_results,
        )

    if metrics:
        cpu_pct = float(metrics.get("cpu_percent") or 0)
        if cpu_pct >= 80:
            issues.append(
                {
                    "severity": "critical" if cpu_pct >= 90 else "warn",
                    "category": "cpu",
                    "message": f"CPU high at {cpu_pct:.1f}%",
                    "server": server_name,
                }
            )
        mem_total = (metrics.get("mem_total_kb") or 0) * 1024
        mem_avail = (metrics.get("mem_avail_kb") or 0) * 1024
        if mem_total:
            mem_pct = (mem_total - mem_avail) / mem_total * 100.0
            if mem_pct >= 80:
                issues.append(
                    {
                        "severity": "critical" if mem_pct >= 90 else "warn",
                        "category": "memory",
                        "message": f"Memory use at {mem_pct:.1f}%",
                        "server": server_name,
                    }
                )

    severity_rank = {"critical": 0, "warn": 1}
    issues.sort(key=lambda item: (severity_rank.get(item["severity"], 9), item["server"], item["category"]))

    popup_html = format_capacity_report_html(capacity, pools_output)
    if not popup_html:
        popup_html = format_linux_host_capacity_html(command_results, metrics, server_name)
    if not popup_html:
        popup_html = format_preset_capacity_fallback_html(command_results)

    # Always fill capacity for Linux / metric hosts — not only when a popup exists.
    if not capacity:
        root_item = _find_result(command_results, "capacity - root disk", "df -h /")
        capacity = _parse_root_disk_capacity(_result_output(root_item))
        if not capacity:
            fs_item = _find_result(
                command_results,
                "capacity - all filesystems",
                "df -h --output",
                "df -h",
            )
            capacity = _parse_root_disk_capacity(_result_output(fs_item))
        if not capacity and metrics:
            capacity = _capacity_from_metrics(metrics)

    if not popup_html and capacity:
        popup_html = format_linux_host_capacity_html(command_results, metrics, server_name)

    pools = parse_pool_capacity_rows(pools_output) if pools_output else []
    if not pools and capacity:
        pools = [
            {
                "name": capacity.get("name") or "Root disk",
                "used_bytes": int(capacity.get("used_bytes") or 0),
                "total_bytes": int(capacity.get("total_bytes") or 0),
                "free_bytes": int(capacity.get("free_bytes") or 0),
                "used_pct": float(capacity.get("used_pct") or 0),
            }
        ]
    if not capacity and pools:
        capacity = capacity_summary_from_pools(pools)

    return {
        "health_issues": issues,
        "capacity_summary": capacity,
        "capacity_popup_html": popup_html,
        "pools": pools,
    }
