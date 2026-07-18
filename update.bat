@echo off
setlocal
cd /d "%~dp0"

for /f "delims=" %%V in ('python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"') do set "APP_VERSION=%%V"
echo Updating LaunchPad to v%APP_VERSION% ...
echo.

if not exist "dist\LaunchPad.exe" (
    echo dist\LaunchPad.exe not found. Running build.bat...
    call build.bat
    if errorlevel 1 exit /b 1
)

set "INSTALL_DIR=%LOCALAPPDATA%\LaunchPad"
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "LaunchPad-Install" mkdir "LaunchPad-Install"

echo Copying latest files to %INSTALL_DIR%...
tasklist /FI "IMAGENAME eq LaunchPad.exe" 2>nul | find /I "LaunchPad.exe" >nul
if not errorlevel 1 (
    echo.
    echo ERROR: LaunchPad is still running. Close it completely, then run update.bat again.
    echo.
    pause
    exit /b 1
)
tasklist /FI "IMAGENAME eq LaunchPad_latest.exe" 2>nul | find /I "LaunchPad_latest.exe" >nul
if not errorlevel 1 (
    echo.
    echo ERROR: LaunchPad_latest.exe is still running. Close it, then run update.bat again.
    echo.
    pause
    exit /b 1
)

copy /Y "dist\LaunchPad.exe" "%INSTALL_DIR%\LaunchPad.exe" >nul
copy /Y "dist\ssh_askpass.exe" "%INSTALL_DIR%\ssh_askpass.exe" >nul
copy /Y "dist\ssh_interactive.exe" "%INSTALL_DIR%\ssh_interactive.exe" >nul
copy /Y "dist\LaunchPad.exe" "LaunchPad-Install\LaunchPad.exe" >nul
copy /Y "dist\ssh_askpass.exe" "LaunchPad-Install\ssh_askpass.exe" >nul
copy /Y "dist\ssh_interactive.exe" "LaunchPad-Install\ssh_interactive.exe" >nul
if exist "dist\BUILD_STAMP.txt" copy /Y "dist\BUILD_STAMP.txt" "%INSTALL_DIR%\BUILD_STAMP.txt" >nul

for %%F in ("dist\LaunchPad.exe") do echo Installed build dated: %%~tF

echo Refreshing Desktop shortcuts (removes old LaunchPad.exe copies)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"

echo.
echo Update complete (v%APP_VERSION%).
echo Launch from the LaunchPad SHORTCUT on your Desktop — not LaunchPad.exe in a folder.
echo Login screen should show: Secure connection dashboard  ·  v%APP_VERSION%
echo Admin header should show: Admin Dashboard  ·  v%APP_VERSION%
echo.
pause

endlocal
