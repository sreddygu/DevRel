"""Extensive unit tests for scripts/board_profile.py's core functions.

board_profile.py is a standalone script under scripts/, not part of the
quad_mcp_client package, so it's loaded via importlib rather than a normal
import. Loading it once per test session (module-scoped fixture) is safe
because none of its top-level code has side effects beyond defining names --
it only executes I/O inside main()/cmd_*() functions, guarded by
`if __name__ == "__main__":`.

No live hardware is required anywhere in this file -- every test either
exercises a pure function directly, or feeds hand-built fixture strings
through the parsing/filtering functions to simulate probe output. Where a
prior manual (live-board) verification exists, see
docs/debugging/SoC_Identity_DSP_Skel_False_Positive.md and
docs/debugging/Board_Auto_Detect_RB5_RubioPi.md for the real-hardware
confirmation this suite is meant to guard against regressing.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "board_profile.py"


@pytest.fixture(scope="session")
def bp():
    """Load board_profile.py once per test session.

    Registering in sys.modules BEFORE exec_module is load-bearing: the
    @dataclass decorator on BoardProfile calls _is_type(), which looks up
    cls.__module__ in sys.modules -- if the module isn't registered yet,
    that lookup returns None and dataclass() raises AttributeError. This
    bit an earlier manual verification attempt in this same investigation
    (see docs/debugging/Verification_Pass_SoC_Skel_SSH_Target.md) before
    being understood and fixed here.
    """
    spec = importlib.util.spec_from_file_location("board_profile_under_test", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["board_profile_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


# ─────────────────────────────────────────────────────────────────────────
# BOARD_PROFILES registry -- every board this repo claims to support
# ─────────────────────────────────────────────────────────────────────────


class TestBoardProfilesRegistry:
    def test_all_expected_boards_present(self, bp):
        assert set(bp.BOARD_PROFILES.keys()) == {"iq-9075", "uno-q", "rubio-pi", "rb5", "generic"}

    def test_generic_is_the_unconfirmed_fallback(self, bp):
        g = bp.BOARD_PROFILES["generic"]
        assert g.soc == "unknown"
        assert g.confirmed_fields == ()
        assert g.ram_mb is None

    @pytest.mark.parametrize(
        "board_id,expected_soc,expected_hexagon,expected_tops,expected_ram",
        [
            ("iq-9075", "qcs9075", "v73", 100.0, 35285),
            ("uno-q", "qcs2210", "v66", 1.0, 2048),
            ("rubio-pi", "qcs6490", "v69", 12.0, 8192),
            ("rb5", "qcs8250", "v68", 15.0, 8192),
        ],
    )
    def test_registered_board_specs(self, bp, board_id, expected_soc, expected_hexagon, expected_tops, expected_ram):
        p = bp.BOARD_PROFILES[board_id]
        assert p.soc == expected_soc
        assert p.hexagon_version == expected_hexagon
        assert p.npu_tops_dense == expected_tops
        assert p.ram_mb == expected_ram

    def test_no_two_boards_declare_the_same_soc(self, bp):
        """A silent duplicate soc across two real (non-generic) board_ids
        would make resolve_board_id_from_soc0 ambiguous for every user of
        that SoC, not just a --board-json edge case. Guard the registry
        itself, not just the resolver's ambiguity-reporting path below."""
        socs = [p.soc for bid, p in bp.BOARD_PROFILES.items() if bid != "generic"]
        assert len(socs) == len(set(socs)), f"duplicate soc values in BOARD_PROFILES: {socs}"

    def test_rb5_and_rubio_pi_not_marked_confirmed(self, bp):
        """Unlike iq-9075/uno-q, no live `detect` has ever run against a
        physical rb5/rubio-pi unit in this repo -- confirmed_fields must
        stay empty until that happens for real (see caveat in
        docs/debugging/Board_Auto_Detect_RB5_RubioPi.md)."""
        assert bp.BOARD_PROFILES["rb5"].confirmed_fields == ()
        assert bp.BOARD_PROFILES["rubio-pi"].confirmed_fields == ()


# ─────────────────────────────────────────────────────────────────────────
# resolve_profile() / _build_registry() -- --board-json overlay behavior
# ─────────────────────────────────────────────────────────────────────────


