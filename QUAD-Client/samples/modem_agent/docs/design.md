# Modem Agent - Design Document

| | |
|---|---|
| **Document** | Architecture & Design |
| **Version** | 0.1 (initial scoping) |
| **Status** | Draft for review |
| **Date** | 2026-05-26 |
| **Companion** | requirements.md, open_questions.md |

---

## 1. Architecture Overview

### 1.1 QUAD as the development framework

The agent is built as a QUAD sample - same lifecycle as
`samples/stc_classifier/` and `samples/ai_gateway_classifier/`. QUAD
sits between the agent code and the vendor SDKs, providing adapter
interfaces, codegen scaffolds, profiling, and validation gates that
all run mock-first on a developer laptop and flip to real hardware
behind environment variables.

```
                     +----------------------------+
                     |      AGENT SOURCE CODE     |
                     |  (this repo, per use case) |
                     +-------------+--------------+
                                   |
                                   v
   +-------------------------------+--------------------------------+
   |                       QUAD FRAMEWORK                           |
   |                                                                |
   |   adapters/   templates/   build/    profiler/   device/       |
   |   modem/      modem/       modem.py  modem.py    modem.py      |
   |                                                                |
   |   ModemPlatformAdapter   ModemInferenceAdapter                 |
   |   ModemTelemetryAdapter  ModemActionAdapter                    |
   +-------------------------------+--------------------------------+
                                   |
            +----------------------+----------------------+
            |                                             |
            v (mock, dev laptop)                          v (real)
   +--------+----------+                       +----------+--------+
   |  Mock impls       |                       |  Vendor SDKs       |
   |  - Trace replay   |                       |  - NWAIOS / QNN    |
   |  - Synthetic feed |                       |  - MPSS hooks      |
   |  - In-process FSM |                       |  - NSP runtime     |
   +-------------------+                       +--------------------+
```

The adapter interface is the contract; each adapter has a mock
implementation (used during development on a Snapdragon X laptop) and a
real implementation (linked into the modem FW build). Agent code never
imports a vendor SDK directly.

### 1.2 QUAD adapter set for the modem agent

| Adapter | Mock implementation | Real implementation |
|---|---|---|
| `ModemPlatformAdapter` | Always-available stub; reports synthetic SoC info | Probes MPSS for SoC version, NSP availability, FW version |
| `ModemTelemetryAdapter` | Replays captured RLM/HARQ/PDCP traces from file | Taps real diag rings on Q6 |
| `ModemInferenceAdapter` | Runs the DLC model on host CPU via QNN-CPU backend, or returns deterministic stub outputs | Loads DLC via NSP runtime, schedules per-call with priority lanes |
| `ModemActionAdapter` | Records intended actions to an in-memory log; never mutates state | Calls into RLC/PDCP/RRC hook tables in the live FW |

A single environment variable (`MODEM_HOST` / `QUAD_MODEM_MODE=real|mock`)
selects the adapter family at process startup, identical to how
`GATEWAY_HOST` flips the AI Gateway samples.

### 1.3 Three-tier model

```
   +------------------------------------------------------------+
   |                       AGENT TIER                           |
   |    Telemetry Tap | Feature Engine | Model Server (NSP)     |
   +------------------------------------------------------------+
                              |
                              v
   +------------------------------------------------------------+
   |                  ARBITRATION TIER                          |
   |  Decision Arbiter | Confidence Filter | Safety Constraints |
   +------------------------------------------------------------+
                              |
                              v
   +------------------------------------------------------------+
   |                     ACTION TIER                            |
   |   RLC hooks | PDCP hooks | RRC hooks | (L1 read-only v1)   |
   +------------------------------------------------------------+
                              |
                              v
                +------------------------------+
                |   3GPP MODEM STACK (host)    |
                +------------------------------+
```

* **Agent tier** observes the stack and produces *recommendations*
  (predictions + confidence + suggested action).
* **Arbitration tier** mediates between competing recommendations,
  applies safety bounds, decides whether to act.
* **Action tier** is the only tier that mutates modem state, and only
  through pre-approved hooks with bounded action spaces.

This separation guarantees that no single ML model can take an
unsafe action by itself - the arbiter is the choke point.

