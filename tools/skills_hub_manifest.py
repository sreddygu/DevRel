#!/usr/bin/env python3
"""Normalize and validate the Skills Hub manifests (skills.json) in this repo.

Usage:
    python tools/skills_hub_manifest.py            # apply normalization, then validate
    python tools/skills_hub_manifest.py --check    # validate only (exit 1 on problems)

Rules follow docs/skills-hub-maintainer-guide.md and the reference manifests in
qualcomm/skills and qualcomm/qimsdk-skills:
  * Inside a folder source, path/docPath/files are repo-relative, so they carry
    the folder prefix (e.g. GesturDJ/skills/<name>).
  * license/homepage are set on every skill.
  * compatibility is declared only where a project documents its target
    hardware; everything else stays portable (no compatibility block).
  * triggers reference real Skills Hub MCP tools only.
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LICENSE = "Apache-2.0"
HOMEPAGE = "https://github.com/sreddygu/DevRel"
CATEGORIES = {"hardware", "connectivity", "ai", "devtools", "general"}
HUB_AGENTS = {"claude", "codex", "cursor"}  # cursor is used by qualcomm/skills manifests
DEVKITS = {
    "qcs6490-rb3gen2-vision-kit", "qcs6490-rb3gen2-core-kit",
    "qcs6490-rb3gen2-vision-lite-kit", "qcs6490-rubikpi3-kit",
    "qcs9075-iq-9075-evk", "qcs8275-iq-8275-evk-pro",
}
INTERNAL_TERMS = re.compile(r"\b(p3|synapse|devrel|academy|dogfood\w*)\b", re.I)
HUB_TOOLS = {"get_active_device", "list_devices", "validate_ssh_connection"}

IQ8 = "qcs8275-iq-8275-evk-pro"
IQ9 = "qcs9075-iq-9075-evk"
QLI2 = [{"os": "qualcomm_linux", "variant": "qualcomm-linux-proprietary",
         "minVersion": "qli-2.0", "maxVersion": "qli-2.0"}]  # the image the evidence was run on
WIN_LINUX = ["windows", "linux"]  # Windows PC or WSL host

# Hub compatibility per skill, declared only where the repo's evidence supports it.
# Anything not listed stays portable (no compatibility block).
IQ8_DEVICE = {"devkits": [IQ8], "targetOs": QLI2}
IQ9_DEVICE = {"devkits": [IQ9], "targetOs": QLI2}
IQ8_IQ9_DEVICE = {"devkits": [IQ8, IQ9], "targetOs": QLI2}
GESTURDJ_DEVICE = {
    "gesturdj-agent", "gesturdj-build-journey", "device-and-host-discovery",
    "model-export-and-deployment", "on-device-gesture-validation",
    "gesture-to-live-mix-design", "audio-output-integration",
    "live-mixer-and-latency-validation", "music-model-npu-deployment",
    "npu-quantization-and-accuracy-gating",
}
QUAD_DEVICE = {"device-target-configuration"}
QLI_DEVICE = {
    "device-identity-discovery", "baseline-evidence-collection", "ai-model-execution",
    "ai-inference-benchmark", "diagnostic-log-collection", "device-connectivity-validation",
    "developer-readiness-assessment", "qli-readiness-agent", "qli-linux-domain",
}


ALL_HOSTS = ["linux", "windows", "macos"]
ALL_DEVKITS = sorted(DEVKITS)


def compat_for(folder, name):
    if folder == ".":
        # Process skills: any host; the readiness check works for every public devkit.
        c = {"hostOs": ALL_HOSTS}
        if name == "device-readiness":
            c = {"devkits": ALL_DEVKITS, **c}
        return c
    if folder == "AURA":
        return IQ8_DEVICE
    if folder == "EdgeAgent":
        return {**IQ8_IQ9_DEVICE, "hostOs": WIN_LINUX}
    if folder == "GesturDJ":
        # Dataset preparation and training are host-side Python (validated on a PC).
        return IQ8_DEVICE if name in GESTURDJ_DEVICE else {"hostOs": WIN_LINUX}
    if folder == "QUAD-Client":
        if name in QUAD_DEVICE:
            return IQ9_DEVICE
        if name == "quad-run-ps1":
            return {"hostOs": ["windows"]}
        if name == "quad-build-npu-bundle":
            return {"hostOs": ["linux", "windows", "macos"]}
        return {"hostOs": WIN_LINUX}
    if folder == "RoboAgent":
        return {"hostOs": ["windows"]}  # Windows on Snapdragon is both host and target
    if folder == "VSaaS":
        return IQ8_DEVICE_NO_OS if name in ("video-stream-ingestion", "vision-model-validation") else None
    if folder == "qli_dogfooding":
        if name in QLI_DEVICE:
            return IQ8_IQ9_DEVICE
        if name == "host-environment-validation":
            return {"hostOs": WIN_LINUX}
    return None


IQ8_DEVICE_NO_OS = {"devkits": [IQ8]}

# Requirements the hub schema cannot express (shown on the skills-metadata pages).
REQUIREMENTS = {
    "AURA": "Arduino VENTUNO Q or Qualcomm IQ8 (QCS8275); Python 3.10+; optional Genie endpoint (QAIRT 2.47) on a trusted Snapdragon host",
    "EdgeAgent": "Python 3.10+; llama.cpp server (CPU) or Genie shim over QAIRT (NPU, Snapdragon X Elite host)",
    "GesturDJ": "Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path",
    "QUAD-Client": "Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows",
    "RoboAgent": "Snapdragon X (SC8380XP) Windows on ARM device; QAIRT 2.47; no adb or cross-compile",
    "VSaaS": "Python 3.12 and Linux (Ubuntu 24.04); ONNX Runtime or QNN YOLOv8 DLC for real perception",
    "qli_dogfooding": "Qualcomm Linux 2.0 on IQ8 or IQ9; SSH access; Python 3.10+ on the host",
}
HOMEPAGES = {".": "https://github.com/sreddygu/DevRel/tree/main/skills"}


TRIGGERS = {
    "device-readiness": [("get_active_device", "suggest-install")],
    "device-and-host-discovery": [("get_active_device", "suggest-install")],
    "device-identity-discovery": [("get_active_device", "suggest-install")],
    "device-target-configuration": [("get_active_device", "suggest-install")],
    "device-connectivity-validation": [("validate_ssh_connection", "suggest-install")],
}


def manifests():
    yield ".", ROOT / "skills.json"
    for p in sorted(ROOT.glob("*/skills.json")):
        yield p.parent.name, p


def prefixed(folder, value):
    if folder == "." or value.startswith(folder + "/"):
        return value
    return f"{folder}/{value}"


def published_files(skill_path):
    """Download globs for an installed skill: everything except skill.yaml.

    skill.yaml is repo-internal catalog metadata (maintainer/review fields); the
    hub's SKILL.md plus its references, scripts and resources are what a user needs.
    """
    d = ROOT / skill_path
    files = []
    for entry in sorted(d.iterdir()):
        if entry.name in ("skill.yaml", "__pycache__"):
            continue
        files.append(f"{skill_path}/{entry.name}" + ("/**" if entry.is_dir() else ""))
    return files


def normalize(folder, manifest):
    copy = json.loads((ROOT / "tools" / "skills_hub_copy.json").read_text(encoding="utf-8"))
    for s in manifest["skills"]:
        s["license"] = LICENSE
        s["homepage"] = HOMEPAGES.get(folder, f"{HOMEPAGE}/tree/main/{folder}")
        if s["name"] in copy:
            s.update(copy[s["name"]])
        if s["name"] in TRIGGERS:
            s["triggers"] = [{"action": a, "tool": t} for t, a in TRIGGERS[s["name"]]]
        c = compat_for(folder, s["name"])
        for v in s["versions"]:
            for key in ("path", "docPath"):
                if key in v:
                    v[key] = prefixed(folder, v[key])
            v["files"] = published_files(v["path"])
            v.pop("compatibility", None)
            if c:
                v["compatibility"] = json.loads(json.dumps(c))
        # canonical key order: identity first, versions last
        order = ["name", "displayName", "owner", "description", "agents", "category",
                 "tags", "useCases", "license", "homepage", "triggers", "versions"]
        rest = [k for k in s if k not in order]
        for k in order + rest:
            if k in s:
                s[k] = s.pop(k)


# Internal labels that mean nothing to an external audience.
DROP_TAGS = {"academy", "p3", "p3-portfolio", "devrel", "qli_dogfooding"}
PROJECT_TAGS = {
    ".": ["open-source", "release"],
    "AURA": ["ai-agent", "physical-ai", "on-device-ai", "iq8", "ventuno-q"],
    "EdgeAgent": ["ai-agent", "llm", "edge-ai", "snapdragon-x-elite", "iq8", "iq9"],
    "GesturDJ": ["gesture-recognition", "music", "npu", "iq8"],
    "QUAD-Client": ["qualcomm-ai", "mcp", "npu", "snapdragon-x-elite", "qairt"],
    "RoboAgent": ["llm", "executorch", "qnn", "windows-on-snapdragon", "gemma"],
    "VSaaS": ["video-analytics", "computer-vision", "yolov8", "iq8"],
    "qli_dogfooding": ["qualcomm-linux", "qli", "iq8", "iq9", "readiness"],
}
# Skills offered through the public catalog. Everything else stays in the repo
# (and keeps its SKILL.md and metadata page) but is not listed in skills.json:
# context documents, agent coordinators, MCP-tool candidates, demo-specific and
# evidence-only skills, and the internal-visibility qli_dogfooding skills.
CATALOG = {
    ".": {"public-asset-license-review", "release-bundle-preparation", "device-readiness"},
    "AURA": {"aura-agent-orchestration"},
    "EdgeAgent": {"edge-agent-runtime-setup"},
    "GesturDJ": {
        "gesturdj-build-journey", "gesture-dataset-preparation",
        "gesture-model-training-and-evaluation", "model-export-and-deployment",
        "on-device-gesture-validation", "music-model-npu-deployment",
        "npu-quantization-and-accuracy-gating", "audio-output-integration",
    },
    "QUAD-Client": {
        "quad-quickstart", "quad-doctor", "quad-detect", "quad-configure",
        "quad-npu-prereqs", "quad-convert", "quad-codegen", "quad-profile",
        "quad-deploy", "quad-executorch", "quad-qnn-runtime-debug",
        "quad-recommend", "quad-app-builder",
    },
    "RoboAgent": {"roboagent-setup", "roboagent-run-model"},
    "VSaaS": {"vision-model-validation"},
    "qli_dogfooding": set(),  # all marked visibility: internal
}


def curate(folder, manifest):
    keep = CATALOG.get(folder, set())
    manifest["skills"] = [s for s in manifest["skills"] if s["name"] in keep]
    if folder == ".":
        manifest["sources"] = [s for s in manifest.get("sources", [])
                               if CATALOG.get(s.get("path"), True)]


STOP = {"and", "the", "of", "for", "to", "a", "in", "on", "with", "an"}
# Runtime-synced skills (shipped/byte-checked copies); never edited here.
RUNTIME_DIRS = (".claude/", ".pi/", ".codex/")

ACRONYMS = {"quad": "QUAD", "qli": "QLI", "npu": "NPU", "qnn": "QNN", "pte": "PTE", "ps1": "PS1",
            "roboagent": "RoboAgent", "pi": "Pi", "p3": "P3", "aura": "AURA", "unoq": "UNO Q",
            "gesturdj": "GesturDJ", "executorch": "ExecuTorch", "onnx": "ONNX", "ai": "AI"}

MOJIBAKE = "â"  # UTF-8 punctuation mis-decoded as cp1252 (â€”, â†’, ...)
PLACEHOLDER_RE = r"^description:[ \t]*(.*)\n((?:[ \t]+.*\n?)*)"


HEAD_TEMPLATE = '---\nname: {name}\ndescription: "{desc_q}"\n---\n\n# {title}\n\n{desc}\n\n'


def fix_mojibake(text):
    try:
        return text.encode("cp1252").decode("utf-8") if MOJIBAKE in text else text
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def yaml_description(skill_dir):
    """Read a (possibly folded `>`) top-level description from skill.yaml."""
    y = skill_dir / "skill.yaml"
    if not y.is_file():
        return None
    m = re.search(PLACEHOLDER_RE, y.read_text(encoding="utf-8"), re.M)
    if not m:
        return None
    first = m.group(1).strip()
    if first in (">", ">-", "|", "|-"):
        return " ".join(l.strip() for l in m.group(2).splitlines() if l.strip())
    return first.strip('"')


def summary_from_trigger_text(desc):
    """'Use when the user asks "...". Does X.' -> 'Does X.' (quote-aware sentence split)."""
    if not desc.startswith("Use when"):
        return desc
    in_q = False
    for i, ch in enumerate(desc):
        if ch == '"':
            in_q = not in_q
        elif ch == "." and not in_q and desc[i + 1:i + 2] == " " and desc[i + 2:i + 3].isupper():
            rest = desc[i + 2:].strip()
            return rest if len(rest) > 30 else desc
    return desc


def display_name(name):
    return " ".join(ACRONYMS.get(w, w.capitalize()) for w in name.split("-"))


def read_text(path):
    raw = path.read_bytes().decode("utf-8-sig")
    return raw, ("\r\n" if "\r\n" in raw else "\n")


def write_text(path, text, nl):
    path.write_bytes(text.replace("\r\n", "\n").replace("\n", nl).encode("utf-8"))


def is_runtime(skill_path):
    return any(f"/{d}" in "/" + skill_path for d in RUNTIME_DIRS)


def yaml_info(skill_dir):
    """Minimal skill.yaml reader (no PyYAML): selection.triggers and synapse.domain."""
    y = skill_dir / "skill.yaml"
    if not y.is_file():
        return {}, None
    text = y.read_text(encoding="utf-8")
    sel = {}
    m = re.search(r"^selection:[ \t]*\n((?:[ \t]+.*\n?)+)", text, re.M)
    if m:
        km = re.search(r"^\s+triggers:\s*(\[.*\])\s*$", m.group(1), re.M)
        if km:
            try:
                sel["triggers"] = json.loads(km.group(1))
            except ValueError:
                pass
    dm = re.search(r'^\s+domain:\s*"?([\w-]+)"?', text, re.M)
    return sel, (dm.group(1) if dm else None)


def front_matter_description(skill_md):
    m = re.match(r"---\r?\n(.*?)\r?\n---", skill_md.read_text(encoding="utf-8-sig"), re.S)
    if not m:
        return ""
    d = re.search(r"^description:\s*(.*)$", m.group(1), re.M)
    return d.group(1) if d else ""


def derive_use_cases(skill_dir):
    sel, _ = yaml_info(skill_dir)
    cases = [c for c in sel.get("triggers", []) if c.strip()]
    if not cases:
        desc = front_matter_description(skill_dir / "SKILL.md")
        phrases = re.findall(r'\\?"([^"\\]{6,90})\\?"', desc)
        cases = [p[0].upper() + p[1:] for p in phrases if not p.startswith("/")]
    return cases[:8]


def derive_tags(skill, skill_dir, folder):
    _, domain = yaml_info(skill_dir)
    tags = [t for t in skill["tags"] if t not in DROP_TAGS]
    extra = PROJECT_TAGS.get(folder, []) + [w for w in skill["name"].split("-") if len(w) > 2 and w not in STOP]
    if domain:
        extra.append(domain)
    for w in extra:
        if w not in tags and w not in DROP_TAGS:
            tags.append(w)
    return tags


def ensure_front_matter(skill, version, skill_dir):
    """Add or complete SKILL.md front matter (the hub's install gate / fallback scan)."""
    path = skill_dir / "SKILL.md"
    text, nl = read_text(path)
    text = text.replace("\r\n", "\n")
    desc = skill["description"].replace('"', '\\"')
    if not text.startswith("---"):
        block = f'---\nname: {skill["name"]}\ndescription: "{desc}"\nversion: {version}\n---\n\n'
        write_text(path, block + text, nl)
        return 1
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    changed = 0
    # Keep the description in step with the manifest only when it is still the
    # generated copy of skill.yaml's description; hand-written trigger text stays.
    dm = re.search(r"^description:[ \t]*(.*)$", m.group(1), re.M) if m else None
    old = yaml_description(skill_dir)
    if dm and old and dm.group(1).strip().strip('"').replace('\\"', '"') == old:
        new_line = f'description: "{desc}"'
        if dm.group(0) != new_line:
            text = text[:m.start(1) + dm.start()] + new_line + text[m.start(1) + dm.end():]
            changed = 1
            m = re.match(r"---\n(.*?)\n---", text, re.S)
    if m and not re.search(r"^version:", m.group(1), re.M):
        text = text[:m.end(1)] + f"\nversion: {version}" + text[m.end(1):]
        changed = 1
    if changed:
        write_text(path, text, nl)
    return changed


DEVKIT_LABELS = {
    "qcs6490-rb3gen2-vision-kit": "Dragonwing RB3 Gen 2 Vision Kit",
    "qcs6490-rb3gen2-core-kit": "Dragonwing RB3 Gen 2 Core Kit",
    "qcs6490-rb3gen2-vision-lite-kit": "Dragonwing RB3 Gen 2 Lite Vision Kit",
    "qcs6490-rubikpi3-kit": "RUBIK Pi 3 Development Board",
    "qcs9075-iq-9075-evk": "Dragonwing IQ-9075 EVK",
    "qcs8275-iq-8275-evk-pro": "Dragonwing IQ-8275 EVK",
}
HOST_LABELS = {"windows": "Windows", "linux": "Linux (or WSL)", "macos": "macOS"}
# Repo-relative documents that back each project's compatibility claims.
REFERENCES = {
    ".": [("Delivery models", "skills/project-onboarding/references/DELIVERY_MODELS.md"),
          ("Skills Hub compatibility values", "docs/skills-hub-compatibility-values.md")],
    "AURA": [("AURA README", "AURA/README.md"), ("IQ8 deployment", "AURA/docs/IQ8_DEPLOYMENT.md"),
             ("NPU setup", "AURA/docs/NPU_SETUP.md")],
    "EdgeAgent": [("EdgeAgent README", "EdgeAgent/README.md"), ("Run on IQ8", "EdgeAgent/RUN_ON_IQ8.md"),
                  ("NPU quickstart", "EdgeAgent/devrel_runtime/docs/NPU_QUICKSTART.md")],
    "GesturDJ": [("GesturDJ README", "GesturDJ/README.md"),
                 ("IQ8 SSH runbook", "GesturDJ/ACE-Step/IQ8_SSH_RUNBOOK.md")],
    "QUAD-Client": [("QUAD Client README", "QUAD-Client/README.md")],
    "RoboAgent": [("RoboAgent README", "RoboAgent/README.md")],
    "VSaaS": [("VSaaS README", "VSaaS/README.md"), ("Edge AI notes", "VSaaS/docs/EDGE_AI.md")],
}
MARK_BEGIN, MARK_END = "<!-- skills-hub:begin -->", "<!-- skills-hub:end -->"


def compat_rows(skill, folder):
    """(label, value) rows describing where a skill works; value uses plain language."""
    v = skill["versions"][-1]
    c = v.get("compatibility", {})
    rows = []
    if c.get("devkits"):
        rows.append(("Devkits", ", ".join(f"{DEVKIT_LABELS.get(d, d)} (`{d}`)" for d in c["devkits"])))
    else:
        rows.append(("Devkits", "Not device-specific"))
    for t in c.get("targetOs", []):
        rng = t.get("minVersion", "")
        if t.get("maxVersion") and t["maxVersion"] != rng:
            rng += f" to {t['maxVersion']}"
        rows.append(("Target OS", f"Qualcomm Linux (`{rng}`, `{t['variant']}`)" if t["os"] == "qualcomm_linux"
                     else f"`{t['os']}` (`{rng}`)"))
    if not c.get("targetOs"):
        rows.append(("Target OS", "No target OS constraint declared"))
    rows.append(("Host OS", ", ".join(HOST_LABELS[h] for h in c["hostOs"]) if c.get("hostOs") else "Any"))
    if folder in REQUIREMENTS:
        rows.append(("Requirements", REQUIREMENTS[folder]))
    return rows


def reference_links(folder, base_dir=None):
    """Markdown links to the docs behind a project's compatibility claims.

    With base_dir, links are relative to it (metadata pages in the repo). Without,
    they are absolute GitHub URLs, because an installed SKILL.md is copied out of the repo.
    """
    out = []
    for label, rel in REFERENCES.get(folder, []):
        if (ROOT / rel).is_file():
            href = (Path(os.path.relpath(ROOT / rel, base_dir)).as_posix() if base_dir
                    else f"{HOMEPAGE}/blob/main/{rel}")
            out.append(f"[{label}]({href})")
    return out


def skill_sections(skill, folder, skill_dir):
    lines = [MARK_BEGIN, "", "## Compatibility", "", "| Item | Details |", "| --- | --- |"]
    lines += [f"| {k} | {val} |" for k, val in compat_rows(skill, folder)]
    refs = reference_links(folder)
    if refs:
        lines += ["", "References: " + ", ".join(refs) + "."]
    lines += ["", "## Example prompts", ""] + [f"- {u}" for u in skill["useCases"]] + ["", MARK_END, ""]
    return "\n".join(lines)


def ensure_sections(skill, folder, skill_dir):
    """Append or refresh the generated Compatibility and Example prompts sections of SKILL.md."""
    path = skill_dir / "SKILL.md"
    text, nl = read_text(path)
    text = text.replace("\r\n", "\n")
    block = skill_sections(skill, folder, skill_dir)
    if MARK_BEGIN in text:
        head, rest = text.split(MARK_BEGIN, 1)
        tail = rest.split(MARK_END, 1)[1].lstrip("\n") if MARK_END in rest else ""
        new = head.rstrip("\n") + "\n\n" + block + (("\n" + tail) if tail else "")
    else:
        new = text.rstrip("\n") + "\n\n" + block
    if new == text:
        return 0
    write_text(path, new, nl)
    return 1


def render_catalog(skill, level, folder):
    v = skill["versions"][-1]
    c = v.get("compatibility", {})
    parts = []
    if c.get("devkits"):
        parts.append("devkits " + ", ".join(f"`{d}`" for d in c["devkits"]))
    for t in c.get("targetOs", []):
        rng = t.get("minVersion", "")
        if t.get("maxVersion") and t["maxVersion"] != rng:
            rng += f" to {t['maxVersion']}"
        parts.append(f"target OS `{t['os']}`" + (f" ({rng})" if rng else ""))
    if c.get("hostOs"):
        parts.append("host OS " + ", ".join(f"`{h}`" for h in c["hostOs"]))
    compat = "; ".join(parts) or "portable (no hardware constraint declared)"
    trig = ", ".join(f"`{t['action']}` after `{t['tool']}`" for t in skill.get("triggers", [])) or "none"
    lines = [
        "## Catalog", "",
        f"- **Level:** {level}",
        f"- **Owner:** `{skill['owner']}`",
        f"- **Category:** `{skill['category']}`",
        f"- **Version:** `{v['version']}`",
        f"- **Agents:** {', '.join('`' + a + '`' for a in skill['agents'])}",
        f"- **Tags:** {', '.join('`' + t + '`' for t in skill['tags'])}",
        f"- **License:** `{skill['license']}`",
        f"- **Compatibility:** {compat}",
    ]
    if folder in REQUIREMENTS:
        lines.append(f"- **Requirements:** {REQUIREMENTS[folder]}")
    refs = reference_links(folder, ROOT / folder / "skills-metadata")
    if refs:
        lines.append("- **References:** " + ", ".join(refs))
    lines.append(f"- **Hub triggers:** {trig}")
    return lines


def sync_metadata_md(folder, skill):
    md = ROOT / folder / "skills-metadata" / f"{skill['name']}.md"
    if not md.is_file():
        return 0
    text, nl = read_text(md)
    text = text.replace("\r\n", "\n")
    lm = re.search(r"^- \*\*Level:\*\* (.*)$", text, re.M)
    pm = re.search(r"^(- \*\*Manifest:.*\n- \*\*Procedure:.*)$", text, re.M)
    if not (lm and pm):
        return 0
    desc = skill["description"].replace('"', '\\"')
    head = HEAD_TEMPLATE.format(name=skill["name"], desc_q=desc, title=skill["displayName"], desc=skill["description"])
    body = "\n".join(render_catalog(skill, lm.group(1), folder) + pm.group(1).split("\n"))
    uses = "\n".join(f"- {u}" for u in skill["useCases"])
    new = f"{head}{body}\n\n## Use Cases\n\n{uses}\n"
    if new == text:
        return 0
    write_text(md, new, nl)
    return 1


def enrich(folder, manifest):
    changed = {"useCases": 0, "tags": 0, "frontmatter": 0, "md": 0}
    for s in manifest["skills"]:
        v = s["versions"][-1]
        sdir = ROOT / v["path"]
        s["description"] = fix_mojibake(s["description"])
        if len(s["description"]) < 10:
            s["description"] = yaml_description(sdir) or s["description"]
        s["description"] = summary_from_trigger_text(s["description"])
        if s["displayName"] == s["name"].replace("-", " ").title() or MOJIBAKE in s["displayName"]:
            s["displayName"] = display_name(s["name"])
        if s["useCases"] == [s.get("displayName")]:
            cases = derive_use_cases(sdir)
            if cases:
                s["useCases"] = cases
                changed["useCases"] += 1
        tags = derive_tags(s, sdir, folder)
        if tags != s["tags"]:
            s["tags"] = tags
            changed["tags"] += 1
        if not is_runtime(v["path"]):
            changed["frontmatter"] += ensure_front_matter(s, v["version"], sdir)
            changed["sections"] = changed.get("sections", 0) + ensure_sections(s, folder, sdir)
        changed["md"] += sync_metadata_md(folder, s)
    return changed


def validate(folder, label, manifest):
    problems = []
    seen = set()
    for s in manifest["skills"]:
        n = s.get("name", "?")
        if n in seen:
            problems.append(f"{label}:{n}: duplicate name")
        seen.add(n)
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", n):
            problems.append(f"{label}:{n}: bad name")
        for k in ("owner", "description", "versions"):
            if not s.get(k):
                problems.append(f"{label}:{n}: missing {k}")
        if len(s.get("useCases", [])) < 5:
            problems.append(f"{label}:{n}: fewer than 5 use cases")
        if len(s.get("description", "")) < 60:
            problems.append(f"{label}:{n}: description too short to be self-explanatory")
        for field in ("displayName", "description", *s.get("useCases", [])):
            text = s[field] if field in s else field
            if INTERNAL_TERMS.search(text):
                problems.append(f"{label}:{n}: internal term in public text: {text[:60]}")
        if s.get("category") not in CATEGORIES:
            problems.append(f"{label}:{n}: bad category {s.get('category')}")
        if set(s.get("agents", [])) - HUB_AGENTS:
            problems.append(f"{label}:{n}: unknown agent")
        for t in s.get("triggers", []):
            if t["tool"] not in HUB_TOOLS:
                problems.append(f"{label}:{n}: unknown trigger tool {t['tool']}")
        vers = [v["version"] for v in s.get("versions", [])]
        if len(vers) != len(set(vers)):
            problems.append(f"{label}:{n}: duplicate versions")
        for v in s.get("versions", []):
            doc = ROOT / v.get("docPath", "<none>")
            if not doc.is_file():
                problems.append(f"{label}:{n}: docPath not found {v.get('docPath')}")
            elif not any(f == doc.relative_to(ROOT).as_posix() or
                         (f.endswith("/**") and doc.relative_to(ROOT).as_posix().startswith(f[:-3])) for f in v["files"]):
                problems.append(f"{label}:{n}: files do not cover SKILL.md")
            if any(f.endswith("skill.yaml") for f in v["files"]):
                problems.append(f"{label}:{n}: skill.yaml must not be published")
            if not is_runtime(v["path"]) and MARK_BEGIN not in doc.read_text(encoding="utf-8-sig"):
                problems.append(f"{label}:{n}: SKILL.md lacks Compatibility / Example prompts sections")
            for f in v.get("files", []):
                if f.endswith("/**") and not (ROOT / f[:-3]).is_dir():
                    problems.append(f"{label}:{n}: files glob dir missing {f}")
            if folder != "." and not v.get("path", "").startswith(folder + "/"):
                problems.append(f"{label}:{n}: path is not repo-relative")
            for dk in v.get("compatibility", {}).get("devkits", []):
                if dk not in DEVKITS:
                    problems.append(f"{label}:{n}: unknown devkit {dk}")
    return problems


def main():
    check_only = "--check" in sys.argv
    problems, total = [], 0
    for folder, path in manifests():
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        if not check_only:
            curate(folder, manifest)
            normalize(folder, manifest)
            print(f"{path.relative_to(ROOT).as_posix()}: {enrich(folder, manifest)}")
            path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        total += len(manifest["skills"])
        problems += validate(folder, path.relative_to(ROOT).as_posix(), manifest)
    print(f"{total} skills checked, {len(problems)} problem(s)")
    for p in problems:
        print("  " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
