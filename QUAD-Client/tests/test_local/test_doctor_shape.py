"""Doctor checks must produce shape-correct results regardless of the
host machine's actual SDK installation status.
"""

from __future__ import annotations

import sys

from quad_mcp_client.local import has_failures, run_doctor


def test_each_check_has_required_keys_and_valid_status() -> None:
    results = run_doctor()
    assert results, "expected at least one check"
    for c in results:
        assert set(c.keys()) == {"name", "status", "message"}, f"unexpected keys: {c.keys()}"
        assert c["status"] in {"pass", "warn", "fail"}, f"bad status: {c['status']!r}"
        assert isinstance(c["name"], str) and c["name"]
        assert isinstance(c["message"], str)


def test_real_mode_only_escalates_known_warnings() -> None:
    plain = {c["name"]: c["status"] for c in run_doctor(real_mode=False)}
    strict = {c["name"]: c["status"] for c in run_doctor(real_mode=True)}
    # Names that strict-mode is allowed to escalate from warn to fail.
    escalatable = {
        "SDK env vars",
        "SDK tools in PATH",
        "DSP env (ADSP_LIBRARY_PATH)",
        "DLC compatibility (>=1.16)",
        "onnxruntime package conflict",
        "Active venv for NPU",
    }
    for name, status in strict.items():
        if status == "fail" and plain.get(name) == "warn":
            assert name in escalatable, f"unexpected escalation: {name}"


def test_python_version_check_reflects_npu_wheel_policy() -> None:
    """3.10–3.12 pass; 3.13 warns; 3.14+ fails (NPU wheels are 3.10–3.12 only)."""
    pyver = next(c for c in run_doctor() if c["name"] == "Python version")
    v = sys.version_info
    if (3, 10) <= (v.major, v.minor) <= (3, 12):
        assert pyver["status"] == "pass"
    elif (v.major, v.minor) == (3, 13):
        assert pyver["status"] == "warn"
    else:  # < 3.10 or >= 3.14
        assert pyver["status"] == "fail"
        assert "3.10 to 3.12" in pyver["message"]


def test_has_failures_true_when_any_failure() -> None:
    fake = [
        {"name": "x", "status": "pass", "message": ""},
        {"name": "y", "status": "fail", "message": ""},
    ]
    assert has_failures(fake) is True
