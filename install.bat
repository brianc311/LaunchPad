@echo off
setlocal
cd /d "%~dp0"

if not exist "dist\LaunchPad.exe" (
    echo LaunchPad.exe not found in dist\. Running build first...
    call build.bat
    if errorlevel 1 exit /b 1
)

set "INSTALL_DIR=%LOCALAPPDATA%\LaunchPad"
set "DESKTOP=%USERPROFILE%\Desktop"

if not exist "%DESKTOP%" mkdir "%DESKTOP%"
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo Installing LaunchPad to %INSTALL_DIR%...
copy /Y "dist\LaunchPad.exe" "%INSTALL_DIR%\LaunchPad.exe" >nul
copy /Y "dist\ssh_askpass.exe" "%INSTALL_DIR%\ssh_askpass.exe" >nul

echo Creating Desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"

echo.
echo LaunchPad installed successfully!
echo Desktop shortcut: %DESKTOP%\LaunchPad.lnk
echo.
echo First launch: set your master and admin passwords, then add cards in Admin.

endlocal
