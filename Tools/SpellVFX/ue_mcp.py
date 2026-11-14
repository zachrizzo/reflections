"""Minimal client for the editor-hosted Unreal MCP server (http://127.0.0.1:8000/mcp).

Used by ue_import.py and the other MapKit editor scripts. Standard library only.
`call(toolset, tool, args)` returns the tool's `returnValue` (or the parsed JSON / raw text) and raises McpError
on a protocol or tool error.
"""

import json
import os
import random
import tempfile
import urllib.request

URL = "http://127.0.0.1:8000/mcp"
_SESSION_FILE = os.path.join(tempfile.gettempdir(), "mapkit_mcp_session.txt")

P = "editor_toolset.toolsets."
SM = P + "static_mesh.StaticMeshTools"
MAT = P + "material.MaterialTools"
MI = P + "material_instance.MaterialInstanceTools"
SCENE = P + "scene.SceneTools"
ACTOR = P + "actor.ActorTools"
DA = P + "data_asset.DataAssetTools"
PROG = P + "programmatic.ProgrammaticToolset"
AT = P + "asset.AssetTools"
OT = P + "object.ObjectTools"
ED = "EditorToolset.EditorAppToolset"
LG = "EditorToolset.LogsToolset"


class McpError(RuntimeError):
    pass


def _post(body, sid=None, timeout=600):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if sid:
        headers["Mcp-Session-Id"] = sid
    req = urllib.request.Request(URL, json.dumps(body).encode(), headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.headers.get("Mcp-Session-Id"), resp.read().decode()


def _init():
    sid, _ = _post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                               "clientInfo": {"name": "mapkit", "version": "1"}}})
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    with open(_SESSION_FILE, "w") as f:
        f.write(sid)
    return sid


def _sid():
    if os.path.exists(_SESSION_FILE):
        with open(_SESSION_FILE) as f:
            s = f.read().strip()
        if s:
            return s
    return _init()


def rpc(method, params, retry=True):
    try:
        _, body = _post({"jsonrpc": "2.0", "id": random.randint(1, 10 ** 6), "method": method, "params": params},
                        _sid())
    except urllib.error.HTTPError:
        if not retry:
            raise
        _init()
        return rpc(method, params, False)
    d = json.loads(body)
    if "error" in d and retry and "session" in json.dumps(d).lower():
        _init()
        return rpc(method, params, False)
    return d


def call(toolset, tool, args, check=True):
    d = rpc("tools/call", {"name": "call_tool",
                           "arguments": {"toolset_name": toolset, "tool_name": tool, "arguments": args}})
    if "error" in d:
        raise McpError("%s.%s: %s" % (toolset.split(".")[-1], tool, d["error"]))
    result = d["result"]
    text = "".join(b.get("text", "") for b in result.get("content", []))
    if check and result.get("isError"):
        raise McpError("%s.%s: %s" % (toolset.split(".")[-1], tool, text[:2000]))
    try:
        j = json.loads(text)
    except ValueError:
        return text
    return j.get("returnValue", j) if isinstance(j, dict) else j


def ref(path):
    return {"refPath": path}


def no_pie():
    """Raises unless PIE is off (every edit must check this first)."""
    if call(ED, "IsPIERunning", {}) is not False:
        raise McpError("BLOCKED: PIE is running")


def script(code):
    """Runs a ProgrammaticToolset script (must define run() -> dict) and returns its dict."""
    out = call(PROG, "execute_tool_script", {"script": code})
    return json.loads(out) if isinstance(out, str) else out
