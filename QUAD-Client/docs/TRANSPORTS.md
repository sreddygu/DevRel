# MCP Transports

QUAD-Client supports three transports for connecting Claude Code to a
QUAD MCP server. They differ in **where the server runs**, **how
the client reaches it**, and **what setup the user has done in advance**.

## TL;DR

| Transport | Server runs | Connection method | When to pick |
|---|---|---|---|
| `stdio-local` | This same machine | `python -m quad.mcp.server` as subprocess | Solo dev on a Snapdragon laptop |
| `stdio-ssh` | A remote machine | `ssh user@host python -m quad.mcp.server` | Lab box / cloud VM you already SSH to |
| `sse-http` | A hosted HTTP service | HTTPS + Server-Sent Events | Multi-tenant gateway / managed service |

If you're picking transports for a team:
- **Most teams want `stdio-ssh`** for shared lab hardware.
- **Solo developers** with their own Snapdragon machine: `stdio-local`.
- **Larger orgs** running QUAD as SaaS: `sse-http`.

---

## stdio-local

```
┌────────────────────────┐
│  Developer machine     │
│  ┌──────────────────┐  │
│  │   Claude Code    │  │
│  └────────┬─────────┘  │
│           │ stdio       │
│  ┌────────▼─────────┐  │
│  │ python -m        │  │
│  │ quad.mcp.server  │  │  ← subprocess
│  └──────────────────┘  │
└────────────────────────┘
```

### How it works

Claude Code reads `.claude/settings.json`, sees `command: "python"` +
`args: ["-m", "quad.mcp.server"]`, and spawns it as a child process with
stdin/stdout pipes. The MCP protocol speaks over those pipes.

### Pros

- Simplest setup
- Lowest latency (no network)
- Works fully offline

### Cons

- Need the QUAD server installed on this machine (~1.2 GB with SDK)
- Only this machine can run inference

### Connection probe

`quad-client connect-test stdio-local`:
1. Spawns `python -m quad.mcp.server` as a subprocess
2. Waits 1 second
3. If it didn't crash → `ok=True`, kills it cleanly
4. If it exited within 1 second → `ok=False` with the stderr excerpt

