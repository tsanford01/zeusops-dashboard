# PANEL-RECOMMENDATIONS.md
## ZeusOps Dashboard Redesign — Unified Panel Analysis

**Date**: 2026-03-23
**Panel**: UX Architect, Data Analytics Reporter, Workflow Architect
**Subject**: Operational Intelligence Dashboard Redesign
**Status**: Ready for Developer Handoff

---

# Section 1: UX Architect

## 📐 Information Architecture Proposal

### The Core Problem
The current dashboard answers "what are agents doing now?" but not "how well is the system performing?" Travis needs a **feedback loop visualization** — the flywheel that turns agent activity into visible improvement signals.

### Proposed Visual Hierarchy (Z-Pattern Reading Flow)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LEVEL 1: COMMAND BAR (Top) — Instant System Health                        │
│  ═══════════════════════════════════════════════════════════════════════   │
│  [SYSTEM PULSE]   [CI STATUS]   [PR VELOCITY]   [PIPELINE FLOW]   [ALERT]  │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LEVEL 2: THE GRID (Center-Left) — Agent Activity                          │
│  ┌─────────────────────────────────────┐  LEVEL 3: THE FLYWHEEL            │
│  │                                     │  (Center-Right)                   │
│  │      ZEUSOPS AGENT GRID             │  ┌─────────────────────────┐      │
│  │      (13 agents, current state)     │  │                         │      │
│  │                                     │  │   PIPELINE FLOW VIZ     │      │
│  │      ┌───┐ ┌───┐ ┌───┐ ┌───┐       │  │   Trello → Code → CI    │      │
│  │      │ M │ │ A │ │ C │ │ R │       │  │   → PR → Deploy         │      │
│  │      └───┘ └───┘ └───┘ └───┘       │  │                         │      │
│  │      ┌───┐ ┌───┐ ┌───┐ ┌───┐       │  │   [Animated Flow]       │      │
│  │      │ T │ │ D │ │ S │ │ O │       │  │                         │      │
│  │      └───┘ └───┘ └───┘ └───┘       │  └─────────────────────────┘      │
│  │           ...                       │                                   │
│  └─────────────────────────────────────┘                                   │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  LEVEL 4: ACTIVITY STREAM (Bottom) — Time-Based Events                     │
│  ═══════════════════════════════════════════════════════════════════════   │
│  [LIVE FEED: manager_log events, CI triggers, PR events, deploys]          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Spatial Organization Strategy

#### Zone A: Command Bar (Top 80px)
**Purpose**: Glanceable system health — answer "is everything OK?" in 2 seconds.

| Element | Width | Content | Visual Treatment |
|---------|-------|---------|------------------|
| System Pulse | 150px | Active agents / Total, overall health score | Pulsing TRON ring, green/amber/red |
| CI Status | 200px | Last 10 runs: pass/fail sparkline | Horizontal bar segments, glow on fail |
| PR Velocity | 200px | PRs opened vs merged (24h) | Dual counter with trend arrow |
| Pipeline Flow | 300px | Trello card counts per stage | Mini horizontal funnel |
| Alert Zone | 150px | Active escalations count | Red pulse if > 0, dim if clear |

#### Zone B: Agent Grid (Left 55% of main area)
**Purpose**: Preserve existing agent monitoring — who's doing what right now.

**Enhancements**:
- Add **agent performance badge** (small indicator showing job success rate)
- Add **heat glow** based on activity level (brighter = more active)
- Keep tool stream boxes but add **outcome indicator** (checkmark/X for last completed job)

#### Zone C: Flywheel Visualization (Right 45% of main area)
**Purpose**: The "make it better" loop — show the pipeline as a living system.

**Design**: Circular/semicircular flow diagram in TRON style

