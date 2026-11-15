"""Runs a Python file inside the open Unreal Editor through its MCP server (streamable HTTP, default
http://127.0.0.1:8000/mcp), the same `execute_python` tool the other PIE checks use.

    python run_in_editor.py test_npc_dialogue_pie.py [--timeout 400]
    python run_in_editor.py --list            # tool names and their argument schemas
"""
import argparse
import json
import sys

import httpx

URL = "http://127.0.0.1:8000/mcp"


def _parse(response):
    kind = response.headers.get("content-type", "")
    if "text/event-stream" in kind:
        result = None
        for line in response.text.splitlines():
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload:
                    message = json.loads(payload)
                    if "result" in message or "error" in message:
                        result = message
        return result
    return response.json() if response.content else None


class Mcp:
    def __init__(self, url, timeout):
        self.url, self.session, self.next_id = url, None, 1
        self.client = httpx.Client(timeout=timeout, trust_env=False)

    def call(self, method, params=None, notify=False):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        body = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            body["id"] = self.next_id
            self.next_id += 1
        response = self.client.post(self.url, json=body, headers=headers)
        self.session = response.headers.get("mcp-session-id", self.session)
        response.raise_for_status()
        return None if notify else _parse(response)

    def open(self):
        self.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "reflections-npc-dialogue", "version": "1"}})
        self.call("notifications/initialized", notify=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("script", nargs="?")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--tool", default="execute_python")
    parser.add_argument("--arg", default=None, help="argument name for the code (default: discovered)")
    parser.add_argument("--timeout", type=float, default=400.0)
    parser.add_argument("--url", default=URL)
    args = parser.parse_args()
    mcp = Mcp(args.url, args.timeout)
    mcp.open()
    tools = mcp.call("tools/list", {})["result"]["tools"]
    if args.list or not args.script:
        for tool in tools:
            print(tool["name"], json.dumps(tool.get("inputSchema", {}).get("properties", {}))[:400])
        return 0
    with open(args.script, encoding="utf-8") as handle:
        code = handle.read()
    direct = next((t for t in tools if t["name"] == args.tool), None)
    if direct is not None:
        props = list(direct.get("inputSchema", {}).get("properties", {}))
        arg = args.arg or next((p for p in props if p in ("code", "script", "source", "python")), props[0])
        reply = mcp.call("tools/call", {"name": direct["name"], "arguments": {arg: code}})
    else:
        # The editor toolset exposes execute_python behind call_tool.
        reply = mcp.call("tools/call", {"name": "call_tool", "arguments": {
            "toolset_name": "editor_toolset.toolsets.python_scripting.PythonScriptingTools",
            "tool_name": args.tool, "arguments": {"script": {"content": code, "language": "python"}}}})
    if "error" in reply:
        print(json.dumps(reply["error"], indent=1))
        return 1
    for part in reply["result"].get("content", []):
        if part.get("type") == "text":
            print(part["text"])
    return 1 if reply["result"].get("isError") else 0


if __name__ == "__main__":
    sys.exit(main())
