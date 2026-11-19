#!/usr/bin/env bash
# ===========================================================================
# QUAD-Client — Lightweight MCP client installer
#
# Configures Claude Code (or another MCP-compatible IDE) to talk to a
# QUAD MCP server. The MCP server itself lives in the separate QUAD
# repository (https://github.qualcomm.com/pavanr/QUAD) — this installer does NOT
# install the server.
#
# Three deployment topologies are supported. The script asks which one
# you want (or pass --transport):
#
#   1. stdio-local  — server + client on the same machine. You will
#                     need to install the QUAD server separately
#                     (https://github.qualcomm.com/pavanr/QUAD).
#
#   2. stdio-ssh    — server runs on a remote machine; this client
#                     proxies through SSH. You must have key-based SSH
#                     to the server.
#
#   3. sse-http     — server runs as a hosted HTTP/SSE service.
#                     Auth via bearer token in env var.
#
# AI Gateway support (gwapps SDK / NWAIOS / lcmd / aigw_daemon):
# --------------------------------------------------------------
# This client installer does NOT install the gwapps SDK — that's a
# server-side dependency. To enable AI Gateway development:
#   1. On the QUAD server machine, install the gwapps SDK and run:
#        ../QUAD/install.sh --adapters qairt,qnn,gwapps
#      (or `--adapters gwapps` for AI Gateway only).
#   2. Drop a gwapps-sdk-<ver>.tar.gz under QUAD/QUAD_Packages/gwapps/
#      before running the server installer.
#   3. The server then exposes the AI Gateway codegen + deploy tools
#      via MCP; this client provisions the matching Claude Code skills
#      (quad-codegen, quad-app-builder — already AI-Gateway-aware).
#
# Examples:
#   ./install.sh                                      # interactive prompts
#   ./install.sh --transport=stdio-local
#   ./install.sh --transport=stdio-ssh \
#       --ssh-user=alice --ssh-host=lab.example.com
#   ./install.sh --transport=sse-http \
#       --sse-url=https://mcp.example.com/sse
#   ./install.sh --transport=sse-http \
#       --sse-url=... --sse-auth-token-env=QUAD_MCP_TOKEN
#
# Coding agent launched at the end (Claude Code by default):
#   --agent claude|opencode|codex   choose the agent (overrides env + config).
#                                    Priority: --agent > QUAD_CLIENT_DEFAULT_AGENT
#                                    env > quad-client.toml default_agent > claude.
#                                    opencode/codex fall back to Claude Code if
#                                    not installed or they fail to launch.
#                                    Selecting opencode also writes opencode.json
#                                    (it reuses the same .claude/skills + CLAUDE.md).
#   --no-launch                      finish setup without starting any agent.
# ===========================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

# Python version policy (kept in sync with pyproject.toml requires-python)
MIN_PY="3.10"
RECOMMENDED_PY="3.11"
# Upper bound: onnxruntime-qnn / onnxruntime-genai NPU wheels are built only for
# 3.10–3.12. 3.13+ installs fail later with a cryptic wheel error, so gate here.
MAX_NPU_PY="3.12"

# Source colour helpers if available
log_section() { echo ""; echo "=== $1 ==="; echo ""; }
log_info()    { echo "  [INFO]  $1"; }
log_ok()      { echo "  [OK]    $1"; }
log_warn()    { echo "  [WARN]  $1"; }
log_error()   { echo "  [ERROR] $1"; }

# Upsert KEY=VALUE into an .env file: replace an existing KEY= line in place,
# otherwise append. Creates the file (chmod 600) if missing. The bearer token
# lives in PROJECT_ROOT/.env (gitignored) so the ${env:KEY} reference in
# settings.json / opencode.json resolves without the user re-exporting it by
# hand each shell.
upsert_env() {
    local file="$1" key="$2" value="$3"
    if [ ! -f "$file" ]; then
        : > "$file"
        chmod 600 "$file" 2>/dev/null || true
    fi
    if grep -q "^${key}=" "$file" 2>/dev/null; then
        # Use a tmp file so we don't depend on GNU vs BSD sed -i semantics.
        local tmp
        tmp="$(mktemp)"
        # `|| true`: when KEY is the ONLY line in the file, grep -v matches
        # nothing and returns 1, which under `set -e` aborts the whole script
        # silently. The empty $tmp is the correct intermediate state here.
        grep -v "^${key}=" "$file" > "$tmp" || true
        printf '%s=%s\n' "$key" "$value" >> "$tmp"
        cat "$tmp" > "$file"
        rm -f "$tmp"
    else
        printf '%s=%s\n' "$key" "$value" >> "$file"
    fi
}

