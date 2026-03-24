#!/bin/bash
cd /home/travis/projects/zeusops-dashboard-v2
python3 -m http.server 8879 --bind 0.0.0.0
