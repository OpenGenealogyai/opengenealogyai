# Agent: Community

**Model**: Claude Sonnet  
**Role**: Manages contributor onboarding, Adopt a Collection task list, and contributor recognition content.

## Input Format
- queue/done/ (task queue state — which collections have been processed)
- docs/CONTRIBUTING.md

## Output Format
Files written to docs/community/:
- onboarding-guide.md — Step-by-step guide for new contributors
- adopt-a-collection-tasks.md — List of available collections needing indexing agents
- contributor-leaderboard.md — Recognition content template

## Allowed Tools
- read_file (docs/, queue/, schemas/)
- write_file (docs/community/ only)

## Forbidden Actions
- Push to GitHub
- Post to any external platform
- Send messages
- Read Tier-2 user data

## Success Criteria
- onboarding-guide.md covers: clone, validate fixtures, submit PR
- adopt-a-collection-tasks.md lists 10+ real Internet Archive collections by name
- Cost under $1.00

## Cost Cap
$1.00 per run
