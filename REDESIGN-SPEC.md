# ZeusOps Observability Dashboard v2 — Full Redesign Spec
**Date:** 2026-03-24
**Status:** Approved for build

---

## Goal
Clean full rebuild of index-v2.html. Preserve all JS data functions from current file.
All backend (grid-server-v2.py) stays unchanged — only the frontend HTML/CSS/SVG changes.

---

## Layout (1400×900 SVG viewBox)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  COMMAND BAR                                                    [●LIVE/OFFLINE] │
│  [HEALTH 87] [CI ▪▪▪▪▪▪▪▪▪▪] [↑12 PR ←8] [ALERTS 0]          70px        │
├──────────────┬──────────────────────────────────────┬──────────────────────┤
│              │                                      │                      │
│  PIPELINE    │   AGENT GRID                         │  ACTIVITY STREAM     │
│  FLOW        │                                      │                      │
│              │   ┌─ ZEUSOPS PIPELINE ─────────────┐ │  [alert card]        │
│  BACKLOG     │   │ mgr  arch  res  coder  tester  │ │  [dispatch card]     │
│  ↓ [157]     │   │ rev  rel   pm   sre   inc-mgr  │ │  [ci card]           │
│  DESIGN      │   │ wf-a dops  sec  tiger          │ │  [pr card]           │
│  ↓ [48]      │   └────────────────────────────────┘ │  [checkpoint card]   │
│  CODE        │                                      │  ...scrollable       │
│  ↓ [2]       │   ┌─ MC GATEWAY ───────────────────┐ │                      │
│  REVIEW      │   │ ● MC  ● ZEUS⚡  ● TRAVIS  ● OBR│ │  click → detail      │
│  ↓ [7]       │   └────────────────────────────────┘ │  modal overlay       │
│  DONE        │                                      │                      │
│  [85]        │   [spawn lines between active agents] │                      │
│              │                                      │                      │
│  200px       │   700px                              │  300px               │
├──────────────┴──────────────────────────────────────┴──────────────────────┤
│  TOOL STREAM — horizontal scroll, full width, 110px                         │
│  [agent] [tool] [summary...]  [agent] [tool] [summary...]  newest→left     │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Zone coordinates (SVG):**
- Command bar: x=0, y=0, w=1400, h=70
- Pipeline: x=0, y=70, w=200, h=720
- Agent grid: x=200, y=70, w=700, h=720
- Activity stream: x=900, y=70, w=500, h=720
- Tool stream: x=0, y=790, w=1400, h=110

---

## TRON Color System (unchanged)
```css
:root {
  --bg-primary: #0A0A12;
  --bg-secondary: #0D0D1A;
  --bg-panel: #0F0F1F;
  --cyan: #00D4FF;
  --cyan-dim: rgba(0,212,255,0.15);
  --amber: #FFB000;
  --red: #FF0040;
  --green: #00FF88;
  --purple: #9B59B6;
  --text-primary: #E0F4FF;
  --text-dim: #4A7A8A;
  --border: #1A2A3A;
}
```
Fonts: Orbitron (data/headings), Share Tech Mono (labels/body). Load from Google Fonts.

---

## Zone A: Command Bar (y=0-70, full width)

5 panels in a horizontal flex row:

**1. System Health (x=10, w=160)**
- Pulsing ring + score number (0-100)
- Ring color: green ≥80, amber 60-79, red <60
- "SYSTEM HEALTH" label

**2. CI Status (x=180, w=240)**
- 10 colored segments (last 10 runs, both repos combined)
  - green=success, red=failure, grey=skipped/unknown
- Pass rate % below: "94% (24h)"
- "CI STATUS" label

**3. PR Velocity (x=430, w=220)**
- "↑ N opened  ← N merged"
- Merge rate % below
- "PR VELOCITY" label

**4. Alerts (x=660, w=180)**  
- Large count of active alerts (escalation + sre_alert + wip_violation where unresolved)
- Red pulse if >0, dim cyan if 0
- "0 CLEAR" or "N ALERTS"
- "ALERTS" label

**5. Connection (x=1340, w=60) — top right**
- ● dot + "LIVE" / "OFFLINE"
- Green=SSE connected, red=disconnected

**Panel dividers:** 1px vertical lines at x=170, 420, 650, 850 — dim cyan

---

## Zone B: Pipeline Flow (x=0, y=70, w=200, h=720)

Narrow vertical strip. Background slightly different from main bg.
Right border: 1px cyan, opacity 0.2.
Title "PIPELINE" at top, Orbitron 10px cyan.

5 stage nodes stacked vertically, centered in 200px:
- Node: rounded rect, w=160, h=60, centered at x=100
- Count: Orbitron 24px
- Label: Share Tech Mono 10px
- Connector: thin animated dashed line between nodes (6px dash, 4px gap, animates downward)
- Colors: cyan=normal, amber=bottleneck (stage > 2× next stage AND count > 2), green=done

