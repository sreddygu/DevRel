"""Generate QUAD_Cloud_MCP_Server_Guide.docx — client connection guide.

A shareable one-stop DOCX for developers who need to point their IDE / MCP
client at the hosted QUAD MCP server (quad.infra.foundries.io). Uses the
shared _docx_style helpers in the QUAD repo so it matches the rest of the doc
set (cover, tables, code blocks, callouts).

Run:    python docs/generate_cloud_mcp_guide.py
Output: docs/QUAD_Cloud_MCP_Server_Guide.docx
"""

from __future__ import annotations

import sys
from pathlib import Path

# The _docx_style helpers live in the sibling QUAD platform repo. This
# generator lives in QUAD-Client (client-facing doc). Import via absolute path
# so both repos stay independent.
_QUAD_DOCS = Path(__file__).resolve().parents[2] / "QUAD" / "docs"
if not (_QUAD_DOCS / "_docx_style.py").is_file():
    raise SystemExit(
        f"Cannot find _docx_style.py at {_QUAD_DOCS}. This generator expects "
        "the QUAD platform repo checked out alongside QUAD-Client."
    )
sys.path.insert(0, str(_QUAD_DOCS))
from _docx_style import (  # noqa: E402
    bullets,
    callout,
    code_block,
    cover,
    setup_styles,
    table,
)
from docx import Document  # noqa: E402

# ── Deployment facts (as of 2026-07-20) ──────────────────────────────────────
FQDN = "quad.infra.foundries.io"
ENDPOINT = f"https://{FQDN}/mcp"
BEARER_TOKEN = "24334a8d888850b0a3519c653b8eb628fbb9cc09d58cd9d528ce45736a4a1080"
QAIRT_VERSION = "v2.41.0.251128"
QUAD_VERSION = "0.9.0"


def _h1(doc: Document, text: str) -> None:
    doc.add_heading(text, level=1)


def _h2(doc: Document, text: str) -> None:
    doc.add_heading(text, level=2)


def _p(doc: Document, text: str, *, bold_lead: str | None = None) -> None:
    p = doc.add_paragraph()
    if bold_lead:
        r = p.add_run(bold_lead)
        r.bold = True
    p.add_run(text)


