# ZeusOps Dashboard

Real-time monitoring dashboard for the ZeusOps AI agent network.

## Dashboards

### `index-tron.html` — 2D TRON Edition (primary)
Flat circuit board aesthetic. SVG-based, no WebGL dependencies.
- 13 ZeusOps agent nodes in hexagonal cells across 4 tiers (COMMAND / ENGINEERING / OPS / INTEL)
- Orthogonal PCB-style circuit traces with directional pulse animation
- Data packets animate along dispatch paths
- Context window heat map: arc color shifts base → yellow → orange → red as context fills
- Tool use badges (EXC / AI / SPN / etc.) appear inside hex on tool calls, fade after 10s
- Agent labels elevated to top SVG layer — never occluded by glow or traces

### `index-3d.html` — 3D Edition (alternate)
Three.js force-directed graph. Same data pipeline, 3D sphere nodes with bloom post-processing.

## Backend

### `grid-server.py`
HTTP server (port 8877) that aggregates agent status from two OpenClaw gateways:
- **MC gateway** — main, mctravis, zeus, obr
- **ZeusOps gateway** — manager, architect, pm, sre, coder, reviewer, tester, releaser, researcher, incident-manager, devops-automator, security, workflow-architect

### PocketBase (port 8090)
Stores live job dispatch records (`agent_jobs`) and activity log (`manager_log`).
Dashboard subscribes via SSE for real-time updates.

## Running

```bash
# Start everything
./start-dashboard.sh

# Or individually
python3 grid-server.py          # Agent status API on :8877
python3 -m http.server 8878     # Serve dashboard HTML on :8878
./start-pocketbase.sh           # PocketBase on :8090
```

Then open: http://localhost:8878/index-tron.html

## Agent Status Logic

| Source | Priority | Used for |
|--------|----------|----------|
| PocketBase `agent_jobs` | High | Active job overrides (running → active) |
| OpenClaw gateway sessions | Base | Status, context %, last active time |

Agents with `running` jobs in PocketBase show as active on the grid regardless of gateway session state.

## Architecture

```
OpenClaw MC Gateway  ──┐
                        ├── grid-server.py (:8877) ──── Dashboard HTML
OpenClaw ZeusOps GW ──┘

PocketBase (:8090) ─── SSE + polling ──── Activity feed + job dispatch
```
