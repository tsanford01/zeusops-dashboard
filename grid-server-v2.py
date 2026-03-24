#!/usr/bin/env python3
"""ZeusOps Grid Dashboard v2 — Data Server
Listens on http://localhost:8880 (configurable via GRID_V2_PORT).
Serves existing endpoints (/data, /tools, /agents, /check-pid) plus:
  - /ci: GitHub Actions CI status
  - /trello: Trello board stats
  - /events/stream: SSE proxy for PocketBase realtime

Pure Python stdlib only (no pip installs).
"""

import json
import os
import re
import sys
import time
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone
from queue import Queue, Empty

# ── Configuration ─────────────────────────────────────────────────────────────

SERVER_PORT = int(os.environ.get("GRID_V2_PORT", "8880"))
REFRESH_INTERVAL = 5  # seconds for agent data refresh

# Read credentials from environment (required)
PB_URL = os.environ.get("PB_URL", "http://localhost:8090")
PB_ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "")
PB_ADMIN_PASS = os.environ.get("PB_ADMIN_PASS", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
TRELLO_API_KEY = os.environ.get("TRELLO_API_KEY", "")
TRELLO_TOKEN = os.environ.get("TRELLO_TOKEN", "")

# Gateway paths with env var support
MC_STATE_DIR = os.environ.get("MC_STATE_DIR", "/home/travis/.openclaw/agents/")
ZEUSOPS_STATE_DIR = os.environ.get("ZEUSOPS_STATE_DIR", "/home/travis/.openclaw-zmc-dev-ops/agents/")

GATEWAYS = {
    "mc": {
        "state_dir": MC_STATE_DIR,
        "agents": ["main", "mctravis", "zeus", "obr"],
        "faction": "mc",
    },
    "zeusops": {
        "state_dir": ZEUSOPS_STATE_DIR,
        "agents": [
            "manager",
            "architect", "pm", "sre", "releaser",
            "coder", "tester", "reviewer", "researcher",
            "incident-manager", "workflow-architect", "devops-automator",
        ],
        "faction": "zeusops",
    },
}

# Agent name → canonical id (for receiver detection from jsonl)
AGENT_NAME_MAP = {
    "manager":            "manager",
    # Note: 'main' is NOT aliased to manager — MC 'main' and ZeusOps 'manager' are separate
    "architect":          "architect",
    "pm":                 "pm",
    "project manager":    "pm",
    "sre":                "sre",
    "site reliability":   "sre",
    "releaser":           "releaser",
    "coder":              "coder",
    "tester":             "tester",
    "reviewer":           "reviewer",
    "researcher":         "researcher",
    "incident manager":   "incident-manager",
    "incident-manager":   "incident-manager",
    "workflow architect": "workflow-architect",
    "workflow-architect": "workflow-architect",
    "devops automator":   "devops-automator",
    "devops-automator":   "devops-automator",
    "devops":             "devops-automator",
}

TOOL_FILTER = {'exec','sessions_spawn','message','web_fetch','browser','process',
               'read','write','edit','image','memory_search','web_search'}

DISCOVER_BLOCKLIST = {
    # MC-side agents (not ZeusOps)
    "main", "zeus", "mctravis", "obr", "obr-team", "claude-code",
    # ZeusOps ghost sessions
    "main",  # dead ZeusOps alias — real manager is under 'manager'
    # Dev/test artifacts
    "test", "test-minimal", "master", "sc", "system",
    # Boot/utility stubs
    "janitor", "reality-checker",
}

# CI and Trello polling intervals
CI_POLL_INTERVAL = 30  # seconds
TRELLO_POLL_INTERVAL = 300  # 5 minutes

# GitHub repos to monitor
GITHUB_REPOS = [
    "Deconstraint/zeus",
    "Deconstraint/argus",
]

# Trello boards to monitor
TRELLO_BOARDS = {
    "Zeus": "XkxELwmf",
    "Argus": "OLdizAcY",
    "SRE": "hPBL8oW6",
}

# ── Shared state ──────────────────────────────────────────────────────────────

_lock = threading.Lock()
_cache: dict = {}
_first_seen: dict = {}   # handoff_id -> unix ms when first discovered

_tools_lock = threading.Lock()
_tool_seen_ts = 0.0
_mc_tool_seen_ts = 0.0

_pb_lock = threading.Lock()
_pb_token: str = ""
_pb_token_ts: float = 0.0
PB_TOKEN_TTL = 3600  # 1 hour, re-auth before expiry

_ci_lock = threading.Lock()
_ci_cache: dict = {"repos": {}, "lastUpdated": 0}

_trello_lock = threading.Lock()
_trello_cache: dict = {"boards": {}, "lastUpdated": 0}

_sse_clients: list = []  # list of Queue objects for SSE clients
_sse_lock = threading.Lock()

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str):
    """Log with timestamp to stderr."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", file=sys.stderr, flush=True)


def now_ms() -> int:
    return int(time.time() * 1000)


def read_json(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def parse_iso_ms(ts_str: str):
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


def read_jsonl_head(path: str, max_lines: int = 40) -> list:
    result = []
    try:
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                line = line.strip()
                if line:
                    try:
                        result.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        pass
    return result


def detect_receiver(objects: list) -> str:
    """Scan jsonl objects to identify which agent was spawned."""
    for obj in objects:
        msg = obj.get("message", {})
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "user":
            continue
        content = msg.get("content", [])
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            text = block.get("text", "")
            # Look for "## AgentName —" pattern in subagent task header
            m = re.search(r"##\s+([A-Za-z][A-Za-z0-9 \-]+?)(?:\s*[—–|]|\n|$)", text)
            if m:
                raw = m.group(1).strip().lower()
                for pattern, agent_id in AGENT_NAME_MAP.items():
                    if pattern in raw:
                        return agent_id
    return "unknown"


def get_handoff_meta(state_dir: str, parent_agent: str, session_id: str):
    """Return (receiver_id, start_ts_ms) by reading the subagent's jsonl file."""
    jsonl_path = os.path.join(state_dir, parent_agent, "sessions", f"{session_id}.jsonl")
    objects = read_jsonl_head(jsonl_path)

    # Start timestamp from first "session" record
    start_ts = None
    for obj in objects:
        if obj.get("type") == "session":
            ts_str = obj.get("timestamp")
            if ts_str:
                start_ts = parse_iso_ms(ts_str)
            break

    receiver = detect_receiver(objects)
    return receiver, start_ts


