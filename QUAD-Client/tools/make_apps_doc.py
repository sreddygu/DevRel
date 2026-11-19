"""Generate the 'Building & Profiling Apps with QUAD' .docx (MobileNetV2)."""
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

QC_BLUE = RGBColor(0x3B, 0x55, 0x9E)
QC_DARK = RGBColor(0x1F, 0x2A, 0x44)
QC_ACCENT = RGBColor(0x00, 0x6F, 0xCF)
CODE_BG = "F2F3F7"
NOTE_BG = "FFF6E0"
CODE_PINK = RGBColor(0xB0, 0x30, 0x60)

doc = Document()
normal = doc.styles["Normal"]
normal.font.name = "Segoe UI"
normal.font.size = Pt(11)
normal.font.color.rgb = QC_DARK

for section in doc.sections:
    section.top_margin = Inches(0.9)
    section.bottom_margin = Inches(0.9)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)


def shade(paragraph, hex_color):
    pPr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    pPr.append(shd)


def borders(paragraph, color="D8DCE6", size="6"):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), size)
        el.set(qn("w:space"), "6")
        el.set(qn("w:color"), color)
        pBdr.append(el)
    pPr.append(pBdr)


def add_rich(paragraph, text):
    tokens = re.split(r"(\*\*.*?\*\*|`.*?`)", text)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            r = paragraph.add_run(tok[2:-2]); r.font.bold = True
        elif tok.startswith("`") and tok.endswith("`"):
            r = paragraph.add_run(tok[1:-1])
            r.font.name = "Consolas"; r.font.size = Pt(10.5); r.font.color.rgb = CODE_PINK
        else:
            paragraph.add_run(tok)


def code_block(lines):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.left_indent = Inches(0.05)
    shade(p, CODE_BG); borders(p)
    for i, line in enumerate(lines):
        run = p.add_run(line + ("\n" if i < len(lines) - 1 else ""))
        run.font.name = "Consolas"; run.font.size = Pt(10.5)
        run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)
    return p


