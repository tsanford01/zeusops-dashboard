# REFACTOR-PLAN.md — ZeusOps Grid Dashboard

**Reviewer:** Claude Opus
**Date:** 2026-03-23
**Files Reviewed:** `index-tron.html` (2,510 lines), `grid-server.py` (611 lines), `agents.json`

---

## Section 1: Critical Bugs (Breaking Things NOW)

### 1.1 `NODE_DISCOVERED` Temporal Dead Zone Bug (HIGHEST PRIORITY)
**Location:** `index-tron.html:2406` (use) vs `index-tron.html:2423` (declaration)
**Severity:** CRITICAL — Will crash on first discovered agent, breaking dynamic agent discovery

```javascript
// Line 2406 — USED BEFORE DECLARATION (inside mergeDiscoveredAgent)
NODE_DISCOVERED[id] = !cfg.tier;  // ReferenceError: Cannot access before initialization

// Line 2423 — DECLARED AFTER USE
const NODE_DISCOVERED = {};
```

**Problem:** JavaScript `const` has Temporal Dead Zone — accessing before declaration throws `ReferenceError`.

**Fix:** Move `const NODE_DISCOVERED = {};` to line ~2330, before `mergeDiscoveredAgent()` function definition.

---

### 1.2 MC Grid Blank on Switch
**Location:** `index-tron.html:435-532` (`buildMCGrid()`)

**Root Cause:** MC grid nodes lack critical visual update infrastructure that ZO nodes have:
- MC nodes missing `timer1`, `timer2`, `timerBg1`, `timerBg2` elements (ZO has them at lines 1254-1266)
- `updateMCNodeVis()` (lines 535-564) is incomplete compared to `updateNodeVis()` (lines 1681-1804)
- `buildMCGrid()` has a try/catch at line 531 that logs errors but doesn't propagate — silent failures

**Evidence:**
```javascript
// Line 531 - swallows errors silently
}catch(e){ console.error('buildMCGrid error:', e); }
```

**Fix Required:**
1. **FIX FLAG TIMING** — Line 409 sets `mcGridBuilt=true` BEFORE calling `buildMCGrid()`. If build fails, retry never happens:
   ```javascript
   // BROKEN (line 409):
   if(!mcGridBuilt){ buildMCGrid(); mcGridBuilt=true; }
   // FIX:
   if(!mcGridBuilt){ buildMCGrid(); mcGridBuilt = Object.keys(mcNodeEls).length > 0; }
   ```
2. Add `timer1`, `timer2`, `timerBg1`, `timerBg2` elements to MC node creation (mirror lines 1254-1266)
3. Add staleness detection to `updateMCNodeVis()` (mirror lines 1687-1693 from `updateNodeVis()`)
4. Remove try/catch or rethrow after logging to expose real failures

---

### 1.2 Thread-Safety Issue in grid-server.py
**Location:** `grid-server.py:463-464, 533-540, 554-560`

**Problem:** Global state modified without lock protection:
```python
# Lines 463-464 - declared outside lock
_tool_seen_ts = 0.0
_mc_tool_seen_ts = 0.0

# Line 533-540 - modified in request handler without lock
global _tool_seen_ts
...
_tool_seen_ts = max(c['ts'] for c in calls) / 1000.0
```

The main data cache uses `_lock`, but `_tool_seen_ts` and `_mc_tool_seen_ts` do not. Multiple concurrent requests could race.

**Fix Required:**
1. Either protect these with `_lock`, or
2. Create a separate `_tools_lock` for the tool stream state

---

### 1.3 Hardcoded PocketBase Credentials
**Location:** `index-tron.html:355-356`

**Problem:** Production credentials exposed in client-side code:
```javascript
const PB_EMAIL = 'zeus@zeusops.local';
const PB_PASS  = 'ZeusOps2026!';
```

**Severity:** HIGH — anyone viewing source can extract credentials.

**Fix Required:**
1. Move auth to server-side proxy, or
2. Use environment-based token injection, or
3. At minimum, use a read-only API key instead of admin credentials

---

## Section 2: Dead Code Inventory

### 2.1 `renderMobileList()` — Dead UX Path
**Location:** Lines 2121-2144

