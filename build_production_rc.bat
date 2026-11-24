@echo off
cd /d "%~dp0"

set "PYEXE=%USERPROFILE%\miniconda3\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

echo === Language Guard PRODUCTION RELEASE CANDIDATE ===
echo Writes ONLY to dist-rc\ — does NOT touch dist\langstudyguard.exe

echo Dang ghi build_manifest.json (channel=production)...
"%PYEXE%" tools\write_build_manifest.py --channel production --output "%~dp0build_manifest.json"
if errorlevel 1 goto :fail

echo Dang ghi cau hinh phat hanh, khong lay mat khau khan cap...
"%PYEXE%" app\bundle_secrets.py --channel production
if errorlevel 1 goto :fail

if not exist "%~dp0dist-rc" mkdir "%~dp0dist-rc"

echo Dang dong goi langstudyguard-rc.exe ...
"%PYEXE%" -m PyInstaller DutchGuard.spec --noconfirm --distpath "%~dp0dist-rc" --workpath "%~dp0build-rc"
if errorlevel 1 goto :fail

if exist "%~dp0dist-rc\langstudyguard.exe" (
  move /y "%~dp0dist-rc\langstudyguard.exe" "%~dp0dist-rc\langstudyguard-rc.exe" >nul
)

echo Dang nen langstudyguard-rc.zip ...
if exist "%~dp0dist-rc\langstudyguard-rc.zip" del /f /q "%~dp0dist-rc\langstudyguard-rc.zip"
powershell -NoProfile -Command "Compress-Archive -LiteralPath '%~dp0dist-rc\langstudyguard-rc.exe' -DestinationPath '%~dp0dist-rc\langstudyguard-rc.zip' -Force"
if errorlevel 1 goto :fail

echo.
echo RC EXE: %~dp0dist-rc\langstudyguard-rc.exe
echo RC ZIP: %~dp0dist-rc\langstudyguard-rc.zip
echo Production dist\ artifacts were NOT modified.
exit /b 0

:fail
echo Production RC build failed.
pause
exit /b 1
