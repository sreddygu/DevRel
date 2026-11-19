---
name: quad-detect
description: Use when the user asks "what hardware do I have", "is this a Snapdragon", "do I have an NPU", "what's on this machine", "what targets are connected", "probe my UNO Q", "probe my IQ-9075", or invokes /quad-detect. Probes the local host AND any reachable target devices -- USB-attached boards via adb, plus SSH targets configured in quad.toml -- rendering chipset, CPU/GPU/NPU, RAM, runtimes, and SDK status for each. Fully probe-driven: reads the target's own device-tree/SoC strings, never assumes a specific board.
trigger: "detect"
user-invocable: true
allowed-tools:
  - Bash(quad-client *)
  - Bash(.venv/Scripts/python.exe *)
  - Bash(adb *)
  - Bash(adb.exe *)
  - Bash(ssh *)
  - Read
  - Glob
  - mcp__quad__hardware_detect
---

# /quad-detect -- QUAD Hardware Detection

Probes the local machine **and** any reachable target devices for
Qualcomm chipset, CPU/GPU/NPU specs, RAM, available runtimes, and SDK
installation. Targets are discovered two ways:

1. **USB** -- any board attached via Android Debug Bridge (UNO Q, Android phones)
2. **SSH** -- any `[target.*]` block in `quad.toml` (Rubik Pi, RB5, IQ-9075, AI Gateway, custom Linux)

> **No board assumptions.** Every fact below is read from what the target
> itself reports (`/sys/devices/soc0/machine`, `/proc/device-tree/model`,
> `uname`, skel paths, `clinfo`), never hard-coded to UNO Q. Device-tree
> `compatible` strings can be shared platform/family labels rather than
> per-SKU identifiers on multi-SoC reference-distro BSPs — see the SoC
> identity note in step 2. Known SoCs (Snapdragon X Elite, 8 Elite, QCS2210,
> **QCS9075 / Dragonwing IQ-9075**, …) resolve to canonical TOPS/HTP-arch via
> the server registry; unknown SoCs report what was probed with an honest
> "unrecognized SoC" note rather than a fabricated spec.

Arguments passed: `$ARGUMENTS`

---

## Detection steps

### 1. Local host probe

```
.venv/Scripts/python.exe -m quad_mcp_client.cli detect
```

Display the rendered host table verbatim.

### 2. USB target probe (adb)

**Locate `adb`** in this order, taking the first hit:

1. `where.exe adb` -- on PATH
2. `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe` -- winget install
3. `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe` -- Android Studio install

If none found, render this hint and skip step 2:

> No USB targets probed -- `adb` not installed. Install with:
> `winget install Google.PlatformTools`

**Enumerate devices.** Set `MSYS_NO_PATHCONV=1` for every adb invocation
to stop Git Bash from rewriting `/data/...` paths. Then:

```
adb devices
```

Skip lines marked `unauthorized` or `offline`. Skip the header
`List of devices attached`.

**Probe each device** with a single combined `adb shell` one-liner:

```
adb -s <serial> shell '
  echo "===whoami==="; whoami
  echo "===host==="; hostname
  echo "===uname==="; uname -mr
  echo "===os==="; (cat /etc/os-release 2>/dev/null | grep -E "^(PRETTY_NAME|ID)=" || (echo "ANDROID"; getprop ro.build.version.release; getprop ro.product.model))
  echo "===soc_dt==="; (cat /proc/device-tree/model 2>/dev/null; echo; cat /proc/device-tree/compatible 2>/dev/null | tr "\0" " "; echo)
  echo "===soc0==="; cat /sys/devices/soc0/machine 2>/dev/null; cat /sys/devices/soc0/soc_id 2>/dev/null
  echo "===mem==="; free -m | head -2
  echo "===disk==="; df -h / 2>/dev/null | tail -1
  echo "===dsp_skel==="; ls /usr/lib/rfsa/adsp/libSnpe*Skel*.so /vendor/lib*/libSnpe*Skel*.so 2>/dev/null | head -3
  echo "===dsp_skel_qcom_share==="; find /usr/share/qcom -maxdepth 6 -iname "*Skel*.so" 2>/dev/null | head -200
  echo "===fastrpc==="; ls /dev/fastrpc-* 2>/dev/null || echo none
  echo "===gpu==="; ls /sys/class/drm/ 2>/dev/null | head -3; clinfo 2>/dev/null | grep -E "Platform Name|Platform Vendor" | head -2
  echo "===snpe==="; (test -x /opt/snpe/bin/snpe-net-run && /opt/snpe/bin/snpe-net-run --version 2>&1 | head -1) || echo none
  echo "===python==="; python3 --version 2>&1; python3 -c "import onnxruntime; print(\"onnxruntime\", onnxruntime.__version__)" 2>/dev/null || echo "no onnxruntime"
'
```

