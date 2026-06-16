import subprocess
import tempfile
import webbrowser
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

from launchpad.config import TEMP_DIR
from launchpad.ssh_launcher import launch_ssh
from launchpad.subprocess_utils import run_hidden


def launch_rdp(host: str, port: int | None, username: str, password: str) -> str:
    if not host:
        raise ValueError("RDP host is required.")

    address = f"{host}:{port}" if port else host
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    if username and password:
        run_hidden(
            ["cmdkey", f"/generic:TERMSRV/{host}", f"/user:{username}", f"/pass:{password}"],
            check=False,
            capture_output=True,
        )

    rdp_path = Path(tempfile.mkstemp(suffix=".rdp", dir=TEMP_DIR)[1])
    lines = [
        "screen mode id:i:2",
        "desktopwidth:i:1920",
        "desktopheight:i:1080",
        f"full address:s:{address}",
        "prompt for credentials:i:0",
        "authentication level:i:0",
        "redirectclipboard:i:1",
    ]
    if username:
        lines.append(f"username:s:{username}")
    rdp_path.write_text("\n".join(lines), encoding="utf-16-le")

    subprocess.Popen(["mstsc", str(rdp_path)], close_fds=False)
    return f"RDP session launched to {address}."


def launch_web(url: str, username: str, password: str) -> str:
    if not url:
        raise ValueError("Web URL is required.")

    target = url.strip()
    if username and password:
        parsed = urlparse(target if "://" in target else f"https://{target}")
        netloc = parsed.netloc or parsed.path
        path = parsed.path if parsed.netloc else ""
        if parsed.netloc:
            path = parsed.path
        else:
            path = ""
            if "/" in netloc:
                host_part, _, path_part = netloc.partition("/")
                netloc = host_part
                path = f"/{path_part}"

        auth_netloc = f"{quote(username, safe='')}:{quote(password, safe='')}@{netloc}"
        target = urlunparse(
            (
                parsed.scheme or "https",
                auth_netloc,
                path or parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            )
        )
    elif "://" not in target:
        target = f"https://{target}"

    webbrowser.open(target)
    return "Web page opened in your default browser."


def launch_card(
    card_type: str,
    host: str,
    port: int | None,
    username: str,
    password: str,
    key_path: str,
    url: str,
    card_name: str = "",
    key_passphrase: str = "",
) -> str:
    if card_type == "ssh":
        return launch_ssh(
            host,
            port,
            username,
            password,
            key_path,
            card_name or "SSH",
            key_passphrase,
        )
    if card_type == "rdp":
        return launch_rdp(host, port, username, password)
    if card_type == "web":
        return launch_web(url or host, username, password)
    raise ValueError(f"Unsupported card type: {card_type}")
