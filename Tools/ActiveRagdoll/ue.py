"""ue.py <file.py> [file2.py ...] [--max N] [--wait SEC]  - run code in editor via execute_python, print return value.
Files are concatenated. Retries while the editor reports a slow task, up to --wait seconds (default 100)."""
import sys, json, time
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_client import Mcp
args = sys.argv[1:]
lim, wait = 20000, 100.0
if '--max' in args:
    i = args.index('--max'); lim = int(args[i + 1]); del args[i:i + 2]
if '--wait' in args:
    i = args.index('--wait'); wait = float(args[i + 1]); del args[i:i + 2]
files = [a for a in args if not a.isdigit()]
nums = [a for a in args if a.isdigit()]
if nums: lim = int(nums[0])
code = "\n".join(open(f, encoding="utf-8").read() for f in files)
t0 = time.time()
while True:
    m = Mcp("http://127.0.0.1:8019/mcp", 900)
    m.open()
    r = m.call("tools/call", {"name": "call_tool", "arguments": {
        "toolset_name": "editor_toolset.toolsets.python_scripting.PythonScriptingTools",
        "tool_name": "execute_python", "arguments": {"script": {"content": code, "language": "python"}}}})
    txt = json.dumps(r)
    if 'running a slow task' in txt and time.time() - t0 < wait:
        time.sleep(5); continue
    break
if time.time() - t0 > 5: print('[waited %.0fs]' % (time.time() - t0))
if "error" in r:
    print("RPCERR", json.dumps(r["error"])[:lim]); sys.exit(1)
for part in r["result"].get("content", []):
    if part.get("type") == "text":
        t = part["text"]
        try:
            j = json.loads(t)
            if isinstance(j, dict) and "returnValue" in j:
                rv = j["returnValue"]
                print(rv if isinstance(rv, str) else json.dumps(rv, indent=1)[:lim]); continue
        except Exception:
            pass
        print(t[:lim])
if r["result"].get("isError"): sys.exit(1)
