from dataclasses import dataclass

from launchpad.health_server import get_health_server
from launchpad.ssh_launcher import _log
from launchpad.ssh_utils import SshMetricsAuth


@dataclass(frozen=True)
class HealthDashboardEntry:
    card_id: int
    name: str
    host: str
    port: int | None
    username: str
    auth: SshMetricsAuth
    device_profile: str = ""
    custom_commands: str = ""
    serial_number: str = ""
    category: str = ""
    url: str = ""


def _register_entry(server, entry: HealthDashboardEntry) -> None:
    server.register_card(
        entry.card_id,
        entry.name,
        entry.host,
        entry.port,
        entry.username,
        entry.auth.key_path,
        entry.auth.key_passphrase,
        entry.auth.password,
        entry.device_profile,
        entry.custom_commands,
        entry.serial_number,
        entry.category,
        entry.url,
    )


def build_health_dashboard_entries(db, crypto_key: bytes) -> list[HealthDashboardEntry]:
    from launchpad.ssh_utils import resolve_ssh_metrics_auth, ssh_stats_prereq_message

    entries: list[HealthDashboardEntry] = []
    for card in db.list_cards():
        if card.card_type != "ssh":
            continue
        if ssh_stats_prereq_message(card, crypto_key):
            continue
        auth = resolve_ssh_metrics_auth(card, crypto_key)
        entries.append(
            HealthDashboardEntry(
                card_id=card.id,
                name=card.name,
                host=card.host,
                port=card.port,
                username=card.username,
                auth=auth,
                device_profile=card.device_profile,
                custom_commands=card.custom_commands,
                serial_number=getattr(card, "serial_number", "") or "",
                category=card.category or "",
                url=card.url or "",
            )
        )
    return entries


def ensure_health_dashboard_registered(db, crypto_key: bytes) -> int:
    """Register all SSH cards with credentials so the browser page can list them."""
    entries = build_health_dashboard_entries(db, crypto_key)
    server = get_health_server()
    server.ensure_running()
    active_ids = {entry.card_id for entry in entries}
    server.prune_cards(active_ids)
    if not entries:
        return 0
    for entry in entries:
        _register_entry(server, entry)
    return len(entries)


def _open_health_url(server) -> str:
    server.ensure_running()
    return server.open_browser_once()


def open_health_dashboard(
    card_id: int,
    card_name: str,
    host: str,
    port: int | None,
    username: str,
    key_path: str = "",
    key_passphrase: str = "",
    password: str = "",
    device_profile: str = "",
    custom_commands: str = "",
    serial_number: str = "",
) -> str:
    if not key_path and not password:
        raise ValueError("SSH password or key is required for health monitoring.")

    server = get_health_server()
    server.ensure_running()
    server.register_card(
        card_id,
        card_name,
        host,
        port,
        username,
        key_path,
        key_passphrase,
        password,
        device_profile,
        custom_commands,
        serial_number,
    )
    card = server.refresh_card(card_id)
    if card.error and not card.command_results and not card.metrics:
        raise ValueError(card.error)

    url = _open_health_url(server)
    _log(f"Added {card_name} to health dashboard at {url}")
    return url


def open_health_dashboard_for_cards(
    entries: list[HealthDashboardEntry],
    *,
    open_browser: bool = True,
    refresh: bool = False,
) -> tuple[str, list[tuple[str, str | None]]]:
    if not entries:
        raise ValueError("No SSH cards with credentials to monitor.")

    server = get_health_server()
    server.ensure_running()

    results: list[tuple[str, str | None]] = []
    for entry in entries:
        _register_entry(server, entry)
        if refresh:
            card = server.refresh_card(entry.card_id)
            results.append((entry.name, card.error))
            _log(
                f"Health refresh for {entry.name}: "
                f"{'failed - ' + card.error if card.error else 'ok'}"
            )
        else:
            results.append((entry.name, None))

    url = _open_health_url(server) if open_browser else server.url
    return url, results


def open_capacity_report_for_cards(
    entries: list[HealthDashboardEntry],
    *,
    refresh: bool = False,
) -> str:
    if not entries:
        raise ValueError("No SSH cards with credentials to monitor.")

    server = get_health_server()
    server.ensure_running()

    for entry in entries:
        _register_entry(server, entry)
        if refresh:
            card = server.refresh_card(entry.card_id)
            _log(
                f"Capacity refresh for {entry.name}: "
                f"{'failed - ' + card.error if card.error else 'ok'}"
            )

    return server.open_capacity_report_once()


def open_fc_wwpn_report_for_cards(
    entries: list[HealthDashboardEntry],
    *,
    refresh: bool = False,
) -> str:
    if not entries:
        raise ValueError("No SSH cards with credentials to monitor.")

    server = get_health_server()
    server.ensure_running()

    for entry in entries:
        _register_entry(server, entry)
        if refresh:
            card = server.refresh_card(entry.card_id)
            _log(
                f"FC WWPN refresh for {entry.name}: "
                f"{'failed - ' + card.error if card.error else 'ok'}"
            )

    return server.open_fc_wwpn_report_once()


def open_site_lookup_for_cards(entries: list[HealthDashboardEntry]) -> str:
    if not entries:
        raise ValueError("No SSH cards with credentials to monitor.")

    server = get_health_server()
    server.ensure_running()
    for entry in entries:
        _register_entry(server, entry)
    return server.open_site_lookup()


def open_ansible_pad_for_cards(entries: list[HealthDashboardEntry]) -> str:
    if not entries:
        raise ValueError("No SSH cards with credentials to monitor.")

    server = get_health_server()
    server.ensure_running()
    for entry in entries:
        _register_entry(server, entry)
    return server.open_ansible_pad()


def get_monitor_states() -> dict[int, bool]:
    server = get_health_server()
    server.ensure_running()
    return {int(card_id): enabled for card_id, enabled in server.monitor_states().items()}


def set_card_monitor_enabled(card_id: int, enabled: bool) -> None:
    server = get_health_server()
    server.ensure_running()
    server.set_monitor_enabled(card_id=card_id, enabled=enabled)


def set_all_monitor_enabled(enabled: bool) -> None:
    server = get_health_server()
    server.ensure_running()
    server.set_monitor_enabled(enabled=enabled, all_cards=True)
