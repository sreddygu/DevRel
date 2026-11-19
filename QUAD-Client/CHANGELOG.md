# Changelog

All notable changes to QUAD-Client are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Corporate-proxy TLS auto-retry** (`quad_mcp_client.local.download.download_file`):
  model/asset downloads that fail with `CERTIFICATE_VERIFY_FAILED` now retry
  automatically via the OS trust store (`truststore`) → a CA bundle env var
  (`QUAD_CA_BUNDLE`/`REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE`) → an unverified
  fallback. The MobileNetV2 sample uses it. Documented in
  `docs/NPU_QUICKSTART.md` §10 (IQ9 issue 24).
- **`quad-qnn-runtime-debug` skill** — symbol-level (`LD_DEBUG=libs`) runtime
  debugging of compiled QNN/QAIRT artifacts: ABI/version matching, backend-init
  vs missing-symbol diagnosis, ordered GPU/OpenCL workflow, input-contract
  validation (IQ9 issue 43).
- **ConvInteger INT8 rejection** — `ort_qnn.create_npu_session` now raises
  `ConvIntegerFormatError` for ConvInteger/MatMulInteger INT8 ONNX models
  instead of letting ORT silently fall back to CPU; the HTP needs QDQ
  (IQ9 issue 23).
- **`hardware_detect` completeness** — the local probe now returns `storage_gb`
  and `os_version`, and resolves GPU/NPU specs from real WMI/`/proc` CPU strings
  (SoC part-number aliases) instead of reporting "unknown" (IQ9 issue 22).
- **quad-doctor**: new `TLS CA bundle env vars` check flags a stale
  `REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE` pointing at a missing file (IQ9 issue 47).
- `QUAD_MCP_URL` / `QUAD_MCP_TOKEN` added to `.env.example` (IQ9 issue 40).

### Changed
- `install.ps1` now honors `$env:PYTHON` **before** scanning PATH, so an
  explicitly chosen interpreter is no longer discarded by the version gate
  (IQ9 issue 25).
- Skill refresh from IQ-9075 findings: `quad-detect` (deep-probe checklist),
  `quad-profile` (profiler failure modes + ORT-version reproducibility),
  `quad-npu-prereqs` (Linux-SoC ORT-EP caveat), `quad-convert` (QDQ-only,
  int8-not-always-faster, remote-fs boundary) (IQ9 issues 42/45/46/48).
- Moved `generate_capabilities_guide.py` and `generate_pitch_presentation.py`
  from `docs/` to `tools/` (IQ9 issues 52/53).

## [0.2.0] - 2026-06-30

### Added

- **Typed `QuadClient` SDK** (`quad_mcp_client.client`) — the programmatic
  path the README promised. `create_client()` auto-resolves the transport
  (explicit args → `QUAD_MCP_URL`/`QUAD_MCP_TOKEN` → discovered
  `.claude/settings.json` → local spawn), typed methods for all six MCP tools,
  `RetryPolicy` (exponential backoff), `ClientAuth` (bearer + mTLS + CA bundle),
  `search_aihub()` pagination, and schema-compat across fastmcp envelope
  shapes. fastmcp is imported lazily so the core package stays lightweight.
- **Server-first hardware discovery** — `detect_hardware_server_first()` (and
  `quad-client detect`, now server-first with a `--local-only` escape hatch)
  queries the server's authoritative, registry-enriched `hardware_detect`,
  falling back to the local static probe only when the server is unreachable.
  Every result carries a `discovery_source` provenance tag.

### Fixed

- **Skills accuracy**: removed the bogus `mcp__quad__doctor` allowed-tool (the
  server registers no such tool; the doctor flow is CLI-based); added
  `mcp__quad__aihub_select` to the default permissions; corrected the
  quickstart "five tools" → six.
- **Honest OS provenance**: a macOS host probing a Linux target envelope now
  records `host_os=macos` instead of silently claiming it *is* Linux.
- **Broken sample**: `samples/gpu_inference` imported a `create_client` that
  didn't exist — now runs against the real SDK's typed methods.

## [0.1.0] - 2026-05-08

### Added

- Initial public release of `quad-mcp-client`, extracted from the QUAD
  repository as a standalone, lightweight client provisioner.
- `MCPClientProvisioner` abstract base, `ProvisionResult` dataclass, and
  `get_provisioner()` factory under `quad_mcp_client.__init__`.
- `ClaudeCodeProvisioner` — concrete provisioner for Claude Code that
  generates `.claude/settings.json` and installs 11 bundled skill files
  into `.claude/skills/`.
- Three transport templates for `settings.json`:
  - `stdio-local` — server + client on the same machine
  - `stdio-ssh` — server on a remote machine, proxied over SSH
  - `sse-http` — hosted MCP service over HTTP/Server-Sent Events
- Three connection probes (`probe_stdio_local`, `probe_stdio_ssh`,
  `probe_sse_http`) plus a `probe()` dispatcher. Each returns a
  `ConnectionProbeResult` with context-specific failure hints.
- Standalone `quad-client` Typer CLI with five subcommands:
  `install`, `status`, `preview`, `uninstall`, `connect-test`.
- `install.sh` — Bash installer with interactive transport prompts and
  pre-provision connection verification.
- `install.ps1` — Windows PowerShell entry point that delegates to
  `install.sh` (auto-installs Git Bash via `winget` if missing).
- 46 tests covering CLI commands, connection probes (real + mocked),
  settings templates, the provisioner end-to-end, and a subprocess-isolated
  test verifying the lightweight package doesn't pull heavy modules.
- Public-facing documentation: `README.md`, `docs/INSTALL.md`,
  `docs/TRANSPORTS.md`, `docs/DEVELOPER_GUIDE.md`, `docs/TROUBLESHOOTING.md`.
- GitHub Actions CI workflow running tests on Linux/macOS/Windows ×
  Python 3.10/3.11/3.12 plus a ruff lint job.
- Apache 2.0 license.

[Unreleased]: https://github.qualcomm.com/pavanr/QUAD-Client/compare/v0.1.0...HEAD
[0.1.0]: https://github.qualcomm.com/pavanr/QUAD-Client/releases/tag/v0.1.0
