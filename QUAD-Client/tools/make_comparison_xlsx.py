"""Generate a formatted Modular vs QUAD comparison .xlsx."""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

wb = Workbook()
ws = wb.active
ws.title = "Modular vs QUAD"

headers = ["Dimension", "Modular (MAX/Mojo)", "QUAD"]
rows = [
    ["Hardware target", "Datacenter GPUs — NVIDIA & AMD, plus server CPUs",
     "Qualcomm Snapdragon SoCs — Hexagon NPU, Adreno GPU, Oryon CPU"],
    ["Environment", "Cloud / server, large-scale serving",
     "Edge / on-device — AI PCs, Android, Arduino UNO Q"],
    ["Core problem", "Break CUDA lock-in for cloud inference",
     "Make Qualcomm NPU/QNN/SNPE development tractable"],
    ["Primary workload", "High-throughput LLM serving",
     "Vision, ASR, LLMs under power/thermal budgets"],
    ["Key abstraction", "Mojo kernels + MAX graph compiler",
     "MCP tools (hardware_detect, convert_model, profile_workload, orchestrate_workload, generate_code) + skills"],
    ["Optimization lens", "Throughput/cost per GPU",
     "Latency + power (e.g. NPU at ~4.5 W vs CPU ~10.7 W)"],
]

# ---- styles ----
QC_BLUE = "3B559E"
header_font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
header_fill = PatternFill("solid", fgColor=QC_BLUE)
dim_font = Font(name="Calibri", size=11, bold=True, color="1F2A44")
dim_fill = PatternFill("solid", fgColor="EAF0FB")
body_font = Font(name="Calibri", size=11, color="1F2A44")
stripe_fill = PatternFill("solid", fgColor="F2F3F7")
thin = Side(style="thin", color="C3CBE0")
border = Border(left=thin, right=thin, top=thin, bottom=thin)
wrap_top = Alignment(wrap_text=True, vertical="center", horizontal="left")
center = Alignment(vertical="center", horizontal="left")

# ---- header row ----
for col, h in enumerate(headers, start=1):
    c = ws.cell(row=1, column=col, value=h)
    c.font = header_font
    c.fill = header_fill
    c.alignment = Alignment(vertical="center", horizontal="left")
    c.border = border
ws.row_dimensions[1].height = 24

# ---- data rows ----
for i, row in enumerate(rows, start=2):
    for col, val in enumerate(row, start=1):
        c = ws.cell(row=i, column=col, value=val)
        c.border = border
        c.alignment = wrap_top
        if col == 1:
            c.font = dim_font
            c.fill = dim_fill
        else:
            c.font = body_font
            if i % 2 == 1:
                c.fill = stripe_fill
    ws.row_dimensions[i].height = 38

# ---- column widths ----
ws.column_dimensions["A"].width = 20
ws.column_dimensions["B"].width = 42
ws.column_dimensions["C"].width = 70

# freeze header
ws.freeze_panes = "A2"

out = r"C:\work\QUAD\QUAD-Client\docs\Modular_vs_QUAD_Comparison.xlsx"
wb.save(out)
print("Saved:", out)