class TestResolveProfile:
    def test_known_board_resolves_directly(self, bp):
        p = bp.resolve_profile("iq-9075", None)
        assert p.board_id == "iq-9075"

    def test_unknown_board_falls_back_to_generic_with_warning(self, bp, capsys):
        p = bp.resolve_profile("totally-made-up-board", None)
        assert p.board_id == "generic"
        captured = capsys.readouterr()
        assert "unknown --board" in captured.err

    def test_board_json_single_profile_overlay(self, bp, tmp_path):
        overlay = tmp_path / "override.json"
        overlay.write_text(
            '{"board_id": "custom-board", "soc": "qcs1234", "aihub_chipset": "", '
            '"npu_arch": "x", "npu_tops_dense": null, "ram_mb": null, "hexagon_version": null}'
        )
        p = bp.resolve_profile("custom-board", overlay)
        assert p.board_id == "custom-board"
        assert p.soc == "qcs1234"

    def test_board_json_registry_style_overlay(self, bp, tmp_path):
        overlay = tmp_path / "override.json"
        overlay.write_text(
            '{"board-a": {"board_id": "board-a", "soc": "qcsA", "aihub_chipset": "", '
            '"npu_arch": "x", "npu_tops_dense": null, "ram_mb": null, "hexagon_version": null}, '
            '"board-b": {"board_id": "board-b", "soc": "qcsB", "aihub_chipset": "", '
            '"npu_arch": "x", "npu_tops_dense": null, "ram_mb": null, "hexagon_version": null}}'
        )
        a = bp.resolve_profile("board-a", overlay)
        b = bp.resolve_profile("board-b", overlay)
        assert (a.soc, b.soc) == ("qcsA", "qcsB")

    def test_board_json_can_override_a_builtin_board(self, bp, tmp_path):
        overlay = tmp_path / "override.json"
        overlay.write_text(
            '{"board_id": "iq-9075", "soc": "qcs9075", "aihub_chipset": "", '
            '"npu_arch": "x", "npu_tops_dense": 999.0, "ram_mb": null, "hexagon_version": null}'
        )
        p = bp.resolve_profile("iq-9075", overlay)
        assert p.npu_tops_dense == 999.0  # overlay wins over the built-in entry

    def test_build_registry_used_by_both_resolve_profile_and_auto_path(self, bp, tmp_path):
        """resolve_profile() and cmd_detect()'s --board auto path must build
        the registry identically -- via the same _build_registry() helper,
        not two copies that can drift (this was a real duplication found
        and fixed during this investigation)."""
        overlay = tmp_path / "override.json"
        overlay.write_text(
            '{"board_id": "dup-test", "soc": "qcsdup", "aihub_chipset": "", '
            '"npu_arch": "x", "npu_tops_dense": null, "ram_mb": null, "hexagon_version": null}'
        )
        via_resolve_profile = bp.resolve_profile("dup-test", overlay)
        via_build_registry = bp._build_registry(overlay, "dup-test")["dup-test"]
        assert via_resolve_profile.soc == via_build_registry.soc == "qcsdup"


# ─────────────────────────────────────────────────────────────────────────
# resolve_board_id_from_soc0() -- the --board auto resolver
# ─────────────────────────────────────────────────────────────────────────


