from launchpad.storage_presets import (
    DEVICE_PROFILES,
    preset_commands_for_profile,
)

POWER_PREFIX = "Power -"


def test_hadoop_linux_profile_label():
    assert DEVICE_PROFILES.get("hadoop_linux") == "Hadoop / Linux SSH"


def test_hadoop_linux_presets_include_os_hadoop_and_power():
    cmds = preset_commands_for_profile("hadoop_linux")
    assert cmds, "expected non-empty preset list"
    labels = [label for label, _ in cmds]
    joined = "\n".join(labels).lower()

    assert any(label.startswith("Health -") for label in labels)
    assert any(label.startswith("CPU -") for label in labels)
    assert any(label.startswith("Memory -") for label in labels)
    assert any(label.startswith("Capacity -") for label in labels)
    assert "hdfs" in joined or "yarn" in joined or "hadoop" in joined

    power = [(label, cmd) for label, cmd in cmds if label.startswith(POWER_PREFIX)]
    assert len(power) >= 2
    assert any("shutdown" in cmd.lower() or "poweroff" in cmd.lower() for _, cmd in power)
    assert power[-1][0].startswith(POWER_PREFIX)
    # Power defaults must not swallow failures
    for label, cmd in power:
        assert "|| true" not in cmd, f"{label} must not use || true"
