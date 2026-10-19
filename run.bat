@echo off
title TrafficPulse
setlocal enabledelayedexpansion

:: Set project root
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

:: Configure Hadoop environment for Windows PySpark
if exist "%PROJECT_ROOT%hadoop\bin\winutils.exe" (
    set "HADOOP_HOME=%PROJECT_ROOT%hadoop"
    set "PATH=%PROJECT_ROOT%hadoop\bin;!PATH!"
)

:: Detect Python executable (.venv, venv, or system python)
if exist "%PROJECT_ROOT%.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%PROJECT_ROOT%.venv\Scripts\python.exe"
) else if exist "%PROJECT_ROOT%venv\Scripts\python.exe" (
    set "PYTHON_CMD=%PROJECT_ROOT%venv\Scripts\python.exe"
) else (
    set "PYTHON_CMD=python"
)

:: Verify Python is available
where !PYTHON_CMD! >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo.
    echo [ERROR] Python was not found on your system!
    echo Please install Python 3.10+ or set up a virtual environment.
    echo.
    pause
    exit /b 1
)

:: Verify Node.js / npm is available
where npm >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo.
    echo [ERROR] Node.js / npm was not found on your system!
    echo Please install Node.js (v18+) to run the frontend.
    echo.
    pause
    exit /b 1
)

:: Run the unified runner (FastAPI + React Vite in a single window)
"!PYTHON_CMD!" -u "%PROJECT_ROOT%run.py" %*

:: Final cleanup safety net on script exit
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

exit /b 0