```
            ┌─────────────┐
        ┌───│   TRELLO    │───┐
        │   │  (Backlog)  │   │
        │   └─────────────┘   │
        ▼                     │
  ┌───────────┐               │
  │   CODE    │               │
  │ (In Dev)  │               │
  └─────┬─────┘               │
        │                     │
        ▼                     │
  ┌───────────┐               │
  │    CI     │◄──────────────┤ (Feedback loop)
  │  (Build)  │               │
  └─────┬─────┘               │
        │                     │
        ▼                     │
  ┌───────────┐               │
  │    PR     │               │
  │ (Review)  │               │
  └─────┬─────┘               │
        │                     │
        ▼                     │
  ┌───────────┐               │
  │  DEPLOY   │───────────────┘
  │  (Live)   │
  └───────────┘
```

- Each node shows count of items in that stage
- Animated particles flow between nodes (TRON light cycles concept)
- Color indicates health: cyan = flowing, amber = stuck, red = blocked
- Click a node to see breakdown

#### Zone D: Activity Stream (Bottom 120px)
**Purpose**: Time-ordered event feed — the war room ticker.

**Replaces**: Current right sidebar activity feed (reclaim horizontal space for flywheel)

**Format**: Horizontal scrolling timeline with event cards

```
◄─────────────────────────────────────────────────────────────────────────────►
│ 14:32 │ 14:31 │ 14:30 │ 14:28 │ 14:25 │ 14:22 │ 14:20 │ 14:15 │ ...
│ CI ✓  │ PR    │ DISP  │ ESCAL │ CI ✗  │ DEPLOY│ CHKPT │ PR    │
│ zeus  │ #47   │ arch  │ mgr   │ argus │ v2.1  │ coder │ #46   │
└───────┴───────┴───────┴───────┴───────┴───────┴───────┴───────┴─────────────►
```

### Visual Hierarchy Rules

1. **First glance (0-2s)**: Command bar health indicators — system OK/NOT OK
2. **Second glance (2-5s)**: Agent grid activity — who's working, what's hot
3. **Third glance (5-15s)**: Flywheel flow — where's work stuck, what's moving
4. **Deep dive (15s+)**: Activity stream — investigate specific events

### The Improvement Loop Visualization

Travis said: "You can't improve what you can't see."

The dashboard must show **causality**:

```
Agent does work → Code changes → CI validates → PR reviewed → Ships → VISIBLE OUTCOME
      ↑                                                                      │
      └──────────────────────────────────────────────────────────────────────┘
                              (Feedback informs next dispatch)
```

**Implementation**:
- When a deploy succeeds, briefly highlight the full path backward (deploy → PR → CI → commit → agent)
- Show "attribution traces" — click an agent to see their contribution to shipped code this week

### TRON Aesthetic Guidelines

