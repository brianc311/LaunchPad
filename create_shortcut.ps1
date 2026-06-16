$installDir = Join-Path $env:LOCALAPPDATA "LaunchPad"
$desktop = Join-Path $env:USERPROFILE "Desktop"
if (-not (Test-Path $desktop)) {
    New-Item -ItemType Directory -Path $desktop | Out-Null
}
$shortcutPath = Join-Path $desktop "LaunchPad.lnk"
$target = Join-Path $installDir "LaunchPad.exe"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = "LaunchPad Connection Dashboard"
$shortcut.Save()
Write-Host "Shortcut created: $shortcutPath"