### 1.4 Process / address-space layout

```
   +-------------------+     +-------------------+
   |  Modem Q6 Core    |     |  Modem NSP        |
   |  (MPSS / 3GPP)    |     |  (Inference)      |
   |                   |     |                   |
   |  RLC / PDCP / RRC | <-> |  Model Server     |
   |  Feature Engine   |     |  (multi-model)    |
   |  Decision Arbiter |     |                   |
   |  Action Dispatch  |     |                   |
   +-------------------+     +-------------------+
            ^                          ^
            |                          |
            v                          v
   +-----------------------------------------------+
   |  Shared lock-free buffers (telemetry, results)|
   +-----------------------------------------------+
```

The Q6 core runs the 3GPP stack and the agent's control plane (feature
engine, arbiter, dispatcher) - this keeps the action path low-latency
and physically close to the layers it acts on. The NSP runs the model
server, fed via shared lock-free buffers. This avoids cross-core IPC
on the hot path.

---

## 2. Data Path

### 2.1 Telemetry sources and granularity

| Layer | Source | Granularity | Examples |
|---|---|---|---|
| L1 (PHY) | DSP firmware | per-TTI | CQI, BLER, RSRP, RSRQ, SINR, SSB/CSI-RS, beam reports |
| L2 (MAC) | Q6 MAC | per-TTI | HARQ ACK/NACK pattern per HARQ process |
| L2 (RLC) | Q6 RLC | per-event | retx counter, status PDU events, last-valid-status-PDU time |
| L2.5 (PDCP) | Q6 PDCP | per-event | SN gaps, reordering events, ROHC state |
| L3 (RRC) | Q6 RRC | per-event | timer state, measurement events, current config |
| Diag | Q6 / DSP | varies | thermal, PA condition, RF tuneaway, coexistence |

### 2.2 Telemetry tap

* Each layer publishes telemetry via a **per-source lock-free SPSC ring buffer**.
* Producer: the layer's existing logging hook, lightly augmented to
  drop a structured record into the ring.
* Consumer: the feature engine.
* No locks shared with the scheduler. Buffer overruns increment a
  diagnostic counter and the oldest record is dropped (telemetry is
  best-effort; scheduler real-time is not).

### 2.3 Feature engine

* Per-use-case feature extractors registered at startup.
* Each extractor declares: (input streams, sliding window length,
  output feature vector layout, feature dtype).
* Extractor runs in a tight loop on Q6, draining the rings it depends on,
  computing rolling stats / convolutions / event-time features.
* Output: a feature vector pushed into the model server's input queue.

Feature engine is the **only** place where the contract between the
3GPP stack and the agent is defined. Stack-level changes (e.g., a new
RLC field) require updating one feature extractor; the rest of the agent
is insulated.

### 2.4 Model server

* Multi-model scheduler running on Hexagon NSP.
* Models are pre-loaded at boot, kept resident.
* Inference scheduling has priority lanes: critical models (UC-1 RLF
  prediction) preempt lower-priority ones (UC-5 DRX adaptation).
* Each inference is bounded by a 200 us watchdog. On expiry, the model
  server returns a "no-decision" sentinel; the arbiter treats this as
  defer-to-standards.

### 2.5 Decision arbiter

* Receives `(use_case_id, prediction, confidence, suggested_action)` tuples.
* Applies safety filter: rejects any action outside pre-declared bounds.
* Applies confidence filter: rejects below threshold.
* Resolves conflicts: when two models target the same parameter, highest
  priority wins; ties resolved by higher confidence.
* Emits `(decision_id, action, reason_code)` to the action dispatcher.

### 2.6 Action dispatcher

* Per-target hooks registered at boot:
  * RLC: `set_t_pollretransmit(value, duration)`, `set_max_retx(value, duration)`.
  * PDCP: `set_t_reordering(value, duration)`, `flush_reorder_buffer()`.
  * RRC: `trigger_procedure(BFR | RLF | meas_report)`, `modify_meas_config(delta)`.
  * L1: read-only in v1.
* Each hook validates the call against 3GPP timer ranges and current
  RRC config (some procedures are only legal in certain states).