# ── Coding-agent launcher ─────────────────────────────────────────────────
# install.sh ends by launching a CLI coding agent. Which one is chosen by, in
# priority order:  --agent <name>  >  QUAD_CLIENT_DEFAULT_AGENT env  >
# quad-client.toml default_agent  >  built-in default: claude (Claude Code).
# Allowed names: claude | opencode | codex. opencode/codex fall back to Claude
# Code when not installed or they cannot be launched. `exec` replaces the
# shell, so we probe launch-ability with command -v BEFORE exec.

quad_agent_bin() {
    case "$1" in
        claude)   echo "claude" ;;
        opencode) echo "opencode" ;;
        codex)    echo "codex" ;;
        *)        echo "" ;;
    esac
}

# Read  default_agent = "<name>"  from a TOML-style file (no parser dependency).
quad_config_agent() {
    local file="$1"
    [ -f "$file" ] || return 0
    sed -n 's/^[[:space:]]*default_agent[[:space:]]*=[[:space:]]*"\{0,1\}\([A-Za-z]\{1,\}\)"\{0,1\}.*/\1/p' \
        "$file" | head -n1
}

# Resolve desired agent: flag > env > config-file > claude. Args: flag env file.
quad_resolve_agent() {
    local flag="$1" envname="$2" file="$3" val=""
    if [ -n "$flag" ]; then
        val="$flag"
    elif [ -n "${!envname:-}" ]; then
        val="${!envname}"
    else
        val="$(quad_config_agent "$file")"
    fi
    val="$(printf '%s' "$val" | tr '[:upper:]' '[:lower:]')"
    case "$val" in
        claude|opencode|codex) echo "$val" ;;
        "")                    echo "claude" ;;
        *) log_error "Unknown agent '$val' — using claude." >&2; echo "claude" ;;
    esac
}

quad_agent_available() {
    local bin; bin="$(quad_agent_bin "$1")"
    [ -n "$bin" ] || return 1
    command -v "$bin" >/dev/null 2>&1
}

# Print an agent that is actually launchable, falling back to claude. Prints
# "" and returns 1 if nothing is available.
quad_pick_launchable() {
    local want="$1"
    if quad_agent_available "$want"; then echo "$want"; return 0; fi
    if [ "$want" != "claude" ]; then
        log_warn "Requested agent '$want' not found on PATH — falling back to Claude Code." >&2
        if quad_agent_available claude; then echo "claude"; return 0; fi
    fi
    echo ""
    return 1
}

# Returns 0 if $1 (e.g. "3.10.11") is >= $2 (e.g. "3.10"). Uses sort -V.
version_ge() {
    [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

# Returns 0 if $1's major.minor is <= $2 (e.g. "3.14.1" <= "3.12" is false).
# Compares only major.minor so patch level doesn't matter.
version_minor_le() {
    local a_mm b_mm
    a_mm="$(echo "$1" | cut -d. -f1,2)"
    b_mm="$2"
    [ "$(printf '%s\n%s\n' "$a_mm" "$b_mm" | sort -V | tail -n1)" = "$b_mm" ]
}

# Read X.Y.Z from `<python> --version`. Errors if the binary doesn't print
# something starting with "Python ".
python_version_of() {
    local py="$1"
    local out
    out=$("$py" --version 2>&1) || return 1
    case "$out" in
        Python\ *) echo "${out#Python }" ;;
        *) return 1 ;;
    esac
}

# --- Defaults / parse args ------------------------------------------------

TRANSPORT=""
SSH_USER=""
SSH_HOST=""
SSH_PORT=22
SSH_KEY=""
SSH_SERVER_CMD="python -m quad.mcp.server"
SSE_URL=""
SSE_AUTH_TOKEN_ENV=""
ADAPTER_MODE="mock"
FORCE=false
SKIP_TEST=false
PROJECT_ROOT="${PWD}"
USE_LOCAL_CHECKOUT=true
NO_LAUNCH=false        # --no-launch: finish setup without starting the coding agent
AGENT_FLAG=""          # --agent <name>: claude | opencode | codex (overrides config/env)
PRINT_AGENT=false      # --print-agent: resolve + print the launchable agent, then exit

