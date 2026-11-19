# Modem Agent - Requirements Specification

| | |
|---|---|
| **Document** | Requirements Specification |
| **Version** | 0.1 (initial scoping) |
| **Status** | Draft for review |
| **Date** | 2026-05-26 |
| **Audience** | Modem firmware, AI/ML, systems engineering, certification |

---

## 1. Executive Summary

The **Modem Agent** is an on-device, AI-driven decision-making system embedded
within the UE modem stack (5G NR / LTE). It continuously observes radio link
telemetry (RLM, L1/L2/PDCP, modem diagnostics), runs context-aware predictive
models on a modem-resident inference engine (Hexagon NSP), and executes
proactive interventions that pre-empt link failures before legacy 3GPP
reactive thresholds would trigger.

**Headline target use case** (UC-1, this release): Max-Retransmission-Based RLF
Prevention - predict Radio Link Failure ~720 ms earlier than the current
fixed-counter mechanism, and adjust recovery timers / initiate remediation
before the user-visible outage begins.

**Architectural shift**: from reactive failure handling (wait for counter to
expire) to predictive, closed-loop radio resource optimization (anticipate
the failure trajectory and intervene early).

---

## 2. Problem Statement

3GPP procedures govern UE radio link behavior through static, conservatively
chosen thresholds and timers - e.g., `maxRetxThreshold`, `T310`, `T311`,
`N310`, `N311`, `t-PollRetransmit`, `t-Reordering`, BFI counters. These
defaults must work across an enormous variance of radio environments
(suburban macro, urban dense, indoor, vehicular, mmWave LOS/NLOS, NTN LEO/GEO,
RF-tuneaway during DSDA), and consequently:

* They trigger **too late** in benign environments where recovery could
  start sooner (the 720 ms RLF wait being a textbook case);
* They trigger **too early** in transiently degraded environments where
  the link would have recovered without intervention (causing unnecessary
  RRC re-establishment, throughput collapse, or HOF);
* They cannot adapt to **scenario-specific dynamics** - a HARQ NACK pattern
  that predicts RLF on a terrestrial cell may be entirely benign on an
  LEO NTN link with deterministic 12 ms one-way propagation delay.

Modern radio environments have higher variance than the 3GPP threshold
designers could account for. Machine-learned policies, conditioned on the
richer state available inside the UE modem stack, can make better decisions.

---

## 3. Goals and Non-Goals

### 3.1 Goals (Release 1)

| ID | Goal | Acceptance metric |
|---|---|---|
| G-1 | Reduce RLF rate vs legacy baseline | -30% to -50% in target field cohort |
| G-2 | Reduce average time-to-recovery from RLF onset to data resumption | -720 ms (UC-1 target) |
| G-3 | Provide a generalizable agent framework, not a single-feature point solution | UC-2 through UC-5 implementable as plugins |
| G-4 | Maintain 3GPP compliance | All GCF / PTCRB conformance suites pass with agent enabled |
| G-5 | Maintain operator interoperability | IOT pass rate unchanged across top-N MNOs |
| G-6 | Deterministic, isolated failure modes | Agent crash never crashes modem; standards fallback always reachable |

### 3.2 Non-Goals (Release 1)

* Replacing 3GPP procedures wholesale - the agent operates *within* the
  standardized envelope and adjusts only parameters the spec already permits.
* Modifying L1/PHY behavior (BWP switches, beamforming, frequency hopping)
  - L1 is read-only in v1. Future releases may extend.
* Cloud-based or RAN-side inference - latency budget forbids it; this is
  on-device only.
* Per-cell optimization - that is the RAN's job (xApp/rApp via O-RAN). The
  UE agent optimizes *its own* radio link only.
* Continuous online learning on-device - models are trained offline,
  deployed via signed firmware updates, and frozen at runtime in v1.

---

## 4. Use Cases

### 4.1 UC-1 - Max-Retx RLF Prevention (primary, this release)

