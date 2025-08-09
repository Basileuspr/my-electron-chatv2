@echo off
setlocal
cd /d "%~dp0"
cd ..\backend

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment. Make sure Python is installed and on PATH.
        exit /b 1
    )
)

call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install backend requirements.
    exit /b 1
)
echo Backend setup complete.
