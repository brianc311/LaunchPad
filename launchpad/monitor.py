from launchpad.health_metrics import run_remote_metrics
from launchpad.health_server import get_health_server
from launchpad.ssh_launcher import _log


def open_health_dashboard(
    card_id: int,
    card_name: str,
    host: str,
    port: int | None,
    username: str,
    key_path: str,
    key_passphrase: str = "",
) -> str:
    if not key_path:
        raise ValueError("SSH key is required for health monitoring.")

    server = get_health_server()
    server.ensure_running()
    server.register_card(card_id, card_name, host, port, username, key_path, key_passphrase)
    card = server.refresh_card(card_id)
    if card.error:
        raise ValueError(card.error)

    url = server.open_browser_once()
    _log(f"Added {card_name} to health dashboard at {url}")
    return url
