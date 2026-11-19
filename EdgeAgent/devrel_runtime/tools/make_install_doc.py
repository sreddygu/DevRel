"""Generate a professional DevRel Client installation instructions .docx."""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

# Brand palette
QC_BLUE = RGBColor(0x3B, 0x55, 0x9E)      # heading blue
QC_DARK = RGBColor(0x1F, 0x2A, 0x44)      # near-black text
QC_ACCENT = RGBColor(0x00, 0x6F, 0xCF)    # link / accent
CODE_BG = "F2F3F7"
NOTE_BG = "FFF6E0"

doc = Document()

# ---- base style ----
normal = doc.styles["Normal"]
normal.font.name = "Segoe UI"
normal.font.size = Pt(11)
normal.font.color.rgb = QC_DARK

# ---- page margins ----
for section in doc.sections:
    section.top_margin = Inches(0.9)
    section.bottom_margin = Inches(0.9)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)


def shade(paragraph, hex_color):
    """Apply a background shade to a paragraph."""
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


def code_block(lines, comment_lines=None):
    """Render a shaded monospace code block. comment_lines = set of indices to render greyed."""
    comment_lines = comment_lines or set()
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.left_indent = Inches(0.05)
    shade(p, CODE_BG)
    borders(p)
    for i, line in enumerate(lines):
        run = p.add_run(line + ("\n" if i < len(lines) - 1 else ""))
        run.font.name = "Consolas"
        run.font.size = Pt(10.5)
        if i in comment_lines:
            run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
            run.italic = True
        else:
            run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)
    return p


def heading(text, level=1):
    if level == 1:
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.font.size = Pt(16)
        run.font.bold = True
        run.font.color.rgb = QC_BLUE
        p.paragraph_format.space_before = Pt(16)
        p.paragraph_format.space_after = Pt(4)
        # bottom rule
        pPr = p._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "8")
        bottom.set(qn("w:space"), "4")
        bottom.set(qn("w:color"), "C3CBE0")
        pBdr.append(bottom)
        pPr.append(pBdr)
    else:
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.font.size = Pt(12.5)
        run.font.bold = True
        run.font.color.rgb = QC_DARK
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(2)
    return p


