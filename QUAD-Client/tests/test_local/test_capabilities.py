"""The vendored capabilities table must keep resolving the four known chipsets."""

from __future__ import annotations

from quad_mcp_client.local.capabilities import known_chipsets, lookup_for_chipset


def test_snapdragon_x_elite_with_trademark_glyphs() -> None:
    cap = lookup_for_chipset("Snapdragon(R) X Elite - X1E78100 - Qualcomm(R) Oryon(TM) CPU")
    assert cap is not None
    assert cap["chipset"] == "Snapdragon X Elite"
    assert cap["npu_tops"] == 45.0


def test_all_known_chipsets_resolve() -> None:
    for chipset in known_chipsets():
        assert lookup_for_chipset(chipset) is not None


def test_qcs9075_registered() -> None:
    """IQ-9075 / QCS9075 was previously unknown to the client (issue IQ9-27)."""
    cap = lookup_for_chipset("QCS9075")
    assert cap is not None
    assert cap["npu_tops"] == 20.0
    assert "v73" in cap["npu_model"]
    assert cap["gpu_model"] == "Adreno 663"


def test_unknown_chipset_returns_none() -> None:
    assert lookup_for_chipset("Apple M3 Pro") is None
    assert lookup_for_chipset("") is None
    assert lookup_for_chipset(None) is None
