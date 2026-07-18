$installDir = Join-Path $env:LOCALAPPDATA "LaunchPad"
$target = Join-Path $installDir "LaunchPad.exe"

if (-not (Test-Path $target)) {
    Write-Error "LaunchPad.exe not found at $target. Run install.bat first."
    exit 1
}

$desktopRoots = @(
    (Join-Path $env:USERPROFILE "Desktop")
)

Get-ChildItem (Join-Path $env:USERPROFILE "OneDrive*") -Directory -ErrorAction SilentlyContinue |
    ForEach-Object {
        $candidate = Join-Path $_.FullName "Desktop"
        if (Test-Path $candidate) {
            $desktopRoots += $candidate
        }
    }

$desktopRoots = $desktopRoots | Select-Object -Unique
$shell = New-Object -ComObject WScript.Shell

foreach ($desktop in $desktopRoots) {
    if (-not (Test-Path $desktop)) {
        New-Item -ItemType Directory -Path $desktop | Out-Null
    }

    $staleExe = Join-Path $desktop "LaunchPad.exe"
    if (Test-Path $staleExe) {
        Remove-Item -Force $staleExe
        Write-Host "Removed old desktop copy: $staleExe"
    }

    $shortcutPath = Join-Path $desktop "LaunchPad.lnk"
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $target
    $shortcut.WorkingDirectory = $installDir
    $shortcut.Description = "LaunchPad Connection Dashboard"
    $shortcut.Save()
    Write-Host "Shortcut created: $shortcutPath -> $target"
}
