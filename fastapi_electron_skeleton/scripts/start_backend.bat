@echo off
setlocal
cd /d "%~dp0"
cd ..\backend

if not exist .venv (
    echo No virtual environment found. Run setup_backend.bat first.
    exit /b 1
)

call .venv\Scripts\activate
echo Starting FastAPI backend...
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