class TestResolveBoardIdFromSoc0:
    @pytest.mark.parametrize(
        "soc0_machine,expected_board_id",
        [
            ("QCS9075", "iq-9075"),
            ("qcs9075", "iq-9075"),  # case-insensitive
            ("QCS2210", "uno-q"),
            ("QCS6490", "rubio-pi"),
            ("QCS8250", "rb5"),
        ],
    )
    def test_registered_socs_resolve(self, bp, soc0_machine, expected_board_id):
        board_id, matches = bp.resolve_board_id_from_soc0(soc0_machine, bp.BOARD_PROFILES)
        assert board_id == expected_board_id
        assert matches == [expected_board_id]

    def test_unregistered_soc_returns_none(self, bp):
        board_id, matches = bp.resolve_board_id_from_soc0("QCS9999", bp.BOARD_PROFILES)
        assert board_id is None
        assert matches == []

    def test_empty_string_returns_none(self, bp):
        board_id, matches = bp.resolve_board_id_from_soc0("", bp.BOARD_PROFILES)
        assert board_id is None

    def test_generic_profile_is_never_matched(self, bp):
        """generic.soc == 'unknown' must never be treated as a real match --
        otherwise a device that fails to report soc0 at all could spuriously
        resolve to 'generic' as if it were a confirmed identification."""
        board_id, matches = bp.resolve_board_id_from_soc0("unknown", bp.BOARD_PROFILES)
        assert board_id is None
        assert "generic" not in matches

    def test_ambiguous_soc_reports_all_matches(self, bp):
        """A --board-json overlay introducing a second board with the same
        soc as an existing one must be surfaced as ambiguous, not silently
        resolved by dict iteration order (a real gap found and fixed during
        this investigation's critical review)."""
        registry = dict(bp.BOARD_PROFILES)
        registry["duplicate-soc-board"] = bp.BoardProfile(
            board_id="duplicate-soc-board", soc="qcs9075", aihub_chipset="",
            npu_arch="x", npu_tops_dense=None, ram_mb=None, hexagon_version=None,
        )
        board_id, matches = bp.resolve_board_id_from_soc0("QCS9075", registry)
        assert board_id is not None  # a result is still returned (first match)...
        assert len(matches) > 1       # ...but the caller can detect and report the ambiguity
        assert set(matches) == {"iq-9075", "duplicate-soc-board"}

    def test_hyphen_and_underscore_normalization(self, bp):
        """soc comparison strips hyphens/underscores so 'qcs-9075' and
        'qcs_9075' style variants still match 'qcs9075'."""
        registry = {
            "hyphen-board": bp.BoardProfile(
                board_id="hyphen-board", soc="qcs-9999", aihub_chipset="",
                npu_arch="x", npu_tops_dense=None, ram_mb=None, hexagon_version=None,
            )
        }
        board_id, _ = bp.resolve_board_id_from_soc0("qcs9999", registry)
        assert board_id == "hyphen-board"


# ─────────────────────────────────────────────────────────────────────────
# _reject_board_auto_outside_detect() -- the --board auto guard
# ─────────────────────────────────────────────────────────────────────────


class TestRejectBoardAutoOutsideDetect:
    @pytest.mark.parametrize("subcommand", ["configure", "push", "profile", "report"])
    def test_board_auto_rejected_for_non_detect_subcommands(self, bp, subcommand):
        args = argparse.Namespace(board="auto")
        err = bp._reject_board_auto_outside_detect(args, subcommand)
        assert err is not None
        assert subcommand in err
        assert "detect" in err.lower()

    def test_board_auto_case_insensitive(self, bp):
        args = argparse.Namespace(board="AUTO")
        err = bp._reject_board_auto_outside_detect(args, "push")
        assert err is not None

    def test_real_board_id_not_rejected(self, bp):
        args = argparse.Namespace(board="iq-9075")
        err = bp._reject_board_auto_outside_detect(args, "push")
        assert err is None


# ─────────────────────────────────────────────────────────────────────────
# _filter_skel_by_soc0() -- SoC-aware skel filtering (the original bug fix)
# ─────────────────────────────────────────────────────────────────────────


