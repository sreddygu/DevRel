"""Serve device-health question answering through an A2A JSON-RPC endpoint.

Workflow: On-Device A2A Device Health Agent.
The server gathers live, read-only health context and sends it to a configurable
OpenAI-compatible chat-completions endpoint. Camera and QNN locations are CLI
options so the same source can run on different QLI devices.

Endpoints: ``GET /health``, ``GET /.well-known/agent-card.json``, and
``POST /rpc``.

Example::

    python3 qli_a2a_agent.py --host 0.0.0.0 --port 8765
"""

import argparse
import json
import shlex
import socket
import subprocess
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


WORKFLOWS = ("On-Device A2A Device Health Agent",)


def run_command(command):
    """Run a short diagnostic command and return standard output or error text."""
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=10,
        check=False,
    )
    return completed.stdout.strip() or completed.stderr.strip()


def build_health_context(camera_device, qnn_root):
    """Collect live service, capacity, network, camera, and QNN health context."""
    failed_units = run_command(
        ["systemctl", "--failed", "--no-legend", "--plain"]
    ).splitlines()
    video_nodes = run_command(["sh", "-c", "ls /dev/video* 2>/dev/null || true"])
    camera_stream_check = run_command(
        [
            "sh",
            "-c",
            "rm -f /tmp/qli_a2a_frame.mjpg /tmp/qli_a2a_camera.log; "
            f"timeout 8 v4l2-ctl -d {shlex.quote(camera_device)} "
            "--set-fmt-video=width=320,height=240,pixelformat=MJPG "
            "--stream-mmap=3 --stream-count=1 --stream-poll "
            "--stream-to=/tmp/qli_a2a_frame.mjpg >/tmp/qli_a2a_camera.log 2>&1; "
            "status=$?; bytes=0; "
            "[ -f /tmp/qli_a2a_frame.mjpg ] && bytes=$(wc -c </tmp/qli_a2a_frame.mjpg); "
            "echo status=$status bytes=$bytes; cat /tmp/qli_a2a_camera.log; "
            "rm -f /tmp/qli_a2a_frame.mjpg /tmp/qli_a2a_camera.log",
        ]
    )
    qnn_assets = run_command(
        [
            "sh",
            "-c",
            f"find {shlex.quote(qnn_root)} -maxdepth 2 -type f 2>/dev/null | head -20",
        ]
    )
    return {
        "capturedAtUtc": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "osRelease": run_command(["cat", "/etc/os-release"]),
        "uptime": run_command(["uptime"]),
        "storage": run_command(["df", "-h", "/"]),
        "network": run_command(["ip", "-brief", "address"]),
        "failedUnitCount": len([line for line in failed_units if line.strip()]),
        "failedUnits": failed_units,
        "videoNodes": video_nodes.splitlines(),
        "cameraStreamCheck": camera_stream_check,
        "qnnAssetsPresent": bool(qnn_assets.strip()),
    }


def extract_text(params):
    """Extract and concatenate text parts from A2A SendMessage parameters."""
    message = params.get("message", {}) if isinstance(params, dict) else {}
    parts = message.get("parts", []) if isinstance(message, dict) else []
    texts = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            texts.append(part["text"])
    return "\n".join(texts).strip()


