#!/usr/bin/env python3
"""Tiny tool-using LLM agent for the Qualcomm Academy curriculum.

Design goal: write the agent ONCE and run it unchanged on a Snapdragon X Elite
host PC first, then on the IQ8 edge device so forth. The agent never loads a model
itself -- it speaks HTTP to an OpenAI-compatible server
(`/v1/chat/completions`). That server can be `llama.cpp` (CPU) or the
`genie_server.py` shim (X Elite NPU). The only thing that changes between
hosts is `--base-url`; the model and the agent code stay identical.

Portability rule: the default model is the effective-4B Gemma 4
(`gemma-4-E4B-it-Q4_K_M.gguf`), which is the proven-safe fit for the IQ8's
~11 GiB RAM. If it runs here, it runs on IQ8.

Small edge models are unreliable at native OpenAI function-calling, so this
agent uses a ReAct-style JSON-action loop instead: the model replies with a
single JSON object -- either {"tool": ..., "args": {...}} or
{"answer": "..."} -- which we parse and act on. That is far more robust on a
4B model than tool/function-calling and needs no special server flags.

Structure (see the section banners below):
  Tools        -- plain functions + a Tool registry describing each one.
  Prompt       -- system prompt generated FROM the registry.
  Model I/O    -- ModelClient (HTTP + retry) and the lenient JSON parser.
  Action       -- Action dataclass + parse_action: the seam where a capable
                  backend could swap JSON-ReAct for native tool-calling.
  Agent loop   -- run_agent: THINK -> ACT -> OBSERVE -> RESPOND.

Stdlib only (urllib/json/argparse/dataclasses) -- matches the curriculum's
AGENTS.md.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import platform
import re
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
# Each tool is a plain function taking a dict of args and returning a string.
# Keep them small, safe, and side-effect-light -- they run on an edge device.

def tool_calculator(args: dict[str, Any]) -> str:
    """Evaluate a basic arithmetic expression (digits and + - * / ^ . ( ) only).

    `^` is accepted as the power operator (a small model's natural notation for
    "2^10") and rewritten to Python's `**` before evaluation.

    Exponents are capped: without a bound, `9^9^9` would build a ~350M-digit
    integer and hang/OOM the process -- a real DoS on an 11 GiB IQ8 reachable
    straight from model output. We refuse any exponent above _MAX_EXPONENT.
    """
    expr = str(args.get("expression", "")).strip()
    if not expr:
        return "error: missing 'expression'"
    if not re.fullmatch(r"[0-9+\-*/^().\s]+", expr):
        return "error: expression may only contain numbers and + - * / ^ ( ) ."
    # Model-friendly: treat `^` as exponentiation. `**` already passes the regex
    # above (it's just two `*`), so both `2^10` and `2**10` now work.
    expr = expr.replace("^", "**")
    # Guard against runaway powers. Two vectors: (a) a single huge exponent like
    # 2**999999, and (b) chaining like 9**9**9 (= 9**(9**9)) where each literal
    # is tiny but the tower explodes. Refuse chains outright, and cap any single
    # exponent literal.
    if expr.count("**") > 1:
        return "error: chained exponentiation (a**b**c) is not allowed"
    for exp_literal in re.findall(r"\*\*\s*(\d+)", expr):
        if int(exp_literal) > _MAX_EXPONENT:
            return f"error: exponent {exp_literal} too large (max {_MAX_EXPONENT})"
    try:
        # No names/builtins exposed -- the regex above already restricts input.
        result = eval(expr, {"__builtins__": {}}, {})  # noqa: S307 (input is whitelisted)
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"
    return str(result)


# Cap for the calculator's exponent operand -- keeps `2^10` working while
# refusing `9^9^9`-style expressions that would exhaust CPU/RAM on the edge.
_MAX_EXPONENT = 1000


def tool_now(_args: dict[str, Any]) -> str:
    """Return the current local date and time (ISO 8601, seconds precision)."""
    return _dt.datetime.now().isoformat(timespec="seconds")


def tool_read_file(args: dict[str, Any]) -> str:
    """Read a small text file. Capped to keep tokens (and edge RAM) sane."""
    path = str(args.get("path", "")).strip()
    if not path:
        return "error: missing 'path'"
    p = Path(path).expanduser()
    if not p.is_file():
        return f"error: not a file: {p}"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"
    limit = 2000
    if len(text) > limit:
        text = text[:limit] + f"\n...[truncated, {len(text)} chars total]"
    return text


def tool_list_dir(args: dict[str, Any]) -> str:
    """List a directory's entries (name, type, size). Read-only, edge-safe.

    Complements read_file: the agent can explore a directory before deciding
    what to read. Output is capped so a huge directory can't blow the context.
    """
    path = str(args.get("path", "")).strip() or "."
    p = Path(path).expanduser()
    if not p.is_dir():
        return f"error: not a directory: {p}"
    try:
        entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    except OSError as exc:
        return f"error: {exc}"
    limit = 200
    lines = []
    for e in entries[:limit]:
        try:
            if e.is_dir():
                lines.append(f"{e.name}/  <dir>")
            else:
                lines.append(f"{e.name}  {e.stat().st_size} bytes")
        except OSError:
            lines.append(f"{e.name}  <unreadable>")
    if len(entries) > limit:
        lines.append(f"...[truncated, {len(entries)} entries total]")
    return "\n".join(lines) if lines else "(empty directory)"


def tool_stat_file(args: dict[str, Any]) -> str:
    """Return metadata for a file or directory (size, modified time, type).

    Lets the agent check a path without reading its contents -- cheap on tokens
    and edge RAM.
    """
    path = str(args.get("path", "")).strip()
    if not path:
        return "error: missing 'path'"
    p = Path(path).expanduser()
    try:
        st = p.stat()
    except OSError as exc:
        return f"error: {exc}"
    kind = "directory" if p.is_dir() else "file" if p.is_file() else "other"
    mtime = _dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
    return f"path: {p}\ntype: {kind}\nsize: {st.st_size} bytes\nmodified: {mtime}"


def tool_sys_info(_args: dict[str, Any]) -> str:
    """Return a portable device profile (OS, arch, CPU count, Python, hostname).

    Uses the stdlib `platform`/`os` modules, so it works IDENTICALLY on the
    Windows X Elite host and the Linux IQ8 -- unlike shelling out to lscpu/free,
    which don't exist on Windows. One call replaces several run_shell steps.
    """
    uname = platform.uname()
    return (
        f"system: {uname.system}\n"
        f"hostname: {uname.node}\n"
        f"release: {uname.release}\n"
        f"machine (arch): {uname.machine}\n"
        f"processor: {uname.processor or 'unknown'}\n"
        f"cpu_count: {os.cpu_count()}\n"
        f"python: {platform.python_version()} ({platform.architecture()[0]})"
    )


# Read-only commands the agent is allowed to run. The FIRST word of the command
# must be one of these; anything else is refused. This is what makes run_shell
# safe to expose on an edge device -- the model can inspect the system but not
# change it. Add to this set deliberately.
SHELL_ALLOWLIST = {
    "ls", "cat", "head", "tail", "wc", "grep", "find", "echo", "pwd",
    "uname", "hostname", "whoami", "id", "uptime", "date",
    "free", "df", "du", "nproc", "lscpu", "lsblk", "ps", "env",
}


def tool_run_shell(args: dict[str, Any]) -> str:
    """Run a single read-only shell command from the allowlist.

    Refuses anything whose first word isn't allowlisted, and refuses shell
    metacharacters (; | & > < ` $) so a command can't be chained into something
    unlisted. Output is captured and truncated.
    """
    cmd = str(args.get("command", "")).strip()
    if not cmd:
        return "error: missing 'command'"
    if any(ch in cmd for ch in ";|&><`$\n"):
        return "error: shell metacharacters (; | & > < ` $) are not allowed"
    try:
        parts = shlex.split(cmd)
    except ValueError as exc:
        return f"error: could not parse command: {exc}"
    if not parts:
        return "error: empty command"
    prog = parts[0]
    if prog not in SHELL_ALLOWLIST:
        return (f"error: '{prog}' is not allowed. Allowed commands: "
                f"{', '.join(sorted(SHELL_ALLOWLIST))}")
    try:
        proc = subprocess.run(  # noqa: S603 (prog is allowlisted, no shell)
            parts, capture_output=True, text=True, timeout=15,
        )
    except subprocess.TimeoutExpired:
        return "error: command timed out (15s)"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"
    out = (proc.stdout + proc.stderr).strip()
    limit = 2000
    if len(out) > limit:
        out = out[:limit] + f"\n...[truncated, {len(out)} chars total]"
    return out or f"(no output, exit code {proc.returncode})"


# --------------------------------------------------------------------------- #
# Coding tools (OPT-IN, off by default) -- write files + run commands.
# --------------------------------------------------------------------------- #
# These break the read-only default on purpose: a coding agent must edit files
# and run builds/tests. They're only registered with --coding / --allow-exec.
# The safety model mirrors run_shell's allowlist: writes are sandboxed to a
# workspace dir, and command execution is gated behind an interactive y/N prompt.

# Workspace root that write tools are confined to. Set by main() when --coding
# is on; None means coding tools are unavailable.
_WORKSPACE: Path | None = None
_WRITE_LIMIT = 64 * 1024  # cap written content (edge RAM / runaway output)


def _resolve_in_workspace(path: str) -> Path | str:
    """Resolve `path` under the workspace, or return an 'error:' string.

    The security core of the coding tools: refuses absolute paths, `..`
    traversal, and anything whose resolved real path escapes the workspace root.
    """
    if _WORKSPACE is None:
        return "error: coding tools are disabled (run with --coding)"
    p = Path(path)
    if p.is_absolute():
        return f"error: absolute paths are not allowed; give a path under the workspace ({_WORKSPACE})"
    target = (_WORKSPACE / p).resolve()
    root = _WORKSPACE.resolve()
    if target != root and root not in target.parents:
        return f"error: path escapes the workspace ({_WORKSPACE}); '..' and outside paths are refused"
    return target


def tool_write_file(args: dict[str, Any]) -> str:
    """Create or overwrite a text file INSIDE the workspace. args: path, content."""
    path = str(args.get("path", "")).strip()
    if not path:
        return "error: missing 'path'"
    content = str(args.get("content", ""))
    if len(content) > _WRITE_LIMIT:
        return f"error: content too large ({len(content)} chars, max {_WRITE_LIMIT})"
    target = _resolve_in_workspace(path)
    if isinstance(target, str):
        return target  # error message
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"error: {exc}"
    rel = target.relative_to(_WORKSPACE.resolve())
    return f"wrote {len(content)} chars to {rel}"


def tool_apply_patch(args: dict[str, Any]) -> str:
    """Replace an exact snippet in a workspace file. args: path, search, replace.

    `search` must match EXACTLY ONCE -- 0 matches (not found) and >1 (ambiguous)
    are both refused. This single-match rule is what makes small-model edits safe:
    no guessing which occurrence, no silent whole-file clobber.
    """
    path = str(args.get("path", "")).strip()
    if not path:
        return "error: missing 'path'"
    search = str(args.get("search", ""))
    replace = str(args.get("replace", ""))
    if not search:
        return "error: missing 'search' (the exact text to replace)"
    target = _resolve_in_workspace(path)
    if isinstance(target, str):
        return target
    if not target.is_file():
        return f"error: not a file: {path} (use write_file to create it)"
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"error: {exc}"
    count = text.count(search)
    if count == 0:
        return "error: 'search' text not found in the file"
    if count > 1:
        return f"error: 'search' matches {count} times (must be unique); include more surrounding context"
    updated = text.replace(search, replace)
    if len(updated) > _WRITE_LIMIT:
        return f"error: result too large ({len(updated)} chars, max {_WRITE_LIMIT})"
    try:
        target.write_text(updated, encoding="utf-8")
    except OSError as exc:
        return f"error: {exc}"
    rel = target.relative_to(_WORKSPACE.resolve())
    return f"patched {rel}: -{len(search)} chars / +{len(replace)} chars"


def tool_run_command(args: dict[str, Any]) -> str:
    """Run a shell command in the workspace AFTER interactive y/N approval.

    Unlike run_shell there is NO allowlist -- the safety gate is that a human
    must confirm each command. Only registered when --allow-exec is passed.
    """
    cmd = str(args.get("command", "")).strip()
    if not cmd:
        return "error: missing 'command'"
    cwd = str(_WORKSPACE) if _WORKSPACE is not None else None
    # Approval gate -- the whole point of this tool.
    print(f"\n\033[35m[approve] run in {cwd or '.'}:\033[0m {cmd}")
    try:
        reply = input("Run this command? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        reply = ""
    if reply not in ("y", "yes"):
        return "error: command declined by user"
    try:
        parts = shlex.split(cmd)
    except ValueError as exc:
        return f"error: could not parse command: {exc}"
    if not parts:
        return "error: empty command"
    try:
        proc = subprocess.run(  # noqa: S603 (human-approved, no shell)
            parts, capture_output=True, text=True, timeout=120, cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return "error: command timed out (120s)"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"
    out = (proc.stdout + proc.stderr).strip()
    limit = 2000
    if len(out) > limit:
        out = out[:limit] + f"\n...[truncated, {len(out)} chars total]"
    return f"[exit {proc.returncode}] " + (out or "(no output)")


# --------------------------------------------------------------------------- #
# Tool registry
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Tool:
    """A callable tool plus the metadata used to describe it to the model.

    `args` maps each accepted arg name to a one-line description; it drives both
    the generated system prompt and the light arg-shape check in dispatch_tool.
    `example` is a ready-to-copy args object shown in the (non-compact) prompt --
    small models imitate examples far more reliably than they read schemas.
    """
    name: str
    summary: str
    fn: Callable[[dict[str, Any]], str]
    args: dict[str, str] = field(default_factory=dict)
    example: dict[str, Any] = field(default_factory=dict)

    def signature(self) -> str:
        """`name(arg1, arg2)` -- compact one-liner for the prompt/tool list."""
        return f"{self.name}({', '.join(self.args)})"

    def describe(self) -> str:
        """Full line for the verbose prompt: summary + a concrete example."""
        ex = json.dumps(self.example) if self.example else "{}"
        return f"{self.summary} args: {ex}"


def _build_registry(*, coding: bool = False, allow_exec: bool = False) -> dict[str, Tool]:
    tools = [
        Tool("calculator", "evaluate arithmetic, incl. ^ for powers.",
             tool_calculator, {"expression": "arithmetic expression"},
             {"expression": "2^10"}),
        Tool("now", "current local date/time.", tool_now),
        Tool("sys_info", "portable device profile: OS, arch, CPU count, Python, hostname.",
             tool_sys_info),
        Tool("read_file", "read a small text file (truncated).",
             tool_read_file, {"path": "file path"}, {"path": "/etc/hostname"}),
        Tool("list_dir", "list a directory (name, type, size).",
             tool_list_dir, {"path": "directory path"}, {"path": "."}),
        Tool("stat_file", "metadata for a path (size, mtime, type).",
             tool_stat_file, {"path": "file path"}, {"path": "/etc/hostname"}),
        Tool("run_shell",
             "run ONE read-only shell command (e.g. "
             + ", ".join(sorted(SHELL_ALLOWLIST)[:5]) + ", etc).",
             tool_run_shell, {"command": "one allowlisted command"}, {"command": "free -h"}),
    ]
    # Opt-in coding tools (write files in the workspace). See --coding.
    if coding:
        tools += [
            Tool("write_file", "create/overwrite a text file in the workspace.",
                 tool_write_file, {"path": "workspace-relative path", "content": "file text"},
                 {"path": "hello.py", "content": "print('hi')"}),
            Tool("apply_patch",
                 "replace an EXACT unique snippet in a workspace file.",
                 tool_apply_patch,
                 {"path": "workspace file", "search": "exact text to find (unique)",
                  "replace": "new text"},
                 {"path": "hello.py", "search": "hi", "replace": "hello"}),
        ]
    # Opt-in command execution (approval-gated). See --allow-exec.
    if allow_exec:
        tools.append(
            Tool("run_command", "run a shell command in the workspace (asks y/N first).",
                 tool_run_command, {"command": "any command"}, {"command": "python hello.py"}))
    return {t.name: t for t in tools}


# Registry: name -> Tool. Rebuilt in main() once --coding/--allow-exec are known.
# Add a tool by writing a `tool_*(args) -> str` function and appending a Tool(...)
# entry in _build_registry above.
TOOLS: dict[str, Tool] = _build_registry()


# --------------------------------------------------------------------------- #
# Prompt (generated from the registry above)
# --------------------------------------------------------------------------- #
def build_system_prompt(*, compact: bool = False) -> str:
    if compact:
        # Just signatures -- keeps the prompt tiny for small-context servers.
        tool_lines = "\n".join(f"- {t.signature()}" for t in TOOLS.values())
        return (
            "You are an autonomous agent. Reply with EXACTLY ONE JSON object.\n"
            "Either:\n"
            '  {"thought":"...","tool":"<name>","args":{...}}\n'
            "or:\n"
            '  {"thought":"...","answer":"..."}\n'
            "Rules: one tool per turn; no markdown fences.\n"
            "Tools:\n" + tool_lines
        )

    tool_lines = "\n".join(f"- {name}: {t.describe()}" for name, t in TOOLS.items())
    coding_note = ""
    if "write_file" in TOOLS:
        coding_note = (
            "- Coding: read a file before editing it. Use apply_patch for small\n"
            "  edits (give an EXACT, unique search snippet) and write_file for new\n"
            "  files. Paths are relative to the workspace.\n")
    return (
        "You are an autonomous agent running on an edge device. You solve a task\n"
        "by reasoning, then taking ONE action at a time, observing the result,\n"
        "and continuing until the task is fully done.\n\n"
        "On every turn reply with EXACTLY ONE JSON object and nothing else.\n"
        "To take a tool action:\n"
        '  {"thought": "<why this step>", "tool": "<name>", "args": { ... }}\n'
        "To finish with the final answer:\n"
        '  {"thought": "<why you are done>", "answer": "<final answer for the user>"}\n\n'
        "Rules:\n"
        "- Always include a short \"thought\" explaining your reasoning for this step.\n"
        "- Take only ONE tool action per turn; you will see its result next turn.\n"
        "- Break multi-part tasks into multiple steps. Gather what you need with\n"
        "  tools BEFORE answering. Do not guess values a tool can give you.\n"
        "- Only answer once you actually have everything the task requires.\n"
        "- Do not wrap the JSON in markdown fences.\n"
        + coding_note + "\n"
        "Available tools:\n" + tool_lines
    )


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
@dataclass
class AgentConfig:
    """Everything a run needs, so functions take one object not eight kwargs."""
    base_url: str = "http://127.0.0.1:8080"
    model: str = "gemma-4-E4B-it-Q4_K_M.gguf"
    max_steps: int = 8
    max_tokens: int = 256
    temperature: float = 0.2
    timeout: float = 120.0
    retries: int = 2
    # Context cap: keep system + first user + this many trailing messages, so a
    # long multi-step run doesn't overflow a small-context server (the NPU Genie
    # bundle is only 2048 tokens). 0 disables trimming.
    max_history: int = 12
    verbose: bool = False
    # Coding mode (opt-in): file-write tools sandboxed to `workspace`, and
    # (with allow_exec) an approval-gated run_command. Off = read-only default.
    coding: bool = False
    allow_exec: bool = False
    workspace: str | None = None


# --------------------------------------------------------------------------- #
# Model I/O (OpenAI-compatible /v1/chat/completions) + lenient JSON parse
# --------------------------------------------------------------------------- #
@dataclass
class Usage:
    """Running token/step tally across an agent run.

    Servers that report OpenAI-style `usage` (llama.cpp does) fill this exactly;
    genie_server.py does not, so we fall back to a chars/4 estimate and flag it.
    """
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated: bool = False  # True if ANY value was estimated, not server-reported

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add(self, prompt: int, completion: int, *, estimated: bool) -> None:
        self.calls += 1
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.estimated = self.estimated or estimated

    def summary(self) -> str:
        est = " (estimated)" if self.estimated else ""
        return (f"{self.calls} model calls, ~{self.prompt_tokens} prompt "
                f"+ ~{self.completion_tokens} completion = {self.total_tokens} tokens{est}")


def _estimate_tokens(text: str) -> int:
    """Rough token count when the server omits usage. ~4 chars/token."""
    return max(1, len(text) // 4)


class ModelClient:
    """Thin HTTP client for an OpenAI-compatible chat server, with retry.

    Wrapping the request in a small object (rather than a bare function) is the
    seam that lets a different backend -- e.g. one that uses native OpenAI
    tool-calling instead of our JSON-ReAct convention -- be dropped in without
    touching the agent loop: it just needs a `.complete(messages) -> str`.

    Token usage accrues on `self.usage` as a side effect of each call, so the
    seam contract stays `complete(messages) -> str`.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.url = config.base_url.rstrip("/") + "/v1/chat/completions"
        self.usage = Usage()

    def complete(self, messages: list[dict[str, str]]) -> str:
        cfg = self.config
        payload = {
            "model": cfg.model,
            "messages": messages,
            "max_tokens": cfg.max_tokens,
            "temperature": cfg.temperature,
        }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # A loaded NPU (or a cold llama.cpp) can drop a request with a transient
        # timeout/reset. Retry a couple of times with a short backoff before
        # giving up -- one flaky request shouldn't kill the whole agent run.
        last_exc: Exception | None = None
        for attempt in range(cfg.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=cfg.timeout) as resp:
                    obj = json.load(resp)
                content = (obj["choices"][0]["message"].get("content") or "").strip()
                self._record_usage(obj, messages, content)
                return content
            except urllib.error.URLError as exc:
                last_exc = exc
                if attempt < cfg.retries:
                    time.sleep(1.5 * (attempt + 1))  # 1.5s, then 3.0s
        raise SystemExit(
            f"Could not reach model server at {self.url} after "
            f"{cfg.retries + 1} attempts: {last_exc}\n"
            "Is the server running? (see README/usage.md for how to start CPU or NPU server)"
        )

    def _record_usage(self, obj: dict[str, Any], messages: list[dict[str, str]],
                       content: str) -> None:
        """Add this call's tokens to self.usage (server-reported or estimated)."""
        usage = obj.get("usage") or {}
        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
        if prompt is not None and completion is not None:
            self.usage.add(int(prompt), int(completion), estimated=False)
        else:
            # genie_server.py omits usage -- estimate from the text we sent/got.
            sent = "".join(m.get("content", "") for m in messages)
            self.usage.add(_estimate_tokens(sent),
                           _estimate_tokens(content), estimated=True)


def _first_json_object(text: str) -> str | None:
    """Return the first balanced {...} substring (quote/escape aware), else None."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_json(text: str) -> dict[str, Any] | None:
    """Leniently pull the first JSON object out of a model reply.

    Small quantized models (especially on the NPU) are sloppy JSON emitters, so
    we try a series of increasingly forgiving repairs and return the first that
    parses to a dict. The repairs, in order:

      0. Strip ```json ... ``` fences the model added despite instructions.
      1. Parse the whole reply as-is (strict=False so literal newlines/tabs
         inside string values are tolerated -- multi-line "thought" strings).
      2. Parse just the first balanced {...} substring (ignores prose around it).
      3. For each of the above, retry with two repairs applied (order matters):
         a. Collapse stray `\\"` to `"` -- some models escape quotes BETWEEN
            fields, e.g. {"thought":"...",\\"tool\\":\\"list_dir\\"}.
         b. Collapse a RUN of quotes just before a closing `}`/`]`/`,` down to
            one -- the NPU model sometimes ends a value with extra quotes before
            the brace (e.g. `...done.` followed by three quotes then `}`).
         Both run only AFTER the clean parse fails, so legitimately-escaped
         quotes inside a value are never harmed.
      4. Last resort: close a TRUNCATED object -- when a long answer is cut off
         by max_tokens mid-string (e.g. a big file listing), close the dangling
         string and balance open braces/brackets so we recover a partial answer
         instead of dumping the raw JSON at the user.

    Returns None if nothing parses -- the caller then treats the reply as a
    plain-text answer.
    """
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()

    candidates = [text]
    obj_str = _first_json_object(text)
    if obj_str and obj_str != text:
        candidates.append(obj_str)

    for cand in candidates:
        for repaired in (cand, _repair_json(cand), _close_truncated_json(cand)):
            try:
                parsed = json.loads(repaired, strict=False)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return None


def _close_truncated_json(text: str) -> str:
    """Best-effort close of a JSON object cut off mid-value by max_tokens.

    Walks the text tracking string/escape state and brace/bracket depth, then
    appends whatever is needed to terminate: a closing quote if we ended inside
    a string, then the right number of `]`/`}`. Returns text unchanged if it
    isn't a truncated object (nothing open to close).
    """
    if not text.lstrip().startswith("{"):
        return text
    in_str = False
    esc = False
    stack: list[str] = []
    for c in text:
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c in "{[":
            stack.append(c)
        elif c == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif c == "]" and stack and stack[-1] == "[":
            stack.pop()
    if not stack and not in_str:
        return text  # already balanced -- not a truncation we can help with
    repaired = text
    if in_str:
        repaired += '"'
    for opener in reversed(stack):
        repaired += "}" if opener == "{" else "]"
    return repaired


def _repair_json(text: str) -> str:
    r"""Apply forgiving fixes for common small-model JSON glitches.

    - `\"` -> `"`       : quotes escaped between fields.
    - a run of 2+ quotes right before a closing }/]/, is collapsed to a single
      quote (the NPU model's extra-trailing-quote bug).
    - a key that lost its OPENING quote after `{`/`,` gets it back, e.g.
      `{"thought":"..",tool":"read_file"}` -> `..,"tool":"read_file"` (the 4B
      NPU model's dropped-open-quote bug -- caused tool calls to fall back to
      raw text). Only fires when the key already has its closing `"` + `:`, so
      correctly-quoted keys (`,"tool":`) are never touched.
    """
    text = text.replace('\\"', '"')
    text = re.sub(r'"{2,}(\s*[}\],])', r'"\1', text)
    text = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*"\s*:)', r'\1"\2', text)
    return text


# --------------------------------------------------------------------------- #
# Action -- the parsed intent for one turn (the ReAct <-> native-tools seam)
# --------------------------------------------------------------------------- #
@dataclass
class Action:
    """One turn's decision: either finish (answer) or call a tool.

    parse_action() turns a raw model reply into this. A backend that used native
    OpenAI tool-calling would build the same Action from the tool_calls field
    instead -- the agent loop only ever sees Action, never the wire format.
    """
    thought: str = ""
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    answer: str | None = None
    raw: str = ""

    @property
    def is_answer(self) -> bool:
        return self.answer is not None


# Aliases small models invent instead of the intended {"answer": ...} form.
_FINISH_TOOLS = ("finish", "final", "done", "answer")
_ANSWER_KEYS = ("answer", "text", "result", "output", "response", "summary")
# Key names small models reach for instead of our "tool"/"args" -- LangChain
# ReAct ("action"/"action_input") and OpenAI function-calling ("name"/"arguments")
# are all over their training data. Our own keys are listed first so they win.
_TOOL_KEYS = ("tool", "action", "tool_name", "name", "function")
_ARGS_KEYS = ("args", "action_input", "tool_input", "arguments", "parameters", "params", "input")
# Sentinels a model uses to mean "no tool needed" (it wants to just answer).
_NO_TOOL = ("", "none", "<none>", "null", "no_tool", "no-tool", "n/a")


def parse_action(reply: str) -> Action:
    """Parse a raw model reply into an Action (JSON-ReAct convention).

    Handles the shapes small models drift into:
      {"answer": "..."}                              -- intended finish
      {"tool": "finish", "args": {"answer": "..."}}  -- invented finish tool
      {"thought": ..., "tool": ..., "args": {...}}   -- intended tool call
      {"thought": ..., "result": "..."}              -- answer under a synonym key
      {"thought": "<the answer>", "tool": "<none>"}  -- no-tool sentinel: the
                                                        answer is in the thought
      <non-JSON prose>                               -- treated as the answer
    """
    obj = extract_json(reply)
    if obj is None:
        # Not JSON at all -- treat the whole reply as the final answer.
        return Action(answer=reply, raw=reply)

    thought = str(obj.get("thought", "")).strip()

    # Direct answer.
    if "answer" in obj:
        return Action(thought=thought, answer=str(obj["answer"]), raw=reply)

    tool = None
    for key in _TOOL_KEYS:
        if obj.get(key) is not None:
            tool = obj[key]
            break
    args = None
    for key in _ARGS_KEYS:
        if key in obj:
            args = obj[key]
            break
    # `args` may arrive as a dict (intended), a JSON string ('{"path":"x"}'), or a
    # bare scalar ("README.md" under action_input). Coerce to a dict either way;
    # a scalar is stashed under the named tool's first declared arg below.
    scalar_arg = None
    if isinstance(args, str):
        try:
            parsed_args = json.loads(args)
            args = parsed_args if isinstance(parsed_args, dict) else args
        except (json.JSONDecodeError, ValueError):
            pass
    if not isinstance(args, dict):
        scalar_arg = args if isinstance(args, (str, int, float)) and args != "" else None
        args = {}

    # Normalize a call-syntax tool name: models often emit "now()" or
    # "calculator(2^10)" instead of the bare "now". Strip a trailing (...) so it
    # matches the registry; if it held an argument and args is empty, keep it.
    if isinstance(tool, str):
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*$", tool)
        if m:
            tool = m.group(1)
            inner = m.group(2).strip()
            if inner and not args:
                # Best-effort: stash the raw inside-parens value under the tool's
                # first declared arg (e.g. calculator(2^10) -> {expression: 2^10}).
                spec = TOOLS.get(tool)
                if spec and spec.args:
                    args = {next(iter(spec.args)): inner.strip("'\"")}

    # A "finish"-style tool is really an answer.
    if tool in _FINISH_TOOLS:
        for key in _ANSWER_KEYS:
            if key in args:
                return Action(thought=thought, answer=str(args[key]), raw=reply)
        return Action(thought=thought, answer=str(args) if args else "", raw=reply)

    if tool in TOOLS:
        # A bare scalar arg (e.g. action_input:"README.md") -> the tool's first
        # declared arg, so {"action":"read_file","action_input":"README.md"} works.
        if scalar_arg is not None and not args:
            spec = TOOLS[tool]
            if spec.args:
                args = {next(iter(spec.args)): scalar_arg}
        return Action(thought=thought, tool=tool, args=args, raw=reply)

    # No known tool. Before giving up, small models often stash the final answer
    # under a synonym key (e.g. {"thought": ..., "result": "1024"}) with no
    # "tool"/"answer" at all -- accept that as the answer rather than looping.
    for key in _ANSWER_KEYS:
        if key in obj:
            return Action(thought=thought, answer=str(obj[key]), raw=reply)

    # A no-tool sentinel (tool is None / "" / "<none>" / "null" ...) means the
    # model wants to answer, not call a tool -- and it puts the answer in the
    # `thought`. Treat the thought as the answer instead of erroring and looping.
    # An unfilled template placeholder like "<name>" / "<tool>" (small models
    # echo the prompt's example verbatim) counts as a no-tool sentinel too.
    tool_norm = (tool or "").strip().lower()
    is_placeholder = tool_norm.startswith("<") and tool_norm.endswith(">")
    if (tool_norm in _NO_TOOL or is_placeholder) and thought:
        return Action(thought="", answer=thought, raw=reply)

    # Genuinely a (probably malformed) tool call -- let the loop report it.
    return Action(thought=thought, tool=tool, args=args, raw=reply)


# --------------------------------------------------------------------------- #
# Agent loop
# --------------------------------------------------------------------------- #
# ANSI colors for the -v trace: THINK dim, ACT cyan, OBSERVE yellow,
# RESPOND green, errors red.
_COLORS = {"THINK": "2", "ACT": "36", "OBSERVE": "33", "RESPOND": "32", "ERROR": "31"}


def _emit(step: int, label: str, text: str, *, preview: bool = False) -> None:
    """Print one colored trace line (with multi-line indent + optional preview)."""
    color = _COLORS.get(label, "0")
    if preview and len(text) > 300:
        text = text[:300] + " ...[more]"
    indent = "\n" + " " * (len(f"[step {step}] {label}: "))
    text = text.replace("\n", indent)
    print(f"\033[{color}m[step {step}] {label}: {text}\033[0m")


def _normalize_action(action: Action) -> Action:
    """Coerce common small-model tool-naming mistakes into real tool calls.

    Small models frequently set the tool to a SHELL COMMAND name (e.g. ls, cat,
    pwd) instead of the actual tool, `run_shell`. If the named "tool" is in the
    shell allowlist, rewrite it into run_shell with the command reassembled from
    the tool name + any args, so `{"tool":"ls"}` just works.
    """
    name = action.tool or ""
    if name in TOOLS or name not in SHELL_ALLOWLIST:
        return action
    # Rebuild a command line: tool name + any string arg values (e.g. a path).
    extras = " ".join(str(v) for v in action.args.values() if isinstance(v, (str, int, float)))
    command = f"{name} {extras}".strip()
    return Action(thought=action.thought, tool="run_shell",
                  args={"command": command}, raw=action.raw)


def dispatch_tool(action: Action, *, step: int, verbose: bool) -> str:
    """Run the tool named by `action` and return its observation string.

    Centralizes arg validation, unknown-tool handling, and the ACT/OBSERVE
    trace, so run_agent stays readable as just the ReAct control flow.
    """
    action = _normalize_action(action)
    tool = TOOLS.get(action.tool or "")
    if tool is None:
        if verbose:
            _emit(step, "ERROR", f"unknown tool: {action.tool!r}")
        return f"error: unknown tool '{action.tool}'. Available: {', '.join(TOOLS)}"

    args = action.args if isinstance(action.args, dict) else {}
    # Light arg-shape check: warn (don't block) on args the tool doesn't declare
    # -- the tool functions do their own required-arg validation.
    unknown = [k for k in args if k not in tool.args]
    if verbose:
        arg_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        _emit(step, "ACT", f"{tool.name}({arg_str})")
        if unknown:
            _emit(step, "ERROR", f"(note) ignoring unknown args: {', '.join(unknown)}")

    result = tool.fn(args)
    if verbose:
        _emit(step, "OBSERVE", result, preview=True)
    return result


def trim_history(messages: list[dict[str, str]], max_history: int) -> list[dict[str, str]]:
    """Cap context growth: keep system + first user turn + last `max_history`.

    Every step appends an assistant action and a tool observation, so on a
    small-context server (the 2048-token NPU bundle) a long run would overflow.
    We always preserve the system prompt and the original task, then keep only
    the most recent exchanges. `max_history <= 0` disables trimming.
    """
    if max_history <= 0 or len(messages) <= max_history + 2:
        return messages
    head = messages[:2]          # system + original user task
    tail = messages[-max_history:]
    return head + tail


def run_agent(user_msg: str, client: ModelClient, system_prompt: str,
              config: AgentConfig,
              history: list[dict[str, str]] | None = None) -> str:
    """Drive the THINK -> ACT -> OBSERVE loop until the model answers.

    `history` is the prior conversation as clean {user, assistant} turns (no
    system message, no intra-run tool scratchpad). When given, the model sees
    earlier turns so follow-ups like "run it" resolve -- without it, each call
    starts blank. The one-shot path passes nothing, so behavior is unchanged.
    """
    verbose = config.verbose
    # Reset per-run token/call tally so the [usage] line reports THIS prompt, not
    # the whole interactive session. `client.usage` lives for the session (one
    # ModelClient across many turns), so without this the per-run `step` count
    # gets printed next to a cumulative `calls`/token total -- e.g. "4 steps, 14
    # model calls" when 10 of those calls were earlier prompts.
    client.usage = Usage()

    def _finish(step: int, answer: str) -> str:
        if verbose:
            _emit(step, "RESPOND", answer, preview=True)
            print(f"\033[2m[usage] {step} steps, {client.usage.summary()}\033[0m")
        return answer

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_msg})
    # Repeat-call guard: small models sometimes call the SAME tool with the same
    # args over and over (the answer sits in their `thought` but they won't
    # stop). Track the last signature + observation so we can nudge once, then
    # break the loop by answering from that observation.
    last_call: tuple[str, str] | None = None
    last_observation = ""
    nudged = False
    for step in range(1, config.max_steps + 1):
        reply = client.complete(trim_history(messages, config.max_history))
        action = parse_action(reply)

        if verbose and action.thought:
            _emit(step, "THINK", action.thought)

        if action.is_answer:
            return _finish(step, action.answer or "")

        signature = f"{action.tool}:{json.dumps(action.args, sort_keys=True)}"
        if last_call is not None and signature == last_call:
            if not nudged:
                # First repeat: tell the model it already has this result.
                nudged = True
                if verbose:
                    _emit(step, "ERROR", f"(repeat) {action.tool} already run -- "
                          "nudging model to answer")
                messages.append({"role": "assistant", "content": action.raw})
                messages.append({
                    "role": "user",
                    "content": (f"You already called {action.tool} and got: "
                                f"{last_observation}\nDo NOT call it again. "
                                "Reply now with your final answer."),
                })
                continue
            # Second repeat: it's stuck. Answer from the observation we have.
            # (_finish emits the RESPOND line -- don't double it here.)
            return _finish(step, last_observation)

        # Tool action: run it, feed the observation back, and loop.
        observation = dispatch_tool(action, step=step, verbose=verbose)
        last_call, last_observation, nudged = signature, observation, False
        messages.append({"role": "assistant", "content": action.raw})
        messages.append({
            "role": "user",
            "content": f"Tool result for {action.tool}: {observation}",
        })

    return _finish(config.max_steps, "(stopped: reached max steps without a final answer)")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
PROFILES_FILE = Path(__file__).with_name("agent_profiles.json")


def load_profiles() -> dict[str, dict[str, Any]]:
    """Load named argument presets from agent_profiles.json (empty if missing)."""
    try:
        data = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data.get("profiles", {})


def _print_profiles(profiles: dict[str, dict[str, Any]]) -> None:
    if not profiles:
        print("(no profiles found in agent_profiles.json)")
        return
    print("Available profiles (select with --profile <name>):")
    for name, p in profiles.items():
        desc = p.get("description", "")
        print(f"  {name:8} {p.get('model', '?')} @ {p.get('base_url', '?')}"
              + (f"  -- {desc}" if desc else ""))


def _print_tools() -> None:
    print("Tools the agent can use:")
    for name, tool in TOOLS.items():
        print(f"  {tool.signature():28} {tool.summary}")


def resolve_config(args: argparse.Namespace,
                   profiles: dict[str, dict[str, Any]]) -> tuple[AgentConfig, bool]:
    """Layer settings: default < env < profile < explicit CLI flag.

    Returns (config, compact_prompt). argparse defaults are None sentinels, so a
    value is "explicit" only if the user actually passed it.
    """
    profile: dict[str, Any] = {}
    if args.profile:
        if args.profile not in profiles:
            raise SystemExit(
                f"error: unknown profile '{args.profile}'. "
                f"Known: {', '.join(profiles) or '(none)'}. See agent_profiles.json."
            )
        profile = profiles[args.profile]

    def pick(cli_val, profile_key, env_key, default):
        if cli_val is not None:              # explicit CLI flag wins
            return cli_val
        if profile_key in profile:           # then the selected profile
            return profile[profile_key]
        if env_key and os.environ.get(env_key):  # then env var
            return os.environ[env_key]
        return default                       # finally the built-in default

    compact = pick(args.compact_system_prompt, "compact_system_prompt",
                   None, os.environ.get("AGENT_COMPACT_SYSTEM_PROMPT", "") == "1")

    config = AgentConfig(
        base_url=pick(args.base_url, "base_url", "AGENT_BASE_URL", "http://127.0.0.1:8080"),
        model=pick(args.model, "model", "AGENT_MODEL", "gemma-4-E4B-it-Q4_K_M.gguf"),
        max_steps=pick(args.max_steps, "max_steps", None, 8),
        max_tokens=pick(args.max_tokens, "max_tokens", None, 256),
        temperature=pick(args.temperature, "temperature", None, 0.2),
        timeout=pick(args.timeout, "timeout", None, 120.0),
        max_history=pick(args.max_history, "max_history", None, 12),
        verbose=bool(args.verbose),
        coding=bool(args.coding),
        allow_exec=bool(args.allow_exec),
        workspace=args.workspace,
    )
    return config, bool(compact)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tiny ReAct tool-using agent over an OpenAI-compatible server (CPU or NPU). "
                    "Runs unchanged on XElite host and IQ8 -- only --base-url differs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("prompt", nargs="?", help="One-shot prompt. Omit (or use -i) for interactive chat.")
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="Force interactive chat mode (profile picker + tool list, then a prompt loop).")
    parser.add_argument("--profile", help="Named preset from agent_profiles.json (e.g. cpu, npu).")
    parser.add_argument("--list-profiles", action="store_true",
                        help="List profiles from agent_profiles.json and exit.")
    # Flags below default to None so resolve_config can tell "explicitly passed"
    # from "left at default" and apply profile/env values correctly.
    parser.add_argument(
        "--base-url", default=None,
        help="OpenAI-compatible server base URL (env: AGENT_BASE_URL, or a profile). "
             "CPU default is llama.cpp on :8080; NPU default is genie_server.py on :8081.",
    )
    parser.add_argument(
        "--model", default=None,
        help="Model name the server reports (env: AGENT_MODEL, or a profile). "
             "The E4B default is the proven IQ8 fit.",
    )
    parser.add_argument("--max-steps", type=int, default=None, help="Max tool/answer iterations. (default: 8)")
    parser.add_argument("--max-tokens", type=int, default=None, help="Tokens per model reply. (default: 256)")
    parser.add_argument("--temperature", type=float, default=None, help="Sampling temperature. (default: 0.2)")
    parser.add_argument("--timeout", type=float, default=None, help="HTTP timeout (seconds). (default: 120.0)")
    parser.add_argument("--max-history", type=int, default=None,
                        help="Keep system + first task + this many recent messages "
                             "(caps context for small-context servers; 0 = no trim). (default: 12)")
    parser.add_argument("--coding", action="store_true",
                        help="Enable coding tools (write_file, apply_patch) sandboxed to the "
                             "workspace dir. Off by default (agent stays read-only).")
    parser.add_argument("--allow-exec", action="store_true",
                        help="Also enable run_command (write-capable shell). Each call asks for "
                             "y/N approval. Implies --coding.")
    parser.add_argument("--workspace", default=None,
                        help="Workspace dir coding tools are confined to (default: ./workspace).")
    parser.add_argument(
        "--compact-system-prompt", action=argparse.BooleanOptionalAction, default=None,
        help="Use a shorter system prompt (helps small-context servers like Genie bundles). "
             "Env AGENT_COMPACT_SYSTEM_PROMPT=1, or set per profile.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show each step + tool calls.")
    return parser.parse_args()


def _choose_profile(profiles: dict[str, dict[str, Any]]) -> str | None:
    """Interactive profile picker for when no --profile was given. Enter = skip."""
    if not profiles:
        return None
    names = list(profiles)
    print("\nSelect a profile (or press Enter for defaults):")
    for i, name in enumerate(names, 1):
        p = profiles[name]
        print(f"  {i}. {name:8} {p.get('model', '?')} @ {p.get('base_url', '?')}")
    try:
        choice = input("profile #> ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not choice:
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(names):
        return names[int(choice) - 1]
    if choice in profiles:
        return choice
    print(f"(unknown choice {choice!r}, using defaults)")
    return None


def _setup_coding(config: AgentConfig) -> None:
    """Apply coding mode: set the workspace sandbox and rebuild TOOLS.

    --allow-exec implies --coding. When on, resolves/creates the workspace dir,
    sets the module-level _WORKSPACE the write tools are confined to, and adds
    the coding tools to the registry. No-op (read-only default) otherwise.
    """
    global _WORKSPACE, TOOLS
    coding = config.coding or config.allow_exec
    if not coding:
        return
    root = Path(config.workspace).expanduser() if config.workspace else Path.cwd() / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    _WORKSPACE = root
    TOOLS = _build_registry(coding=True, allow_exec=config.allow_exec)
    print(f"\033[35m[coding] workspace: {root.resolve()}"
          + ("  (run_command enabled, approval-gated)" if config.allow_exec else "")
          + "\033[0m")


def main() -> None:
    args = parse_args()
    profiles = load_profiles()

    if args.list_profiles:
        _print_profiles(profiles)
        return

    # Interactive if -i was passed OR no one-shot prompt was given.
    interactive = args.interactive or not args.prompt

    # In interactive mode with no explicit --profile, let the user pick one.
    if interactive and not args.profile:
        args.profile = _choose_profile(profiles)

    config, compact = resolve_config(args, profiles)
    _setup_coding(config)
    client = ModelClient(config)
    system_prompt = build_system_prompt(compact=compact)

    if not interactive:
        print(run_agent(args.prompt, client, system_prompt, config))
        return

    # The THINK -> ACT -> OBSERVE -> RESPOND trace is OFF by default; pass `-v`
    # to start with it ON, or toggle it live with /verbose. config.verbose
    # already reflects `-v` (set in resolve_config), so don't override it here.
    print(f"\nAgent ready (model={config.model} @ {config.base_url}).")
    _print_tools()
    print("\nCommands: /verbose (toggle THINK/ACT/OBSERVE trace), /tools, "
          "/reset (clear memory), /help, /exit.")
    print(f"Trace is {'ON' if config.verbose else 'OFF'} -- "
          "toggle with /verbose (or pass -v to start ON).")
    # Conversation memory across turns: clean {user, assistant} pairs so
    # follow-ups ("run it") resolve. Cap it so a long session can't overflow the
    # small NPU context; /reset clears it.
    history: list[dict[str, str]] = []
    max_turns = max(config.max_history // 2, 1)  # history entries come in pairs
    while True:
        try:
            user = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user in ("/exit", "/quit", "exit", "quit"):
            break
        if user in ("/verbose", "/v", "/trace"):
            config.verbose = not config.verbose
            print(f"trace {'ON' if config.verbose else 'OFF'}")
            continue
        if user in ("/reset", "/clear", "/new"):
            history.clear()
            print("conversation memory cleared")
            continue
        if user == "/tools":
            _print_tools()
            continue
        if user in ("/help", "/?"):
            print("Commands: /verbose toggle trace | /tools list tools | "
                  "/reset clear memory | /exit quit. Anything else is sent to the agent.")
            continue
        answer = run_agent(user, client, system_prompt, config, history=history)
        print(answer)
        # Record the turn, then trim to the most recent `max_turns` exchanges.
        history.append({"role": "user", "content": user})
        history.append({"role": "assistant", "content": answer})
        if len(history) > max_turns * 2:
            del history[:-max_turns * 2]


if __name__ == "__main__":
    main()
