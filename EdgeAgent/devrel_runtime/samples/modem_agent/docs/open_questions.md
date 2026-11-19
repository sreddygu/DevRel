# Modem Agent - Open Questions

| | |
|---|---|
| **Document** | Open Questions / Unresolved Decisions |
| **Version** | 0.1 |
| **Status** | Living document |
| **Date** | 2026-05-26 |
| **Companion** | requirements.md, design.md |

These are the decisions that block - or shape - downstream work. Each
needs an owner, a target close date, and a recommendation.

Questions are grouped by domain. The format is:

* **Q-N.M** - the question
* **Why it matters** - what work is blocked or shaped by this
* **Options** - candidate answers
* **Recommendation** - the architect's lean (subject to challenge)
* **Owner / due** - who decides, by when

---

## A. Product / Standards Strategy

### Q-A.1 - Shadow mode vs active mode for first deployment

**Why it matters**: Determines whether Release 1 ships with the agent
making decisions in production, or only observing. Sets MNO/regulatory
posture, KPI proof methodology, and rollback complexity.

**Options**:
1. Shadow only for R1; active in R2 after data proves safety.
2. Active from R1, gated by per-PLMN approval.
3. Hybrid: active for UC-1 (clear win), shadow for everything else.

**Recommendation**: Option 3. UC-1 has a clean predicted gain (720 ms);
shadow first for UC-2-5 where false positives have higher cost.

**Owner**: Product + Modem Architecture. **Due**: before Phase 1 exit.

---

### Q-A.2 - 3GPP / GSMA disclosure posture

**Why it matters**: Some operators / standards bodies will want to know
that the agent exists and how it operates. This affects compliance,
labelling, and possibly RAN behavior assumptions.

**Options**:
1. Disclose to top-N MNOs as part of standard IOT collateral.
2. Treat as proprietary modem optimization (existing precedent for
   non-ML proprietary tweaks).
3. Submit aspects to 3GPP RAN / SA for awareness without normative claims.

**Recommendation**: Option 1 + 2 hybrid. Disclose to MNOs (they will
notice in IOT anyway), keep model details proprietary. Avoid 3GPP
normative submission in R1.

**Owner**: Standards / Legal. **Due**: before MNO IOT engagement.

---

### Q-A.3 - Per-operator model personalization vs global model

**Why it matters**: A model trained on operator-X traces may overfit and
behave poorly on operator-Y. But N PLMN-specific models multiplies model
size, validation cost, OTA bandwidth.

**Options**:
1. Single global model per use case.
2. Tiered: global model + per-PLMN calibration deltas.
3. Per-PLMN model (one per top-tier MNO).

**Recommendation**: Option 2. Single model + lightweight calibration
(normalization stats, confidence threshold) per PLMN. Allows training
data sharing while letting each PLMN tune its own threshold.

**Owner**: AI/ML + Modem. **Due**: model design phase.

---

### Q-A.4 - LTE / 5G NR / NTN scope

**Why it matters**: Different RATs have different telemetry surfaces,
timer ranges, and conformance suites. Multiplies validation cost.

**Options**:
1. NR only in R1 (cleanest spec, biggest greenfield).
2. NR + LTE in R1 (LTE has more deployed devices, more impact).
3. NR + LTE + NR-NTN in R1 (NTN is the differentiated story).

**Recommendation**: Option 1 for R1, with NR-NTN added in R1.5 once
the framework is stable. LTE in R2 if business case warrants.

**Owner**: Product. **Due**: before Phase 1 kickoff.

---

### Q-A.5 - eCall / emergency call posture

**Why it matters**: 3GPP TS 22.101 makes emergency calls priority-zero.
Agent intervention during eCall is regulatory hot zone.

**Options**:
1. Disable agent entirely during emergency call session.
2. Allow only "fail-safer" actions (extend timers, never shorten).
3. Run normally; arbiter priority-0 already covers it.

**Recommendation**: Option 1. Simplest, regulator-friendly, matches
existing precedent. Document in compliance posture.

**Owner**: Standards / Legal. **Due**: before any active-mode rollout.

---

## B. Architecture and Technical

### Q-B.1 - DevRel adapter strategy: extend DevRel vs build a parallel framework

