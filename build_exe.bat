@echo off
cd /d "%~dp0"

set "PYEXE=%USERPROFILE%\miniconda3\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

echo Dang cai PyInstaller...
"%PYEXE%" -m pip install pyinstaller
if errorlevel 1 goto :fail

echo Dang ghi build_manifest.json (channel=production)...
"%PYEXE%" tools\write_build_manifest.py --channel production --output "%~dp0build_manifest.json"
if errorlevel 1 goto :fail

echo Dang ghi cau hinh phat hanh, khong lay mat khau khan cap...
"%PYEXE%" app\bundle_secrets.py --channel production
if errorlevel 1 goto :fail

echo Dang dong goi langstudyguard.exe ...
"%PYEXE%" -m PyInstaller DutchGuard.spec --noconfirm
if errorlevel 1 goto :fail

echo Dang nen langstudyguard.zip ...
if exist "%~dp0dist\langstudyguard.zip" del /f /q "%~dp0dist\langstudyguard.zip"
powershell -NoProfile -Command "Compress-Archive -LiteralPath '%~dp0dist\langstudyguard.exe' -DestinationPath '%~dp0dist\langstudyguard.zip' -Force"
if errorlevel 1 goto :fail

echo.
echo Xong: %~dp0dist\langstudyguard.exe
echo Zip : %~dp0dist\langstudyguard.zip
exit /b 0

:fail
echo Dong goi that bai.
pause
exit /b 1
