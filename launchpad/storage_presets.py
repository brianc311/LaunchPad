"""Storage device CLI presets — health, CPU, memory, and capacity commands."""

from __future__ import annotations

from launchpad.command_format import format_command_lines

SVC_FC_COMMANDS: list[tuple[str, str]] = [
    ("FC - Ports WWPN", "svcinfo lsportfc -delim :"),
    ("FC - Hosts", "svcinfo lshost -delim :"),
    ("FC - Host LUN Maps", "svcinfo lshostvdiskmap -delim :"),
    ("FC - Fabric", "svcinfo lsfabric -delim :"),
]

# IBM Spectrum Virtualize / SVC CLI (FlashSystem, Storwize)
SVC_COMMANDS: list[tuple[str, str]] = [
    ("Health - Nodes", "svcinfo lsnode -delim :"),
    ("Health - Controllers", "svcinfo lsnode -delim :"),
    ("Health - Alerts", "svcinfo lseventlog -alert yes -delim :"),
    ("Capacity - System %", "svcinfo lssystem -delim :"),
    ("Capacity - Pools %", "svcinfo lsmdiskgrp -delim :"),
    ("Capacity - MDisks", "svcinfo lsmdisk -delim :"),
    ("CPU - Nodes %", "svcinfo lsnode -delim :"),
    ("Memory - Volumes %", "svcinfo lsvdisk -delim :"),
    ("Memory - Copies", "svcinfo lssevdiskcopy -delim :"),
    *SVC_FC_COMMANDS,
]

# HPE 3PAR (8200 / 8400 / 8450 share the same CLI)
# Capacity first so checkhealth cannot starve/bleed into capacity SSH reads.
# Capacity: showsys -d (MB totals) + showcpg (Usr/Free/Total). Do not use
# showcpg -sdg — that option only shows snapshot-data autogrow settings.
HP_3PAR_COMMANDS: list[tuple[str, str]] = [
    ("Capacity - System", "showsys -d"),
    ("Capacity - CPG %", "showcpg"),
    ("Health - Overall", "checkhealth"),
    ("Health - Alerts", "showalert"),
    ("Volumes - VV list", "showvv"),
    ("Hosts - host list", "showhost"),
    ("CPU - Load", "statcpu"),
    ("Health - Disks", "showpd"),
    ("Health - Nodes", "shownode -d"),
    ("Health - Battery", "showbattery"),
]

# HPE Primera 600 (same CLI family as 3PAR for capacity)
# showspace -cpg requires a CPG name/pattern; use showcpg for CPG capacity.
HPE_PRIMERA_COMMANDS: list[tuple[str, str]] = [
    ("Capacity - System", "showsys -d"),
    ("Capacity - CPG %", "showcpg"),
    ("Health - Nodes", "shownode -status"),
    ("Health - Alerts", "showalert"),
    ("Health - Disks", "showpd -status"),
    ("Volumes - VV list", "showvv"),
    ("Hosts - host list", "showhost"),
    ("CPU - All Nodes %", "statcpu -iter 1"),
    ("Memory - Cache %", "statcache -iter 1"),
]

# IBM DS8884 (DS CLI — run from a host with dscli in PATH, or adjust for your shell)
DS8884_COMMANDS: list[tuple[str, str]] = [
    ("Health - System", "dscli lssi"),
    ("Health - Arrays", "dscli lsarray -all"),
    ("Health - Alerts", "dscli lsalertentry -all"),
    ("Capacity - System %", "dscli lssi"),
    ("Capacity - Ext Pools %", "dscli lsextpool -s 0"),
    ("Capacity - Ranks", "dscli lsrank -all"),
    ("CPU - Nodes %", "dscli lsnode -all -cpumetrics"),
    ("Memory - Nodes %", "dscli lsnode -all -memorymetrics"),
]

# IBM XIV (Gen 3 / 114 / 2812)
XIV_COMMANDS: list[tuple[str, str]] = [
    ("Health - Components", "comp_list"),
    ("Health - Events", "event_list -f"),
    ("Capacity - System %", "space_show"),
    ("Capacity - Pools %", "pool_list -f"),
    ("Capacity - Volumes %", "vol_list -f"),
    ("CPU - Snapshot %", "xiv_top -a -n 1"),
    ("Memory - Snapshot %", "xiv_top -a -n 1"),
]