Stage → list name mapping:
```javascript
backlog: sum of board["Backlog"]
design:  sum of board["Design"]
code:    sum of board["Code/Test"] || board["🚧 In Progress"] || board["Code"]
review:  sum of board["Review"] || board["👀 Awaiting Approval"]
done:    sum of board["Done"]
```
Boards: Zeus (XkxELwmf), Argus (OLdizAcY), SRE (hPBL8oW6)

Tooltip on hover: per-board breakdown "Zeus: 119 | Argus: 21 | SRE: 17"

**Bottleneck detection:**
```javascript
function detectBottlenecks(p) {
  const stages = ["backlog","design","code","review"];
  const next = {backlog:"design", design:"code", code:"review", review:"done"};
  const result = new Set();
  for (const s of stages) {
    if (p[s] > 2 && p[s] > (p[next[s]] || 0) * 2) result.add(s);
  }
  return result;
}
```

---

## Zone C: Agent Grid (x=200, y=70, w=700, h=720)

Two sections with visual separator:

### Section 1: ZeusOps Pipeline (y=70 to ~y=640)
Label "ZEUSOPS PIPELINE" — Orbitron 9px, cyan, at top of section.
Thin cyan top border.

14 agent hex tiles in 4 columns × 4 rows (last row has 2 + MC strip):
```
Row 1 (y=105): manager  architect  researcher  coder
Row 2 (y=235): tester   reviewer   releaser    pm
Row 3 (y=365): sre      incident-manager  workflow-architect  devops-automator
Row 4 (y=495): security tiger-team  [empty]  [empty]
```

Each hex tile (w=120, h=100, centered in 175px column):
- Hexagonal SVG shape (use polygon, not circle)
- Agent name: Orbitron 9px, centered
- Status dot: bottom-left, r=4, green/amber/red
- Performance badge: top-right, r=3, green/amber/red (success rate)
- Context bar: thin bar at bottom of hex, width proportional to contextPct
  - cyan 0-70%, amber 70-90%, red >90%
- Task text: below hex, Share Tech Mono 8px, italic, current task_summary
- Glow class: glow-hot (active), glow-warm (idle), glow-dim (offline)

Status colors: active=#00FF88, idle=#FFB000, offline=dim (#4A7A8A)

### Spawn Lines Layer (behind tiles)
SVG group id="spawn-lines" rendered BEHIND agent tiles.
When handoff is active (from /data handoffs[] where active=true):
- Draw quadratic bezier from source tile center to destination tile center
- Cyan dashed line (stroke-dasharray="5,4") with animate stroke-dashoffset 1s loop
- Traveling dot: animateMotion along path, 1.5s loop, r=3
- If destination is "unknown": skip the line (don't render) — unknown means receiver detection failed
- Only render lines when BOTH from and to are known agent IDs that have tiles in the grid

### Section 2: MC Gateway (y=650 to y=720)
Label "MC GATEWAY" — Orbitron 9px, color=#9B59B6 (purple).
Thin purple top border (separates from ZeusOps section).

4 compact indicators in a row:
- Each: circle r=6 (status color) + label below
- Labels: "MC" (main), "ZEUS⚡" (zeus), "TRAVIS" (mctravis), "OBR" (obr)
- IDs: mc-dot-main, mc-dot-zeus, mc-dot-mctravis, mc-dot-obr
- Spaced evenly across 700px

---

## Zone D: Activity Stream (x=900, y=70, w=500, h=720)

Title "ACTIVITY" — Orbitron 10px, cyan.
Left border: 1px cyan, opacity 0.2.

**Vertical scroll list** — newest events at TOP.
Use SVG foreignObject with a scrollable HTML div inside (most reliable cross-browser approach).
foreignObject x=900, y=70, width=500, height=720. Inner div: overflow-y:auto, height:100%.

Each event card (w=480, h=80, margin-bottom=4px):
```
┌ [3px color border] ─────────────────────────────────────────────┐
│  [TYPE BADGE]                                    [15:32]         │
│  description text (max 2 lines, truncated)                      │
│  [context preview — key fields only, 1 line, dim]               │
└──────────────────────────────────────────────────────────────────┘
```

**Alert events get special treatment:**
For action_type in [escalation, sre_alert, wip_violation, manager_alert, scrum_alert]:
- Card height: 110px (more space)
- Red/amber left border (3px)
- Subtle red/amber background glow
- Context preview shows: severity + key metric (e.g. "doing_count: 27 | limit: 2")
- Red pulse animation on card border when fresh (<60s old)

**Type → color mapping:**
```javascript
const EVENT_COLORS = {
  dispatch:         "#00D4FF",  // cyan
  agent_checkpoint: "#00FF88",  // green
  ci_check:         null,       // green if success, red if failure (from context.result)
  pr_event:         "#7B68EE",  // purple
  trello_update:    "#00D4FF",  // cyan
  deploy:           "#00FF88",  // green
  heartbeat:        "#4A7A8A",  // dim
  escalation:       "#FF0040",  // RED — large card
  sre_alert:        "#FFB000",  // AMBER — large card
  wip_violation:    "#FF0040",  // RED — large card
  manager_alert:    "#FF0040",  // RED — large card
  scrum_alert:      "#FFB000",  // AMBER — large card
  scrum_check:      "#FFB000",  // amber
  system:           "#4A7A8A",  // dim
  tool_call:        "#4A7A8A",  // dim
};
```

**Context preview (1 line, dim):**
Parse context JSON, show 2-3 most relevant fields:
```javascript
function contextPreview(action_type, ctx) {
  if (!ctx || Object.keys(ctx).length === 0) return "";
  switch(action_type) {
    case "dispatch":   return `agent: ${ctx.agent} | task: ${(ctx.task||"").slice(0,30)}`;
    case "ci_check":   return `${ctx.repo} | branch: ${ctx.branch} | ${ctx.duration_s}s`;
    case "pr_event":   return `${ctx.repo} PR#${ctx.pr_number} | ${ctx.action}`;
    case "escalation": return `severity: ${ctx.severity} | ${JSON.stringify(ctx).slice(0,60)}`;
    case "wip_violation": return `doing: ${ctx.current_wip||ctx.doing_count} | limit: ${ctx.limit||2}`;
    case "sre_alert":  return `${ctx.severity} | ${ctx.issue||ctx.service}`;
    case "deploy":     return `${ctx.environment} | ${ctx.service} | ${ctx.result}`;
    default: return Object.entries(ctx).slice(0,2).map(([k,v])=>`${k}: ${v}`).join(" | ");
  }
}
```

**Click to expand — modal overlay:**
Full-width dark overlay. Centered panel (w=800, h=auto):
- Event type badge + timestamp
- Full description
- All context fields as key: value list
- Raw context JSON (collapsible)
- Click outside or ESC to close

**Seeding on load:** fetch /events/recent (last 20), render oldest→newest so newest is at top.
**SSE:** append new events to top as they arrive.

---

## Zone E: Tool Stream (x=0, y=790, w=1400, h=110)

Full-width horizontal strip at bottom.
Top border: 1px cyan, opacity 0.2.
Title "TOOL STREAM" left, Orbitron 9px, cyan.

Horizontal scroll, newest tools on LEFT.
Each tool card (w=200, h=85):
- Agent name: dim, 8px
- Tool name: cyan, 10px, bold
- Summary: white, 9px, up to 3 lines of ~25 chars each
- Timestamp: dim, 7px
- Left border: 2px cyan

A subtle connector line from each tool card up to its agent's hex tile position.
Line: very dim (opacity 0.12), thin (0.5px), from top of tool card to approx agent x position.

When no tool calls: "NO RECENT TOOL ACTIVITY" centered, dim.

---

## Data Sources (all from grid-server-v2.py on port 8878)

All fetch URLs use: `http://${window.location.hostname}:8878/...`

