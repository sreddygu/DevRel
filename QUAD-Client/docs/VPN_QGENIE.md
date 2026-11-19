# VPN & QGenie — Claude Model Access

> Claude Code reaches Claude models **via QGenie**, which is only reachable over
> the corporate VPN. If the VPN drops, Claude Code can't reach the model and
> fails in confusing ways. The IQ-9075 bring-up lost time to this (retrospective
> IQ9-29 / IQ9-30); this doc makes the requirement explicit.

_Author: Pavan R_

---

## The rule

**Connecting to the VPN (BIG-IP Edge Client) is mandatory** for:

- QGenie chat access, and
- Claude model access in Claude Code (Claude is routed through QGenie).

If Claude Code reports auth/connection errors, **check the VPN first** — a
dropped BIG-IP Edge Client session is the most common cause, not a bad install.

## Credential aliases — they are the same thing

These environment variables are **aliases for the same credential** in this
deployment. Set **one** (prefer `QGENIE_API_KEY`):

- `QGENIE_API_KEY`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_AUTH_TOKEN`

`quad-client doctor` includes a **"Model access token"** check that passes when
any of these is set and warns (with this explanation) when none is.

## The env-inheritance trap (set it in the SAME shell)

Environment variables set in a PowerShell window are **not** inherited by
Claude Code launched from the **VS Code GUI** (clicking the icon). Two ways to
avoid the trap:

1. **Launch Claude Code from the same PowerShell window** where you set the key:
   ```powershell
   $env:QGENIE_API_KEY = "<your-key>"
   claude    # launched from THIS shell — inherits the var
   ```
2. Or set it at **User scope** (persists across shells and GUI launches):
   ```powershell
   setx QGENIE_API_KEY "<your-key>"
   # then open a NEW shell / restart VS Code so it's picked up
   ```

If you set the var in one PowerShell window but open Claude Code from the VS
Code GUI, it **won't** inherit it — this looks like a missing/invalid key.

## Quick recovery checklist

1. Is BIG-IP Edge Client **connected**? Reconnect if not.
2. Is a token set **in the shell that launched Claude Code**? (`echo $env:QGENIE_API_KEY`)
3. Restart Claude Code from that shell after reconnecting / setting the token.