# Vultr Cloud API (vultr-cli on SSH host — set Serial Number to your Vultr instance ID)
VULTR_CLI_COMMANDS: list[tuple[str, str]] = [
    ("Health - Instance Status", "vultr-cli instance get YOUR_INSTANCE_ID"),
    ("Health - Instance List", "vultr-cli instance list"),
    ("Health - Account", "vultr-cli account"),
    ("Capacity - Bandwidth", "vultr-cli instance bandwidth YOUR_INSTANCE_ID"),
    ("Capacity - Block Storage", "vultr-cli block-storage list"),
    ("Capacity - Snapshots", "vultr-cli snapshot list"),
]

# Vultr VPS (Linux SSH — run on the instance for live CPU / memory / disk %)
VULTR_VPS_COMMANDS: list[tuple[str, str]] = [
    ("Health - Uptime", "uptime"),
    ("Health - Failed Units", "systemctl --failed --no-pager 2>/dev/null || true"),
    ("CPU - Load Average", "cat /proc/loadavg"),
    ("CPU - Usage %", "vmstat 1 2 | tail -1 | awk '{printf \"%.1f%% busy (idle %.1f%%)\\n\", 100-$15, $15}'"),
    ("Memory - Usage %", "free -m | awk '/Mem:/ {printf \"%.1f%% used (%d MB / %d MB)\\n\", $3/$2*100, $3, $2}'"),
    ("Memory - Detailed", "free -h"),
    ("Capacity - Root Disk %", "df -h / | awk 'NR==2 {print $5\" used (\"$3\" / \"$2\")\"}'"),
    ("Capacity - All Filesystems", "df -h --output=target,pcent,size,used,avail 2>/dev/null || df -h"),
]

# Combined preset: vultr-cli cloud checks + on-instance Linux metrics
VULTR_COMBINED_COMMANDS: list[tuple[str, str]] = [
    *VULTR_CLI_COMMANDS,
    *VULTR_VPS_COMMANDS,
]

# NetApp ONTAP (AFF / FAS — SSH to cluster management LIF)
NETAPP_ONTAP_COMMANDS: list[tuple[str, str]] = [
    ("Health - Cluster", "system health status show"),
    ("Health - Nodes", "system node show"),
    ("Capacity - Aggregates %", "storage aggregate show"),
    ("Capacity - Aggregate Space %", "storage aggregate show-space"),
    ("Capacity - Volumes %", "volume show -fields total,used,available,percent-used"),
    ("Capacity - Disks", "storage disk show"),
    ("CPU - Nodes %", "node run -node * -command sysstat -c 1 -u 1"),
]

# Dell EMC PowerMax / Symmetrix (SYMCLI on a Solutions Enabler host)
DELL_SYMCLI_COMMANDS: list[tuple[str, str]] = [
    ("Health - Arrays", "symcfg list"),
    ("Health - Status", "symcfg list -status"),
    ("Capacity - System %", "symcfg list -v"),
    ("Capacity - Pools %", "symcfg list -pool -v"),
    ("Capacity - Thin Devices", "symcfg list -tdev"),
    ("Capacity - Disks", "symdisk list"),
]

# Dell EMC PowerScale / Isilon (OneFS SSH)
DELL_POWERSCALE_COMMANDS: list[tuple[str, str]] = [
    ("Health - Cluster", "isi status"),
    ("Health - Alerts", "isi event events list --limit=20"),
    ("Capacity - System %", "isi status -q"),
    ("Capacity - Pools %", "isi storagepool list"),
    ("Capacity - Filesystems %", "df -h"),
    ("CPU - Nodes %", "isi statistics system --nodes=all -n 1"),
]

