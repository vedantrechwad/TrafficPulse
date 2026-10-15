@echo off
title TrafficPulse - Stop Services
cls
echo ====================================================================
echo    Stopping TrafficPulse Services...
echo ====================================================================
echo.

:: Stop processes listening on port 8000 (FastAPI Backend)
echo Stopping Backend on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: Stop processes listening on port 5173 (Vite Frontend)
echo Stopping Frontend on port 5173...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo.
echo All TrafficPulse backend and frontend servers have been stopped.
echo.
timeout /t 3