def ask_genie(endpoint, model, question, health_context):
    """Ask the configured chat endpoint about the current device-health context."""
    prompt = (
        "You are an on-device health assistant. Answer the user's question using "
        "only the live device context. Be concise, separate healthy observations from "
        "items needing attention, and give one safe next step. Device-node presence does "
        "not prove that camera streaming works; use cameraStreamCheck for that conclusion.\n\n"
        f"Live device context:\n{json.dumps(health_context, indent=2)}\n\n"
        f"User question: {question}"
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 384,
        "temperature": 0,
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"].strip()


def receive_http_request(connection):
    """Read and minimally parse one HTTP request from a socket connection."""
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = connection.recv(4096)
        if not chunk:
            break
        data += chunk
        if len(data) > 1024 * 1024:
            raise ValueError("request headers too large")
    header_bytes, separator, body = data.partition(b"\r\n\r\n")
    if not separator:
        raise ValueError("invalid HTTP request")
    header_lines = header_bytes.decode("iso-8859-1").split("\r\n")
    request_line = header_lines[0].split()
    if len(request_line) != 3:
        raise ValueError("invalid HTTP request line")
    method, path, _ = request_line
    headers = {}
    for line in header_lines[1:]:
        name, delimiter, value = line.partition(":")
        if delimiter:
            headers[name.strip().lower()] = value.strip()
    content_length = int(headers.get("content-length", "0"))
    while len(body) < content_length:
        chunk = connection.recv(min(4096, content_length - len(body)))
        if not chunk:
            break
        body += chunk
    return method, path, headers, body[:content_length]


def send_json(connection, status, body):
    """Send a JSON HTTP response with the supplied status and body."""
    encoded = json.dumps(body, indent=2).encode("utf-8")
    reason = {200: "OK", 404: "Not Found", 500: "Internal Server Error"}.get(
        status, "OK"
    )
    headers = (
        f"HTTP/1.1 {status} {reason}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(encoded)}\r\n"
        "Cache-Control: no-store\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    connection.sendall(headers + encoded)


def process_rpc(request_body, genie_endpoint, model, camera_device, qnn_root):
    """Validate an A2A RPC request and construct its device-health response."""
    request_id = request_body.get("id")
    if request_body.get("jsonrpc") != "2.0":
        raise ValueError("jsonrpc must be 2.0")
    if request_body.get("method") != "SendMessage":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "Method not found"},
        }
    question = extract_text(request_body.get("params", {}))
    if not question:
        raise ValueError("message.parts must contain text")
    health_context = build_health_context(camera_device, qnn_root)
    answer = ask_genie(genie_endpoint, model, question, health_context)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "message": {
                "messageId": str(uuid.uuid4()),
                "role": "ROLE_AGENT",
                "parts": [{"text": answer}],
                "metadata": {
                    "deviceHostname": health_context["hostname"],
                    "capturedAtUtc": health_context["capturedAtUtc"],
                    "model": model,
                },
            }
        },
    }


def handle_connection(
    connection,
    address,
    agent_card,
    genie_endpoint,
    model,
    camera_device,
    qnn_root,
):
    """Route one connection to health, agent-card, or JSON-RPC handling."""
    try:
        method, path, _, body = receive_http_request(connection)
        print(f"{datetime.now(timezone.utc).isoformat()} {address[0]} {method} {path}", flush=True)
        if method == "GET" and path == "/.well-known/agent-card.json":
            send_json(connection, 200, agent_card)
            return
        if method == "GET" and path == "/health":
            send_json(connection, 200, {"status": "ready", "hostname": socket.gethostname()})
            return
        if method == "POST" and path == "/rpc":
            try:
                request_body = json.loads(body.decode("utf-8"))
                response = process_rpc(
                    request_body,
                    genie_endpoint,
                    model,
                    camera_device,
                    qnn_root,
                )
            except (ValueError, KeyError, json.JSONDecodeError) as error:
                response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32602, "message": str(error)},
                }
            except (HTTPError, URLError, TimeoutError) as error:
                response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32603,
                        "message": f"Genie endpoint unavailable: {error}",
                    },
                }
            send_json(connection, 200, response)
            return
        send_json(connection, 404, {"error": "not found"})
    except Exception as error:
        send_json(connection, 500, {"error": str(error)})


def build_agent_card(host, port):
    """Build the A2A agent card advertised by this device-health service."""
    base_url = f"http://{host}:{port}"
    return {
        "name": "QLI Device Health Agent",
        "description": "Answers questions using live operating-system and device-health information.",
        "supportedInterfaces": [
            {
                "url": f"{base_url}/rpc",
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            }
        ],
        "version": "1.0.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "extendedAgentCard": False,
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": "qli-device-health",
                "name": "QLI Device Health Q&A",
                "description": "Summarizes current device health and suggests one safe next step.",
                "tags": ["QLI", "device health", "QNN"],
                "examples": ["What is healthy and what needs attention on this device?"],
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain"],
            }
        ],
    }


def main():
    """Start the A2A server and process requests until interrupted."""
    parser = argparse.ArgumentParser(description="Run an A2A 1.0 device-health agent.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--genie-endpoint",
        default="http://127.0.0.1:18081/v1/chat/completions",
    )
    parser.add_argument("--model", default="qwen3-4b-genie")
    parser.add_argument("--camera-device", default="/dev/video0")
    parser.add_argument("--qnn-root", default="/opt/qnn")
    parser.add_argument("--list-workflows", action="store_true")
    args = parser.parse_args()
    if args.list_workflows:
        print("\n".join(WORKFLOWS))
        return
    agent_card = build_agent_card(args.host, args.port)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen(8)
    print(
        json.dumps(
            {
                "status": "ready",
                "listen": f"http://{args.host}:{args.port}",
                "genieEndpoint": args.genie_endpoint,
                "model": args.model,
            }
        ),
        flush=True,
    )
    while True:
        connection, address = server.accept()
        with connection:
            handle_connection(
                connection,
                address,
                agent_card,
                args.genie_endpoint,
                args.model,
                args.camera_device,
                args.qnn_root,
            )


if __name__ == "__main__":
    main()