# Dell EMC PowerStore (pstcli from a management host, or edit for appliance SSH)
DELL_POWERSTORE_COMMANDS: list[tuple[str, str]] = [
    ("Health - Cluster", "pstcli cluster show"),
    ("Health - Appliance", "pstcli appliance show"),
    ("Health - Alerts", "pstcli alert show"),
    ("Capacity - System %", "pstcli cluster show"),
    ("Capacity - Pools %", "pstcli storage_container show"),
    ("Capacity - Volumes", "pstcli volume show"),
]

# Dell EMC Unity (uemcli)
DELL_UNITY_COMMANDS: list[tuple[str, str]] = [
    ("Health - System", "uemcli /sys/general show"),
    ("Health - Alerts", "uemcli /event/alert/hist show"),
    ("Capacity - System %", "uemcli /sys/general show"),
    ("Capacity - Pools %", "uemcli /stor/prov/pool show"),
    ("Capacity - LUNs", "uemcli /stor/prov/luns show"),
    ("CPU - SPs %", "uemcli /metric/value/rt show -path sp.*.cpu.summary.utilization"),
]

# Dell EMC VNX (naviseccli — often from a management host; add -h/-user if needed)
DELL_VNX_COMMANDS: list[tuple[str, str]] = [
    ("Health - Agent", "naviseccli getagent"),
    ("Health - SP", "naviseccli getall -sp"),
    ("Capacity - System %", "naviseccli getall -sp"),
    ("Capacity - Pools %", "naviseccli storagepool -list"),
    ("Capacity - Disks", "naviseccli getdisk"),
    ("Capacity - LUNs", "naviseccli getlun"),
]

# Dell EMC VPLEX
DELL_VPLEX_COMMANDS: list[tuple[str, str]] = [
    ("Health - Clusters", "ll /clusters/*"),
    ("Health - Directors", "ll /engines/*/directors/*"),
    ("Capacity - Usage %", "report capacity-usage"),
    ("Capacity - Storage Volumes", "ll /clusters/*/storage-volumes"),
    ("Capacity - Virtual Volumes", "ll /clusters/*/virtual-volumes"),
]

# Dell EMC XtremIO (XMS CLI)
DELL_XTREMIO_COMMANDS: list[tuple[str, str]] = [
    ("Health - Cluster", "show-clusters"),
    ("Health - XMS", "show-xms-info"),
    ("Health - Alerts", "show-alerts"),
    ("Capacity - System %", "show-clusters"),
    ("Capacity - Pools %", "show-clusters --prop=name,ud-ssd-space,ud-ssd-space-in-use,ud-ssd-space-in-use-percent"),
    ("Capacity - Volumes", "show-volumes"),
]

PRESET_HEADERS: dict[str, str] = {
    "ibm_ds8884": (
        "# IBM DS8884 — dscli from a management host or DS CLI session.\n"
    ),
    "ibm_xiv_gen3": (
        "# IBM XIV Gen 3 — XIV CLI session (space_show / pool_list for capacity).\n"
    ),
    "ibm_xiv_114": (
        "# IBM XIV 114 / 2812 — XIV CLI session (space_show / pool_list for capacity).\n"
    ),
    "netapp_aff_c250": (
        "# NetApp ONTAP — SSH to cluster management LIF (aggregates + volumes).\n"
    ),
    "netapp_aff_c400": (
        "# NetApp ONTAP — SSH to cluster management LIF (aggregates + volumes).\n"
    ),
    "netapp_fas2650": (
        "# NetApp ONTAP — SSH to cluster management LIF (aggregates + volumes).\n"
    ),
    "dell_powermax_8000": (
        "# Dell PowerMax — SYMCLI on a Solutions Enabler management host.\n"
    ),
    "dell_powermax_2000": (
        "# Dell PowerMax — SYMCLI on a Solutions Enabler management host.\n"
    ),
    "dell_symmetrix_250f": (
        "# Dell Symmetrix — SYMCLI on a Solutions Enabler management host.\n"
    ),
    "dell_symmetrix_40k": (
        "# Dell Symmetrix — SYMCLI on a Solutions Enabler management host.\n"
    ),
    "dell_powerscale_h700": (
        "# Dell PowerScale / Isilon — SSH to OneFS node.\n"
    ),
    "dell_powerstore_3000t": (
        "# Dell PowerStore — pstcli from a management host (edit if using appliance SSH).\n"
    ),
    "dell_unity_650f": (
        "# Dell Unity — uemcli (add -d/-u/-p if not already authenticated).\n"
    ),
    "dell_vnx_5200": (
        "# Dell VNX — naviseccli (add -h/-user/-password if needed).\n"
    ),
    "dell_vnx_5400": (
        "# Dell VNX — naviseccli (add -h/-user/-password if needed).\n"
    ),
    "dell_vnx_5800": (
        "# Dell VNX — naviseccli (add -h/-user/-password if needed).\n"
    ),
    "dell_vplex_vs2": (
        "# Dell VPLEX — VPLEX CLI session.\n"
    ),
    "dell_xtremio_x1": (
        "# Dell XtremIO — XMS CLI session.\n"
    ),
    "dell_xtremio_x2": (
        "# Dell XtremIO — XMS CLI session.\n"
    ),
    "vultr_cli": (
        "# Vultr API - requires vultr-cli and VULTR_API_KEY on the SSH host.\n"
        "# Put your Vultr instance ID in Serial Number (replaces YOUR_INSTANCE_ID).\n"
    ),
    "vultr_vps": (
        "# Vultr VPS - SSH into the instance for live CPU, memory, and disk %.\n"
    ),
    "vultr_combined": (
        "# Vultr - vultr-cli cloud checks plus Linux metrics on the VPS.\n"
        "# Put your Vultr instance ID in Serial Number (replaces YOUR_INSTANCE_ID).\n"
    ),
}

