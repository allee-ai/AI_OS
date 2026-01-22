@echo off
REM AI_OS Windows Launcher
REM Requires: Python 3.11+, Node.js, Ollama

echo.
echo ============================================
echo      AI_OS / Nola - Windows Launcher
echo ============================================
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org
    pause
    exit /b 1
)
echo [OK] Python found

REM Check for Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install from https://nodejs.org
    pause
    exit /b 1
)
echo [OK] Node.js found

REM Check for Ollama
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Ollama not found. Install from https://ollama.ai
    pause
    exit /b 1
)
echo [OK] Ollama found

REM Set up directories
set REPO_ROOT=%~dp0
set CHAT_APP=%REPO_ROOT%Nola\react-chat-app
set VENV_DIR=%REPO_ROOT%.venv

REM Create virtual environment if needed
if not exist "%VENV_DIR%" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
)

REM Activate virtual environment
call "%VENV_DIR%\Scripts\activate.bat"

REM Install backend dependencies
echo Installing backend dependencies...
pip install -q -r "%CHAT_APP%\backend\requirements.txt"

REM Install frontend dependencies
echo Installing frontend dependencies...
cd "%CHAT_APP%\frontend"
call npm install --silent 2>nul
cd "%REPO_ROOT%"

REM Start Ollama if not running
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo Starting Ollama...
    start /b ollama serve
    timeout /t 3 >nul
)

REM Pull model if needed
set MODEL_NAME=qwen2.5:7b
echo Ensuring model %MODEL_NAME% is available...
ollama pull %MODEL_NAME% >nul 2>&1

REM Start backend
echo Starting backend...
cd "%CHAT_APP%\backend"
start /b python -m uvicorn main:app --host 0.0.0.0 --port 8000
cd "%REPO_ROOT%"

REM Start frontend
echo Starting frontend...
cd "%CHAT_APP%\frontend"
start /b npm run dev
cd "%REPO_ROOT%"

REM Wait for services
echo Waiting for services to start...
timeout /t 5 >nul

echo.
echo ============================================
echo   Nola is ready!
echo   Open: http://localhost:5173
echo ============================================
echo.
echo Press Ctrl+C to stop

REM Open browser
start http://localhost:5173

REM Keep window open
pause
