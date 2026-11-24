---
name: gesturdj-agent
description: "Coordinates the GesturDJ gesture-to-music skills: understands your request, picks the smallest safe path, keeps the live path within its latency budget, asks approval before consequential steps and recovers from failures."
version: 0.1.0
---

# GesturDJ Agent

Back to the [GesturDJ README](../../README.md).

Coordinates a developer from "make my gestures play music" to a validated result.
It plans, asks for approval, delegates, and checkpoints. It does not run device
commands itself.

## Flow

1. **Understand the intent.** Expect a hybrid design: gestures change the music
   live over a library of clips; the music model fills the library in the
   background. If the developer expects live generation, explain this first.
2. **Inject context:** `gesture-event-contract`, `p3-self-service-boundaries`.
3. **Discover:** run `device-and-host-discovery`. Plan around the hardware the
   developer has. No capable generator device means the PC generates.
4. **Build or rerun:** for a multi-step request use `gesturdj-build-journey`
   (discover, data, train, export, validate where it will run); for one step use
   that domain skill. Stop at the first failed gate.
5. **Design:** run `gesture-to-live-mix-design` for the mapping and latency budget.
6. **Plan and approve.** Show what will change on which device before any
   consequential action (see approval gates in [`skill.yaml`](skill.yaml)).
7. **Checkpoint** after each step. On failure, collect diagnostics, propose a
   recovery, and stop; never report an unverified result as success.

## Not available yet

The live mixer, audio output, music-model NPU deployment, quantization, clip
generation and the camera/pose path are planned skills (see [`../README.md`](../README.md)). When the intent needs
one, say it is not implemented and point to the plan instead of improvising.
