"""Generate a standalone 'Accessing the Repository' section .docx (DevRel style)."""
import re

from docx import Document
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
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hex_color)
    pPr.append(shd)


def borders(paragraph, color="D8DCE6", size="6"):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single"); el.set(qn("w:sz"), size)
        el.set(qn("w:space"), "6"); el.set(qn("w:color"), color)
        pBdr.append(el)
    pPr.append(pBdr)


def add_rich(paragraph, text):
    for tok in re.split(r"(\*\*.*?\*\*|`.*?`)", text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            r = paragraph.add_run(tok[2:-2]); r.font.bold = True
        elif tok.startswith("`") and tok.endswith("`"):
            r = paragraph.add_run(tok[1:-1]); r.font.name = "Consolas"
            r.font.size = Pt(10.5); r.font.color.rgb = CODE_PINK
        else:
            paragraph.add_run(tok)


def code_block(lines):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6); p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.left_indent = Inches(0.05)
    shade(p, CODE_BG); borders(p)
    for i, line in enumerate(lines):
        run = p.add_run(line + ("\n" if i < len(lines) - 1 else ""))
        run.font.name = "Consolas"; run.font.size = Pt(10.5)
        run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)


def h1(text):
    p = doc.add_paragraph()
    r = p.add_run(text); r.font.size = Pt(16); r.font.bold = True; r.font.color.rgb = QC_BLUE
    p.paragraph_format.space_before = Pt(16); p.paragraph_format.space_after = Pt(4)
    pPr = p._p.get_or_add_pPr(); pBdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    b.set(qn("w:val"), "single"); b.set(qn("w:sz"), "8"); b.set(qn("w:space"), "4"); b.set(qn("w:color"), "C3CBE0")
    pBdr.append(b); pPr.append(pBdr)


def h2(text):
    p = doc.add_paragraph()
    r = p.add_run(text); r.font.size = Pt(12.5); r.font.bold = True; r.font.color.rgb = QC_DARK
    p.paragraph_format.space_before = Pt(10); p.paragraph_format.space_after = Pt(2)


def body(text, indent=0.0, after=4):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(indent); p.paragraph_format.space_after = Pt(after)
    add_rich(p, text)


def numbered(n, text, indent=0.1):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3); p.paragraph_format.left_indent = Inches(indent)
    r = p.add_run(f"{n}.  "); r.font.bold = True; r.font.color.rgb = QC_ACCENT
    add_rich(p, text)


def bullet(text, indent=0.3):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Inches(indent); p.paragraph_format.space_after = Pt(3)
    add_rich(p, text)


def note(text, label="Note", fill=NOTE_BG, border="E8C66B", lab=RGBColor(0xB5, 0x7A, 0x00)):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6); p.paragraph_format.space_after = Pt(6)
    shade(p, fill); borders(p, color=border)
    r = p.add_run(label + "   "); r.font.bold = True; r.font.color.rgb = lab
    add_rich(p, text)


# ============ SECTION ============
h1("3.  Accessing the devrelAgent Repository")

rp = doc.add_paragraph()
rp.paragraph_format.left_indent = Inches(0.1)
rr = rp.add_run("Repository:  ")
rr.font.bold = True
lr = rp.add_run("https://github.com/CBN-AI-TEAM/devrelAgent")
lr.font.color.rgb = QC_ACCENT; lr.underline = True
rp.paragraph_format.space_after = Pt(4)

body("This repository is **Internal** to the Qualcomm GitHub Enterprise. It is **not public** and "
     "cannot be made public. You can only access it while signed in to **github.com** with your "
     "Qualcomm-managed (EMU) account — the one that looks like `username_QCOM`.", indent=0.1)

note("**github.com** and **github.qualcomm.com** are two different sites with separate logins. "
     "This repository lives on **github.com**. Make sure you are on the correct site.")

h2("Step 1 — Sign in with the right account")
numbered(1, "Go to `https://github.com` and check the account shown in the top-right corner.")
numbered(2, "You must be signed in as your **`*_QCOM` Enterprise Managed User (EMU)** account via "
            "Qualcomm SSO — **not** a personal github.com account.")
numbered(3, "If you are on a personal account, sign out and sign back in through the Qualcomm SSO flow.")

h2("Step 2 — Confirm enterprise access")
body("Open `https://github.com/CBN-AI-TEAM` while signed in:", indent=0.1)
bullet("**If you see the organization**, you have access. Go to the repository: "
       "`https://github.com/CBN-AI-TEAM/devrelAgent`")
bullet("**If you get a 404 / \"not found\"**, your account is not yet provisioned into the "
       "CBN-AI-TEAM enterprise. **Request enterprise provisioning from IT** (the GitHub "
       "Enterprise / EMU access group, via the standard IT access request). This is "
       "identity-managed and cannot be granted by the repository owner directly.")

h2("Step 3 — Command line / git clone")
body("If the browser works but the command line does not, confirm the GitHub CLI is pointed at "
     "github.com with your `_QCOM` account:", indent=0.1)
code_block([
    "gh auth status",
    "gh auth login --hostname github.com      # if logged into the wrong host or account",
    "git clone https://github.com/CBN-AI-TEAM/devrelAgent.git",
])
body("A stale saved credential for github.com is a common cause of failure. If clone still fails, "
     "clear the github.com entry in your OS credential manager (Windows Credential Manager or "
     "macOS Keychain) and authenticate again.", indent=0.1)

h2("Still stuck?")
body("A **404 means \"no access,\" not \"does not exist\"** — GitHub hides internal repositories "
     "from non-members. Almost always the cause is one of:", indent=0.1)
numbered(1, "Wrong account (personal vs. `_QCOM`) or wrong site (github.com vs. github.qualcomm.com), or")
numbered(2, "Not yet provisioned into the enterprise — submit an **IT access request**.")

out = r"C:\work\DevRel\devrelAgent\docs\Section3_Accessing_the_Repository.docx"
doc.save(out)
print("Saved:", out)
