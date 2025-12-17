@echo off
REM start.bat - Quick start script for React Chat App (Windows)
REM This script starts all services and opens the browser

title React Chat App

echo.
echo ========================================
echo   React Chat App - Starting...
echo ========================================
echo.

REM Get script directory
set SCRIPT_DIR=%~dp0
cd /d %SCRIPT_DIR%

REM Check for Ollama
where ollama >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Ollama not found. Please install from https://ollama.ai
    pause
    exit /b 1
)
echo [OK] Ollama installed

REM Check if Ollama is running
curl -s http://localhost:11434/api/tags >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [INFO] Starting Ollama...
    start "" ollama serve
    timeout /t 5 >nul
)
echo [OK] Ollama running

REM Check for Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.11+
    pause
    exit /b 1
)
echo [OK] Python installed

REM Check for Node.js
where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    pause
    exit /b 1
)
echo [OK] Node.js installed

echo.
echo Setting up environment...
echo.

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo Creating Python virtual environment...
    python -m venv .venv
)

REM Activate virtual environment and install backend dependencies
echo Installing backend dependencies...
call .venv\Scripts\activate.bat
pip install -q -r backend\requirements.txt

REM Install frontend dependencies
echo Installing frontend dependencies...
cd frontend
call npm install --silent
cd ..

echo.
echo Starting services...
echo.

REM Start backend in new window
echo Starting backend server...
start "Backend - React Chat App" cmd /k "cd backend && ..\.venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8000"

REM Start frontend in new window
echo Starting frontend server...
start "Frontend - React Chat App" cmd /k "cd frontend && npm run dev"

REM Wait for services
echo.
echo Waiting for services to start...
timeout /t 10 >nul

REM Open browser
echo Opening browser...
start http://localhost:5173

echo.
echo ========================================
echo   React Chat App is running!
echo ========================================
echo.
echo   Frontend:  http://localhost:5173
echo   Backend:   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo.
echo Close the terminal windows to stop services.
echo.

pause
