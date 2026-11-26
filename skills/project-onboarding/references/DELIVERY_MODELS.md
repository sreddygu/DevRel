# Delivery Models

This policy serves independent developers: makers, students, hobbyists, and
community builders. Delivery must therefore be public, self-service, and
repeatable on hardware they can obtain. A public release must never depend on an
internal build, corporate account, private network, or undocumented support
path.

This policy applies to the projects cataloged in
[`SYNAPSE_SKILLS.md`](../../../portfolio/SYNAPSE_SKILLS.md).

## Delivery Lanes

### 1. Source Skill Pack

**Use for:** narrative projects, learning projects, and any capability that can
run from public source with common developer tools.

**Deliver:** a public repository or tagged source archive containing project
documentation, `skills/<skill-id>/SKILL.md`, `skill.yaml`, sample inputs, a
non-destructive quickstart, and a validation command.

**Best fit:** `AI-Across-Devices`, `Developer-Journey`,
`Edge-AI-for-Everyone`, `Multiverse-of-Developers`, and the early stages of all
other projects.

**Developer experience:** clone or download, select a skill, run the quickstart, and
attach the generated evidence to a community issue when help is needed.

### 2. Installable Starter Kit

**Use for:** runnable applications with dependencies, local tooling, or a
repeatable model workflow.

**Deliver:** the source skill pack plus a versioned package or installer
(`pip`, `npm`, container, or platform-native package), a lockfile, public model
fetch instructions, example configuration, and smoke-test command.

**Best fit:** `AURA`, `EdgeAgent`, `LLM`, `RoboAgent`, `VSaaS`,
`wake_word`, `sinewave`, `mojo-max-int`, and `DiffRhythm_old_songs`.

**Developer experience:** install a signed/versioned starter kit, run a local smoke
test, then use the project skills to configure, validate, and troubleshoot it.

### 3. Device-Ready Release Kit

**Use for:** a capability that has been validated on a named, publicly
obtainable device or board and needs device-specific assets.

**Deliver:** the installable starter kit plus a release manifest, compatibility
matrix, checksums, evidence summary, rollback instructions, and only the assets
that may legally be redistributed.

**Best fit:** `GesturDJ`, `wake_word`, `Wearable-AI`, `XR-Experiences`, `AURA`,
and `EdgeAgent` after each has public-device validation.

**Developer experience:** choose a compatible target, download one immutable release
bundle, verify it locally, and follow an explicit approval gate before writes,
device installation, sensor capture, or flashing.

## Progressive Promotion

| Channel | Purpose | Admission criteria | Developer promise |
| --- | --- | --- | --- |
| `incubating` | Share a design or early skill | Owner, scope, public-source check | May change or be incomplete; no device claim. |
| `preview` | Gather feedback on a runnable workflow | Reproducible quickstart and validation evidence | Works in the documented test environment. |
| `stable` | Support a declared use case | Device/OS compatibility, evidence, license review, rollback | Reproducible supported path and documented upgrade behavior. |
| `lts` | Preserve a teaching or hardware baseline | Stable release plus published maintenance end date | Security and critical-fix policy is explicit. |

Promotion is per project release, not per repository. A source skill pack can be
`stable` while a device-ready kit remains `preview`.

## Required Release Bundle

Every `preview`, `stable`, or `lts` delivery publishes a `release-bundle.json`
conforming to [`release-bundle.schema.json`](../../release-bundle-preparation/resources/release-bundle.schema.json). Keep
an example beside the implementation in
[`release-bundle.example.json`](../../release-bundle-preparation/resources/release-bundle.example.json).

The manifest makes a release independently verifiable:

- **Identity:** project, version, channel, source revision, release date.
- **Compatibility:** supported host, OS, device, runtime, and known exclusions.
- **Assets:** URL or public retrieval instructions, SHA-256, size, and license.
- **Skills:** included skill IDs and their entrypoints.
- **Evidence:** validation command and public evidence location or summary.
- **Safety:** approval gates, rollback, and prohibited secret handling.

Run the local validator before publishing:

```powershell
py -3 .\skills\release-bundle-preparation\scripts\validate_release_bundle.py .\skills\release-bundle-preparation\resources\release-bundle.example.json
```

## Open-Source Distribution Rules

1. **Source first.** Publish the code, skill definitions, configuration schema,
   and reproducible build instructions under a declared repository license.
2. **Separate code from restricted assets.** Do not ship proprietary SDKs,
   credentials, private certificates, internal scripts, or model weights whose
   license does not permit redistribution. Publish a public downloader with
   checksum and license acknowledgement instead.
3. **Tag immutable releases.** Use SemVer (`vMAJOR.MINOR.PATCH`), a source tag,
   release notes, and per-asset SHA-256 values. Never replace an asset in place.
4. **Publish provenance.** State where model/data assets came from, how they
   were transformed, the target runtime, and the validation hardware.
5. **Give developers a public support path.** Link to public issue templates and label
   issues by project, release version, target device, and skill ID. Do not make
   a private account or internal channel a prerequisite for support.
6. **Protect users by default.** Release smoke tests are read-only where
   possible. Device writes, package installation, sensor recording, camera use,
   and flashing require an explicit approval step.

## Project Selection Guidance

Start every project as a **Source Skill Pack**. Promote only when the project
can satisfy the next lane's contract:

| Project class | Start with | Promote when |
| --- | --- | --- |
| Narrative or portfolio experience | Source Skill Pack | A runnable public prototype and evidence exist. |
| Local application or model workflow | Installable Starter Kit | A public device target and repeatable device evidence exist. |
| Hardware, sensing, or NPU workflow | Installable Starter Kit | Compatibility, public assets, safety gates, and target-device validation exist. |

`GesturDJ` and `qli_dogfooding` remain the catalog references. Their
skill-layer model should be reused, while public release contents must follow this
public delivery policy rather than any internal deployment path.
