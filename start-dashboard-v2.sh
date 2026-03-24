#!/bin/bash
# ZeusOps Dashboard v2 — managed by systemd (auto-restart on crash)
# Install: cp zeusops-dashboard.service ~/.config/systemd/user/
#          systemctl --user daemon-reload && systemctl --user enable zeusops-dashboard

case "${1:-status}" in
  start)   systemctl --user start zeusops-dashboard.service ;;
  stop)    systemctl --user stop zeusops-dashboard.service ;;
  restart) systemctl --user restart zeusops-dashboard.service ;;
  status)  systemctl --user status zeusops-dashboard.service ;;
  logs)    journalctl --user -u zeusops-dashboard.service -f ;;
esac
