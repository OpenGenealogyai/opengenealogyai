@echo off
REM OpenGenealogyAI Autopilot Resume Script
REM This runs when the previous Claude session ran out of context.
REM It opens a new Claude Code session with a resume prompt.

set RESUME_PROMPT="You are running OpenGenealogyAI autopilot. The previous session ended. Resume immediately: read C:\Users\stock\.claude\.flow\specs\fn-1-opengenealogyai-4-week-agentic-build.md and C:\Users\stock\dev\opengenealogyai\docs\RESUME.md to understand current state, then continue executing tasks in order. Do not ask questions. Do not wait for input. Build everything."

REM Open Claude Code with the resume prompt
claude --print "%RESUME_PROMPT%"
