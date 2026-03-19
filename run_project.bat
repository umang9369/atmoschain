@echo off
echo =======================================================
echo ATMOSCHAIN - Launching Platform
echo =======================================================

echo Starting FastAPI Backend (Port 8000)...
start "ATMOSCHAIN Backend" cmd /k "cd /d "%~dp0" && set PYTHONPATH=%~dp0 && uvicorn backend.api.app:app --reload --port 8000"

echo Starting Next.js Frontend (Port 3000)...
start "ATMOSCHAIN Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo Both servers are starting in separate windows.
echo - Backend API: http://localhost:8000/docs
echo - Frontend UI: http://localhost:3000
echo.
pause
