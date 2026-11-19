@echo off
cd /d "%~dp0"

set "PYEXE=%USERPROFILE%\miniconda3\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

echo === Language Guard STAGING build (ADR-025) ===
echo Does NOT write to dist\langstudyguard.exe

echo Dang cai PyInstaller...
"%PYEXE%" -m pip install pyinstaller
if errorlevel 1 goto :fail

echo Dang ghi build_manifest.json (channel=staging)...
"%PYEXE%" tools\write_build_manifest.py --channel staging --output "%~dp0build_manifest.json"
if errorlevel 1 goto :fail

echo Dang lay mat khau + localhost account server tu .env ...
"%PYEXE%" app\bundle_secrets.py --channel staging
if errorlevel 1 goto :fail

if not exist "%~dp0dist-staging" mkdir "%~dp0dist-staging"

echo Dang dong goi langstudyguard-staging.exe vao dist-staging\ ...
"%PYEXE%" -m PyInstaller LangStudyGuardStaging.spec --noconfirm --distpath "%~dp0dist-staging" --workpath "%~dp0build-staging"
if errorlevel 1 goto :fail

echo Dang nen langstudyguard-staging.zip ...
if exist "%~dp0dist-staging\langstudyguard-staging.zip" del /f /q "%~dp0dist-staging\langstudyguard-staging.zip"
powershell -NoProfile -Command "Compress-Archive -LiteralPath '%~dp0dist-staging\langstudyguard-staging.exe' -DestinationPath '%~dp0dist-staging\langstudyguard-staging.zip' -Force"
if errorlevel 1 goto :fail

echo.
echo Xong: %~dp0dist-staging\langstudyguard-staging.exe
echo Zip : %~dp0dist-staging\langstudyguard-staging.zip
echo Production dist\langstudyguard.exe was NOT modified.
exit /b 0

:fail
echo Dong goi staging that bai.
pause
exit /b 1
