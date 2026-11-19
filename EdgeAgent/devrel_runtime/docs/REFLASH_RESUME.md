# IQ Reflash — Resume Checkpoint (saved 2026-07-23)

> Pick this up next session. Everything below is verified state, not plan.
> Related: `INSTALL_ISSUES_REPORT.md` (Issues 23/24), `docs/IQ8275_REFLASH.md`,
> `docs/IQ9075_REFLASH.md`, `backups/iq9_backup_20260723.README.md`.

## The one-line status
NPU inference on both IQ boards is blocked by the **QAIRT version wall** (Issue
24): the DevRel server compiles `.bin` at **2.47**, both boards run **2.43** on-device,
and a 2.47 binary won't load on a 2.43 runtime (`err 5000` / "newer context binary
on old SDK"). **The fix is a reflash to a QLI image carrying QAIRT ≥2.45.** All
software-side workarounds are exhausted and proven dead ends (see below).

## Fleet state (verified 2026-07-23)
| Board | IP | SSH key | SoC / HTP | On-device QAIRT | Reachable now |
|---|---|---|---|---|---|
| X-Elite host | (local) | — | v73 / SDK **2.47.1** | host, not a target | ✅ |
| IQ8 (QCS8275) | 10.92.210.214 | `~/.ssh/iq8_nopass` | qcs8275 / **v75** | **2.43.0** | ❌ offline (port 22 timeout) |
| IQ9 (QCS9075) | 192.168.29.185 | `~/.ssh/iq9_nopass` | qcs9075 / **v73** | **2.43.0** | ✅ (on 192.168.29.x subnet) |

- DevRel MCP server: `http://10.227.21.202:8000/mcp`, bearer `DevRel_MCP_TOKEN` (in `.env`),
  server version **DevRel 3.4.2**. `connect-test sse-http` OK (~900 ms).
- Run CLI via `./.venv/Scripts/devrel-agent.exe` (not on PATH).

## What was COMPLETED this session
1. ✅ IQ9 pre-reflash **state snapshot** → recorded in report (kernel 6.8.0-1080-qcom,
   Ubuntu 24.04.4, QAIRT 2.43.0, HTP skels v68+v73+v75, `/dev/fastrpc-cdsp`).
2. ✅ IQ9 **backup** → `backups/iq9_backup_20260723.tar.gz` (62 MB, 2319 entries,
   sha256-verified matching board). Manifest in `.README.md` alongside it.
3. ✅ Proved the **on-board 2.46 SDK cannot shim around the wall** (see report,
   IQ9 section). Three host/skel combos all fail; a ≥2.45 skel that also knows
   SoC 77 (QCS9075) only ships in the QLI image. **Confirms reflash is the real fix.**
4. ✅ Cleaned temp files off IQ9.

## The reflash BLOCKER (why I can't finish it)
`docs/IQ9075_REFLASH.md` happy path = 4 steps. I can do 2, 3, 4. **Step 1 (flash
via Qualcomm_Launcher GUI over USB-EDL) is physical + GUI + QPM3-gated** — an agent
cannot: put the board in 9008/EDL mode (hold download button + apply power), click
the Windows Launcher GUI, or download the QPM3-gated tools/image (VPN + Qualcomm login).

**Gated prerequisites (need YOU / portal access):**
- QLI image for the board (QAIRT ≥2.45) — QCS9075 build for IQ9, **QCS8275 build for IQ8** (do NOT cross them)
- Qualcomm_Launcher 2.1.0, QDL 2.3.9.2, CDM ARM64 driver v2.12.36.20 — all from QPM3
- IQ8 EVK download-button / EDL-entry location (open item in `IQ8275_REFLASH.md`)

Note: `IQ9075_REFLASH.md` lists board QAIRT as "validated 2.47.0" but the real
board today is **2.43.0** — so flashing that QLI image should land ≥2.45 and kill
the wall.

## RESUME HERE — next actions
When you have the Launcher + QLI image and can put a board in EDL mode, ping me. I will:
1. (pre-flash, IQ8 only) snapshot + back up IQ8 like IQ9 — **needs IQ8 powered on** (offline now).
2. Hand you the copy-paste EDL-entry + Launcher click sequence (still to be written).
3. (post-flash) SSH in and auto-verify: `qnn-net-run --version` ≥2.45, `libSnpeHtpV{73|75}Skel.so`, `/dev/fastrpc-cdsp`.
4. Restore the backup tarball to the reflashed board.
5. Re-run `/devrel-detect`, then compile MobileNetV2 for the board's HTP arch → push → `qnn-net-run` on NPU (the Issue 24 run). Capture latency/FPS.
6. Update `INSTALL_ISSUES_REPORT.md` Issue 24 → RESOLVED with the new version + NPU numbers.

## Deferred / not client-fixable
- **Issue 25** (AI Hub `force` compile rejects raw .onnx) — server-side, not fixable in this checkout.
- **Issue 23** (host NPU crash 0xC0000409) — root cause unconfirmed; needs a known-good `.bin`, which needs a build-capable (≥64 GB, non-arm64) DevRel server. Same server unblocks the Falcon bundle (`FALCON_NPU_BUNDLE_HANDOFF.md`).
