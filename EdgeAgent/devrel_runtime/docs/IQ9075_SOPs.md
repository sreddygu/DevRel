# IQ-9075 Standard Operating Procedures (SOPs)

> Dragonwing **IQ-9075 EVK (QCS9075)** — the operating procedures the IQ-9075
> bring-up retrospective flagged as missing. This is the canonical sequence for
> getting a board from powered-off to running DevRel inference.

_Author: Pavan R_

---

## 0. Prerequisites (host laptop)

| Item | Needed for |
|------|-----------|
| Qualcomm_Launcher 2.1.0 (Windows-AnyCPU) | Flashing |
| QAIRT v2.48.40.260702 (or the board-native 2.47) | On-device runtime |
| CDM v2.12.36.20 Universal Driver for ARM64 (WHQL) | USB device enumeration |
| QDL 2.3.9.2 (Win ARM64) | Low-level download |
| BIG-IP Edge Client VPN | QGenie / Claude model access (see `VPN_QGENIE.md`) |

Full dependency list + links: **`IQ9075_REFLASH.md`**.

---

## 1. Power-On Sequence SOP

1. Connect the **12V DC** barrel jack to the EVK. Do **not** hot-plug USB before power.
2. Verify the **power LED** is solid.
3. Connect the **USB-C debug/console** cable from the board to the host.
4. Connect the **USB (device/QDL) port** only when flashing (see §4).

## 2. Host-Connection SOP

1. Attach the USB-C console cable.
2. Confirm the serial device appears:
   - Windows: a new **COM port** in Device Manager (needs the CDM ARM64 driver).
   - Linux/macOS: `/dev/ttyUSB*` or `/dev/tty.usbserial-*`.
3. Open a serial console at **115200 8N1**.
4. For network/SSH, bring up the board's Ethernet or USB-RNDIS interface and
   note the board IP. DevRel reaches the board over SSH — see `devrel-agent unoq`
   (works for any Linux-SSH board, IQ-9075 included).
   - **SSH is the primary transport for the IQ-9075 (~95% of workflows) —
     it is Step 1 before running inference.** Store the board IP/user/
     password locally in `.env_boards` (copy from `.env_boards.example` at
     the repo root; gitignored, never committed).
   - Windows' built-in OpenSSH client fails with `Permission denied
     (publickey,password)` against this board's interactive password
     prompt — use PuTTY's `plink.exe` instead:
     ```
     "C:\Program Files\PuTTY\plink.exe" -ssh -pw oelinux123 -hostkey "SHA256:<fingerprint>" root@<board-ip> "<command>"
     ```
     The host key fingerprint changes on every reflash; plink prints the new
     one on first connect — re-accept and update `.env_boards` then.
   - ADB/USB is a **secondary, bootstrap-only** transport — only needed
     before WiFi/SSH is up on a freshly flashed board, and requires
     re-running `touch /etc/usb-debugging-enabled && systemctl start
     android-tools-adbd.service` on-device after every reflash (wiped along
     with `/etc`). Full RCA and rationale: `docs/debugging/`.

## 3. Boot SOP

1. Power on; watch the serial console for the bootloader banner.
2. A healthy boot reaches the **QLI 2.0** login prompt (kernel 6.18.30).
3. Log in (default per your provisioning).
4. Sanity checks:
   ```sh
   uname -a                     # expect 6.18.30
   cat /etc/os-release          # QLI 2.0
   ls /usr/lib/libQnnHtp.so     # HTP backend present
   ls /dev/fastrpc-*            # FastRPC (DSP) node present
   qnn-net-run --version        # QAIRT 2.47 on-device runtime
   ```

## 4. Flashing SOP

> Flashing is a **manual, host-driven** procedure. DevRel does not automate it.

1. Put the board in **download / EDL mode** (hold the board's download button
   while applying power, per the EVK hardware guide).
2. Connect the **USB QDL port** to the host.
3. Confirm the device enumerates (Qualcomm QDL 9008 / HS-USB).
4. Launch **Qualcomm_Launcher 2.1.0**, select the QLI 2.0 build image, and flash.
   - QDL 2.3.9.2 is the underlying download tool if launching from CLI.
5. Wait for the flash to complete; do **not** disconnect power mid-flash.
6. Power-cycle and follow the **Boot SOP** (§3) to verify QLI 2.0 / kernel 6.18.30.

Reference links + exact dependency versions: **`IQ9075_REFLASH.md`**.

---

## Verified compute paths on this board

| Path | Status | Notes |
|------|--------|-------|
| CPU (onnxruntime) | ✅ Working | Use onnxruntime 1.27.0 — 1.22.1 is ~2.4× slower. |
| NPU (HTP v73) | ✅ Working | `qnn-net-run --retrieve_context --backend libQnnHtp.so` + AI Hub Models `.bin`. |
| GPU (Adreno 663, QNN) | ✗ Blocked | Adreno OpenCL driver symbol gap — see `IQ9075_GPU_STATUS.md`. |

See the retrospective results (`docs/IQ9075 Retrospectibe Results v2.pdf` in the
workspace) for measured latencies.



### IQ9075 Reference Links: 

1. https://dragonwingdocs.qualcomm.com/Linux/devices/iq9075-evk/update-software/flash-using-qualcomm-launcher
2. https://dragonwingdocs.qualcomm.com/Linux/devices/iq9075-evk/set-up-the-device

Kindly refer above links to finish re-flashing IQ9075 with latest BSP using Qualcomm Launcher and configured login (with Wi-Fi connection). The Setup will be complete. 
- Use QLI 2.0 (without rc suffix from Qualcomm Linux Proprietary) as it is the General Availability (GA) (full, validated, and officially released) build. This has also been the build tested with DevRel.
- When facing USB driver issues (like COM Port not showing up or being detected, use reference link (2)'s secions - setup debug UART / Windows: If the UART port isn’t detected, install the FTDI driver section for fixes).

### Notes: 

1) If using QUALCOMM Corporate Wi-Fi Network
IP Addr: ssh root@QCOM_IP_EXAMPLE
QCOM_IP_EXAMPLE: 10.73.92.162

2) If using some other Wi-Fi Network
IP Addr: ssh root@EXT_IP_EXAMPLE
EXT_IP_EXAMPLE: 192.168.15.73 

p.s.: If the password you set during login doesn't work use oelinux123 (this will work).
