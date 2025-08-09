@echo off
setlocal
cd /d "%~dp0"
cd ..

REM Ensure backend is ready
call scripts\setup_backend.bat || exit /b 1

REM Node deps
if not exist node_modules (
    echo Installing Node dependencies...
    call npm install || exit /b 1
)

REM If Ollama is enabled, start it and warm the model
for /f "usebackq tokens=1,* delims==" %%A in ("backend\.env") do (
    if /I "%%A"=="OLLAMA_ENABLED" set OLLAMA_ENABLED=%%B
    if /I "%%A"=="OLLAMA_HOST" set OLLAMA_HOST=%%B
    if /I "%%A"=="OLLAMA_PORT" set OLLAMA_PORT=%%B
    if /I "%%A"=="OLLAMA_MODEL" set OLLAMA_MODEL=%%B
)

if /I "%OLLAMA_ENABLED%"=="true" (
    if "%OLLAMA_HOST%"=="" set OLLAMA_HOST=127.0.0.1
    if "%OLLAMA_PORT%"=="" set OLLAMA_PORT=11434
    if "%OLLAMA_MODEL%"=="" set OLLAMA_MODEL=gpt-oss:20b

    powershell -NoLogo -NoProfile -Command ^
        "try { iwr http://%OLLAMA_HOST%:%OLLAMA_PORT%/api/tags -TimeoutSec 2 | Out-Null; $ok=$true } catch { $ok=$false }; if (-not $ok) { Start-Process -WindowStyle Minimized cmd -ArgumentList '/c ollama serve' }"

    timeout /t 3 >nul

    powershell -NoLogo -NoProfile -Command ^
        "$body = @{ model='%OLLAMA_MODEL%'; messages=@(@{role='user'; content='warmup'}) ; stream=$false } | ConvertTo-Json; " ^
        "try { iwr -Method Post -Uri 'http://%OLLAMA_HOST%:%OLLAMA_PORT%/api/chat' -Body $body -ContentType 'application/json' -TimeoutSec 30 | Out-Null } catch { }"
)

REM Start backend in a new window
start "Backend - FastAPI" cmd /k "scripts\start_backend.bat"

REM Wait for backend health before starting Electron
echo Waiting for backend health...
:waitloop
powershell -NoLogo -NoProfile -Command ^
    "try { $r = iwr http://127.0.0.1:8000/health -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch { exit 1 }"
if errorlevel 1 (
    timeout /t 2 >nul
    goto waitloop
)

REM Launch Electron app
echo Launching Electron app...
call npm start