**Status:** Function exists and is called (line 2240), but:
- `#mobile-list` has `display:none` (line 128) with NO CSS that ever enables it
- No media query activates it
- Travis rejected this feature (per task notes)

**Action:** DELETE lines 2121-2144 and line 2240 (the call site)

---

### 2.2 `agentMeta` — FALSE POSITIVE (Actually Used)
**Location:** Line 1032

```javascript
const agentMeta= {}; // id -> {sessionCount, gateway, model}
```

**Usage:** Populated at line 2196, **IS read** in `openInspect()` at lines 1433, 1520-1521:
- `meta.sessionCount` at line 1520
- `meta.gateway` at line 1521
- `meta.model` — stored but model is also in agentData

**Action:** KEEP — this was incorrectly flagged in the known issues list. Consider consolidating into `agentData` for simplicity in a future refactor.

---

### 2.3 `hexPoints()` — Inlinable Helper
**Location:** Lines 1041-1049

```javascript
function hexPoints(cx,cy,r,flat=true){
  // only called from tronInnerHex() at line 1067
}
```

**Usage:** Called exactly once from `tronInnerHex()` at line 1067.

**Action:** INLINE into `tronInnerHex()` or KEEP if future plans require it (low priority)

---

### 2.4 Duplicate `main` in DISCOVER_BLOCKLIST
**Location:** `grid-server.py:355-364`

```python
DISCOVER_BLOCKLIST = {
    "main", "zeus", "mctravis", ...  # Line 358
    "main",  # dead ZeusOps alias     # Line 359 - DUPLICATE
    ...
}
```

**Action:** REMOVE duplicate `"main"` at line 359

---

### 2.5 Duplicate Import in grid-server.py
**Location:** Line 422-423

```python
from datetime import datetime, timezone  # Already imported at line 13
```

**Action:** REMOVE the inner import

---

### 2.6 Unused `launch()` Function Wrapper
**Location:** Line 938

```javascript
function launch(from,to){ spawnPackets(from,to); }
```

This is just a thin wrapper over `spawnPackets` with no additional logic. Called only from demo animation (line 2243).

**Action:** LOW PRIORITY — can inline to `spawnPackets()` call directly

---

### 2.7 Legacy Tool Badge Code
**Location:** Lines 1639-1644

```javascript
function updateToolIcon(id){
  // Legacy badge hidden -- dots are used now
  const el=nodeEls[id];
  if(el?.toolIcon) el.toolIcon.setAttribute('opacity','0');
  if(el?.toolBadgeBg) el.toolBadgeBg.setAttribute('opacity','0');
}
```

The function only hides elements that are never shown. The tool badge elements (`toolBadgeBg`, `toolIconEl`) at lines 1222-1223 are created but never used visually.

**Action:** REMOVE `toolBadgeBg`, `toolIconEl` from node creation AND `updateToolIcon()` function

---

### 2.8 `ctxArcColor()` Unreachable Return Statement
**Location:** Lines 1654-1676

```javascript
function ctxArcColor(baseColor,pct){
  if(pct<0.65) return baseColor;          // RETURN
  // ...
  if(pct<0.75){
    t=(pct-0.65)/0.10;[tr,tg,tb]=yellow;
  } else if(pct<0.88){
    // ...
    return`rgb(...)`;                      // RETURN
  } else {
    // ...
    return`rgb(...)`;                      // RETURN
  }
  return`rgb(${...})`;  // LINE 1675 — UNREACHABLE
}
```

**Action:** Remove unreachable return at line 1675 or restructure for clarity.

---

### 2.9 Demo Packet Animation (Production Leak)
**Location:** Lines 2242-2243

```javascript
const demoPairs=[['manager','architect'],['architect','coder'],...];
if(Math.random()<0.2){const[a,b]=demoPairs[...];launch(a,b);}
```

**Problem:** Random demo animations fire in production (20% chance per 8-second fetch cycle).

**Action:** DELETE these lines or gate behind a `const DEBUG = false;` flag.

---

## Section 3: MC Grid Fix — Exact Changes Needed

### 3.1 Add Timer Elements to MC Nodes
**Insert after line 478** (after `ctxArc` creation):

