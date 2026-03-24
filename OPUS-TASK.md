# Opus Implementation Task — ZeusOps Grid Dashboard Refactor

You are implementing a refactor of a production real-time AI agent monitoring dashboard.
A detailed review has already been done. Your job is to implement the fixes precisely.

## Your Working Directory
`/home/travis/projects/zeusops-grid/`

## Files to Modify
- `index-tron.html` — primary target (2510 lines)
- `grid-server.py` — secondary target (611 lines)

## The Plan
Read `REFACTOR-PLAN.md` in your working directory. It has exact line numbers and exact fixes.

## What to Implement (in order)

### Phase 1 — Critical Fixes (do these first)
1. **Fix NODE_DISCOVERED TDZ** — move `const NODE_DISCOVERED = {};` from line ~2423 to before `mergeDiscoveredAgent()` function (~line 2330)
2. **Fix mcGridBuilt race** — line ~409: change `mcGridBuilt=true` to `mcGridBuilt = Object.keys(mcNodeEls).length > 0;`
3. **Delete demo packet animation** — find and delete the demoPairs block (lines ~2242-2243) — random 20% packet animation firing in production
4. **Fix thread-safety in grid-server.py** — `_tool_seen_ts` and `_mc_tool_seen_ts` need lock protection

### Phase 2 — Dead Code Removal
5. Delete `renderMobileList()` function and its call site
6. Delete legacy tool badge code (`toolBadgeBg`, `toolIconEl` creation + `updateToolIcon()`)
7. Delete duplicate `"main"` in DISCOVER_BLOCKLIST (grid-server.py)
8. Delete duplicate import in grid-server.py (inner `from datetime import datetime, timezone`)
9. Fix unreachable return in `ctxArcColor()`

### Phase 3 — MC Grid Feature Parity
10. Add timer elements (`timer1`, `timer2`, `timerBg1`, `timerBg2`) to `buildMCGrid()` node creation — mirror the ZO node timer pattern from `_buildOneNode()`
11. Update `mcNodeEls[id]` assignment to include the new timer fields
12. Update `updateTimers()` to also iterate `mcNodeEls` — so MC node timers actually update
13. Expand `updateMCNodeVis()` to include:
    - Staleness detection (call `stalenessFor(id)`, use `STALE_COLOR`/`LIKELY_DONE_COLOR`)  
    - Stale pulse animation on `el.hex`
    - Full visual state (expand triangle, glow, inner hex — same as `updateNodeVis()`)
14. Remove the `try/catch` blanket from `buildMCGrid()` OR rethrow after logging

## Constraints
- NO frameworks, NO React — pure SVG + vanilla JS
- Keep single HTML file
- Do NOT change ZO grid behavior — only fix/improve
- Do NOT change the TRON aesthetic
- After changes, verify JS parses: `node -e "const fs=require('fs'),html=fs.readFileSync('index-tron.html','utf8'),m=html.match(/<script>([\\s\\S]*?)<\\/script>/);try{new Function(m[1]);console.log('JS OK');}catch(e){console.error('ERR:',e.message);}"`

## Git Instructions
After completing all phases:
1. `git add index-tron.html grid-server.py`
2. `git commit -m "refactor: Phase 1-3 — critical fixes, dead code removal, MC grid parity"`
3. `git push deconstraint master`

## Done Signal
When completely finished (all phases committed and pushed), run:
openclaw system event --text "Done: Opus refactor complete — Phases 1-3 implemented and pushed" --mode now
