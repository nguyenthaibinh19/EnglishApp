@echo off
cd /d "%~dp0"

set "PYEXE=%USERPROFILE%\miniconda3\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

echo Dang cai PyInstaller...
"%PYEXE%" -m pip install pyinstaller
if errorlevel 1 goto :fail

echo Dang lay mat khau dev tu .env ...
"%PYEXE%" app\bundle_secrets.py
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