| | |
|---|---|
| **Trigger** | HARQ NACK pattern over rolling window + Last_Valid_Status_PDU_Received_Time + scenario class (terrestrial / NTN / mmWave / RF-tuneaway) |
| **Inputs** | HARQ ACK/NACK history (last N TTIs), RLC retx counter, status PDU recency, RSRP/RSRQ trajectory, cell type, mobility state, beam context (FR2 only) |
| **Output** | P(RLF within H ms), confidence |
| **Action** | When confidence > threshold: pre-emptively shorten `t-PollRetransmit`, raise `pollByte` / `pollPDU`, reset RLC retx counter window, optionally trigger early measurement report |
| **Constraint** | Cannot exceed 3GPP timer ranges; must remain reversible if prediction proves wrong |
| **Expected gain** | ~720 ms saved vs waiting for `maxRetxThreshold` |

### 4.2 UC-2 - Beam Failure Pre-emption (FR2 / mmWave)

| | |
|---|---|
| **Trigger** | SSB / CSI-RS L1-RSRP trajectory + UE mobility (IMU-derived) + obstruction prediction |
| **Action** | Trigger Beam Failure Recovery (BFR) before `beamFailureInstanceMaxCount` expires, reduce L1-RSRP filter coefficient adaptively |
| **Expected gain** | Avoid 200-500 ms outage from late-detected beam failure |

### 4.3 UC-3 - Handover Anticipation

| | |
|---|---|
| **Trigger** | Source / target cell RSRP differential trajectory + UE velocity + cell config + neighbor cell beam topology |
| **Action** | Adjust A3 offset / hysteresis / `timeToTrigger` dynamically per UE; pre-prepare HO target |
| **Expected gain** | Reduce HOF rate (target -25%); smoother throughput at cell edge |

### 4.4 UC-4 - NTN HARQ Adaptation

| | |
|---|---|
| **Trigger** | Constellation parameters (LEO/MEO/GEO), one-way propagation delay, Doppler trajectory, ephemeris |
| **Action** | Adapt HARQ feedback timing; choose retx vs forego per round-trip budget; trigger pre-compensation for Doppler |
| **Expected gain** | Throughput +10-20% in LEO scenarios; reduced wasted retx |

### 4.5 UC-5 - DRX Adaptation (future, gated)

| | |
|---|---|
| **Trigger** | Application traffic class prediction (XR / VoIP / browsing / bulk / IoT), arrival pattern, latency budget |
| **Action** | Adapt DRX cycle length and on-duration within RRC-permitted range |
| **Expected gain** | Battery savings 10-30% with no QoS regression |

> **Scope note**: UC-1 is the deliverable for Release 1. UC-2 through UC-5 must
> be implementable as plugins under the same framework with no breaking changes
> to UC-1 - that is the architectural acceptance test for the agent core.

---

## 5. Functional Requirements

### 5.1 Telemetry ingestion (FR-1)

* **FR-1.1** - The agent SHALL ingest L1 telemetry: CQI, BLER, RSRP, RSRQ,
  SINR, SSB/CSI-RS measurements, beam reports.
* **FR-1.2** - The agent SHALL ingest L2 telemetry: HARQ ACK/NACK pattern
  per HARQ process, RLC retransmission counter, status PDU events,
  `Last_Valid_Status_PDU_Received_Time`, RLC SDU loss counters.
* **FR-1.3** - The agent SHALL ingest L2.5 (PDCP) telemetry: SN gaps,
  reordering events, ROHC compressor state.
* **FR-1.4** - The agent SHALL ingest L3 (RRC) state: timer values,
  measurement events, current configuration.
* **FR-1.5** - The agent SHALL ingest modem diagnostics: thermal state,
  PA condition, RF tuneaway state, multi-modem coexistence state.
* **FR-1.6** - Telemetry collection SHALL NOT impact modem real-time
  scheduling. Per-TTI telemetry must use lock-free data structures
  (ring buffers) and SHALL NOT take locks shared with the scheduler.