class TestFilterSkelBySoc0:
    REAL_MULTI_SOC_SKEL_LIST = "\n".join([
        "/usr/share/qcom/qcs8300/Qualcomm/QCS8300-RIDE/dsp/cdsp/libSnpeHtpV75Skel.so",
        "/usr/share/qcom/qcm6490/Thundercomm/RB3gen2/dsp/cdsp/libQnnHtpV68Skel.so",
        "/usr/share/qcom/qcs615/Qualcomm/QCS615-RIDE/dsp/cdsp/libSnpeDspV66Skel.so",
        "/usr/share/qcom/sa8775p/Qualcomm/SA8775P-RIDE/dsp/cdsp/libQnnHtpV73Skel.so",
        "/usr/share/qcom/sa8775p/Qualcomm/SA8775P-RIDE/dsp/cdsp/libQnnNetRunDirectV73Skel.so",
        "/usr/share/qcom/sa8775p/Qualcomm/SA8775P-RIDE/dsp/cdsp1/libQnnHtpV73Skel.so",
    ])

    def test_filters_to_only_the_matching_soc_version(self, bp):
        filtered, warning = bp._filter_skel_by_soc0(self.REAL_MULTI_SOC_SKEL_LIST, "QCS9075\n676")
        lines = filtered.splitlines()
        assert warning is None
        assert len(lines) == 3
        assert all("v73" in line.lower() for line in lines)
        assert not any("v75" in line.lower() or "v68" in line.lower() or "v66" in line.lower() for line in lines)

    def test_registered_but_different_soc_filters_correctly(self, bp):
        """UNO Q (v66) filtering the same multi-SoC list should surface only
        the v66 entry, not the v73 one -- proves the filter is genuinely
        soc0-driven, not hardcoded to whichever board was tested first."""
        filtered, warning = bp._filter_skel_by_soc0(self.REAL_MULTI_SOC_SKEL_LIST, "QCS2210\n123")
        assert warning is None
        assert filtered.strip() == (
            "/usr/share/qcom/qcs615/Qualcomm/QCS615-RIDE/dsp/cdsp/libSnpeDspV66Skel.so"
        )

    def test_unregistered_soc_fails_open_with_warning(self, bp):
        """A soc0 reading that resolves to no capabilities.py entry (e.g.
        rb5/rubio-pi before they were registered, or any future
        not-yet-registered SoC) must return the UNFILTERED list with an
        explicit warning -- never silently guess a filter, never crash."""
        filtered, warning = bp._filter_skel_by_soc0(self.REAL_MULTI_SOC_SKEL_LIST, "QCS9999\n000")
        assert filtered == self.REAL_MULTI_SOC_SKEL_LIST
        assert warning is not None
        assert "registry has no" in warning

    def test_no_matches_at_all_fails_open_with_warning(self, bp):
        """A resolvable SoC whose HTP version genuinely doesn't appear in
        the skel list (e.g. skel filed under a differently-named variant
        folder) must also fail open, not report an empty/silent result."""
        skel_list = "/usr/share/qcom/qcs8300/Qualcomm/QCS8300-RIDE/dsp/cdsp/libSnpeHtpV75Skel.so"
        filtered, warning = bp._filter_skel_by_soc0(skel_list, "QCS9075\n676")  # v73, list only has v75
        assert filtered == skel_list  # unfiltered passthrough
        assert warning is not None
        assert "none of the" in warning

    def test_empty_skel_list_passthrough(self, bp):
        filtered, warning = bp._filter_skel_by_soc0("none", "QCS9075\n676")
        assert filtered == "none"
        assert warning is None

    def test_unreadable_soc0_passthrough(self, bp):
        filtered, warning = bp._filter_skel_by_soc0("libFooV1Skel.so", "none")
        assert filtered == "libFooV1Skel.so"
        assert warning is None

    def test_empty_soc0_string_passthrough(self, bp):
        filtered, warning = bp._filter_skel_by_soc0("libFooV1Skel.so", "")
        assert filtered == "libFooV1Skel.so"
        assert warning is None

    @pytest.mark.parametrize(
        "filename,should_match_v73",
        [
            ("libQnnHtpV73Skel.so", True),
            ("libSnpeHtpV73CalculatorStub.so", True),  # real filename observed on-device
            ("libSnpeHtpV75Skel.so", False),
            ("libQnnHtpV730Skel.so", False),  # must NOT match v73 as a substring of v730
            ("libQnnHtpV7Skel.so", False),
            ("libQnnHtpV173Skel.so", False),
        ],
    )
    def test_regex_boundary_regression_matrix(self, bp, filename, should_match_v73):
        """Regression guard for TWO real bugs caught during this
        investigation: (1) `v73\\b` never matches `...V73Skel...` because
        there's no word-boundary between adjacent word characters -- fixed
        with a negative lookahead instead. (2) a same-day attempt to also
        exclude letter-suffix variants via `(?![0-9a-z])` was ITSELF broken
        by re.IGNORECASE making the character class match the uppercase 'S'
        in 'Skel' too, silently breaking the filter -- reverted. This test
        exists so neither regression can silently reappear.
        See docs/debugging/Verification_Pass_SoC_Skel_SSH_Target.md.
        """
        filtered, warning = bp._filter_skel_by_soc0(filename, "QCS9075\n676")
        matched = filtered == filename and warning is None
        assert matched == should_match_v73, (
            f"{filename!r}: expected match={should_match_v73}, "
            f"got filtered={filtered!r} warning={warning!r}"
        )


# ─────────────────────────────────────────────────────────────────────────
# _parse_sections() -- the ===section=== probe-output parser
# ─────────────────────────────────────────────────────────────────────────


