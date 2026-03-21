#!/bin/bash
PB_DIR="$HOME/.openclaw-zmc-dev-ops/pocketbase"
PB_BIN="$PB_DIR/pocketbase"
PIDFILE="$PB_DIR/pb.pid"

if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
  exit 0  # already running
fi

nohup "$PB_BIN" serve --http "0.0.0.0:8090" --dir "$PB_DIR/pb_data" \
  > "$PB_DIR/pb.log" 2>&1 &
echo $! > "$PIDFILE"
