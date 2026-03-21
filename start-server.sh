#!/bin/bash
PIDFILE=/tmp/zeusops-grid.pid
LOGFILE=/tmp/zeusops-grid.log
PORT=8877

# Check if already running on the port
if fuser $PORT/tcp > /dev/null 2>&1; then
    echo "Already running (port $PORT)"
    exit 0
fi

# Clean up stale PID file
rm -f "$PIDFILE"

nohup python3 /mnt/c/MC/workspace/clawd/projects/zeusops-grid/grid-server.py > "$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"
echo "ZeusOps Grid Server started (PID $!, log: $LOGFILE)"
