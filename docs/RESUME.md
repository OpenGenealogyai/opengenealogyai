# OpenGenealogyAI — Autopilot Resume Instructions

Read this file at the start of every new session. Then check git log and continue.

## Current Status (auto-updated)

**Completed tasks (by git commit):**
- Task .1: Domain glossary, HUMAN_GATES.md, PROJECT_CHARTER.md
- Task .2: RawRecord JSON schema, AJV validator, 20 fixtures
- Task .3: Person JSON schema, AJV validator, 22 fixtures
- Task .4: TaskQueue JSON schema, AJV validator, 20 fixtures, CONFLICT_PROTOCOL.md
- Task .5: README, CONTRIBUTING, LICENSE, .gitignore

**Next task: Task .6 — Multi-model brainstorm**
- Query Grok, GPT-4, and Gemini (via API) on: business model, growth ideas, technical risks
- Synthesize into BRAINSTORM_SYNTHESIS.md in docs/
- Use OPENAI_API_KEY for GPT-4, GROK_API_KEY for Grok

**Blocked:**
- GitHub remote push: PAT lacks repo:write scope. User must go to github.com/settings/tokens and add repo scope to the fine-grained PAT, then: `git remote add origin https://github.com/garlonmaxwell-stack/opengenealogyai && git push -u origin master`

## Resume Protocol

1. `cd C:\Users\stock\dev\opengenealogyai`
2. `git log --oneline -10` — see what is done
3. `python scripts/qwen_consult.py "Resuming task X. What should I prioritize?"` — consult Qwen
4. Build the next task
5. Commit
6. Update this file

## Rules (from CLAUDE.md)

- Consult Qwen 3 before every significant decision (schema changes, agent definitions, etc.)
- Never ask Garlon questions except at Human Gates
- Hard cost cap: $50/day
- No Tier-2 data in the public repo
- Judge-agent must be built and tested before any producer agent