while [[ $# -gt 0 ]]; do
    case "$1" in
        --transport)            TRANSPORT="$2"; shift 2 ;;
        --transport=*)          TRANSPORT="${1#--transport=}"; shift ;;
        --ssh-user)             SSH_USER="$2"; shift 2 ;;
        --ssh-user=*)           SSH_USER="${1#--ssh-user=}"; shift ;;
        --ssh-host)             SSH_HOST="$2"; shift 2 ;;
        --ssh-host=*)           SSH_HOST="${1#--ssh-host=}"; shift ;;
        --ssh-port)             SSH_PORT="$2"; shift 2 ;;
        --ssh-port=*)           SSH_PORT="${1#--ssh-port=}"; shift ;;
        --ssh-key)              SSH_KEY="$2"; shift 2 ;;
        --ssh-key=*)            SSH_KEY="${1#--ssh-key=}"; shift ;;
        --ssh-server-cmd)       SSH_SERVER_CMD="$2"; shift 2 ;;
        --sse-url)              SSE_URL="$2"; shift 2 ;;
        --sse-url=*)            SSE_URL="${1#--sse-url=}"; shift ;;
        --sse-auth-token-env)   SSE_AUTH_TOKEN_ENV="$2"; shift 2 ;;
        --sse-auth-token-env=*) SSE_AUTH_TOKEN_ENV="${1#--sse-auth-token-env=}"; shift ;;
        --adapter-mode)         ADAPTER_MODE="$2"; shift 2 ;;
        --force|-f)             FORCE=true; shift ;;
        --skip-test)            SKIP_TEST=true; shift ;;
        --project-root)         PROJECT_ROOT="$2"; shift 2 ;;
        --from-pypi)            USE_LOCAL_CHECKOUT=false; shift ;;
        --no-launch)            NO_LAUNCH=true; shift ;;
        --agent)                AGENT_FLAG="$2"; shift 2 ;;
        --agent=*)              AGENT_FLAG="${1#--agent=}"; shift ;;
        --print-agent)          PRINT_AGENT=true; shift ;;
        --help|-h)
            grep -E '^# ' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) log_error "Unknown argument: $1"; echo "Run with --help for usage." >&2; exit 2 ;;
    esac
done

# ── --print-agent: resolve the launchable agent and exit (debug / CI) ────────
if [ "$PRINT_AGENT" = true ]; then
    _want="$(quad_resolve_agent "$AGENT_FLAG" "QUAD_CLIENT_DEFAULT_AGENT" "$SCRIPT_DIR/quad-client.toml")"
    _pick="$(quad_pick_launchable "$_want")" || true   # may be empty; don't trip set -e
    echo "requested=${_want} launchable=${_pick:-<none>}"
    [ -n "$_pick" ]
    exit $?
fi

log_section "QUAD-Client Installer"
echo "  Project root:  ${PROJECT_ROOT}"

# --- Python check ---------------------------------------------------------

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    log_error "Python not found on PATH (tried: $PYTHON)"
    log_error "Install Python ${MIN_PY}+ first, then re-run this script."
    log_error "If you have 'uv' installed, this script can also download Python for you --"
    log_error "  install uv from https://docs.astral.sh/uv/ and re-run."
    exit 1
fi

PY_VERSION="$(python_version_of "$PYTHON")" || {
    log_error "Could not parse 'Python X.Y.Z' from '$PYTHON --version'"
    exit 1
}
if ! version_ge "$PY_VERSION" "$MIN_PY"; then
    log_error "Python ${PY_VERSION} is too old; need >= ${MIN_PY}"
    log_error "Install a newer Python and re-run, or set PYTHON=<path-to-newer-python>."
    exit 1
fi
if ! version_minor_le "$PY_VERSION" "$MAX_NPU_PY"; then
    log_error "Python ${PY_VERSION} is not supported — please use Python ${MIN_PY} to ${MAX_NPU_PY}."
    log_error "The onnxruntime-qnn NPU wheels are not built for 3.13+, so NPU support"
    log_error "would fail to install with a cryptic wheel error. Set PYTHON=<3.10-3.12>."
    exit 1
fi
log_ok "Python ${PY_VERSION}  (${MIN_PY}–${MAX_NPU_PY}, NPU-wheel compatible)"

# --- Auto-detect QUAD server venv Python (for stdio-local) ----------------
# Preference order:
#   1. QUAD_SERVER_PYTHON env var (explicit override)
#   2. Sibling QUAD repo .venv (most common layout: QUAD-Client/ next to QUAD/)
#   3. System python3 (fallback — probe will fail if quad isn't installed)