class TestParseSections:
    def test_basic_multi_section_parse(self, bp):
        stdout = "===alive===\nALIVE\n===uname===\nLinux foo 6.0\n"
        sections = bp._parse_sections(stdout)
        assert sections["alive"] == "ALIVE"
        assert sections["uname"] == "Linux foo 6.0"

    def test_empty_section_parses_to_empty_string(self, bp):
        stdout = "===dsp_skel===\n===fastrpc===\nnone\n"
        sections = bp._parse_sections(stdout)
        assert sections["dsp_skel"] == ""
        assert sections["fastrpc"] == "none"

    def test_multiline_section_preserved(self, bp):
        stdout = "===soc0===\nQCS9075\n676\n===mem===\nMem: 100 200\n"
        sections = bp._parse_sections(stdout)
        assert sections["soc0"] == "QCS9075\n676"

    def test_trailing_newline_regression_guard(self, bp):
        """Regression guard for a real bug: `tr '\\0' ' '` in the devicetree
        probe left no trailing newline, so the next `echo "===soc0==="`
        landed on the SAME output line and was silently absorbed into the
        devicetree section instead of starting its own. Fixed by adding an
        explicit trailing `echo` after the `tr` in the actual probe -- this
        test guards the PARSER's behavior on both the broken and fixed
        shapes so a future probe edit can't reintroduce this silently.
        See docs/debugging/SoC_Identity_DSP_Skel_False_Positive.md.
        """
        # Fixed shape: devicetree probe ends with its own newline before the
        # next section header starts on its own line.
        fixed_stdout = "===devicetree===\nfoo bar \n===soc0===\nQCS9075\n676\n"
        sections = bp._parse_sections(fixed_stdout)
        assert sections["soc0"] == "QCS9075\n676"
        assert "soc0" not in sections["devicetree"]

        # Broken shape (what the bug produced): no trailing newline, so
        # "===soc0===" glues onto the devicetree line instead of starting a
        # new section -- this demonstrates WHY the probe-side fix mattered,
        # the parser itself cannot recover from this on its own.
        broken_stdout = "===devicetree===\nfoo bar ===soc0===\nQCS9075\n676\n"
        sections = bp._parse_sections(broken_stdout)
        assert "soc0" not in sections  # proves the parser can't compensate -- the probe fix is required

    def test_no_section_markers_returns_empty(self, bp):
        assert bp._parse_sections("just some text\nwith no markers\n") == {}


# ─────────────────────────────────────────────────────────────────────────
# BoardProfile.is_confirmed()
# ─────────────────────────────────────────────────────────────────────────


class TestBoardProfileIsConfirmed:
    def test_confirmed_field_reports_true(self, bp):
        p = bp.BOARD_PROFILES["iq-9075"]
        assert p.is_confirmed("soc") is True

    def test_unconfirmed_field_reports_false(self, bp):
        p = bp.BOARD_PROFILES["rb5"]
        assert p.is_confirmed("ram_mb") is False

    def test_unknown_field_name_reports_false(self, bp):
        p = bp.BOARD_PROFILES["iq-9075"]
        assert p.is_confirmed("not_a_real_field") is False


# ─────────────────────────────────────────────────────────────────────────
# _build_detect_probe() -- probe shell-script assembly
# ─────────────────────────────────────────────────────────────────────────


class TestBuildDetectProbe:
    def test_probe_embeds_profile_specific_globs(self, bp):
        profile = bp.BOARD_PROFILES["iq-9075"]
        probe = bp._build_detect_probe(profile)
        assert profile.qnn_bin_glob in probe
        assert profile.snpe_bin_glob in probe

    def test_probe_includes_soc0_and_qcom_share_sections(self, bp):
        probe = bp._build_detect_probe(bp.BOARD_PROFILES["rb5"])
        assert "===soc0===" in probe
        assert "===dsp_skel_qcom_share===" in probe

    def test_probe_has_no_hardcoded_head_cap_below_200(self, bp):
        """Regression guard: head -10 and head -30 were both proven, live,
        to truncate before reaching the real match on a 59-entry multi-SoC
        skel list. The cap must stay generous (currently 200) -- this test
        doesn't re-derive the right number, it just prevents a future edit
        from silently reintroducing a too-small cap on this specific find.
        """
        probe = bp._build_detect_probe(bp.BOARD_PROFILES["iq-9075"])
        for line in probe.splitlines():
            if "dsp_skel_qcom_share" in line and "find /usr/share/qcom" in line:
                assert "head -10" not in line
                assert "head -30" not in line

    def test_python_path_extra_prepended_when_set(self, bp):
        profile = bp.BOARD_PROFILES["iq-9075"]  # has python_path_extra set
        probe = bp._build_detect_probe(profile)
        assert f"PYTHONPATH={profile.python_path_extra}" in probe

    def test_no_pythonpath_prefix_when_unset(self, bp):
        profile = bp.BOARD_PROFILES["rb5"]  # python_path_extra defaults to ""
        probe = bp._build_detect_probe(profile)
        assert "PYTHONPATH=" not in probe


