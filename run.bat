@echo off
title TrafficPulse
setlocal

:: Set project root
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

:: Configure Hadoop environment for Windows PySpark
if exist "%PROJECT_ROOT%hadoop\bin\winutils.exe" (
    set "HADOOP_HOME=%PROJECT_ROOT%hadoop"
    set "PATH=%PROJECT_ROOT%hadoop\bin;%PATH%"
)

:: Detect Python executable (.venv, venv, or system python)
if exist "%PROJECT_ROOT%.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%PROJECT_ROOT%.venv\Scripts\python.exe"
) else if exist "%PROJECT_ROOT%venv\Scripts\python.exe" (
    set "PYTHON_CMD=%PROJECT_ROOT%venv\Scripts\python.exe"
) else (
    set "PYTHON_CMD=python"
)

:: Run the unified runner (FastAPI + React Vite in a single window)
"%PYTHON_CMD%" -u "%PROJECT_ROOT%run.py" %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo TrafficPulse encountered an issue and exited with code %ERRORLEVEL%.
    pause
)
