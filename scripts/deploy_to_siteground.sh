#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy_to_siteground.sh
# Deploys the OpenGenealogyAI static site (docs/) to SiteGround via rsync/scp.
#
# BEFORE FIRST RUN:
#   1. Fill in SITEGROUND_HOST below (find it in SiteGround Site Tools →
#      SSH/SFTP → SSH Hostname — looks like "access1234.siteground.biz"
#      or a bare IP like "185.93.x.x").
#   2. Make sure your SSH public key is added in SiteGround Site Tools →
#      Devs → SSH Key Manager  —OR—  be prepared to enter the password
#      when prompted.
#   3. chmod +x deploy_to_siteground.sh
#
# USAGE:
#   ./scripts/deploy_to_siteground.sh
# ─────────────────────────────────────────────────────────────────────────────

# ── Config ────────────────────────────────────────────────────────────────────
SITEGROUND_HOST=""          # ← FILL THIS IN (e.g. access1234.siteground.biz)
SITEGROUND_USER="diamon69"
SITEGROUND_PORT=18765       # SiteGround's non-standard SSH port
REMOTE_DIR="public_html"    # destination on server (~/public_html/)

# Source directory (repo root → docs/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_DOCS="${SCRIPT_DIR}/../docs"

# ── Validation ────────────────────────────────────────────────────────────────
if [[ -z "$SITEGROUND_HOST" ]]; then
  echo "ERROR: SITEGROUND_HOST is not set."
  echo "Open this script and fill in the SITEGROUND_HOST variable."
  echo "Find it in: SiteGround Site Tools → SSH/SFTP → SSH Hostname"
  exit 1
fi

if [[ ! -d "$LOCAL_DOCS" ]]; then
  echo "ERROR: docs/ directory not found at: $LOCAL_DOCS"
  exit 1
fi

# ── Deploy ────────────────────────────────────────────────────────────────────
echo "Deploying docs/ → ${SITEGROUND_USER}@${SITEGROUND_HOST}:~/${REMOTE_DIR}/"
echo ""

rsync -avz --progress \
  --exclude="*.py" \
  --exclude=".git" \
  --exclude=".gitignore" \
  --exclude="node_modules" \
  --exclude="*.md" \
  --exclude="*.json" \
  -e "ssh -p ${SITEGROUND_PORT} -o StrictHostKeyChecking=accept-new" \
  "${LOCAL_DOCS}/" \
  "${SITEGROUND_USER}@${SITEGROUND_HOST}:~/${REMOTE_DIR}/"

EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
  echo ""
  echo "Deployment successful."
  echo "Site should be live at: https://opengenealogyai.org"
else
  echo ""
  echo "Deployment FAILED (rsync exit code: $EXIT_CODE)."
  echo ""
  echo "Troubleshooting:"
  echo "  1. Verify SITEGROUND_HOST is correct."
  echo "  2. Test SSH manually:"
  echo "     ssh -p ${SITEGROUND_PORT} ${SITEGROUND_USER}@${SITEGROUND_HOST}"
  echo "  3. If rsync is unavailable on the server, use the .bat script (WinSCP)"
  echo "     or run: scp -P ${SITEGROUND_PORT} -r docs/* ${SITEGROUND_USER}@${SITEGROUND_HOST}:~/${REMOTE_DIR}/"
  exit $EXIT_CODE
fi
