"""LAN-only transport: a tiny token-protected HTTP server and client (stdlib only).

The server binds to loopback by default so it is reachable only through an SSH
tunnel; pass ``host`` explicitly to expose it on a trusted LAN interface.
"""

from __future__ import annotations

import hmac
import json
import socketserver
import threading
import urllib.parse
import urllib.request

from aura.memory.store import MemoryStore

from .bundle import build_bundle, import_bundle

PATH = "/v1/handoff"


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def make_server(
    db_path: str, token: str, *, host: str = "127.0.0.1", port: int = 8765, node: str | None = None
) -> socketserver.ThreadingTCPServer:
    """Serve read-only bundles from the MemoryStore at ``db_path``.

    Speaks a minimal HTTP/1.0 subset on ``socketserver`` because the Qualcomm
    Linux image's trimmed Python lacks ``html`` and therefore ``http.server``.
    """
    if not token:
        raise ValueError("a non-empty token is required")

    class Handler(socketserver.StreamRequestHandler):
        def _send(self, code: int, reason: str, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            head = (f"HTTP/1.0 {code} {reason}\r\nContent-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n")
            self.wfile.write(head.encode("ascii") + body)

        def handle(self) -> None:
            self.connection.settimeout(10)
            try:
                request_line = self.rfile.readline(8192).decode("latin-1").split()
                headers = {}
                for _ in range(100):
                    line = self.rfile.readline(8192).decode("latin-1").strip()
                    if not line:
                        break
                    name, _, value = line.partition(":")
                    headers[name.strip().lower()] = value.strip()
            except (OSError, ValueError):
                return
            if len(request_line) < 2 or request_line[0] != "GET":
                return self._send(405, "Method Not Allowed", {"error": "GET only"})
            supplied = headers.get("authorization", "").removeprefix("Bearer ")
            if not hmac.compare_digest(supplied.encode(), token.encode()):
                return self._send(401, "Unauthorized", {"error": "unauthorized"})
            url = urllib.parse.urlparse(request_line[1])
            if url.path != PATH:
                return self._send(404, "Not Found", {"error": "not found"})
            q = urllib.parse.parse_qs(url.query)
            since = q.get("since", [None])[0]
            try:
                limit = max(1, min(int(q.get("limit", ["500"])[0]), 5000))
            except ValueError:
                return self._send(400, "Bad Request", {"error": "bad limit"})
            # SQLite connections are per-request: handler threads differ.
            with MemoryStore(db_path).connect() as store:
                self._send(200, "OK", build_bundle(store, since=since, limit=limit, node=node))

    return _Server((host, port), Handler)


def serve_in_thread(server: socketserver.BaseServer) -> threading.Thread:
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return t


def fetch_bundle(base_url: str, token: str, *, since: str | None = None, limit: int = 500, timeout: float = 10) -> dict:
    query = {"limit": str(limit)}
    if since:
        query["since"] = since
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{PATH}?{urllib.parse.urlencode(query)}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - caller-supplied LAN URL
        return json.loads(resp.read().decode("utf-8"))


def catch_up(store: MemoryStore, base_url: str, token: str, *, since: str | None = None) -> dict:
    """Pull the hub's recent context into ``store`` ("catch me up on the bay")."""
    return import_bundle(store, fetch_bundle(base_url, token, since=since))
