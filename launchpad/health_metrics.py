import base64
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from launchpad.ssh_keys import secure_private_key_file
from launchpad.ssh_launcher import _log, _ssh_executable
from launchpad.ssh_paramiko import run_ssh_command
from launchpad.ssh_passphrase import askpass_env
from launchpad.subprocess_utils import run_hidden

REMOTE_METRICS_SCRIPT = r"""
import json, os, shutil, time, socket, subprocess

def cpu_percent():
    def snap():
        with open("/proc/stat") as handle:
            parts = handle.readline().split()[1:8]
        vals = [int(x) for x in parts]
        idle = vals[3]
        total = sum(vals)
        return idle, total
    idle1, total1 = snap()
    time.sleep(0.4)
    idle2, total2 = snap()
    delta_total = total2 - total1
    delta_idle = idle2 - idle1
    if delta_total <= 0:
        return 0.0
    return round((1.0 - delta_idle / delta_total) * 100.0, 1)

mem = {}
with open("/proc/meminfo") as handle:
    for line in handle:
        key = line.split(":", 1)[0]
        if key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
            mem[key] = int(line.split()[1])

disk = shutil.disk_usage("/")
load = os.getloadavg()
uptime_seconds = 0.0
with open("/proc/uptime") as handle:
    uptime_seconds = float(handle.read().split()[0])

def process_count():
    return sum(1 for name in os.listdir("/proc") if name.isdigit())

def users_logged_in():
    try:
        output = subprocess.check_output(["who"], text=True).strip()
        if not output:
            return 0
        return len({line.split()[0] for line in output.splitlines() if line.strip()})
    except Exception:
        return 0

def primary_ipv4():
    try:
        output = subprocess.check_output(["ip", "-4", "-o", "addr", "show"], text=True)
        for line in output.splitlines():
            if "scope global" not in line:
                continue
            parts = line.split()
            iface = parts[1]
            inet_idx = parts.index("inet") + 1
            ip = parts[inet_idx].split("/")[0]
            return iface, ip
    except Exception:
        pass
    try:
        return "", socket.gethostbyname(socket.gethostname())
    except Exception:
        return "", ""

iface, ipv4 = primary_ipv4()

payload = {
    "hostname": os.uname().nodename,
    "cpu_percent": cpu_percent(),
    "cpu_cores": os.cpu_count() or 1,
    "load_1": round(load[0], 2),
    "load_5": round(load[1], 2),
    "load_15": round(load[2], 2),
    "mem_total_kb": mem.get("MemTotal", 0),
    "mem_avail_kb": mem.get("MemAvailable", 0),
    "swap_total_kb": mem.get("SwapTotal", 0),
    "swap_free_kb": mem.get("SwapFree", 0),
    "disk_total": disk.total,
    "disk_used": disk.used,
    "disk_free": disk.free,
    "uptime_seconds": int(uptime_seconds),
    "process_count": process_count(),
    "users_logged_in": users_logged_in(),
    "ipv4_interface": iface,
    "ipv4_address": ipv4,
}
print(json.dumps(payload))
"""


def run_remote_metrics(
    host: str,
    port: int | None,
    username: str,
    key_path: str = "",
    key_passphrase: str = "",
    password: str = "",
) -> dict[str, Any]:
    use_password_auth = bool(password)
    if use_password_auth:
        key_path = ""
    elif key_path:
        secure_private_key_file(Path(key_path))

    if not key_path and not password:
        raise ValueError("SSH password or key is required for health metrics.")

    encoded = base64.b64encode(REMOTE_METRICS_SCRIPT.encode("utf-8")).decode("ascii")
    remote_cmd = f"echo {encoded} | base64 -d | python3"

    target = f"{username}@{host}" if username else host
    _log(f"Health check SSH: {target} ({'password' if use_password_auth else 'key'})")

    if use_password_auth:
        try:
            output = run_ssh_command(host, port, username, password, remote_cmd, timeout=25)
        except ValueError as exc:
            raise ValueError(f"Could not fetch health metrics:\n{exc}") from exc
        try:
            return json.loads(output.strip())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid metrics response from server:\n{output[:300]}") from exc

    ssh = _ssh_executable()
    args = [
        ssh,
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=12",
        "-i",
        key_path,
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "BatchMode=yes" if not key_passphrase else "BatchMode=no",
    ]
    env = {**os.environ, **askpass_env(key_passphrase)}
    if port:
        args.extend(["-p", str(port)])
    args.extend([target, remote_cmd])

    result = run_hidden(args, capture_output=True, text=True, timeout=25, check=False, env=env)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Unknown SSH error").strip()
        raise ValueError(f"Could not fetch health metrics:\n{detail}")

    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid metrics response from server:\n{result.stdout[:300]}") from exc