def build(out: Path) -> None:
    doc = Document()
    setup_styles(doc)

    # ── Cover ────────────────────────────────────────────────────────────────
    cover(
        doc,
        title="QUAD Cloud MCP Server",
        subtitle="Client Connection Guide",
        tagline=(
            f"How to point Claude Code, opencode, codex, or any MCP client "
            f"at the hosted server at {FQDN}. Includes endpoint, bearer "
            f"token, IDE configs, CLI probes, and troubleshooting."
        ),
        meta=f"QUAD {QUAD_VERSION} · QAIRT {QAIRT_VERSION} · updated 2026-07-20",
    )

    # ── Section 1 — What this server is ─────────────────────────────────────
    _h1(doc, "1. What this server is")
    _p(
        doc,
        f"A shared, always-on QUAD MCP server hosted at "
        f"https://{FQDN}. Any developer with the bearer token below can "
        f"attach an IDE (Claude Code, opencode, codex, Cursor, …) or a "
        f"scripted MCP client and reach QUAD's tool set without installing "
        f"the platform locally. This mirrors the DGX-hosted MCP server 1:1 "
        f"— same QUAD version, same QAIRT SDK, same tools.",
    )
    _h2(doc, "What it exposes")
    bullets(
        doc,
        [
            "MCP RPC at /mcp — the six tools: hardware_detect, "
            "profile_workload, convert_model, orchestrate_workload, "
            "generate_code, aihub_select.",
            "Bundle registry data plane at /bundles/{model_id}/manifest and "
            "/bundles/{model_id}/download — NPU LLM bundle pull for clients.",
        ],
    )
    _h2(doc, "What it does NOT expose")
    bullets(
        doc,
        [
            "No /v1/chat/completions or /rag/* — the chat/RAG serve plane "
            "(quad serve) is a per-developer surface, not hosted here.",
            "No on-device NPU inference — this is a general-purpose Linux VM "
            "(AMD EPYC, no Hexagon NPU). Real NPU work stays on developers' "
            "Snapdragon devices; this server does the SDK-driven convert / "
            "profile / codegen / aihub work in real mode.",
        ],
    )
    callout(
        doc,
        "Real mode, no NPU",
        f"'Real mode' here means QAIRT {QAIRT_VERSION} is installed and its "
        f"CLIs (qairt-converter, qairt-quantizer, etc.) are on PATH — so "
        f"MCP tool calls do genuine work, not simulated. It does NOT mean "
        f"there is an NPU attached: there isn't. Model conversion / "
        f"quantization / codegen run on the CPU here; on-device inference "
        f"happens on the developer's Snapdragon box after the artifacts are "
        f"produced. This is the same shape as the DGX MCP server.",
    )

    # ── Section 2 — Connection details ──────────────────────────────────────
    _h1(doc, "2. Connection details")
    table(
        doc,
        headers=["Field", "Value"],
        rows=[
            ["Endpoint URL", ENDPOINT],
            ["Transport", "HTTP (MCP streamable-HTTP)"],
            ["TLS", "Let's Encrypt (auto-renew)"],
            ["Auth header", "Authorization: Bearer <token>"],
            ["Token", BEARER_TOKEN],
            ["Server version", f"QUAD {QUAD_VERSION}, QAIRT {QAIRT_VERSION}"],
            ["Adapter mode", "real"],
        ],
        col_widths_in=[1.6, 5.0],
    )
    callout(
        doc,
        "Handle the token like a password",
        "The bearer token above authenticates every MCP call. Do not commit "
        "it to git, do not paste it in tickets or chat channels — use an "
        "environment variable (QUAD_MCP_TOKEN) or the IDE's secret store. "
        "Token rotation is a stop-the-world operation: when it rotates, all "
        "clients drop and must update their env var. Contact the server "
        "admin if you suspect the token has leaked.",
    )

    # ── Section 3 — Claude Code (recommended) ───────────────────────────────
    _h1(doc, "3. Configure Claude Code (recommended)")
    _p(
        doc,
        "Claude Code is the primary MCP client for QUAD. It reads MCP servers "
        "from ~/.claude.json (global) or .claude/settings.json (per-project). "
        "The env-var form below is preferred so the token is never checked "
        "into git.",
    )
    _h2(doc, "Step 1 — Set the token in your environment")
    _p(doc, "On Linux / macOS (persist in ~/.bashrc or ~/.zshrc):")
    code_block(doc, [f"export QUAD_MCP_TOKEN={BEARER_TOKEN}"])
    _p(doc, "On Windows PowerShell (persist for the current user):")
    code_block(
        doc,
        [f'[Environment]::SetEnvironmentVariable("QUAD_MCP_TOKEN", "{BEARER_TOKEN}", "User")'],
    )
    _h2(doc, "Step 2 — Register the MCP server")
    _p(
        doc,
        "Add this block to your Claude Code settings (either global "
        "~/.claude.json or the project's .claude/settings.json under "
        "mcpServers):",
    )
    code_block(
        doc,
        [
            "{",
            '  "mcpServers": {',
            '    "quad-cloud": {',
            '      "type": "http",',
            f'      "url": "{ENDPOINT}",',
            '      "headers": {',
            '        "Authorization": "Bearer ${env:QUAD_MCP_TOKEN}"',
            "      }",
            "    }",
            "  }",
            "}",
        ],
    )
    _p(
        doc,
        "Restart Claude Code (or /reload) and confirm the connection with "
        "/mcp — the server should list with status 'connected' and expose "
        "quad__hardware_detect, quad__convert_model, etc.",
    )

    # ── Section 4 — Alternative clients ─────────────────────────────────────
    _h1(doc, "4. Alternative MCP clients")
    _h2(doc, "opencode")
    _p(doc, "In opencode.json (or the per-project .opencode/opencode.json):")
    code_block(
        doc,
        [
            "{",
            '  "mcp": {',
            '    "quad-cloud": {',
            '      "type": "remote",',
            f'      "url": "{ENDPOINT}",',
            '      "headers": {"Authorization": "Bearer ${env:QUAD_MCP_TOKEN}"}',
            "    }",
            "  }",
            "}",
        ],
    )
    _h2(doc, "codex")
    _p(doc, "Codex uses the same MCP-over-HTTP shape:")
    code_block(
        doc,
        [
            "{",
            '  "mcpServers": {',
            '    "quad-cloud": {',
            '      "transport": "http",',
            f'      "url": "{ENDPOINT}",',
            '      "auth": {"type": "bearer", "token": "${env:QUAD_MCP_TOKEN}"}',
            "    }",
            "  }",
            "}",
        ],
    )
    _h2(doc, "Any other MCP client")
    _p(
        doc,
        "MCP over streamable-HTTP is a spec, not vendor-specific. Any client "
        "that supports the 2024-11-05 protocol can connect — provide the URL "
        f"({ENDPOINT}) and an Authorization: Bearer <token> header. The "
        "server accepts both text/event-stream and application/json accept "
        "types.",
    )

    # ── Section 5 — CLI probes ──────────────────────────────────────────────
    _h1(doc, "5. Sanity-check the connection from a shell")
    _p(
        doc,
        "Before wiring up an IDE, prove the server is reachable and the token "
        "works. All of these run in seconds and require nothing beyond curl.",
    )
    _h2(doc, "TLS + auth handshake")
    code_block(
        doc,
        [
            f"curl -i https://{FQDN}/mcp",
            "# Expected: HTTP/2 401 Unauthorized  (auth is on — correct)",
        ],
    )
    _h2(doc, "MCP initialize handshake")
    code_block(
        doc,
        [
            f"export QUAD_MCP_TOKEN={BEARER_TOKEN}",
            f"curl -s -X POST {ENDPOINT} \\",
            '  -H "Authorization: Bearer $QUAD_MCP_TOKEN" \\',
            '  -H "Content-Type: application/json" \\',
            '  -H "Accept: application/json, text/event-stream" \\',
            "  -d \'{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",",
            '       "params":{"protocolVersion":"2024-11-05",',
            '                 "capabilities":{},',
            '                 "clientInfo":{"name":"probe","version":"1"}}}\'',
            "# Expected: result.serverInfo.name == 'QUAD — Qualcomm Unified Agent for Developers'",
        ],
    )
    _h2(doc, "quad_mcp_client connect-test (from a QUAD-Client checkout)")
    code_block(
        doc,
        [
            f"export QUAD_MCP_TOKEN={BEARER_TOKEN}",
            ".venv/Scripts/python.exe -m quad_mcp_client.cli \\",
            f"    connect-test sse-http --sse-url {ENDPOINT} \\",
            '    --auth-token "$QUAD_MCP_TOKEN"',
        ],
    )

    # ── Section 6 — First-tool checks ───────────────────────────────────────
    _h1(doc, "6. Try the MCP tools")
    _p(
        doc,
        "Once the client is attached, invoke tools from the IDE prompt. "
        "These three cover 90% of first-day usage.",
    )
    table(
        doc,
        headers=["Ask the IDE", "MCP tool exercised", "What it returns"],
        rows=[
            [
                "what hardware do I have on linux?",
                "hardware_detect(platform=linux)",
                f"real DeviceProfile — AMD EPYC 7B12, QAIRT {QAIRT_VERSION} SDK reachable",
            ],
            [
                "convert my ONNX model to a QNN binary",
                "convert_model(source_format=onnx, target_sdk=qnn)",
                "compiled .bin path + AI Hub Models routing decision",
            ],
            [
                "find an AI Hub Models model for a Snapdragon 8 Elite",
                "aihub_select(action=search, platform=android)",
                "ranked catalog matches + compat verdict",
            ],
        ],
        col_widths_in=[2.1, 2.1, 2.4],
    )
    _p(
        doc,
        "Every tool call carries a decisions[] trail (correlation id + "
        "rationale) so you can audit what QUAD chose and why. See "
        "docs/DEVELOPER_GUIDE.md for the full tool reference.",
    )

    # ── Section 7 — Troubleshooting ─────────────────────────────────────────
    _h1(doc, "7. Troubleshooting")
    table(
        doc,
        headers=["Symptom", "Cause", "Fix"],
        rows=[
            [
                "curl returns empty body / SSL error",
                "Corp proxy (Netskope) is MITM'ing HTTPS with its own CA.",
                "Add the corp root CA to your OS/IDE trust store, or connect "
                "from a non-Netskope network.",
            ],
            [
                "HTTP 401 Unauthorized",
                "Missing or wrong Authorization header.",
                "Confirm QUAD_MCP_TOKEN is exported and the header reads "
                "'Bearer <token>' (no quotes, no newlines).",
            ],
            [
                "HTTP 502 Bad Gateway",
                "MCP process is down; nginx cannot reach 127.0.0.1:8000.",
                "Contact server admin — restart is 'launch.sh background restart'.",
            ],
            [
                "HTTP 429 or 503",
                "Concurrency cap hit (200 in-flight requests).",
                "Retry with backoff; report to admin if it persists so the "
                "cap can be raised.",
            ],
            [
                "'Bad Request: Missing session ID' after initialize",
                "Sending tools/list before completing the MCP session dance.",
                "Use a real MCP client (Claude Code etc.) — it manages "
                "session state. curl is only for the initialize handshake.",
            ],
            [
                "Connection times out (no TCP handshake)",
                "Client network blocks outbound 443, or the server is down.",
                "Test with 'curl -v https://" + FQDN + "/mcp'; if TCP "
                "fails, the outbound firewall is the culprit.",
            ],
            [
                "Token stops working overnight",
                "Admin rotated it.",
                "Ask for the new token; update QUAD_MCP_TOKEN and reconnect.",
            ],
        ],
        col_widths_in=[2.0, 2.0, 2.6],
    )

    # ── Section 8 — Security posture ────────────────────────────────────────
    _h1(doc, "8. Security posture")
    bullets(
        doc,
        [
            "Bearer auth is required on every route (including the /bundles "
            "data plane).",
            "MCP server binds loopback (127.0.0.1:8000); nginx is the only "
            "public listener. Public firewall exposes 80 (redirects to 443) "
            "and 443 only.",
            "TLS termination at nginx via Let's Encrypt; auto-renew via the "
            "certbot systemd timer.",
            "The bundle registry data plane also enforces the same bearer "
            "token (defence-in-depth beyond the middleware).",
            "The 'quad' service user has passwordless sudo scoped only for "
            "operational commands. SSH access is admin-key-only.",
            "Token rotation is stop-the-world: 'launch.sh background restart "
            "--rotate-token' → all clients drop and must update.",
        ],
    )

    # ── Section 9 — What's next ─────────────────────────────────────────────
    _h1(doc, "9. What's next")
    _p(
        doc,
        "Once connected, the two most useful reference docs are:",
    )
    bullets(
        doc,
        [
            "docs/DEVELOPER_GUIDE.md — full tool reference, arg semantics, "
            "sample workflows.",
            "docs/NPU_QUICKSTART.md — how to combine this MCP server with a "
            "local NPU on your Snapdragon device (convert here, run there).",
            "The QUAD-Client CLI (.venv/Scripts/python.exe -m "
            "quad_mcp_client.cli --help) — local-only helpers (detect, "
            "doctor, connect-test) that don't need the server.",
        ],
    )
    _p(
        doc,
        "For server-side ops (upgrades, cert renewal, log inspection), see "
        "the QUAD platform repo's deploy/AWS.md runbook — the DGX and cloud "
        "boxes are provisioned from the same template.",
    )

    # ── Contact / provenance ────────────────────────────────────────────────
    _h1(doc, "Reference")
    bullets(
        doc,
        [
            f"Server FQDN: {FQDN}",
            f"MCP endpoint: {ENDPOINT}",
            f"QUAD version: {QUAD_VERSION}",
            f"QAIRT SDK version: {QAIRT_VERSION}",
            "Server admin: infra@foundries.io (per certbot registration).",
            "Companion DGX server: same shape, separate token — ask admin for details.",
            "Deployment runbook: QUAD repo, deploy/AWS.md.",
        ],
    )

    doc.save(str(out))
    print(f"Wrote {out}")


def main() -> None:
    out = Path(__file__).resolve().parent / "QUAD_Cloud_MCP_Server_Guide.docx"
    build(out)


if __name__ == "__main__":
    main()
