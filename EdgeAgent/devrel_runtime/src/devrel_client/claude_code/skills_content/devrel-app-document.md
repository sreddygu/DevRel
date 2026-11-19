---
name: devrel-app-document
description: Use when the user asks "generate documentation", "create docs for this app", "write architecture doc", "create a Word document for this project", "document this application", or invokes /devrel-app-document. Generates ARCHITECTURE.md and app_documentation.docx for any DevRel application directory.
trigger: "app-document"
---

# DevRel App Documentation Generator

Generate comprehensive documentation for an existing DevRel application.
Produces both Markdown (for GitHub) and Word (.docx, for stakeholders).

## Prerequisites

- An existing DevRel application directory with inference code
- Profiling results (run `devrel-profile` first for accurate KPIs)
- `python-docx` installed (`pip install python-docx`)

## Steps

### 1. Gather app metadata

Read the application directory to understand:
- App name (from directory name or main script)
- Model used (from code or CLI args)
- Target platform and runtime
- Input/output formats
- Dependencies (from requirements.txt)

If profiling data is available (from a previous `devrel-profile` call
or captured metrics in the code), extract:
- Latency (mean, p95, p99)
- Throughput (FPS)
- Power draw (mW)
- Memory usage (peak MB)
- Model size (original and compressed)

### 2. Generate ARCHITECTURE.md

Write `ARCHITECTURE.md` in the app directory with these sections:

1. **Overview** — 1-2 paragraph description
2. **System Diagram** — ASCII art showing data flow through DevRel pipeline
3. **Components** — table of files, their purpose, and dependencies
4. **Model Card** — model name, task, input/output shapes, quantization, accuracy
5. **Data Flow** — numbered steps from raw input to final output
6. **KPI Summary** — table comparing CPU / GPU / NPU performance
7. **Build & Run** — copy of setup instructions from README.md
8. **Dependencies** — extracted from requirements.txt with version pins

### 3. Generate app_doc_config.json

Create a JSON config file describing the app for the .docx generator:

```json
{
    "app_name": "MobileNetV2 Classifier",
    "author": "DevRel App Builder",
    "date": "2026-05-13",
    "description": "Image classification on Snapdragon X Elite...",
    "architecture": {
        "diagram": "Input -> Preprocess -> QNN Runtime -> Postprocess -> Output",
        "components": [
            {"name": "Preprocessor", "file": "preprocess.py", "description": "..."},
        ]
    },
    "model_card": {
        "name": "MobileNetV2",
        "task": "Image Classification",
        "input_shape": "[1, 3, 224, 224]",
        "output_shape": "[1, 1000]",
        "quantization": "INT8",
        "size_mb": 3.4
    },
    "kpis": {
        "cpu": {"latency_ms": 6.4, "throughput_fps": 157, "power_mw": 10700},
        "gpu": {"latency_ms": 4.2, "throughput_fps": 238, "power_mw": 8000},
        "npu": {"latency_ms": 5.5, "throughput_fps": 183, "power_mw": 4500}
    },
    "usage": {
        "setup": ".\\run.ps1",
        "run": ".venv\\Scripts\\python.exe app.py --image test.jpg",
        "deploy": "devrel deploy --target android"
    },
    "troubleshooting": [
        {"symptom": "ModuleNotFoundError", "fix": "Run .\\run.ps1"},
    ]
}
```

### 4. Generate .docx

Run the doc generator:

```bash
.venv/Scripts/python.exe -m devrel_client.doc_generator \
    --config app_doc_config.json \
    --output app_documentation.docx
```

If `python-docx` is not installed, add it to requirements.txt and
re-run `run.ps1`.

### 5. Present results

Show the user:
- Path to `ARCHITECTURE.md`
- Path to `app_documentation.docx`
- Summary of what each document contains
- Suggest: "Use `devrel-app-builder` Phase 7 to push these to GitHub"

## Output format

```
Documentation generated:
  ARCHITECTURE.md          — 120 lines, 8 sections
  app_documentation.docx   — 12 pages, 9 sections

Sections included:
  1. Title Page
  2. Table of Contents
  3. Architecture Overview
  4. System Diagram
  5. Setup & Installation
  6. Usage Guide
  7. KPI Summary (CPU vs GPU vs NPU)
  8. Troubleshooting
  9. Model Card & Appendix
```
