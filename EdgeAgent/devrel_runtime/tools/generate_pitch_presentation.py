"""
Generate DevRel Pitch Presentation (.pptx)

Executive pitch deck covering:
1. Title slide
2. The Problem — SDK fragmentation
3. The Solution — DevRel unified platform
4. Architecture — 7-layer stack
5. Supported Hardware — 6 target platforms
6. 5 MCP Tools — what they do
7. Developer Experience — 15 skills
8. Competitive Advantage — DevRel vs CUDA
9. Differentiators — what CUDA can never do
10. IoT & Board Ecosystem
11. Platform Status — metrics
12. KPI Testing Framework
13. User Journey — zero to inference
14. The Ask — what we need
15. Call to Action
"""

import os
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# ── Colors ──────────────────────────────────────────────────────
QBLUE = RGBColor(0x32, 0x53, 0xDC)
DARK = RGBColor(0x33, 0x33, 0x33)
MED = RGBColor(0x66, 0x66, 0x66)
LIGHT = RGBColor(0x99, 0x99, 0x99)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BG_DARK = RGBColor(0x1A, 0x1A, 0x2E)
BG_LIGHT = RGBColor(0xF5, 0xF7, 0xFA)
GREEN = RGBColor(0x1B, 0x7A, 0x3D)
HIGHLIGHT = RGBColor(0xEE, 0xF1, 0xFB)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


def add_slide(prs, layout_idx=6):
    """Add a blank slide."""
    layout = prs.slide_layouts[layout_idx]
    return prs.slides.add_slide(layout)


def add_bg(slide, color):
    """Set solid background color."""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_text(slide, text, left, top, width, height, size=18, bold=False,
             italic=False, color=DARK, align=PP_ALIGN.LEFT, font="Calibri"):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    para = tf.paragraphs[0]
    para.text = text
    para.font.size = Pt(size)
    para.font.bold = bold
    para.font.italic = italic
    para.font.color.rgb = color
    para.font.name = font
    para.alignment = align
    return txBox