**Why it matters**: This is the foundational software dependency for the
agent. The agent could be developed (a) as a DevRel sample with new
modem-specific adapters added to DevRel core, (b) inside a parallel
modem-tooling framework that reuses DevRel's patterns but is a separate
codebase, or (c) directly against vendor SDKs with no abstraction.

**Options**:
1. **Extend DevRel core** with `ModemPlatformAdapter`,
   `ModemInferenceAdapter`, `ModemTelemetryAdapter`,
   `ModemActionAdapter`; ship the agent as a DevRel sample under
   `samples/modem_agent_uc<N>/`. Pattern matches AI Gateway exactly.
2. **Parallel framework** that copies DevRel's adapter / codegen / CLI
   patterns but lives in modem-FW org. Avoids cross-org DevRel core
   contributions but duplicates code.
3. **Direct vendor SDK** - skip the framework entirely; agent code
   links libnwaios / QNN directly. Smallest line-of-code count;
   no mock-first development.

**Recommendation**: Option 1. Three reasons:
* The five-gate validation pattern is the productivity multiplier;
  rebuilding it in a parallel framework wastes 6+ engineer-months.
* AI Gateway is the closest precedent (NSP-resident inference,
  cross-compile, signed bundles, IPK/SLA distribution) - the modem
  adapters are direct analogs of `NWAIOSAdapter` / `MockLCMAdapter`.
* Mock-first development on a Snapdragon X laptop is unreachable
  without an adapter layer.

**Risk for Option 1**: cross-org review cycles for DevRel core changes.
Mitigation: prototype the adapters in `devrelAgent/samples/modem_agent/`
first (no DevRel core changes), prove the value, then upstream to DevRel
core in a single coordinated PR.

**Owner**: Modem Architecture + DevRel core. **Due**: phase-0 / week 4.

> Companion questions: Q-B.1.1 (NSP runtime selection), Q-B.1.2
> (codegen template scope) - both downstream of this decision.

---

### Q-B.1.1 - Underlying NSP runtime: NWAIOS vs QNN-Hexagon vs purpose-built

**Why it matters**: Even with DevRel adapters in place, the *real*
implementation behind the adapter must use one of the available NSP
runtimes. Each option has different latency, memory, and integration
profiles.

**Options**:
1. NWAIOS (already used by AI Gateway samples; modem adapter might
   reuse the runtime as-is).
2. QNN-Hexagon (general-purpose; higher overhead; broader op support).
3. Custom modem-NSP minimal runtime (smallest, most work to build).

**Recommendation**: Need a benchmark before deciding. Build a TCN-style
toy model and measure latency + memory on the actual NSP target with
each option. Decision deferred 4-6 weeks. The DevRel adapter abstraction
makes this a swap behind the interface, not a foundational redesign.

**Owner**: Modem AI. **Due**: phase-0 / week 4.

---

### Q-B.1.2 - Codegen template scope: per-use-case vs per-agent

**Why it matters**: The AI Gateway has one app per use case
(`ai_gateway_classifier`, `gwapps_fault_detection`). The modem agent
could ship as a single binary hosting all use cases (one sample) or as
N binaries, one per use case (N samples).

**Options**:
1. Single agent binary with N model plugins. One sample
   (`samples/modem_agent/`), one IPK / SLA artifact.
2. N use-case binaries sharing common infrastructure as a static
   library. N samples, N artifacts.
3. Hybrid: shared agent core + per-use-case plugin DLCs loaded at
   runtime.

**Recommendation**: Option 1. Modem FW context favors a single
process; rolling out N IPKs to N config slots is operational
complexity for no architectural benefit.

**Owner**: Modem Architecture. **Due**: phase-0 design freeze.

---

### Q-B.2 - Per-TTI inference vs event-driven inference

**Why it matters**: Worst case (UC-1 needs feature update per TTI),
best case (UC-3 needs update per HO event). Power and latency budget
depends on which.

**Options**:
1. Per-TTI for time-critical models; event-driven for others.
2. All event-driven with feature aggregation per event.
3. All per-TTI with throttling.

