@echo off
chcp 65001 >nul
title TikTok HD Downloader

echo ==========================================================
echo       🚀 Đang khởi động TikTok HD Downloader...
echo ==========================================================

cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM Kiểm tra python trong PATH hoặc thư mục mặc định
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else (
    echo [X] Khong tim thay Python tren he thong!
    echo [!] Vui long cai dat Python 3.10 tro len de su dung.
    pause
    exit /b 1
)

REM Kiểm tra môi trường ảo venv
if not exist "venv\Scripts\python.exe" (
    echo [*] Dang tao moi truong ao Python (venv)...
    "%PYTHON_CMD%" -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo [X] Loi khi tao moi truong ao.
        pause
        exit /b 1
    )
    echo [*] Dang cai dat cac thu vien can thiet...
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    python -m pip install -r backend\requirements.txt
) else (
    call venv\Scripts\activate.bat
)

REM Chạy chương trình
python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Chuong trinh bi dung lai do co loi.
    pause
)