### 5.2 Feature engineering (FR-2)

* **FR-2.1** - Features SHALL be computed on a fast path within the
  feature engine; no Python, no allocations on the hot path.
* **FR-2.2** - The agent SHALL support sliding windows of configurable
  length (default: 10 / 100 / 1000 TTIs).
* **FR-2.3** - The agent SHALL handle missing values, sensor failures,
  and out-of-range values without crashing or producing NaN outputs.

### 5.3 Inference (FR-3)

* **FR-3.1** - Models SHALL be INT8 quantized and execute on Hexagon NSP.
* **FR-3.2** - The agent SHALL support multiple concurrent models (one
  per use case), each with independent priority.
* **FR-3.3** - Each inference call SHALL be guarded by a watchdog timer
  (default 200 us); a stall SHALL fall back to standards behavior.
* **FR-3.4** - The agent SHALL support pre-loaded models; no JIT compile
  or model load on the hot path.

### 5.4 Decision arbitration (FR-4)

* **FR-4.1** - Multiple models MAY produce conflicting recommendations.
  The arbiter SHALL resolve by priority + confidence + safety constraints.
* **FR-4.2** - Predictions below a per-use-case confidence threshold
  SHALL NOT be acted on; the agent SHALL defer to standards behavior.
* **FR-4.3** - The arbiter SHALL enforce hard safety bounds; it SHALL
  NOT issue an action that would violate 3GPP timer ranges or break
  conformance.

### 5.5 Action dispatch (FR-5)

* **FR-5.1** - Action space is bounded per use case (see use-case tables).
* **FR-5.2** - Every action SHALL be logged with: timestamp, feature
  vector hash, model version, confidence, action taken, reason code.
* **FR-5.3** - Actions SHALL be reversible where possible (timer
  adjustments, configuration deltas), and idempotent (re-applying the
  same action SHALL be a no-op).

### 5.6 Online adaptation (FR-6)

* **FR-6.1** - Models SHALL be trained offline; deployed models are
  frozen at runtime in v1.
* **FR-6.2** - Per-device personalization (e.g., learning the device's
  typical environments) is permitted IF it does not require online
  weight updates - acceptable mechanisms are feature normalization
  statistics, threshold calibration, or scenario classifier
  fine-tuning via signed delta.
* **FR-6.3** - Telemetry-back is permitted for offline analysis but
  SHALL NOT be a continuous-learning loop in v1.

### 5.7 Observability (FR-7)

* **FR-7.1** - The agent SHALL maintain an action audit trail (see FR-5.2)
  with at least 10,000-event circular buffer in non-volatile storage.
* **FR-7.2** - The agent SHALL emit aggregated metrics (prediction
  accuracy, action efficacy, false-positive rate) for OEM/operator
  dashboards via existing diag/QXDM channels, with PII scrubbed.
  Mock-mode dev builds SHALL emit the same metrics via DevRel's
  `profile_workload` shape, so the dashboard plumbing is exercised
  end-to-end on a developer laptop.
* **FR-7.3** - On modem crash, the action audit trail SHALL survive
  in the crash dump.

### 5.8 Configuration (FR-8)

* **FR-8.1** - Per-PLMN policy: each PLMN SHALL have an enable/disable
  flag and per-use-case configuration block.
* **FR-8.2** - Per-RAT policy: separate config for LTE, NR, NR-NTN.
* **FR-8.3** - Remote kill switch via existing OMA-DM / firmware update
  channel; activation MUST take effect within 60 seconds of receipt.

---

