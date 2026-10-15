@echo off
title TrafficPulse - Launcher
cls

echo ====================================================================
echo    TrafficPulse: Scalable Traffic Prediction ^& Simulation
echo ====================================================================
echo.
echo [1/3] Preparing environment...

:: Set project root
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

:: Configure Hadoop environment for Windows PySpark
if exist "%PROJECT_ROOT%hadoop\bin\winutils.exe" (
    set "HADOOP_HOME=%PROJECT_ROOT%hadoop"
    set "PATH=%PROJECT_ROOT%hadoop\bin;%PATH%"
)

:: Detect Python executable (.venv or system python)
if exist "%PROJECT_ROOT%.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%PROJECT_ROOT%.venv\Scripts\python.exe"
) else if exist "%PROJECT_ROOT%venv\Scripts\python.exe" (
    set "PYTHON_CMD=%PROJECT_ROOT%venv\Scripts\python.exe"
) else (
    set "PYTHON_CMD=python"
)

echo        Python: %PYTHON_CMD%
echo        Hadoop: %HADOOP_HOME%
echo.

:: Start FastAPI Backend
echo [2/3] Launching FastAPI Backend (port 8000)...
start "TrafficPulse - FastAPI Backend" cmd /k "cd /d "%PROJECT_ROOT%" && "%PYTHON_CMD%" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"

:: Start React + Vite Frontend
echo [3/3] Launching Vite Frontend (port 5173)...
start "TrafficPulse - Vite Frontend" cmd /k "cd /d "%PROJECT_ROOT%frontend" && npm run dev"

echo.
echo Waiting for services to initialize...
timeout /t 5 /nobreak >nul

:: Open browser
echo.
echo Opening TrafficPulse in default browser...
start http://127.0.0.1:5173

echo.
echo ====================================================================
echo    TrafficPulse is now RUNNING!
echo ====================================================================
echo.
echo    - Frontend Dashboard:   http://127.0.0.1:5173
echo    - FastAPI Backend:      http://127.0.0.1:8000
echo    - Swagger API Docs:     http://127.0.0.1:8000/docs
echo.
echo    Keep the backend and frontend terminal windows open.
echo    To stop TrafficPulse, simply close those terminal windows
echo    or run stop.bat.
echo ====================================================================
echo.
pause
