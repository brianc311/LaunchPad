"""Regression: normal Windows build must sync origin/main before reading APP_VERSION."""

from pathlib import Path


def test_build_bat_syncs_origin_main_before_version():
    text = Path("build.bat").read_text(encoding="utf-8")
    assert "EnableDelayedExpansion" in text
    assert "git fetch origin main" in text
    assert "git merge --ff-only origin/main" in text
    assert "Build must run on branch main" in text
    assert "from launchpad.config import APP_VERSION" in text
    # Sync must appear before the version echo used for the build banner.
    sync_at = text.index("git fetch origin main")
    version_at = text.index("Building LaunchPad v%APP_VERSION%")
    assert sync_at < version_at