> **SoC identity — `/sys/devices/soc0/machine` is authoritative, `/proc/device-tree/compatible` is not, on any board that may run a multi-SoC "reference distro" BSP (e.g. QLI 2.0+).** `soc0/machine` is read from fused/firmware SoC identity and does not change with the OS image; `compatible` is DT content shipped *in* the OS image. Confirmed case: an IQ-9075 EVK (QCS9075) reflashed from QLI 1.6 to QLI 2.0 reported `compatible = "qcom,lemans-evk qcom,qcs9100 qcom,sa8775p"` (a shared platform/family string covering several related SoCs on one reference rootfs) while `soc0/machine = QCS9075` correctly identified the actual silicon. Treat `compatible` alone as **insufficient** to declare a SoC mismatch — always read `soc0` first, and if the two disagree, report `soc0` as ground truth and note the DT string as a platform-family label, not a misdetection.

> **`dsp_skel_qcom_share` is uncapped-then-filtered, not truncated-then-hoped.** `head -200` above exists only to bound worst-case output size, not to cap "enough" results — a `head -10` in an earlier version of this probe, and a `head -30` in the very next revision, both truncated *before* reaching the real match on a live IQ-9075 (its `V73` skel sorted at line 31 of 59 total hits, one line past that second cap). **Any fixed cap can be defeated by a rootfs with one more bundled SoC variant** — this glob returns 50+ hits across every SoC variant bundled on a multi-SoC reference distro, in filesystem-traversal order, not relevance order. **Never hardcode an HTP version (e.g. `V73`) when filtering either** — that only works for the specific board seen once and silently returns nothing on a QCS6490 (v68) or QCS8550 (v69) board. The only correct fix is filter-then-cap: capture the (nearly) full list uncapped, THEN filter host-side by the `soc0`-resolved chipset via this repo's own registry, and only then truncate the *filtered* result for display:
> ```
> .venv/Scripts/python.exe -c "
> import sys; sys.path.insert(0, 'src')
> from quad_mcp_client.local.capabilities import lookup_for_chipset
> cap = lookup_for_chipset('<soc0_machine_value>')  # e.g. 'QCS9075'
> print(cap['npu_model'] if cap else 'unresolved')  # -> 'Hexagon NPU (v73)' -- extract the vNN
> "
> ```
> Then re-filter the already-captured `dsp_skel_qcom_share` output for `*V<NN>*Skel*.so` using that derived version, and treat the unfiltered `head -200` list as a fallback if the registry has no entry for this SoC (unrecognized/newer chipset) rather than failing closed.

Parse each `===section===` block and render one markdown table per device:

```markdown
#### USB device <serial>

| Field | Value |
|-------|-------|
| Model | <SoC name from /sys/devices/soc0/machine (authoritative) — cross-check against /proc/device-tree/model/compatible, but do not let a DT family/platform string override soc0> |
| OS | <os-release PRETTY_NAME or "Android <version>"> |
| Kernel | <uname -mr> |
| RAM | <total> MB total / <available> MB free |
| Disk (/) | <df> |
| DSP (Hexagon) | <skel paths found under BOTH /usr/lib/rfsa/adsp/ AND /usr/share/qcom/*/**/dsp/cdsp/, filtered by the soc0-derived HTP version — see note above>, fastrpc=<yes/no> |
| GPU | <DRM cards>, OpenCL=<platform name or "none"> |
| SNPE | <version + path, or "not installed"> |
| Python | <python version>, onnxruntime=<version or "missing"> |
| Working compute | <see notes below> |
```

