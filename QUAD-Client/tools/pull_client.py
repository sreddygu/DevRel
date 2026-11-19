#!/usr/bin/env python3
"""pull_client.py — client-side bundle pull against the remote QUAD registry.

The MCP `aihub_select(action=pull)` tool runs the compat check using the
SERVER's hardware_detect, which on this deployment mis-reports the X-Elite as
"Snapdragon X (Compute, Windows)" / 0 TOPS and wrongly fails the run-fit gate.

This driver instead runs `pull_bundle` locally with THIS host's real detect
profile, while streaming the archive bytes from the server's HTTP /bundles
routes (registry_url). Identical download + sha256 verify + atomic unpack —
just with the correct device profile for the compat verdict.

Usage:
  python pull_client.py <model_id> <dest_dir>
Env:
  QUAD_MCP_TOKEN   bearer for the /bundles routes (required)
  QUAD_REGISTRY_URL  base URL (default http://10.227.21.202:8000)
"""
import json
import os
import sys
from pathlib import Path

# Make the QUAD server package importable (bundle_registry lives there).
QUAD_SRC = Path(r"C:\work\QUAD\QUAD\src")
if str(QUAD_SRC) not in sys.path:
    sys.path.insert(0, str(QUAD_SRC))

from quad.bundle_registry.pull import PullError, pull_bundle  # noqa: E402


def _local_profile() -> dict:
    """Real hardware profile for THIS host (not the server's self-detect)."""
    prof_file = Path(__file__).with_name("local_profile.json")
    if prof_file.exists():
        return json.loads(prof_file.read_text())
    # Fallback: probe locally via the client CLI hardware module.
    from quad_mcp_client.local.hardware import detect_hardware  # type: ignore
    return detect_hardware()


def _progress(done: int, total: int) -> None:
    pct = (done / total * 100) if total else 0
    sys.stderr.write(f"\r  download {done/1e6:8.1f} / {total/1e6:8.1f} MB ({pct:5.1f}%)")
    sys.stderr.flush()


def main() -> int:
    model_id = sys.argv[1] if len(sys.argv) > 1 else "falcon-v3-7b-instruct"
    dest = sys.argv[2] if len(sys.argv) > 2 else None
    url = os.environ.get("QUAD_REGISTRY_URL", "http://10.227.21.202:8000")
    token = os.environ.get("QUAD_MCP_TOKEN")
    if not token:
        print("ERROR: QUAD_MCP_TOKEN not set", file=sys.stderr)
        return 2

    profile = _local_profile()
    print(f"client profile chipset: {profile.get('chipset')!r}", file=sys.stderr)
    try:
        result = pull_bundle(
            model_id,
            profile,
            registry_url=url,
            token=token,
            dest=dest,
            verify=True,
            verify_run=False,   # genai isn't in this x86 venv; verify on arm64 separately
            progress=_progress,
        )
    except PullError as exc:
        print(f"\nPullError: {exc}", file=sys.stderr)
        return 3
    sys.stderr.write("\n")
    out = {
        "ok": result.get("ok"),
        "verified": result.get("verified"),
        "compat_verdict": (result.get("compat_verdict") or {}).get("verdict"),
        "device_class": (result.get("compat_verdict") or {}).get("device_class"),
        "local_path": result.get("local_path"),
    }
    print(json.dumps(out, indent=2).encode("ascii", "replace").decode())
    return 0 if result.get("ok") else 4


if __name__ == "__main__":
    raise SystemExit(main())
