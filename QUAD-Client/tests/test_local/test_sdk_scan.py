"""SDK-scan resolution order: env vars -> sibling QUAD repo -> vendor defaults."""

from __future__ import annotations

from pathlib import Path

from quad_mcp_client.local.sdk_scan import find_sdk


def test_env_var_wins(monkeypatch, tmp_path: Path) -> None:
    fake = tmp_path / "qairt-2.45.0"
    fake.mkdir()
    monkeypatch.setenv("QAIRT_SDK_ROOT", str(fake))
    monkeypatch.delenv("QNN_SDK_ROOT", raising=False)
    monkeypatch.delenv("SNPE_ROOT", raising=False)
    path, version = find_sdk(project_root=tmp_path / "client-isolated")
    assert path == str(fake)
    assert version == "2.45.0"


def test_missing_env_falls_through_without_crashing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("QAIRT_SDK_ROOT", raising=False)
    monkeypatch.delenv("QNN_SDK_ROOT", raising=False)
    monkeypatch.delenv("SNPE_ROOT", raising=False)
    isolated = tmp_path / "no-sibling"
    isolated.mkdir()
    # No sibling, no vendor default -> (None, None)
    path, version = find_sdk(project_root=isolated)
    if path is None:
        assert version is None
    # else: vendor default may exist on a real dev machine -- that's also fine,
    # we just assert the function doesn't crash.


def test_invalid_env_path_skipped(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("QAIRT_SDK_ROOT", "C:/this/does/not/exist")
    monkeypatch.delenv("QNN_SDK_ROOT", raising=False)
    monkeypatch.delenv("SNPE_ROOT", raising=False)
    isolated = tmp_path / "no-sibling"
    isolated.mkdir()
    path, version = find_sdk(project_root=isolated)
    # Either falls through to (None, None) or finds a vendor default -- both fine.
    if path is not None:
        assert Path(path).exists()
