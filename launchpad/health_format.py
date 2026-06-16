from typing import Any


def _pct(used: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return round(used / total * 100.0, 1)


def _gb(value: int) -> str:
    if value <= 0:
        return "0 GB"
    return f"{value / (1024 ** 3):.2f}GB"


def enrich_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    mem_total = metrics.get("mem_total_kb", 0) * 1024
    mem_avail = metrics.get("mem_avail_kb", 0) * 1024
    mem_used = max(0, mem_total - mem_avail)

    swap_total = metrics.get("swap_total_kb", 0) * 1024
    swap_free = metrics.get("swap_free_kb", 0) * 1024
    swap_used = max(0, swap_total - swap_free)

    disk_total = metrics.get("disk_total", 0)
    disk_used = metrics.get("disk_used", 0)

    enriched = dict(metrics)
    enriched["mem_used_pct"] = _pct(mem_used, mem_total)
    enriched["swap_used_pct"] = _pct(swap_used, swap_total)
    enriched["disk_used_pct"] = _pct(disk_used, disk_total)
    enriched["disk_total_label"] = _gb(disk_total)
    return enriched


def card_stats_columns(metrics: dict[str, Any]) -> tuple[list[str], list[str]]:
    data = enrich_metrics(metrics)
    iface = data.get("ipv4_interface", "")
    ip = data.get("ipv4_address", "")
    ip_label = f"{iface}: {ip}" if iface else ip

    left = [
        f"Load: {data.get('load_1', 0):.2f}",
        f"Disk: {data['disk_used_pct']:.1f}% of {data['disk_total_label']}",
        f"Memory: {data['mem_used_pct']:.1f}%",
        f"Swap: {data['swap_used_pct']:.1f}%",
    ]
    right = [
        f"Processes: {data.get('process_count', 0)}",
        f"Users: {data.get('users_logged_in', 0)}",
        f"IP: {ip_label or '—'}",
    ]
    return left, right
