@echo off
:: OpenGenealogyAI — Auto-Restart Pipeline
:: Keeps the pipeline running forever. If it stops for any reason,
:: waits 60 seconds and restarts it. Press Ctrl+C twice to actually stop.
::
:: Usage: Double-click start_pipeline.bat  OR  run from a terminal

title OpenGenealogyAI Pipeline

cd /d "%~dp0"

:: Load .env if it exists (sets SLACK_BOT_TOKEN etc.)
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
    )
)

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

:loop
echo.
echo [%date% %time%] Starting OpenGenealogyAI pipeline...
python -X utf8 -m pipeline.orchestrator

set EXIT_CODE=%ERRORLEVEL%
echo.
echo [%date% %time%] Pipeline exited (code %EXIT_CODE%). Restarting in 60 seconds...
echo    Press Ctrl+C to cancel restart.
timeout /t 60 /nobreak

goto loop