def h1(text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(16); run.font.bold = True; run.font.color.rgb = QC_BLUE
    p.paragraph_format.space_before = Pt(16); p.paragraph_format.space_after = Pt(4)
    pPr = p._p.get_or_add_pPr(); pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single"); bottom.set(qn("w:sz"), "8")
    bottom.set(qn("w:space"), "4"); bottom.set(qn("w:color"), "C3CBE0")
    pBdr.append(bottom); pPr.append(pBdr)
    return p


def h2(text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(12.5); run.font.bold = True; run.font.color.rgb = QC_DARK
    p.paragraph_format.space_before = Pt(10); p.paragraph_format.space_after = Pt(2)
    return p


def body(text, indent=0.0, after=4):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(indent)
    p.paragraph_format.space_after = Pt(after)
    add_rich(p, text)
    return p


def bullet(text, indent=0.25):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Inches(indent)
    p.paragraph_format.space_after = Pt(2)
    add_rich(p, text)
    return p


def numbered(n, text, indent=0.1):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.left_indent = Inches(indent)
    r = p.add_run(f"{n}.  "); r.font.bold = True; r.font.color.rgb = QC_ACCENT
    add_rich(p, text)
    return p


def note(text, label="Note", fill=NOTE_BG, border="E8C66B", lab_color=RGBColor(0xB5,0x7A,0x00)):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6); p.paragraph_format.space_after = Pt(6)
    shade(p, fill); borders(p, color=border)
    r = p.add_run(label + "   "); r.font.bold = True; r.font.color.rgb = lab_color
    add_rich(p, text)


def make_table(headers, rows, widths, code_col=None):
    """code_col: index of a column to render monospace."""
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.style = "Table Grid"
    table.autofit = False
    for c, w in zip(table.columns, widths):
        c.width = Inches(w)
    hdr = table.rows[0].cells
    for cell, label, w in zip(hdr, headers, widths):
        cell.width = Inches(w)
        cell.text = ""
        r = cell.paragraphs[0].add_run(label)
        r.font.bold = True; r.font.color.rgb = RGBColor(0xFF,0xFF,0xFF); r.font.size = Pt(10.5)
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:fill"), "3B559E")
        tcPr.append(shd)
    for i, row in enumerate(rows):
        cells = table.add_row().cells
        for j, (cell, val, w) in enumerate(zip(cells, row, widths)):
            cell.width = Inches(w)
            cell.text = ""
            p = cell.paragraphs[0]
            # support **bold** marker for emphasis in result tables
            if "**" in val:
                add_rich(p, val)
                for rr in p.runs:
                    rr.font.size = Pt(10)
            else:
                r = p.add_run(val)
                r.font.size = Pt(9.5 if j == code_col else 10)
                if j == code_col:
                    r.font.name = "Consolas"; r.font.bold = True; r.font.color.rgb = CODE_PINK
                else:
                    r.font.color.rgb = QC_DARK
            if i % 2 == 1:
                tcPr = cell._tc.get_or_add_tcPr()
                shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:fill"), CODE_BG)
                tcPr.append(shd)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


# ============ TITLE ============
title = doc.add_paragraph()
tr = title.add_run("Building & Profiling Apps with QUAD")
tr.font.size = Pt(24); tr.font.bold = True; tr.font.color.rgb = QC_BLUE
title.paragraph_format.space_after = Pt(0)

sub = doc.add_paragraph()
sr = sub.add_run("MobileNetV2 on Snapdragon X Elite & Arduino UNO Q")
sr.font.size = Pt(14); sr.font.color.rgb = QC_DARK
sub.paragraph_format.space_after = Pt(2)

meta = doc.add_paragraph()
mr = meta.add_run("Build, profile on CPU / GPU / NPU, and apply optimization recommendations")
mr.font.size = Pt(10); mr.italic = True; mr.font.color.rgb = RGBColor(0x6B,0x72,0x80)
meta.paragraph_format.space_after = Pt(8)

rule = doc.add_paragraph()
pPr = rule._p.get_or_add_pPr(); pBdr = OxmlElement("w:pBdr")
bottom = OxmlElement("w:bottom")
bottom.set(qn("w:val"), "single"); bottom.set(qn("w:sz"), "18")
bottom.set(qn("w:space"), "1"); bottom.set(qn("w:color"), "3B559E")
pBdr.append(bottom); pPr.append(pBdr)
rule.paragraph_format.space_after = Pt(6)

body("A hands-on guide to building simple inference applications with the **QUAD** platform, "
     "running **MobileNetV2** across **CPU, GPU, and NPU**, profiling the performance on each "
     "backend, and applying QUAD's optimization recommendations.", after=6)

# ============ 1. WHAT YOU'LL BUILD ============
h1("1.  What You'll Build")
make_table(
    ["App", "Target", "Backends profiled", "Outcome"],
    [
        ["MobileNetV2 Benchmark", "Snapdragon X Elite", "CPU, GPU (Adreno), NPU (Hexagon HTP)", "Latency / throughput / power table"],
        ["MobileNetV2 on-device", "Arduino UNO Q (QCS2210)", "CPU (ONNX Runtime)", "On-board latency + top-K predictions"],
        ["GPU Inference", "Snapdragon X Elite", "GPU (Adreno)", "Generated C++ libQnnGpu code"],
        ["Whisper ASR", "Snapdragon X Elite", "NPU encoder + CPU decoder", "Live streaming speech-to-text"],
    ],
    widths=[1.55, 1.55, 1.95, 1.45],
)
body("Every app follows the same five-step QUAD pattern, so once you understand the first one "
     "the rest are variations on a theme.", after=4)

# ============ 2. PREREQUISITES ============
h1("2.  Prerequisites")
make_table(
    ["Requirement", "Notes"],
    [
        ["QUAD Client installed", "See the QUAD Client Installation Instructions — install.ps1 + QUAD_MCP_TOKEN"],
        ["Connection verified", 'In Claude Code, ask "Is this client connected to the MCP server?"'],
        ["Python 3.10+", "python --version"],
        ["QAIRT SDK", "Installed via install.ps1 -QairtArchive <path> (for real NPU/GPU runs)"],
        ["adb on PATH", "Only for the UNO Q sample — winget install Google.PlatformTools"],
    ],
    widths=[1.9, 4.6],
)
note("**Mock mode works without hardware.** You can develop and test every sample in "
     "`--adapter-mode mock` (no SDK or device needed), then switch to real mode when you "
     "have a Snapdragon target attached.")

# ============ 3. WORKFLOW ============
h1("3.  The QUAD Workflow")
body("Every QUAD application follows the same five-tool MCP pattern:", after=4)
code_block(["hardware_detect  ->  convert_model  ->  profile_workload  ->  orchestrate_workload  ->  generate_code"])
make_table(
    ["Step", "MCP tool / skill", "What it does"],
    [
        ["1. Detect", "hardware_detect  /  /quad-detect", "Find CPU, GPU, NPU, RAM, runtimes, SDK status"],
        ["2. Convert", "convert_model  /  /quad-convert", "ONNX → QNN/SNPE DLC, quantize to INT8"],
        ["3. Profile", "profile_workload  /  /quad-profile", "Measure latency, throughput, power per backend"],
        ["4. Orchestrate", "orchestrate_workload  /  /quad-orchestrate", "Compare power modes; choose where each op runs"],
        ["5. Generate", "generate_code  /  /quad-codegen", "Emit compilable C++ / Python / JNI inference code"],
    ],
    widths=[1.0, 2.4, 3.1],
)
body("The fastest way to drive this in Claude Code is natural language — for example, "
     "*\"profile MobileNetV2 on CPU, GPU and NPU and recommend the best backend\"* — or the "
     "`/quad-*` slash commands.", after=4)

# ============ 4. SAMPLE APP 1 ============
h1("4.  Sample App 1 — MobileNetV2 CPU vs GPU vs NPU (Snapdragon X Elite)")
body("This sample downloads MobileNetV2, converts it via the QUAD MCP server, and benchmarks "
     "**CPU (ONNX Runtime) vs GPU (Adreno) vs NPU (Hexagon HTP)** in one script. It lives at "
     "`samples/mobilenetv2/`.")
h2("Build & run")
code_block([
    "cd samples\\mobilenetv2",
    "",
    "# One-time: install sample dependencies into a local .venv",
    ".\\run.ps1",
    "",
    "# Run the full pipeline (download -> convert -> benchmark all 3 backends)",
    ".venv\\Scripts\\python.exe run_mobilenetv2.py --image test_input.jpg",
])
body("The script will:")
numbered(1, "**Download** MobileNetV2 ONNX + ImageNet labels.")
numbered(2, "**Convert** to a QNN INT8 DLC via the QUAD MCP server (auto-spawned over stdio — no server to start).")
numbered(3, "**Benchmark** CPU (10 timed runs), GPU (Adreno duration benchmark), and NPU "
            "(`qnn-net-run --duration` with 1000+ iterations for accurate timing).")
numbered(4, "**Print** a side-by-side comparison table with latency, throughput, and estimated power.")
h2("Useful options")
code_block([
    "# Use your own photo, skip re-download",
    ".venv\\Scripts\\python.exe run_mobilenetv2.py --image my_photo.jpg --skip-download",
    "",
    "# Mock mode - no SDK needed (simulated conversion)",
    ".venv\\Scripts\\python.exe run_mobilenetv2.py --adapter-mode mock",
    "",
    "# SNPE DLC for Android/Linux targets",
    ".venv\\Scripts\\python.exe run_mobilenetv2.py --target-sdk snpe",
    "",
    "# Better INT8 accuracy with calibration images",
    ".venv\\Scripts\\python.exe run_mobilenetv2.py --calibration .\\calib_images\\",
])
h2("Doing it conversationally in Claude Code")
body("You don't have to remember the flags. Just ask:")
note('"Convert MobileNetV2 to INT8, then profile it on CPU, GPU and NPU on my Snapdragon X '
     'Elite and show me a comparison table."', label="Ask", fill="EAF2FB",
     border="9AC2EA", lab_color=QC_ACCENT)
body("Claude Code runs `convert_model` then `profile_workload` for each runtime and renders the results.")

# ============ 5. SAMPLE APP 2 ============
h1("5.  Sample App 2 — MobileNetV2 on Arduino UNO Q")
body("Run the **same** MobileNetV2 model on an Arduino UNO Q (QCS2210) board attached over USB. "
     "This uses `samples/mobilenetv2/run_target_cpu.py`.")
h2("Build & run")
code_block([
    "# Prereq: adb on PATH, one device listed",
    "adb devices",
    "",
    "cd samples\\mobilenetv2",
    ".venv\\Scripts\\python.exe run_target_cpu.py",
])
body("The orchestrator preprocesses the host image into a float32 NCHW `.npy`, pushes the model "
     "+ input + labels + `deploy/inference.py` to `/data/local/tmp/quad/` on the board, runs "
     "inference over `adb shell`, and prints latency + top-K predictions.")
h2("Hardware reality on this SoC")
body("On the shipped UNO Q Debian image, the Hexagon DSP and Adreno GPU are **not** reachable by "
     "the SNPE/QNN runtime (no `/dev/fastrpc*`; OpenCL is Mesa rusticl, not the Adreno driver). "
     "The **working on-target path is ONNX Runtime CPU**, which is what `deploy/inference.py` "
     "uses. The NPU silicon exists but the compute stack isn't exposed on this variant.")
note("Use **UNO Q** to validate the *portability* of your pipeline to an edge SoC; use the "
     "**Snapdragon X Elite** to demonstrate *NPU acceleration*.", label="Tip",
     fill="EAF2FB", border="9AC2EA", lab_color=QC_ACCENT)

# ============ 6. PROFILING RESULTS ============
h1("6.  Profiling Results & How to Read Them")
body("These are **real measured numbers** from the QUAD `mobilenetv2` sample.", after=4)
h2("Snapdragon X Elite — CPU vs NPU")
make_table(
    ["Metric", "CPU (ONNX Runtime)", "NPU (QNN HTP)"],
    [
        ["Avg latency", "6.4 ms", "**5.48 ms**"],
        ["Throughput", "157 FPS", "**183 FPS**"],
        ["Speedup", "1.0x", "**1.2x**"],
        ["Avg CPU utilisation", "47%", "~0% (offloaded)"],
        ["Est. package power", "~10.7 W", "**~4.5 W**"],
    ],
    widths=[2.1, 2.2, 2.2],
)
body("**Reading it:** the NPU is modestly faster *and* uses **less than half the power** while "
     "freeing the CPU entirely — the headline win on a battery device is energy efficiency, not "
     "just raw latency.", after=6)
h2("Arduino UNO Q — ONNX Runtime CPU (Cortex-A53 quad-core)")
make_table(
    ["Metric", "Value"],
    [
        ["Avg latency", "~64 ms"],
        ["P50 latency", "~62 ms"],
        ["P99 latency", "~71 ms"],
        ["Throughput", "~15-16 FPS"],
        ["Model", "mobilenetv2.onnx (FP32)"],
    ],
    widths=[2.6, 3.9],
)
body("**Reading it:** ~10x slower than the X Elite CPU — expected for a low-power edge SoC "
     "running FP32 on four A53 cores. INT8 quantization is the first lever to pull here.")

# ============ 7. OPTIMIZATION RECOMMENDATIONS ============
h1("7.  Optimization Recommendations")
body("Based on the profiles above, in priority order:", after=4)
numbered(1, "**Offload to the NPU (Hexagon HTP) on Snapdragon X Elite.** Best latency *and* "
            "lowest power (~4.5 W vs ~10.7 W). For any sustained or battery-sensitive workload, "
            "this is the default choice.")
numbered(2, "**Quantize to INT8 with calibration data.** MobileNetV2 quantizes cleanly. Pass "
            "`--calibration <dir>` with ~50–100 representative images so INT8 accuracy stays "
            "close to FP32. On UNO Q, INT8 on the A53 CPU is the single biggest speed lever.")
numbered(3, "**Use the right power mode (`orchestrate_workload`).** Performance = lowest latency / "
            "highest power (bursty); Balanced = sensible default; Efficiency = lowest power for "
            "always-on / streaming. Compare with `/quad-orchestrate` before committing.")
numbered(4, "**Benchmark with `--duration`, not per-call timing.** Process-spawn overhead (~1 s) "
            "dominates single-shot calls and makes the NPU look slow. Run many iterations in one "
            "process for accurate averages.")
numbered(5, "**Pick the backend per model, not per device.** Small CNNs like MobileNetV2 see "
            "modest NPU speedups; larger models (transformers, detectors) show much bigger wins. "
            "Always profile *your* model with `profile_workload` and let the numbers decide.")
numbered(6, "**GPU (Adreno) as the middle ground.** When the NPU is busy or an op is unsupported "
            "on HTP, route to the Adreno GPU via `libQnnGpu` rather than falling back to CPU.")
note("In Claude Code you can simply ask: *\"Given these profiles, what's the best backend and "
     "power mode for a battery-powered always-on camera?\"* — the `/quad-recommend` skill "
     "synthesises model + target + use case into a concrete recommendation.")

# ============ 8. TWO MORE SAMPLES ============
h1("8.  Two More Simple Sample Apps")
h2("A.  GPU Inference  (samples/gpu_inference/)")
body("End-to-end targeting of the **Adreno GPU** via QUAD: detect hardware, convert an ONNX model, "
     "profile with `runtime=\"gpu\"`, and generate C++ inference code using `libQnnGpu`.")
code_block([
    "cd samples\\gpu_inference",
    ".\\run.ps1",
    ".venv\\Scripts\\python.exe gpu_inference.py",
    "# Or a custom model:",
    ".venv\\Scripts\\python.exe gpu_inference.py --model path\\to\\model.onnx",
])
body("Mock mode works for development; real GPU execution needs a Snapdragon device with an "
     "Adreno GPU + QAIRT SDK.", after=6)
h2("B.  Whisper Streaming ASR  (samples/whisper_asr/)")
body("Real-time speech-to-text using **Whisper-tiny** with an **NPU-accelerated encoder** and "
     "**CPU decoder** — a nice example of multi-backend orchestration.")
code_block([
    "Microphone/WAV -> 80 ms chunks -> 5 s sliding window -> Mel spectrogram (CPU)",
    "    -> Encoder (NPU INT8) -> Decoder (CPU INT8) -> Streaming text -> Console",
])
code_block([
    "cd samples\\whisper_asr",
    ".\\run.ps1",
    ".venv\\Scripts\\python.exe whisper_asr.py            # live mic",
    ".venv\\Scripts\\python.exe whisper_asr.py --wav sample.wav",
])
body("This shows the QUAD pattern applied to a **pipeline**: the mel frontend and decoder run on "
     "CPU while the heavy encoder is offloaded to the NPU — exactly the kind of split "
     "`orchestrate_workload` helps you reason about.")

# ============ 9. TROUBLESHOOTING ============
h1("9.  Troubleshooting")
make_table(
    ["Symptom", "Fix"],
    [
        ["ModuleNotFoundError: fastmcp", "Run .\\run.ps1 in the sample directory"],
        ["Could not import quad.mcp.server", "Install the QUAD server: cd ..\\..\\QUAD && .\\install.ps1"],
        ["qairt-converter not found", "Install the QAIRT SDK: .\\install.ps1 -QairtArchive <path>"],
        ["NPU benchmark skipped: QNN_SDK_ROOT not set", "Run .\\install.ps1 in the QUAD-Client root to create .QUAD/ paths"],
        ["DspTransport.openSession failed", "HTP init warning only — the graph still runs on the NPU"],
        ["Low / random predictions", "Use --calibration with representative images for INT8 accuracy"],
        ["UNO Q: PLATFORM_NOT_SUPPORTED", "Expected on this board — use the ONNX Runtime CPU path (default)"],
    ],
    widths=[2.9, 3.6],
)

# ============ FOOTER ============
foot = doc.add_paragraph()
foot.paragraph_format.space_before = Pt(18)
fr = foot.add_run("QUAD Client  •  Building & Profiling Apps with QUAD — MobileNetV2")
fr.font.size = Pt(8); fr.font.color.rgb = RGBColor(0x9A,0xA0,0xAE)

out = r"C:\work\QUAD\QUAD-Client\docs\Building_Apps_with_QUAD_MobileNetV2.docx"
doc.save(out)
print("Saved:", out)
