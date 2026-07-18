@echo off
setlocal
cd /d "%~dp0"

if not exist "dist\LaunchPad.exe" (
    echo dist\LaunchPad.exe not found. Running build...
    call build.bat
    if errorlevel 1 exit /b 1
)

set "OUT=LaunchPad-Install"
if exist "%OUT%" rmdir /S /Q "%OUT%"
mkdir "%OUT%"

copy /Y "dist\LaunchPad.exe" "%OUT%\LaunchPad.exe" >nul
copy /Y "dist\ssh_askpass.exe" "%OUT%\ssh_askpass.exe" >nul
copy /Y "dist\ssh_interactive.exe" "%OUT%\ssh_interactive.exe" >nul
copy /Y "install.bat" "%OUT%\install.bat" >nul
copy /Y "create_shortcut.ps1" "%OUT%\create_shortcut.ps1" >nul

echo.
echo Package ready: %~dp0%OUT%
echo.
echo Copy this entire folder to the other computer, then run install.bat
echo   - USB drive, network share, or zip the folder and email/cloud it
echo.
echo Both LaunchPad.exe, ssh_askpass.exe, and ssh_interactive.exe must stay together.

endlocal
