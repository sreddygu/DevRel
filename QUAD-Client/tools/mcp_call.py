#!/usr/bin/env python3
"""mcp_call.py — minimal MCP client for the QUAD server's aihub_select tool.

Usage:
  python mcp_call.py <action> '<json-args>'
Example:
  python mcp_call.py request_build '{"model_id":"falcon-v3-7b-instruct","device_class":"snapdragon-x-elite","requester":"sage"}'

Reads QUAD_MCP_TOKEN from env. Prints the tool result JSON (ascii-safe).
"""
import json
import os
import sys

import httpx

URL = os.environ.get("QUAD_MCP_URL", "http://10.227.21.202:8000/mcp")
TOK = os.environ["QUAD_MCP_TOKEN"]
H = {
    "Authorization": f"Bearer {TOK}",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-06-18",
}


def _parse(r):
    if "text/event-stream" in r.headers.get("content-type", ""):
        for ln in r.text.splitlines():
            if ln.startswith("data:"):
                return json.loads(ln[5:].strip())
        return None
    return r.json()


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    # args may be inline JSON (argv[2]) or a @path to a JSON file (avoids
    # shell backslash/quoting issues on Windows paths).
    raw = sys.argv[2] if len(sys.argv) > 2 else ""
    if raw.startswith("@"):
        with open(raw[1:], encoding="utf-8") as fh:
            args = json.load(fh)
    elif raw:
        args = json.loads(raw)
    else:
        args = {}
    args["action"] = action
    timeout = float(os.environ.get("MCP_TIMEOUT", "120"))
    with httpx.Client(timeout=timeout, follow_redirects=True) as c:
        r = c.post(URL, headers=H, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "sage-mcp", "version": "0"}}})
        sid = r.headers.get("mcp-session-id")
        h2 = dict(H)
        if sid:
            h2["mcp-session-id"] = sid
        c.post(URL, headers=h2, json={"jsonrpc": "2.0",
                                      "method": "notifications/initialized"})
        d = _parse(c.post(URL, headers=h2, json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "aihub_select", "arguments": args}}))
    res = (d or {}).get("result", {})
    out = {"isError": res.get("isError")}
    payload = None
    for b in res.get("content", []):
        txt = b.get("text", "")
        try:
            payload = json.loads(txt)
        except Exception:
            payload = txt
    out["result"] = payload
    sys.stdout.write(json.dumps(out, indent=2).encode("ascii", "replace").decode())
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
