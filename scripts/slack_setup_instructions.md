# How to Create a Slack Incoming Webhook
### For: Garlon Maxwell — OpenGenealogyAI Daily Reports

This gives OpenGenealogyAI permission to post the daily goal report directly into a Slack channel. Takes about 3 minutes.

---

## Step 1 — Go to your Slack workspace's app directory

Open this URL in your browser (replace `YOUR-WORKSPACE` with your actual Slack workspace name):

```
https://YOUR-WORKSPACE.slack.com/apps/manage
```

Or: In Slack, click your workspace name (top-left) → **Settings & administration** → **Manage apps**.

---

## Step 2 — Create a new app with Incoming Webhooks

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App**
3. Choose **From scratch**
4. Name it: `OpenGenealogyAI Reports`
5. Pick your workspace from the dropdown
6. Click **Create App**

---

## Step 3 — Enable Incoming Webhooks

1. On the app settings page, click **Incoming Webhooks** in the left sidebar
2. Toggle **Activate Incoming Webhooks** to **On**
3. Scroll down and click **Add New Webhook to Workspace**
4. Choose the channel where reports should post (example: `#opengenealogyai-goals` or `#general`)
5. Click **Allow**

---

## Step 4 — Copy the webhook URL

After allowing, you'll see a URL like:

```
https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX
```

Copy the entire URL.

---

## Step 5 — Add the URL to your .env file

Open `C:\Users\stock\dev\opengenealogyai\.env` and find this line:

```
SLACK_WEBHOOK_URL=
```

Paste your webhook URL after the `=` so it looks like:

```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX
```

Save the file.

---

## Test it

Run this in a terminal from the project root:

```bash
python scripts/daily_goal_reporter.py --dry-run
```

This prints the report to console without posting.

To do a live post:

```bash
python scripts/daily_goal_reporter.py
```

You should see the message appear in your chosen Slack channel within a few seconds.

---

## To run it automatically every morning

Add this to Windows Task Scheduler (or tell Claude Code to set it up):

- **Program:** `python`
- **Arguments:** `C:\Users\stock\dev\opengenealogyai\scripts\daily_goal_reporter.py`
- **Trigger:** Daily at 7:00 AM

Or run it via cron if using WSL.