DEVICE_PROFILES: dict[str, str] = {
    "": "General Linux / SSH",
    # IBM FlashSystem (Spectrum Virtualize CLI)
    "flashsystem_5200": "IBM FlashSystem 5200",
    "flashsystem_7200": "IBM FlashSystem 7200",
    "flashsystem_7300": "IBM FlashSystem 7300",
    "flashsystem_9200": "IBM FlashSystem 9200",
    "flashsystem_9500": "IBM FlashSystem 9500",
    # IBM Storwize / SVC (Spectrum Virtualize CLI)
    "ibm_storwize_v7000": "IBM Storwize V7000",
    "ibm_storwize_v7000_g2": "IBM Storwize V7000 G2",
    "ibm_storwize_v7000_g3": "IBM Storwize V7000 G3",
    "ibm_svc_2145": "IBM SAN Volume Controller (2145-SV1)",
    # IBM DS / XIV
    "ibm_ds8884": "IBM DS8884",
    "ibm_xiv_gen3": "IBM XIV Gen 3- 314",
    "ibm_xiv_114": "IBM XIV 114 / 2812",
    # HPE 3PAR
    "hpe_3par_8450": "HPE 3PAR 8450",
    "hpe_3par_8400": "HPE 3PAR 8400",
    "hpe_3par_8200": "HPE 3PAR 8200",
    # HPE Primera
    "hpe_primera_600": "HPE Primera 600 4-way",
    # NetApp ONTAP
    "netapp_aff_c250": "NetApp AFF-C250",
    "netapp_aff_c400": "NetApp AFF-C400",
    "netapp_fas2650": "NetApp FAS2650",
    # Dell EMC
    "dell_powermax_8000": "Dell EMC PowerMax 8000",
    "dell_powermax_2000": "Dell EMC PowerMax 2000",
    "dell_powerscale_h700": "Dell EMC PowerScale H700",
    "dell_powerstore_3000t": "Dell EMC PowerStore 3000T",
    "dell_symmetrix_250f": "Dell EMC Symmetrix 250F",
    "dell_symmetrix_40k": "Dell EMC Symmetrix 40K",
    "dell_unity_650f": "Dell EMC UNITY 650F",
    "dell_vnx_5200": "Dell EMC VNX 5200",
    "dell_vnx_5400": "Dell EMC VNX 5400",
    "dell_vnx_5800": "Dell EMC VNX 5800",
    "dell_vplex_vs2": "Dell EMC VPLEX VS2",
    "dell_xtremio_x1": "Dell EMC XtremIO X1",
    "dell_xtremio_x2": "Dell EMC XtremIO X2",
    # Vultr Cloud
    "vultr_combined": "Vultr Cloud VPS (CLI + Linux)",
    "vultr_cli": "Vultr Cloud (vultr-cli API)",
    "vultr_vps": "Vultr VPS (Linux SSH)",
}