SERVER_PYTHON="${QUAD_SERVER_PYTHON:-}"
if [ -z "$SERVER_PYTHON" ]; then
    # Try Windows .exe candidates first so the on-disk filename (with
    # extension) is what gets handed downstream. Git Bash's `[ -f foo ]`
    # silently resolves to foo.exe via MSYS rewrites, but Python's
    # shutil.which (used by the probe) does NOT do that auto-extension
    # for absolute paths -- so passing the bare path through breaks the
    # probe even though the file exists.
    for candidate in \
        "${SCRIPT_DIR}/../QUAD/.venv/Scripts/python.exe" \
        "${SCRIPT_DIR}/../QUAD/.venv/Scripts/python3.exe" \
        "${SCRIPT_DIR}/../QUAD/.venv/bin/python" \
        "${SCRIPT_DIR}/../QUAD/.venv/bin/python3" \
        "${SCRIPT_DIR}/../QUAD/.venv/Scripts/python" \
        "${SCRIPT_DIR}/../QUAD/.venv/Scripts/python3"
    do
        if [ -f "$candidate" ]; then
            SERVER_PYTHON="$candidate"
            break
        fi
    done
fi
if [ -n "$SERVER_PYTHON" ]; then
    log_ok "QUAD server Python: ${SERVER_PYTHON}"
else
    SERVER_PYTHON="$PYTHON"
    log_warn "QUAD server venv not found. Set QUAD_SERVER_PYTHON=<path> or install QUAD first."
    log_warn "Expected: $(cd "${SCRIPT_DIR}/.." && pwd)/QUAD/.venv"
fi

# --- Interactive transport prompt -----------------------------------------

if [ -z "$TRANSPORT" ]; then
    echo ""
    echo "Where does the QUAD MCP server live?"
    echo "  1) stdio-local  — same machine"
    echo "  2) stdio-ssh    — remote machine, via SSH"
    echo "  3) sse-http     — remote machine, hosted HTTP/SSE service"
    echo ""
    read -r -p "Choice [1/2/3, default 1]: " choice
    case "${choice:-1}" in
        1) TRANSPORT="stdio-local" ;;
        2) TRANSPORT="stdio-ssh" ;;
        3) TRANSPORT="sse-http" ;;
        *) log_error "Invalid choice: ${choice}"; exit 2 ;;
    esac
fi
log_ok "Transport: ${TRANSPORT}"

# --- Per-transport prompts ------------------------------------------------

if [ "$TRANSPORT" = "stdio-ssh" ]; then
    [ -z "$SSH_USER" ] && read -r -p "SSH username on the server machine: " SSH_USER
    [ -z "$SSH_HOST" ] && read -r -p "SSH hostname or IP: " SSH_HOST
    if [ -z "$SSH_KEY" ]; then
        echo "  (Press Enter to use the default key from your SSH agent / ~/.ssh/id_rsa)"
        read -r -p "Path to SSH private key (optional): " SSH_KEY
    fi
elif [ "$TRANSPORT" = "sse-http" ]; then
    [ -z "$SSE_URL" ] && read -r -p "Server URL (e.g. https://mcp.example.com/sse): " SSE_URL
    if [ -z "$SSE_AUTH_TOKEN_ENV" ]; then
        # If QUAD_MCP_TOKEN is already exported in the parent shell, use it
        # without prompting -- that's the documented default token env var
        # and asking again is just friction. Warn so the user can re-export
        # if they pasted a wrong value.
        if [ -n "${QUAD_MCP_TOKEN:-}" ]; then
            SSE_AUTH_TOKEN_ENV="QUAD_MCP_TOKEN"
            log_ok "Using bearer token from \$QUAD_MCP_TOKEN (already set in this shell)"
            log_warn "Verify \$QUAD_MCP_TOKEN holds the correct token; re-export if not."
        else
            echo "  (Press Enter to skip if the server is open / no auth required)"
            read -r -p "Env var name holding the bearer token (e.g. QUAD_MCP_TOKEN): " SSE_AUTH_TOKEN_ENV
        fi
    fi
    # Persist the token to PROJECT_ROOT/.env so ${env:NAME} in the generated
    # settings.json / opencode.json resolves without the user re-exporting it
    # every shell. If the named var isn't set in this shell, prompt for the
    # value (hidden input). Skip silently when no auth var was chosen.
    if [ -n "$SSE_AUTH_TOKEN_ENV" ]; then
        TOKEN_VAL="${!SSE_AUTH_TOKEN_ENV:-}"
        if [ -z "$TOKEN_VAL" ]; then
            read -r -s -p "Paste the value for ${SSE_AUTH_TOKEN_ENV} (hidden, Enter to skip): " TOKEN_VAL
            echo ""
        fi
        if [ -n "$TOKEN_VAL" ]; then
            upsert_env "${PROJECT_ROOT}/.env" "$SSE_AUTH_TOKEN_ENV" "$TOKEN_VAL"
            # Export for this process so the connection test below can use it.
            export "${SSE_AUTH_TOKEN_ENV}=${TOKEN_VAL}"
            log_ok "Saved ${SSE_AUTH_TOKEN_ENV} to ${PROJECT_ROOT}/.env (gitignored)"
        else
            log_warn "No value for ${SSE_AUTH_TOKEN_ENV}; the connection test and"
            log_warn "live tools will fail until it is set. Export it or re-run."
        fi
    fi