# ── PocketBase Auth ───────────────────────────────────────────────────────────

def pb_auth() -> str:
    """Authenticate with PocketBase and return access token. Cached with TTL."""
    global _pb_token, _pb_token_ts

    with _pb_lock:
        # Return cached token if still valid
        if _pb_token and (time.time() - _pb_token_ts) < PB_TOKEN_TTL:
            return _pb_token

    if not PB_ADMIN_EMAIL or not PB_ADMIN_PASS:
        log("ERROR: PB_ADMIN_EMAIL or PB_ADMIN_PASS not set")
        return ""

    try:
        url = f"{PB_URL}/api/collections/_superusers/auth-with-password"
        payload = json.dumps({
            "identity": PB_ADMIN_EMAIL,
            "password": PB_ADMIN_PASS
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            token = data.get("token", "")

            with _pb_lock:
                _pb_token = token
                _pb_token_ts = time.time()

            log("PocketBase auth successful")
            return token
    except Exception as e:
        log(f"PocketBase auth failed: {e}")
        return ""


def pb_request(path: str, method: str = "GET", data: dict = None) -> dict:
    """Make authenticated request to PocketBase. Re-auth on 401."""
    token = pb_auth()
    if not token:
        return {}

    url = f"{PB_URL}{path}"

    try:
        if data:
            payload = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=payload, method=method)
            req.add_header("Content-Type", "application/json")
        else:
            req = urllib.request.Request(url, method=method)

        req.add_header("Authorization", token)

        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            # Token expired, re-auth and retry once
            log("PocketBase 401, re-authenticating...")
            with _pb_lock:
                global _pb_token
                _pb_token = ""
            token = pb_auth()
            if not token:
                return {}

            # Retry request
            try:
                if data:
                    payload = json.dumps(data).encode("utf-8")
                    req = urllib.request.Request(url, data=payload, method=method)
                    req.add_header("Content-Type", "application/json")
                else:
                    req = urllib.request.Request(url, method=method)

                req.add_header("Authorization", token)

                with urllib.request.urlopen(req, timeout=10) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as retry_e:
                log(f"PocketBase retry failed: {retry_e}")
                return {}
        else:
            log(f"PocketBase request failed: {e}")
            return {}
    except Exception as e:
        log(f"PocketBase request error: {e}")
        return {}


# ── Core data computation (preserved from grid-server.py) ─────────────────────

def compute_data() -> dict:
    all_agents = []
    all_handoffs = []
    gateway_status = {}
    now = now_ms()

    for gw_id, gw_cfg in GATEWAYS.items():
        state_dir = gw_cfg["state_dir"]
        faction = gw_cfg["faction"]
        has_any = False

        for agent_id in gw_cfg["agents"]:
            sessions_path = os.path.join(state_dir, agent_id, "sessions", "sessions.json")
            sessions = read_json(sessions_path) or {}
            if sessions:
                has_any = True

            # Filter to sessions with updatedAt
            valid = {k: v for k, v in sessions.items()
                     if isinstance(v, dict) and v.get("updatedAt")}

            if not valid:
                all_agents.append({
                    "id": agent_id,
                    "gateway": gw_id,
                    "faction": faction,
                    "status": "offline",
                    "lastActive": None,
                    "totalTokens": 0,
                    "contextTokens": 0,
                    "contextPct": 0,
                    "model": None,
                    "sessionCount": len(sessions),
                    "activeSession": None,
                })
                continue

            # Most recently updated session
            sorted_s = sorted(valid.items(), key=lambda x: x[1]["updatedAt"], reverse=True)
            active_key, active_v = sorted_s[0]
            last_active = active_v["updatedAt"]
            age_min = (now - last_active) / 60_000

            # Also check jsonl file mtime — updates while agent is mid-stream
            jsonl_path = active_v.get("sessionFile") or ""
            jsonl_age_min = 999
            if jsonl_path and os.path.exists(jsonl_path):
                jsonl_mtime_ms = os.path.getmtime(jsonl_path) * 1000
                jsonl_age_min = (now - jsonl_mtime_ms) / 60_000

            effective_age = min(age_min, jsonl_age_min)

            if effective_age <= 10:
                status = "active"
            elif effective_age <= 120:
                status = "idle"
            else:
                status = "offline"

            total_tokens = sum((v.get("totalTokens") or 0) for v in sessions.values())
            # totalTokens = tokens used in current session, contextTokens = max window size
            used_tokens = active_v.get("totalTokens") or 0
            max_ctx = active_v.get("contextTokens") or 200_000
            ctx_tokens = max_ctx  # keep for output field
            # Only report ctx% if session is active or idle (≤120 min)
            # Offline agents show 0% — their last-known value is stale and misleading
            if status == "offline":
                ctx_pct = 0
            else:
                ctx_pct = min(100, round(used_tokens / max_ctx * 100)) if max_ctx else 0
            model = active_v.get("model")

            all_agents.append({
                "id": agent_id,
                "gateway": gw_id,
                "faction": faction,
                "status": status,
                "lastActive": last_active,
                "totalTokens": total_tokens,
                "contextTokens": ctx_tokens,
                "contextPct": ctx_pct,
                "model": model,
                "sessionCount": len(sessions),
                "activeSession": active_key,
            })

            # ── Handoff detection ──────────────────────────────────────────
            for skey, sv in sessions.items():
                m = re.match(r"^agent:([^:]+):subagent:([0-9a-f\-]+)$", skey)
                if not m:
                    continue

                parent = m.group(1)
                uuid = m.group(2)
                handoff_id = f"{gw_id}:{parent}:{uuid}"
                session_id = sv.get("sessionId") if isinstance(sv, dict) else None

                receiver = "unknown"
                started_at = sv.get("updatedAt", now) if isinstance(sv, dict) else now

                # Skip expensive jsonl scanning — receiver shown as unknown
                # (can be improved later with cached scanning)
                pass

                # Track first-seen time for "new" detection
                if handoff_id not in _first_seen:
                    _first_seen[handoff_id] = now

                is_active = (now - (sv.get("updatedAt", 0) or 0)) < 10 * 60_000 \
                    if isinstance(sv, dict) else False

                all_handoffs.append({
                    "id": handoff_id,
                    "from": parent,
                    "to": receiver,
                    "sessionKey": skey,
                    "startedAt": started_at,
                    "firstSeenAt": _first_seen[handoff_id],
                    "active": is_active,
                })

        gateway_status[gw_id] = {"online": has_any}

    # Deduplicate handoffs by id (keep latest startedAt)
    seen_ids: dict = {}
    for h in all_handoffs:
        hid = h["id"]
        if hid not in seen_ids or h["startedAt"] > seen_ids[hid]["startedAt"]:
            seen_ids[hid] = h
    all_handoffs = list(seen_ids.values())

    # ── Stats ──────────────────────────────────────────────────────────────────
    total_sessions = sum(a["sessionCount"] for a in all_agents)
    active_count = sum(1 for a in all_agents if a["status"] == "active")
    total_tokens = sum(a["totalTokens"] for a in all_agents)

    today_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_ms = int(today_dt.timestamp() * 1000)
    handoffs_today = sum(1 for h in all_handoffs if h["startedAt"] >= today_ms)

    hottest_name = "-"
    if all_agents:
        hottest = max(all_agents, key=lambda a: a["totalTokens"])
        raw_id = hottest["id"]
        hottest_name = AGENT_NAME_MAP.get(raw_id, raw_id)

    last_event = "no handoffs yet"
    if all_handoffs:
        last_h = max(all_handoffs, key=lambda h: h["startedAt"])
        age_s = (now - last_h["startedAt"]) / 1000
        if age_s < 60:
            ago = "just now"
        elif age_s < 3600:
            ago = f"{int(age_s / 60)}m ago"
        elif age_s < 86400:
            ago = f"{int(age_s / 3600)}h ago"
        else:
            ago = f"{int(age_s / 86400)}d ago"
        last_event = f"{last_h['from']} → {last_h['to']} {ago}"

    return {
        "timestamp": now,
        "gateways": gateway_status,
        "agents": all_agents,
        "handoffs": all_handoffs,
        "stats": {
            "totalSessions": total_sessions,
            "activeSessions": active_count,
            "handoffsToday": handoffs_today,
            "totalTokensBurned": total_tokens,
            "hottestAgent": hottest_name,
            "lastEventDesc": last_event,
        },
    }


# ── Agent discovery (preserved from grid-server.py) ───────────────────────────

AGENTS_JSON_PATH = os.path.join(os.path.dirname(__file__), "agents.json")

def load_agents_config() -> dict:
    """Load agents.json; return {} on failure."""
    try:
        with open(AGENTS_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {}


def discover_agents(known_ids: set) -> list:
    """Scan ZeusOps gateway dir for agent IDs not in agents.json."""
    all_known = set(known_ids) | DISCOVER_BLOCKLIST
    for gw_cfg in GATEWAYS.values():
        all_known.update(gw_cfg.get("agents", []))

    discovered = []
    # Only scan ZeusOps gateway — MC agents belong to a different grid
    zeusops_dir = GATEWAYS["zeusops"]["state_dir"]
    if os.path.isdir(zeusops_dir):
        for name in os.listdir(zeusops_dir):
            if name in all_known or name.startswith("."):
                continue
            if os.path.isdir(os.path.join(zeusops_dir, name)):
                discovered.append(name)
    return sorted(set(discovered))


# ── Tool call scanning (preserved from grid-server.py) ────────────────────────

def tail_tool_calls(state_dir: str, since_ms: float) -> list:
    """Scan newest jsonl per agent, return tool calls newer than since_ms."""
    results = []
    if not os.path.isdir(state_dir):
        return results
    for agent_name in os.listdir(state_dir):
        sessions_dir = os.path.join(state_dir, agent_name, "sessions")
        if not os.path.isdir(sessions_dir):
            continue
        # Newest jsonl only
        jsonls = sorted(
            [os.path.join(sessions_dir, f) for f in os.listdir(sessions_dir) if f.endswith('.jsonl')],
            key=os.path.getmtime, reverse=True
        )
        if not jsonls:
            continue
        newest = jsonls[0]
        # Only if modified in last 15 minutes
        if (time.time() - os.path.getmtime(newest)) > 900:
            continue
        try:
            with open(newest, 'r', errors='replace') as fh:
                lines = fh.readlines()[-120:]  # last 120 lines
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                ts_raw = obj.get('timestamp', 0)
                # timestamp is ISO string e.g. "2026-03-21T07:35:07.369Z"
                if isinstance(ts_raw, str):
                    try:
                        from datetime import datetime, timezone
                        ts = datetime.fromisoformat(ts_raw.replace('Z','+00:00')).timestamp() * 1000
                    except Exception:
                        ts = 0
                else:
                    ts = float(ts_raw) if ts_raw else 0
                if ts < since_ms:
                    continue
                msg = obj.get('message', {})
                if not isinstance(msg, dict):
                    continue
                content = msg.get('content', [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get('type') not in ('toolCall', 'tool_use'):
                        continue
                    tool_name = block.get('name') or block.get('tool','')
                    if tool_name not in TOOL_FILTER:
                        continue
                    args = block.get('arguments') or block.get('input') or {}
                    summary = ''
                    if tool_name == 'exec':
                        summary = str(args.get('command',''))[:60]
                    elif tool_name == 'sessions_spawn':
                        summary = str(args.get('task',''))[:60]
                    elif tool_name == 'web_fetch':
                        summary = str(args.get('url',''))[:60]
                    results.append({
                        'agent': agent_name,
                        'tool': tool_name,
                        'summary': summary,
                        'args': args,  # full args for rich detail in tool stream boxes
                        'ts': ts,
                    })
        except Exception:
            continue
    return results


# ── Background refresh thread (preserved from grid-server.py) ─────────────────

def refresh_loop():
    while True:
        try:
            data = compute_data()
            with _lock:
                _cache.clear()
                _cache.update(data)
        except Exception as e:
            log(f"refresh error: {e}")
        time.sleep(REFRESH_INTERVAL)


# ── CI Poller (GitHub Actions) ────────────────────────────────────────────────

def fetch_github_runs(repo: str) -> list:
    """Fetch last 10 workflow runs from GitHub Actions API."""
    if not GITHUB_TOKEN:
        return []

    try:
        url = f"https://api.github.com/repos/{repo}/actions/runs?per_page=10"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
        req.add_header("Accept", "application/vnd.github.v3+json")

        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("workflow_runs", [])
    except Exception as e:
        log(f"GitHub API error for {repo}: {e}")
        return []


def check_ci_run_exists(run_id: int) -> bool:
    """Check if CI run already exists in manager_log."""
    try:
        # Query manager_log for ci_check with this run_id
        path = f'/api/collections/manager_log/records?filter=action_type="ci_check"&perPage=100&sort=-created'
        records = pb_request(path)

        for item in records.get("items", []):
            context_str = item.get("context", "{}")
            try:
                context = json.loads(context_str)
                if context.get("run_id") == run_id:
                    return True
            except Exception:
                pass
        return False
    except Exception as e:
        log(f"Error checking CI run existence: {e}")
        return False


def write_ci_log(repo: str, branch: str, run_id: int, status: str, duration_s: int):
    """Write CI event to manager_log via PocketBase."""
    try:
        context = {
            "repo": repo,
            "branch": branch,
            "run_id": run_id,
            "result": status,
            "duration_s": duration_s
        }

        record = {
            "action_type": "ci_check",
            "description": f"CI {status} on {repo} ({branch}) in {duration_s}s",
            "context": json.dumps(context)
        }

        pb_request("/api/collections/manager_log/records", method="POST", data=record)
        log(f"Logged CI event: {repo} run {run_id} {status}")
    except Exception as e:
        log(f"Failed to write CI log: {e}")


def ci_poll_loop():
    """Background thread that polls GitHub Actions every 30s."""
    while True:
        try:
            ci_data = {"repos": {}, "lastUpdated": int(time.time())}

            for repo in GITHUB_REPOS:
                runs = fetch_github_runs(repo)
                if not runs:
                    continue

                # Process most recent run
                recent_runs = []
                for run in runs[:10]:
                    status = run.get("conclusion") or run.get("status", "unknown")
                    run_id = run.get("id")
                    created_at = run.get("created_at", "")
                    updated_at = run.get("updated_at", "")
                    branch = run.get("head_branch", "unknown")

                    # Calculate duration
                    duration_s = 0
                    try:
                        if created_at and updated_at:
                            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                            duration_s = int((updated - created).total_seconds())
                    except Exception:
                        pass

                    recent_runs.append({
                        "status": status,
                        "run_id": run_id,
                        "created_at": created_at,
                        "duration_s": duration_s,
                        "branch": branch
                    })

                    # Check if this is a new run we haven't logged yet
                    if run == runs[0]:  # Only log most recent run
                        if not check_ci_run_exists(run_id):
                            write_ci_log(repo, branch, run_id, status, duration_s)

                # Update cache
                if recent_runs:
                    ci_data["repos"][repo] = {
                        "lastRun": recent_runs[0],
                        "recentRuns": recent_runs
                    }

            # Update global cache
            with _ci_lock:
                _ci_cache.clear()
                _ci_cache.update(ci_data)

        except Exception as e:
            log(f"CI poll error: {e}")

        time.sleep(CI_POLL_INTERVAL)


# ── Trello Poller ─────────────────────────────────────────────────────────────

def fetch_trello_board(board_id: str) -> dict:
    """Fetch lists and card counts from Trello board."""
    if not TRELLO_API_KEY or not TRELLO_TOKEN:
        return {}

    try:
        url = f"https://api.trello.com/1/boards/{board_id}/lists?cards=open&key={TRELLO_API_KEY}&token={TRELLO_TOKEN}"
        req = urllib.request.Request(url)

        with urllib.request.urlopen(req, timeout=15) as resp:
            lists = json.loads(resp.read().decode("utf-8"))

            # Count cards per list
            counts = {}
            for lst in lists:
                list_name = lst.get("name", "Unknown")
                cards = lst.get("cards", [])

                # Map to canonical stage names (fuzzy matching)
                canonical = list_name
                name_lower = list_name.lower()
                if "backlog" in name_lower or "todo" in name_lower:
                    canonical = "Backlog"
                elif "design" in name_lower or "plan" in name_lower:
                    canonical = "Design"
                elif "code" in name_lower or "dev" in name_lower or "test" in name_lower:
                    canonical = "Code/Test"
                elif "review" in name_lower or "qa" in name_lower:
                    canonical = "Review"
                elif "done" in name_lower or "complete" in name_lower:
                    canonical = "Done"

                counts[canonical] = len(cards)

            return counts
    except Exception as e:
        log(f"Trello API error for board {board_id}: {e}")
        return {}


def write_trello_log(board_name: str, list_name: str, old_count: int, new_count: int):
    """Write Trello update to manager_log."""
    try:
        context = {
            "board": board_name,
            "list": list_name,
            "old_count": old_count,
            "new_count": new_count
        }

        record = {
            "action_type": "trello_update",
            "description": f"Board {board_name}: {list_name} {old_count}→{new_count}",
            "context": json.dumps(context)
        }

        pb_request("/api/collections/manager_log/records", method="POST", data=record)
        log(f"Logged Trello update: {board_name} {list_name} {old_count}→{new_count}")
    except Exception as e:
        log(f"Failed to write Trello log: {e}")


def trello_poll_loop():
    """Background thread that polls Trello boards every 5 minutes."""
    last_counts = {}  # board_name -> {list_name: count}

    while True:
        try:
            trello_data = {"boards": {}, "lastUpdated": int(time.time())}

            for board_name, board_id in TRELLO_BOARDS.items():
                counts = fetch_trello_board(board_id)
                if not counts:
                    continue

                trello_data["boards"][board_name] = counts

                # Compare with last known counts
                if board_name in last_counts:
                    for list_name, new_count in counts.items():
                        old_count = last_counts[board_name].get(list_name, 0)
                        if old_count != new_count:
                            write_trello_log(board_name, list_name, old_count, new_count)

                last_counts[board_name] = counts

            # Update global cache
            with _trello_lock:
                _trello_cache.clear()
                _trello_cache.update(trello_data)

        except Exception as e:
            log(f"Trello poll error: {e}")

        time.sleep(TRELLO_POLL_INTERVAL)


# ── SSE Proxy for PocketBase Realtime ─────────────────────────────────────────

def sse_broadcast(event_data: str):
    """Broadcast SSE event to all connected clients."""
    with _sse_lock:
        dead_clients = []
        for client_queue in _sse_clients:
            try:
                client_queue.put(event_data, block=False)
            except Exception:
                dead_clients.append(client_queue)

        # Remove dead clients
        for dead in dead_clients:
            _sse_clients.remove(dead)


def pb_sse_listener():
    """Background thread that listens to PocketBase SSE and broadcasts to clients."""
    while True:
        try:
            token = pb_auth()
            if not token:
                log("SSE: No PB token, waiting 30s...")
                time.sleep(30)
                continue

            # Connect to PocketBase realtime endpoint
            url = f"{PB_URL}/api/realtime"
            req = urllib.request.Request(url)
            req.add_header("Authorization", token)

            log("SSE: Connecting to PocketBase realtime...")

            with urllib.request.urlopen(req, timeout=None) as resp:
                log("SSE: Connected to PocketBase")

                # Read SSE stream
                for line in resp:
                    line_str = line.decode("utf-8", errors="replace")

                    # SSE format: "data: {json}\n"
                    if line_str.startswith("data:"):
                        event_data = line_str[5:].strip()
                        if event_data:
                            # Broadcast to all connected clients
                            sse_broadcast(f"data: {event_data}\n\n")
                    elif line_str.strip() == "":
                        # Empty line = end of event
                        pass

        except Exception as e:
            log(f"SSE listener error: {e}")

        # Reconnect after delay
        log("SSE: Reconnecting in 5s...")
        time.sleep(5)


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class GridHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default access log

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        # ── Existing endpoints (preserved) ────────────────────────────────────

        if path == "/data":
            with _lock:
                body = json.dumps(_cache, default=str).encode("utf-8")
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except BrokenPipeError:
                pass

        elif path == "/check-pid":
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            pid_list = qs.get("pid", [])
            result = {}
            for pid_str in pid_list:
                try:
                    pid = int(pid_str)
                    os.kill(pid, 0)
                    result[pid_str] = True
                except (ProcessLookupError, ValueError):
                    result[pid_str] = False
                except PermissionError:
                    result[pid_str] = True  # exists but not owned by us
            body = json.dumps(result).encode("utf-8")
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except BrokenPipeError:
                pass

        elif path == "/agents":
            try:
                cfg = load_agents_config()
                known = set(cfg.keys())
                new_ids = discover_agents(known)
                result = {"registered": cfg, "discovered": new_ids}
                body = json.dumps(result).encode("utf-8")
            except Exception as e:
                body = json.dumps({"registered": {}, "discovered": [], "error": str(e)}).encode("utf-8")
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except BrokenPipeError:
                pass

        elif path == "/tools":
            global _tool_seen_ts
            try:
                with _tools_lock:
                    since = _tool_seen_ts
                # Only scan ZeusOps gateway
                calls = tail_tool_calls(ZEUSOPS_STATE_DIR, since * 1000)
                if calls:
                    with _tools_lock:
                        _tool_seen_ts = max(c['ts'] for c in calls) / 1000.0
                body = json.dumps(calls).encode("utf-8")
            except Exception as e:
                body = json.dumps([]).encode("utf-8")
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except BrokenPipeError:
                pass

        elif path == "/tools-mc":
            global _mc_tool_seen_ts
            try:
                with _tools_lock:
                    since = _mc_tool_seen_ts
                calls = tail_tool_calls(MC_STATE_DIR, since * 1000)
                if calls:
                    with _tools_lock:
                        _mc_tool_seen_ts = max(c['ts'] for c in calls) / 1000.0
                body = json.dumps(calls).encode("utf-8")
            except Exception as e:
                body = json.dumps([]).encode("utf-8")
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except BrokenPipeError:
                pass

        # ── New endpoints ─────────────────────────────────────────────────────

        elif path == "/ci":
            with _ci_lock:
                body = json.dumps(_ci_cache, default=str).encode("utf-8")
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except BrokenPipeError:
                pass

        elif path == "/trello":
            with _trello_lock:
                body = json.dumps(_trello_cache, default=str).encode("utf-8")
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except BrokenPipeError:
                pass

        elif path == "/events/stream":
            # SSE endpoint
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                # Create queue for this client
                client_queue = Queue()
                with _sse_lock:
                    _sse_clients.append(client_queue)

                # Send initial connection event
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()

                last_keepalive = time.time()

                # Stream events to client
                while True:
                    try:
                        # Get event from queue with timeout
                        event = client_queue.get(timeout=5)
                        self.wfile.write(event.encode("utf-8"))
                        self.wfile.flush()
                        last_keepalive = time.time()
                    except Empty:
                        # No event, send keep-alive if needed
                        if time.time() - last_keepalive > 15:
                            self.wfile.write(b": keepalive\n\n")
                            self.wfile.flush()
                            last_keepalive = time.time()

            except Exception as e:
                # Client disconnected
                with _sse_lock:
                    if client_queue in _sse_clients:
                        _sse_clients.remove(client_queue)

        else:
            # Static file serving — serve from the working directory
            serve_path = path.lstrip("/") or "index-v2.html"
            # Redirect bare / to index-v2.html
            if path == "/" or path == "":
                serve_path = "index-v2.html"
            file_path = os.path.join(os.path.dirname(__file__), serve_path)
            if os.path.isfile(file_path):
                ext = os.path.splitext(file_path)[1].lower()
                mime = {".html": "text/html", ".js": "application/javascript",
                        ".css": "text/css", ".json": "application/json",
                        ".png": "image/png", ".ico": "image/x-icon"}.get(ext, "text/plain")
                try:
                    with open(file_path, "rb") as f:
                        body = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(body)
                except BrokenPipeError:
                    pass
            else:
                self.send_response(404)
                self.end_headers()

    def handle_error(self, request, client_address):
        pass  # suppress socket error noise


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Validate required credentials
    if not PB_ADMIN_EMAIL or not PB_ADMIN_PASS:
        log("WARNING: PB_ADMIN_EMAIL or PB_ADMIN_PASS not set - PocketBase features disabled")
    if not GITHUB_TOKEN:
        log("WARNING: GITHUB_TOKEN not set - CI polling disabled")
    if not TRELLO_API_KEY or not TRELLO_TOKEN:
        log("WARNING: TRELLO_API_KEY or TRELLO_TOKEN not set - Trello polling disabled")

    # Initial data load
    try:
        data = compute_data()
        with _lock:
            _cache.update(data)
        agent_count = len(data["agents"])
        handoff_count = len(data["handoffs"])
        log(f"Initial load: {agent_count} agents, {handoff_count} handoffs")
    except Exception as e:
        log(f"Initial load error: {e}")

    # Start background threads
    threads = [
        ("agent-refresh", refresh_loop),
        ("ci-poller", ci_poll_loop),
        ("trello-poller", trello_poll_loop),
        ("sse-listener", pb_sse_listener),
    ]

    for name, func in threads:
        t = threading.Thread(target=func, daemon=True, name=name)
        t.start()
        log(f"Started {name} thread")

    # Start HTTP server
    class QuietHTTPServer(HTTPServer):
        def handle_error(self, request, client_address):
            pass  # swallow BrokenPipe and other socket noise

    server = QuietHTTPServer(("0.0.0.0", SERVER_PORT), GridHandler)
    log(f"ZeusOps Grid Server v2 → http://localhost:{SERVER_PORT}")
    log(f"Endpoints: /data /agents /tools /check-pid /ci /trello /events/stream")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Shutting down")


if __name__ == "__main__":
    main()
