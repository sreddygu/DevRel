# IQ-9075 Reflashing — References & Dependencies

> Everything needed to (re)flash and provision the **Dragonwing IQ-9075 EVK
> (QCS9075)**. The IQ-9075 bring-up retrospective flagged the absence of a
> single dependency + reference list; this is it.

_Author: Pavan R_

---

## Required host tooling

| # | Tool | Version | Purpose |
|---|------|---------|---------|
| 1 | Qualcomm_Launcher | **2.1.0** (Windows-AnyCPU) | GUI flashing tool |
| 2 | QAIRT | **v2.48.40.260702** (board-native validated at 2.47.0) | On-device runtime + host converter |
| 3 | CDM Universal Driver for ARM64 | **v2.12.36.20** (WHQL-certified) | USB device enumeration on the host |
| 4 | QDL | **2.3.9.2** (Win ARM64) | Low-level download (EDL/9008) |
| 5 | BIG-IP Edge Client | latest | VPN for QGenie/Claude access — see `VPN_QGENIE.md` |

> Version-pin these. Mixing QAIRT versions across host and board caused
> conversion/compatibility gaps during bring-up (retrospective IQ9-21): a model
> converted with a newer host QAIRT than the board's runtime may fail to load.
> The safe rule: **convert with a QAIRT ≤ the board's on-device QAIRT**, or
> convert through the remote MCP server / AI Hub Models which targets the board's HTP
> arch (v73) directly.

## Board target facts (validated)

| Fact | Value |
|------|-------|
| SoC | QCS9075 (Dragonwing IQ-9075) |
| BSP | Qualcomm Linux QLI 2.0 |
| Kernel | 6.18.30 |
| QAIRT (on-device) | 2.47.0 |
| HTP / Hexagon arch | **v73** (`libQnnHtp.so`) |
| GPU | Adreno 663 (QNN GPU backend blocked — see `IQ9075_GPU_STATUS.md`) |
| FastRPC | `/dev/fastrpc-cdsp` present (DSP acceleration active) |

## Reference links

- Qualcomm Dragonwing IQ-9075 product & EVK hardware documentation (Qualcomm
  developer portal / Qualcomm Package Manager 3).
- Qualcomm Linux (QLI) 2.0 flashing guide.
- QAIRT / QNN SDK documentation for the on-device runtime and `qnn-net-run`.
- Qualcomm AI Hub Models — compile an ONNX model to an HTP `.bin` targeting the
  `QCS9075` / HTP v73 device class.

> These are gated behind Qualcomm developer login + VPN. Fill exact URLs from
> your Qualcomm Package Manager 3 catalog for the versions pinned above.

## Reflash → provision → run (the happy path)

1. Flash QLI 2.0 with Qualcomm_Launcher 2.1.0 (see `IQ9075_SOPs.md` §4).
2. Boot and verify (SOP §3): kernel 6.18.30, `libQnnHtp.so`, `/dev/fastrpc-cdsp`.
3. From the host, configure a DevRel target for the board:
   ```sh
   devrel-agent unoq configure <board-ip> --board iq9075
   # writes a devrel.toml [target] stanza: soc=qcs9075, hexagon=v73, runtime=htp
   ```
4. Compile a model for HTP v73 via AI Hub Models or the remote MCP server, push the
   `.bin` to the board, and run `qnn-net-run` (NPU) — see `IQ9075_SOPs.md`.
