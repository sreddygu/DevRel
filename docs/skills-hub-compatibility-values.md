# Skills Hub — Compatibility Reference

> **Generated file — do not edit by hand.** Produced from the live QSC devkit
> catalog by `packages/community-extension/scripts/generate-skills-compatibility-reference.ts`.
> Regenerate with `pnpm generate-skills-compat-reference` from `packages/community-extension`.

These are the exact values a skill manifest's `compatibility` block may use. See the
[Maintainer Guide](skills-hub-maintainer-guide.md#compatibility) for how they are applied.

- **`compatibility.devkits`** — any devkit id below.
- **`compatibility.hostOs`** — `"linux"`, `"windows"`, `"macos"`.
- **`compatibility.targetOs[]`** — `os` + `variant` from a devkit's Target OS table;
  `minVersion`/`maxVersion` from that row's version list.
- **`compatibility.sdks[]`** — `id` from a devkit's SDKs table; `minVersion`/`maxVersion`
  from that row's version list.

## Devkit ids

- `qcs6490-rb3gen2-vision-kit` — Dragonwing RB3 Gen 2 Vision Kit
- `qcs6490-rb3gen2-core-kit` — Dragonwing RB3 Gen 2 Core Kit
- `qcs6490-rb3gen2-vision-lite-kit` — Dragonwing RB3 Gen 2 Lite Vision Kit
- `qcs6490-rubikpi3-kit` — RUBIK Pi 3 Development Board
- `qcs9075-iq-9075-evk` — Dragonwing IQ-9075 EVK
- `qcs8275-iq-8275-evk-pro` — Dragonwing IQ-8275 EVK

## Per-devkit target OS and SDKs

### `qcs6490-rb3gen2-vision-kit` — Dragonwing RB3 Gen 2 Vision Kit

**Target OS** (`compatibility.targetOs[]` → `os` / `variant`; versions oldest → newest):

| `os` | `variant` | versions |
|---|---|---|
| `ubuntu` | `ubuntu-server` | `24.04-x08`, `24.04-x11`, `24.04-x12` |
| `ubuntu` | `ubuntu-desktop` | `24.04-x08`, `24.04-x11`, `24.04-x12` |
| `qualcomm_linux` | `qualcomm-linux-proprietary` | `qli-1.6`, `qli-1.7`, `qli-1.8`, `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |
| `qualcomm_linux` | `qualcomm-linux-open-source` | `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |

**SDKs** (`compatibility.sdks[]` → `id`; versions oldest → newest):

| `id` | versions |
|---|---|
| `QIMPSDK CORE` | `2.0.1`, `2.1.1`, `2.2.1`, `2.3.0` |
| `QIMPSDK VISION` | `2.0.1`, `2.1.1`, `2.2.1`, `2.3.0` |
| `QIMPSDK ARMv8a` | `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |

### `qcs6490-rb3gen2-core-kit` — Dragonwing RB3 Gen 2 Core Kit

**Target OS** (`compatibility.targetOs[]` → `os` / `variant`; versions oldest → newest):

| `os` | `variant` | versions |
|---|---|---|
| `ubuntu` | `ubuntu-server` | `24.04-x08`, `24.04-x11`, `24.04-x12` |
| `ubuntu` | `ubuntu-desktop` | `24.04-x08`, `24.04-x11`, `24.04-x12` |
| `qualcomm_linux` | `qualcomm-linux-proprietary` | `qli-1.6`, `qli-1.7`, `qli-1.8`, `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |
| `qualcomm_linux` | `qualcomm-linux-open-source` | `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |

**SDKs** (`compatibility.sdks[]` → `id`; versions oldest → newest):

| `id` | versions |
|---|---|
| `QIMPSDK CORE` | `2.0.1`, `2.1.1`, `2.2.1`, `2.3.0` |
| `QIMPSDK VISION` | `2.0.1`, `2.1.1`, `2.2.1`, `2.3.0` |
| `QIMPSDK ARMv8a` | `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |

### `qcs6490-rb3gen2-vision-lite-kit` — Dragonwing RB3 Gen 2 Lite Vision Kit

**Target OS** (`compatibility.targetOs[]` → `os` / `variant`; versions oldest → newest):

| `os` | `variant` | versions |
|---|---|---|
| `ubuntu` | `ubuntu-server` | `24.04-x08`, `24.04-x11`, `24.04-x12` |
| `ubuntu` | `ubuntu-desktop` | `24.04-x08`, `24.04-x11`, `24.04-x12` |
| `qualcomm_linux` | `qualcomm-linux-proprietary` | `qli-1.6`, `qli-1.7`, `qli-1.8`, `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |
| `qualcomm_linux` | `qualcomm-linux-open-source` | `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |

**SDKs** (`compatibility.sdks[]` → `id`; versions oldest → newest):

| `id` | versions |
|---|---|
| `QIMPSDK CORE` | `2.0.1`, `2.1.1`, `2.2.1`, `2.3.0` |
| `QIMPSDK VISION` | `2.0.1`, `2.1.1`, `2.2.1`, `2.3.0` |
| `QIMPSDK ARMv8a` | `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |

### `qcs6490-rubikpi3-kit` — RUBIK Pi 3 Development Board

**Target OS** (`compatibility.targetOs[]` → `os` / `variant`; versions oldest → newest):

| `os` | `variant` | versions |
|---|---|---|
| `ubuntu` | `ubuntu-server` | `24.04-x01`, `24.04-x03` |
| `ubuntu` | `ubuntu-desktop` | `24.04-x01`, `24.04-x03` |
| `qualcomm_linux` | `qualcomm-linux-proprietary` | `qli-1.0`, `qli-1.1`, `qli-1.1.1`, `qli-1.2` |

**SDKs** (`compatibility.sdks[]` → `id`; versions oldest → newest):

| `id` | versions |
|---|---|
| `QIMPSDK CORE` | `2.0.1`, `2.1.1`, `2.2.1`, `2.3.0` |
| `QIMPSDK VISION` | `2.0.1`, `2.1.1`, `2.2.1`, `2.3.0` |
| `QIMPSDK ARMv8a` | `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |

### `qcs9075-iq-9075-evk` — Dragonwing IQ-9075 EVK

**Target OS** (`compatibility.targetOs[]` → `os` / `variant`; versions oldest → newest):

| `os` | `variant` | versions |
|---|---|---|
| `ubuntu` | `ubuntu-server` | `24.04-x08`, `24.04-x11`, `24.04-x12` |
| `ubuntu` | `ubuntu-desktop` | `24.04-x08`, `24.04-x11`, `24.04-x12` |
| `qualcomm_linux` | `qualcomm-linux-proprietary` | `qli-1.6`, `qli-1.7`, `qli-1.8`, `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |
| `qualcomm_linux` | `qualcomm-linux-open-source` | `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |

**SDKs** (`compatibility.sdks[]` → `id`; versions oldest → newest):

| `id` | versions |
|---|---|
| `QIMPSDK EVK` | `2.1.1`, `2.2.1`, `2.3.0` |
| `QIMPSDK ARMv8a` | `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |

### `qcs8275-iq-8275-evk-pro` — Dragonwing IQ-8275 EVK

**Target OS** (`compatibility.targetOs[]` → `os` / `variant`; versions oldest → newest):

| `os` | `variant` | versions |
|---|---|---|
| `ubuntu` | `ubuntu-server` | `24.04-x08`, `24.04-x11`, `24.04-x12` |
| `ubuntu` | `ubuntu-desktop` | `24.04-x08`, `24.04-x11`, `24.04-x12` |
| `qualcomm_linux` | `qualcomm-linux-proprietary` | `qli-1.7`, `qli-1.8`, `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |
| `qualcomm_linux` | `qualcomm-linux-open-source` | `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |

**SDKs** (`compatibility.sdks[]` → `id`; versions oldest → newest):

| `id` | versions |
|---|---|
| `QIMPSDK EVK` | `2.2.1`, `2.3.0` |
| `QIMPSDK ARMv8a` | `qli-2.0-rc2`, `qli-2.0-rc3`, `qli-2.0` |
