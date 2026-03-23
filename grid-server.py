#!/usr/bin/env python3
"""ZeusOps Grid Dashboard — Data Server
Listens on http://localhost:8877, serves GET /data as JSON.
Pure Python stdlib only.
"""

import json
import os
import re
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

PORT = 8877
REFRESH_INTERVAL = 5  # seconds

GATEWAYS = {
    "mc": {
        "state_dir": "/home/travis/.openclaw/agents/",
        "agents": ["main", "zeus", "mctravis", "obr"],
        "faction": "mc",
    },
    "zeusops": {
        "state_dir": "/home/travis/.openclaw-zmc-dev-ops/agents/",
        "agents": [
            "manager", "main",  # 'main' is manager's session alias in ZeusOps gateway
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
    "main":               "manager",  # ZeusOps gateway alias for manager
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

# ── Shared state ──────────────────────────────────────────────────────────────
_lock = threading.Lock()
_cache: dict = {}
_first_seen: dict = {}   # handoff_id -> unix ms when first discovered


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# ── Core data computation ──────────────────────────────────────────────────────

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


# ── Background refresh thread ─────────────────────────────────────────────────

def refresh_loop():
    while True:
        try:
            data = compute_data()
            with _lock:
                _cache.clear()
                _cache.update(data)
        except Exception as e:
            print(f"[refresh error] {e}")
        time.sleep(REFRESH_INTERVAL)


# ── HTTP Handler ──────────────────────────────────────────────────────────────

AGENTS_JSON_PATH = os.path.join(os.path.dirname(__file__), "agents.json")

def load_agents_config() -> dict:
    """Load agents.json; return {} on failure."""
    try:
        with open(AGENTS_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {}


# Agents to never surface on the grid — dev artifacts, MC-only, boot stubs, etc.
DISCOVER_BLOCKLIST = {
    # MC-side agents (not ZeusOps)
    "main", "zeus", "mctravis", "obr", "obr-team", "claude-code",
    # Dev/test artifacts
    "test", "test-minimal", "master", "sc", "system",
    # Boot/utility stubs
    "janitor", "reality-checker",
}

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


TOOL_FILTER = {'exec','sessions_spawn','message','web_fetch','browser','process',
               'read','write','edit','image','memory_search','web_search'}

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

_tool_seen_ts = 0.0

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
                since = _tool_seen_ts
                # Scan both gateways for tool calls
                calls = tail_tool_calls("/home/travis/.openclaw-zmc-dev-ops/agents/", since * 1000)
                calls += tail_tool_calls("/home/travis/.openclaw/agents/", since * 1000)
                if calls:
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
        else:
            self.send_response(404)
            self.end_headers()

    def handle_error(self, request, client_address):
        pass  # suppress socket error noise


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Initial data load before server starts
    try:
        data = compute_data()
        with _lock:
            _cache.update(data)
        agent_count = len(data["agents"])
        handoff_count = len(data["handoffs"])
        print(f"Initial load: {agent_count} agents, {handoff_count} handoffs")
    except Exception as e:
        print(f"[initial load error] {e}")

    # Background refresh thread
    t = threading.Thread(target=refresh_loop, daemon=True)
    t.start()

    class QuietHTTPServer(HTTPServer):
        def handle_error(self, request, client_address):
            pass  # swallow BrokenPipe and other socket noise

    server = QuietHTTPServer(("0.0.0.0", PORT), GridHandler)
    print(f"ZeusOps Grid Server → http://localhost:{PORT}/data")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")


if __name__ == "__main__":
    main()
