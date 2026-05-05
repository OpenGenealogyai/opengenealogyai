# RESUME.md — Autopilot Resume Instructions

When a new Claude Code session starts, read this file FIRST.

## Current Project
OpenGenealogyAI — C:\Users\stock\dev\opengenealogyai\

## Epic
fn-1-opengenealogyai-4-week-agentic-build

## How to Check Where We Are
```bash
FLOWCTL="C:/Users/stock/.claude/plugins/cache/flow-next/flow-next/0.38.0/scripts/flowctl"
bash "$FLOWCTL" show fn-1-opengenealogyai-4-week-agentic-build --json
```
Find the first task with status "todo" that has all dependencies done. Start there.

## How to Resume
1. Read the task spec for the next todo task
2. Build what the spec describes
3. Commit to git in C:\Users\stock\dev\opengenealogyai\
4. Move to the next task
5. Repeat until all 25 tasks are done
6. Then: push to GitHub, enable GitHub Pages, done.

## Rules
- Never ask Garlon questions unless it is a Human Gate (HG-1 through HG-8)
- .env is at C:\Users\stock\dev\opengenealogyai\.env — never commit it
- All API keys are in .env — load them before making API calls
- Push to GitHub only after Garlon signs in (HG-4)

## What Has Been Built So Far
Check git log: cd C:\Users\stock\dev\opengenealogyai && git log --oneline