**"Working compute" decision rules:**
- `fastrpc=yes` AND `snpe-net-run --version` works -> `Hexagon DSP via SNPE/QNN (likely)`
- `fastrpc=no` AND skel present -> `Skel installed but no fastrpc -- DSP compute unavailable on this image`
- OpenCL platform shows `rusticl` -> append `; SNPE GPU backend will not initialize (Mesa rusticl, not Adreno)`
- onnxruntime present and CPU-only path -> add `ONNX Runtime CPU` as the always-available fallback
- **Skel search is two-glob, not one, AND arch-filtered dynamically, not hardcoded.** `/usr/lib/rfsa/adsp/libSnpe*Skel*.so` is the standard path, but a multi-SoC reference-distro image (QLI 2.0+) can ship the real skel nested under `/usr/share/qcom/<variant-name>/.../dsp/cdsp/` instead — e.g. an IQ-9075's actual `libQnnHtpV73Skel.so` was found under `/usr/share/qcom/sa8775p/.../dsp/cdsp/`, not the standard path. An empty result at the standard glob means "not found there yet", never "not installed" — always check the broader `/usr/share/qcom` search (`===dsp_skel_qcom_share===` above) before reporting a skel/NPU-arch as missing. That broader search can return 50+ hits across every SoC variant bundled on the rootfs — **filter by the `soc0`-derived HTP version (via `capabilities.py`'s `lookup_for_chipset`, see the note above the probe), never a hardcoded `V73`** — a fixed version string only matches the one board already seen and silently returns nothing on any other SoC.
- SoC resolves to **QCS9075 / IQ-9075** (per `soc0/machine`, not the DT `compatible` string alone) -> NPU (HTP v73, confirmed dynamically via `lookup_for_chipset`, not assumed) via `qnn-net-run` + AI Hub Models `.bin` is the validated path; the **QNN GPU backend is blocked** by an Adreno OpenCL driver symbol gap (see `docs/IQ9075_GPU_STATUS.md`), so report GPU as `present but QNN GPU backend unavailable (driver)`. **A different SoC resolving from `soc0` on this same multi-SoC BSP (e.g. an actual QCS8300 or QCS6490 board) is expected and must use its own registry-resolved arch/NPU-model, not this IQ-9075 profile** — do not assume every device connected while QLI 2.0 is running is an IQ-9075.

### 3. SSH target probe (quad.toml + .env_boards)

**Look for quad.toml** in CWD using Glob, then `..` and `../..` (workspace
root common locations).

> **Mandatory ordering — source `.env_boards` BEFORE parsing `quad.toml`,
> every run, no exceptions.** This is not optional prose to remember when
> convenient — on a genuinely fresh terminal (new session, `.env_boards`
> never sourced yet) skipping this step does not error or leave the
> literal `${env:...}` placeholder behind; `os.environ.get(VAR, '')`
> silently substitutes an **empty string** for any unset var, so an
> unsourced run produces `host=""`/`user=""` with no exception raised
> anywhere in the parse itself. The only signal that anything went wrong
> is the *value* being empty — nothing forces you to check it. Always run,
> immediately before the Python block below, in the same shell session:
> ```bash
> set -a; source .env_boards 2>/dev/null; set +a
> ```
> (`.env_boards` is optional/absent for boards that don't need it — the
> `2>/dev/null` on a missing file is expected, not an error to chase. But
> if the target you're resolving DOES need it, per its `quad.toml`
> `${env:VAR}` reference, and you skipped this line, you will get an
> empty host with no error.)

**Parse `[target.*]` blocks** -- there may be multiple. Use the venv's
Python so tomllib is available without installing anything. `host`/`user`
values may reference `${env:VAR}` (the same expansion pattern
`.claude/settings.json` uses for `QUAD_MCP_TOKEN`) -- expand these against
the current shell environment (`.env_boards` must already be sourced per
the mandatory step above) so a `quad.toml` stanza that points at env vars
resolves to a real value instead of silently becoming an empty string:

```
.venv/Scripts/python.exe -c "
import tomllib, sys, json, os, re
missing_vars = []
def expand(v):
    if not isinstance(v, str):
        return v
    def repl(m):
        val = os.environ.get(m.group(1))
        if val is None:
            missing_vars.append(m.group(1))
            return ''
        return val
    return re.sub(r'\\\$\{env:([A-Z_][A-Z0-9_]*)\}', repl, v)
with open(sys.argv[1], 'rb') as f:
    cfg = tomllib.load(f)
targets = []
tgt = cfg.get('target')
if isinstance(tgt, dict):
    # tomllib nests [target.<name>] as cfg['target'][<name>], NOT a flat
    # 'target.<name>' key. TWO valid shapes exist in this repo:
    #  (a) a bare [target] block (single board, no name -- e.g. what
    #      `quad-client unoq configure` emits): 'ssh' is a DIRECT key of
    #      cfg['target'] itself.
    #  (b) [target.<name>] blocks (one or more named boards): 'ssh' is
    #      nested one level deeper, under cfg['target'][<name>].
    # Check both -- do not assume only one shape, and do not filter on
    # k.startswith('target.'), it never matches tomllib's real output.
    if isinstance(tgt.get('ssh'), dict) and tgt['ssh'].get('host'):
        before = len(missing_vars)
        host, user = expand(tgt['ssh']['host']), expand(tgt['ssh'].get('user', 'root'))
        targets.append({
            'name': 'target',
            'host': host,
            'user': user,
            'port': tgt['ssh'].get('port', 22),
            'key':  tgt['ssh'].get('key', '~/.ssh/id_rsa'),
            'soc':  tgt.get('soc', '?'),
            'hexagon': tgt.get('hexagon', '?'),
            'board': tgt.get('board', '?'),
            'missing_env_vars': missing_vars[before:],
        })
    for name, v in tgt.items():
        if not isinstance(v, dict):
            continue
        ssh = v.get('ssh', {})
        if isinstance(ssh, dict) and ssh.get('host'):
            before = len(missing_vars)
            host, user = expand(ssh['host']), expand(ssh.get('user', 'root'))
            targets.append({
                'name': name,
                'host': host,
                'user': user,
                'port': ssh.get('port', 22),
                'key':  ssh.get('key',  '~/.ssh/id_rsa'),
                'soc':  v.get('soc', '?'),
                'hexagon': v.get('hexagon', '?'),
                'board': v.get('board', '?'),
                'missing_env_vars': missing_vars[before:],
            })
print(json.dumps(targets))
" <path-to-quad.toml>
```