```javascript
// Timer displays (copy from ZO node pattern at lines 1254-1266)
const timerY1 = (r * 0.28).toFixed(1);
const timerY2 = (r * 0.64).toFixed(1);
const timerBg1 = svgEl('rect',{x:'-28',y:(r*0.28-12).toFixed(1),
  width:'56',height:'16',rx:'3',
  fill:'#000810',stroke:col,'stroke-width':'0.7',opacity:'0'});
const timer1 = svgEl('text',{x:'0',y:timerY1,'text-anchor':'middle',
  'font-family':'Orbitron,sans-serif','font-weight':'700','font-size':'11',
  fill:col,opacity:'0','letter-spacing':'1'});
const timerBg2 = svgEl('rect',{x:'-24',y:(r*0.64-10).toFixed(1),
  width:'48',height:'13',rx:'3',
  fill:'#000810',stroke:col,'stroke-width':'0.5',opacity:'0'});
const timer2 = svgEl('text',{x:'0',y:timerY2,'text-anchor':'middle',
  'font-family':'Orbitron,sans-serif','font-weight':'400','font-size':'9',
  fill:col,opacity:'0','letter-spacing':'0.8'});

g.appendChild(timerBg1);
g.appendChild(timer1);
g.appendChild(timerBg2);
g.appendChild(timer2);
```

**Update mcNodeEls at line 527:**
```javascript
mcNodeEls[id]={g, hex:outerTri, fill:outerFill, outerGlow, innerHex, innerFill, innerGlow,
  ctxArc, ctxArcGlow, ctxBarBg, label, pill, col, r,
  foLeft, foRight, entriesLeft, entriesRight, hdrLeft, hdrRight,
  timer1, timer2, timerBg1, timerBg2};  // ADD THESE
```

---

### 3.2 Add Staleness Detection to updateMCNodeVis()
**Replace lines 535-564** with expanded version:

```javascript
function updateMCNodeVis(id){
  const el=mcNodeEls[id];
  const ag=agentData[id]||{};
  if(!el) return;
  const col=el.col, st=ag.status||'offline', pct=(ag.contextPct||0)/100, r=el.r;
  const isActive=st==='active', isIdle=st==='idle', isOffline=st==='offline';

  // Staleness detection (mirror ZO logic from updateNodeVis lines 1687-1693)
  const staleState = stalenessFor(id);
  const isStale = staleState==='stale';
  const isLikelyDone = staleState==='likely-done';
  const effCol = isLikelyDone ? LIKELY_DONE_COLOR : isStale ? STALE_COLOR : col;

  const showActive = isActive && !isStale && !isLikelyDone;
  const showBusy = showActive || isStale || isLikelyDone;
  const expand = showBusy ? 4 : isIdle ? 1 : 0;

  // Visual updates (same pattern as updateNodeVis)
  el.hex.setAttribute('points', tronOuterTriangle(r, expand));
  el.hex.setAttribute('stroke', effCol);
  // ... (rest of visual update logic)

  // Stale pulse animation
  el.hex.style.animation = isStale ? 'stale-pulse 2.5s ease-in-out infinite' : '';
}
```

---

### 3.3 Add MC Node Timer Updates
**Modify `updateTimers()` at lines 742-789** to also iterate over `mcNodeEls`:

```javascript
function updateTimers(){
  const now = Date.now();
  // ZO nodes
  for(const[id, el] of Object.entries(nodeEls)){
    // existing logic...
  }
  // MC nodes (ADD THIS BLOCK)
  for(const[id, el] of Object.entries(mcNodeEls)){
    if(!el.timer1) continue;
    const ag = agentData[id];
    const isActive = ag?.status==='active';
    const jobs = agentTimers[id]||[];
    // Same timer display logic as ZO nodes...
  }
}
```

---

### 3.4 Remove Silent Error Swallowing
**Line 531:** Change from:
```javascript
}catch(e){ console.error('buildMCGrid error:', e); }
```
To:
```javascript
}catch(e){ console.error('buildMCGrid error:', e); throw e; }
```

Or better — remove the try/catch entirely and let errors propagate naturally during development.

---

## Section 4: ZO Grid Improvements

