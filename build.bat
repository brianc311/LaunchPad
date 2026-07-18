@echo off
setlocal
cd /d "%~dp0"

for /f "delims=" %%V in ('python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"') do set "APP_VERSION=%%V"
echo Building LaunchPad v%APP_VERSION% ...
echo.

tasklist /FI "IMAGENAME eq LaunchPad.exe" 2>nul | find /I "LaunchPad.exe" >nul
if not errorlevel 1 (
    echo ERROR: Close LaunchPad before building.
    exit /b 1
)
tasklist /FI "IMAGENAME eq LaunchPad_latest.exe" 2>nul | find /I "LaunchPad_latest.exe" >nul
if not errorlevel 1 (
    echo ERROR: Close LaunchPad_latest.exe before building ^(do not run from dist_new^).
    exit /b 1
)

echo Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo Building LaunchPad executables...
if exist "build_new" rmdir /S /Q "build_new"
python -m PyInstaller --clean --noconfirm --distpath dist_new --workpath build_new LaunchPad.spec
if errorlevel 1 (
    echo.
    echo Build FAILED. Close LaunchPad completely, then run build.bat again.
    exit /b 1
)

if not exist "dist_new\LaunchPad_latest.exe" (
    echo Build failed - LaunchPad_latest.exe was not created.
    exit /b 1
)
if not exist "dist_new\ssh_askpass.exe" (
    echo Build failed - ssh_askpass.exe was not created.
    exit /b 1
)
if not exist "dist_new\ssh_interactive.exe" (
    echo Build failed - ssh_interactive.exe was not created.
    exit /b 1
)

if not exist "dist" mkdir "dist"
copy /Y "dist_new\LaunchPad_latest.exe" "dist\LaunchPad.exe" >nul
copy /Y "dist_new\ssh_askpass.exe" "dist\ssh_askpass.exe" >nul
copy /Y "dist_new\ssh_interactive.exe" "dist\ssh_interactive.exe" >nul

python -c "from launchpad.config import APP_VERSION; from datetime import datetime; from pathlib import Path; Path('dist/BUILD_STAMP.txt').write_text(f'LaunchPad v{APP_VERSION}\nBuilt: {datetime.now():%%Y-%%m-%%d %%H:%%M:%%S}\n', encoding='utf-8')"

echo.
echo Build complete (v%APP_VERSION%):
echo   dist\LaunchPad.exe
echo   dist\BUILD_STAMP.txt  ^(open this to confirm today's build^)
echo   dist\ssh_askpass.exe
echo   dist\ssh_interactive.exe
echo.
echo IMPORTANT: build.bat does NOT update the app you launch from Desktop.
echo Next step: close LaunchPad, then run update.bat
echo   Login screen should show: Secure connection dashboard  ·  v%APP_VERSION%
echo   (or install.bat on a fresh PC / package.bat to zip for others)

endlocal