**Hard check, before probing anything — do not skip.** For every target
in the parsed output, if `missing_env_vars` is non-empty for that target
(i.e. its `quad.toml` stanza references at least one `${env:VAR}` that
had no value in the current shell), **stop and report it as
unreachable** with the exact var name(s) named, e.g.:

> `iq-9075: unreachable -- IQ9075_HOST not set. Did you source
> .env_boards in this shell before running quad-detect? (`set -a; source
> .env_boards 2>/dev/null; set +a`)`

Do **not** fall through to attempting an SSH/adb connection with an empty
`host`/`user` — that produces a confusing generic connection failure
instead of the actionable "you forgot to source .env_boards" message
this check exists to give. This is the difference between a target that
is genuinely unreachable (real network/auth failure) and one that was
never actually resolved in the first place.

> **Dual-source fallback -- do not stop at "quad.toml not found/empty."**
> Per `docs/debugging/Issue_MCP_Connectivity_investigation.md`-style
> config-fragmentation risk: a board's SSH connection details may live in
> `.env_boards` (gitignored per-board secrets, see `.env_boards.example`)
> with no matching `quad.toml` `[target.*]` stanza yet -- this is a valid,
> supported project state, not a misconfiguration. If `quad.toml` yields
> zero targets, before rendering the "no target devices" message, check
> whether `.env_boards` (or the current shell env) defines any
> `<BOARD>_HOST` var (e.g. `IQ9075_HOST`) and probe that host directly with
> its matching `<BOARD>_SSH_USER`/`<BOARD>_SSH_PASSWORD`/`<BOARD>_PLINK_PATH`
> vars, rather than silently reporting no SSH targets when a real,
> documented connection path exists. Render this target the same as a
> `quad.toml`-sourced one, noting `source: .env_boards` instead of
> `source: quad.toml` so the report is honest about where the config came
> from.

