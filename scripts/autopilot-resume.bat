@echo off
REM OpenGenealogyAI autopilot resume ? launched by Task Scheduler every 30 min
REM Opens a new Claude Code session that reads RESUME.md and continues building

set PROJECT_DIR=C:\Users\stock\dev\opengenealogyai
set RESUME_PROMPT=You are in autopilot mode for OpenGenealogyAI. Read CLAUDE.md and RESUME.md in %PROJECT_DIR% then immediately continue the next incomplete task without asking any questions. Do not greet or explain ? just build.

REM Check if claude CLI is available
where claude >nul 2>&1
if errorlevel 1 (
    echo Claude CLI not found ? skipping autopilot resume
    exit /b 1
)

REM Launch Claude Code in the project directory with the resume prompt
cd /d %PROJECT_DIR%
claude --print "%RESUME_PROMPT%" >> "%PROJECT_DIR%\logs\autopilot.log" 2>&1
