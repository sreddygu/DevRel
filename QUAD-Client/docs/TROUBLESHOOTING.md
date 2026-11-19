# Troubleshooting

Common errors when running QUAD-Client, grouped by symptom.

If your issue isn't here, open one at
[github.qualcomm.com/pavanr/QUAD-Client/issues](https://github.qualcomm.com/pavanr/QUAD-Client/issues)
with the output of:

```bash
quad-client --version
quad-client status
quad-client connect-test <your-transport> [<args>]   # paste the full output
```

---

## Install-time errors

### `Python not found on PATH (tried: python3)`

The installer needs Python 3.10+ on PATH. On Windows, the installer
defaults to `python` (without the `3`) — if you only have `python3`,
set `PYTHON=python3 ./install.sh`.

If you don't have Python installed:
- **Windows**: Download from [python.org](https://www.python.org/downloads/) — make sure to tick "Add to PATH".
- **macOS**: `brew install python@3.12`
- **Linux**: `apt install python3.12` or `dnf install python3.12`

### `quad_mcp_client.cli not importable after install`

Something went wrong with the pip install. Run with verbose output:

```bash
python -m pip install -e . -v
```

The most common cause: trying to install on a system Python without
permissions. Always use a virtualenv:

```bash
python -m venv .venv
source .venv/bin/activate                      # or .venv\Scripts\Activate.ps1
pip install -e .
```

### `Bootstrap fails: 'winget' is not recognized`

You're on Windows < 10 1809. Install Git for Windows manually from
[git-scm.com](https://git-scm.com/) and re-run `install.ps1`. Or skip
the bootstrap and run `install.sh` directly from Git Bash.

---

## stdio-local probe failures

### `server exited immediately with code 1` + `ModuleNotFoundError: No module named 'quad'`

The QUAD MCP server isn't installed on this machine. Install it from
the separate [QUAD repository](https://github.qualcomm.com/pavanr/QUAD):

```bash
git clone https://github.qualcomm.com/pavanr/QUAD.git
cd QUAD
./install.sh --mock-only            # ~150 MB, no QAIRT SDK
# or:
./install.sh --qairt-archive ~/Downloads/qairt-2.45.0.zip
```

Then re-run `quad-client connect-test stdio-local`.

### `server exited immediately with code 1` + cryptic stderr

Check the `stderr_excerpt` in the probe output. Common cases:

| Stderr fragment | Meaning |
|---|---|
| `ImportError: cannot import name 'X' from 'Y'` | The QUAD server is installed but at a version with a different API. Update QUAD: `pip install -U quad-agent` (in the QUAD venv). |
| `ConfigError: ...` | The QUAD server can't load its config. Run `quad doctor` (in the QUAD venv) to diagnose. |
| `OSError: [Errno 13] Permission denied` | Probably a file in `./sdks/` or `~/.quad/` isn't readable. `chmod -R u+r ./sdks/`. |

### Probe passes but Claude Code can't connect

The probe verifies the server *starts*; Claude Code also requires the
server to *speak MCP correctly*. If the probe is `ok` but Claude Code
shows the server as disconnected:

1. Open Claude Code's MCP debug log (Settings → Developer → MCP logs)
2. Look for the actual error message
3. Most often: a Python import error that takes >1 second to surface
   (the probe only waits 1 second). Bump the probe timeout:
   ```bash
   quad-client connect-test stdio-local --timeout 10
   ```
   Or run the server manually for 10 seconds and watch stderr:
   ```bash
   python -m quad.mcp.server
   ```

---

## stdio-ssh probe failures

### `Permission denied (publickey)`

SSH key authentication failed. The server doesn't have your public key
in its `~/.ssh/authorized_keys`.

**Fix:**
```bash
ssh-copy-id user@host                          # easiest, if available
# or manually:
cat ~/.ssh/id_ed25519.pub | ssh user@host "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

If you have multiple keys, specify which one:
```bash
quad-client install --transport stdio-ssh \
    --ssh-user alice --ssh-host lab.example.com \
    --ssh-key ~/.ssh/quad_lab_key
```

### `Could not resolve hostname X`

DNS lookup failed. Verify:
```bash
ping lab.example.com
# or:
nslookup lab.example.com
```

If the host is on your local network and your DNS doesn't resolve `.lan`
addresses, use the IP directly:
```bash
quad-client install --transport stdio-ssh \
    --ssh-user alice --ssh-host 192.168.1.42
```

### `SSH connection timed out after 12s`

The server is unreachable from this network. Check:
1. Is the server actually up? (`ping <host>`)
2. Is SSH listening on the expected port? (`nmap -p 22 <host>`)
3. Is there a firewall between you and the server? (try from a different network)

If it's behind a corporate firewall, you may need a VPN or a jump host:
```bash
# Add to ~/.ssh/config
Host lab.example.com
    ProxyJump bastion.corp.example.com
```
Then SSH transparently uses the jump host.

### `ssh exit 1: ModuleNotFoundError: No module named 'quad'`

SSH worked but the QUAD server isn't installed on the remote machine.
Install it there:

```bash
ssh user@host
# on the remote:
git clone https://github.qualcomm.com/pavanr/QUAD.git
cd QUAD
./install.sh
```

### `ssh: command not found` (on the client)

Install OpenSSH:
- **Windows**: `winget install Microsoft.OpenSSH.Client`
- **macOS / Linux**: usually preinstalled; otherwise `apt install openssh-client` etc.

### Claude Code hangs when invoking SSH

The SSH connection prompted for input (password, host-key confirmation,
2FA) and Claude Code can't see or answer it.

**Fix**: ensure SSH is fully non-interactive. The probe uses
`-o BatchMode=yes` which matches the settings.json — if the probe
passes but Claude Code hangs, something else is prompting:

```bash
# Verify with the same flags Claude Code uses:
ssh -o BatchMode=yes -o ServerAliveInterval=30 user@host echo ok
```

If this hangs:
- 2FA enforced by the server? Use a key-only path or push a long-lived ticket
- Host key not yet cached? Run `ssh -o StrictHostKeyChecking=accept-new user@host echo ok` once

---

## sse-http probe failures

### `auth failed: HTTP 401` (or 403)

The server is reachable but rejected your token.

**Check:**
1. The env var is set in the shell that runs `quad-client install`:
   ```bash
   echo $QUAD_MCP_TOKEN                   # not empty?
   ```
2. The token hasn't expired — most providers have rotation policies.
3. The token has the right scope — some MCP gateways issue read-only
   vs. full-access tokens.
4. The server expects a different auth header (e.g. `X-API-Key` instead of `Authorization: Bearer`). The hosted-server admin can confirm.

### `endpoint not found: HTTP 404` (or 405)

The URL path is wrong. MCP servers typically expose one of:
- `/sse`
- `/mcp`
- `/`

Try each in turn:
```bash
quad-client connect-test sse-http --sse-url https://mcp.example.com/sse
quad-client connect-test sse-http --sse-url https://mcp.example.com/mcp
quad-client connect-test sse-http --sse-url https://mcp.example.com/
```

The hosted-server admin should document the correct path.

### `connection refused`

The server isn't running on that URL. Verify:

```bash
curl -v https://mcp.example.com/sse
```

If `curl` also gets connection refused, the URL itself is wrong or the
server is down.

### `connection timed out after 8s`

Network reachability problem. Check from outside any corporate VPN:

```bash
curl --max-time 5 https://mcp.example.com/sse
```

If a slow network is genuinely the issue:
```bash
quad-client connect-test sse-http --sse-url <url> --timeout 30
```
But Claude Code's own request timeout will eventually bite. If your
connection is slow enough that 8 seconds isn't enough, consider the
`stdio-ssh` transport instead (you can use `Mosh` to handle high latency).

### `httpx not installed`

Reinstall with the standard deps:
```bash
pip install --upgrade quad-mcp-client
# or, from a checkout:
pip install -e .
```

---

## After install — Claude Code doesn't see the QUAD tools

### Step 1: confirm settings.json is picked up

Restart Claude Code. Then check Settings → MCP Servers — you should see
`quad` listed.

If it's not listed: Claude Code may be looking for `settings.json` in a
different directory. By default it reads `<workspace>/.claude/settings.json`.
If your workspace is somewhere else, run:

```bash
quad-client install --project-root /actual/workspace/path
```

### Step 2: confirm the connection

In Claude Code, ask: "What MCP tools are available?"

If `quad` shows up with no tools listed, the server is configured but
not actually responding. Re-run the probe:

```bash
quad-client connect-test <your-transport> [<args>]
```

### Step 3: check Claude Code's MCP logs

Settings → Developer → MCP logs. Filter for `quad`. The error message
there is more detailed than what the probe sees.

### Step 4: tools listed but error when invoked

The MCP handshake worked but a specific tool call failed. The error
message will mention the tool. Common cases:

- `QUAD_ADAPTER_MODE not set` → re-run `quad-client install --adapter-mode mock` (or `real`)
- `SDK not found` → install QAIRT SDK on the server side (see QUAD repo)
- `permission denied` → the tool isn't in the `permissions.allow` list. Re-run `quad-client install --force` to refresh.

---

## Skill-related issues

### Skills don't show up in Claude Code's slash menu

1. Restart Claude Code after running `quad-client install` — skills are
   loaded at startup.
2. Verify the files are present:
   ```bash
   ls -la .claude/skills/
   # Expected: quad-quickstart.md, quad-detect.md, quad-convert.md, ...
   ```
3. If files are missing, re-run with `--force`:
   ```bash
   quad-client install --force
   ```

### A skill triggers when I don't want it to

Skills include a YAML `description` that Claude Code uses to decide
when to fire. If you find a skill is over-triggering:
1. Open the `.md` file under `.claude/skills/`
2. Tighten the `description` field (e.g. add specific keywords the skill should respond to)
3. The change takes effect immediately for new conversations

You can also delete a skill outright:
```bash
rm .claude/skills/quad-quickstart.md
```

The bundled skill won't come back unless you run `quad-client install --force`
(at which point it'll be restored).

---

## Getting help

If none of the above resolves your issue:

1. **Check your version**: `quad-client --version`. Make sure you're on the latest.
2. **Search existing issues**: [github.qualcomm.com/pavanr/QUAD-Client/issues](https://github.qualcomm.com/pavanr/QUAD-Client/issues)
3. **Open a new issue** with:
   - Your OS + Python version
   - The full output of `quad-client connect-test <transport> ...`
   - The exit code
   - What you expected to happen vs. what did happen

For bugs in the **QUAD MCP server itself** (not the client), file at
[github.qualcomm.com/pavanr/QUAD/issues](https://github.qualcomm.com/pavanr/QUAD/issues).