| Element | TRON Treatment |
|---------|----------------|
| Healthy state | Cyan glow (#00D4FF), subtle pulse |
| Warning state | Amber glow (#FFB000), faster pulse |
| Critical state | Red glow (#FF0040), sharp pulse + sound option |
| Inactive | Dim cyan outline, no fill |
| Data flow | Animated dashed lines, particle effects |
| Containers | Beveled edges, inner shadow, glass effect |
| Typography | Monospace for data, geometric sans for labels |
| Backgrounds | Near-black (#0A0A12) with subtle grid lines |

### Responsive Considerations

**viewBox adjustment**: Expand to 1400×900 to accommodate flywheel zone.

**Priority on space constraints**:
1. Command bar always visible (collapse to icons if needed)
2. Agent grid can compress (smaller tiles)
3. Flywheel can switch to vertical layout
4. Activity stream can reduce to single-line ticker

### Component Architecture

```
css/
├── tron-variables.css    # TRON color palette, glow effects
├── dashboard-layout.css  # Grid zones, responsive breakpoints
├── components/
│   ├── command-bar.css   # Top health indicators
│   ├── agent-grid.css    # Agent tiles with enhancements
│   ├── flywheel.css      # Pipeline flow visualization
│   └── activity-stream.css # Bottom timeline
```

### Developer Implementation Notes

1. **Keep SVG for all visualizations** — continue current pattern
2. **Use CSS custom properties for theming** — already have TRON palette
3. **Animate with CSS where possible, JS for complex paths** — reduce CPU
4. **viewBox 1400×900** recommended for new layout
5. **Preserve existing agent grid code** — enhance, don't rewrite

---

# Section 2: Data Analytics Reporter

## 📈 Metrics Specification

### Core Metrics Framework

The dashboard must answer three questions at different time horizons:

| Time Horizon | Question | Primary Metrics |
|--------------|----------|-----------------|
| **Now** (real-time) | Is the system working? | Active agents, running jobs, CI status |
| **Today** (24h rolling) | How's today going? | Jobs completed, PRs merged, CI pass rate |
| **This Week** (7d) | Are we improving? | Velocity trends, failure patterns, throughput |

### Metric Definitions

#### 1. System Health Score (Real-time)
**Purpose**: Single glanceable health indicator (0-100)

**Formula**:
```
health_score = (
  (active_agents / total_agents) * 0.20 +
  (ci_pass_rate_1h) * 0.30 +
  (jobs_completed_without_failure_1h / total_jobs_1h) * 0.25 +
  (1 - escalation_rate_1h) * 0.25
) * 100
```

**Display**: Pulsing ring with numeric score
- 80-100: Green/Cyan (healthy)
- 60-79: Amber (degraded)
- 0-59: Red (critical)

**Data Sources**:
- `agent_jobs` (job success rate)
- `manager_log` where `type = 'ci_check'`
- `manager_log` where `type = 'escalation'`

#### 2. CI Status Panel

**Metrics**:
| Metric | Time Window | Source | Display |
|--------|-------------|--------|---------|
| Last run status | Most recent | GitHub Actions API | Icon (✓/✗) |
| Pass rate (1h) | Rolling 1 hour | `manager_log` type=ci_check | Percentage |
| Pass rate (24h) | Rolling 24 hours | `manager_log` type=ci_check | Sparkline |
| Streak | Since last failure | Computed | Number |

**Visualization**: Horizontal segments (10 most recent runs), glow intensity = recency

```
[✓][✓][✓][✗][✓][✓][✓][✓][✓][✓]
         ↑
    failure 4 runs ago
```

**Breakdown by repo** (on hover/click):
- zeus: pass/total (rate%)
- mission-control: pass/total (rate%)
- argus: pass/total (rate%)

#### 3. PR Velocity

**Metrics**:
| Metric | Definition | Time Window |
|--------|------------|-------------|
| PRs Opened | count of `pr_event` where action=opened | 24h rolling |
| PRs Merged | count of `pr_event` where action=merged | 24h rolling |
| PRs Failed | count of `pr_event` where action=closed (no merge) | 24h rolling |
| Merge Rate | merged / (merged + failed) | 24h rolling |
| Time to Merge | avg(merged_at - opened_at) | 24h rolling |

**Display**: Dual counter with trend
```
↑ 12 opened   ← 8 merged   (67% merge rate)
      └─ vs yesterday: +3      └─ vs yesterday: +2
```

**Threshold alerts**:
- Merge rate < 50%: amber warning
- PRs open > 20 (backlog growing): amber warning
- No merges in 4h: flag stale

#### 4. Pipeline Flow (Trello Integration)

**Metrics per stage**:
| Stage | Trello List | What to Track |
|-------|-------------|---------------|
| Backlog | "Backlog" | count, age of oldest card |
| Design | "Design" | count, avg time in stage |
| Code | "In Progress" / "Code" | count, avg time in stage |
| Review | "Review" | count, avg time in stage |
| Done | "Done" | count (this week) |

**Flow Rate**: Cards moved per stage per day (7-day average)

**Visualization**: Horizontal funnel with counts
```
Backlog → Design → Code → Review → Done
  [24]     [3]     [7]     [4]    [12]
                    ↑
              bottleneck flag
```

**Bottleneck detection**:
- If stage N has > 2x items of stage N+1 for > 24h: flag as bottleneck
- Color that stage amber

#### 5. Agent Performance Matrix

**Per-agent metrics**:
| Metric | Definition | Source |
|--------|------------|--------|
| Jobs completed (24h) | count of agent_jobs where status=done | agent_jobs |
| Success rate (7d) | done / (done + failed) | agent_jobs |
| Avg job duration | avg(completed_at - started_at) | agent_jobs |
| Tools called (24h) | count of tool invocations | session JSONL |
| Escalation rate | escalations / total_jobs | manager_log |

**Display**: Badge on each agent tile
- Green dot: >90% success, normal duration
- Amber dot: 70-90% success or slow
- Red dot: <70% success or frequent escalations

**Leaderboard** (optional panel):
```
HOTTEST THIS WEEK
1. coder     — 47 jobs, 94% success
2. architect — 32 jobs, 97% success
3. reviewer  — 28 jobs, 89% success
```

#### 6. Dispatch & Handoff Metrics

**Source**: `manager_log` type=dispatch, type=agent_checkpoint

**Metrics**:
| Metric | Definition | Display |
|--------|------------|---------|
| Dispatches today | count type=dispatch | Counter |
| Checkpoints today | count type=agent_checkpoint | Counter |
| Handoffs today | count of agent-to-agent transitions | Counter |
| Escalations today | count type=escalation | Counter (red if > 0) |

**Escalation breakdown** (on click):
```
ESCALATIONS (last 24h)
- 14:32 coder → manager: "CI failing, need guidance"
- 11:15 tester → manager: "Flaky test, unsure how to proceed"
```

#### 7. Time-Based Aggregations

| Aggregation | Granularity | Retention | Use |
|-------------|-------------|-----------|-----|
| Real-time | Per-event | Current state | Live indicators |
| Hourly | 1h buckets | 48h | Sparklines, short trends |
| Daily | 1d buckets | 30d | Week-over-week comparison |
| Weekly | 1w buckets | 12w | Trend analysis |

**Sparkline specifications**:
- 24 data points = 24 hours (1h buckets)
- Width: 100-150px
- Height: 20-30px
- Style: Area fill with glow on latest point

### Alert Thresholds

| Condition | Severity | Visual |
|-----------|----------|--------|
| CI failed 3+ times in 1h | Critical | Red pulse on CI panel |
| No agent activity for 30min | Warning | Amber pulse on agent grid |
| Escalation unresolved > 1h | Critical | Red alert badge |
| PR backlog > 10 | Warning | Amber on PR panel |
| Pipeline stage stuck > 24h | Warning | Amber on flywheel node |
| Health score < 60 | Critical | Red system pulse |

### Data Freshness Requirements

| Data | Freshness | Method |
|------|-----------|--------|
| Agent status | < 5s | SSE real-time |
| Job status | < 5s | SSE real-time |
| CI status | < 30s | Poll GitHub API |
| PR status | < 60s | Poll or webhook |
| Trello counts | < 5min | Poll Trello API |
| Aggregations | < 1min | Computed client-side from events |

### KPI Dashboard Summary View

For executive/quick view, show these 6 numbers prominently:

```
┌──────────────────────────────────────────────────────────────┐
│  ZEUSOPS WAR ROOM — OPERATIONAL INTELLIGENCE                │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────┤
│ HEALTH   │ CI TODAY │ PR MERGE │ JOBS/24h │ SHIPPED  │ALERT │
│   87     │  94%     │   67%    │   142    │    8     │  0   │
│  ████    │  ▁▃▅▇█   │  ↑12%    │  ↑vs avg │  deploys │ clear│
└──────────┴──────────┴──────────┴──────────┴──────────┴──────┘
```

---

# Section 3: Workflow Architect

## 🗺️ Data Flow Architecture

### System Context

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ZEUSOPS DASHBOARD                                 │
│                                                                             │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌────────────┐  │
│   │  Command    │    │   Agent     │    │  Flywheel   │    │  Activity  │  │
│   │    Bar      │    │    Grid     │    │    Viz      │    │   Stream   │  │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └─────┬──────┘  │
│          │                  │                  │                  │         │
│          └──────────────────┴──────────────────┴──────────────────┘         │
│                                      │                                      │
│                             ┌────────┴────────┐                             │
│                             │   STATE STORE   │                             │
│                             │  (In-Memory JS) │                             │
│                             └────────┬────────┘                             │
│                                      │                                      │
└──────────────────────────────────────┼──────────────────────────────────────┘
                                       │
          ┌────────────────────────────┼────────────────────────────┐
          │                            │                            │
          ▼                            ▼                            ▼
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│   POCKETBASE    │          │  GITHUB ACTIONS │          │     TRELLO      │
│      SSE        │          │      API        │          │      API        │
│                 │          │                 │          │                 │
│  - manager_log  │          │  - CI runs      │          │  - Card counts  │
│  - agent_jobs   │          │  - PR status    │          │  - List status  │
│                 │          │                 │          │                 │
└─────────────────┘          └─────────────────┘          └─────────────────┘
      │                              │                            │
      │ SSE (real-time)              │ Poll (30s)                 │ Poll (5min)
      │                              │                            │
      └──────────────────────────────┴────────────────────────────┘
```

### Data Source Mapping

#### Source 1: PocketBase `manager_log` (SSE Real-time)

| Event Type | Visual Element | Transform |
|------------|----------------|-----------|
| `dispatch` | Activity stream, dispatch counter | Direct append |
| `agent_checkpoint` | Activity stream, agent tile flash | Direct append |
| `ci_check` | CI panel sparkline, health score | Aggregate into 1h buckets |
| `deploy` | Activity stream, deploy counter, flywheel highlight | Direct append |
| `trello_update` | Flywheel counts (if included) | Update stage counts |
| `pr_event` | PR panel, activity stream | Update counters, append stream |
| `heartbeat` | Agent tile "alive" indicator | Update last_seen timestamp |
| `sre_alert` | Alert zone, activity stream | Priority append (top of stream) |
| `escalation` | Alert zone, activity stream, agent tile | Priority append, update agent badge |
| `subagent_start` | Agent tile nested indicator | Update agent state |
| `subagent_complete` | Agent tile nested indicator | Update agent state |

**SSE Connection Spec**:
```javascript
// Connection
const sse = new EventSource('/api/realtime');

// Event handling
sse.onmessage = (event) => {
  const record = JSON.parse(event.data);

  switch(record.collection) {
    case 'manager_log':
      handleManagerLog(record);
      break;
    case 'agent_jobs':
      handleAgentJob(record);
      break;
  }
};

// Reconnection on failure
sse.onerror = () => {
  setTimeout(() => reconnectSSE(), 5000);
  showConnectionWarning();
};
```

#### Source 2: PocketBase `agent_jobs` (SSE Real-time)

| Field | Visual Element | Transform |
|-------|----------------|-----------|
| `status = 'running'` | Agent tile active state, job timer | Set agent to active, start timer |
| `status = 'done'` | Agent tile success indicator, job counter | Increment success count, clear timer |
| `status = 'failed'` | Agent tile failure indicator, alert | Increment fail count, show warning |
| `agent` | Agent tile mapping | Map to grid position |
| `task` | Tool stream box | Display current task |
| `duration` | Agent performance metrics | Compute rolling average |

#### Source 3: GitHub Actions API (Polled every 30s)

| Endpoint | Visual Element | Transform |
|----------|----------------|-----------|
| `/repos/{owner}/{repo}/actions/runs` | CI panel, sparkline | Extract status, compute pass rate |

**Poll implementation**:
```javascript
async function pollCIStatus() {
  const repos = ['Deconstraint/zeus', 'Deconstraint/mission-control', 'Deconstraint/argus'];

  for (const repo of repos) {
    const runs = await fetch(`/api/github/runs?repo=${repo}`);
    updateCIPanel(repo, runs);
  }
}

setInterval(pollCIStatus, 30000);
```

**Rate limit consideration**: GitHub API allows 5000 requests/hour for authenticated users. Polling 3 repos every 30s = 360 requests/hour. Safe margin.

#### Source 4: Trello API (Polled every 5min)

| Endpoint | Visual Element | Transform |
|----------|----------------|-----------|
| `/boards/{id}/lists` | Flywheel stage counts | Count cards per list |

**Mapping**:
```javascript
const TRELLO_LIST_MAP = {
  'Backlog': 'backlog',
  'Design': 'design',
  'In Progress': 'code',
  'Code': 'code',
  'Review': 'review',
  'Done': 'done'
};
```

### State Management Architecture

```javascript
// Central state store
const DashboardState = {
  // Real-time state
  agents: {
    // keyed by agent_id
    'architect': { status: 'idle', lastSeen: timestamp, successRate: 0.94 },
    'coder': { status: 'active', currentJob: 'job_123', timer: 342 },
    // ...
  },

  // Aggregated metrics (computed)
  metrics: {
    healthScore: 87,
    ci: {
      passRate1h: 0.94,
      passRate24h: 0.89,
      lastRuns: [true, true, true, false, true, ...], // last 10
    },
    pr: {
      opened24h: 12,
      merged24h: 8,
      failed24h: 2,
    },
    pipeline: {
      backlog: 24,
      design: 3,
      code: 7,
      review: 4,
      done: 12,
    },
    jobs: {
      completed24h: 142,
      successRate: 0.91,
    },
  },

  // Event log (ring buffer, last 100 events)
  events: [],

  // Alert state
  alerts: {
    active: [],
    escalations: [],
  },
};

// Update functions (called by SSE/poll handlers)
function updateAgentState(agentId, update) { ... }
function appendEvent(event) { ... }
function recomputeMetrics() { ... }
function triggerAlert(alert) { ... }
```

### Event Flow Sequences

#### Sequence 1: Agent Starts Job

```
1. SSE receives agent_jobs record (status='running')
   │
   ▼
2. handleAgentJob() called
   │
   ├─► Update DashboardState.agents[agent_id].status = 'active'
   ├─► Update DashboardState.agents[agent_id].currentJob = job_id
   ├─► Start job timer in agent tile
   │
   ▼
3. Re-render agent tile
   │
   ├─► Add glow effect
   ├─► Show task description in tool stream box
   └─► Update "Active Agents" counter in command bar
```

#### Sequence 2: CI Run Completes

```
1. SSE receives manager_log (type='ci_check')
   │
   ▼
2. handleManagerLog() routes to handleCICheck()
   │
   ├─► Append to DashboardState.metrics.ci.lastRuns
   ├─► Recompute passRate1h, passRate24h
   ├─► Recompute healthScore
   │
   ▼
3. If status='failed':
   │
   ├─► Trigger alert
   ├─► Flash CI panel red
   └─► Priority append to activity stream
   │
   ▼
4. Re-render CI panel sparkline
   │
   └─► Update segment colors
```

#### Sequence 3: Escalation Received

```
1. SSE receives manager_log (type='escalation')
   │
   ▼
2. handleManagerLog() routes to handleEscalation()
   │
   ├─► Add to DashboardState.alerts.escalations
   ├─► Update DashboardState.agents[agent_id] escalation flag
   │
   ▼
3. Trigger critical alert
   │
   ├─► Red pulse on alert zone
   ├─► Red badge on agent tile
   ├─► Sound notification (if enabled)
   │
   ▼
4. Priority append to activity stream (top)
   │
   └─► Show escalation details
```

### Data Model Gaps Analysis

| Gap | Impact | Recommendation |
|-----|--------|----------------|
| **PR events not in manager_log** | Can't track PR velocity from SSE | Add `pr_event` type to manager_log OR poll GitHub PRs |
| **Trello updates sparse in manager_log** | Flywheel relies on polling | Accept 5min staleness OR add Trello webhook → manager_log |
| **No agent success rate in real-time** | Must compute from historical jobs | Pre-compute on server, include in SSE payload |
| **No session JSONL in real-time** | Tool call counts require file parsing | Add tool_call events to manager_log OR accept staleness |
| **CI run details not in manager_log** | Must poll GitHub for repo-level breakdown | Add repo field to ci_check events |
| **No explicit "deploy succeeded" event** | Can't confirm deploy completion | Add `deploy_complete` event type to manager_log |

### Recommended Data Model Additions

```javascript
// New manager_log event types needed:

// PR tracking (if not polling GitHub)
{
  type: 'pr_event',
  action: 'opened' | 'merged' | 'closed',
  pr_number: 47,
  repo: 'zeus',
  title: 'Add retry logic',
  author: 'agent:coder',
  timestamp: '2026-03-23T14:32:00Z'
}

// Deploy confirmation
{
  type: 'deploy_complete',
  environment: 'production',
  version: '2.1.0',
  status: 'success' | 'failed' | 'rollback',
  timestamp: '2026-03-23T14:35:00Z'
}

// Enriched ci_check
{
  type: 'ci_check',
  repo: 'zeus',           // ADD THIS
  run_id: 12345,          // ADD THIS
  status: 'success',
  duration_seconds: 142,  // ADD THIS
  timestamp: '2026-03-23T14:30:00Z'
}
```

### Polling Strategy Summary

| Source | Method | Interval | Rationale |
|--------|--------|----------|-----------|
| PocketBase manager_log | SSE | Real-time | Native support, low latency required |
| PocketBase agent_jobs | SSE | Real-time | Native support, low latency required |
| GitHub Actions runs | Poll | 30s | No webhook, rate limits allow |
| GitHub PRs | Poll | 60s | Unless pr_event added to manager_log |
| Trello board | Poll | 5min | Low change frequency, rate limits |

### Error Handling & Recovery

| Failure Mode | Detection | Recovery |
|--------------|-----------|----------|
| SSE disconnect | `onerror` event | Reconnect with exponential backoff (5s, 10s, 20s, max 60s) |
| SSE reconnect | `onopen` event | Request events since last_event_id to fill gap |
| GitHub API 429 | Response status | Back off for `Retry-After` header value |
| GitHub API 5xx | Response status | Retry with backoff, show "CI data stale" after 3 failures |
| Trello API failure | Fetch error | Show "Pipeline data stale", retry next interval |
| State desync suspected | Manual trigger | Full state reload from PocketBase REST API |

### Render Pipeline

```
SSE Event / Poll Result
        │
        ▼
   Parse & Validate
        │
        ▼
   Update State Store
        │
        ▼
  Mark Dirty Components
        │
        ▼
  requestAnimationFrame
        │
        ▼
  Batch DOM Updates
        │
        ▼
    Render Complete
```

**Performance considerations**:
- Batch updates within same animation frame
- Use `requestAnimationFrame` for smooth rendering
- Avoid layout thrashing by reading then writing
- Use CSS transitions for visual effects, not JS animation loops

### Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    DATA SOURCES                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐   ┌────────────┐  │
│  │   PocketBase    │   │   PocketBase    │   │  GitHub Actions │   │   Trello   │  │
│  │  manager_log    │   │   agent_jobs    │   │      API        │   │    API     │  │
│  │  (SSE stream)   │   │  (SSE stream)   │   │   (Poll 30s)    │   │ (Poll 5m)  │  │
│  └────────┬────────┘   └────────┬────────┘   └────────┬────────┘   └─────┬──────┘  │
│           │                     │                     │                  │         │
│           │ dispatch            │ status              │ runs             │ cards   │
│           │ checkpoint          │ agent               │                  │         │
│           │ ci_check            │ task                │                  │         │
│           │ deploy              │ duration            │                  │         │
│           │ escalation          │                     │                  │         │
│           │ pr_event            │                     │                  │         │
│           │ heartbeat           │                     │                  │         │
│           │                     │                     │                  │         │
└───────────┼─────────────────────┼─────────────────────┼──────────────────┼─────────┘
            │                     │                     │                  │
            ▼                     ▼                     ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              EVENT HANDLERS                                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  handleManagerLog()         handleAgentJob()       pollCI()          pollTrello()   │
│       │                          │                    │                   │         │
│       ├─► handleDispatch()       │                    │                   │         │
│       ├─► handleCheckpoint()     │                    │                   │         │
│       ├─► handleCICheck()        │                    │                   │         │
│       ├─► handleDeploy()         │                    │                   │         │
│       ├─► handleEscalation()     │                    │                   │         │
│       └─► handlePREvent()        │                    │                   │         │
│                                  │                    │                   │         │
└──────────────────────────────────┼────────────────────┼───────────────────┼─────────┘
                                   │                    │                   │
                                   ▼                    ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               STATE STORE                                           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  DashboardState = {                                                                 │
│    agents: { ... },           ◄─── agent status, jobs, timers                       │
│    metrics: {                                                                       │
│      healthScore,             ◄─── computed from all sources                        │
│      ci: { ... },             ◄─── from manager_log + GitHub poll                   │
│      pr: { ... },             ◄─── from manager_log or GitHub poll                  │
│      pipeline: { ... },       ◄─── from Trello poll                                 │
│      jobs: { ... },           ◄─── from agent_jobs stream                           │
│    },                                                                               │
│    events: [ ... ],           ◄─── ring buffer of recent events                     │
│    alerts: { ... },           ◄─── active escalations and warnings                  │
│  }                                                                                  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ state change triggers re-render
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              RENDER LAYER                                           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐        │
│  │ Command Bar  │  │  Agent Grid  │  │   Flywheel   │  │ Activity Stream  │        │
│  │              │  │              │  │              │  │                  │        │
│  │ • Health     │  │ • 13 tiles   │  │ • Stage      │  │ • Event cards    │        │
│  │ • CI spark   │  │ • Status     │  │   counts     │  │ • Timeline       │        │
│  │ • PR counts  │  │ • Timers     │  │ • Flow       │  │ • Filters        │        │
│  │ • Alerts     │  │ • Badges     │  │   animation  │  │                  │        │
│  │              │  │              │  │              │  │                  │        │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────┘        │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

# Appendix: Implementation Checklist

## Phase 1: Foundation (Week 1)
- [ ] Expand viewBox to 1400×900
- [ ] Implement new 4-zone layout (command bar, grid, flywheel, stream)
- [ ] Refactor CSS to TRON variable system
- [ ] Set up state store architecture

## Phase 2: Command Bar (Week 1-2)
- [ ] Health score calculation and display
- [ ] CI sparkline from manager_log
- [ ] PR velocity counters
- [ ] Alert zone with escalation handling

## Phase 3: Flywheel (Week 2)
- [ ] Trello API integration (poll)
- [ ] Pipeline stage visualization
- [ ] Animated flow particles
- [ ] Bottleneck detection and highlighting

## Phase 4: Enhanced Agent Grid (Week 2-3)
- [ ] Performance badges per agent
- [ ] Success rate computation
- [ ] Heat glow based on activity
- [ ] Tool stream enhancements

## Phase 5: Activity Stream (Week 3)
- [ ] Horizontal timeline layout
- [ ] Event card rendering
- [ ] Priority ordering for escalations
- [ ] Filtering and scrolling

## Phase 6: Polish (Week 3-4)
- [ ] Connection error handling
- [ ] State recovery on reconnect
- [ ] Performance optimization
- [ ] Sound notifications (optional)
- [ ] Mobile/responsive fallbacks

---

**Panel Complete**
**Ready for Developer Handoff**

*"You can't improve what you can't see." — Now you can see everything.*