fi

# --- Create / activate virtual environment --------------------------------
#
# Prefer `uv venv --python <ver>` so the client owns its Python: uv will
# download a managed CPython build of the recommended version if the local
# system doesn't already have one. Fall back to `python -m venv` (using the
# Python we already validated above) if uv isn't installed.

VENV_DIR="${SCRIPT_DIR}/.venv"
if [ ! -d "$VENV_DIR" ]; then
    if command -v uv >/dev/null 2>&1; then
        log_info "Creating virtual environment at ${VENV_DIR} (uv, python ${RECOMMENDED_PY})"
        # --seed installs pip/setuptools into the venv. Without it, uv venvs
        # ship no pip and the `python -m pip install` calls below fail with
        # "No module named pip".
        if ! uv venv --seed --python "$RECOMMENDED_PY" "$VENV_DIR" 2>/dev/null; then
            log_warn "uv venv failed for python ${RECOMMENDED_PY}; falling back to: $PYTHON -m venv"
            "$PYTHON" -m venv "$VENV_DIR"
        fi
    else
        log_info "Creating virtual environment at ${VENV_DIR}  (using $PYTHON; install 'uv' for managed Python)"
        "$PYTHON" -m venv "$VENV_DIR"
    fi
fi
# Use the venv Python for all client installs from here on
VENV_PYTHON="${VENV_DIR}/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    # Windows fallback (use .exe so shutil.which works downstream)
    VENV_PYTHON="${VENV_DIR}/Scripts/python.exe"
fi
if [ ! -f "$VENV_PYTHON" ]; then
    log_error "venv Python not found under ${VENV_DIR} -- venv creation failed?"
    exit 1
fi
VENV_PY_VERSION="$(python_version_of "$VENV_PYTHON")" || {
    log_error "venv Python at $VENV_PYTHON did not return a version"
    exit 1
}
if ! version_ge "$VENV_PY_VERSION" "$MIN_PY"; then
    log_error "venv has Python ${VENV_PY_VERSION}; need >= ${MIN_PY}. Delete .venv and re-run."
    exit 1
fi
log_ok "Using venv Python: ${VENV_PYTHON}  (${VENV_PY_VERSION})"

# --- Install lightweight client deps --------------------------------------

log_section "Installing quad-mcp-client"

# Ensure pip exists in the venv. uv venvs created without --seed (e.g. by an
# earlier run of this script) have no pip, which breaks every install below.
# ensurepip is shipped inside the venv's stdlib, so this repairs them in place
# without requiring the venv be deleted and recreated.
if ! "$VENV_PYTHON" -m pip --version >/dev/null 2>&1; then
    log_info "pip missing from venv — bootstrapping with ensurepip"
    if "$VENV_PYTHON" -m ensurepip --upgrade >/dev/null 2>&1; then
        log_ok "pip bootstrapped into venv"
    elif command -v uv >/dev/null 2>&1; then
        log_warn "ensurepip unavailable; seeding pip with: uv pip install --python <venv> pip"
        uv pip install --python "$VENV_PYTHON" pip >/dev/null 2>&1 \
            || log_error "Could not install pip into ${VENV_DIR}. Delete it and re-run."
    else
        log_error "Could not install pip into ${VENV_DIR}. Delete it and re-run."
    fi
fi

# pip_install — install into the venv while trusting the OS certificate store.
#
# On a corporate network (e.g. Qualcomm) an intercepting TLS proxy presents a
# self-signed root CA that IT has installed into the OS trust store. Plain pip
# trusts only its bundled certifi bundle, NOT the OS store, so it dies with
# "CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain" —
# typically while building a sdist dep like cryptography under build isolation.
#
# We avoid hardcoding any CA path by deferring to the OS trust store, exactly
# as the sample run.ps1 scripts do, in priority order:
#   1. uv pip install --system-certs   (uv reads the OS/native trust store)
#   2. pip --use-feature=truststore    (pip >= 24.2 reads the OS store)
#   3. plain pip                       (works off-proxy; clear hint on failure)
# All args (e.g. --quiet, -e DIR, package specs) are forwarded verbatim.
pip_install() {
    if command -v uv >/dev/null 2>&1; then
        uv pip install --system-certs --python "$VENV_PYTHON" "$@" && return 0
    fi
    "$VENV_PYTHON" -m pip install --use-feature=truststore "$@" 2>/dev/null && return 0
    # Final attempt with plain pip — succeeds when not behind an intercepting proxy.
    "$VENV_PYTHON" -m pip install "$@"
}