* Hooks log every invocation to the audit trail (FR-5.2 / FR-7.1).

---

## 3. Model Architecture

### 3.1 Per-use-case models, not a monolith

| Use case | Model class | Approx params | Quantized size | Inference budget |
|---|---|---|---|---|
| UC-1 RLF | TCN over HARQ + status PDU window | ~10 K | ~50 KB | 100 us |
| UC-2 BFR | RNN (GRU) over RSRP/SSB trajectory | ~5 K | ~30 KB | 80 us |
| UC-3 HO | Gradient-boosted trees over geo+RF features | ~20 K | ~100 KB | 50 us |
| UC-4 NTN | Bayesian filter (analytical, no ML) | n/a | ~1 KB constants | 20 us |
| UC-5 DRX | Temporal Fusion Transformer over traffic profile | ~50 K | ~200 KB | 200 us |

Total budget: ~500 KB models in flash, ~5 MB working set in RAM, well
within NFR-2 (<10 MB).

Per-use-case models keep the architecture flexible: training data
contracts, validation suites, and rollback paths are independent.
Adding UC-6 in the future is a new model + new feature extractor; no
agent core changes.

### 3.2 Model lifecycle

```
   train (offline, server farm)
        |
        v
   regression-test on trace suite
        |
        v
   AIMET INT8 quantize
        |
        v
   export QDQ ONNX -> qairt-converter -> DLC
        |
        v
   sign with FW signing key
        |
        v
   bundle into FW image OR ship as OTA delta
        |
        v
   on-device verification + hot-swap
```

### 3.3 Confidence and uncertainty

* Every model emits `(prediction, confidence)`.
* Confidence is calibrated offline (Platt scaling or temperature scaling).
* The arbiter applies a per-use-case confidence threshold; below
  threshold, the agent defers to standards behavior.
* This is the primary safety mechanism for "the model is unsure".

### 3.4 Where ML is NOT the right tool

UC-4 (NTN HARQ adaptation) is included as a **deliberate non-ML use case**:
it is a closed-form computation given the constellation parameters and
ephemeris. The agent framework hosts both ML and non-ML decision modules
through the same interface; this is by design - the agent is a *policy
host*, not a model host.

---

## 4. Decision Arbitration

### 4.1 Priority levels

| Priority | Use case | Rationale |
|---|---|---|
| 0 (highest) | Safety overrides (e.g., emergency call, eCall) | Never preempt regulatory paths |
| 1 | UC-1 RLF, UC-2 BFR | Imminent link loss; missed prediction = user-visible outage |
| 2 | UC-3 HO | High-impact but slower-moving |
| 3 | UC-4 NTN | Throughput optimization |
| 4 (lowest) | UC-5 DRX | Power/efficiency optimization |

### 4.2 Conflict resolution

When two models suggest conflicting actions on the same parameter:
1. Higher priority wins.
2. If priorities tie, higher confidence wins.
3. If both tie, defer to standards (no action).

### 4.3 Safety filter

A static, pre-validated rule set:
* All adjusted timer values MUST remain within 3GPP-defined ranges.
* Some actions are illegal in certain RRC states (e.g., cannot trigger
  BFR before BFR is configured).
* The filter is unit-tested separately from any model.

The safety filter is the **last line of defense** between an
incorrect model output and a non-conformant modem. It is intentionally
written as static code (not learned).

---

## 5. Failure Modes and Recovery

| Failure | Detection | Recovery |
|---|---|---|
| Model crash | NSP exception / watchdog timeout | Disable that model; mark unhealthy; fall back to standards behavior; log crash dump |
| NSP unavailable | Health probe at boot | CPU fallback for low-priority models; disable high-priority models that can't meet latency on CPU |
| Telemetry stall (ring buffer empty for N TTIs) | Feature engine watchdog | Freeze last action (idempotent); resume on telemetry resumption |
| Feature engine hang | Outer supervisor timer | Kill agent thread; spawn fresh; deploy with last known good state |
| Action effect harmful (predicted RLF still occurred) | Outcome log diff | Increment counter; if rate > threshold, auto-disable that use case via local kill |
| Safety filter rejected action repeatedly | Audit-trail anomaly | Mark model unhealthy; auto-disable; surface to operator dashboard |