| Endpoint | Poll | Used for |
|---|---|---|
| /data | every 5s | agent status, handoffs |
| /tools | every 8s | tool stream |
| /ci | every 30s | CI sparkline, pass rate |
| /trello | every 5min | pipeline counts |
| /events/stream | SSE | activity stream live feed |
| /events/recent | on load | seed last 20 events |

---

## State Store

```javascript
const DashboardState = {
  agents: {},      // id → {status, contextPct, totalTokens, model, lastActive}
  agentStats: {},  // id → {done7d, failed7d, lastResult, runningJob}
  handoffs: [],    // [{from, to, active, startedAt}]
  metrics: {
    healthScore: 0,
    ci: { lastRuns: [], passRate: 0 },
    pr: { opened24h: 0, merged24h: 0 },
    pipeline: { backlog:0, design:0, code:0, review:0, done:0 },
    pipelineByBoard: {},
    alerts: { active: 0 },
    jobs: { completed24h: 0, successRate: 1 }
  },
  toolCalls: {},   // agentId → [{tool, summary, ts}]
  events: [],      // ring buffer max 100
  stats: {},
  connected: false
};
```

---

## Init Sequence

```javascript
async function initDashboard() {
  buildPipeline();     // creates SVG nodes
  buildAgentGrid();    // creates hex tiles + spawn line layer
  buildActivityStream();  // creates scroll container
  buildToolStream();   // creates tool card container
  buildCommandBar();   // creates indicator elements

  // Seed data — await all polls before first render
  await Promise.allSettled([pollAgentData(), pollCI(), pollTrello()]);

  // Force renders after data loaded
  render();  // master render function that calls all sub-renders

  // Seed activity stream
  await seedActivityStream();

  // Start SSE
  connectSSE();

  // Polling intervals
  setInterval(pollAgentData, 5000);
  setInterval(pollTools, 8000);
  setInterval(pollCI, 30000);
  setInterval(pollTrello, 300000);
}

function render() {
  renderCommandBar();
  renderPipeline();
  renderAgentGrid();
  renderSpawnLines();
  renderToolStream();
  // Activity stream is append-only, not re-rendered
}
```

---

## Key Constraints
- Pure SVG + vanilla JS only — NO frameworks, NO build step
- Single HTML file
- No new external dependencies (Google Fonts OK)
- All API URLs use window.location.hostname (not hardcoded localhost)
- JS must pass: `node -e "var fs=require('fs')...new Function(code)...OK"`
- git commit when done