# ─────────────────────────────────────────────────────────────────────────
# _detect_profiling_strategy() -- distinguishes "onnxruntime missing" from
# "device unreachable" instead of conflating both into a silent CLI fallback
# (docs/debugging/7. CPU_Profiling_Revalidation_MobileNetV2_IQ9075.md §6.3)
# ─────────────────────────────────────────────────────────────────────────


class TestDetectProfilingStrategy:
    def test_ok_probe_with_ok_stdout_is_python_strategy(self, bp):
        from quad_mcp_client.local.board.ssh import CommandResult

        probe = CommandResult(returncode=0, stdout="OK\n", stderr="", elapsed_ms=10.0)
        strategy, error = bp._detect_profiling_strategy(probe)
        assert strategy == "python"
        assert error is None

    def test_ok_probe_with_missing_stdout_is_cli_strategy(self, bp):
        from quad_mcp_client.local.board.ssh import CommandResult

        probe = CommandResult(returncode=0, stdout="MISSING\n", stderr="", elapsed_ms=10.0)
        strategy, error = bp._detect_profiling_strategy(probe)
        assert strategy == "cli"
        assert error is None

    def test_failed_probe_is_ambiguous_not_cli(self, bp):
        """Regression guard for the exact bug in
        docs/debugging/7. CPU_Profiling_Revalidation_MobileNetV2_IQ9075.md §6.3:
        a transport-level failure (device offline) must NOT silently resolve
        to the CLI strategy -- it previously did, producing a plausible-looking
        but misleading ".onnx needs conversion" result.
        """
        from quad_mcp_client.local.board.ssh import CommandResult

        probe = CommandResult(returncode=255, stdout="", stderr="ssh: connect timed out", elapsed_ms=5000.0)
        strategy, error = bp._detect_profiling_strategy(probe)
        assert strategy is None
        assert error is not None
        assert "connect timed out" in error


# ─────────────────────────────────────────────────────────────────────────
# resolve_target() -- transport dispatch (ssh vs adb), no live connection
# ─────────────────────────────────────────────────────────────────────────


class TestResolveTarget:
    def test_ssh_transport_builds_ssh_target(self, bp):
        target = bp.resolve_target("10.0.0.5", "root", 22, None, "ssh")
        assert target.transport == "ssh"
        assert target.ssh.host == "10.0.0.5"

    def test_unknown_transport_raises(self, bp):
        with pytest.raises(ValueError):
            bp.resolve_target("host", "root", 22, None, "carrier-pigeon")

    def test_adb_transport_missing_binary_raises_actionable_error(self, bp, monkeypatch):
        monkeypatch.setattr(bp, "_find_adb", lambda: None)
        with pytest.raises(RuntimeError, match="adb not found"):
            bp.resolve_target("some-serial", "root", 22, None, "adb")

    def test_adb_auto_with_zero_devices_raises(self, bp, monkeypatch):
        monkeypatch.setattr(bp, "_find_adb", lambda: "/fake/adb")
        monkeypatch.setattr(bp, "_adb_devices", lambda exe: [])
        with pytest.raises(RuntimeError, match="found 0"):
            bp.resolve_target("auto", "root", 22, None, "adb")

    def test_adb_auto_with_multiple_devices_raises(self, bp, monkeypatch):
        monkeypatch.setattr(bp, "_find_adb", lambda: "/fake/adb")
        monkeypatch.setattr(bp, "_adb_devices", lambda exe: ["serial1", "serial2"])
        with pytest.raises(RuntimeError, match="found 2"):
            bp.resolve_target("auto", "root", 22, None, "adb")

    def test_adb_auto_with_exactly_one_device_resolves(self, bp, monkeypatch):
        monkeypatch.setattr(bp, "_find_adb", lambda: "/fake/adb")
        monkeypatch.setattr(bp, "_adb_devices", lambda exe: ["only-serial"])
        target = bp.resolve_target("auto", "root", 22, None, "adb")
        assert target.adb_serial == "only-serial"

    def test_adb_explicit_serial_bypasses_auto_selection(self, bp, monkeypatch):
        monkeypatch.setattr(bp, "_find_adb", lambda: "/fake/adb")
        target = bp.resolve_target("explicit-serial", "root", 22, None, "adb")
        assert target.adb_serial == "explicit-serial"
