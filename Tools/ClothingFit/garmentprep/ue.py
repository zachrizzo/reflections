"""Run Python in the shared Unreal editor (its own MCP on 127.0.0.1:8019) under the project's editor lease.

  python ue.py status                               # who holds Saved/PIE_LOCK.json
  python ue.py claim "<purpose>" [seconds<=240]     # take the lease if it is free or expired (or already ours)
  python ue.py wait-claim "<purpose>" [seconds] [max wait]  # poll until it is free, then take it
  python ue.py release                              # give it back (only if it is ours)
  python ue.py py <file.py> [--no-lock]             # run a file; refuses while someone else holds the lease

The lease is claimed here, outside the editor, never by waiting inside an editor script.
Scripts may use top-level `await asyncio.sleep(...)`; the value of the last expression is printed.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

URL = "http://127.0.0.1:8019/mcp"
PROJECT = Path(__file__).resolve().parents[3]
LOCK = PROJECT / "Saved/PIE_LOCK.json"
OWNER = "garment-fit (image-to-3D clothing pipeline session)"


def lock_state():
    """Returns (state, data): 'free', 'ours' or 'held'."""
    try:
        data = json.loads(LOCK.read_text())
    except FileNotFoundError:
        return "free", None
    except Exception:
        return "held", {"owner": "unreadable lock file"}
    if data.get("expires_epoch", 0) <= time.time():
        return ("ours" if data.get("owner") == OWNER else "free"), data
    return ("ours" if data.get("owner") == OWNER else "held"), data


def claim(purpose, seconds=240):
    state, data = lock_state()
    if state == "held":
        return False, data
    now = int(time.time())
    seconds = min(int(seconds), 240)
    LOCK.write_text(json.dumps({"owner": OWNER, "purpose": purpose, "acquired_epoch": now, "expires_epoch": now + seconds,
                                "expires_local": time.strftime("%H:%M:%S", time.localtime(now + seconds))}, indent=2))
    time.sleep(1.6)
    again, data = lock_state()   # someone may have written at the same moment
    return again == "ours", data


def wait_claim(purpose, seconds=240, max_wait=900):
    """Poll until the lease is free, then take it. Returns (ok, data)."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        state, data = lock_state()
        if state != "held":
            ok, data = claim(purpose, seconds)
            if ok:
                return True, data
        time.sleep(3)
    return False, lock_state()[1]


def release():
    state, _ = lock_state()
    if state == "ours" or (state == "free" and LOCK.exists() and json.loads(LOCK.read_text()).get("owner") == OWNER):
        LOCK.unlink(missing_ok=True)
        return True
    return False


class Client:
    def __init__(self, timeout=280):
        self.sid, self.n, self.timeout = None, 0, timeout
        self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                "clientInfo": {"name": "garment-fit", "version": "0.1"}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _post(self, body):
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        if self.sid:
            req.add_header("Mcp-Session-Id", self.sid)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            self.sid = resp.headers.get("Mcp-Session-Id") or self.sid
            raw = resp.read().decode("utf-8", "replace")
        if not raw.strip():
            return None
        if raw.lstrip().startswith("data:") or "\ndata:" in raw:
            raw = "\n".join(line[5:] for line in raw.splitlines() if line.startswith("data:"))
        return json.loads(raw)

    def rpc(self, method, params=None):
        self.n += 1
        out = self._post({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}})
        if out and "error" in out:
            raise RuntimeError(json.dumps(out["error"])[:3000])
        return out["result"] if out else None

    def python(self, code):
        res = self.rpc("tools/call", {"name": "call_tool", "arguments": {
            "toolset_name": "editor_toolset.toolsets.python_scripting.PythonScriptingTools", "tool_name": "execute_python",
            "arguments": {"script": {"content": code, "language": "Python"}}}})
        structured = res.get("structuredContent")
        if not structured:
            text = "\n".join(c.get("text", "") for c in res.get("content", []))
            try:
                structured = json.loads(text)
            except Exception:
                structured = text
        failed = bool(res.get("isError"))
        value = structured.get("returnValue", structured) if isinstance(structured, dict) else structured
        return failed, value


def run_file(path, need_lock=True, params=None):
    state, data = lock_state()
    if state == "held" or (need_lock and state != "ours"):
        print(f"REFUSED: editor lease is {state}: {data}")
        return 3
    code = Path(path).read_text(encoding="utf-8")
    if params is not None:
        code = "import json\nPARAMS = json.loads(" + repr(json.dumps(params)) + ")\n" + code
    for attempt in range(20):
        failed, value = Client().python(code)
        busy = isinstance(value, str) and "running a slow task" in value
        if not busy:
            break
        time.sleep(5)       # another session's long editor task; nothing was run, try again
        if lock_state()[0] == "held":
            print("REFUSED: lost the editor lease while waiting for a slow task")
            return 3
    print(value if isinstance(value, str) else json.dumps(value, indent=1))
    return 1 if failed or busy else 0


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "status":
        print(*lock_state())
    elif cmd == "claim":
        ok, data = claim(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 240)
        print("CLAIMED" if ok else "BUSY", data)
        sys.exit(0 if ok else 3)
    elif cmd == "wait-claim":
        ok, data = wait_claim(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 240, float(sys.argv[4]) if len(sys.argv) > 4 else 900)
        print("CLAIMED" if ok else "TIMEOUT", data)
        sys.exit(0 if ok else 3)
    elif cmd == "release":
        print("RELEASED" if release() else "NOT OURS")
    elif cmd == "py":
        params = None
        if "--params" in sys.argv:
            params = json.loads(Path(sys.argv[sys.argv.index("--params") + 1]).read_text(encoding="utf-8"))
        sys.exit(run_file(sys.argv[2], need_lock="--no-lock" not in sys.argv, params=params))
