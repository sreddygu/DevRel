"""Find a QAIRT/QNN/SNPE SDK installation without importing quad-agent.

Search order (mirrors what QUAD's `sdk_manager.resolve_sdk_root` does in spirit,
but rebuilt in <100 lines and with no `quad.*` imports):

1. Environment variables in priority order:
   ``QAIRT_SDK_ROOT`` -> ``QNN_SDK_ROOT`` -> ``SNPE_ROOT``.
   First one whose path exists wins.

2. Sibling repo: when QUAD-Client is checked out next to QUAD, look in
   ``../QUAD/sdks/`` for any ``qairt-*`` / ``v*`` directory and pick the
   newest by version regex. This is the primary "developer machine"
   path: install.ps1 deposits the SDK there.

3. Vendor defaults:
   - Windows: ``C:\\Qualcomm\\AIStack\\QAIRT\\*``
   - Linux/macOS: ``/opt/qcom/aistack/qairt/*``

Each step is wrapped in try/except so a missing sibling repo or unreadable
directory never breaks the probe -- it just returns ``(None, None)``.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+(?:\.\d+)?)")


def _newest_version_dir(root: Path) -> Path | None:
    """Pick the directory under ``root`` whose name has the highest version tuple."""
    if not root.is_dir():
        return None
    best: tuple[tuple[int, ...], Path] | None = None
    try:
        children = list(root.iterdir())
    except OSError:
        return None
    for child in children:
        if not child.is_dir():
            continue
        m = _VERSION_RE.search(child.name)
        if not m:
            continue
        ver = tuple(int(p) for p in m.group(1).split("."))
        if best is None or ver > best[0]:
            best = (ver, child)
    return best[1] if best else None


def _version_from_path(path: Path) -> str | None:
    m = _VERSION_RE.search(str(path))
    return m.group(1) if m else None


def find_sdk(*, project_root: Path | None = None) -> tuple[str | None, str | None]:
    """Return ``(sdk_path, sdk_version)`` for the first SDK found, or ``(None, None)``.

    ``project_root`` defaults to QUAD-Client's repo root; pass an explicit
    value in tests to control sibling-lookup.
    """
    # 1. Env vars
    for env_var in ("QAIRT_SDK_ROOT", "QNN_SDK_ROOT", "SNPE_ROOT"):
        val = os.environ.get(env_var, "").strip()
        if not val:
            continue
        path = Path(val)
        if path.exists():
            return str(path), _version_from_path(path) or path.name

    # 2. Sibling QUAD repo
    if project_root is None:
        project_root = Path(__file__).resolve().parents[3]
    sibling_sdks = project_root.parent / "QUAD" / "sdks"
    sibling_pick = _newest_version_dir(sibling_sdks)
    if sibling_pick:
        return str(sibling_pick), _version_from_path(sibling_pick) or sibling_pick.name

    # 3. Vendor defaults
    if sys.platform == "win32":
        vendor_root = Path(r"C:\Qualcomm\AIStack\QAIRT")
    else:
        vendor_root = Path("/opt/qcom/aistack/qairt")
    vendor_pick = _newest_version_dir(vendor_root)
    if vendor_pick:
        return str(vendor_pick), _version_from_path(vendor_pick) or vendor_pick.name

    return None, None
