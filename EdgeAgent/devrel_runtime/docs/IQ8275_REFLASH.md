# IQ8 (8275 Pro SKU EVK) Reflashing — References & Dependencies

> Everything needed to (re)flash and provision the **Qualcomm IQ8 8275 Pro SKU
> EVK (SoC QCS8275)** so its on-device QAIRT runtime is new enough (**≥ 2.45**)
> to load HTP context binaries compiled by the DevRel server / AI Hub Models.
>
> **Why reflash:** the board shipped with **QAIRT 2.43.0**, which is below the
> 2.45 compile floor. A `.bin` compiled by the host/server QAIRT 2.47 fails to
> load on-device with `Using newer context binary on old SDK` (err 5000 /
> 0x1388). See `INSTALL_ISSUES_REPORT.md` Issue 24. Reflashing to a QLI image
> carrying QAIRT ≥2.45 is the documented fix for on-device NPU inference.
>
> _Adapted from `IQ9075_REFLASH.md` (author: Pavan R). **The IQ8 is a DIFFERENT
> SoC (QCS8275, HTP v75) from the IQ-9075 (QCS9075, HTP v73)** — image and HTP
> arch differ. Treat the IQ9075 doc as a reference, not a drop-in recipe._

---

## ⚠️ Before you start — read this

- Reflashing is **destructive** (wipes the board) and **brick-risky** if
  interrupted. **Do not disconnect power mid-flash.**
- This is a **host-side GUI + USB-EDL** procedure. It cannot be driven over SSH
  from an agent — a human runs it at the machine physically connected to the EVK.
- **Back up** anything on the board you need first (over SSH, while it still
  boots): `~/` artifacts, any custom configs.
- The IQ8's current state (verified 2026-07-22, keep for rollback reference):

  | Fact | Value |
  |------|-------|
  | Board | Qualcomm IQ8 8275 Pro SKU EVK |
  | SoC | QCS8275 (soc_id 675) |
  | CPU | 8× Cortex-A55 |
  | RAM | 11 GB |
  | OS | Ubuntu 24.04.4 LTS, kernel 6.8.0-1078-qcom (aarch64) |
  | QAIRT (on-device) | **2.43.0** ← the reason for reflash |
  | HTP / Hexagon arch | **v75** (`libSnpeHtpV75Skel.so` present) |
  | Runtimes | `qnn-net-run`, `snpe-net-run` at `/usr/bin` |
  | SSH | `ubuntu@10.92.210.214`, key `~/.ssh/iq8_nopass` (also pw `qualcomm123`) |
  | Serial console | FTDI FT4232H → AP console (was COM11); SAIL on adjacent port |

---

## Required host tooling

Mirrors the IQ9075 list; **version-pin** everything. `⚠️ CONFIRM` = value taken
from the IQ9075 doc that must be verified against the QCS8275 catalog before use.

| # | Tool | Version | Purpose |
|---|------|---------|---------|
| 1 | Qualcomm_Launcher | 2.1.0 (Windows-AnyCPU) | GUI flashing tool |
| 2 | **QLI board image for QCS8275** | **QAIRT ≥ 2.45** ⚠️ CONFIRM | the OS/BSP image to flash — must be the **QCS8275 / IQ8** build, NOT the QCS9075 image |
| 3 | QAIRT (host converter) | match/≤ the flashed board runtime | host-side model conversion |
| 4 | CDM Universal Driver for ARM64 | v2.12.36.20 (WHQL) | USB device enumeration on the host |
| 5 | QDL | 2.3.9.2 (Win ARM64) | low-level download (EDL/9008) |
| 6 | BIG-IP Edge Client | latest | VPN for Qualcomm portal / QGenie access |

> **Sources are gated** behind Qualcomm developer login + VPN (Qualcomm Package
> Manager 3 catalog). Exact download URLs for the **QCS8275** image + tooling
> versions must be filled from QPM3 — I could not resolve these from the repo.
> **Action:** locate the IQ8/QCS8275 QLI image in QPM3 and pin its QAIRT version.

---

## The version rule (why this whole exercise exists)

From `IQ9075_REFLASH.md`, applies identically to the IQ8:

> A model converted with a **newer host QAIRT than the board's runtime may fail
> to load.** Safe rule: **convert with a QAIRT ≤ the board's on-device QAIRT**,
> or convert through the remote MCP server / **AI Hub Models targeting the
> board's HTP arch** (for the IQ8: **v75 / QCS8275**) directly.

**Non-reflash alternative worth trying first:** compiling MobileNetV2 via **AI
Hub Models targeting the QCS8275 (HTP v75)** device class may yield a `.bin` the
board's 2.43 runtime can load, avoiding a reflash entirely. If that works, you
may not need to flash at all. (Untested this session — flagged as the cheaper
path.)

---

## Reflash → provision → run (the happy path)

1. **Enter EDL / download mode.** Power the board off. Hold the board's
   **download button** while applying 12V power (per the EVK hardware guide).
   Do **not** hot-plug USB before power.
2. Confirm the host enumerates the board as **Qualcomm QDL 9008 / HS-USB**
   (Device Manager). If not, (re)install the CDM ARM64 driver (#4).
3. **Flash** the QCS8275 QLI image (QAIRT ≥2.45) with Qualcomm_Launcher 2.1.0.
   **Do not disconnect power mid-flash.**
4. Power-cycle. Boot and verify over serial/SSH:
   - `uname -r` (new kernel), `cat /etc/os-release`
   - `qnn-net-run --version` → **must now report ≥ 2.45**
   - `ls /usr/lib/rfsa/adsp/libSnpeHtpV75Skel.so` and `/dev/fastrpc-cdsp` present
5. **Re-provision the DevRel target** (host, from the devrelAgent checkout). The
   IP/key are unchanged, but re-verify the stanza:
   ```sh
   devrel-agent unoq configure 10.92.210.214 --board iq8275
   # or the existing devrel.toml [target.iq-8275] (soc=qcs8275, hexagon=v75)
   ```
   Note: `.env_boards` already has `IQ8_HOST/USER/KEY`; `devrel.toml` already has
   `[target.iq-8275]`. Just re-run `/devrel-detect` to confirm.
6. **Compile for HTP v75** via AI Hub Models or the remote MCP server, push the
   `.bin`, and run `qnn-net-run` on the IQ8 NPU. This is the step that was
   blocked by Issue 24 pre-reflash.

---

## Post-reflash verification checklist

- [ ] `qnn-net-run --version` ≥ 2.45 (the whole point)
- [ ] Board boots to Ubuntu, SSH `ubuntu@10.92.210.214` works with `iq8_nopass`
- [ ] `libSnpeHtpV75Skel.so` + `/dev/fastrpc-cdsp` present
- [ ] `/devrel-detect` shows `iq-8275` ✅ with resolved runtime version
- [ ] A QCS8275/v75-compiled `.bin` loads (no `err 5000`) and `qnn-net-run`
      produces output `.raw` — capture NPU latency/FPS
- [ ] Update `INSTALL_ISSUES_REPORT.md` Issue 24 → RESOLVED with the new version

---

## Open items I could not resolve (need your input / portal access)

1. **Exact QCS8275 QLI image + its QAIRT version** — from Qualcomm Package
   Manager 3 (gated). Must be the IQ8/QCS8275 build, not QCS9075.
2. **IQ8 EVK download-button location / EDL entry** — from the IQ8 8275 Pro EVK
   hardware guide (the IQ9075 SOP button step is a reference only).
3. Whether the **AI Hub Models QCS8275 (v75) compile** path avoids the reflash
   altogether — cheaper to try first (see alternative above).
