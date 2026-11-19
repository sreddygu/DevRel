# QLI Dogfooding Context

This project provides evidence-driven readiness validation for Linux-based QLI
devices. It organizes reusable device operations into Synapse skills that lead
to a validated developer outcome.

## Synapse Terms

**Context Document**:
A reference file injected as system context before skills run. Defines supported
platforms, safety gates, evidence rules, and ownership. Never executed as a skill.
The `qli-linux-domain` entry is the QLI context document.
_Avoid_: domain skill, product guide, selectable skill

**Domain Skill**:
A bounded, independently verifiable operation with declared prerequisites, inputs,
outputs, and safety behavior. Justified only when conditional judgment is needed
about which tool to invoke or how to sequence based on discovered state.
_Avoid_: command, utility, workflow row, foundational skill

**Journey Skill**:
A composed developer outcome that coordinates domain skills and MCP tools across
multiple operations, manages safety gates, and produces deliverables.
_Avoid_: checklist, script bundle

**Agent Skill**:
The context-aware selector and coordinator that chooses skills, exposes a plan,
enforces approvals, and records execution checkpoints. In this project the agent
skill is `qli-readiness-agent`. Every published agent skill declares its
responsibilities, not_responsible_for list, approval gates, and failure behavior.
_Avoid_: model prompt, autonomous shell, hosting framework responsibility

**MCP Tool**:
A deterministic, single-step executable that produces a predictable, repeatable
result. No agent reasoning required. Implemented once, reused by skills across
products. Check the shared MCP inventory before writing a new tool.
_Avoid_: foundational skill, skill wrapper around a single CLI call

**Developer Journey**:
The three stages a developer moves through, used to decide where to invest:
Discovery, Enablement, and Platform Experience. Each skill declares its
`developer_journey_stage`. Stages and layers do not map one-to-one.
_Avoid_: skill layer, workflow tier

**Publishing Contract**:
The minimum metadata a published skill declares, in five areas: Ownership,
Classification, Contract, Authority, and Control.
_Avoid_: optional metadata

**Review Gates**:
The six exit criteria for an external capability: Ownership, Scope & Boundary,
Validation Evidence, Feedback Mechanism, Discoverability, and Lifecycle
Commitment. Pilot means Gates 1 and 3 are met. Supported means all six are met.
_Avoid_: best-effort checklist

**Readiness Evidence**:
Objective device, command, or artifact proof used to assign a workflow status.
_Avoid_: assertion, tool presence

**Safety Gate**:
An explicit approval boundary before an action can affect device state,
connectivity, data, or user deliverables.
_Avoid_: warning, best effort

**Validated Outcome**:
A requested developer result whose expected state is confirmed with appropriate
readiness evidence.
_Avoid_: completed command, generated file
