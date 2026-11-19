# QUAD-Client Install — Issue Report

**Date:** 2026-07-21 · **Refined:** 2026-08-03 · **Updated:** 2026-08-05 (IQ8 + IQ-9075 both reflashed to QLI 2.0 → Issue 24 **FULLY RESOLVED** fleet-wide; Issue 23 accuracy sub-note RESOLVED; new Issue 38 logged — tar drops exec bit)
**Reporter:** sreddygu
**Host:** Windows 11 Enterprise (ARM64 / Snapdragon X Elite, Prism x86 emulation active)
**Project:** `C:\Dropbox\DevRel\Academy\qa-intermediate-curriculum\projects\QUAD-Client`
**Baseline code:** `origin/main @ 3cfd3da` (CBN-AI-TEAM/QUAD-Client)

---

## Scope of this report

This report tracks **only issues empirically confirmed live against the current
code/hardware.** Purely informational entries, environment/network non-bugs,
doc-only gaps, feature-request enhancements, and the git force-sync/recovery
process narrative have been **removed** in this refinement. Issue numbers are
left unchanged for traceability, so the sequence has gaps (removed: 3, 4, 5, 6,
7, 8, 10, 11, 13, 17, 18, 26, 27).

Every issue below was **executed live** on the X-Elite host (emulated-x86
Python 3.10 `.venv`, and a native ARM64 venv where noted), on the IQ8
(`10.92.210.214`) and IQ-9075 (`192.168.29.185`) boards over SSH, with the MCP
server (`http://10.227.21.202:8000/mcp`, **QUAD 3.4.2**) reachable and the
`QUAD_MCP_TOKEN` loaded from `.env`.

> **Why the code fixes are "valid again":** Issues 1, 2, 14, 15, 16, 20, 21 were
> fixed locally on 07-21/07-22, but those fixes lived **only in the local working
> tree and were never pushed**. A `git reset --hard origin/main` reverted them
> all. Until they land on `origin/main` via a PR to CBN-AI-TEAM, any sync/reset
> re-loses them. Full set preserved in
> `../QUAD-Client-local-changes-2026-07-27.patch` (`git apply --3way`; 4 files —
> `quad.toml` + 3 `quad-detect` copies — need manual conflict resolution).

---

## Issue tracker (valid/live-confirmed only)

Status legend: 🔧 open (code fix needed) · 🖥️ server/hardware-side.

