@echo off
echo Starting famous people genealogy download...
echo GPU is NOT used. Downloads only.
start /LOW /B python scripts/famous_people_fetcher.py > _logs/famous_download_tonight.log 2>&1
echo Download running in background. Check _logs/famous_download_tonight.log for progress.
