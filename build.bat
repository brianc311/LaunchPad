@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM Normal build process: sync source from GitHub main so APP_VERSION matches
REM what was merged (avoids building a stale local tree still pinned at e.g. 1.6.156).
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo WARNING: Not a git checkout — building whatever is in this folder.
    echo Expected path example: C:\Users\Brian Colley\LaunchPad
) else (
    echo Syncing latest code from origin/main ...
    git fetch origin main
    if errorlevel 1 (
        echo ERROR: git fetch origin main failed. Check network / GitHub access.
        exit /b 1
    )
    for /f "delims=" %%B in ('git rev-parse --abbrev-ref HEAD') do set "GIT_BRANCH=%%B"
    if /I not "!GIT_BRANCH!"=="main" (
        echo.
        echo ERROR: Build must run on branch main ^(currently: !GIT_BRANCH!^).
        echo   git checkout main
        echo   git pull --ff-only origin main
        echo   build.bat
        exit /b 1
    )
    git merge --ff-only origin/main
    if errorlevel 1 (
        echo.
        echo ERROR: Could not fast-forward main to origin/main.
        echo Commit or stash local changes, then:
        echo   git pull --ff-only origin main
        exit /b 1
    )
    echo Source is up to date with origin/main.
    echo.
)

REM Drop stale bytecode so the version import cannot pick up an old .pyc
if exist "launchpad\__pycache__" rmdir /S /Q "launchpad\__pycache__" 2>nul

set "APP_VERSION="
for /f "delims=" %%V in ('python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"') do set "APP_VERSION=%%V"
if not defined APP_VERSION (
    echo ERROR: Could not read APP_VERSION from launchpad.config
    exit /b 1
)
echo Building LaunchPad v%APP_VERSION% ...
python -c "from pathlib import Path; import launchpad.config as c; print('  config:', Path(c.__file__).resolve()); print('  version:', c.APP_VERSION)"
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
