@echo off
setlocal
cd /d "%~dp0"

echo Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo Building LaunchPad executables...
python -m PyInstaller --noconfirm --distpath dist_new --workpath build_new LaunchPad.spec

if not exist "dist_new\LaunchPad_latest.exe" (
    echo Build failed - LaunchPad_latest.exe was not created.
    exit /b 1
)
if not exist "dist_new\ssh_askpass.exe" (
    echo Build failed - ssh_askpass.exe was not created.
    exit /b 1
)

if not exist "dist" mkdir "dist"
copy /Y "dist_new\LaunchPad_latest.exe" "dist\LaunchPad.exe" >nul
copy /Y "dist_new\ssh_askpass.exe" "dist\ssh_askpass.exe" >nul

echo.
echo Build complete:
echo   dist\LaunchPad.exe
echo   dist\ssh_askpass.exe
echo.
echo Next: run package.bat to create a folder you can copy to another PC.

endlocal