## 6. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Inference latency P99 per call | < 1 ms |
| NFR-2 | Total memory footprint (all models + working set) | < 10 MB |
| NFR-3 | Power overhead vs modem baseline | < 5% |
| NFR-4 | Performance regression vs legacy 3GPP behavior | 0 (must prove no regression in conformance + IOT before deployment) |
| NFR-5 | Determinism | Same input + state SHALL produce same output |
| NFR-6 | Crash isolation | Agent fault MUST NOT crash modem; supervisor restarts agent within 100 ms |
| NFR-7 | Cold start (first inference after boot) | < 100 ms |
| NFR-8 | Model OTA hot-swap | Without modem reboot where feasible |
| NFR-9 | ABI compatibility | Modem FW for 4+ generations of SoC |
| NFR-10 | Security - model integrity | Models cryptographically signed; chain of trust to FW root |
| NFR-11 | Privacy - no PII in off-device telemetry | Location, IMSI, IMEI hashes only; aggregated locally before send |

---

## 7. Hardware and Software Targets

* **SoC family**: Snapdragon X75 (entry) / X80 (mid) / X85 (top tier) / future X-series.
* **Inference engine**: Hexagon NSP (modem-NPU), DSP fallback for low-cost SKUs.
* **Modem stack**: MPSS (Modem Subsystem) firmware on Hexagon Q6 cores.
* **Inference runtime (vendor SDK layer)**: NWAIOS (modem-resident) or QNN-Hexagon
  variant. Final selection is an open question (see Q-B.1).
* **Model toolchain**: ONNX -> AIMET INT8 quantized -> DLC.
* **Build flow**: Standard Qualcomm modem FW build, with model bundle integrated
  into the FW image via the existing SLA (SoC Library Archive) mechanism.

### 7.1 DevRel as the development framework

The Modem Agent is **developed using DevRel** (Qualcomm Unified AI Developer
toolchain) - the same framework that hosts the AI Gateway, UNO Q, and
Snapdragon X classes of DevRel samples. DevRel provides the developer-facing
abstraction over the underlying vendor SDKs (NWAIOS / QNN / AIMET / QAIRT)
so the agent code targets a stable, mockable, testable interface rather
than directly linking against vendor binaries.

Concretely, DevRel supplies:

| DevRel capability | What it gives the modem agent program |
|---|---|
| **Adapter pattern** (`adapters/`) | New `ModemPlatformAdapter`, `ModemInferenceAdapter`, `ModemTelemetryAdapter`, `ModemActionAdapter` interfaces. Real implementations link against MPSS/NSP runtimes; mock implementations run on a developer laptop. |
| **Codegen templates** (`templates/modem/c_modular/`) | Scaffolds the per-use-case agent app structure with the same modular layout as `templates/gateway/c_modular/`. Emits `main.c`, `feature_engine.c`, `model_inferencing.c`, `arbiter.c`, `action_dispatcher.c`, `tensor_io.c`, `service.json`, `CMakeLists.txt`. |
| **MCP operations** | `convert_model` (ONNX->DLC for NSP), `profile_workload(platform="modem", runtime="npu")` returning a modem-NSP-shaped report, `generate_code` for the per-use-case scaffold. |
| **CLI** | `devrel modem build --target <triple>`, `devrel modem deploy --host <modem>`, `devrel modem profile --duration 30`. Mirrors the `devrel gwapps build/deploy/profile` flow. |
| **Doctor** | `devrel doctor --section modem` validates: NSP runtime ABI, model bundle signing chain, simulator availability, FW headers, cross-toolchain. |
| **Sample structure** | Each use case ships under `samples/modem_agent_uc<N>/` with `run.ps1`, `requirements.txt`, `tests/`, `README.md`, `ARCHITECTURE.md` - the devrelAgent convention. |

**Mock-first development.** Following the precedent set by the AI Gateway
samples (`samples/ai_gateway_classifier/`, `samples/stc_classifier/`),
the modem agent is developed mock-first on a Snapdragon X laptop. The
five-gate validation pattern from DevRel samples applies directly:

1. Pytest host suite (units, smoke, e2e on captured traces)
2. `devrel modem build --dry-run` (cross-compile cmake plan)
3. Mock deploy (`MockModemAdapter` runs install/start in-process)
4. `profile_workload(platform="modem")` returns shaped report
5. Trace-replay validation (real captured RLM/HARQ traces drive the
   agent in-process; predictions checked against actual outcomes)