**Recommendation**: Option 1. UC-1 gets per-TTI feature updates (HARQ
state changes per TTI); inference is event-triggered when feature
volatility crosses a threshold.

**Owner**: Modem AI. **Due**: phase-1 design freeze.

---

### Q-B.3 - Action space scope for R1

**Why it matters**: Wider action space = more impact + more risk.
Defines safety filter complexity.

**Options**:
1. Timer adjustments only (RLC `t-PollRetransmit`, PDCP `t-Reordering`).
2. Timer adjustments + procedure triggers (BFR, meas reports).
3. Above + RRC config tweaks (A3 offset, hysteresis).

**Recommendation**: Option 2 in R1 (covers UC-1 + UC-2 fully). Add
option 3 in R2.

**Owner**: Modem Architecture. **Due**: Phase 1 design freeze.

---

### Q-B.4 - Conflict between agent action and gNB scheduler decision

**Why it matters**: Agent might reset RLC retx counter at the same
moment the gNB has decided to declare RLF. Race condition produces
non-conformant behavior on either side.

**Options**:
1. Agent never acts during a "transition" RRC state (defer to standards).
2. Agent acts, telemetry channel detects post-hoc and rolls back.
3. Synchronization handshake with gNB (requires protocol extension; out
   of scope for R1).

**Recommendation**: Option 1 for R1. Document state transitions where
agent is muted.

**Owner**: Modem Architecture. **Due**: Phase 1 design freeze.

---

### Q-B.5 - Multi-modem coexistence (DSDA / 5G+WiFi)

**Why it matters**: Two radios sharing PA / RF front-end means agent
decisions on one path can interact with the other. Existing MMS
(Multi-Mode Subsystem) already arbitrates RF; agent must respect it.

**Options**:
1. Agent only operates on the "primary" modem path; other paths use
   legacy.
2. Agent on both paths but coordinated via shared state.
3. Single agent instance arbitrating both paths (most invasive).

**Recommendation**: Option 1 for R1. Defer 2/3 to R2.

**Owner**: Modem Systems. **Due**: Phase 1 design freeze.

---

### Q-B.6 - Concurrent agents per use case vs unified policy engine

**Why it matters**: Architecture choice. Multiple independent agents
are simpler to develop but require strong arbitration. Unified engine
is harder to develop but inherently consistent.

**Options**:
1. Per-use-case agents + arbiter (current design.md proposal).
2. Single multi-task model spanning all use cases.
3. Hierarchical: high-level meta-controller dispatches to specialist
   models.

**Recommendation**: Option 1 (current design). Decoupled rollout, simpler
validation. Reconsider for R3 if maintenance burden grows.

**Owner**: Modem Architecture. **Due**: already proposed; confirm.

---

### Q-B.7 - Watchdog policy on inference timeout

**Why it matters**: 200 us watchdog (NFR-1 sub-budget) - what happens
on timeout matters for safety vs availability.

**Options**:
1. Defer to standards (silent fallback).
2. Mark model unhealthy after K consecutive timeouts; disable.
3. Lower-priority alternate model (cascade).

**Recommendation**: Option 1 + Option 2 combined. Single timeout =
silent defer; K-in-a-row = disable + alert.

**Owner**: Modem AI. **Due**: Phase 1.

---

### Q-B.8 - Feature contract stability across modem FW iterations

**Why it matters**: Modem FW changes fast. If features change, models
break. Need a stable surface.

**Options**:
1. Versioned feature contract; old models reject new features.
2. Feature engine adapters per FW version (translation layer).
3. Frozen feature schema for the lifetime of the agent (most rigid).

**Recommendation**: Option 1 + Option 2 combined. Schema is versioned;
adapters bridge minor versions. Major version = model retrain.

**Owner**: Modem AI + Modem FW. **Due**: before model training starts.

---

## C. Data, Training, and ML Lifecycle

### Q-C.1 - Training data: synthetic vs lab vs field

**Why it matters**: Field data is highest fidelity but raises privacy +
operator concerns. Synthetic / lab is freer but quality risk.

**Options**:
1. Synthetic + lab only for R1; field for R2.
2. Synthetic + lab + opt-in field collection on test fleet.
3. Field data via existing diag pipeline (privacy-anonymized).

