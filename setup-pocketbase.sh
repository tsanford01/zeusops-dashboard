#!/bin/bash
# ZeusOps PocketBase Setup
# Downloads PB, starts it, creates agent_jobs + manager_log collections

set -e

PB_DIR="$HOME/.openclaw-zmc-dev-ops/pocketbase"
PB_BIN="$PB_DIR/pocketbase"
PB_URL="https://github.com/pocketbase/pocketbase/releases/download/v0.36.7/pocketbase_0.36.7_linux_amd64.zip"
PB_PORT=8090
ADMIN_EMAIL="zeus@zeusops.local"
ADMIN_PASS="ZeusOps2026!"

echo "⚡ ZeusOps PocketBase Setup"
echo "────────────────────────────────────────"

# 1. Create directory
mkdir -p "$PB_DIR"
cd "$PB_DIR"

# 2. Download if not present
if [ ! -f "$PB_BIN" ]; then
  echo "→ Downloading PocketBase v0.36.7..."
  curl -L "$PB_URL" -o pb.zip
  unzip -o pb.zip pocketbase
  rm pb.zip
  chmod +x pocketbase
  echo "✓ Downloaded"
else
  echo "✓ Binary already present"
fi

# 3. Kill any existing instance
pkill -f "pocketbase serve" 2>/dev/null && sleep 1 || true

# 4. Start PocketBase in background
echo "→ Starting PocketBase on port $PB_PORT..."
nohup "$PB_BIN" serve \
  --http "0.0.0.0:$PB_PORT" \
  --dir "$PB_DIR/pb_data" \
  > "$PB_DIR/pb.log" 2>&1 &

PB_PID=$!
echo $PB_PID > "$PB_DIR/pb.pid"

# Wait for it to be ready
echo "→ Waiting for PocketBase to start..."
for i in $(seq 1 15); do
  if curl -s "http://127.0.0.1:$PB_PORT/api/health" | grep -q '"code":200'; then
    echo "✓ PocketBase is up (PID $PB_PID)"
    break
  fi
  sleep 1
done

# 5. Create superuser account (first run only)
echo "→ Creating admin account..."
"$PB_BIN" superuser upsert "$ADMIN_EMAIL" "$ADMIN_PASS" \
  --dir "$PB_DIR/pb_data" 2>/dev/null && echo "✓ Admin account ready" || echo "  (already exists)"

# 6. Authenticate and get token
echo "→ Authenticating..."
TOKEN=$(curl -s -X POST "http://127.0.0.1:$PB_PORT/api/admins/auth-with-password" \
  -H "Content-Type: application/json" \
  -d "{\"identity\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASS\"}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  # Try superusers endpoint (PB v0.23+)
  TOKEN=$(curl -s -X POST "http://127.0.0.1:$PB_PORT/api/collections/_superusers/auth-with-password" \
    -H "Content-Type: application/json" \
    -d "{\"identity\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASS\"}" \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))" 2>/dev/null)
fi

if [ -z "$TOKEN" ]; then
  echo "⚠ Could not get auth token — collections must be created manually via UI"
  echo "  Admin UI: http://127.0.0.1:$PB_PORT/_/"
  echo "  Email: $ADMIN_EMAIL  Password: $ADMIN_PASS"
  exit 0
fi

echo "✓ Auth token obtained"

AUTH="-H \"Authorization: Bearer $TOKEN\""

# Helper: create collection
create_collection() {
  local PAYLOAD="$1"
  local NAME="$2"
  RESULT=$(curl -s -X POST "http://127.0.0.1:$PB_PORT/api/collections" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "$PAYLOAD")
  if echo "$RESULT" | grep -q '"id"'; then
    echo "✓ Collection '$NAME' created"
  elif echo "$RESULT" | grep -q 'already exists\|name.*exist'; then
    echo "✓ Collection '$NAME' already exists"
  else
    echo "⚠ '$NAME': $(echo $RESULT | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("message","unknown error"))' 2>/dev/null)"
  fi
}

# 7. Create agent_jobs
echo "→ Creating agent_jobs collection..."
create_collection '{
  "name": "agent_jobs",
  "type": "base",
  "fields": [
    {"name":"agent_name",     "type":"text",   "required":true},
    {"name":"session_id",     "type":"text",   "required":false},
    {"name":"task_summary",   "type":"text",   "required":false},
    {"name":"status",         "type":"select", "required":true, "maxSelect":1,
     "values":["queued","running","done","failed"]},
    {"name":"dispatched_at",  "type":"date",   "required":false},
    {"name":"completed_at",   "type":"date",   "required":false},
    {"name":"trello_card_url","type":"url",    "required":false},
    {"name":"result",         "type":"text",   "required":false},
    {"name":"pr_url",         "type":"url",    "required":false}
  ],
  "indexes": ["CREATE INDEX idx_agent_jobs_agent ON agent_jobs (agent_name)"],
  "listRule": "",
  "viewRule": "",
  "createRule": "",
  "updateRule": "",
  "deleteRule": ""
}' "agent_jobs"

# 8. Create manager_log
echo "→ Creating manager_log collection..."
create_collection '{
  "name": "manager_log",
  "type": "base",
  "fields": [
    {"name":"action_type",  "type":"text", "required":true},
    {"name":"description",  "type":"text", "required":true},
    {"name":"context",      "type":"json", "required":false}
  ],
  "listRule": "",
  "viewRule": "",
  "createRule": "",
  "updateRule": "",
  "deleteRule": ""
}' "manager_log"

# 9. Enable CORS for localhost dashboard
echo ""
echo "────────────────────────────────────────"
echo "✅ PocketBase is ready!"
echo ""
echo "  API:       http://localhost:$PB_PORT/api/"
echo "  Admin UI:  http://localhost:$PB_PORT/_/"
echo "  Email:     $ADMIN_EMAIL"
echo "  Password:  $ADMIN_PASS"
echo "  PID file:  $PB_DIR/pb.pid"
echo "  Logs:      $PB_DIR/pb.log"
echo ""
echo "  Collections: agent_jobs, manager_log"
echo "  Dashboard will connect automatically."
echo ""
echo "  To stop:  kill \$(cat $PB_DIR/pb.pid)"
echo "  To start: $PB_BIN serve --http 127.0.0.1:$PB_PORT --dir $PB_DIR/pb_data"