# Hint shown whenever a pip_install fails — covers the corporate-proxy CA case.
cert_hint() {
    log_warn "If this is an SSL CERTIFICATE_VERIFY_FAILED behind a corporate proxy:"
    log_warn "  • quickest:  uv pip install --system-certs --python \"$VENV_PYTHON\" <pkgs>"
    log_warn "  • or point pip at your org root CA bundle (durable):"
    log_warn "      setx SSL_CERT_FILE      C:\\path\\to\\org-root-ca.pem"
    log_warn "      setx REQUESTS_CA_BUNDLE C:\\path\\to\\org-root-ca.pem"
    log_warn "      \"$VENV_PYTHON\" -m pip config set global.cert C:\\path\\to\\org-root-ca.pem"
}

"$VENV_PYTHON" -m pip install --quiet --upgrade pip 2>/dev/null || true

if [ "$USE_LOCAL_CHECKOUT" = true ] && [ -f "${SCRIPT_DIR}/pyproject.toml" ]; then
    log_info "Installing quad-mcp-client from local checkout (editable mode)"
    pip_install --quiet -e "${SCRIPT_DIR}"
    log_ok "Installed from local checkout"
else
    log_info "Installing quad-mcp-client from PyPI"
    pip_install --quiet "quad-mcp-client"
    log_ok "Installed from PyPI"
fi

# Guard against the onnxruntime / onnxruntime-qnn file-overwrite conflict
# (both write onnxruntime/capi/onnxruntime.dll to the same place; the last
# install silently clobbers the other and NPU support breaks with no error).
# pip cannot detect this, so check explicitly before layering sample deps.
if "$VENV_PYTHON" -c "import importlib.metadata as m; names={ (d.metadata['Name'] or '').lower() for d in m.distributions() }; raise SystemExit(0 if {'onnxruntime','onnxruntime-qnn'} <= names else 1)" 2>/dev/null; then
    log_warn "Both onnxruntime and onnxruntime-qnn are installed in this venv — they"
    log_warn "overwrite each other's onnxruntime.dll and NPU support breaks silently."
    log_warn "Fix: $VENV_PYTHON -m pip uninstall onnxruntime   (keep only onnxruntime-qnn)"
    log_warn "Reminder: NPU wheels belong in the native-ARM64 .venv-arm64, not this tooling venv."
fi

# Install sample-script dependencies (fastmcp, numpy, Pillow, onnxruntime, …).
# These are declared in pyproject.toml [project.optional-dependencies.samples]
# and are needed to run anything under samples/.
log_info "Installing sample dependencies (fastmcp, numpy, Pillow, onnxruntime, scipy, tqdm)..."
SAMPLE_PKGS=(fastmcp numpy "Pillow>=10.0" "onnxruntime>=1.18" "scipy>=1.10" tqdm)
if [ "$USE_LOCAL_CHECKOUT" = true ] && [ -f "${SCRIPT_DIR}/pyproject.toml" ]; then
    # Try the [samples] extra first. pip's editable+extras needs a native
    # Windows path on Git Bash/MSYS ("C:\path[extras]"); uv accepts the bash
    # path directly. Convert with cygpath for the pip fallback path inside
    # pip_install, then fall back to the explicit package list either way.
    _win_dir="$(cygpath -w "${SCRIPT_DIR}" 2>/dev/null || echo "${SCRIPT_DIR}")"
    if pip_install --quiet -e "${_win_dir}[samples]" 2>/dev/null; then
        log_ok "Sample deps installed"
    elif pip_install --quiet "${SAMPLE_PKGS[@]}"; then
        log_ok "Sample deps installed"
    else
        log_warn "Some sample deps failed -- run: uv pip install --system-certs --python \"$VENV_PYTHON\" ${SAMPLE_PKGS[*]}"
        cert_hint
    fi
else
    if pip_install --quiet "${SAMPLE_PKGS[@]}"; then
        log_ok "Sample deps installed"
    else
        log_warn "Some sample deps failed -- run: uv pip install --system-certs --python \"$VENV_PYTHON\" ${SAMPLE_PKGS[*]}"
        cert_hint
    fi
fi

# Verify quad-client is importable
if ! "$VENV_PYTHON" -c "from quad_mcp_client.cli import cli" >/dev/null 2>&1; then
    log_error "quad_mcp_client.cli not importable after install — something went wrong."
    log_error "Manual recovery: $VENV_PYTHON -m pip install -e ."
    exit 1
fi
log_ok "quad-client CLI ready"