### 4.1 Consolidate Duplicate Status Logic
**Problem:** Status color determination is repeated in multiple places:
- `updateNodeVis()` lines 1686-1693
- `openInspect()` lines 1500-1507
- `updateCard()` lines 2153-2168
- `renderMobileList()` lines 2121-2144

**Fix:** Extract to shared helper:
```javascript
function statusColor(status, staleState=null){
  if(staleState==='likely-done') return LIKELY_DONE_COLOR;
  if(staleState==='stale') return STALE_COLOR;
  return status==='active'?'#00FF88':status==='idle'?'#FFD700':'#445566';
}
```

---

### 4.2 Consolidate Token Formatting
**Problem:** Token formatting duplicated at lines 1514-1517 and 1611-1614.

**Fix:** Extract to helper:
```javascript
function fmtTokens(n){
  if(n==null) return '—';
  if(n>=1e6) return (n/1e6).toFixed(2)+'M';
  if(n>=1e3) return (n/1e3).toFixed(1)+'K';
  return String(n);
}
```

---

### 4.3 Clean Up Inspect Panel Duplication
**Problem:** `openInspect()` (lines 1428-1560) and `refreshInspect()` (lines 1563-1617) share ~60% of the same code for building job HTML.

**Fix:** Extract job HTML builder:
```javascript
function buildJobHTML(id, jobs, col){
  const now = Date.now();
  return jobs.map(j=>{
    const elapsed = fmtElapsed(now-j.dispatchedAt);
    // ... shared logic
  }).join('');
}
```

---

## Section 5: grid-server.py Findings

### 5.1 Hardcoded Paths
**Location:** Lines 18-33

```python
GATEWAYS = {
    "mc": {
        "state_dir": "/home/travis/.openclaw/agents/",
        ...
    },
    "zeusops": {
        "state_dir": "/home/travis/.openclaw-zmc-dev-ops/agents/",
        ...
    },
}
```

**Fix:** Use environment variables or config file:
```python
import os
MC_STATE_DIR = os.environ.get('MC_STATE_DIR', '/home/travis/.openclaw/agents/')
ZO_STATE_DIR = os.environ.get('ZO_STATE_DIR', '/home/travis/.openclaw-zmc-dev-ops/agents/')
```

---

### 5.2 Comment-Disabled Receiver Detection
**Location:** Lines 250-252

```python
# Skip expensive jsonl scanning — receiver shown as unknown
# (can be improved later with cached scanning)
pass
```

This disables handoff receiver detection. The `receiver` field will always be `"unknown"`.

**Action:** Either re-enable with caching, or document as known limitation.

---

### 5.3 Missing Error Context in Exception Handlers
**Location:** Multiple places (lines 75-76, 83-84, 98-101, etc.)

```python
except Exception:
    return None  # or pass
```

**Fix:** At minimum, log the exception for debugging:
```python
except Exception as e:
    # logging.debug(f"read_json failed for {path}: {e}")
    return None
```

---

### 5.4 Unbounded _first_seen Dict Growth
**Location:** Lines 62, 255-256

```python
_first_seen: dict = {}   # handoff_id -> unix ms when first discovered
...
if handoff_id not in _first_seen:
    _first_seen[handoff_id] = now
```

This dict grows forever — old handoffs are never cleaned up.

**Fix:** Add periodic cleanup of entries older than 7 days:
```python
def cleanup_first_seen():
    cutoff = now_ms() - (7 * 24 * 60 * 60 * 1000)
    to_delete = [k for k, v in _first_seen.items() if v < cutoff]
    for k in to_delete:
        del _first_seen[k]
```

---

### 5.5 TOOL_FILTER Should Be Configurable
**Location:** Lines 384-385

```python
TOOL_FILTER = {'exec','sessions_spawn','message','web_fetch','browser','process',
               'read','write','edit','image','memory_search','web_search'}
```

This hardcoded set determines which tools appear in the stream. Should be configurable.

---

## Section 6: Prioritized Execution Plan

