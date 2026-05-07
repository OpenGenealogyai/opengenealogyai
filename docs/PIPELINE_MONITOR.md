# Pipeline Monitor — Standing Orders

This file is for the dedicated pipeline-monitoring Claude session only.
Other sessions working on genealogy build tasks should ignore this file.

## On Every New Session Start

1. Read this file.
2. Create a recurring cron job (every 4 hours) using CronCreate:
   - cron: `17 */4 * * *`
   - durable: true
   - prompt: (see "Cron Prompt" section below)
3. Run the monitor once immediately to get a baseline.
4. Apply any action indicated by the Bottleneck Playbook.

## Cron Prompt (paste verbatim into CronCreate)

```
Run the pipeline bottleneck monitor and act on findings:
1. Run: python "D:/AI/Companies/open-genealogical-ai/scripts/bottleneck_monitor.py"
2. Read: D:/AI/Companies/open-genealogical-ai/rawdata/_logs/bottleneck_latest.json
3. Check the bottleneck field and apply the matching action from the Bottleneck Playbook in docs/PIPELINE_MONITOR.md
4. Verify the pipeline is still running by checking rawdata/_logs/gpu_heartbeat.json after any change
5. Append one line to rawdata/_logs/bottleneck_actions.log: timestamp | bottleneck | action taken | embed rate
```

## Bottleneck Playbook

| Bottleneck label | Action |
|---|---|
| `GPU_UNDERUTILIZED` | Increase `CONCURRENT_BATCHES` in `pipeline/workers/gpu_worker.py`. Start at 4, add 2 each cycle if GPU still < 50%. Max 16. Find and kill the gpu_worker subprocess so the orchestrator restarts it with the new value. |
| `GPU_SATURATED` | No action — already at max. Note the rate. |
| `CPU_BOUND` | Reduce `NUM_WORKERS` in `cpu_worker.py` from 10 toward 6. Restart cpu_workers subprocess. |
| `DATA_STARVATION` | Check fetcher logs. Verify BLM fetcher is running. Check Wikidata fetcher. Consider broadening BLM surname list. |
| `MEMORY_PRESSURE` | Reduce `NUM_WORKERS` in cpu_worker to 6. Reduce `CONCURRENT_BATCHES` in gpu_worker to 2. Restart both subprocesses. |
| `NETWORK_IDLE` | Normal. No action unless queue depth < 500. |
| `BALANCED` | No action. Log the embed rate. |

## Rules

- Never change a parameter by more than 2 steps per cycle.
- Always verify the pipeline is still running after a change (gpu_heartbeat.json updated within last 2 minutes).
- If a change causes embed rate to drop > 20%, revert it immediately.
- Log every action with timestamp to `rawdata/_logs/bottleneck_actions.log`.
- This session's only job is monitoring and tuning. Do not take on other build tasks.

## Key Files

| File | Purpose |
|---|---|
| `scripts/bottleneck_monitor.py` | Measures GPU/CPU/RAM/queue, writes bottleneck_latest.json |
| `rawdata/_logs/bottleneck_latest.json` | Most recent monitor reading |
| `rawdata/_logs/bottleneck_report.jsonl` | Full history of all monitor runs |
| `rawdata/_logs/bottleneck_actions.log` | History of tuning actions taken |
| `rawdata/_logs/gpu_heartbeat.json` | GPU worker liveness check |
| `rawdata/_checkpoints/pipeline.db` | Record counts by status |
| `pipeline/workers/gpu_worker.py` | CONCURRENT_BATCHES tuning target |
| `pipeline/workers/cpu_worker.py` | NUM_WORKERS tuning target |
