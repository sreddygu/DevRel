"""
Generate QUAD Capabilities & User Guide (.docx)

Comprehensive document covering:
1. Platform overview & architecture
2. Supported hardware targets
3. 5 MCP tools reference
4. 15 Claude Code skills catalog
5. User guide: getting started, workflows, samples
6. Target board guide (UNO-Q, Rubio Pi, RB5, Android, Windows)
7. KPI testing framework
8. Troubleshooting & FAQ
"""

import os
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Cm, Pt, RGBColor

# ── Colors ──────────────────────────────────────────────────────
QUALCOMM_BLUE = RGBColor(0x32, 0x53, 0xDC)
DARK_GRAY = RGBColor(0x33, 0x33, 0x33)
MEDIUM_GRAY = RGBColor(0x66, 0x66, 0x66)
LIGHT_GRAY = RGBColor(0x99, 0x99, 0x99)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SUCCESS_GREEN = RGBColor(0x1B, 0x7A, 0x3D)
HEADER_BG = "3253DC"
ALT_ROW_BG = "F5F7FA"
HIGHLIGHT_BG = "EEF1FB"
CODE_BG = "1A1A2E"


def shade(cell, color_hex):
    cell._tc.get_or_add_tcPr().append(
        parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    )


def borders_light(table):
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else parse_xml(f'<w:tblPr {nsdecls("w")}/>')
    tblPr.append(parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="4" w:space="0" w:color="DDDDDD"/>'
        f'<w:left w:val="single" w:sz="4" w:space="0" w:color="DDDDDD"/>'
        f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="DDDDDD"/>'
        f'<w:right w:val="single" w:sz="4" w:space="0" w:color="DDDDDD"/>'
        f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="DDDDDD"/>'
        f'<w:insideV w:val="single" w:sz="4" w:space="0" w:color="DDDDDD"/>'
        f'</w:tblBorders>'
    ))


def borders_none(table):
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else parse_xml(f'<w:tblPr {nsdecls("w")}/>')
    tblPr.append(parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        f'<w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        f'<w:bottom w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        f'<w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        f'<w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        f'<w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        f'</w:tblBorders>'
    ))


def p(doc, text, size=11, bold=False, italic=False, color=DARK_GRAY,
      align=WD_ALIGN_PARAGRAPH.LEFT, before=0, after=6, font="Calibri"):
    para = doc.add_paragraph()
    para.alignment = align
    para.paragraph_format.space_before = Pt(before)
    para.paragraph_format.space_after = Pt(after)
    run = para.add_run(text)
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return para


def h1(doc, text):
    heading = doc.add_heading(text, level=1)
    for run in heading.runs:
        run.font.name = "Calibri Light"
        run.font.size = Pt(26)
        run.font.color.rgb = QUALCOMM_BLUE
        run.font.bold = True
    heading.paragraph_format.space_after = Pt(18)
    return heading


def h2(doc, text):
    heading = doc.add_heading(text, level=2)
    for run in heading.runs:
        run.font.name = "Calibri"
        run.font.size = Pt(16)
        run.font.color.rgb = QUALCOMM_BLUE
        run.font.bold = True
    heading.paragraph_format.space_after = Pt(10)
    return heading


def h3(doc, text):
    heading = doc.add_heading(text, level=3)
    for run in heading.runs:
        run.font.name = "Calibri"
        run.font.size = Pt(13)
        run.font.color.rgb = DARK_GRAY
        run.font.bold = True
    heading.paragraph_format.space_after = Pt(8)
    return heading


def bullet(doc, title, desc, indent=1):
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(4)
    para.paragraph_format.space_after = Pt(8)
    para.paragraph_format.left_indent = Cm(indent)
    r1 = para.add_run(title + ": ")
    r1.font.name = "Calibri"
    r1.font.size = Pt(11)
    r1.font.bold = True
    r1.font.color.rgb = DARK_GRAY
    r2 = para.add_run(desc)
    r2.font.name = "Calibri"
    r2.font.size = Pt(11)
    r2.font.color.rgb = MEDIUM_GRAY
    return para