This is the productivity multiplier vs traditional modem dev cycles -
no FW build/sign/flash/lab-rack iteration needed for the algorithmic
work. Real-modem validation flips on by setting `MODEM_HOST=<device>`,
the same env-var pattern DevRel uses for `GATEWAY_HOST`.

**Architectural posture.** DevRel is the *development* framework, not a
runtime dependency on the modem. The shipped agent binary links the
vendor runtime directly (libnwaios or QNN-Hexagon). DevRel's adapters are
a developer-time abstraction that the build system collapses to the
real vendor calls in production builds. The agent is a DevRel sample in
the same sense `stc_classifier` is - a deliverable artifact developed
against DevRel's templates, tools, and validation gates.

---

## 8. Compliance and Certification

* **3GPP** TS 36.* (LTE), 38.* (NR) - the agent SHALL operate within the
  envelope of these specifications. Conformance test cases (TS 36.523 /
  38.523) SHALL pass with the agent enabled.
* **GCF / PTCRB** certification SHALL pass at PTCRB lab and major MNO IOT.
* **FCC / ETSI / TELEC / PTCRB** RF certification SHALL be unaffected -
  the agent does not modify L1 emissions in v1.
* **Operator approval** - top-N MNOs may require explicit IOT testing
  before the agent is enabled on their PLMN. The kill-switch (FR-8.3)
  exists in part to enable this.
* **Regulatory** - if AI-driven RAN behavior becomes subject to specific
  telecom regulation (EU AI Act sector annexes, etc.), the agent SHALL
  support audit and explainability requirements via the action log (FR-7.1).

---

## 9. Privacy and Security

* **No PII** in off-device telemetry. Identifiers (IMSI, IMEI) are not
  transmitted; cell IDs and location are aggregated/anonymized locally
  before any off-device send.
* **Models signed** - model bundles cryptographically signed; chain of
  trust to FW root.
* **Action audit log encrypted at rest** in modem persistent storage.
* **Telemetry channel** uses existing diag infrastructure (QXDM); no new
  off-device channel introduced by the agent.

---

## 10. Acceptance Criteria

The Release 1 agent SHALL be considered ready for field deployment when:

1. UC-1 (Max-Retx RLF Prevention) achieves the G-2 latency target
   (-720 ms time-to-recovery) on a defined regression trace suite.
2. UC-1 achieves the G-1 RLF reduction target (-30% to -50%) in
   shadow-mode field validation across at least 3 MNO networks.
3. All applicable 3GPP conformance, GCF, and PTCRB suites pass with
   the agent enabled (G-4).
4. IOT regression vs the same FW build with the agent disabled shows
   zero breakage in the top-N MNO networks (G-5).
5. The kill switch demonstrably disables the agent in < 60 seconds (FR-8.3).
6. The agent framework can host UC-2 through UC-5 as plugins without
   breaking changes to the agent core (G-3).
7. **DevRel validation gates pass** (the same pattern used by every DevRel
   sample): host pytest, `devrel modem build --dry-run`, `devrel modem
   deploy` mock, `profile_workload` shape, trace-replay regression -
   all green in CI before any FW image promotion.

---

## 11. References

* 3GPP TS 36.331 (LTE RRC), 38.331 (NR RRC)
* 3GPP TS 36.322 / 38.322 (RLC)
* 3GPP TS 36.323 / 38.323 (PDCP)
* 3GPP TS 38.321 (NR MAC) - HARQ
* 3GPP TR 22.876 (5G AI/ML use cases) - background
* 3GPP TR 38.843 (NR AI/ML for air interface) - L1 ML, complementary
* O-RAN.WG2.AIML-Architecture - RAN-side AI architecture, complementary
* ETSI ENI - Experiential Networked Intelligence