**Recommendation**: Option 2. Synthetic + lab covers initial training;
opt-in test fleet provides realistic distribution validation.

**Owner**: AI/ML + Privacy. **Due**: before training pipeline starts.

---

### Q-C.2 - Model versioning and rollback

**Why it matters**: Field models will need updates; bad model must roll
back fast.

**Options**:
1. Two-slot scheme (A/B), atomic switch, instant rollback.
2. Single slot with FW reflash to roll back (slow).
3. Per-use-case slots.

**Recommendation**: Option 1 (per-use-case A/B). Standard practice for
on-device ML.

**Owner**: Modem FW + AI/ML. **Due**: before first OTA model update.

---

### Q-C.3 - Confidence threshold tuning

**Why it matters**: Threshold is the agent's main safety knob. Too
permissive = false-positive interventions; too strict = missed
predictions; both lose value.

**Options**:
1. Static per-use-case threshold, set in lab, frozen.
2. Per-PLMN threshold (set during operator IOT).
3. Adaptive threshold (e.g., move toward stricter on rolling
   false-positive rate).

**Recommendation**: Option 2 for R1. Option 3 considered for R2.

**Owner**: AI/ML + Modem Architecture. **Due**: phase 3 (field
validation).

---

### Q-C.4 - Online learning policy

**Why it matters**: Continuous on-device learning is appealing but
introduces non-determinism and model drift risk.

**Options**:
1. No on-device weight updates in R1 (current design).
2. On-device feature normalization stats only (no weight update).
3. Federated learning with periodic weight aggregation.

**Recommendation**: Option 2. Accept normalization adaptation, defer
weight updates.

**Owner**: AI/ML. **Due**: Phase 1 freeze.

---

### Q-C.5 - Trace corpus for DevRel mock-mode replay

**Why it matters**: Gate 4 of the DevRel validation pattern is
trace-replay (real captured RLM/HARQ/PDCP traces driven through the
agent in-process via `ModemTelemetryAdapter`). The corpus IS the
test suite - quality and coverage of the corpus determines what the
mock gates can prove.

**Options**:
1. Synthetic trace generator only (per-scenario parameterizable).
2. Lab-captured traces (controlled environment; smaller distribution).
3. Field traces (anonymized, high-fidelity, privacy + operator review
   needed).
4. All three layered, with field traces gated behind opt-in.

**Recommendation**: Option 4. Synthetic gives wide coverage cheaply,
lab gives realism, field gives statistical truth. Trace corpus
versioning is part of the agent release artifacts.

**Owner**: AI/ML + Privacy. **Due**: before Phase 2 starts.

---

### Q-C.6 - When does DevRel mock mode stop being good enough

**Why it matters**: Mock-first development is the productivity multiplier,
but at some point real-modem testing must take over. Deciding *when*
to stop trusting mocks bounds the developer-laptop dev cycle's value.

**Options**:
1. Mocks until KPI proof; everything after that is real-only.
2. Mocks always run alongside real for regression; real for any
   stability / power / thermal claim.
3. Mocks only for unit / e2e structural tests; algorithmic correctness
   requires HIL or simulator.

**Recommendation**: Option 2. Mocks remain authoritative for
structural and contract tests forever; real hardware authoritative for
KPI / stability / power / certification. Both run in CI; mocks pre-PR,
real on nightly.

**Owner**: Modem Architecture + Test Infra. **Due**: Phase 0 exit.

---

## D. Compliance, Privacy, Legal

### Q-D.1 - Regulatory characterization of AI-driven modem behavior

**Why it matters**: Some jurisdictions are starting to regulate AI in
critical infrastructure. EU AI Act sectoral annexes, FCC AI guidance,
etc. could apply.

**Options**:
1. Treat the agent as proprietary modem firmware (existing regime).
2. Pre-emptively classify as "AI system" and document for transparency.
3. Wait for explicit regulator guidance.

**Recommendation**: Option 2. The audit log (FR-7.1) makes
explainability achievable; documenting it now avoids retrofit.

**Owner**: Legal. **Due**: before active mode rollout.

---

### Q-D.2 - Privacy-preserving telemetry off-device

**Why it matters**: Even aggregated KPIs might re-identify if combined
with cell tower fingerprints + time windows.