def styled_table(doc, headers, rows, col_widths=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    borders_light(table)
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        rn = cell.paragraphs[0].add_run(h)
        rn.font.name = "Calibri"
        rn.font.size = Pt(10)
        rn.font.bold = True
        rn.font.color.rgb = WHITE
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        shade(cell, HEADER_BG)
    for r_idx, row in enumerate(rows):
        bg = ALT_ROW_BG if r_idx % 2 == 0 else None
        for c_idx, val in enumerate(row):
            cell = table.rows[r_idx + 1].cells[c_idx]
            cell.text = ""
            rn = cell.paragraphs[0].add_run(str(val))
            rn.font.name = "Calibri"
            rn.font.size = Pt(10)
            rn.font.color.rgb = DARK_GRAY
            if c_idx == 0:
                rn.font.bold = True
                rn.font.color.rgb = QUALCOMM_BLUE
            if bg:
                shade(cell, bg)
    if col_widths:
        for i, w in enumerate(col_widths):
            for cell in table.columns[i].cells:
                cell.width = Cm(w)
    return table


def code_box(doc, text):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = t.cell(0, 0)
    shade(cell, CODE_BG)
    cell.text = ""
    pr = cell.paragraphs[0]
    pr.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pr.paragraph_format.space_before = Pt(8)
    pr.paragraph_format.space_after = Pt(8)
    run = pr.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(0x6C, 0xE0, 0x6C)
    for c in t.columns[0].cells:
        c.width = Cm(16)
    borders_none(t)
    return t


def highlight_box(doc, text, bg=HIGHLIGHT_BG):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = t.cell(0, 0)
    shade(cell, bg)
    cell.text = ""
    pr = cell.paragraphs[0]
    pr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pr.paragraph_format.space_before = Pt(14)
    pr.paragraph_format.space_after = Pt(14)
    run = pr.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(13)
    run.font.color.rgb = QUALCOMM_BLUE
    run.font.bold = True
    for c in t.columns[0].cells:
        c.width = Cm(16)
    borders_none(t)
    return t


# ================================================================
# BUILD DOCUMENT
# ================================================================

doc = Document()
style = doc.styles['Normal']
style.font.name = 'Calibri'
style.font.size = Pt(11)
style.font.color.rgb = DARK_GRAY

for section in doc.sections:
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

# ================================================================
# TITLE PAGE
# ================================================================

for _ in range(4):
    doc.add_paragraph().paragraph_format.space_after = Pt(24)

p(doc, "QUAD", size=48, bold=True, color=QUALCOMM_BLUE,
  align=WD_ALIGN_PARAGRAPH.CENTER, font="Calibri Light", after=12)

p(doc, "Qualcomm Unified Agent for Developers", size=20,
  color=DARK_GRAY, align=WD_ALIGN_PARAGRAPH.CENTER,
  font="Calibri Light", after=18)

p(doc, "Capabilities Overview & User Guide", size=16,
  italic=True, color=LIGHT_GRAY, align=WD_ALIGN_PARAGRAPH.CENTER,
  font="Calibri Light", after=36)

sep = doc.add_paragraph()
sep.alignment = WD_ALIGN_PARAGRAPH.CENTER
sep.paragraph_format.space_after = Pt(24)
run = sep.add_run("_" * 60)
run.font.color.rgb = RGBColor(0xDD, 0xDD, 0xDD)
run.font.size = Pt(8)

p(doc, "Version 1.0  |  May 2026  |  Qualcomm Internal", size=11,
  color=MEDIUM_GRAY, align=WD_ALIGN_PARAGRAPH.CENTER, after=36)

p(doc, "Zero to running NPU inference in < 5 minutes",
  size=14, italic=True, color=QUALCOMM_BLUE,
  align=WD_ALIGN_PARAGRAPH.CENTER, font="Calibri Light")

doc.add_page_break()

# ================================================================
# TABLE OF CONTENTS
# ================================================================

h1(doc, "Table of Contents")

toc_items = [
    "1. Platform Overview",
    "2. Architecture",
    "3. Supported Hardware Targets",
    "4. MCP Tools Reference",
    "5. Claude Code Skills Catalog",
    "6. Getting Started",
    "7. Developer Workflows",
    "8. Target Board Guide",
    "9. KPI Testing Framework",
    "10. Sample Applications",
    "11. Troubleshooting & FAQ",
    "12. Appendix: SDK Reference",
]

for item in toc_items:
    p(doc, item, size=12, color=QUALCOMM_BLUE, before=4, after=4)

doc.add_page_break()

# ================================================================
# 1. PLATFORM OVERVIEW
# ================================================================

h1(doc, "1. Platform Overview")

p(doc, "QUAD (Qualcomm Unified Agent for Developers) is a unified AI computing "
  "platform for Qualcomm SoCs. It abstracts 5 separate Qualcomm SDKs behind "
  "a single, natural-language interface powered by the Model Context Protocol (MCP).",
  after=12)

p(doc, "Instead of learning QNN, SNPE, Hexagon SDK, Adreno SDK, and AIMET separately, "
  "developers describe what they want in plain English and QUAD handles hardware "
  "detection, model conversion, profiling, workload orchestration, and code generation "
  "automatically.", after=12)

# Stats row
stats = doc.add_table(rows=1, cols=4)
stats.alignment = WD_TABLE_ALIGNMENT.CENTER
borders_none(stats)
for i, (num, label) in enumerate([
    ("2002+", "Tests Passing"), ("120+", "Python Modules"),
    ("15", "Claude Code Skills"), ("6", "Target Platforms"),
]):
    cell = stats.rows[0].cells[i]
    shade(cell, HIGHLIGHT_BG)
    cell.text = ""
    pr = cell.paragraphs[0]
    pr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pr.paragraph_format.space_before = Pt(10)
    pr.paragraph_format.space_after = Pt(2)
    run = pr.add_run(num)
    run.font.name = "Calibri Light"
    run.font.size = Pt(22)
    run.font.bold = True
    run.font.color.rgb = QUALCOMM_BLUE
    p2 = cell.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_after = Pt(10)
    r2 = p2.add_run(label)
    r2.font.name = "Calibri"
    r2.font.size = Pt(9)
    r2.font.color.rgb = MEDIUM_GRAY

p(doc, "", after=12)

h2(doc, "Key Capabilities")

capabilities = [
    ("Hardware Detection", "Automatic discovery of CPU, GPU, and NPU compute "
     "topology on any Qualcomm SoC with TOPS/TFLOPS ratings and available runtimes"),
    ("Model Conversion", "One-command conversion from ONNX, PyTorch, or TensorFlow "
     "to QNN or SNPE format with INT8/INT4 quantization support"),
    ("Performance Profiling", "Detailed latency, power, memory, and per-layer "
     "analysis with bottleneck identification"),
    ("Workload Orchestration", "Intelligent allocation of inference operations "
     "across CPU, GPU, and NPU based on power budget and performance targets"),
    ("Code Generation", "Platform-specific inference code in C++, Python, Kotlin, "
     "or Arduino sketch with build instructions"),
    ("Natural Language Interface", "All capabilities accessible through plain English "
     "via the Claude Code AI agent \u2014 no SDK API memorization required"),
    ("Multi-Target Deployment", "Seamless deployment from Windows AI PC to IoT boards "
     "(UNO-Q, Rubio Pi, RB5) to Android phones"),
    ("On-Device Testing", "Built-in KPI validation for performance, stability, "
     "power, and functionality on target hardware"),
]

for title, desc in capabilities:
    bullet(doc, title, desc)

doc.add_page_break()

# ================================================================
# 2. ARCHITECTURE
# ================================================================

h1(doc, "2. Architecture")

p(doc, "QUAD is organized as a 7-layer platform stack, from silicon up to "
  "developer experience:", after=12)

styled_table(doc,
    ["Layer", "Component", "Purpose"],
    [
        ["Layer 7", "CLI + IDE Plugins + AI Agent (MCP)", "Developer Interface"],
        ["Layer 6", "Inference Server (QUAD Serve)", "Deployment & Serving"],
        ["Layer 5", "Optimizer (Graph Fusion + Quantization)", "Performance Optimization"],
        ["Layer 4", "Libraries (QualcommDNN + QualcommBLAS)", "Math & AI Operations"],
        ["Layer 3", "Runtime (Device + Tensor + Model + Stream)", "Execution Engine"],
        ["Layer 2", "Compiler (QUAD IR + Portable Binary)", "Compilation & Targeting"],
        ["Layer 1", "Hardware (CPU + GPU + NPU)", "Silicon Execution"],
    ],
    col_widths=[2.5, 10, 4]
)

p(doc, "", after=12)

h2(doc, "SDK Abstraction Layer")

p(doc, "QUAD wraps 5 Qualcomm SDKs behind a unified adapter interface. "
  "The adapter pattern enables mock-first development with hot-swappable "
  "real SDK backends:", after=12)

styled_table(doc,
    ["SDK", "Version", "Purpose", "Platforms"],
    [
        ["QNN / QAIRT", "2.x", "Primary inference runtime", "All"],
        ["SNPE", "2.x", "Deep learning runtime", "Mobile, IoT, Linux"],
        ["Hexagon SDK", "5.x", "DSP/HTP programming", "All (NPU access)"],
        ["Adreno SDK", "\u2014", "GPU compute (OpenCL/Vulkan)", "AI PC, Mobile"],
        ["AIMET", "\u2014", "Model quantization/compression", "AI PC, Mobile"],
    ],
    col_widths=[3, 2, 6, 5]
)

p(doc, "", after=12)

h2(doc, "Two-Repository Architecture")

styled_table(doc,
    ["Repository", "Purpose", "Key Contents"],
    [
        ["QUAD (Server)", "Core platform + MCP server", "5 MCP tools, 7-layer stack, adapters, templates, CLI"],
        ["QUAD-Client", "Client SDK + skills", "Install scripts, 15 skills, doc generators, samples"],
    ],
    col_widths=[3.5, 5, 8]
)

doc.add_page_break()

# ================================================================
# 3. SUPPORTED HARDWARE TARGETS
# ================================================================

h1(doc, "3. Supported Hardware Targets")

p(doc, "QUAD supports 6 target platforms spanning AI PCs, IoT boards, "
  "robotics devices, and mobile phones:", after=12)

styled_table(doc,
    ["Target", "SoC", "NPU", "TOPS", "RAM", "Interface"],
    [
        ["Windows AI PC", "Snapdragon X Elite", "Hexagon V75 (HTP)", "45", "16-32 GB", "Local"],
        ["Arduino UNO Q", "QCS2210", "Hexagon V66 (DSP)", "1.0", "2 GB", "SSH"],
        ["Rubio Pi (RB3 Gen 2)", "QCS6490", "Hexagon V69 (HTP)", "12.0", "8 GB", "SSH"],
        ["Robotics RB5", "QCS8250", "Hexagon V68 (HTP)", "15", "8 GB", "SSH"],
        ["Android Phone", "Snapdragon 8 Elite", "Hexagon V79 (HTP)", "45", "12-16 GB", "ADB"],
        ["Custom Linux", "User-specified", "User-specified", "\u2014", "\u2014", "SSH"],
    ],
    col_widths=[3.5, 3.5, 3, 1.5, 2, 2.5]
)

p(doc, "", after=18)

h2(doc, "Arduino UNO Q (QCS2210)")
p(doc, "Entry-level IoT board ideal for always-on sensing, keyword detection, "
  "and tiny classifiers. 2 GB RAM constrains models to ~500 MB loaded. "
  "The DSP V66 runs INT8 only \u2014 FP32 falls back to CPU at 10x slower. "
  "Managed via SSH with the /quad-unoq skill providing 12 board management "
  "commands including deploy, debug, stability testing, and power profiling.", after=12)

h2(doc, "Rubio Pi / RB3 Gen 2 (QCS6490)")
p(doc, "Mid-range Linux board for vision pipelines, robotics, and LLMs up to "
  "3B parameters. 8 GB RAM and HTP V69 at 12 TOPS provide significant compute "
  "headroom. Supports INT8, INT16, and FP16 inference. Available for cloud "
  "profiling via AI Hub Models as 'QCS6490 (Proxy)'. Same SSH-based deploy workflow as UNO Q.", after=12)

h2(doc, "Windows AI PC (Snapdragon X Elite)")
p(doc, "Primary development target. 45 TOPS NPU with full precision support. "
  "Local execution \u2014 no file transfer needed. Supports large models including "
  "7B parameter LLMs. Default target for most QUAD samples.", after=12)

h2(doc, "Android (Snapdragon 8 Elite)")
p(doc, "Mobile deployment target. 45 TOPS HTP V79 with deployment via ADB. "
  "Build with Kotlin/Java (Android Studio) or C++ (NDK). Thermal-aware power "
  "management critical for sustained mobile workloads.", after=12)

doc.add_page_break()

# ================================================================
# 4. MCP TOOLS REFERENCE
# ================================================================

h1(doc, "4. MCP Tools Reference")

p(doc, "QUAD exposes 5 core tools via the Model Context Protocol. Each tool is "
  "callable through the Claude Code AI agent or programmatically via the "
  "MCP client SDK.", after=12)

tools = [
    {
        "name": "hardware_detect",
        "purpose": "Detect chipset & compute topology",
        "input": "platform (windows | linux | android)",
        "output": "DeviceProfile JSON \u2014 CPU/GPU/NPU specs, RAM, TOPS, available runtimes",
        "example": '"What hardware do I have?"',
    },
    {
        "name": "convert_model",
        "purpose": "Convert ML model to device-optimized format",
        "input": "source_format + model_path + quantization (fp32/int8/int4) + target_sdk",
        "output": "Output DLC/BIN path + compression ratio + op coverage %",
        "example": '"Convert mobilenetv2.onnx to INT8 for QNN"',
    },
    {
        "name": "profile_workload",
        "purpose": "Run profiler, extract structured metrics",
        "input": "model_path + platform + runtime + duration + profiling_level",
        "output": "Latency (mean/p95/p99), throughput, power, memory, per-layer breakdown",
        "example": '"Profile this model on NPU with detailed metrics"',
    },
    {
        "name": "orchestrate_workload",
        "purpose": "Allocate ops across CPU/GPU/NPU",
        "input": "model_path + power_mode (performance/balanced/efficiency)",
        "output": "Per-layer allocation map + projected latency/power + utilization %",
        "example": '"Show me balanced vs performance mode allocation"',
    },
    {
        "name": "generate_code",
        "purpose": "Emit platform-specific inference code",
        "input": "platform + sdk + language (cpp/python/kotlin/arduino_sketch) + model_path",
        "output": "Source files + build instructions + dependency list",
        "example": '"Generate C++ inference code for Windows QNN"',
    },
]

for tool in tools:
    h2(doc, tool["name"])
    bullet(doc, "Purpose", tool["purpose"])
    bullet(doc, "Input", tool["input"])
    bullet(doc, "Output", tool["output"])
    bullet(doc, "Example prompt", tool["example"])
    p(doc, "", after=8)

doc.add_page_break()

# ================================================================
# 5. SKILLS CATALOG
# ================================================================

h1(doc, "5. Claude Code Skills Catalog")

p(doc, "QUAD provides 15 Claude Code skills that orchestrate the MCP tools "
  "into guided workflows. Skills are invoked by natural language or with "
  "slash commands.", after=12)

skills_data = [
    ["quad-quickstart", "New user onboarding", "End-to-end: detect \u2192 convert \u2192 profile \u2192 run"],
    ["quad-detect", "Hardware discovery", "Probe chipset, show TOPS/TFLOPS, runtimes"],
    ["quad-convert", "Model conversion", "ONNX/PyTorch/TF \u2192 QNN/SNPE with calibration guidance"],
    ["quad-profile", "Performance profiling", "Latency, power, memory, bottleneck analysis"],
    ["quad-orchestrate", "Workload allocation", "3-mode comparison: performance/balanced/efficiency"],
    ["quad-codegen", "Code generation", "Platform-specific C++/Python/Kotlin/Arduino code"],
    ["quad-serve", "Inference server", "HTTP API setup with curl examples"],
    ["quad-deploy", "Target deployment", "Push model + runtime to remote device"],
    ["quad-doctor", "Installation diagnosis", "Validate SDK setup, exact fix per warning"],
    ["quad-configure", "Setup wizard", "Interactive quad.toml + .env configuration"],
    ["quad-recommend", "AI recommendations", "Best approach for model + target + use case"],
    ["quad-app-builder", "Full app lifecycle", "Requirements \u2192 impl \u2192 test \u2192 docs \u2192 git push"],
    ["quad-app-document", "Documentation gen", "ARCHITECTURE.md + .docx from running app"],
    ["quad-run-ps1", "Dependency setup", "Generic run.ps1 template for any app"],
    ["quad-unoq", "Board management", "12 commands: status, deploy, debug, perf, stability, power"],
]

styled_table(doc,
    ["Skill", "Category", "What It Does"],
    skills_data,
    col_widths=[3.5, 3.5, 9.5]
)

doc.add_page_break()

# ================================================================
# 6. GETTING STARTED
# ================================================================

h1(doc, "6. Getting Started")

h2(doc, "Step 1: Install QUAD Server")

code_box(doc, "cd QUAD && python -m venv .venv && source .venv/bin/activate\npip install -e .")

p(doc, "", after=12)

h2(doc, "Step 2: Install QUAD Client")

code_box(doc, "cd QUAD-Client && ./install.sh")

p(doc, "The installer creates a .venv, installs dependencies, detects the QUAD "
  "server, and configures Claude Code with the MCP tools.", after=12)

h2(doc, "Step 3: Open Claude Code")

p(doc, "Launch Claude Code in the QUAD-Client directory. The 15 skills and "
  "5 MCP tools will be available automatically.", after=12)

h2(doc, "Step 4: Try Your First Inference")

p(doc, "Use natural language to run the full pipeline:", after=8)

code_box(doc,
    '> "What hardware do I have?"\n'
    '> "Convert mobilenetv2.onnx to INT8 and profile on NPU"\n'
    '> "Build a classification app for Arduino UNO Q"'
)

p(doc, "", after=12)

highlight_box(doc, "Target: Zero to running NPU inference in < 5 minutes")

doc.add_page_break()

# ================================================================
# 7. DEVELOPER WORKFLOWS
# ================================================================

h1(doc, "7. Developer Workflows")

h2(doc, "7.1 Standard Inference Pipeline")

steps = [
    ("1. Detect", "hardware_detect \u2192 discover chipset, NPU specs, available runtimes"),
    ("2. Convert", "convert_model \u2192 ONNX/PyTorch \u2192 QNN/SNPE format with quantization"),
    ("3. Profile", "profile_workload \u2192 latency, power, memory, per-layer breakdown"),
    ("4. Orchestrate", "orchestrate_workload \u2192 allocate ops across CPU/GPU/NPU"),
    ("5. Generate", "generate_code \u2192 platform-specific inference code"),
    ("6. Deploy", "deploy to target device (local, SSH, or ADB)"),
]

for step, desc in steps:
    bullet(doc, step, desc)

p(doc, "", after=12)

h2(doc, "7.2 App Builder Workflow (Full Lifecycle)")

p(doc, "The /quad-app-builder skill orchestrates 8 phases:", after=8)

phases = [
    ["Phase 1", "Requirements & Planning", "Gather ML task, target, model, runtime preferences"],
    ["Phase 2", "Discovery & Pre-flight", "Hardware detect, URL validation, target-specific checks"],
    ["Phase 3", "Implementation", "Convert, profile, orchestrate, codegen, scaffold app + tests"],
    ["Phase 4", "End-to-End Verification", "Install deps, run pytest, run app, on-target smoke test"],
    ["Phase 5", "KPI Validation", "Performance, stability, power testing on target hardware"],
    ["Phase 6", "Documentation", "ARCHITECTURE.md + .docx generation"],
    ["Phase 7", "Final Gate", "Re-run all tests after doc/hardening edits"],
    ["Phase 8", "Git Push", "Branch, commit, push, optional PR creation"],
]

styled_table(doc, ["Phase", "Name", "Activities"], phases, col_widths=[2, 4, 10.5])

p(doc, "", after=12)

h2(doc, "7.3 Remote Target Workflow (IoT/Board)")

p(doc, "For UNO Q, Rubio Pi, RB5, and custom Linux boards:", after=8)

steps_remote = [
    ("1. Configure", "Set up SSH credentials and board profile via /quad-configure or /quad-unoq configure"),
    ("2. Detect", "Probe remote hardware over SSH"),
    ("3. Build", "Cross-compile C++ for ARM64 or prepare Python package on host"),
    ("4. Deploy", "scp artifacts to board workspace"),
    ("5. Validate", "Run single inference on target, verify output"),
    ("6. KPI Test", "Performance benchmarks, 1-hour stability soak, power profiling"),
    ("7. Iterate", "Adjust quantization, power mode, or model based on KPI results"),
]

for step, desc in steps_remote:
    bullet(doc, step, desc)

doc.add_page_break()

# ================================================================
# 8. TARGET BOARD GUIDE
# ================================================================

h1(doc, "8. Target Board Guide")

h2(doc, "8.1 Arduino UNO Q (QCS2210)")

styled_table(doc,
    ["Attribute", "Value"],
    [
        ["SoC", "QCS2210"],
        ["CPU", "4x Kryo @ 2.0 GHz (ARM64)"],
        ["GPU", "Adreno 504 (0.4 TFLOPS)"],
        ["NPU", "Hexagon DSP V66 (1.0 TOPS)"],
        ["RAM", "2 GB"],
        ["Interface", "SSH (primary), Serial/UART (recovery)"],
        ["SDK", "SNPE 2.x"],
        ["Skel Library", "libSnpeDspV66Skel.so"],
        ["Quantization", "INT8 mandatory for DSP (FP32 \u2192 CPU fallback)"],
        ["Power Envelope", "< 2W sustained"],
        ["Max Model Size", "~500 MB loaded, ~200 MB on disk"],
        ["Use Cases", "Always-on sensing, keyword detection, tiny classifiers"],
    ],
    col_widths=[4, 12.5]
)

p(doc, "", after=12)

h3(doc, "UNO Q Management Commands (/quad-unoq)")

unoq_cmds = [
    ["status", "Board health, resources, thermal, DSP state"],
    ["configure", "Interactive SSH/board setup \u2192 quad.toml"],
    ["deploy", "Build, push, validate pipeline"],
    ["firmware", "Flash/update with serial fallback"],
    ["logs", "Extract dmesg, SNPE, DSP trace, crash dumps"],
    ["debug", "Systematic troubleshooting with failure table"],
    ["perf", "Latency/throughput benchmarks with KPI pass/fail"],
    ["stability", "1-hour soak test, memory leak detection"],
    ["power", "Per-mode power measurement"],
    ["app", "Start/stop/status of deployed services"],
    ["ota", "Fleet update + rollback"],
    ["test", "Combined KPI report across all categories"],
]

styled_table(doc, ["Command", "Purpose"], unoq_cmds, col_widths=[3, 13.5])

p(doc, "", after=12)

h2(doc, "8.2 Rubio Pi / RB3 Gen 2 (QCS6490)")

styled_table(doc,
    ["Attribute", "Value"],
    [
        ["SoC", "QCS6490"],
        ["CPU", "Kryo 670 @ 2.7 GHz"],
        ["GPU", "Adreno 643 (1.5 TFLOPS)"],
        ["NPU", "Hexagon V69 (HTP) \u2014 12.0 TOPS"],
        ["RAM", "8 GB"],
        ["Interface", "SSH"],
        ["SDK", "QNN 2.x (preferred) or SNPE 2.x"],
        ["Skel Library", "libQnnHtpV69Skel.so / libSnpeHtpV69Skel.so"],
        ["Quantization", "INT8, INT16, FP16"],
        ["Power Envelope", "< 5W sustained"],
        ["Max Model Size", "~2 GB loaded, ~1 GB on disk"],
        ["Cloud Profiling", "AI Hub Models \u2014 'QCS6490 (Proxy)'"],
        ["Use Cases", "Vision pipelines, LLMs (1-3B), robotics, multi-model"],
    ],
    col_widths=[4, 12.5]
)

doc.add_page_break()

h2(doc, "8.3 Robotics RB5 (QCS8250)")

styled_table(doc,
    ["Attribute", "Value"],
    [
        ["SoC", "QCS8250"],
        ["NPU", "Hexagon V68 (HTP) \u2014 15 TOPS"],
        ["RAM", "8 GB"],
        ["SDK", "QNN 2.x"],
        ["Use Cases", "Drones, autonomous robots, edge gateways"],
    ],
    col_widths=[4, 12.5]
)

p(doc, "", after=12)

h2(doc, "8.4 Common SSH Setup (All Linux Boards)")

code_box(doc,
    "# quad.toml configuration for remote boards\n"
    "[target]\n"
    'type = "linux-ssh"\n'
    'board = "arduino-unoq"    # or "rubio-pi", "rb5"\n'
    'soc = "qcs2210"           # or "qcs6490", "qcs8250"\n\n'
    "[target.ssh]\n"
    'host = "192.168.1.42"\n'
    'user = "root"\n'
    'key = "~/.ssh/id_rsa"\n'
    "port = 22\n\n"
    "[target.paths]\n"
    'workspace = "/data/local/tmp/quad/"'
)

doc.add_page_break()

# ================================================================
# 9. KPI TESTING FRAMEWORK
# ================================================================

h1(doc, "9. KPI Testing Framework")

p(doc, "Every application deployed to a target board should be validated across "
  "four KPI categories: functionality, performance, stability, and power.", after=12)

h2(doc, "9.1 Performance KPIs")

styled_table(doc,
    ["Target", "Latency P50", "Latency P99", "Throughput", "Init Time"],
    [
        ["UNO Q (QCS2210)", "< 33 ms", "< 50 ms", "> 30 fps", "< 2 s"],
        ["Rubio Pi (QCS6490)", "< 15 ms", "< 25 ms", "> 60 fps", "< 1.5 s"],
        ["Windows X Elite", "< 10 ms", "< 20 ms", "> 100 fps", "< 1 s"],
        ["Android 8 Elite", "< 10 ms", "< 15 ms", "> 100 fps", "< 1 s"],
        ["RB5 (QCS8250)", "< 20 ms", "< 35 ms", "> 45 fps", "< 1.5 s"],
    ],
    col_widths=[4, 3, 3, 3, 3.5]
)

p(doc, "(Thresholds above are for typical small models like MobileNetV2. "
  "Scale expectations for larger models.)", size=10, italic=True,
  color=MEDIUM_GRAY, after=12)

h2(doc, "9.2 Stability KPIs")

styled_table(doc,
    ["Metric", "Target", "Duration"],
    [
        ["Success rate", "> 99.9%", "1 hour soak test"],
        ["Memory leak", "< 5 MB growth/hour", "RSS monitoring"],
        ["Thermal stability", "< 75\u00b0C sustained", "Continuous thermal zone read"],
        ["DSP crashes", "0 remoteproc restarts", "dmesg monitoring"],
        ["Latency drift", "< 10% P99 increase", "Compare first vs last 5 min"],
    ],
    col_widths=[4, 5, 7.5]
)

p(doc, "", after=12)

h2(doc, "9.3 Power KPIs")

styled_table(doc,
    ["Target", "balanced Mode", "low_balanced", "high_performance", "burst (benchmark only)"],
    [
        ["UNO Q", "1.0 W", "0.5 W", "1.2 W", "1.5 W"],
        ["Rubio Pi", "3.0 W", "1.5 W", "5.0 W", "6.0 W"],
        ["RB5", "4.0 W", "2.0 W", "5.0 W", "6.5 W"],
    ],
    col_widths=[3, 3.5, 3, 3.5, 3.5]
)

p(doc, "", after=12)

h2(doc, "9.4 End-to-End Test Report")

p(doc, "The /quad-unoq test command generates a combined KPI report:", after=8)

code_box(doc,
    "UNO-Q Test Report \u2014 2026-05-15 14:30\n"
    "Model:       mobilenetv2_int8.dlc\n"
    "Board:       Arduino UNO Q (192.168.1.42)\n"
    "Runtime:     SNPE 2.x / DSP V66\n"
    "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
    "Functionality   PASS    Top-1 acc 71.2%\n"
    "Performance     PASS    P50=28ms, 34 fps\n"
    "Stability       PASS    99.97% (1h soak)\n"
    "Power           PASS    0.8W balanced\n"
    "Recovery        PASS    DSP restart OK\n"
    "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
    "Overall:        PASS (5/5)"
)

doc.add_page_break()

# ================================================================
# 10. SAMPLE APPLICATIONS
# ================================================================

h1(doc, "10. Sample Applications")

h2(doc, "MobileNetV2 Image Classification")

p(doc, "The reference sample application demonstrates the full QUAD workflow:", after=8)

bullet(doc, "Location", "samples/mobilenetv2/")
bullet(doc, "Task", "ImageNet classification (1000 classes)")
bullet(doc, "Model", "MobileNetV2 ONNX (14 MB)")
bullet(doc, "Runtimes", "CPU, GPU (Adreno), NPU (Hexagon HTP)")
bullet(doc, "Features", "Three-way benchmark, graceful degradation, UTF-8 output")

p(doc, "", after=8)

code_box(doc,
    "cd samples/mobilenetv2\n"
    ".\\run.ps1                                # Install deps\n"
    ".venv\\Scripts\\python.exe run_mobilenetv2.py   # Run benchmark"
)

p(doc, "", after=12)

h2(doc, "Whisper ASR (Speech Recognition)")

bullet(doc, "Location", "samples/whisper_asr/")
bullet(doc, "Task", "Automatic speech recognition with Whisper-tiny")
bullet(doc, "Features", "INT8 calibration, CPU/GPU/NPU benchmark, mel spectrogram pipeline")

p(doc, "", after=12)

h2(doc, "Building Your Own App")

p(doc, "Use the /quad-app-builder skill for a guided experience:", after=8)

code_box(doc,
    '> "Build a detection app for YOLOv8 on Rubio Pi"\n'
    '> "Create an ASR app for Whisper on Arduino UNO Q"\n'
    '> "Scaffold a classification app for MobileNet on Windows"'
)

doc.add_page_break()

# ================================================================
# 11. TROUBLESHOOTING
# ================================================================

h1(doc, "11. Troubleshooting & FAQ")

h2(doc, "Common Issues")

issues = [
    ["SSH connection refused", "Check network, verify sshd running on board, try serial console"],
    ["Failed to load DSP", "Push skel library to /usr/lib/rfsa/adsp/ on device"],
    ["SNPE_ERROR_RUNTIME_INIT", "DSP signature mismatch \u2014 sign skel or use testsig"],
    ["Out of memory", "Quantize to INT8, reduce batch size, use smaller model"],
    ["Inference timeout / hang", "Reboot DSP via remoteproc, check model compatibility"],
    ["Conversion timeout at 60s", "Increase timeout to 600s \u2014 qairt-quantizer needs time"],
    ["INT8 quantizer hangs", "Need real calibration data, not random \u2014 fall back to FP32"],
    ["Thermal shutdown", "Reduce perf_profile to balanced, add heatsink, reduce duty cycle"],
    ["pip: externally managed", "Use .venv (install.sh creates one automatically)"],
]

styled_table(doc, ["Issue", "Resolution"], issues, col_widths=[5, 11.5])

p(doc, "", after=12)

h2(doc, "Diagnostic Tool")

p(doc, "Run /quad-doctor for automated diagnosis:", after=8)

code_box(doc, 'quad-client doctor --project-root /path/to/project')

doc.add_page_break()

# ================================================================
# 12. APPENDIX
# ================================================================

h1(doc, "12. Appendix: SDK Reference")

h2(doc, "Hexagon Version Mapping")

styled_table(doc,
    ["SoC", "Hexagon Version", "Skel Library"],
    [
        ["QCS2210 (UNO Q)", "V66", "libSnpeDspV66Skel.so"],
        ["QCS8250 (RB5)", "V68", "libSnpeHtpV68Skel.so"],
        ["QCS6490 (Rubio Pi)", "V69", "libSnpeHtpV69Skel.so / libQnnHtpV69Skel.so"],
        ["Snapdragon X Elite", "V75", "libSnpeHtpV75Skel.so"],
        ["Snapdragon 8 Elite", "V79", "libSnpeHtpV79Skel.so"],
    ],
    col_widths=[4.5, 3.5, 8.5]
)

p(doc, "", after=12)

h2(doc, "Power Profile Modes")

styled_table(doc,
    ["Mode", "When to Use", "Typical Power Impact"],
    [
        ["low_balanced", "Always-on sensing, battery-critical", "50% of balanced"],
        ["balanced", "Default for sustained workloads", "Baseline"],
        ["high_performance", "Real-time requirements, plugged in", "1.5x balanced"],
        ["burst", "Benchmarking ONLY (thermal limit)", "2x balanced"],
    ],
    col_widths=[3.5, 7, 6]
)

p(doc, "", after=12)

h2(doc, "Quantization Quick Reference")

styled_table(doc,
    ["Mode", "Calibration", "Best For", "NPU Support"],
    [
        ["FP32", "None needed", "First-time conversion, development", "All HTP versions"],
        ["INT8", "32+ real samples", "Production, latency-critical", "All (mandatory for V66 DSP)"],
        ["INT16", "Optional", "Accuracy-sensitive with some speedup", "V68+"],
        ["FP16", "None needed", "Good accuracy with 2x speedup", "V68+"],
        ["INT4", "Required + AIMET", "LLMs, aggressive compression", "V75+"],
    ],
    col_widths=[2, 3, 5.5, 6]
)

p(doc, "", after=24)

# Footer
sep2 = doc.add_paragraph()
sep2.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = sep2.add_run("_" * 60)
run.font.color.rgb = RGBColor(0xDD, 0xDD, 0xDD)
run.font.size = Pt(8)

p(doc, "QUAD  |  Qualcomm Unified Agent for Developers  |  May 2026",
  size=10, color=LIGHT_GRAY, align=WD_ALIGN_PARAGRAPH.CENTER)

# ================================================================
# SAVE
# ================================================================

# Script lives in tools/; the generated doc belongs in docs/ (sibling dir).
output_path = str(Path(__file__).resolve().parent.parent / "docs" / "QUAD_Capabilities_and_User_Guide.docx")
doc.save(output_path)
print(f"Document saved to: {output_path}")
print(f"File size: {os.path.getsize(output_path) / 1024:.1f} KB")
