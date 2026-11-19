# devrelAgent Developer Guide

> Audience: contributors who want to extend devrelAgent — add a new IDE
> client, support a new transport, modify a probe, or improve the bundled
> skills. Also useful background for **users** who want to understand
> exactly what `devrel-agent install` does to their machine.

This guide assumes basic familiarity with Python, pytest, and Claude Code.
For installation and end-user usage, see [`README.md`](../README.md) and
[`INSTALL.md`](INSTALL.md).

---

## Table of contents

1. [Architecture overview](#1-architecture-overview)
2. [Repository layout](#2-repository-layout)
3. [Local development setup](#3-local-development-setup)
4. [Testing](#4-testing)
5. [Adding a new MCP transport](#5-adding-a-new-mcp-transport)
6. [Adding support for a new IDE client](#6-adding-support-for-a-new-ide-client)
7. [Modifying or adding bundled Claude Code skills](#7-modifying-or-adding-bundled-claude-code-skills)
8. [Connection probes — design and extension](#8-connection-probes--design-and-extension)
9. [Release process](#9-release-process)
10. [Versioning policy](#10-versioning-policy)
11. [Coding standards](#11-coding-standards)
12. [Contributing pull requests](#12-contributing-pull-requests)
13. [Frequently asked questions](#13-frequently-asked-questions)

---

## 1. Architecture overview

devrelAgent has **one job**: produce a correct `.claude/settings.json`
for whichever IDE the developer uses, plus a verified path to a DevRel MCP
server they can reach. Nothing else.

```
                                       ┌─────────────────────────────────┐
                                       │       Developer laptop          │
                                       │                                 │
                                       │   ┌─────────────────────────┐   │
                                       │   │     Claude Code IDE     │   │
                                       │   └────────────┬────────────┘   │
                                       │                │                │
                                       │      reads .claude/settings.json│
                                       │                │                │
                                       │      uses bundled .claude/skills│
                                       │                │                │
   ┌──────────────────┐                │   ┌────────────▼────────────┐   │
   │  devrel-mcp-client │  installs      │   │ MCP server connection   │   │
   │  (this package)  │ ────────────►  │   │ (one of three flavors)  │   │
   └──────────────────┘                │   └────────────┬────────────┘   │
                                       └────────────────┼────────────────┘
                                                        │
                       ┌────────────────────────────────┼────────────────────────────────┐
                       │                                │                                │
                       ▼                                ▼                                ▼
        ┌──────────────────────────┐    ┌──────────────────────────┐    ┌──────────────────────────┐
        │      stdio-local         │    │       stdio-ssh          │    │        sse-http          │
        │ python -m devrel.mcp.server│    │ ssh user@host python …   │    │ HTTPS to MCP gateway     │
        │ on this same machine     │    │ on a remote lab machine  │    │ behind a load balancer   │
        └──────────────────────────┘    └──────────────────────────┘    └──────────────────────────┘
                       │                                │                                │
                       └────────────────────────────────┴────────────────────────────────┘
                                                        │
                                                        ▼
                                       ┌──────────────────────────────────┐
                                       │       DevRel MCP server            │
                                       │  (separate repo: pavanr/DevRel)    │
                                       │                                  │
                                       │  - QAIRT SDK adapter             │
                                       │  - 5 MCP tools                   │
                                       │  - hardware probe / compiler /   │
                                       │    runtime / codegen / serve     │
                                       └──────────────────────────────────┘
```

**Layered responsibilities inside the package**

| Layer | Module | What lives here | What does NOT |
|---|---|---|---|
| **Abstraction** | `devrel_client.__init__` | `MCPClientProvisioner` ABC, `ProvisionResult` dataclass, `get_provisioner()` factory | No I/O; no transport-specific code |
| **Connection** | `devrel_client.connection` | `probe_stdio_local`, `probe_stdio_ssh`, `probe_sse_http`, `probe()` dispatcher | No file writes; no IDE specifics |
| **CLI** | `devrel_client.cli` | Five Typer commands wrapping the layers below | No business logic — pure delegation |
| **IDE-specific** | `devrel_client.claude_code.*` | settings templates, skill copy, provisioner | Server-side concepts |

Adding support for a new IDE client means adding a sibling subpackage
to `claude_code/`. Adding a new transport means adding a probe and a
settings template. The other layers don't need to change.

---

## 2. Repository layout

```
devrelAgent/
├── README.md                           # End-user landing page
├── LICENSE                             # Apache 2.0
├── pyproject.toml                      # Package metadata + build config
├── install.sh                          # Bash installer (interactive, runs the probe)
├── install.ps1                       # Windows PS5+ entry point that delegates to install.sh
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml                      # ruff + pytest on Linux/macOS/Windows × Py 3.10/3.11/3.12
├── src/
│   └── devrel_client/
│       ├── __init__.py                 # MCPClientProvisioner, ProvisionResult, get_provisioner
│       ├── cli.py                      # `devrel-agent` Typer CLI (5 commands)
│       ├── connection.py               # 3 transport probes + dispatcher
│       └── claude_code/
│           ├── __init__.py             # Re-exports + public API
│           ├── settings.py             # 3 settings.json templates (stdio-local / stdio-ssh / sse-http)
│           ├── skills.py               # Bundled-skill install/uninstall/list
│           ├── provisioner.py          # ClaudeCodeProvisioner + TransportConfig
│           └── skills_content/         # 11 .md skill files (force-included in wheel)
├── tests/
│   ├── test_cli.py                     # Typer CliRunner + lightweight-import subprocess test
│   ├── test_connection.py              # All 3 probes (real + mocked)
│   ├── test_provisioner.py             # ClaudeCodeProvisioner end-to-end
│   └── test_transport_settings.py      # Cross-transport settings template tests
├── docs/
│   ├── INSTALL.md                      # End-user install walkthrough
│   ├── TRANSPORTS.md                   # When to pick which transport
│   ├── DEVELOPER_GUIDE.md              # ← you are here
│   └── TROUBLESHOOTING.md              # Common errors
└── examples/
    └── settings_examples/              # Reference settings.json snippets
```

---

## 3. Local development setup

### 3.1 Prerequisites

- Python ≥ 3.10
- `git`
- `bash` (Git Bash on Windows works fine)
- *(optional)* a DevRel MCP server somewhere reachable to test stdio-local

### 3.2 Clone and install in editable mode

```bash
git clone https://github.qualcomm.com/pavanr/devrelAgent.git
cd devrelAgent

python -m venv .venv
source .venv/bin/activate                  # macOS / Linux
# or:
.venv\Scripts\Activate.ps1                 # Windows PowerShell

pip install -e .[dev]
```

This installs `devrel-mcp-client` in editable mode (so source edits are
picked up live) plus pytest, ruff, mypy, and build.

### 3.3 Verify

```bash
devrel-agent --help          # CLI is on PATH
pytest -q                   # 46 tests, ~5 sec
ruff check .                # lints clean
mypy src/                   # optional — non-strict by default
```

If any test fails on a fresh clone, please open an issue with your
Python version and OS — that's a CI-blocking bug.

---

## 4. Testing

### 4.1 Test suite layout

| File | What it covers |
|---|---|
| `tests/test_connection.py` | All three probe functions, real + mocked. Real test: spawning `python` and verifying clean startup. Mocked tests: SSH errors (DNS, permission, module-not-found), HTTP error codes (200/401/404/timeout). |
| `tests/test_provisioner.py` | `ClaudeCodeProvisioner.install / uninstall / status / render_settings_preview`. Idempotency, force-overwrite, user-skill preservation. |
| `tests/test_transport_settings.py` | All three settings.json templates plus `TransportConfig` dispatch. Verifies each transport's settings shape. |
| `tests/test_cli.py` | Typer CliRunner-based tests for the five subcommands plus a **subprocess-isolated test** that asserts importing `devrel_client.cli` does not pull in any heavy modules. |

### 4.2 Running the suite

```bash
pytest -q                                  # all tests
pytest tests/test_connection.py -v         # one file, verbose
pytest -k transport                        # by keyword
pytest -k "not LightweightImport"          # skip the subprocess test (slowest)
```

### 4.3 The lightweight-import test

`TestLightweightImport.test_client_cli_does_not_pull_heavy_modules` is the
**most important test in the repo**. It boots a fresh Python interpreter,
imports `devrel_client.cli`, then asserts that `sys.modules` contains
none of:

- `fastmcp`, `numpy`, `pydantic`, `onnx`, `fastapi`, `uvicorn`, `psutil`, `jinja2`, `structlog`
- `devrel.adapters.*`, `devrel.runtime.*`, `devrel.compiler.*`, `devrel.codegen.*`, `devrel.serve.*`, `devrel.profiler.*`, `devrel.mcp.*`, `devrel.tools.*`, `devrel.cli.*`

If you find this test failing because of a new feature you added, that's
a sign the new code accidentally pulled in the DevRel server tree — refactor
to keep the dependency boundary clean.

### 4.4 Adding tests

Follow the existing pytest patterns:

- Use `tmp_path` fixture for filesystem state — never write into the repo
- Use `monkeypatch` for `subprocess.run`, `shutil.which`, and `httpx.Client`
- Group related tests in a `class TestX:` so the failure header tells the user where they are
- Aim for one assertion per test; multi-assert tests are fine when they're inspecting one logical behavior

### 4.5 CI

`.github/workflows/ci.yml` runs the suite on:
- `ubuntu-latest`, `macos-latest`, `windows-latest`
- Python 3.10, 3.11, 3.12

Plus `ruff check .` as a separate job. CI must be green before merging.

---

## 5. Adding a new MCP transport

The MCP spec doesn't mandate three transports; it allows any. Suppose you
want to add a fourth — say, `websocket` for an MCP server that speaks
plain WebSockets instead of SSE. Here's what you'd do.

### 5.1 Add the probe

In `src/devrel_client/connection.py`:

```python
def probe_websocket(
    url: str,
    *,
    auth_token: str | None = None,
    timeout_s: float = 8.0,
) -> ConnectionProbeResult:
    """Verify a remote MCP-over-WebSocket endpoint is reachable."""
    try:
        import websockets
    except ImportError:
        return ConnectionProbeResult(
            ok=False, transport="websocket",
            error="websockets not installed",
            hint="pip install websockets",
        )

    # ... handshake logic ...
    return ConnectionProbeResult(ok=True, transport="websocket", latency_ms=elapsed)
```

### 5.2 Wire it into the dispatcher

```python
def probe(transport: Transport, /, **kwargs: Any) -> ConnectionProbeResult:
    if transport == "stdio-local": return probe_stdio_local(**kwargs)
    if transport == "stdio-ssh":   return probe_stdio_ssh(**kwargs)
    if transport == "sse-http":    return probe_sse_http(**kwargs)
    if transport == "websocket":   return probe_websocket(**kwargs)   # ← new
    return ConnectionProbeResult(ok=False, transport=transport, error=f"Unknown transport: {transport!r}")
```

Don't forget to extend the `Transport` `Literal` at the top of the file.

### 5.3 Add the settings template

In `src/devrel_client/claude_code/settings.py`:

```python
def settings_template_websocket(*, url: str, ...) -> dict[str, Any]:
    return {
        "permissions": {"allow": list(DEFAULT_PERMISSIONS)},
        "mcpServers": {
            "devrel": {
                "transport": {"type": "websocket", "url": url},
            }
        },
    }
```

### 5.4 Extend `TransportConfig`

In `src/devrel_client/claude_code/provisioner.py`, add fields and a branch in `to_settings()`.

### 5.5 Update the CLI

In `src/devrel_client/cli.py`, add `--ws-url` options to `install` / `preview` /
`connect-test` and a branch in each command body.

### 5.6 Update the installer

In `install.sh`, add the `4) websocket` choice to the interactive prompt
and the per-transport prompt block + arg-passing block.

### 5.7 Tests

Add tests in `tests/test_connection.py`, `tests/test_transport_settings.py`,
and `tests/test_cli.py` matching the patterns of the existing transports.

### 5.8 Docs

Update `README.md`, `docs/TRANSPORTS.md`, and `docs/INSTALL.md` to mention
the new transport.

That's the full surface area for a transport. **Six files, three test files,
three docs.** The layering exists precisely so this list is short.

---

## 6. Adding support for a new IDE client

The DevRel MCP server doesn't care which IDE connects — it speaks MCP over
stdio. What changes per IDE is **where the config file lives**, **what
schema it follows**, and **what skill / instruction format the IDE
expects**.

Suppose you want to add Cursor support.

### 6.1 Create the subpackage

```
src/devrel_client/cursor/
├── __init__.py
├── settings.py            # Cursor's MCP config shape (different from Claude Code)
├── skills.py              # If Cursor has an equivalent — Cursor calls them "rules"
├── provisioner.py         # CursorProvisioner(MCPClientProvisioner)
└── skills_content/        # Bundled rule files (if applicable)
```

### 6.2 Implement `MCPClientProvisioner`

```python
# src/devrel_client/cursor/provisioner.py
from devrel_client import MCPClientProvisioner, ProvisionResult

class CursorProvisioner(MCPClientProvisioner):
    name = "cursor"

    def install(self, project_root, *, force=False, **kwargs) -> ProvisionResult:
        # Write Cursor's MCP config to the right path
        # (Cursor uses ~/.cursor/mcp.json or .cursor/rules.json depending on scope)
        ...

    def uninstall(self, project_root) -> ProvisionResult: ...
    def status(self, project_root) -> dict[str, Any]: ...
```

### 6.3 Register in the factory

```python
# src/devrel_client/__init__.py
def get_provisioner(client: str = "claude_code") -> MCPClientProvisioner:
    if client == "claude_code":
        from devrel_client.claude_code.provisioner import ClaudeCodeProvisioner
        return ClaudeCodeProvisioner()
    if client == "cursor":                                          # ← new
        from devrel_client.cursor.provisioner import CursorProvisioner
        return CursorProvisioner()
    raise ValueError(...)
```

### 6.4 CLI surface

The CLI's `--client cursor` flag already routes through `get_provisioner`.
You may need to add Cursor-specific options if Cursor's MCP config takes
different parameters than Claude Code's.

### 6.5 Tests

Mirror `tests/test_provisioner.py` as `tests/test_cursor_provisioner.py`.

### 6.6 Documentation

Add a section to `docs/INSTALL.md` covering Cursor's setup.

---

## 7. Modifying or adding bundled Claude Code skills

Skills live in `src/devrel_client/claude_code/skills_content/*.md`.

### 7.1 Skill file format

Each skill is a Markdown file with YAML front matter:

```markdown
---
name: devrel-quickstart
description: Use when the user asks to "get started with DevRel"…
trigger: "quickstart"
---

# DevRel Quickstart Skill

You're guiding the user from cold-start to running inference …
```

The `description` field tells Claude Code when to surface the skill —
keep it specific so Claude doesn't fire it inappropriately.

### 7.2 Adding a new skill

1. Create `src/devrel_client/claude_code/skills_content/devrel-newthing.md`
2. Run `pytest tests/test_provisioner.py::TestSkills` — it auto-discovers `*.md` files, no test changes needed
3. Document the new skill in your PR description

### 7.3 Wheel packaging

The `skills_content/` directory is force-included in the wheel by
`pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/devrel_client/claude_code/skills_content" = "devrel_client/claude_code/skills_content"
```

If you add a sibling directory of skill assets, add a similar
force-include entry, otherwise `pip install` users won't get the files.

### 7.4 Verifying packaging locally

```bash
python -m build              # produces dist/devrel_client-X.Y.Z-*.whl
python -m zipfile -l dist/*.whl | grep skills_content
# expect: a list of all your .md files
```

---

## 8. Connection probes — design and extension

### 8.1 Design contract

Every probe:
- Returns a `ConnectionProbeResult` — never raises
- Sets `ok=True` only on a confirmed-reachable endpoint
- Sets `error` to a single line describing what failed
- Sets `hint` to a context-specific actionable next step
- Stores raw context in `details` (status code, returncode, stderr excerpt)

### 8.2 Why not just speak MCP and call `tools/list`?

A real MCP handshake would be more rigorous, but:
- It pulls in the MCP client SDK (`fastmcp` or similar) — kills the lightweight footprint
- For provisioning, "the server is reachable and the package imports" is a strong-enough signal — most failures *during the install* are at this layer, not the protocol layer
- The actual MCP handshake will be exercised by Claude Code itself the first time the user types something

If you want to add a deeper probe (e.g. an `--mcp-handshake` flag that
optionally pulls in the MCP SDK), keep it opt-in and isolate the import
inside the function so the lightweight default path is preserved.

### 8.3 Hint quality

Hints are the user-experience differentiator. Aim for: **specific, actionable, single-step.**

| Bad hint | Good hint |
|---|---|
| `Connection failed.` | `SSH key auth to alice@lab.example.com failed. Add your public key to the server's ~/.ssh/authorized_keys, or specify a key with --ssh-key.` |
| `Try a different URL.` | `Server is reachable but https://m.example.com/wrong returned 404. Check the URL path — MCP servers typically expose /sse, /mcp, or /.` |
| `Module not found.` | `SSH worked but devrel.mcp.server isn't importable on lab.example.com. Install the DevRel server package on the remote machine: https://github.qualcomm.com/pavanr/DevRel` |

When you add a probe or extend an existing one, write the hint
**before** you write the implementation — it'll force you to think
about the user's failure mode.

---

## 9. Release process

### 9.1 Pre-release checklist

- [ ] All tests passing on CI (Linux/macOS/Windows × Py 3.10/3.11/3.12)
- [ ] `ruff check .` clean
- [ ] CHANGELOG entry under `## [X.Y.Z] - YYYY-MM-DD`
- [ ] Version bump in `pyproject.toml` and `src/devrel_client/__init__.py`
- [ ] If new transport / IDE / CLI flag added: README + INSTALL + TRANSPORTS docs updated
- [ ] If skills changed: bumped count anywhere it's mentioned

### 9.2 Build + publish

```bash
rm -rf dist build
python -m build
python -m twine check dist/*
python -m twine upload dist/*               # requires PyPI credentials
```

Tag the release: `git tag vX.Y.Z && git push --tags`

### 9.3 GitHub release

Create a release on GitHub from the tag. Paste the CHANGELOG section as
the release notes. Attach the `.whl` and `.tar.gz` from `dist/`.

---

## 10. Versioning policy

devrelAgent follows [SemVer](https://semver.org/):

- **Major**: breaking changes to the CLI, the public Python API, or the produced `settings.json` schema (likely if Claude Code itself changes config schema)
- **Minor**: new transports, new IDE clients, new bundled skills, additive CLI flags
- **Patch**: bug fixes, hint-text improvements, dependency bumps

The package is at `0.1.0` while the API stabilises. Pre-1.0 may break
in minor versions; the README will call this out explicitly when it
happens.

---

## 11. Coding standards

- **Python**: 3.10 minimum; use `from __future__ import annotations` everywhere
- **Type hints**: required on all public functions; private helpers can skip them if obvious
- **Docstrings**: required on public APIs; one-liner for trivial helpers; multi-paragraph with Args/Returns for complex
- **Imports**: sorted by `ruff` (`I` rule); no wildcard imports
- **Line length**: 100 chars (ruff `line-length`); long URLs and exception messages exempt
- **Error messages**: full sentences, ending with a period
- **f-strings**: preferred over `.format()` and `%`-formatting
- **`pathlib.Path`** for filesystem paths; never `os.path.join`
- **Subprocess**: always pass list of args, never `shell=True`
- **JSON**: always indent=2 when writing for human inspection
- **Tests**: `tmp_path` fixture for any filesystem state; `monkeypatch` for environment

`ruff` enforces most of this automatically — run `ruff check .` and fix
warnings before committing.

---

## 12. Contributing pull requests

### 12.1 PR checklist

- [ ] Branch named `feat/`, `fix/`, `docs/`, or `chore/` + short description
- [ ] One logical change per PR (split if larger)
- [ ] CI green
- [ ] Updated relevant docs (README / INSTALL / TRANSPORTS / TROUBLESHOOTING)
- [ ] Updated tests; new tests for new behavior
- [ ] CHANGELOG entry under "Unreleased"

### 12.2 PR description template

```
## Summary
1-3 bullet points

## Why
Motivation; what problem does this solve?

## What changes
- File 1: …
- File 2: …

## Test plan
- [ ] pytest -q
- [ ] Manual smoke test: ./install.sh --transport=…
```

### 12.3 Review

PRs need at least one approval before merging. CI must be green.
Squash-merge by default — keeps `main` history readable.

---

## 13. Frequently asked questions

**Q: Why two repos? Why not just keep client code in DevRel?**

Two reasons:
1. **Footprint**: a developer who only ever connects to a remote DevRel server doesn't need to clone 200 MB of compiler / runtime / SDK source. They need ~6 MB.
2. **Audience**: devrelAgent is public-facing and stable. DevRel itself is a much faster-moving server codebase. Splitting them lets each move at its own pace and lets PyPI users `pip install` without getting Qualcomm SDK code.

**Q: Does devrelAgent work without the DevRel server?**

The provisioner does — you can run `devrel-agent install --skip-test` and
it'll write the settings file. But Claude Code won't be able to invoke
the MCP tools until a DevRel server is reachable at the configured location.
The connection probes exist precisely to catch this before it bites the user.

**Q: Why ASCII output by default?**

Actually we use Unicode `✓` and `✗` for the probe summaries — they
render fine on modern terminals (Windows Terminal, PowerShell 7,
iTerm2, Linux terminals). If you're getting `?` characters, your
terminal is using a non-UTF-8 codepage; `chcp 65001` on Windows fixes it.

**Q: Can I add a non-Claude-Code IDE without writing Python?**

Not currently. The `MCPClientProvisioner` ABC is Python — adding a new
client requires implementing it. We may add a JSON-driven provisioner
in the future for IDEs whose config is a single static-template,
single-path operation.

**Q: How do I know which transport to pick?**

See `docs/TRANSPORTS.md`. Short answer: `stdio-local` if the DevRel server
runs on your laptop; `stdio-ssh` if it runs on a lab/cloud machine you
already SSH to; `sse-http` if your org runs a hosted MCP gateway.

**Q: I want to embed `devrel-mcp-client` in a larger installer / bootstrap script. Can I?**

Yes — that's why the package is permissively licensed (Apache 2.0) and
has a stable Python API. Use `from devrel_client import get_provisioner`
and call `.install(Path(...), transport_config=...)` directly. Don't
shell out to `devrel-agent` from inside another Python process.

---

## See also

- [`README.md`](../README.md) — landing page
- [`INSTALL.md`](INSTALL.md) — detailed install walkthrough
- [`TRANSPORTS.md`](TRANSPORTS.md) — how each transport works
- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) — common errors
- [DevRel repository](https://github.qualcomm.com/pavanr/DevRel) — the MCP server side
- [Model Context Protocol spec](https://modelcontextprotocol.io/) — the underlying protocol