SVC_PROFILES = frozenset(
    {
        "flashsystem_5200",
        "flashsystem_7200",
        "flashsystem_7300",
        "flashsystem_9200",
        "flashsystem_9500",
        "ibm_storwize_v7000",
        "ibm_storwize_v7000_g2",
        "ibm_storwize_v7000_g3",
        "ibm_svc_2145",
    }
)

HP_3PAR_PROFILES = frozenset({"hpe_3par_8450", "hpe_3par_8400", "hpe_3par_8200"})

NETAPP_ONTAP_PROFILES = frozenset(
    {
        "netapp_aff_c250",
        "netapp_aff_c400",
        "netapp_fas2650",
    }
)

DELL_SYMCLI_PROFILES = frozenset(
    {
        "dell_powermax_8000",
        "dell_powermax_2000",
        "dell_symmetrix_250f",
        "dell_symmetrix_40k",
    }
)

DELL_VNX_PROFILES = frozenset(
    {
        "dell_vnx_5200",
        "dell_vnx_5400",
        "dell_vnx_5800",
    }
)

DELL_XTREMIO_PROFILES = frozenset(
    {
        "dell_xtremio_x1",
        "dell_xtremio_x2",
    }
)

HPE_SHELL_PROFILES = HP_3PAR_PROFILES | frozenset({"hpe_primera_600"})

HPE_CLI_COMMAND_PREFIXES = (
    "checkhealth",
    "showalert",
    "showsys",
    "showcpg",
    "statcpu",
    "showpd",
    "shownode",
    "showbattery",
    "showspace",
    "statcache",
)

STORAGE_PROFILES = frozenset(k for k in DEVICE_PROFILES if k)


def uses_hpe_shell_cli(
    device_profile: str,
    commands: list[tuple[str, str]] | None = None,
) -> bool:
    if device_profile in HPE_SHELL_PROFILES:
        return True
    if not commands:
        return False
    for _, command in commands:
        first = command.strip().split(None, 1)[0].lower()
        if first in HPE_CLI_COMMAND_PREFIXES:
            return True
    return False

PROFILE_COMMANDS: dict[str, list[tuple[str, str]]] = {
    **{profile: list(SVC_COMMANDS) for profile in SVC_PROFILES},
    **{profile: list(HP_3PAR_COMMANDS) for profile in HP_3PAR_PROFILES},
    **{profile: list(NETAPP_ONTAP_COMMANDS) for profile in NETAPP_ONTAP_PROFILES},
    **{profile: list(DELL_SYMCLI_COMMANDS) for profile in DELL_SYMCLI_PROFILES},
    **{profile: list(DELL_VNX_COMMANDS) for profile in DELL_VNX_PROFILES},
    **{profile: list(DELL_XTREMIO_COMMANDS) for profile in DELL_XTREMIO_PROFILES},
    "hpe_primera_600": list(HPE_PRIMERA_COMMANDS),
    "ibm_ds8884": list(DS8884_COMMANDS),
    "ibm_xiv_gen3": list(XIV_COMMANDS),
    "ibm_xiv_114": list(XIV_COMMANDS),
    "dell_powerscale_h700": list(DELL_POWERSCALE_COMMANDS),
    "dell_powerstore_3000t": list(DELL_POWERSTORE_COMMANDS),
    "dell_unity_650f": list(DELL_UNITY_COMMANDS),
    "dell_vplex_vs2": list(DELL_VPLEX_COMMANDS),
    "vultr_cli": list(VULTR_CLI_COMMANDS),
    "vultr_vps": list(VULTR_VPS_COMMANDS),
    "vultr_combined": list(VULTR_COMBINED_COMMANDS),
}

# Backward-compatible aliases
FLASHSYSTEM_PROFILES = SVC_PROFILES
FLASHSYSTEM_COMMANDS = SVC_COMMANDS