def step(number, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.left_indent = Inches(0.1)
    n = p.add_run(f"{number}.  ")
    n.font.bold = True
    n.font.color.rgb = QC_ACCENT
    n.font.size = Pt(11)
    add_rich(p, text)
    return p


def add_rich(paragraph, text):
    """Add text supporting **bold** and `code` inline markers."""
    import re
    tokens = re.split(r"(\*\*.*?\*\*|`.*?`)", text)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            r = paragraph.add_run(tok[2:-2])
            r.font.bold = True
        elif tok.startswith("`") and tok.endswith("`"):
            r = paragraph.add_run(tok[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(10.5)
            r.font.color.rgb = RGBColor(0xB0, 0x30, 0x60)
        else:
            paragraph.add_run(tok)


def note(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    shade(p, NOTE_BG)
    borders(p, color="E8C66B")
    r = p.add_run("Note   ")
    r.font.bold = True
    r.font.color.rgb = RGBColor(0xB5, 0x7A, 0x00)
    add_rich(p, text)


# ============ TITLE BLOCK ============
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.LEFT
tr = title.add_run("DevRel Client")
tr.font.size = Pt(26)
tr.font.bold = True
tr.font.color.rgb = QC_BLUE
title.paragraph_format.space_after = Pt(0)

sub = doc.add_paragraph()
sr = sub.add_run("Installation Instructions")
sr.font.size = Pt(15)
sr.font.color.rgb = QC_DARK
sub.paragraph_format.space_after = Pt(2)

meta = doc.add_paragraph()
mr = meta.add_run("Setup guide for Windows, macOS, and Linux")
mr.font.size = Pt(10)
mr.italic = True
mr.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
meta.paragraph_format.space_after = Pt(8)

# title underline rule
rule = doc.add_paragraph()
pPr = rule._p.get_or_add_pPr()
pBdr = OxmlElement("w:pBdr")
bottom = OxmlElement("w:bottom")
bottom.set(qn("w:val"), "single")
bottom.set(qn("w:sz"), "18")
bottom.set(qn("w:space"), "1")
bottom.set(qn("w:color"), "3B559E")
pBdr.append(bottom)
pPr.append(pBdr)
rule.paragraph_format.space_after = Pt(6)

intro = doc.add_paragraph()
add_rich(intro, "Follow the section for your operating system to install the prerequisites, "
                "then complete the **DevRel Client installation** steps that apply to all platforms.")
intro.paragraph_format.space_after = Pt(6)

# ============ CLAUDE CODE PREREQUISITE BANNER ============
prereq = doc.add_paragraph()
prereq.paragraph_format.space_before = Pt(4)
prereq.paragraph_format.space_after = Pt(8)
shade(prereq, NOTE_BG)
borders(prereq, color="E8C66B")
pr = prereq.add_run("Steps 1 and 2 install Claude Code.   ")
pr.font.bold = True
pr.font.color.rgb = RGBColor(0xB5, 0x7A, 0x00)
add_rich(prereq, "If you **already have Claude Code installed**, you can **skip Steps 1 and 2** "
                 "and go directly to **Step 3 — DevRel Client Installation**.")

# ============ WINDOWS ============
heading("1.  Claude Code — Windows PC", level=1)
step(1, "Download the installer (the attached **.zip** containing the **.exe**) onto your **Desktop**.")
step(2, "Extract the .zip, then **right-click the installer** and choose **Run as administrator**.")

# ============ MAC / LINUX ============
heading("2.  Claude Code — macOS / Linux", level=1)
mac = doc.add_paragraph()
mac.paragraph_format.left_indent = Inches(0.1)
add_rich(mac, "Follow the setup guide at the link below:")
link = doc.add_paragraph()
link.paragraph_format.left_indent = Inches(0.1)
lr = link.add_run("https://qgenie-docs.qualcomm.com/code/claude-code")
lr.font.color.rgb = QC_ACCENT
lr.underline = True
lr.font.size = Pt(11)
link.paragraph_format.space_after = Pt(4)

# ---- API key note (applies to both Windows and Mac/Linux) ----
apik = doc.add_paragraph()
apik.paragraph_format.left_indent = Inches(0.1)
apik.paragraph_format.space_after = Pt(2)
add_rich(apik, "Claude Code uses **Qgenie**. Obtain your **API key** from:")
apilink = doc.add_paragraph()
apilink.paragraph_format.left_indent = Inches(0.1)
alr = apilink.add_run("https://qgenie-model-usage.qualcomm.com/api-keys")
alr.font.color.rgb = QC_ACCENT
alr.underline = True
alr.font.size = Pt(11)

# ============ DevRel CLIENT INSTALL ============
heading("3.  DevRel Client Installation", level=1)
inst = doc.add_paragraph()
inst.paragraph_format.left_indent = Inches(0.1)
add_rich(inst, "Once the prerequisites for your platform are installed, open a terminal "
               "(**PowerShell** on Windows) and run the following steps.")
inst.paragraph_format.space_after = Pt(6)

step(1, "Clone the repository and enter the project directory:")
code_block([
    "git clone https://github.qualcomm.com/pavanr/DevRel.git",
    "cd DevRel",
])

step(2, "Set the MCP authentication token for this session:")
code_block([
    '$env:DevRel_MCP_TOKEN = "36ee2dee472ac92fab76941fe5e6d7a1e7639b6ce62991f49388db03df7704ac"',
])

step(3, "Run the installer:")
code_block([
    ".\\install.ps1",
])

step(4, "When prompted for the **MCP Location**, select **option 3 (SSE HTTP)**.")
step(5, "When prompted for the **MCP server location**, paste the URL below:")
code_block([
    "http://10.227.21.202:8000/mcp",
])

note("Keep the **DevRel_MCP_TOKEN** value confidential. It is set only for the current "
     "terminal session; re-run the export command if you open a new terminal before installing.")

# ============ CONNECTION CHECK ============
heading("4.  Is This Client Connected to the MCP Server?", level=1)
chk = doc.add_paragraph()
chk.paragraph_format.left_indent = Inches(0.1)
add_rich(chk, "You do **not** need to run any commands. Inside **Claude Code**, simply ask:")
chk.paragraph_format.space_after = Pt(4)
code_block([
    "Is this client connected to the MCP server?",
])
ask = doc.add_paragraph()
ask.paragraph_format.left_indent = Inches(0.1)
add_rich(ask, "Claude Code will verify the connection for you and report the server's status "
              "and available tools. The connection is live when the **DevRel skills** (listed "
              "below) are available and the MCP tools (`hardware_detect`, `profile_workload`, "
              "`convert_model`, `orchestrate_workload`, `generate_code`) respond.")
ask.paragraph_format.space_after = Pt(8)

opt = doc.add_paragraph()
opt.paragraph_format.left_indent = Inches(0.1)
optr = opt.add_run("Optional — manual check from a terminal")
optr.font.bold = True
optr.font.color.rgb = QC_DARK
optr.font.size = Pt(11)
opt.paragraph_format.space_after = Pt(2)

man = doc.add_paragraph()
man.paragraph_format.left_indent = Inches(0.1)
add_rich(man, "If you prefer the command line, run **connect-test** — it verifies the transport "
              "without writing any files and exits non-zero on failure:")
man.paragraph_format.space_after = Pt(4)
code_block([
    ".venv\\Scripts\\python.exe -m devrel_client.cli connect-test sse-http \\",
    '    --sse-url "http://10.227.21.202:8000/mcp" \\',
    '    --auth-token "$env:DevRel_MCP_TOKEN"',
])

# ============ DevRel SKILLS REFERENCE ============
heading("5.  DevRel Skills Reference", level=1)
sk_intro = doc.add_paragraph()
sk_intro.paragraph_format.left_indent = Inches(0.1)
add_rich(sk_intro, "Once connected, the following **DevRel skills** are available in Claude Code. "
                   "Invoke a skill by typing its slash command (for example, `/devrel-detect`) "
                   "or by describing the task in natural language.")
sk_intro.paragraph_format.space_after = Pt(8)

SKILLS = [
    ("/devrel-quickstart",
     "End-to-end starting point: detects hardware, checks the SDK, and runs a first "
     "sample inference. Use this to get up and running with DevRel on a Snapdragon laptop."),
    ("/devrel-detect",
     "Probes the local host and any reachable target devices (USB boards via adb, SSH "
     "targets in devrel.toml) and reports chipset, CPU/GPU/NPU, RAM, runtimes, and SDK status."),
    ("/devrel-doctor",
     "Runs the local diagnostic suite and explains each WARN/FAIL row with the exact fix. "
     "Use to confirm DevRel is set up correctly and to troubleshoot real-mode issues."),
    ("/devrel-configure",
     "Interactive configuration wizard. Asks about SDK paths, hardware, and secrets, then "
     "writes devrel.toml and .env. Run before first use or when changing hardware/SDK setup."),
    ("/devrel-recommend",
     "Synthesises model + target + use case into specific deployment recommendations "
     "(e.g. NPU vs GPU, INT4 vs INT8) for the best approach on Snapdragon."),
    ("/devrel-convert",
     "Walks through model conversion and quantization (ONNX/PyTorch → QNN/SNPE) with "
     "calibration-data and image-format guidance."),
    ("/devrel-profile",
     "Picks the right profiling level and renders a latency / utilisation summary. Finds "
     "bottlenecks, measures NPU latency, and runs QHAS profiling and linting."),
    ("/devrel-orchestrate",
     "Compares performance, balanced, and efficiency power modes side-by-side and advises "
     "where each op should run across CPU/GPU/NPU."),
    ("/devrel-codegen",
     "Generates compilable inference code for the right (platform, language, SDK) combo — "
     "C++ apps, Python boilerplate, or Android JNI bindings for a given model."),
    ("/devrel-deploy",
     "Walks through deploy.sh and remote profiling to push a model to an Android phone, "
     "Arduino UNO Q, or other Snapdragon target."),
    ("/devrel-serve",
     "Sets up `devrel serve` to expose a model as an HTTP API, covering endpoint usage and "
     "load testing for production deployment."),
    ("/devrel-app-builder",
     "Guides the full application lifecycle — requirements, implementation, testing, "
     "hardening, documentation, and git push — for vision/LLM/ASR inference apps on Snapdragon."),
    ("/devrel-app-document",
     "Generates ARCHITECTURE.md and app_documentation.docx for any DevRel application directory."),
    ("/devrel-run-ps1",
     "Adds the standard run.ps1 + requirements.txt to a DevRel app. Applied automatically "
     "whenever a new sample or generated app is scaffolded."),
    ("/devrel-npu-prereqs",
     "Detects host arch + target, reviews and provisions NPU prerequisites — AI Hub Models token, "
     "NPU pip wheels (onnxruntime-qnn / onnxruntime-genai), and env/config — for the "
     "Snapdragon developer workflow."),
    ("/devrel-build-npu-bundle",
     "Builds an AI Hub Models Genie LLM bundle (e.g. Llama/Qwen for the Hexagon NPU) on a "
     "non-arm64 host (WSL / x86 / macOS / Linux) and stages it onto the Snapdragon X-Elite."),
    ("/devrel-unoq",
     "Full Arduino UNO Q / QCS2210 board workflow: configure, flash firmware, deploy, "
     "debug, monitor, profile, extract logs, check status, and run stability/performance tests."),
]

# build the skills table
table = doc.add_table(rows=1, cols=2)
table.alignment = WD_TABLE_ALIGNMENT.LEFT
table.style = "Table Grid"
table.autofit = False
table.columns[0].width = Inches(1.85)
table.columns[1].width = Inches(4.65)

# header row
hdr = table.rows[0].cells
for cell, label in zip(hdr, ("Skill", "Description")):
    cell.text = ""
    p = cell.paragraphs[0]
    r = p.add_run(label)
    r.font.bold = True
    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    r.font.size = Pt(10.5)
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), "3B559E")
    tcPr.append(shd)

for i, (name, desc) in enumerate(SKILLS):
    cells = table.add_row().cells
    cells[0].width = Inches(1.85)
    cells[1].width = Inches(4.65)
    # skill name (monospace)
    cells[0].text = ""
    pn = cells[0].paragraphs[0]
    rn = pn.add_run(name)
    rn.font.name = "Consolas"
    rn.font.size = Pt(9.5)
    rn.font.bold = True
    rn.font.color.rgb = RGBColor(0xB0, 0x30, 0x60)
    # description
    cells[1].text = ""
    pd = cells[1].paragraphs[0]
    rd = pd.add_run(desc)
    rd.font.size = Pt(10)
    rd.font.color.rgb = QC_DARK
    # zebra striping
    if i % 2 == 1:
        for c in cells:
            tcPr = c._tc.get_or_add_tcPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:fill"), "F2F3F7")
            tcPr.append(shd)

# ============ FOOTER ============
foot = doc.add_paragraph()
foot.paragraph_format.space_before = Pt(18)
fr = foot.add_run("DevRel Client  •  Installation Instructions")
fr.font.size = Pt(8)
fr.font.color.rgb = RGBColor(0x9A, 0xA0, 0xAE)

out = r"C:\work\DevRel\devrelAgent\devrelAgent_Installation_Instructions.docx"
doc.save(out)
print("Saved:", out)
