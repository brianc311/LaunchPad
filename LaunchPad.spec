# -*- mode: python ; coding: utf-8 -*-
import os
import customtkinter

ctk_assets = os.path.join(os.path.dirname(customtkinter.__file__), "assets")
health_alert_art = os.path.join(SPECPATH, "launchpad", "resources", "health-alerts")

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (ctk_assets, "customtkinter/assets"),
        (health_alert_art, "launchpad/resources/health-alerts"),
    ],
    hiddenimports=['customtkinter', 'cryptography', 'paramiko', 'launchpad.storage_presets', 'launchpad.flashsystem_fc', 'launchpad.fc_wwpn_report', 'launchpad.fc_wwpn_export', 'launchpad.snapshot_schedule', 'launchpad.snapshot_schedule_export', 'openpyxl'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='LaunchPad_latest',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

askpass_a = Analysis(
    ['askpass_main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
askpass_pyz = PYZ(askpass_a.pure, askpass_a.zipped_data, cipher=block_cipher)
askpass_exe = EXE(
    askpass_pyz,
    askpass_a.scripts,
    askpass_a.binaries,
    askpass_a.zipfiles,
    askpass_a.datas,
    [],
    name='ssh_askpass',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

interactive_a = Analysis(
    ['ssh_interactive_main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['paramiko'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
interactive_pyz = PYZ(interactive_a.pure, interactive_a.zipped_data, cipher=block_cipher)
interactive_exe = EXE(
    interactive_pyz,
    interactive_a.scripts,
    interactive_a.binaries,
    interactive_a.zipfiles,
    interactive_a.datas,
    [],
    name='ssh_interactive',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