The agent supervisor process restarts crashed agent components. The
3GPP modem stack continues running independently throughout - agent
liveness and modem liveness are decoupled.

---

## 6. Observability and Logging

### 6.1 Three log streams

1. **Action audit trail** (per-decision, hot path): timestamp, feature
   vector hash (not raw), model version, confidence, action, reason
   code. Fixed-size ~32-byte record. Goes to a 10K-event circular
   buffer in modem persistent storage. Never blocks on the hot path.
2. **Aggregate metrics** (per-period, slow path): prediction
   accuracy, action efficacy, false-positive rate, RLF rate, TTR
   distribution. Emitted via QXDM diag every N seconds.
3. **Crash dumps** (on fault): include action audit trail tail +
   feature engine state snapshot.

### 6.2 What is *not* logged

* Raw telemetry on the hot path (volume too high; logging would impact RT).
* PII (location, IMSI, IMEI) in off-device telemetry.
* Model weights (they are signed firmware, not telemetry).

### 6.3 On-device debug

* QXDM hook to dump feature vector + model output for the last K decisions.
* Per-use-case enable/disable runtime flag for in-field bisection.

---

## 7. Deployment

### 7.1 First deployment

* Models bundled into FW image as part of the modem build flow,
  invoked via QUAD: `quad modem build --target <triple> --sdk-root
  <mpss-sdk>` produces the model-bundle artifact that the modem FW
  build pipeline consumes.
* Per-PLMN config block includes per-use-case enable flags, defaults
  to disabled for all use cases at first ship.
* Operator IOT testing enables the agent for that PLMN.

### 7.2 Subsequent updates

* Models updated via OTA delta (signed model bundle, no full FW reflash).
* Hot-swap supported where the model class allows it (current inference
  drains, then new model loaded, then resume).
* `quad modem deploy --host <device> --bundle stc.dlc` is the
  developer-side entry point. In production the same artifact moves
  through the OTA channel.

### 7.3 Rollout strategy

| Phase | Scope | Duration |
|---|---|---|
| 0 - Shadow | Agent enabled, predicts but does NOT act; telemetry collected | 4-8 weeks per use case |
| 1 - Canary | Active mode, 1% of devices on a single MNO | 2-4 weeks |
| 2 - Limited rollout | 10% of devices | 2 weeks |
| 3 - General | All devices on PLMNs that have approved | ongoing |
| Kill switch | Available at any phase, < 60 s effect | n/a |

### 7.4 Per-PLMN gating

Some MNOs may require explicit IOT certification before activation.
The per-PLMN enable flag (FR-8.1) accommodates this. Default-off,
opt-in.

---

## 8. Test Strategy

The agent uses the same five-gate validation pattern as every other
QUAD sample (see `samples/stc_classifier/test_procedure.ps1` for the
working precedent). All five gates run on a developer laptop in
mock mode; gates 4 and 5 also run on real hardware once available.

### 8.1 Gate 1 - Pre-flight + model build

* `build_model.py` synthesizes / loads the per-use-case model.
* `quad doctor --section modem` validates SDK, NSP runtime ABI, model
  bundle signing, FW headers.

### 8.2 Gate 2 - Host pytest

* `tests/test_smoke.py` - imports, scaffold structure, model schema.
* `tests/test_units.py` - feature extractors (each input ring -> known
  feature vector), models (known features -> expected output within
  tolerance), safety filter (every illegal action rejected), arbiter
  (matrix of conflicting recommendations -> expected resolution).
* `tests/test_end_to_end.py` - codegen round-trip (`generate_code`
  produces the modular scaffold), `quad modem build --dry-run` plan
  is well-formed, `MockModemAdapter.deploy()` returns running,
  `profile_workload(platform="modem")` returns shaped report.

### 8.3 Gate 3 - Cross-compile dry-run

* `quad modem build --target <triple> --sdk-root <mpss> --dry-run`
  emits the cmake plan and IPK / SLA artifact target without
  invoking the cross-compiler. Validates the build graph is sane
  before any real compile.

### 8.4 Gate 4 - Mock deploy + trace replay