# Sync any system-level quad-client installation that predates the new commands.
# When the user's PATH includes another Python's Scripts dir (e.g. system
# Python 3.10) before the venv, Claude Code's Bash tool uses that version.
# We keep it in sync so `quad-client detect` always works without activation.
_sys_qc=""
for _candidate in "$(command -v quad-client 2>/dev/null)" "$(command -v quad-client.exe 2>/dev/null)"; do
    if [ -n "$_candidate" ] && [ "$_candidate" != "$VENV_DIR/Scripts/quad-client" ] \
            && [ "$_candidate" != "$VENV_DIR/Scripts/quad-client.exe" ] \
            && [ "$_candidate" != "$VENV_DIR/bin/quad-client" ]; then
        _sys_qc="$_candidate"
        break
    fi
done
if [ -n "$_sys_qc" ]; then
    _sys_scripts="$(dirname "$_sys_qc")"
    for _sys_py in "$_sys_scripts/python.exe" "$_sys_scripts/python" "$_sys_scripts/python3"; do
        if [ -f "$_sys_py" ] && [ "$_sys_py" != "$VENV_PYTHON" ]; then
            _win_scripts="$(cygpath -w "${SCRIPT_DIR}" 2>/dev/null || echo "${SCRIPT_DIR}")"
            log_info "Syncing quad-mcp-client to $(basename "$_sys_py") at $(dirname "$_sys_py") ..."
            "$_sys_py" -m pip install --quiet -e "${_win_scripts}" 2>/dev/null \
                && log_ok "System quad-client synced (detect/doctor/unoq now available globally)" \
                || true
            break
        fi
    done
fi

# Export PYTHON to point at the venv for subsequent steps
PYTHON="$VENV_PYTHON"

# --- Build the connect-test arg list --------------------------------------

CT_ARGS=("$TRANSPORT")
if [ "$TRANSPORT" = "stdio-local" ]; then
    CT_ARGS+=(--server-command "$SERVER_PYTHON")
elif [ "$TRANSPORT" = "stdio-ssh" ]; then
    CT_ARGS+=(--ssh-user "$SSH_USER" --ssh-host "$SSH_HOST" --ssh-port "$SSH_PORT")
    [ -n "$SSH_KEY" ] && CT_ARGS+=(--ssh-key "$SSH_KEY")
    CT_ARGS+=(--server "$SSH_SERVER_CMD")
elif [ "$TRANSPORT" = "sse-http" ]; then
    CT_ARGS+=(--sse-url "$SSE_URL")
    if [ -n "$SSE_AUTH_TOKEN_ENV" ]; then
        TOKEN_VAL="${!SSE_AUTH_TOKEN_ENV:-}"
        if [ -n "$TOKEN_VAL" ]; then
            CT_ARGS+=(--auth-token "$TOKEN_VAL")
        fi
    fi
fi

# --- Connection test ------------------------------------------------------

if [ "$SKIP_TEST" = false ]; then
    log_section "Testing connection"
    log_info "Probing ${TRANSPORT}..."
    set +e
    "$PYTHON" -m quad_mcp_client.cli connect-test "${CT_ARGS[@]}"
    PROBE_RC=$?
    set -e
    if [ $PROBE_RC -ne 0 ]; then
        log_warn "Connection test failed (exit ${PROBE_RC})."
        if [ "$FORCE" = false ]; then
            echo ""
            echo "Re-run with --force to provision anyway, or fix the issue and retry."
            echo ""
            if [ "$TRANSPORT" = "stdio-local" ]; then
                echo "Hint: the QUAD MCP server (https://github.qualcomm.com/pavanr/QUAD) needs"
                echo "      to be installed on this machine for stdio-local to work."
            fi
            exit 1
        fi
        log_warn "--force given; provisioning anyway."
    else
        log_ok "Connection test passed"
    fi
fi

# --- Provision Claude Code ------------------------------------------------

log_section "Provisioning Claude Code"
INSTALL_ARGS=(--transport "$TRANSPORT" --skip-test --project-root "$PROJECT_ROOT")
[ "$FORCE" = true ] && INSTALL_ARGS+=(--force)

case "$TRANSPORT" in
    stdio-local)
        INSTALL_ARGS+=(--adapter-mode "$ADAPTER_MODE")
        INSTALL_ARGS+=(--server-command "$SERVER_PYTHON")
        ;;
    stdio-ssh)
        INSTALL_ARGS+=(--ssh-user "$SSH_USER" --ssh-host "$SSH_HOST" --ssh-port "$SSH_PORT")
        [ -n "$SSH_KEY" ] && INSTALL_ARGS+=(--ssh-key "$SSH_KEY")
        INSTALL_ARGS+=(--ssh-server-command "$SSH_SERVER_CMD")
        ;;
    sse-http)
        INSTALL_ARGS+=(--sse-url "$SSE_URL")
        [ -n "$SSE_AUTH_TOKEN_ENV" ] && INSTALL_ARGS+=(--sse-auth-token-env "$SSE_AUTH_TOKEN_ENV")
        ;;