def add_multiline(slide, lines, left, top, width, height, size=16,
                  color=DARK, line_space=1.2, bullet=False):
    """Add multiple lines of text."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, (text, text_bold, text_color) in enumerate(lines):
        if i == 0:
            para = tf.paragraphs[0]
        else:
            para = tf.add_paragraph()
        prefix = "\u2022 " if bullet else ""
        para.text = prefix + text
        para.font.size = Pt(size)
        para.font.bold = text_bold
        para.font.color.rgb = text_color
        para.font.name = "Calibri"
        para.space_after = Pt(size * 0.5)
    return txBox


def add_rect(slide, left, top, width, height, fill_color, text="",
             font_size=14, font_color=WHITE, bold=False, align=PP_ALIGN.CENTER):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    if text:
        tf = shape.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = text
        p.font.size = Pt(font_size)
        p.font.color.rgb = font_color
        p.font.bold = bold
        p.font.name = "Calibri"
        p.alignment = align
        tf.paragraphs[0].space_before = Pt(4)
    return shape


def add_table(slide, left, top, width, height, headers, rows):
    """Add a styled table."""
    tbl_shape = slide.shapes.add_table(
        len(rows) + 1, len(headers), left, top, width, height
    )
    table = tbl_shape.table

    # Header row
    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = h
        for para in cell.text_frame.paragraphs:
            para.font.size = Pt(12)
            para.font.bold = True
            para.font.color.rgb = WHITE
            para.font.name = "Calibri"
            para.alignment = PP_ALIGN.CENTER
        cell.fill.solid()
        cell.fill.fore_color.rgb = QBLUE

    # Data rows
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            cell = table.cell(r_idx + 1, c_idx)
            cell.text = str(val)
            for para in cell.text_frame.paragraphs:
                para.font.size = Pt(11)
                para.font.color.rgb = DARK
                para.font.name = "Calibri"
            if r_idx % 2 == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = BG_LIGHT

    return tbl_shape


# ================================================================
# CREATE PRESENTATION
# ================================================================

prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H

# ================================================================
# SLIDE 1: TITLE
# ================================================================

slide = add_slide(prs)
add_bg(slide, BG_DARK)

add_text(slide, "DevRel", Inches(1), Inches(1.5), Inches(11), Inches(1.5),
         size=60, bold=True, color=WHITE, align=PP_ALIGN.CENTER, font="Calibri Light")

add_text(slide, "Qualcomm Unified Agent for Developers",
         Inches(1), Inches(3.0), Inches(11), Inches(0.8),
         size=24, color=RGBColor(0xAA, 0xBB, 0xFF), align=PP_ALIGN.CENTER,
         font="Calibri Light")

add_text(slide, "A Unified AI Computing Platform for Qualcomm SoCs",
         Inches(1), Inches(3.8), Inches(11), Inches(0.6),
         size=18, color=LIGHT, align=PP_ALIGN.CENTER, font="Calibri Light")

# Stat boxes
stats = [("2002+", "Tests"), ("120+", "Modules"), ("15", "Skills"),
         ("6", "Platforms"), ("45", "TOPS (Max)")]
for i, (num, label) in enumerate(stats):
    x = Inches(1.5 + i * 2.2)
    add_rect(slide, x, Inches(5.2), Inches(1.8), Inches(1.0), QBLUE,
             f"{num}\n{label}", font_size=16, bold=True)

add_text(slide, "May 2026  |  Qualcomm Internal",
         Inches(1), Inches(6.8), Inches(11), Inches(0.4),
         size=12, color=LIGHT, align=PP_ALIGN.CENTER)

# ================================================================
# SLIDE 2: THE PROBLEM
# ================================================================

slide = add_slide(prs)
add_text(slide, "The Problem: Developer Friction", Inches(0.8), Inches(0.4),
         Inches(11), Inches(0.8), size=32, bold=True, color=QBLUE, font="Calibri Light")

problems = [
    ("SDK Sprawl", "5 separate SDKs (QNN, SNPE, Hexagon, Adreno, AIMET) \u2014 each with its own setup, API, and learning curve"),
    ("Manual Profiling", "3+ separate profiling tools with no unified view of CPU, GPU, and NPU utilization"),
    ("No Unified Model", "Different workflows for every chipset and platform combination"),
    ("High Barrier to Entry", "Time to First Inference (TTFI) currently takes DAYS"),
]

for i, (title, desc) in enumerate(problems):
    y = Inches(1.6 + i * 1.3)
    add_rect(slide, Inches(0.8), y, Inches(2.5), Inches(1.0), QBLUE,
             title, font_size=16, bold=True)
    add_text(slide, desc, Inches(3.6), y, Inches(8.5), Inches(1.0),
             size=15, color=MED)

# TTFI box
add_rect(slide, Inches(2), Inches(6.2), Inches(9), Inches(0.8),
         RGBColor(0xEE, 0xF1, 0xFB),
         "Current TTFI: Several Days  \u2192  Target: < 5 Minutes",
         font_size=18, font_color=QBLUE, bold=True)

# ================================================================
# SLIDE 3: THE SOLUTION
# ================================================================

slide = add_slide(prs)
add_text(slide, "DevRel: One Platform. All Qualcomm Silicon.",
         Inches(0.8), Inches(0.4), Inches(11), Inches(0.8),
         size=32, bold=True, color=QBLUE, font="Calibri Light")

add_text(slide, "5 SDKs abstracted behind a single natural-language interface",
         Inches(0.8), Inches(1.2), Inches(11), Inches(0.5),
         size=16, color=MED, italic=True)

# Architecture layers
layers = [
    ("Layer 7", "CLI + IDE + AI Agent (MCP)"),
    ("Layer 6", "Inference Server (DevRel Serve)"),
    ("Layer 5", "Optimizer (Graph Fusion + Quantization)"),
    ("Layer 4", "Libraries (QualcommDNN + QualcommBLAS)"),
    ("Layer 3", "Runtime (Device + Tensor + Model)"),
    ("Layer 2", "Compiler (DevRel IR + Portable Binary)"),
    ("Layer 1", "Hardware (CPU + GPU + NPU)"),
]

for i, (layer, component) in enumerate(layers):
    y = Inches(1.9 + i * 0.72)
    shade_color = QBLUE if i < 3 else RGBColor(0x44, 0x66, 0xE8) if i < 5 else RGBColor(0x55, 0x77, 0xF0)
    add_rect(slide, Inches(1.5), y, Inches(2.0), Inches(0.55), shade_color,
             layer, font_size=13, bold=True)
    add_rect(slide, Inches(3.7), y, Inches(7.5), Inches(0.55),
             BG_LIGHT, component, font_size=13, font_color=DARK)

# ================================================================
# SLIDE 4: SUPPORTED HARDWARE
# ================================================================

slide = add_slide(prs)
add_text(slide, "6 Target Platforms",
         Inches(0.8), Inches(0.4), Inches(11), Inches(0.8),
         size=32, bold=True, color=QBLUE, font="Calibri Light")

add_table(slide, Inches(0.5), Inches(1.5), Inches(12.3), Inches(4.5),
    ["Target", "SoC", "NPU", "TOPS", "RAM", "Interface"],
    [
        ["Windows AI PC", "Snapdragon X Elite", "Hexagon V75", "45", "16-32 GB", "Local"],
        ["Arduino UNO Q", "QCS2210", "Hexagon V66 (DSP)", "1.0", "2 GB", "SSH"],
        ["Rubio Pi (RB3 Gen 2)", "QCS6490", "Hexagon V69 (HTP)", "12", "8 GB", "SSH"],
        ["Robotics RB5", "QCS8250", "Hexagon V68 (HTP)", "15", "8 GB", "SSH"],
        ["Android Phone", "Snapdragon 8 Elite", "Hexagon V79 (HTP)", "45", "12-16 GB", "ADB"],
        ["Custom Linux", "User-specified", "User-specified", "\u2014", "\u2014", "SSH"],
    ]
)

add_text(slide, "Same DevRel API across all platforms. Build once, deploy anywhere.",
         Inches(0.8), Inches(6.5), Inches(11), Inches(0.5),
         size=16, italic=True, color=QBLUE, align=PP_ALIGN.CENTER)

# ================================================================
# SLIDE 5: 5 MCP TOOLS
# ================================================================

slide = add_slide(prs)
add_text(slide, "5 Core MCP Tools",
         Inches(0.8), Inches(0.4), Inches(11), Inches(0.8),
         size=32, bold=True, color=QBLUE, font="Calibri Light")

tools = [
    ("hardware_detect", "Discover chipset, NPU specs, available runtimes"),
    ("convert_model", "ONNX/PyTorch/TF \u2192 QNN/SNPE with INT8/INT4"),
    ("profile_workload", "Latency, power, memory, per-layer analysis"),
    ("orchestrate_workload", "CPU/GPU/NPU allocation by power mode"),
    ("generate_code", "C++, Python, Kotlin, Arduino sketch + build instructions"),
]

for i, (name, desc) in enumerate(tools):
    y = Inches(1.6 + i * 1.1)
    add_rect(slide, Inches(0.8), y, Inches(3.5), Inches(0.8), QBLUE,
             name, font_size=15, bold=True)
    add_text(slide, desc, Inches(4.6), y, Inches(7.5), Inches(0.8),
             size=15, color=MED)

# ================================================================
# SLIDE 6: DEVELOPER EXPERIENCE
# ================================================================

slide = add_slide(prs)
add_text(slide, "15 Claude Code Skills",
         Inches(0.8), Inches(0.4), Inches(11), Inches(0.8),
         size=32, bold=True, color=QBLUE, font="Calibri Light")

add_text(slide, "Natural language workflows \u2014 no SDK memorization required",
         Inches(0.8), Inches(1.2), Inches(11), Inches(0.4),
         size=16, color=MED, italic=True)

skills_grid = [
    ["devrel-quickstart", "devrel-detect", "devrel-convert", "devrel-profile", "devrel-orchestrate"],
    ["devrel-codegen", "devrel-serve", "devrel-deploy", "devrel-doctor", "devrel-configure"],
    ["devrel-recommend", "devrel-app-builder", "devrel-app-document", "devrel-run-ps1", "devrel-unoq"],
]

for row_idx, row in enumerate(skills_grid):
    for col_idx, skill in enumerate(row):
        x = Inches(0.5 + col_idx * 2.5)
        y = Inches(2.0 + row_idx * 1.5)
        bg = QBLUE if row_idx == 0 else RGBColor(0x44, 0x66, 0xE8) if row_idx == 1 else RGBColor(0x55, 0x77, 0xF0)
        add_rect(slide, x, y, Inches(2.3), Inches(1.1), bg,
                 skill, font_size=13, bold=True)

# Category labels
add_text(slide, "Core Pipeline", Inches(0.5), Inches(1.7), Inches(3), Inches(0.3),
         size=11, color=LIGHT, italic=True)
add_text(slide, "Deploy & Manage", Inches(0.5), Inches(3.2), Inches(3), Inches(0.3),
         size=11, color=LIGHT, italic=True)
add_text(slide, "Build & Document", Inches(0.5), Inches(4.7), Inches(3), Inches(0.3),
         size=11, color=LIGHT, italic=True)

# ================================================================
# SLIDE 7: DevRel vs CUDA
# ================================================================

slide = add_slide(prs)
add_text(slide, "Where DevRel Wins",
         Inches(0.8), Inches(0.4), Inches(11), Inches(0.8),
         size=32, bold=True, color=QBLUE, font="Calibri Light")

add_table(slide, Inches(0.8), Inches(1.5), Inches(11.5), Inches(4.5),
    ["Dimension", "CUDA", "DevRel"],
    [
        ["Market", "Data center / HPC", "Edge / Mobile / AI PC / IoT"],
        ["Compute", "GPU only", "CPU + GPU + NPU (heterogeneous)"],
        ["Power", "300\u2013700W", "1\u201315W (power as a feature)"],
        ["Devices", "Millions of GPUs", "Billions of SoCs"],
        ["Differentiator", "Raw throughput", "Performance-per-watt + AI agent"],
        ["Developer UX", "Manual SDK integration", "Natural language (MCP)"],
    ]
)

add_rect(slide, Inches(2), Inches(6.3), Inches(9), Inches(0.8),
         RGBColor(0xEE, 0xF1, 0xFB),
         "Qualcomm ships 3+ BILLION SoCs/year. CUDA reaches millions. DevRel reaches billions.",
         font_size=16, font_color=QBLUE, bold=True)

# ================================================================
# SLIDE 8: DIFFERENTIATORS
# ================================================================

slide = add_slide(prs)
add_text(slide, "What CUDA Can Never Do",
         Inches(0.8), Inches(0.4), Inches(11), Inches(0.8),
         size=32, bold=True, color=QBLUE, font="Calibri Light")

diffs = [
    ("Power-Aware Computing", "Every API accepts power budget as a constraint. DevRel optimizes across CPU, GPU, and NPU within thermal envelopes."),
    ("AI Agent (MCP)", "Natural language to production code in seconds. No SDK memorization."),
    ("Heterogeneous Orchestration", "CPU + GPU + NPU scheduling in a single API call."),
    ("Edge-Native Design", "Built for 1\u201315W devices with thermal-aware scheduling."),
]

for i, (title, desc) in enumerate(diffs):
    col = i % 2
    row = i // 2
    x = Inches(0.8 + col * 6.2)
    y = Inches(1.5 + row * 2.8)
    add_rect(slide, x, y, Inches(5.8), Inches(0.6), QBLUE,
             f"{i+1}. {title}", font_size=15, bold=True, align=PP_ALIGN.LEFT)
    add_text(slide, desc, x + Inches(0.2), y + Inches(0.7), Inches(5.4), Inches(1.5),
             size=13, color=MED)

# ================================================================
# SLIDE 9: IoT & BOARD ECOSYSTEM
# ================================================================

slide = add_slide(prs)
add_text(slide, "IoT & Board Ecosystem",
         Inches(0.8), Inches(0.4), Inches(11), Inches(0.8),
         size=32, bold=True, color=QBLUE, font="Calibri Light")

add_table(slide, Inches(0.5), Inches(1.5), Inches(12.3), Inches(4.0),
    ["Board", "SoC", "TOPS", "Use Case", "Management"],
    [
        ["Arduino UNO Q", "QCS2210", "1.0", "Always-on sensing, tiny classifiers", "/devrel-unoq (12 commands)"],
        ["Rubio Pi (RB3 Gen 2)", "QCS6490", "12", "Vision pipelines, 1-3B LLMs, robotics", "SSH + AI Hub Models cloud profiling"],
        ["Robotics RB5", "QCS8250", "15", "Drones, autonomous robots, edge gateways", "SSH-based management"],
    ]
)

add_text(slide, "Same deploy workflow: configure \u2192 detect \u2192 build \u2192 deploy \u2192 KPI test",
         Inches(0.8), Inches(6.0), Inches(11), Inches(0.5),
         size=16, italic=True, color=QBLUE, align=PP_ALIGN.CENTER)

# Full IoT coverage note
add_text(slide, "111 IoT components across 14 categories cataloged (see IOT_DEPENDENCIES.xlsx)",
         Inches(0.8), Inches(6.5), Inches(11), Inches(0.4),
         size=12, color=LIGHT, align=PP_ALIGN.CENTER)

# ================================================================
# SLIDE 10: PLATFORM STATUS
# ================================================================

slide = add_slide(prs)
add_text(slide, "Platform Status: Feature-Complete",
         Inches(0.8), Inches(0.4), Inches(11), Inches(0.8),
         size=32, bold=True, color=QBLUE, font="Calibri Light")

# Phase status
add_table(slide, Inches(0.8), Inches(1.5), Inches(11.5), Inches(3.5),
    ["Phase", "Name", "Status", "Completion"],
    [
        ["Phase A", "Foundation (MCP Agent)", "COMPLETE", "100%"],
        ["Phase B", "Runtime & Compiler", "COMPLETE", "100%"],
        ["Phase C", "Libraries & Optimizer", "COMPLETE", "100%"],
        ["Phase D", "Deep Profiler", "COMPLETE", "100%"],
        ["Phase E", "Kernels & Streams", "COMPLETE", "100%"],
        ["Phase F", "Serve & Deploy", "COMPLETE", "100%"],
        ["Phase G", "Ecosystem", "COMPLETE", "100%"],
    ]
)

add_text(slide, "All 7 phases complete in mock mode. Real hardware integration: Q3\u2013Q4 2026.",
         Inches(0.8), Inches(5.5), Inches(11), Inches(0.5),
         size=16, italic=True, color=MED, align=PP_ALIGN.CENTER)

# Stats at bottom
stats2 = [("2002+", "Tests Passing"), ("120+", "Python Modules"),
          ("25,000+", "Lines of Code"), ("30+", "Code Templates")]
for i, (num, label) in enumerate(stats2):
    x = Inches(1.0 + i * 3.0)
    add_rect(slide, x, Inches(6.1), Inches(2.5), Inches(0.9),
             RGBColor(0xEE, 0xF1, 0xFB),
             f"{num}\n{label}", font_size=14, font_color=QBLUE, bold=True)

# ================================================================
# SLIDE 11: KPI TESTING
# ================================================================

slide = add_slide(prs)
add_text(slide, "KPI Testing Framework",
         Inches(0.8), Inches(0.4), Inches(11), Inches(0.8),
         size=32, bold=True, color=QBLUE, font="Calibri Light")

add_text(slide, "Every deployment validated across 4 KPI categories",
         Inches(0.8), Inches(1.2), Inches(11), Inches(0.4),
         size=16, color=MED, italic=True)

# 4 KPI boxes
kpis = [
    ("Functionality", "Correct inference output\nmatches golden reference\nTop-1 accuracy verified"),
    ("Performance", "P50/P99 latency within target\nThroughput > threshold fps\nInit time < 2s"),
    ("Stability", "99.9%+ success rate\n1-hour soak test\n< 5 MB memory leak/hour"),
    ("Power", "Within thermal envelope\nPer-mode power profiling\nSustained without throttling"),
]

for i, (title, desc) in enumerate(kpis):
    x = Inches(0.5 + i * 3.2)
    add_rect(slide, x, Inches(2.0), Inches(2.9), Inches(0.7), QBLUE,
             title, font_size=16, bold=True)
    add_text(slide, desc, x + Inches(0.1), Inches(2.8), Inches(2.7), Inches(2.5),
             size=12, color=MED)

# Per-target thresholds
add_table(slide, Inches(0.8), Inches(5.2), Inches(11.5), Inches(2.0),
    ["Target", "Latency P50", "Throughput", "Power (balanced)"],
    [
        ["UNO Q (QCS2210)", "< 33 ms", "> 30 fps", "< 1.0 W"],
        ["Rubio Pi (QCS6490)", "< 15 ms", "> 60 fps", "< 3.0 W"],
        ["Windows X Elite", "< 10 ms", "> 100 fps", "< 15 W"],
    ]
)

# ================================================================
# SLIDE 12: USER JOURNEY
# ================================================================

slide = add_slide(prs)
add_text(slide, "User Journey: Zero to Inference in 5 Minutes",
         Inches(0.8), Inches(0.4), Inches(11), Inches(0.8),
         size=32, bold=True, color=QBLUE, font="Calibri Light")

steps = [
    ("Install", 'pip install devrel-agent\n./install.sh'),
    ("Detect", '"What hardware\ndo I have?"'),
    ("Convert", '"Convert my model\nto INT8"'),
    ("Profile", '"Profile on NPU\nwith detailed metrics"'),
    ("Deploy", '"Deploy to my\nArduino UNO Q"'),
    ("Test", '"Run KPI validation\non target"'),
]

for i, (label, desc) in enumerate(steps):
    x = Inches(0.3 + i * 2.1)
    # Step number circle
    add_rect(slide, x + Inches(0.6), Inches(1.8), Inches(0.7), Inches(0.7),
             QBLUE, str(i + 1), font_size=20, bold=True)
    # Label
    add_text(slide, label, x, Inches(2.7), Inches(1.9), Inches(0.4),
             size=15, bold=True, color=QBLUE, align=PP_ALIGN.CENTER)
    # Description
    add_text(slide, desc, x, Inches(3.2), Inches(1.9), Inches(1.5),
             size=12, color=MED, align=PP_ALIGN.CENTER)
    # Arrow (except last)
    if i < len(steps) - 1:
        add_text(slide, "\u2192", x + Inches(1.9), Inches(2.1), Inches(0.3), Inches(0.4),
                 size=24, color=LIGHT, align=PP_ALIGN.CENTER)

# Command box at bottom
add_rect(slide, Inches(2), Inches(5.5), Inches(9), Inches(1.2), BG_DARK,
         'pip install qualcomm-ai-toolkit && devrel quickstart\n\n'
         '"Build a classification app for my Rubio Pi"',
         font_size=14, font_color=GREEN, bold=True)

# ================================================================
# SLIDE 13: MEASUREMENT FIDELITY
# ================================================================

slide = add_slide(prs)
add_text(slide, "Measurement Fidelity",
         Inches(0.8), Inches(0.4), Inches(11), Inches(0.8),
         size=32, bold=True, color=QBLUE, font="Calibri Light")

add_text(slide, "Every metric is provenance-tagged: measured (real hardware) or estimated (host model)",
         Inches(0.8), Inches(1.2), Inches(11), Inches(0.4),
         size=16, color=MED, italic=True)

add_table(slide, Inches(0.5), Inches(1.9), Inches(12.3), Inches(4.0),
    ["Metric", "Measured Source", "Fallback"],
    [
        ["Latency", "snpe-diagview CSV", "snpe-net-run stdout parser"],
        ["Per-layer", "snpe-diagview (Model Layer Times)", "Synthetic composite (tagged)"],
        ["Memory RSS", "psutil sampler (100ms polling)", "not_measured (tagged)"],
        ["Power", "QPM3 (per-frame PMIC readings)", "Host thermal model (CPU/NPU% \u00d7 TDP)"],
        ["NPU Utilization", "cycles / wall_time / clock", "0.0 (tagged not_measured)"],
        ["CPU Utilization", "psutil.cpu_percent", "Always available"],
    ]
)

add_text(slide, "No fictional defaults. Honest provenance on every number.",
         Inches(0.8), Inches(6.2), Inches(11), Inches(0.5),
         size=16, italic=True, color=QBLUE, align=PP_ALIGN.CENTER)

# ================================================================
# SLIDE 14: THE ASK
# ================================================================

slide = add_slide(prs)
add_text(slide, "What We Need",
         Inches(0.8), Inches(0.4), Inches(11), Inches(0.8),
         size=32, bold=True, color=QBLUE, font="Calibri Light")

asks = [
    ("1. QNN SDK Documentation Access",
     "Unblocks real hardware adapter in 2\u20133 days. Mock framework complete."),
    ("2. Hardware: 4 Device Classes",
     "Snapdragon X Elite (AI PC) + Snapdragon 8 Elite (Mobile) + Arduino UNO Q (entry IoT) + Rubio Pi / RB5 (edge IoT)"),
    ("3. Engineering Team: 12\u201315 Engineers \u00d7 12 Months",
     "To achieve CUDA platform parity across compiler, runtime, libraries, and ecosystem."),
]

for i, (title, desc) in enumerate(asks):
    y = Inches(1.5 + i * 1.8)
    add_rect(slide, Inches(0.8), y, Inches(11.5), Inches(0.7), QBLUE,
             title, font_size=18, bold=True, align=PP_ALIGN.LEFT)
    add_text(slide, desc, Inches(1.0), y + Inches(0.75), Inches(11), Inches(0.7),
             size=15, color=MED)

add_text(slide, "Phase 1 (current team) \u2192 Phase 2 (expand) \u2192 Phase 3 (community & ecosystem)",
         Inches(0.8), Inches(6.5), Inches(11), Inches(0.5),
         size=16, bold=True, color=DARK, align=PP_ALIGN.CENTER)

# ================================================================
# SLIDE 15: CALL TO ACTION
# ================================================================

slide = add_slide(prs)
add_bg(slide, BG_DARK)

add_text(slide, "3 billion Qualcomm SoCs shipped per year.",
         Inches(1), Inches(1.5), Inches(11), Inches(0.8),
         size=28, color=WHITE, align=PP_ALIGN.CENTER, font="Calibri Light")

add_text(slide, "Zero unified developer platform.",
         Inches(1), Inches(2.5), Inches(11), Inches(0.8),
         size=28, color=WHITE, align=PP_ALIGN.CENTER, font="Calibri Light")

add_text(slide, "DevRel makes Qualcomm the default choice\nfor on-device AI development.",
         Inches(1), Inches(4.0), Inches(11), Inches(1.2),
         size=24, color=RGBColor(0xAA, 0xBB, 0xFF), align=PP_ALIGN.CENTER,
         font="Calibri Light")

add_rect(slide, Inches(3), Inches(5.5), Inches(7), Inches(0.9), QBLUE,
         "pip install qualcomm-ai-toolkit && devrel quickstart",
         font_size=16, bold=True)

add_text(slide, "Demo available:  ./install.sh && ./launch.sh",
         Inches(1), Inches(6.7), Inches(11), Inches(0.4),
         size=14, color=LIGHT, align=PP_ALIGN.CENTER)

# ================================================================
# SAVE
# ================================================================

# Script lives in tools/; the generated deck belongs in docs/ (sibling dir).
output_path = str(Path(__file__).resolve().parent.parent / "docs" / "DevRel_Pitch_Presentation.pptx")
prs.save(output_path)
print(f"Presentation saved to: {output_path}")
print(f"File size: {os.path.getsize(output_path) / 1024:.1f} KB")