Common failure: `ModuleNotFoundError: No module named 'quad'` →
the QUAD server isn't installed. Install it from
[github.qualcomm.com/pavanr/QUAD](https://github.qualcomm.com/pavanr/QUAD).

---

## stdio-ssh

```
┌─────────────────────────┐                  ┌─────────────────────────┐
│   Developer laptop      │                  │   Lab / cloud machine   │
│   ┌─────────────────┐   │                  │   ┌─────────────────┐   │
│   │   Claude Code   │   │                  │   │ python -m       │   │
│   └────────┬────────┘   │                  │   │ quad.mcp.server │   │
│            │ stdio       │                  │   └────────▲────────┘   │
│   ┌────────▼────────┐   │   SSH tunnel     │            │            │
│   │  ssh user@host  ├───┼──────────────────┼────────────┘            │
│   └─────────────────┘   │                  │                         │
└─────────────────────────┘                  └─────────────────────────┘
```

### How it works

Claude Code spawns `ssh user@host python -m quad.mcp.server` as a
subprocess. SSH establishes a tunnel; the remote Python process speaks
MCP over its stdin/stdout, which SSH proxies back to Claude Code's
local process.

### Pros

- One server can serve many client laptops
- Server has the heavy SDK + hardware; clients stay lightweight
- Works through corporate networks if SSH does
- No new ports to open

### Cons

- Requires key-based SSH (passwords would hang Claude Code)
- ~10-50 ms added latency per request
- Requires the user to have already-working SSH to the server

### Prerequisites

Test SSH **without** Claude Code first:

```bash
ssh -o BatchMode=yes user@host echo ok
# Expected: prints "ok" and exits 0 immediately
# If it hangs or asks for a password → set up key auth first
```

If you don't have key auth yet:

```bash
ssh-keygen -t ed25519                       # create a key if you don't have one
ssh-copy-id user@host                       # copy your public key to the server
```

Now retry the BatchMode test above.

### Connection probe

`quad-client connect-test stdio-ssh --ssh-user alice --ssh-host lab.example.com`:
1. Builds: `ssh -o BatchMode=yes -o ConnectTimeout=12 alice@lab.example.com python -c 'import quad.mcp.server; print("OK")'`
2. Runs it; checks for exit 0 and `OK` in stdout
3. Classifies common failures:
    - `Permission denied (publickey)` → hint: set up SSH key auth
    - `Could not resolve hostname` → hint: check DNS / hostname spelling
    - `ModuleNotFoundError` → hint: install the QUAD server on the remote machine

### settings.json shape

```json
{
  "mcpServers": {
    "quad": {
      "command": "ssh",
      "args": [
        "-p", "22",
        "-i", "/home/alice/.ssh/lab_key",
        "-o", "BatchMode=yes",
        "-o", "ServerAliveInterval=30",
        "alice@lab.example.com",
        "python -m quad.mcp.server"
      ]
    }
  }
}
```

`ServerAliveInterval=30` keeps the SSH connection alive across periods
of inactivity. `BatchMode=yes` makes SSH fail fast on auth instead of
prompting (which Claude Code can't answer).

---

## sse-http

```
┌─────────────────────────┐               ┌─────────────────────────┐
│   Developer laptop      │               │  HTTP gateway / proxy   │
│   ┌─────────────────┐   │               │  (TLS termination,      │
│   │   Claude Code   │   │   HTTPS+SSE   │   load balancing,       │
│   └────────┬────────┘   ├───────────────┤   auth)                 │
│            │             │               └────────────┬────────────┘
└─────────────────────────┘                            │
                                                        │
                                            ┌───────────▼─────────┐
                                            │ MCP server pool     │
                                            │ (quad.mcp.server)   │
                                            │ behind the gateway  │
                                            └─────────────────────┘
```

### How it works

The QUAD server runs as a long-lived HTTP service speaking MCP over
Server-Sent Events. Claude Code maintains an HTTP/1.1 keep-alive
connection to the URL; messages flow as SSE events. Auth is via
bearer token in the `Authorization` header.

### Pros

- Multi-tenant: one gateway can serve hundreds of users
- Stateless from the client's perspective — no SSH key management
- Can sit behind standard HTTPS infrastructure (CDN, WAF, etc.)
- Auth via OAuth / API keys integrates with existing IAM

### Cons

- Someone has to operate the gateway (your DevOps / Platform team)
- Network round-trip per request (vs local stdio)
- Extra moving piece compared to stdio transports

### Prerequisites

1. Someone has stood up an MCP-over-SSE gateway pointing at QUAD servers.
   - QUAD itself doesn't ship a hosted gateway — that's a deployment concern.
   - Common patterns: `nginx` or `traefik` reverse-proxying to `quad.mcp.server` with an SSE adapter.
2. You have the URL.
3. *(Optional)* You have a bearer token. Set it in an env var:
   ```bash
   export QUAD_MCP_TOKEN="<your-token>"
   ```

### Connection probe

`quad-client connect-test sse-http --sse-url https://mcp.example.com/sse [--auth-token <token>]`:
1. Issues `GET <url>` with optional `Authorization: Bearer ...` header
2. Classifies the response:
    - `2xx` → `ok=True`
    - `401` / `403` → `ok=False`, hint: check the token
    - `404` / `405` → `ok=False`, hint: check the URL path
    - Connection refused / timeout → `ok=False`, hint: check the server is running

### settings.json shape

```json
{
  "mcpServers": {
    "quad": {
      "transport": {
        "type": "sse",
        "url": "https://mcp.example.com/sse",
        "headers": {
          "Authorization": "Bearer ${env:QUAD_MCP_TOKEN}"
        }
      }
    }
  }
}
```

Claude Code expands `${env:QUAD_MCP_TOKEN}` at request time, so the
actual token value never lives in the file. Commit `settings.json` to
your repo without leaking secrets.

---

## Mixed deployments

Nothing prevents one IDE machine from being provisioned with multiple
QUAD servers (e.g. one local for development, one hosted for CI). After
running `quad-client install` for the first server, hand-edit
`.claude/settings.json` to add a second entry:

```json
{
  "mcpServers": {
    "quad-local":  { "command": "python", "args": ["-m", "quad.mcp.server"] },
    "quad-hosted": { "transport": { "type": "sse", "url": "..." } }
  }
}
```

Claude Code surfaces both as separate tool prefixes (`mcp__quad-local__*`
and `mcp__quad-hosted__*`).

The QUAD-Client CLI assumes a single MCP server entry today; multi-server
provisioning is a candidate for a future minor version.

---

## Picking by user persona

| User | Recommended transport |
|---|---|
| Solo developer with a Snapdragon X Elite laptop | `stdio-local` |
| Developer who already SSHes to a lab Snapdragon box | `stdio-ssh` |
| Team of 5-20 sharing one lab machine | `stdio-ssh` from each laptop |
| 100+ developer org with a Platform team | `sse-http` behind a hosted gateway |
| CI runner that needs MCP for automated tests | `stdio-local` (preferred) or `sse-http` |
| Ephemeral Codespaces / dev container | `sse-http` (servers don't outlive the container) |

---

## See also

- [`INSTALL.md`](INSTALL.md) — step-by-step install per transport
- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) — common errors per transport
- [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) — how to add a 4th transport
