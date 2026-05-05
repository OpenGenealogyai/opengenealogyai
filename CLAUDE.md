# CLAUDE.md — OpenGenealogyAI Autopilot Rules

## Mandatory: Consult Qwen 3 Before Every Significant Decision

Before implementing any of the following, run:
```bash
python scripts/qwen_consult.py "your question here"
```

**Consult Qwen on:**
- Schema field additions, removals, or type changes
- Agent role definitions and boundaries
- Confidence scoring algorithms
- Privacy gate logic
- Database schema changes
- API endpoint design
- Any decision where two approaches seem equally valid
- Before starting each new task (paste the task spec, ask "any issues with this approach?")
- After completing each task (paste the output, ask "does this meet the spec?")

**Do NOT consult Qwen on:**
- Trivial file operations (mkdir, git commit, etc.)
- Exact copy of what the spec already specifies
- Formatting and naming conventions (follow existing patterns)

## Consultation Workflow

```
1. Read task spec
2. Ask Qwen: "I'm about to build [task]. Here is the spec. Any issues or improvements?"
3. Incorporate Qwen's feedback into the implementation
4. Build the task
5. Ask Qwen: "Here is what I built. Does it match the spec? What's missing?"
6. Fix any issues Qwen identifies
7. Commit and move to next task
```

## Autopilot Rules

- Never ask Garlon questions unless it is a Human Gate (HG-4 through HG-8)
- Never commit .env to git
- Never expose is_living=true records on public endpoints
- Never write FamilySearch data to Tier-1 dataset
- Always run schema validator before committing new fixture files
- Always log API costs to agent_cost_log table
- Daily hard cap: $50/day across all API calls

## Resume Protocol

On every new session:
1. Read this file
2. Read docs/RESUME.md
3. Run: `bash "$FLOWCTL" show fn-1-opengenealogyai-4-week-agentic-build --json`
4. Find first task with status "todo" and all dependencies complete
5. Consult Qwen on the task spec
6. Build it
7. Repeat

## Project Location

- Code: C:\Users\stock\dev\opengenealogyai\
- Flow tasks: C:\Users\stock\.claude\.flow\
- Qwen: http://localhost:11434 (model: qwen3:14b)
- FLOWCTL: C:/Users/stock/.claude/plugins/cache/flow-next/flow-next/0.38.0/scripts/flowctl