def preset_commands_for_profile(profile: str) -> list[tuple[str, str]]:
    return list(PROFILE_COMMANDS.get(profile, []))


def is_svc_fc_profile(profile: str) -> bool:
    key = (profile or "").strip().lower()
    if key in SVC_PROFILES:
        return True
    return (
        "flashsystem" in key
        or "storwize" in key
        or key.endswith("_svc")
        or "svc_" in key
        or key == "ibm_svc_2145"
    )


def ensure_svc_fc_commands(
    profile: str,
    commands: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Append missing FC inventory commands for Spectrum Virtualize profiles.

    Cards often keep older custom command lists that pre-date the FC presets.
    """
    if not is_svc_fc_profile(profile):
        return list(commands)

    def has_command(*needles: str, exclude: tuple[str, ...] = ()) -> bool:
        for label, command in commands:
            haystack = f"{label} {command}".lower()
            if exclude and any(token in haystack for token in exclude):
                continue
            if any(needle in haystack for needle in needles):
                return True
        return False

    merged = list(commands)
    if not has_command("lsportfc", "ports wwpn"):
        merged.append(SVC_FC_COMMANDS[0])
    if not has_command(
        "lshost",
        "fc - hosts",
        exclude=("lshostvdiskmap", "lsvdiskhostmap", "host lun"),
    ):
        merged.append(SVC_FC_COMMANDS[1])
    if not has_command("lshostvdiskmap", "lsvdiskhostmap", "host lun maps"):
        merged.append(SVC_FC_COMMANDS[2])
    if not has_command("lsfabric", "fc - fabric"):
        merged.append(SVC_FC_COMMANDS[3])
    return merged


def ensure_hpe_capacity_commands(
    profile: str,
    commands: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Rewrite outdated HPE capacity CLI and ensure showsys/showcpg are present.

    Older cards used ``showcpg -sdg`` (autogrow settings only) and bare
    ``showspace -cpg`` (requires a CPG name and fails with Missing -cpg argument).
    """
    if profile not in HPE_SHELL_PROFILES and not uses_hpe_shell_cli(profile, commands):
        return list(commands)

    rewritten: list[tuple[str, str]] = []
    for label, command in commands:
        cmd = command.strip()
        lower = cmd.lower()
        label_lower = (label or "").lower()
        if lower == "showcpg -sdg" or lower.startswith("showcpg -sdg "):
            rewritten.append((label, "showcpg"))
            continue
        if lower == "showspace -cpg":
            rewritten.append((label, "showcpg"))
            continue
        # Bare showspace is a free-space estimate (often 0,0), not system capacity.
        if lower == "showspace" and "capacity" in label_lower:
            rewritten.append((label, "showsys -d"))
            continue
        rewritten.append((label, command))

    def has_command(*needles: str) -> bool:
        for label, command in rewritten:
            haystack = f"{label} {command}".lower()
            if any(needle in haystack for needle in needles):
                return True
        return False

    # Prefer capacity commands before slow checkhealth on custom lists.
    capacity: list[tuple[str, str]] = []
    rest: list[tuple[str, str]] = []
    for item in rewritten:
        label, command = item
        haystack = f"{label} {command}".lower()
        if "showsys" in haystack or "showcpg" in haystack or (
            "capacity" in haystack and "checkhealth" not in haystack
        ):
            capacity.append(item)
        else:
            rest.append(item)
    rewritten = capacity + rest

    if not has_command("showsys"):
        rewritten.insert(0, ("Capacity - System", "showsys -d"))
    if not has_command("showcpg"):
        # After showsys if present.
        insert_at = 1 if rewritten and "showsys" in rewritten[0][1].lower() else 0
        rewritten.insert(insert_at, ("Capacity - CPG %", "showcpg"))
    return rewritten


def preset_command_text(profile: str) -> str:
    header = PRESET_HEADERS.get(profile, "")
    body = format_command_lines(preset_commands_for_profile(profile))
    return f"{header}{body}" if header else body


def is_storage_profile(profile: str) -> bool:
    return profile in STORAGE_PROFILES


def is_flashsystem_profile(profile: str) -> bool:
    return profile in SVC_PROFILES
