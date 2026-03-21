#!/bin/bash
PIDFILE=/tmp/zeusops-dashboard.pid
LOGFILE=/tmp/zeusops-dashboard.log

if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
  exit 0  # already running
fi

cd /mnt/c/MC/workspace/clawd/projects/zeusops-grid
nohup python3 -m http.server 8878 --bind 0.0.0.0 > "$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"
echo "ZeusOps Dashboard started (PID $!, log: $LOGFILE)"
