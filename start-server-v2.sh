#!/bin/bash
# Start grid-server-v2.py with credentials from gopass

set -e

echo "Loading credentials from gopass..."

export PB_URL="http://localhost:8090"
export PB_ADMIN_EMAIL=$(gopass show -o deconstraint/zeusops/pocketbase/admin-email)
export PB_ADMIN_PASS=$(gopass show -o deconstraint/zeusops/pocketbase/admin-password)
export GITHUB_TOKEN=$(gopass show -o deconstraint/github/mc-full-access)
export TRELLO_API_KEY=$(gopass show -o deconstraint/trello/api-key)
export TRELLO_TOKEN=$(gopass show -o deconstraint/trello/api-token)
export GRID_V2_PORT=8880

# Optional: override state directories
# export MC_STATE_DIR="/home/travis/.openclaw/agents/"
# export ZEUSOPS_STATE_DIR="/home/travis/.openclaw-zmc-dev-ops/agents/"

echo "Starting grid-server-v2 on port ${GRID_V2_PORT}..."
exec python3 grid-server-v2.py
