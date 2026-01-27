@echo off
REM AI_OS Universal Windows Launcher
REM Auto-installs dependencies and starts the system

setlocal EnableDelayedExpansion
set "REPO_ROOT=%~dp0.."
cd /d "%REPO_ROOT%"

echo.
echo ============================================
echo      AI_OS / Nola - Windows Launcher
echo ============================================
echo.

REM --- Dependency Checks & Auto-Install ---

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python not found. Attempting auto-install...
    winget install -e --id Python.Python.3.11
    if errorlevel 1 (
        echo [ERROR] Automatic install failed. Please install Python 3.11+ manually: https://python.org
        pause
        exit /b 1
    )
    REM Refresh env vars
    call refreshenv >nul 2>&1
)

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [!] Node.js not found. Attempting auto-install...
    winget install -e --id OpenJS.NodeJS
    if errorlevel 1 (
        echo [ERROR] Automatic install failed. Please install Node.js manually: https://nodejs.org
        pause
        exit /b 1
    )
)

REM Check Ollama
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [!] Ollama not found. Attempting auto-install...
    winget install -e --id Ollama.Ollama
    if errorlevel 1 (
        echo [ERROR] Automatic install failed. Please install Ollama manually: https://ollama.ai
        pause
        exit /b 1
    )
)

REM --- Environment Setup ---

set "VENV_DIR=.venv"

REM Create virtual environment if needed
if not exist "%VENV_DIR%" (
    echo [~] Creating virtual environment...
    python -m venv "%VENV_DIR%"
)

REM Activate virtual environment
call "%VENV_DIR%\Scripts\activate.bat"

REM Install Python Dependencies
echo [~] Syncing Python dependencies...
pip install -q -r requirements.txt

REM Install Frontend Dependencies
echo [~] Syncing Frontend dependencies...
cd frontend
call npm install --silent >nul 2>&1
cd ..

REM --- Start Services ---

REM Start Ollama if not running
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [~] Starting Ollama service...
    start /b ollama serve
    timeout /t 3 >nul
)

REM Pull Models
echo [~] Checking AI models...
ollama pull qwen2.5:7b >nul 2>&1
ollama pull nomic-embed-text >nul 2>&1

REM Start Backend
echo [~] Starting Backend...
start /b python -m uvicorn scripts.server:app --host 0.0.0.0 --port 8000

REM Start Frontend
echo [~] Starting Frontend...
cd frontend
start /b npm run dev
cd ..

REM Wait for startup
timeout /t 5 >nul

echo.
echo ============================================
echo   Nola is ready!
echo   Open: http://localhost:5173
echo ============================================
echo.

start http://localhost:5173
pause
