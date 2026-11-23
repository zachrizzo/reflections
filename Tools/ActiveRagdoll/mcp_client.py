import json
import httpx


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
                                 "clientInfo": {"name": "kimodo-sword-test", "version": "1"}})
        self.call("notifications/initialized", notify=True)
