@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem Tim Python that. Khong dung "python" tren PATH neu do la stub Microsoft Store.

set "PYEXE="

if defined DUTCH_GUARD_PYTHON if exist "%DUTCH_GUARD_PYTHON%" set "PYEXE=%DUTCH_GUARD_PYTHON%"

if not defined PYEXE if exist "%USERPROFILE%\miniconda3\python.exe" set "PYEXE=%USERPROFILE%\miniconda3\python.exe"
if not defined PYEXE if exist "%USERPROFILE%\anaconda3\python.exe" set "PYEXE=%USERPROFILE%\anaconda3\python.exe"
if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

if not defined PYEXE (
    where py >nul 2>&1
    if not errorlevel 1 for /f "delims=" %%I in ('where py') do (
        echo %%I | find /i "WindowsApps" >nul || if not defined PYEXE set "PYEXE=%%I"
    )
)

if not defined PYEXE (
    where python >nul 2>&1
    if not errorlevel 1 for /f "delims=" %%I in ('where python') do (
        echo %%I | find /i "WindowsApps" >nul || if not defined PYEXE set "PYEXE=%%I"
    )
)

if not defined PYEXE (
    echo.
    echo Khong tim thay Python. Tren may nay hay dung Miniconda:
    echo     "%USERPROFILE%\miniconda3\python.exe" main.py
    echo.
    echo Hoac dat bien moi truong:
    echo     set DUTCH_GUARD_PYTHON=C:\duong\dan\python.exe
    echo.
    pause
    exit /b 1
)

echo Dang chay bang: %PYEXE%
"%PYEXE%" main.py %*
if errorlevel 1 (
    echo.
    echo App thoat voi loi. Neu thieu thu vien, chay:
    echo     "%PYEXE%" -m pip install -r requirements.txt
    pause
)
exit /b %errorlevel%