**Probe each SSH target** with the same combined one-liner as the adb
case, but invoked over SSH. Note: password-auth boards (e.g. IQ-9075 per
`.env_boards`) cannot use the OS `ssh` binary non-interactively -- use
`plink.exe -pw <password>` instead (see `CLAUDE.md`'s "Board connect
(IQ-9075)" section for the exact invocation); `ssh -o BatchMode=yes` below
is for key-auth boards only:

```
ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    -p <port> -i <key> <user>@<host> '<combined probe>'
```

If `ssh -o ConnectTimeout=5` fails: render the target row with a
`status: unreachable` cell and the failure reason; do not abort the
overall report.

Render one table per SSH target identical in shape to the USB tables,
plus a `Transport` row (`ssh <user>@<host>:<port>`) and a `Source` row
(`quad.toml` or `.env_boards`).

### 4. Combined report

The final user-facing message is the local host table (verbatim from
the CLI) followed by a `## Targets` section containing every USB and
SSH target table. If neither USB nor SSH yielded any targets, end with:

> No target devices detected. Plug in a USB board (`adb devices` should
> list it) or add a `[target.ssh]` block to `quad.toml`.

---

## 5. Deep-probe checklist (IQ-9075 bring-up findings)

When a shallow probe is ambiguous or the user is bringing up a new board, apply
these harder checks — each caught a real misdiagnosis during IQ-9075 work:

1. **GPU discovery — DRM / KGSL / OpenCL.** Don't stop at "an Adreno exists".
   Check the KGSL/DRM node, then whether OpenCL actually **enumerates** the
   device (`clinfo`). Distinguish Qualcomm GPU paths on Android vs Linux SoCs.
2. **QNN / QAIRT detection.** Probe QNN for *presence*, identify QAIRT, extract
   its version (`qnn-net-run --version 2>&1` — version may be on stderr), detect
   permission state, and look for QNN DSP skeletons. Verify QNN *deployment*,
   not just that a folder exists.
3. **SDK / runtime executability.** A tool being *present* is not the same as
   *executable*. Test the execute bit / that it actually runs.
4. **Transport revalidation.** SSH↔ADB availability flips after OS reflashes.
   Trust **session-local truth over historical truth** — re-probe every run.
5. **SoC identity cross-verification.** Reconcile internal codename vs
   commercial chipset name; flag identity conflicts instead of picking one.
   **On any board that may run a multi-SoC reference-distro BSP (QLI 2.0+
   confirmed case), `/proc/device-tree/compatible` can be a shared
   platform/family string, not a per-SKU identifier** — do not treat it as
   authoritative on its own. Always read `/sys/devices/soc0/machine` (fused
   silicon identity, independent of the flashed OS image) first; if it
   disagrees with the DT `compatible` string, `soc0` wins and the DT string
   is a platform-family label, not evidence of a different board. Confirmed
   case: an IQ-9075 (QCS9075) reflashed to QLI 2.0 reported `compatible =
   "qcom,lemans-evk qcom,qcs9100 qcom,sa8775p"` while `soc0/machine =
   QCS9075` was correct — the DT string covers every SoC sharing that
   reference platform, not just this one.

   > **Principle — verify before trusting, verify before declaring
   > (IQ-9075 reflash lesson).** A single signal at one path is a
   > sample, not a fact. Two failures compounded on this board from the
   > same root cause — trusting the first string read (DT `compatible`)
   > over the authoritative one (`soc0/machine`), and trusting the first
   > path checked (`/usr/lib/rfsa/adsp/`) over a board that files skels
   > elsewhere (`/usr/share/qcom/<variant>/.../dsp/cdsp/` on a multi-SoC
   > reference distro). Key rule: **the cheapest read is rarely the
   > authoritative one — cross-check the fused/firmware source (`soc0`)
   > and the broader search path before declaring identity or absence.**
   > This applies to detection output *and* to the probe code itself —
   > a live check on this same investigation found a new probe field
   > silently merging into the wrong section (missing trailing newline
   > after `tr`), which meant a diff check built on top of it never
   > actually ran. Don't trust a new probe field until you've confirmed
   > it parses into its own section on a real device. **Four failures,
   > not two** — a `head -10` cap on the skel search cut off the real
   > match before it was ever seen; **raising the cap to `head -30` was
   > tried next and still failed** (the real match sorted at line 31 of
   > 59 total hits — one line past the new cap), confirming that raising
   > a cap is not a fix, only a smaller version of the same bug; AND a
   > naive fix of hardcoding `*V73*` as the filter would have been
   > correct only for this one board and silently wrong on any other SoC
   > this same multi-SoC BSP might host next. The durable form removes
   > the shell-side cap (bound it generously, e.g. `head -200`, for
   > output-size safety only) and filters host-side by the
   > `soc0`-derived HTP version via `capabilities.py`'s registry, never
   > a literal version string or a truncation count. Full writeup:
   > `docs/debugging/SoC_Identity_DSP_Skel_False_Positive.md`.

6. **Non-standard runtime install detection.** Try the default path, then a
   manual `PYTHONPATH` location before declaring a runtime missing.
7. **Update-channel visibility.** Probe `opkg`, `dng`, `fwupdmgr` where present.
8. **Compute-capability assessment — report the exact state**, one of:
   GPU physically present · GPU driver usable · GPU backend usable ·
   OpenCL software-only · OpenCL vendor ICD · tool executable ·
   tool non-executable · runtime-discovery bug possibility.
9. **Clean-environment OpenCL validation** (no stray `LD_LIBRARY_PATH` skew).
10. **Executability state** for SNPE/QNN: installed / missing / present-but-not-executable.
11. **ONNX Runtime discovery caveat.** ORT may **not** see the GPU/NPU even when
    the hardware exists — `QNNExecutionProvider` can be absent from
    `get_available_providers()` on a Linux SoC board. Cross-link
    `/quad-qnn-runtime-debug` for the direct-execution fallback.