| # | Severity | Area | Title | Verdict |
|---|---|---|---|---|
| 1  | High | install.sh | `uv --system-certs` invalid flag → `--native-tls` | ✅ VALID (live 07-27: uv rejects flag; in 11 files) |
| 2  | High | TLS/proxy | Netskope `CERTIFICATE_VERIFY_FAILED` on install | ✅ VALID (follows #1; pip fallback hits Netskope TLS) |
| 9  | Med | doctor.py | model-access check misses `ANTHROPIC_BASE_URL` | ✅ VALID (live: `doctor` passes on token alone) |
| 12 | High | cross-platform | `install.sh` CRLF → fails on Linux devices | ✅ VALID (live: 711 CRLF; no `.gitattributes`) |
| 14 | High | sample | remote convert sends no auth token → 401 | ✅ VALID (live 07-27: server 401 no-token) |
| 15 | High | sample | local model path sent to remote server → "Model not found" | ✅ VALID (no upload path in code) |
| 16 | Med | detect | IQ8 not detected (no `iq-8275` stanza in `quad.toml`) | ✅ VALID (live 07-27) |
| 19 | Med | registry | QCS8275 absent from capability table → NPU TOPS unresolved | ✅ VALID (live probe → None) |
| 20 | Med | detect | skill's `import tomllib` fails on Python 3.10 | ✅ VALID (live 07-27: ModuleNotFoundError) |
| 21 | Med | sample | STEP 3 crashes (not skips) when `quad_mcp_client`/SDK missing | ✅ VALID (live 07-27: ImportError escapes handler) |
| 22 | Med | sample | remote-converted artifact benchmarked against local SDK (split not surfaced) | ✅ VALID (observed live; partial) |
| 23 | High | runtime | qnn-net-run NPU crash exit 0xC0000409 | ✅ VALID (live; crashes on x86 **and** native arm64) |
| 24 | High | compat | server QAIRT 2.47 > IQ runtime 2.43 → binary won't load (IQ8+IQ9) | ✅ **RESOLVED fleet-wide** — both IQ8 (v75) & IQ-9075 (v73) reflashed to QLI 2.0; push-2.47-runtime + float DLC → NPU works on both 2026-08-05 |
| 25 | Med | aihub | AI Hub `force` compile rejects sample's single-.onnx upload | ✅ VALID (live: "Incorrect archived model") |
| 28 | High | detect/CLI | `detect` without `--platform` never queries server (silent local fallback) | ✅ VALID (live 07-30) |
| 29 | Med | SDK | `search_aihub()` sends `limit`/`offset` the server rejects → README example crashes | ✅ VALID (live 07-30) |
| 30 | Low | tests | `test_search_aihub_paginates` mocks a pagination contract the live server doesn't implement | ✅ VALID (live 07-30) |
| 31 | Med | skills | `quad-app-builder` points to `samples/mobilenetv2_iq9075/` (×5) — real dir is `mobilenetv2_npu_iq9075` | ✅ VALID (live 07-30) |
| 32 | Med | skills | `quad-app-builder` references 2 export_assets docs + 3 GWAPPS docs that don't exist | ✅ VALID (live 07-30) |
| 33 | Low | skills | `quad-detect`/`quad-build-npu-bundle`/`quad-deploy` cite 4 docs (incl. missing `docs/debugging/`) not in repo | ✅ VALID (live 07-30) |
| 34 | High | profile-device | client-agent workspace hardcoded to Android `/data/local/tmp/quad` → push fails on SSH/Linux boards (IQ9) | ✅ VALID (live IQ9) |
| 35 | High | sample | `mobilenetv2_npu_iq9075` orchestrator hardcodes `/data/local/tmp/quad` → SSH run fails `mkdir /data: Permission denied` | ✅ VALID (live IQ9) |
| 36 | Med | sample | `mobilenetv2_npu_iq9075` README lists `mobilenetv2.onnx` + `imagenet_classes.txt` as shipped; both absent, no auto-download | ✅ VALID (live 07-30) |
| 37 | Low | unoq/UX | `unoq configure` against an IQ9 host emits a wrong `arduino-unoq/qcs2210/v66` stanza unless `--board iq9075` passed | ✅ VALID (live 07-30) |
| 38 | Low | ops | pushed `.tgz` runtime bundle extracts without exec bit → `qnn-net-run: Permission denied`; fix `chmod +x /opt/qnn/bin/*` | ✅ VALID (live IQ9 08-05) |

---

## Live test evidence (commands actually run)

| # | Test run | Observed output | Verdict |
|---|---|---|---|
| 1  | `uv pip install --system-certs …` | `error: unexpected argument '--system-certs' found` | ✅ VALID |
| 1  | flag present in tree | 11 files still carry `--system-certs`; `--native-tls` = 0 | ✅ VALID |
| 2  | (follows #1) | uv branch errors → plain-pip fallback hits Netskope TLS | ✅ VALID |
| 9  | `quad-client doctor` | "Model access token [OK]" passes on token alone; **no** base-URL check | ✅ VALID (live) |
| 9  | `grep ANTHROPIC_BASE_URL doctor.py` | count 0 | ✅ VALID |
| 12 | `.gitattributes` + `install.sh` bytes | file MISSING; `install.sh` has **711 CRLF** | ✅ VALID |
| 14 | `POST /mcp` with no bearer | `HTTPError 401` (server requires auth; code sends none) | ✅ VALID (live) |
| 15 | code path of `_call_convert_remote` | no `upload`/`model_source` — local Win path → remote | ✅ VALID |
| 16 | `quad.toml` target scan | only `iq-9075`; no `iq-8275` stanza | ✅ VALID |
| 19 | `lookup_for_chipset("QCS8275")` | returns `None` (SoC absent from `capabilities.py`) | ✅ VALID (live) |
| 20 | `python -c "import tomllib, sys, json, os, re"` | `ModuleNotFoundError: No module named 'tomllib'` (3.10.10) | ✅ VALID |
| 21 | simulate STEP 3 handler w/ `ImportError` | escapes `(RuntimeError, FileNotFoundError)` → crash | ✅ VALID (live) |
| 23 | host `qnn-net-run` (x86 venv, then native arm64) | exit `0xC0000409` in both | ✅ VALID (live) |
| 24 | server-`.bin` on IQ8 & IQ9 `qnn-net-run` | `err 5000 / 0x1388`, exit 16 on both | ✅ VALID (live) |
| 25 | `convert_model aihub=force` single-.onnx upload | `Incorrect archived model` | ✅ VALID (live) |
| 28 | `detect --json` vs `detect --platform windows --json` | `client-local-static` vs `server` | ✅ VALID (live) |
| 29 | `search_aihub("mobilenet", …)` | `ToolError: limit/offset Unexpected keyword argument` | ✅ VALID (live) |
| 34 | `profile-device --transport ssh` (IQ9) | `scp dest open /data/local/tmp/quad/…: No such file` | ✅ VALID (live) |
| 35 | `run_iq9075.py --transport ssh` (IQ9) | `mkdir: cannot create directory '/data': Permission denied` | ✅ VALID (live) |

`quad-client doctor` overall on latest code: **5 passed / 9 warnings / 0 errors**
(exit 0) — client is functional; warnings are the env/NPU items (Issue 9 plus
onnxruntime-qnn/psutil/SDK-env), not client-startup regressions.

**Grouping:**
- **Code bugs (fix in client):** 1, 2, 9, 12, 14, 15, 16, 20, 21, 22, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37
- **Server-side / hardware:** 19, 23, 24, 25

---

## Issue 1 — `uv pip install --system-certs` is an invalid flag (BUG)

**Severity:** High — a real code bug, not an environment problem.

The `pip_install()` helper in `install.sh` (lines ~463–470) runs:

```bash
uv pip install --system-certs --python "$VENV_PYTHON" "$@"
```

`uv` does **not** have a `--system-certs` option. uv rejects it immediately:

```
error: unexpected argument '--system-certs' found
  tip: a similar argument exists: '--system'
Usage: uv.exe pip install --system <PACKAGE|...>
```

The comments in the script (lines 449–462) claim `--system-certs` makes uv read
the OS/native trust store. The **correct uv flag is `--native-tls`** (uv reads the
platform native certificate store). `--system-certs` appears nowhere in uv's CLI.

**Effect:** the uv branch always errors out, so `pip_install()` silently falls
through to plain pip (`--use-feature=truststore`, then bare pip), losing the
intended corporate-proxy TLS handling. On this machine that fall-through then hit
Issue 2.

**Locations to fix** (all reference the wrong flag):
- `install.sh:465` — the actual command
- `install.sh:475` — `cert_hint()` "quickest" advice
- `install.sh:521` — sample-deps failure hint
- `install.sh:528` — sample-deps failure hint

The same invalid flag was **also** found baked into the canonical `run.ps1`
template and propagated to every sample — a wider blast radius than install.sh:
- `.claude/skills/quad-run-ps1/SKILL.md:86` (canonical template)
- `.claude/skills/quad-run-ps1.md:86`
- `src/quad_mcp_client/claude_code/skills_content/quad-run-ps1.md:86`
- `samples/mobilenetv2/run.ps1:75`
- `samples/mobilenetv2_npu_iq9075/run.ps1:75`
- `samples/executorch_mobilenet/run.ps1:72`
- `samples/gpu_inference/run.ps1:63`
- `samples/npu_ort/run.ps1:70`
- `samples/whisper_asr/run.ps1:63`
- `samples/stc_classifier/run.ps1:23` and `:30`

**Suggested fix:** replace `--system-certs` with `--native-tls` in all places, e.g.

```bash
uv pip install --native-tls --python "$VENV_PYTHON" "$@" && return 0
```

**STATUS: VALID on `@3cfd3da`.** Confirmed live 07-27: `uv pip install
--system-certs` → `error: unexpected argument '--system-certs' found`; the flag is
still present in **11 files**, with **0** `--native-tls`. Fix preserved in the
backup patch; needs re-apply + push.

---

## Issue 2 — TLS `CERTIFICATE_VERIFY_FAILED` behind corporate proxy (Netskope)

**Severity:** High — blocks the install on the corporate network.

After the uv branch failed (Issue 1), plain pip tried to fetch build deps from
PyPI and failed the TLS handshake:

```
SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED]
certificate verify failed: self signed certificate in certificate chain (_ssl.c:997)'))
...
ERROR: Could not find a version that satisfies the requirement hatchling>=1.21 (from versions: none)
ERROR: No matching distribution found for hatchling>=1.21
× pip subprocess to install build dependencies did not run successfully.
```

This is the known Qualcomm/Netskope intercepting-proxy behavior: the proxy
presents a self-signed root CA that lives in the OS trust store, but pip's
bundled certifi bundle doesn't include it, so sdist/build-isolation downloads
fail.

**Note:** `pip --use-feature=truststore` (the intended fallback #2) either was not
reached in a working state or did not pick up the OS store here; the failure
surfaced as plain-pip PyPI fetches.

**Workaround (durable):** point pip/requests at the Netskope CA PEM bundle before
installing:

```bash
export SSL_CERT_FILE=/path/to/netskope-ca.pem
export REQUESTS_CA_BUNDLE=/path/to/netskope-ca.pem
export QUAD_CA_BUNDLE=/path/to/netskope-ca.pem
```

(Or persist with `setx`.) Then re-run the editable install:

```bash
.venv/Scripts/python.exe -m pip install -e . --cert /path/to/netskope-ca.pem
```

Once Issue 1 is fixed, `uv pip install --native-tls ...` should also read the
OS store and succeed without a hardcoded PEM path.

---

## Issue 9 — `quad-client doctor` model-access check is incomplete (CODE)

**Severity:** Medium.

`src/quad_mcp_client/local/doctor.py` (~lines 325–337) passes its "Model access
token" check when **any** of `QGENIE_API_KEY` / `ANTHROPIC_API_KEY` /
`ANTHROPIC_AUTH_TOKEN` is set. But a token alone does not make Claude Code work
— `ANTHROPIC_BASE_URL` must also be set to the QGenie gateway. So `doctor` can
report model access as OK while Claude Code is still stuck at `/login`.
Confirmed live: `doctor` reports "Model access token [OK]" on token-only, and
`grep ANTHROPIC_BASE_URL doctor.py` → count 0.

**Fix:** add an `ANTHROPIC_BASE_URL` presence/shape check to `doctor`, and warn
when a token is set but the base URL is missing (or vice-versa) — that
combination is the actual failure mode.

---

## Issue 12 — `install.sh` has CRLF line endings → fails on Linux (BUG)

**Severity:** High for any Windows→Linux copy (which is exactly the IQ8/IQ9
device workflow).

`install.sh` is checked out with **CRLF line terminators** (711 CR bytes;
`file` reports "with CRLF line terminators"). Under Linux `bash` the very first
executable line fails:

```
install.sh: line 57: set: pipefail: invalid option name
```

because `set -euo pipefail\r` makes `pipefail\r` an invalid option, and every
subsequent line carries a trailing `\r`. The script dies immediately. This hits
**anyone** who copies the repo from a Windows/Dropbox checkout to a Linux device
— the primary IQ8/IQ9 bring-up path.

**Workaround used:** `sed -i 's/\r$//' install.sh` on the device, then re-ran.

**Fix (durable):** add a `.gitattributes` enforcing LF for shell scripts, e.g.

```
*.sh   text eol=lf
*.ps1  text eol=crlf
```

so `*.sh` always lands with LF regardless of checkout platform. (Also consider
`build_falcon_npu_bundle.sh` and any other `*.sh`.) Confirmed live: `.gitattributes`
is MISSING and `install.sh` still has 711 CRLF on `@3cfd3da`.

---

## Issue 14 — sample's remote convert sends no auth token → 401 (BUG)

**Severity:** High — blocks the flagship sample on any auth'd `sse-http` server.

`_call_convert_remote()` in `samples/mobilenetv2/run_mobilenetv2.py` (~line 595)
opens `Client(url)` with **no auth**, but the QUAD server requires a bearer token.
Result:

```
httpx.HTTPStatusError: Client error '401 Unauthorized' for url
'http://10.227.21.202:8000/mcp'
```

The code comment asserts the token is "picked up from the environment by the
settings.json ${env:...} reference at provisioning time." That's only true
**inside the agent** (Claude Code expands `${env:QUAD_MCP_TOKEN}` when it reads
`settings.json`). This standalone script never expands it, and never loads the
repo `.env`, so no `Authorization` header is sent.

**STATUS: VALID on `@3cfd3da`.** Confirmed live 07-27: a tokenless `POST /mcp`
returns **HTTP 401**, and upstream `_call_convert_remote()` still does
`async with Client(url)` with no `auth=`. The fix (env `QUAD_MCP_TOKEN` → repo
`.env` fallback, passed as `Client(url, auth=token)`; fastmcp accepts a bearer
string) is preserved in the backup patch and needs re-apply + push.

**Wider blast radius (not yet fixed):** audit the same tokenless `Client(url)`
pattern in the other samples' remote paths and anywhere else the repo constructs
a fastmcp `Client` from a URL outside the agent. The typed `QuadClient` SDK
(`src/quad_mcp_client/client.py`) already handles auth correctly — samples should
prefer it over hand-rolled fastmcp calls.

---

## Issue 15 — sample sends a LOCAL model path to a REMOTE server → "Model not found" (BUG)

**Severity:** High — after Issue 14, this is the next wall; the sample cannot
complete against a remote server as written.

With auth fixed, `convert_model` failed:

```
fastmcp.exceptions.ToolError: Error calling tool 'convert_model':
Model not found: C:\...\samples\mobilenetv2\mobilenetv2.onnx
```

`step2_convert()` builds `tool_args["model_path"] = str(model_path.resolve())`
— an **absolute client-side Windows path** — and sends it verbatim to a server
running on a **different host** (`10.227.21.202`), which has no such file. The
sample's remote path implicitly assumes the server shares the client's
filesystem (i.e. a local/stdio server), so it breaks for the exact `sse-http`
topology the README's Step 4 tells users to run.

**Root cause / correct mechanism already exists:** the `QuadClient.convert_model`
SDK method supports `upload=<local file>` (POST the file to the server, convert
the uploaded copy) and `model_source={"kind": "upload"|"huggingface"|"url"|...}`
— see `client.py:385-431` and `skills_content/quad-convert.md:68`. The sample's
hand-rolled `_call_convert_remote()` uses none of this.

**Suggested fix:** rework the sample's remote branch to either (a) call the
`QuadClient` SDK with `upload=model_path` instead of hand-rolling a fastmcp
`Client`, or (b) POST the file via `upload_file()` and pass
`model_source={"kind":"upload", "upload_id":...}`. Option (a) is cleanest and
reuses the tested auth + upload + artifact-download logic.

**STATUS: VALID on `@3cfd3da`.** Confirmed 07-27 that upstream
`run_mobilenetv2.py` has none of the upload/download helpers — it still sends the
local Windows `model_path` to the remote server. Fix preserved in the backup
patch; needs re-apply + push. (When live it verified end-to-end against
`10.227.21.202`: upload → convert 100% ops → download → CPU benchmark; NPU
execution then blocked by Issues 22–23.)

---

## Issue 16 — IQ8 not detected: no `[target.iq-8275]` stanza in `quad.toml` (BUG)

**Severity:** Medium — every IQ8 detect over SSH fails until the stanza is added.

Root cause of "IQ8 connected but not detected" is that QUAD only enumerates local
host + adb-USB + `quad.toml` `[target.*]` SSH targets, and upstream `quad.toml`
has only `iq-9075` — no `iq-8275`. Verified live 07-27: the `quad.toml` target
scan shows only `iq-9075`.

It was fixed locally by adding a stanza (reverted by the force-reset):

- `quad.toml`: `[target.iq-8275]` (`soc=qcs8275`, `hexagon=v75`) + `[target.iq-8275.ssh]`
  referencing `${env:IQ8_HOST}` / `${env:IQ8_SSH_USER}` / `${env:IQ8_SSH_KEY}`.
- `.env_boards`: `IQ8_HOST=10.92.210.214`, `IQ8_SSH_USER=ubuntu`,
  `IQ8_SSH_KEY=…\iq8_nopass` (key-auth; verified `BatchMode=yes` works).

**Additional UX note:** Qualcomm Linux boards (IQ8/IQ9) do **not** enumerate over
adb (`adb devices` returns empty even when cabled). The `quad-detect` skill should
steer the user toward the SSH/serial path after an empty `adb devices` rather than
implying no device is present.

Fix preserved in the backup patch; needs re-apply + push.

---

## Issue 19 — QCS8275 (IQ8) absent from capability registry → NPU TOPS unresolved (BUG — server-side)

**Severity:** Medium — every IQ8 detect returns "unresolved" NPU specs.

`/quad-detect` probed the IQ8 correctly (soc0/machine = **QCS8275**,
soc_id 675, authoritative) but `lookup_for_chipset("QCS8275")` returns
**None** — the SoC is not in `src/quad_mcp_client/local/capabilities.py`
(`_CAPABILITIES` / `_ALIASES`). The agent correctly **declined to fabricate**
a TOPS number and reported probed facts only. Contrast: QCS9075 and X1E78100
resolve fine.

**Corroborated facts to register** (from live probe, not guessed):
- Chipset: `QCS8275`; SoC id 675; board "IQ8 8275 Pro SKU EVK".
- NPU: **Hexagon NPU (v75)** — corroborated 3 ways (quad.toml, `libSnpeHtpV75Skel.so`
  at `/usr/lib/rfsa/adsp/`, SoC generation).
- **Unknown / not registerable yet:** authoritative `npu_tops` and Adreno
  `gpu_model`/`gpu_tflops` — no source for these exists in this repo, so they
  must come from the server's authoritative table, not a guess.

**Why not just edit the file here:** `capabilities.py` is a **vendored, frozen
copy** ("last sync from QUAD@2485044"; drift-guarded by
`tests/test_local/test_capabilities.py`, which hard-codes expected TOPS per
chipset). The authoritative table lives server-side
(`QUAD/src/quad/compiler/capabilities.py`).

**Suggested fix (server-side):** add a `QCS8275` entry (+ `iq-8275`/`iq8` aliases)
to the authoritative registry with real Adreno/TOPS specs, then re-sync the
vendored client copy and extend the contract test with a `test_qcs8275_registered`
case (mirroring `test_qcs9075_registered`).

---

## Issue 20 — detect skill's tomllib parse fails on Python 3.10 venv (BUG)

**Severity:** Medium — breaks the `quad.toml` SSH-target parse step on this host.

The `/quad-detect` skill (step 3) parses `quad.toml` with `import tomllib`, which
is **stdlib only on Python ≥3.11**. This host's client `.venv` is **Python
3.10.10** (the emulated-x86 interpreter on this X-Elite host), so the parse snippet
dies with `ModuleNotFoundError: No module named 'tomllib'`. Confirmed live 07-27
in the 3.10.10 venv; `.claude/skills/quad-detect.md:168` still uses plain
`import tomllib`, no fallback, and `tomli` is not in `pyproject.toml`.

**Suggested fix:** in the skill's parse snippet, `try: import tomllib` /
`except ModuleNotFoundError: import tomli as tomllib`, and add `tomli` to the
client deps for 3.10 (`tomli; python_version < "3.11"`). (`import tomli` already
succeeds — 2.4.1 is installed — so the one-line fallback is trivial; it just
isn't wired into the code.) Fix preserved in the backup patch; needs re-apply +
push.

---

## Issue 21 — sample crashes instead of skipping when quad_mcp_client / SDK missing (BUG)

**Severity:** Medium — hard-crashes the flagship sample at STEP 3 on a common config.

STEP 3's GPU/NPU benchmark does `from quad_mcp_client.qnn_utils import
benchmark_qnn_net_run` inside a `try` whose `except` caught
`(RuntimeError, FileNotFoundError, TypeError)` — but **not `ImportError`**. The
sample's own `.venv` (bootstrapped by `run.ps1` via `uv`) does **not** install
`quad_mcp_client`, so the import raised `ModuleNotFoundError`, which escaped the
handler and crashed the whole run — even though the block is explicitly designed
to "graceful skip if SDK missing". A `ValueError` from
`validate_backend_artifact` (HTP `.bin` on the GPU backend) escaped the same way.

**STATUS: VALID on `@3cfd3da`.** Confirmed live 07-27: the upstream NPU handler at
`run_mobilenetv2.py:1186` catches only `(RuntimeError, FileNotFoundError)`, so a
simulated `ImportError` escapes and crashes the run. Fix preserved in the backup
patch; needs re-apply + push.

**Suggested durable fix:** have `samples/*/run.ps1` install the core client into
the sample venv (add `-e ../..` or `quad-mcp-client` to each `requirements.txt`),
so STEP 3 can import `qnn_utils` without a manual step.

---

## Issue 22 — sample benchmarks a REMOTE-converted artifact against the LOCAL SDK (DESIGN — partial)

**Severity:** Medium — remote convert + local benchmark need reconciling.

Even after Issue 15's download fix, STEP 3 needs a **local** QAIRT SDK to run
`qnn-net-run`. With no `QNN_SDK_ROOT`, GPU+NPU skip with "QNN_SDK_ROOT not set".
Setting `QNN_SDK_ROOT=C:\Qualcomm\AIStack\QAIRT\2.47.1.260610` (present on this
host, per `/quad-detect`) lets `qnn-net-run` launch. So the model is *converted*
on the server but *executed* locally — the sample doesn't surface this split or
auto-discover the installed QAIRT.

**Suggested fix:** in the remote path, either run the benchmark server-side too
(via a profile tool) or auto-discover a local QAIRT (the CLI already knows the
path from `hardware_detect`) and set `QNN_SDK_ROOT` for STEP 3 instead of
requiring a manual `export`.

---

## Issue 23 — qnn-net-run crashes on host NPU: exit 0xC0000409 (STACK_BUFFER_OVERRUN) (BUG)

**Severity:** High — blocks actual NPU inference on the X-Elite host; CPU-only
numbers are all we get.

With SDK set and the artifact downloaded locally, the HTP/NPU benchmark launches
but `qnn-net-run` exits **3221226505 = 0xC0000409** (Windows
STATUS_STACK_BUFFER_OVERRUN) — a native crash, no usable output.

**Both original hypotheses DISPROVEN (2026-07-22):**
- **NOT an x86/arm64 emulation issue.** Rebuilt the sample in a **native ARM64
  venv** (`Python312-arm64`, `platform.machine()==ARM64`, onnxruntime 1.27.0
  arm64) and re-ran — `qnn-net-run` **still crashes with the identical
  0xC0000409**. The arm64-boundary theory is wrong.
- **NOT a host QAIRT version skew.** Host `qnn-net-run.exe` is **v2.47.1**
  (`aarch64-windows-msvc`), matching the server QAIRT 2.47 that compiled the
  `.bin`. So unlike the on-device boards (Issue 24), the host has no version
  mismatch — yet it still crashes.

**Revised diagnosis:** a genuine **host-side HTP runtime crash** on the X-Elite's
Hexagon v73 — the QAIRT 2.47 `qnn-net-run.exe` faults while loading/executing the
HTP context binary on this machine's NPU, independent of Python arch and SDK
version. Remaining suspect: the artifact itself (convert reported
`quantization_applied = fp32` despite the INT8 request — an fp32 graph on HTP,
or a context-binary/driver incompatibility on the Windows HTP stack). Next
isolation steps: (a) confirm whether the INT8 path actually quantizes (fp32 on
HTP may be the trigger); (b) try a known-good AI Hub precompiled `.bin` for the
X-Elite HTP; (c) check the Windows Hexagon NPU driver / QnnHtpPrepare.dll stack
version against QAIRT 2.47.

**Isolation step (b) attempted 2026-07-22 — BLOCKED.** Tried to source a
known-good precompiled MobileNet via `aihub_select`. Catalog lookup works
(`mobilenet_v2` exists, supports `snapdragon-x-elite` + `qcs8275`, incl. `w8a8`),
but **no runnable `.bin` is sourceable from here:**
- `action=pull` → *"No published bundle for 'mobilenet_v2' in the store."*
- `action=build_status job_id=mobilenet_v2.snapdragon-x-elite` → **state: failed,
  Pullable: false**.
- `action=ensure` → records a build job but **`client_buildable: false`** —
  *"Windows-on-ARM: torch has no win_arm64 wheel, so the qai-hub-models export
  front-end can't run here."* Building requires a ≥64 GB managed/Linux host, then
  `publish`.

So a precompiled artifact to isolate Issue 23 is **unavailable via this client**.
Issue 23's root cause remains unconfirmed pending a known-good artifact. CPU
inference works fine. The transport/plumbing fixes (14, 15, 21) are independent
of this and are done.

**Benchmark captured (2026-07-22, CPU-only, NPU blocked):** MobileNetV2
INT8-requested, remote-converted — **avg ~8.8 ms, ~113 FPS** (onnxruntime CPU,
emulated-x86 venv); native arm64 re-run **avg ~28.7 ms, ~35 FPS** (noisier, still
CPU-only). Top-1 "envelope" 17.8% is low-confidence — likely a
preprocessing-normalization mismatch (separate accuracy concern, not transport).

> **✅ Accuracy sub-note RESOLVED 2026-08-05 (on IQ8/QLI 2.0).** The "envelope
> 17.8% low-confidence" prediction was proven to be a **bad input tensor**, not
> the model/HTP: the *same* `input.raw` through `mobilenetv2.onnx` on host CPU
> gave the identical garbage top-5, and it traced to `input.raw` having been built
> from the junk `test_input.jpg`. Regenerating from `dog.jpg` with standard
> ImageNet preprocessing (resize 224 / RGB / ÷255 / mean-std / NCHW) → **Samoyed
> 85.9% CPU, 85.6% NPU**. This confirms the "separate accuracy concern" line above.
> The **host `qnn-net-run` 0xC0000409 crash** (this issue's core) is a different,
> Windows-host problem and remains **open** — not re-tested this session.


---

## Issue 24 — server QAIRT (2.47) newer than IQ on-device runtime (2.43) → context binary won't load (COMPAT — FLEET-WIDE)

**Severity:** High — a model converted by the QUAD server can be un-loadable on
the target device, with no pre-flight warning. **Confirmed on BOTH the IQ8
(QCS8275/v75) and IQ-9075 (QCS9075/v73)** — not board-specific.

> **✅ IQ8 RESOLVED 2026-08-05 (via the reflash this issue prescribes).** The IQ8
> was reflashed to the **Qualcomm Linux Reference Distro 2.0 (QLI 2.0)** image
> (`root@10.92.214.184`). QLI 2.0 ships with **no on-device QAIRT at all**, so
> there is no stale 2.43 runtime to be out of date. Pushing the host **QAIRT
> 2.47.1** `aarch64-oe-linux` runtime + `hexagon-v75` skels to `/opt/qnn` and
> converting the model at **2.47** makes runtime and binary match by construction
> — `qnn-net-run` on the HTP v75 ran a genuine MobileNetV2 pass (**~5.57 ms**,
> Samoyed 85.6% vs CPU 85.9%). Full log: `03_Devices/IQ8/IQ8_qli2.0_dogfooding.md`
> (Obsidian vault).
>
> **✅ IQ-9075 ALSO RESOLVED 2026-08-05 — issue now FULLY resolved fleet-wide.** The
> IQ-9075 (`root@192.168.29.185`) was found to be on the **same QLI 2.0 image**
> (also QAIRT-less). Applied the identical recipe with **`hexagon-v73` skels**:
> reused the *same* bin/lib bundle and the *same* float DLC from the IQ8 run
> (swapped only the DSP skel set), pushed to `/opt/qnn`, and `qnn-net-run`
> prepared the graph for **v73 on-device** and ran a genuine pass — **EXIT 0,
> ~2.79 ms, ~331 inf/sec, Samoyed 85.7%** (three-way match: CPU 85.9% / v75 85.6%
> / v73 85.7%). The float-DLC approach means one artifact serves both HTP archs.
> Full log: `03_Devices/IQ9/IQ9_qli2.0_dogfooding.md`. **Both boards now clear the
> version wall by construction; the reflash-to-QLI-2.0 fix is confirmed on v75 AND
> v73.**

`qnn-net-run` on the boards failed to load the server-converted context binary:

```
<E> Using newer context binary on old SDK
<E> Fail to get context blob with err 5000
<E> Failed to create context from binary with err 0x1388
Could not create context from binary   (EXIT=16)
```

Root cause — **QAIRT version skew** (confirmed on all sides):
- Conversion server / host QAIRT: **2.47.1.260610** (compiled the `.bin`).
- IQ8 on-device runtime: **QNN SDK v2.43.0**.
- **IQ-9075 on-device runtime: ALSO v2.43.0** — reproduced the identical
  `err 5000 / 0x1388`, exit 16, with the same `.bin`. Crucially the IQ9 is
  **HTP v73 — the SAME arch as the X-Elite host that compiled the `.bin`** — so the
  arch matches and it *still* fails. That isolates the cause to the SDK version
  skew alone (2.47 > 2.43), independent of HTP arch. Corroborated by the IQ9 skel
  set (`libSnpeHtpV{68,73,75}Skel.so` all present).

A QAIRT context binary compiled by a newer SDK is **not backward-compatible**
with an older on-device runtime. Nothing in the QUAD convert→deploy flow surfaces
the target's runtime version or warns about the skew; the user only finds out at
`qnn-net-run` load time on-device.

**No-reflash shim via the on-board 2.46 SDK — ATTEMPTED 2026-07-23, BLOCKED.**
The IQ9 has a full **QAIRT 2.46 SDK at `~/qairt_2.46.0.260424`**. Three combos
each hit a hard stop:

| Host runtime | DSP skel | Outcome |
|---|---|---|
| 2.46 | 2.46 (its own, hexagon-v73) | `Unsupported SoC model: 77` — the 2.46 skel's SoC table predates QCS9075 (SoC id 77); DSP won't bind (`err 4000`) |
| 2.46 | system 2.43 | `Invalid dsp arch / Failed to init HTP features` — fastRPC forbids mixing a 2.46 host stub with a 2.43 on-device skel |
| 2.43 (system) | 2.43 (system) | HTP starts fine (2.43 knows SoC 77) → 2.47-compiled `.bin` rejected: "newer context binary on old SDK" (the original wall) |

Forcing `dsp_arch=v73` + `soc_model` via an HTP backend-extensions config did
**not** help: the `SoC 77` rejection comes from the skel running on the silicon,
which reads the real hardware ID and can't be overridden from the host config.
**Conclusion:** loading a ≥2.45-compiled `.bin` on the IQ9 requires a **≥2.45 skel
that also recognizes SoC 77** — and that pairing only ships in the **QLI reflash
image**. The loose 2.46 SDK on disk cannot serve as a shim. This confirms the
reflash is the genuine fix.

**This is a DOCUMENTED limitation.** `quad-app-builder.md:1396` already describes
this exact wall and says the fixes are: **reflash the board to a newer image
(QAIRT ≥2.45)**, or **CPU fallback via plain `.onnx` + onnxruntime**. The IQ8/IQ9
2.43 is below the documented 2.45 floor.

**Residual product gaps worth filing upstream** (narrower than the wall itself):
- `convert_model` / the deploy path should record the target's QAIRT runtime
  version (detectable over SSH via `qnn-net-run --version`) and either convert
  with a compatible/older SDK or **warn pre-flight** when the conversion SDK is
  newer.
- `/quad-detect` should report the on-device `qnn-net-run` version per SSH target
  so the skew is visible before conversion.

**Resolution path chosen:** reflash the IQ8/IQ9 to QAIRT ≥2.45 (see
`docs/IQ8275_REFLASH.md` / `IQ9075_REFLASH.md`; physical/EDL, not SSH-drivable).
Cheaper alternative to try first: compile via **AI Hub Models targeting
QCS8275/v75 or QCS9075/v73** directly — but that route is currently blocked by
Issue 25.

---

## Issue 25 — AI Hub `force` compile rejects the sample's single-.onnx upload (BUG/UX)

**Severity:** Medium — blocks the documented non-reflash workaround (AI Hub
cloud compile targeting the board's HTP arch).

Attempted the documented alternative to reflashing: `convert_model` with
`aihub="force"`, `aihub_device="QCS9075 (Proxy)"`, uploading `mobilenetv2.onnx`.
Auth passed (AI Hub tokens exported), but the compile failed at packaging:

```
ToolError: Error calling tool 'convert_model':
Incorrect archived model. Expecting only one model asset at base path
{'.trtmodel', '.mlpackage', '.aimet', '.onnx', '.mlmodelc'}.
```

The AI Hub cloud compiler expects a specific archived-model layout; the sample's
raw single-`.onnx` upload (via `model_source={"kind":"upload"}`) doesn't match
what the `aihub=force` path packages.

**Not client-fixable here (confirmed 2026-07-22):** the client only POSTs raw
`.onnx` bytes (`_upload_file_remote` / `QuadClient.upload_file` → `X-Filename` +
octet-stream); the "Incorrect archived model" check is enforced **server-side**.
Fixing it requires a server-side change (auto-package the uploaded onnx into AI
Hub's archive layout) or a documented `model_source` form. Until then the AI Hub
route to dodge the version wall (Issue 24) is unavailable via this sample.

---

## Issue 28 — `detect` (no `--platform`) never queries the server — silent local fallback (BUG)

**Severity:** High — the default, most-common invocation silently contradicts
its own `--help` and docstring, and returns the inferior client-static answer
even when the authoritative server is reachable.

`quad-client detect` (no flags) is documented to *"Prefer the server's
authoritative (registry-enriched) hardware_detect; fall back to a local static
probe when the server is unreachable."* Live on this host, with the server
reachable (the same URL+token that `connect-test` handshakes in 725 ms):

```
$ quad-client detect --json                 → "discovery_source": "client-local-static"   # never touched the server
$ quad-client detect --platform windows --json → "discovery_source": "server"              # server path fine
```

**Root cause** — `src/quad_mcp_client/local/hardware.py:245-246` in
`detect_hardware_server_first()`:

```python
server_platform = platform if platform in {"windows","linux","android","gateway","robotics"} else None
if server_platform is not None:          # ← when --platform omitted, platform is None,
    try:                                 #    so this whole server-query block is skipped
        profile = _query_server(server_platform)
        ...
return detect_hardware(platform=platform, ...)   # ← always falls straight to local
```

When `platform is None` (the default), `server_platform` is `None`, the `if` is
false, and the function drops directly to the local static probe **without ever
trying the server**.

**Effect:**
- Default `detect` returns `client-local-static` on a fully-connected machine.
- On boards absent from the client's frozen `capabilities.py` (e.g. QCS8275,
  Issue 19), the default `detect` shows "unresolved" NPU specs even though the
  server's registry could resolve them.
- No diagnostic is printed, so the user can't tell the answer came from the local
  mirror.

**Suggested fix:** when `platform is None`, auto-detect the OS first and pass that
into the server-query gate, so the default path is genuinely "server-first" as
documented.

---

## Issue 29 — SDK `search_aihub()` pagination helper sends params the server rejects (BUG — README example crashes)

**Severity:** Medium — the exact `search_aihub` snippet advertised in the README
"Python SDK" section raises a `ToolError` against the live server.

`QuadClient.search_aihub()` (`src/quad_mcp_client/client.py:672-696`) pages the
catalog by sending `limit` + `offset` and reading `next_offset`:

```python
res = await self.aihub_select(action="search", query=query, limit=page_size, offset=offset)
...
next_offset = res.get("next_offset")
```

But the live server's `aihub_select` tool schema has **no `limit`/`offset`/
`next_offset`** — it paginates with `top_k`. Running the README example live:

```
$ async for m in client.search_aihub("mobilenet", max_results=10): ...
fastmcp.exceptions.ToolError: 2 validation errors for call[aihub_select]
  limit  Unexpected keyword argument [input_value=25]
  offset Unexpected keyword argument [input_value=0]
```

Confirmed the server accepts the correct shape — `aihub_select(action='search',
query='mobilenet', top_k=3)` returns `matches` fine. So `search_aihub` is
**client/server contract drift**.

Live server `aihub_select` params (for reference):
`action, query, top_k, platform, model_id, task, use_case, device_class,
target_format, qairt_version, require_npu, require_genie, …` — **no
`limit`/`offset`.**

**Suggested fix:** rework `search_aihub` to the server's real contract — request
with `top_k` (cap = `max_results`/`page_size`), read the returned `matches`, and
drop the `next_offset` loop. Update the README snippet to match. Until fixed,
callers must use `aihub_select(action='search', query=…, top_k=N)` directly.

---

## Issue 30 — `test_search_aihub_paginates` mock encodes a contract the server doesn't honor (TEST GAP)

**Severity:** Low — but it's *why* Issue 29 shipped: the test suite is green
while the real call is broken.

`tests/test_client_sdk.py:181-192` (`test_search_aihub_paginates`,
`test_search_aihub_respects_max_results`) feeds the client mocked responses that
contain `next_offset`:

```python
_Structured({"matches": [{"id": "a"}, {"id": "b"}], "next_offset": 2}),
_Structured({"matches": [{"id": "c"}], "next_offset": None}),
```

Those mocks assert the `limit/offset/next_offset` pagination contract — the same
one the **live server rejects** (Issue 29). This is a classic mock-drift blind
spot — the test can never catch Issue 29 because it *bakes in* the wrong contract.

**Suggested fix:** after fixing Issue 29, update these tests to the server's real
`aihub_select` response shape, and add a **contract test** that validates the
SDK's outgoing argument names against the live/recorded server `inputSchema` for
`aihub_select` (and the other five tools). A recorded-schema fixture (dump
`list_tools()` once, assert SDK kwargs ⊆ server params) would have caught both
Issue 29 and any future rename.

---

## Issue 31 — `quad-app-builder` points to a sample dir that doesn't exist (`mobilenetv2_iq9075`) (BUG)

**Severity:** Medium — the skill names this as *the reference app* for IQ-9075
NPU work; the path is wrong in **all 5 occurrences**.

`quad-app-builder.md` cites `samples/mobilenetv2_iq9075/` at lines **249, 253,
1036, 1404, 1405**. The real directory is **`samples/mobilenetv2_npu_iq9075/`**
(the `_npu_` segment is missing). Verified live:

```
$ ls samples/mobilenetv2_iq9075        → No such file or directory
$ ls samples/mobilenetv2_npu_iq9075/   → ARCHITECTURE.md deploy/ README.md
                                          requirements.txt run.ps1 run_iq9075.py
                                          test_input.jpg tests/
```

The files the skill names (`deploy/inference.py`, `run_iq9075.py`) exist, but only
under the correct `_npu_` name. Likely cause: the sample was renamed when it was
added in `3cfd3da`, but the skill text wasn't updated.

**Suggested fix:** replace `samples/mobilenetv2_iq9075/` →
`samples/mobilenetv2_npu_iq9075/` in all 5 spots (edit the `skills_content/`
source, then `quad-client install --force` to re-sync the flat + dir copies so
the sync guard stays green).

---

## Issue 32 — `quad-app-builder` references 5 docs that don't exist in the repo (BUG)

**Severity:** Medium — the skill routes the agent to these files as authoritative
context, but none exist, so the guidance is unfollowable.

`quad-app-builder.md` names these non-existent paths:

| Referenced path | Exists? |
|---|---|
| `export_assets/mobilenet_v2_iq9075_qnn/SOP_IQ9075_BOARD_BRINGUP.md` | ❌ dir has only `mobilenet_v2-qnn_context_binary-float-qualcomm_qcs9075/` |
| `export_assets/mobilenet_v2_iq9075_qnn/FULL_RETROSPECTIVE_IQ9075.md` | ❌ not in repo |
| `docs/GWAPPS_INTEGRATION.md` | ❌ not in repo |
| `docs/QUAD_GWAPPS_INTEGRATION_PLAN.md` | ❌ not in repo |
| `docs/QUAD_GWAPPS_PROGRESS.md` | ❌ not in repo |

Confirmed live: `export_assets/mobilenet_v2_iq9075_qnn/` contains **only** the
context-binary folder; a repo-wide `find` for those basenames returns nothing.

**Suggested fix:** either add the missing docs, or remove/repoint the references
in `quad-app-builder.md`. If the SOP/retrospective live only in a private repo,
the skill should say so rather than naming an in-repo path.

---

## Issue 33 — three other skills cite docs missing from the repo (BUG — low)

**Severity:** Low — secondary "see also" pointers, not primary instructions, but
still dangling.

| Skill | Missing doc |
|---|---|
| `quad-build-npu-bundle.md` | `docs/BUNDLE_REGISTRY_PLAN.md` |
| `quad-detect.md` | `docs/debugging/Issue_MCP_Connectivity_investigation.md` |
| `quad-detect.md` | `docs/debugging/SoC_Identity_DSP_Skel_False_Positive.md` |
| `quad-deploy.md` | `docs/REAL_HARDWARE.md` |

Confirmed live: **`docs/debugging/` does not exist at all**, and a repo-wide
search for each basename returns nothing. (Docs that DO exist and are correctly
referenced: `docs/DEVELOPER_GUIDE.md`, `docs/TRANSPORTS.md`,
`docs/TROUBLESHOOTING.md`, `docs/IQ9075_SOPs.md`, `docs/IQ9075_GPU_STATUS.md`.)

**Suggested fix:** add the missing docs or drop the references. A cheap durable
guard: extend `scripts/check_skills_sync.py` (or add a lint) to verify every
in-repo path a skill mentions (`samples/…`, `docs/…`, `export_assets/…`,
`scripts/…`) actually resolves — that single check would have caught Issues 31,
32, and 33 in CI.

---

## Issue 34 — `profile-device` client-agent hardcodes an Android workspace → fails on SSH/Linux boards (BUG)

**Severity:** High — the flagship "cloud server + local board" flow is dead on
arrival for the IQ-9075 (and any Qualcomm-Linux board) over SSH.

`quad-client profile-device --transport ssh` against the IQ9 fails at the first
push:

```
$ quad-client profile-device --model …/mobilenetv2.bin --transport ssh \
      --host 192.168.29.185 --user ubuntu --key ~/.ssh/iq9_nopass --runtime npu …
[FAIL] model push failed: /usr/bin/scp: dest open
  "/data/local/tmp/quad/models/mobilenetv2.bin": No such file or directory
```

**Root cause:** `src/quad_mcp_client/local/device_agent.py:74`:

```python
workspace = str(plan.get("workspace", "/data/local/tmp/quad")).rstrip("/")
```

The remote workspace defaults to the **Android/adb path** `/data/local/tmp/quad`.
On the IQ-9075's Qualcomm **Ubuntu Linux** image, `/data` is **not writable** by
the `ubuntu` SSH user, so `mkdir -p`/`scp` fail. The CLI exposes **no
`--workspace`/`--remote-dir` flag** to override it, and the default comes from the
*server's plan*. Verified live: `mkdir /data/local/tmp/quad` → `Permission
denied`; the writable location is `$HOME` (e.g. `/home/ubuntu/quad`).

**Effect:** the entire client-agent profiling path (`profile-device`,
`--model-from-server`, `--convert`) is unusable over SSH on any board whose rootfs
doesn't expose a writable `/data/local/tmp` — i.e. every Qualcomm-Linux EVK.
adb/Android boards are unaffected.

**Suggested fix:** (a) add a `--workspace`/`--remote-dir` flag that overrides
`plan["workspace"]`; and/or (b) default the workspace per transport —
`/data/local/tmp/quad` for adb, `~/quad` for ssh; and/or (c) have the server's
`profile_device_plan` emit an SSH-appropriate workspace when the transport is ssh.
A writable-path pre-flight would turn the failure into an actionable message.

---

## Issue 35 — `mobilenetv2_npu_iq9075` sample orchestrator hardcodes the same Android workspace (BUG)

**Severity:** High — the sample's headline SSH path fails out of the box on the
very board it targets.

`samples/mobilenetv2_npu_iq9075/run_iq9075.py:93` hardcodes:

```python
REMOTE_WORKSPACE = "/data/local/tmp/quad/"
```

Running the documented SSH command against the IQ9:

```
$ python run_iq9075.py --transport ssh --host 192.168.29.185 --user ubuntu \
      --key ~/.ssh/iq9_nopass --cpu-only …
[error] ssh command failed (exit 1): mkdir: cannot create directory '/data': Permission denied
```

Same Android-path assumption as Issue 34, in a second independent code path.
There is **no flag to override** `REMOTE_WORKSPACE`.

**Proof the rest of the sample is sound:** pushing the same artifacts to a
writable `~/quad` by hand and running `deploy/inference.py` on-device produced a
**real CPU benchmark (6.31 ms / 158.6 FPS, ORT 1.28.0)** and correct graceful
NPU/GPU-skip messaging. So the bug is isolated to the orchestrator's workspace
constant, not the inference logic.

**Suggested fix:** add a `--remote-workspace` arg (default `/data/local/tmp/quad/`
for adb, `~/quad/` for ssh), or derive it from the transport. Mirror whatever fix
Issue 34 takes so the sample and the CLI agree.

---

## Issue 36 — `mobilenetv2_npu_iq9075` README lists model + labels as shipped, but they're absent with no auto-download (BUG)

**Severity:** Medium — a fresh clone can't run the sample without manually
sourcing two files the docs imply are present.

The sample README's project-layout diagram lists:

```
├── mobilenetv2.onnx      — ONNX Model Zoo export (CPU / plugin-EP path)
├── test_input.jpg
```

but the directory ships **only** `test_input.jpg` — `mobilenetv2.onnx` is absent,
and so is `imagenet_classes.txt` (the default `--labels`). The orchestrator
hardcodes both as defaults (`DEFAULT_MODEL = HERE / "mobilenetv2.onnx"`,
`DEFAULT_LABELS = HERE / "imagenet_classes.txt"`) and **does not download** them
(unlike the sibling `samples/mobilenetv2/run.ps1`, which fetches the ONNX from the
Model Zoo). Result on a clean checkout:

```
[error] model not found: …/samples/mobilenetv2_npu_iq9075/mobilenetv2.onnx
# and, once model supplied:
[error] labels not found: …/samples/mobilenetv2_npu_iq9075/imagenet_classes.txt
```

(Worked around here by copying both from `samples/mobilenetv2/`.)

**Suggested fix:** either add an ONNX/labels download step to `run_iq9075.py` /
`run.ps1` (reuse the sibling sample's Model-Zoo fetch), or update the README
layout + Prerequisites to state both must be supplied and how. The `.bin` context
binary is already correctly documented as "not shipped, obtain via convert_model /
AI Hub" — apply the same clarity to the ONNX + labels.

---

## Issue 37 — `unoq configure` ignores the connected board, defaults to UNO Q profile (UX BUG)

**Severity:** Low — produces a misleading config; correct output needs a flag the
user may not know to pass.

`quad-client unoq configure <ip>` connects to (and echoes) the given host, but
without `--board` it emits a stanza hardcoded to the **wrong** board:

```
$ quad-client unoq configure 192.168.29.185 --user ubuntu     # an IQ-9075
[target]
board = "arduino-unoq"
soc = "qcs2210"          # ← wrong; IQ9 is qcs9075
hexagon = "v66"          # ← wrong; IQ9 is v73
…
max_ram_mb = 2048        # ← wrong; IQ9 has 35 GB
preferred_runtime = "dsp"
```

Passing `--board iq9075` fixes it (correct `qcs9075/v73/htp/8192 MB`), and the
profile exists in `_BOARD_PROFILES` — but nothing about connecting to a QCS9075
host makes `configure` pick it. It also always writes `key = "~/.ssh/id_rsa"`
regardless of the `--key`/`--user` actually used.

**Suggested fix:** since `configure` already takes a host, do a lightweight SSH
probe (or reuse `detect`) to auto-select the board profile; at minimum, when
`--board` is omitted, warn that it's defaulting to `arduino-unoq`. Populate the
`key` field from the resolved key path rather than a hardcoded `id_rsa`.

---

## Issue 38 — pushing a `.tgz` runtime bundle to QLI 2.0 drops the exec bit → `Permission denied` (OPS — low)

**Severity:** Low — one-line fix, but silently blocks first-run and is easy to
misread as a corrupt/incompatible binary. **Hit live 2026-08-05 on the IQ-9075**
during the QLI 2.0 NPU bring-up (`03_Devices/IQ9/IQ9_qli2.0_dogfooding.md`).

After `pscp`'ing the QAIRT runtime bundle and `tar xzf`'ing it into `/opt/qnn`,
the very first invocation failed:

```
sh: line 15: /opt/qnn/bin/qnn-net-run: Permission denied
```

Root cause — the extracted `bin/` files landed **without** the executable bit
(mode `rw-r--r--`). Depending on how the tar was authored on the Windows host and
the extracting umask, the `+x` on `qnn-net-run` / `qnn-profile-viewer` is not
preserved. Nothing about the message points at file mode, so it reads like an ABI
or arch mismatch.

**Fix (verified):**
```sh
chmod +x /opt/qnn/bin/*
```
**Durable fix:** author the bundle with modes preserved (`tar --mode='a+rx' …` for
the `bin/` entries), or have the deploy step always `chmod +x` the pushed binaries
before the first run. Applies to any board provisioned from a host-built tarball,
not just QLI 2.0.

---

## Recommended fix order

1. **Issue 1** (`--system-certs` → `--native-tls`) — the actual code bug (11
   files). Re-apply from the backup patch + push.
2. **Issue 2** — re-run with the Netskope CA exported, or rely on `--native-tls`
   reading the OS store once #1 lands.
3. **Issue 12** — add `.gitattributes` (`*.sh text eol=lf`) so shell scripts don't
   ship CRLF to Linux devices. High impact for IQ8/IQ9.
4. **Issue 9** — add an `ANTHROPIC_BASE_URL` check to `quad-client doctor`.
5. **Issue 28** (High) — make the default `detect` genuinely server-first
   (auto-detect OS → server gate) instead of silently returning the local mirror.
6. **Issues 14, 15, 21** — MobileNetV2 sample: auth the remote convert, upload the
   model + download the artifact, and catch `ImportError`/`ValueError` in STEP 3.
   Re-apply from the backup patch; durable: add `-e ../..` to sample
   `requirements.txt`.
7. **Issue 16** — re-add the `[target.iq-8275]` `quad.toml` stanza; and steer
   `quad-detect` from an empty `adb devices` toward SSH/serial.
8. **Issue 20** — `tomli` fallback in the detect skill + client deps.
9. **Issues 31, 32, 33** — fix the stale/broken path references in
   `quad-app-builder` / `quad-detect` / `quad-build-npu-bundle` / `quad-deploy`,
   and add a CI lint that resolves every in-repo path a skill mentions.
10. **Issues 34, 35** — add `--remote-workspace`/`--remote-dir` (default `~/quad`
    for ssh, `/data/local/tmp/quad` for adb) to `profile-device` and
    `run_iq9075.py`; unblocks the whole client-agent SSH flow on Qualcomm-Linux.
11. **Issue 36** — download the ONNX + labels in `run_iq9075.py`/`run.ps1`, or fix
    the README to document the fetch.
12. **Issue 29** — rework `search_aihub()` to the server's `top_k` contract; update
    the README snippet.
13. **Issue 30** — after #29, update the pagination tests to the real response
    shape and add a recorded-schema contract test for all tools.
14. **Issue 22** — reconcile remote-convert + local-benchmark: auto-discover the
    installed QAIRT and set `QNN_SDK_ROOT` for STEP 3, or benchmark server-side.
15. **Issue 37** — `unoq configure` should auto-select the board profile from an
    SSH probe (or warn when defaulting to `arduino-unoq`) and use the resolved key.
16. **Issue 19** (server-side) — add `QCS8275` to the authoritative capability
    registry with real Adreno/TOPS specs, re-sync the vendored client copy, extend
    the contract test.
17. **Issue 24** (High) — ✅ RESOLVED on both boards via QLI 2.0 (push-2.47-runtime
    + float DLC). Remaining product work: convert/deploy should still detect the
    target's on-device QAIRT version and warn (or match) when the conversion SDK is
    newer, and `/quad-detect` should report the per-target `qnn-net-run --version`
    — so a *non*-QLI board (still on 2.43) gets a pre-flight warning instead of a
    load-time failure.
18. **Issue 25** (server-side) — package uploaded `.onnx` into AI Hub's archive
    layout so `aihub=force` compiles for QCS8275/QCS9075 succeed.
19. **Issue 23** (High) — host NPU `qnn-net-run` crash (0xC0000409). Arm64-venv and
    version-skew theories both DISPROVEN. Next: confirm INT8 actually quantizes
    (convert reported fp32), try a known-good AI Hub precompiled `.bin`, check the
    Windows Hexagon driver / QnnHtpPrepare stack.

---

## ⚠️ Redaction note (vault policy)

**Report body redacted (2026-07-22):** the `QUAD_MCP_TOKEN` /
`ANTHROPIC_AUTH_TOKEN` prefixes previously shown were replaced with `Stored in
password manager`. This markdown file contains no token material.

**Still live outside this file — do NOT commit / handle with care:**
- `.env` (repo root, gitignored) holds the **full** `QUAD_MCP_TOKEN` (64-char).
  Keep it gitignored; never copy into a note.
- **AI Hub tokens** `QAIHUB_API_TOKEN` / `QAIHUB_CLI_TOKEN` were exported into the
  shell during the Issue 25 attempt. Verify they are not persisted in any tracked
  file or shell profile; rotate if they were.
- Vault policy: log any redaction in `02_Tech/Security/Redaction Log.md`.
