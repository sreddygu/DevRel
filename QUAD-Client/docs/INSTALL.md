# Installing QUAD-Client

This page walks through installing the QUAD MCP client on a developer
machine. For *server* installation (the QUAD MCP server itself), see
the separate [QUAD repository](https://github.qualcomm.com/pavanr/QUAD).

## What you're installing

| | Server (`pavanr/QUAD`) | **Client (this repo)** |
|---|---|---|
| Footprint | ~1.2 GB (with SDK) | **~6 MB** |
| Provides | MCP tools (the actual workhorse) | `.claude/settings.json` + skills + connection probe |
| Lives on | One machine in your network (developer laptop, lab box, or cloud) | Every IDE machine |
| Required deps | Python 3.10+, FastMCP, NumPy, Pydantic, Jinja2, etc. | Python 3.10+, **typer**, **httpx** — that's it |

You can have many clients pointing at one server.

---

## Prerequisites

| OS | Required |
|---|---|
| **Linux** | Python 3.10–3.12 (`apt install python3.12` / `dnf install python3.12`) |
| **macOS** | Python 3.10–3.12 (`brew install python@3.12`) |
| **Windows** | Python 3.10–3.12 from [python.org](https://www.python.org/downloads/) **or** Microsoft Store. PowerShell 5+ (built in) or PowerShell 7 (`winget install Microsoft.PowerShell`). Git Bash (`winget install Git.Git`) — auto-installed by `install.ps1` if missing. |

> **Python version + architecture matter for NPU work.** The NPU wheels
> (`onnxruntime-qnn`) are built **only for Python 3.10–3.12** and **only for
> native ARM64**. Python 3.13+ fails with a cryptic wheel error; an emulated
> x86-64 Python on a Snapdragon box silently fails to load NPU support. The
> installer now rejects 3.13+, and `quad-client doctor` checks both version and
> arch. If you'll run NPU inference, read **[NPU_QUICKSTART.md](NPU_QUICKSTART.md)**
> first — it covers the two-venv pattern, the onnxruntime/onnxruntime-qnn
> conflict, provider verification, and the first-run HTP warmup.

For `stdio-ssh` transport, also: an OpenSSH client and a configured
key-based SSH connection to the server machine.

For `sse-http` transport: nothing extra — `httpx` is already a dep.

---

## Three install paths

Pick the one that matches how you got the package.

### Path A — Install from PyPI (recommended)

Once `quad-mcp-client` is published to PyPI:

```bash
pip install quad-mcp-client
```

Then run the provisioner:

```bash
quad-client install
```

You'll get an interactive prompt:

```
Where does the QUAD MCP server live?
  1) stdio-local  — same machine
  2) stdio-ssh    — remote machine, via SSH
  3) sse-http     — remote machine, hosted HTTP/SSE service

Choice [1/2/3, default 1]:
```

Pick the transport that matches your topology. Per-transport details
follow below.

### Path B — Clone + install.sh (Linux / macOS / Git Bash on Windows)

```bash
git clone https://github.qualcomm.com/pavanr/QUAD-Client.git
cd QUAD-Client
./install.sh
```

`install.sh` is interactive. It:
1. Verifies Python 3.10+ is on PATH
2. Prompts for the transport (or accepts `--transport=...`)
3. Prompts for transport-specific details (SSH user/host, SSE URL)
4. Installs `quad-mcp-client` in editable mode from this checkout
5. **Probes the connection** to the configured server
6. If the probe passes, writes `.claude/settings.json` + `.claude/skills/`
7. Prints next-step verification commands

If the connection probe fails, the install **stops** with a clear
diagnostic and a hint. Re-run with `--force` to provision anyway.

### Path C — Clone + install.ps1 (Windows PowerShell)

```powershell
git clone https://github.qualcomm.com/pavanr/QUAD-Client.git
cd QUAD-Client
.\install.ps1
```

`install.ps1`:
1. Verifies Python 3.10+ is on PATH
2. Locates Git Bash (auto-installs via `winget` if missing)
3. Delegates to `install.sh` with the same flags

You can pass any `install.sh` flag through `install.ps1`:

```powershell
.\install.ps1 -Transport stdio-ssh -SshUser alice -SshHost lab.lan
.\install.ps1 -Transport sse-http -SseUrl https://mcp.example.com/sse -SseAuthTokenEnv QUAD_MCP_TOKEN
.\install.ps1 -Force                                                    # skip the connection probe
```

---

## Per-transport setup

### stdio-local

The simplest case. The QUAD MCP server runs on this same machine; Claude
Code spawns it as a subprocess.

**Prerequisite**: the QUAD server is installed on this machine. From the
[QUAD repository](https://github.qualcomm.com/pavanr/QUAD):

```bash
git clone https://github.qualcomm.com/pavanr/QUAD.git
cd QUAD
./install.sh                              # ~1.2 GB; or --mock-only for ~150 MB
```

Then in your project:

```bash
quad-client install --transport stdio-local
```

What ends up in `.claude/settings.json`:

```json
{
  "permissions": { "allow": [ "mcp__quad__hardware_detect", "..." ] },
  "mcpServers": {
    "quad": {
      "command": "python",
      "args": ["-m", "quad.mcp.server"],
      "cwd": "${workspaceFolder}",
      "env": { "QUAD_ADAPTER_MODE": "mock" }
    }
  }
}
```

### stdio-ssh

The QUAD server runs on a remote lab/cloud machine. Claude Code spawns
`ssh` and pipes MCP-over-stdio through the SSH tunnel.

**Prerequisites**:
1. The QUAD server is installed on the remote machine (same instructions as above, on that box).
2. **Key-based SSH** to the remote machine works *without* a password prompt.
   - Verify: `ssh user@host echo ok` should print `ok` and exit immediately.
   - If it prompts for a password, set up `ssh-copy-id user@host` first.
3. Optionally: a specific private key (`--ssh-key`) if not the default.

```bash
quad-client install \
    --transport stdio-ssh \
    --ssh-user alice \
    --ssh-host lab.example.com \
    --ssh-port 22 \
    --ssh-key ~/.ssh/quad_lab_key
```

Or interactive:

```bash
./install.sh
# Choice [1/2/3]: 2
# SSH username: alice
# SSH hostname: lab.example.com
# Path to SSH private key (Enter for default): ~/.ssh/quad_lab_key
```

What ends up in `settings.json`:

```json
{
  "permissions": { "allow": [...] },
  "mcpServers": {
    "quad": {
      "command": "ssh",
      "args": [
        "-p", "22",
        "-i", "/home/alice/.ssh/quad_lab_key",
        "-o", "BatchMode=yes",
        "-o", "ServerAliveInterval=30",
        "alice@lab.example.com",
        "python -m quad.mcp.server"
      ]
    }
  }
}
```

The `BatchMode=yes` is critical — it makes SSH fail fast on auth issues
rather than hang in Claude Code waiting for a password Claude Code
can't enter.

### sse-http

The QUAD server runs as a hosted HTTP service speaking MCP over
Server-Sent Events. Common when an org runs a multi-tenant gateway
behind a load balancer.

**Prerequisites**:
1. The hosted server URL.
2. Optionally: a bearer token. Set the token in an env var (e.g.
   `QUAD_MCP_TOKEN`) and pass the env var name — the actual token never
   touches `settings.json`.

```bash
export QUAD_MCP_TOKEN="<your-token>"
quad-client install \
    --transport sse-http \
    --sse-url https://mcp.example.com/sse \
    --sse-auth-token-env QUAD_MCP_TOKEN
```

What ends up in `settings.json`:

```json
{
  "permissions": { "allow": [...] },
  "mcpServers": {
    "quad": {
      "transport": {
        "type": "sse",
        "url": "https://mcp.example.com/sse",
        "headers": { "Authorization": "Bearer ${env:QUAD_MCP_TOKEN}" }
      }
    }
  }
}
```

Claude Code substitutes `${env:QUAD_MCP_TOKEN}` at request time.

---

## Verifying the install

```bash
quad-client status            # what's installed in this project
```

Expected output:

```
Client:           claude_code
settings.json:    present @ /path/to/project/.claude/settings.json
Skills dir:       present @ /path/to/project/.claude/skills
Bundled skills:   11
Installed skills: 11
```

Re-test the connection without writing files:

```bash
quad-client connect-test stdio-local
quad-client connect-test stdio-ssh --ssh-user alice --ssh-host lab.example.com
quad-client connect-test sse-http --sse-url https://mcp.example.com/sse
```

Expected on success:

```
✓ stdio-local reachable in 423 ms — {'command': 'python', 'args': ['-m', 'quad.mcp.server']}
```

---

## Updating

```bash
pip install --upgrade quad-mcp-client
quad-client install --force         # rewrite settings.json + skills
```

`--force` overwrites existing `settings.json` and bundled skills (it
preserves any skills you added yourself).

---

## Uninstalling

```bash
quad-client uninstall                               # remove the bundled skills
rm -rf <project-root>/.claude/settings.json         # remove the settings (if you want)
pip uninstall quad-mcp-client                       # remove the package
```

`uninstall` deliberately doesn't auto-delete `settings.json` — you may
have customised it.

---

## Troubleshooting

See [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) for common errors.