**Options**:
1. On-device aggregation only; nothing per-event sent off.
2. Differentially-private aggregates (epsilon-DP).
3. K-anonymity bucketing.

**Recommendation**: Option 1 for R1. Option 2 if research collaboration
demands per-event data.

**Owner**: Privacy + AI/ML. **Due**: before any off-device telemetry.

---

### Q-D.3 - GCF / PTCRB / MNO IOT certification gating

**Why it matters**: Some operators require explicit certification of
agent decisions before enabling on their PLMN.

**Options**:
1. Default-off until per-PLMN MNO IOT pass.
2. Default-on; operators can opt-out via SIM-OTA.
3. Per-region default with opt-in/opt-out per MNO.

**Recommendation**: Option 1. Conservative, matches existing precedent
for proprietary RAN-impacting features.

**Owner**: Cert + Standards. **Due**: before R1 ship.

---

## E. Process, Org, Roadmap

### Q-E.1 - Owning org for the agent

**Why it matters**: Cross-cutting concerns (modem FW, AI/ML, compliance,
field operations) - needs a clear DRI.

**Options**:
1. New cross-functional team chartered around the agent.
2. Modem FW team owns; AI/ML provides models as a service.
3. AI/ML team owns; modem FW provides hooks.

**Recommendation**: Option 1. The agent crosses too many boundaries
for either single org to own end-to-end.

**Owner**: Engineering leadership. **Due**: before Phase 1 kickoff.

---

### Q-E.2 - Release cadence

**Why it matters**: Modem FW is annual; ML wants to update faster.
Disconnect causes friction.

**Options**:
1. Models tied to FW release (annual).
2. Models on independent OTA cadence (quarterly or faster).
3. Models tied to FW for "shape" changes; OTA for weight updates.

**Recommendation**: Option 3. Architecture/feature changes go with FW;
weight updates ship more often.

**Owner**: Engineering Program Mgmt. **Due**: before OTA infrastructure
commits.

---

### Q-E.3 - Telemetry data sharing with operators

**Why it matters**: Some operators want agent KPI visibility on their
networks; others won't permit data sharing.

**Options**:
1. No operator data sharing; OEM-internal analysis only.
2. Aggregated KPI dashboard accessible to operator (per-PLMN slice).
3. Per-event diagnostic stream to operator.

**Recommendation**: Option 2. Aggregated dashboard preserves OEM IP and
gives operators what they need for IOT.

**Owner**: Product + Operator Programs. **Due**: before operator IOT.

---

### Q-E.4 - Phased KPI proof methodology

**Why it matters**: How do we prove the 720 ms G-2 target before active
rollout?

**Options**:
1. Lab traces only.
2. Lab + simulator + shadow-mode field telemetry.
3. Lab + simulator + shadow + small-scale active canary.

**Recommendation**: Option 3. Each layer validates a different concern
- lab proves prediction quality, shadow proves field distribution,
canary proves action effect.

**Owner**: Modem Architecture + Field Ops. **Due**: end of phase 2.

---

### Q-E.5 - Failure-mode communication to user

**Why it matters**: If the agent makes a bad decision and the user
sees a dropped call, do we surface that the agent was involved?

**Options**:
1. No user-facing surfacing (matches current modem behavior).
2. OEM diagnostic visibility only (no end-user UI).
3. End-user-visible "AI active" indicator (transparency posture).

**Recommendation**: Option 2 for R1. Option 3 considered if regulatory
posture (Q-D.1) demands it.

**Owner**: Product + Legal. **Due**: before R1 active rollout.

---

## F. Appendix - Out-of-Scope Items Worth Tracking

These are explicitly out of R1 scope but worth a placeholder for
future releases:

* **F-1** L1/PHY action space (BWP switching, beamforming hints, etc.).
* **F-2** Cross-UE federated learning.
* **F-3** Inter-RAT coordination (LTE-NR DC steering decisions).
* **F-4** End-to-end QoS-aware decisions (cooperate with OS scheduler).
* **F-5** Coexistence with O-RAN xApp/rApp recommendations.
* **F-6** Side-channel hardening (timing attacks against agent action latency).