* `MockModemAdapter` runs install/start in-process; `state=running`
  is the success signal.
* **Trace replay** is the modem-specific gate that doesn't exist in
  the AI Gateway samples: real captured RLM/HARQ/PDCP traces from
  network labs are fed through the agent in-process via
  `ModemTelemetryAdapter`'s replay backend. Predictions are checked
  against the actual outcomes recorded in the trace. Per-use-case
  regression suite gates promotion.

### 8.5 Gate 5 - Profile shape

* `profile_workload(platform="modem", runtime="npu", duration_s=10)`
  returns a report with all required keys (latency, throughput,
  power, runtime_used, measurement_notes) and the latency dict has
  all six sub-keys (mean_ms, p50_ms, p95_ms, p99_ms, min_ms, max_ms).
* Mock backend returns deterministic per-use-case latency; real
  backend reads from the live agent's stats counters via diag.

### 8.6 Real-hardware validation (beyond the five gates)

Once the five mock gates are green, the same pattern continues
against real hardware:

* **Modem simulator** - QUAD's mock adapter swaps for an MPSS
  simulator adapter; same agent code, same tests.
* **Hardware-in-the-loop** - modem on dev board + RF anechoic chamber
  + RF emulator (Anritsu / R&S). Stress traces, NTN traces, mmWave
  fading, edge-of-cell.
* **Field validation** - shadow mode on real devices: agent predicts,
  doesn't act, telemetry proves out the prediction quality. Compare
  predicted vs actual outcome distribution; calibrate confidence
  threshold.
* **Compliance** - GCF / PTCRB pass with agent enabled. MNO IOT
  regression: zero new failures.

### 8.7 CI gates

The five mock gates run in CI on every PR. A use case may not regress
by more than X% on its trace-replay suite (gate 4) or break any of
the structural assertions in the test suite (gate 2). Real-hardware
validation runs on a nightly schedule against a fleet of dev boards
and is not blocking on PRs.

---

## 9. Engineering Plan and Phases

| Phase | Deliverables | Duration |
|---|---|---|
| Phase 0 - QUAD framework extension | Modem adapter interfaces, `templates/modem/c_modular/` scaffold, `quad modem` CLI, `profile_workload(platform="modem")`, `quad doctor --section modem`. Mocks-only at this phase. | 2-3 months |
| Phase 1 - Agent core | Telemetry tap, feature engine API, model server, arbiter, dispatcher, audit log. Plugged into Phase-0 adapters. | 4-6 months (parallelizable with Phase 1 once adapter API is frozen) |
| Phase 2 - UC-1 RLF | UC-1 model, training pipeline, regression trace suite, shadow-mode telemetry. | 3-4 months |
| Phase 3 - Field validation | Shadow mode rollout, model calibration, KPI proof. | 2-3 months |
| Phase 4 - Active rollout | Canary -> limited -> general. | 2-4 months |
| Phase 5 - UC-2 / UC-3 / UC-4 / UC-5 | Each use case as a plugin under the framework, scaffolded via `quad codegen`. | 3-4 months per use case (parallelizable) |

---

## 10. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Operator rejects active mode | High | Medium | Per-PLMN gating, shadow mode first, kill switch |
| Model regresses on rare scenarios | Medium | High | Per-use-case regression suite, confidence threshold defers to standards |
| Crash on hot path crashes modem | Low | Critical | Process isolation, supervisor restart, NSP/Q6 separation |
| Agent power exceeds budget | Medium | Medium | Continuous power monitoring, NFR-3 gate before deploy |
| Telemetry ring overruns drop critical events | Medium | Medium | Per-source ring sizing tuned to peak; overrun counter monitored |
| Inference latency exceeds NFR-1 | Medium | High | Watchdog timeout falls back to standards; CI perf gate |
| Operator data sharing constraints block training data collection | High | High | Synthetic + lab-collected as primary; field data as secondary |
| Standards drift breaks feature contract | Low | Medium | Feature engine isolation: stack changes touch one extractor |

---

## 11. Open Items

See `open_questions.md` for the full list of unresolved architectural,
product, and process questions that need decisions before Phase 1
exit.