esac

"$PYTHON" -m quad_mcp_client.cli install "${INSTALL_ARGS[@]}"

# --- Provision opencode (when selected) -----------------------------------
# Claude Code is always provisioned above (it's the universal fallback). If
# the user picked opencode, also write opencode.json. opencode reuses the
# same .claude/skills + CLAUDE.md, so nothing else is duplicated.
_prov_agent="$(quad_resolve_agent "$AGENT_FLAG" "QUAD_CLIENT_DEFAULT_AGENT" "$SCRIPT_DIR/quad-client.toml")"
if [ "$_prov_agent" = "opencode" ]; then
    log_section "Provisioning opencode"
    "$PYTHON" -m quad_mcp_client.cli install --client opencode "${INSTALL_ARGS[@]}"
fi

# --- Summary --------------------------------------------------------------

log_section "Done"
echo "  Transport:      ${TRANSPORT}"
echo "  Project root:   ${PROJECT_ROOT}"
echo "  Settings file:  ${PROJECT_ROOT}/.claude/settings.json"
echo "  Skills dir:     ${PROJECT_ROOT}/.claude/skills"
if [ "$_prov_agent" = "opencode" ]; then
    echo "  opencode config:${PROJECT_ROOT}/opencode.json (reuses .claude/skills + CLAUDE.md)"
fi
if [ "$TRANSPORT" = "sse-http" ] && [ -n "$SSE_AUTH_TOKEN_ENV" ] && [ -f "${PROJECT_ROOT}/.env" ] && grep -q "^${SSE_AUTH_TOKEN_ENV}=" "${PROJECT_ROOT}/.env" 2>/dev/null; then
    echo "  Token:          ${SSE_AUTH_TOKEN_ENV} saved to ${PROJECT_ROOT}/.env (gitignored)"
fi
echo ""
echo "  Verify:         quad-client status --project-root '${PROJECT_ROOT}'"
echo "  Re-test conn:   quad-client connect-test ${TRANSPORT} ${CT_ARGS[*]:1}"
echo ""
echo "  Open Claude Code in this project — the QUAD MCP tools will appear in the tool list."
echo "  Try: \"What hardware do I have?\" or \"Convert mobilenetv2.onnx to INT8\""
echo ""

cd "${PROJECT_ROOT}"
# Claude Code on Windows needs CLAUDE_CODE_GIT_BASH_PATH to locate bash.exe.
# We're already running inside Git Bash, so `which bash` gives the exact path.
if [ -z "${CLAUDE_CODE_GIT_BASH_PATH:-}" ]; then
    _bash_path="$(which bash 2>/dev/null || true)"
    if [ -n "$_bash_path" ]; then
        # Convert to Windows path (e.g. /c/Program Files/Git/bin/bash.exe →
        # C:\Program Files\Git\bin\bash.exe) so the Claude Code Node process
        # can use it directly.
        export CLAUDE_CODE_GIT_BASH_PATH="$(cygpath -w "$_bash_path" 2>/dev/null || echo "$_bash_path")"
    fi
fi

# Choose + launch the coding agent. Resolution: --agent > env > config > claude;
# opencode/codex fall back to Claude Code if not launchable.
_want_agent="$(quad_resolve_agent "$AGENT_FLAG" "QUAD_CLIENT_DEFAULT_AGENT" "$SCRIPT_DIR/quad-client.toml")"
_agent="$(quad_pick_launchable "$_want_agent")" || true   # may be empty; don't trip set -e

if [ "$NO_LAUNCH" = true ]; then
    echo "  Setup complete. Open your coding agent in this project to use the QUAD MCP tools."
elif [ ! -t 0 ]; then
    echo "  Setup complete (non-interactive). Open a coding agent here to use the QUAD MCP tools."
elif [ -z "$_agent" ]; then
    echo "  No coding agent (claude/opencode/codex) found on PATH."
    echo "  Install Claude Code from https://claude.com/claude-code, then open it in this project."
else
    case "$_agent" in
        claude)
            echo "  Launching Claude Code…"
            exec claude --dangerously-skip-permissions ;;
        codex)
            echo "  Launching codex…"
            exec codex ;;
        opencode)
            echo "  Launching opencode…"
            exec opencode ;;
    esac
    # exec only returns if the binary vanished between probe and launch.
    log_warn "Could not launch ${_agent}. Open a coding agent in this project manually."
fi