### Phase 1: Critical Fixes (Do First — Blocking Issues)
| Priority | Task | Location | Effort |
|----------|------|----------|--------|
| P0 | **Fix `NODE_DISCOVERED` TDZ bug** | Move line 2423 → ~2330 | 2m |
| P0 | Fix `mcGridBuilt` flag timing | Line 409 — move inside try | 5m |
| P0 | Fix MC grid blank issue — add timer elements + staleness | Lines 435-564 | 2h |
| P0 | Fix thread-safety in tool stream state | grid-server.py:463, 533, 554 | 30m |
| P1 | Remove demo packet animation | Lines 2242-2243 | 2m |
| P1 | Remove hardcoded PB credentials | Lines 355-356 | 1h |

### Phase 2: Dead Code Removal (Quick Wins)
| Priority | Task | Location | Effort |
|----------|------|----------|--------|
| P1 | Delete `renderMobileList()` + mobile-list HTML | Lines 128, 2121-2144, 2240, 345 | 15m |
| P1 | Remove duplicate `main` in blocklist | grid-server.py:359 | 2m |
| P1 | Remove duplicate import | grid-server.py:422-423 | 2m |
| P2 | Remove legacy tool badge code | Lines 1222-1223, 1639-1644 | 15m |
| P2 | Fix unreachable return in ctxArcColor | Line 1675 | 2m |

### Phase 3: MC Grid Feature Parity
| Priority | Task | Location | Effort |
|----------|------|----------|--------|
| P1 | Add elapsed timer display to MC nodes | buildMCGrid(), updateTimers() | 1h |
| P1 | Add staleness coloring to MC nodes | updateMCNodeVis() | 1h |
| P2 | Add tool icon badges to MC nodes (optional) | updateMCNodeVis() | 30m |

### Phase 4: Consolidation & Polish
| Priority | Task | Location | Effort |
|----------|------|----------|--------|
| P2 | Extract `statusColor()` helper | Multiple locations | 30m |
| P2 | Extract `fmtTokens()` helper | Lines 1514, 1611 | 15m |
| P2 | Extract `buildJobHTML()` helper | openInspect/refreshInspect | 30m |
| P2 | Inline `hexPoints()` into `tronInnerHex()` | Lines 1041-1049 | 10m |
| P3 | Make hardcoded paths configurable | grid-server.py:18-33 | 30m |

### Phase 5: Server Hardening
| Priority | Task | Location | Effort |
|----------|------|----------|--------|
| P2 | Add `_first_seen` cleanup | grid-server.py | 20m |
| P2 | Add exception logging | grid-server.py:75, 83, 98, etc. | 30m |
| P3 | Make TOOL_FILTER configurable | grid-server.py:384-385 | 20m |
| P3 | Re-enable receiver detection with caching | grid-server.py:250-252 | 2h |

---

## Summary

| Category | Count |
|----------|-------|
| Critical bugs | 5 (incl. NODE_DISCOVERED TDZ, mcGridBuilt race, thread-safety) |
| Dead code blocks | 9 (mobile list, tool badge, demo animation, unreachable code, etc.) |
| MC grid feature gaps | 6 (timers, staleness, dot, ticks, tool badge, hover) |
| ZO consolidation opportunities | 3 |
| Server issues | 5 |

**Estimated total effort:** ~10-12 hours for complete refactor

**Recommended approach:**
1. **Phase 1 first (30min-1h)** — Fix `NODE_DISCOVERED` TDZ + mcGridBuilt race immediately (blocking bugs)
2. **Phase 1 continued (2h)** — MC grid timer elements + staleness
3. **Phase 2 (30min)** — Dead code removal
4. **Phase 3 (2h)** — Full MC grid feature parity
5. **Phases 4-5** — Consolidation and server hardening as time permits

---

## Verification Checklist (Post-Implementation)

- [ ] No JS errors on page load (NODE_DISCOVERED fix verified)
- [ ] MC grid displays nodes on first switch (no blank screen)
- [ ] MC nodes show elapsed timers when jobs running
- [ ] MC nodes show staleness colors (amber → grey)
- [ ] MC tool stream boxes populate from `/tools-mc`
- [ ] ZO grid still works identically to before
- [ ] `#mobile-list` element removed from DOM
- [ ] Demo packets no longer fire randomly
- [ ] No Python exceptions in grid-server logs
- [ ] Thread-safe tool tracking (concurrent requests work)

---

*Generated by Claude Opus 4.5 — ZeusOps Dashboard Code Review*
*Reviewed: 2026-03-23*
