@echo off
cd /d "%~dp0"

set "PYEXE=%USERPROFILE%\miniconda3\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

echo Dang cai PyInstaller...
"%PYEXE%" -m pip install pyinstaller
if errorlevel 1 goto :fail

echo Dang lay mat khau dev tu .env ...
"%PYEXE%" bundle_secrets.py
if errorlevel 1 goto :fail

echo Dang dong goi DutchGuard.exe ...
"%PYEXE%" -m PyInstaller DutchGuard.spec --noconfirm
if errorlevel 1 goto :fail

echo.
echo Xong: %~dp0dist\DutchGuard.exe
exit /b 0

:fail
echo Dong goi that bai.
pause
exit /b 1
