#!/usr/bin/env python3
"""eval_agent.py -- a tiny, stdlib-only capability check for agent.py.

Motivation (per Sebastian Raschka's "Using Local Coding Agents"): don't trust
leaderboard benchmarks -- curate a SMALL set of tasks that reflect your own
workflow and score the agent on them, re-running on every new model/backend to
catch regressions. This is the local-agent equivalent of a unit-test suite.

It reuses agent.py's own loop and parser (no duplicated logic), so it tests the
REAL agent, and runs against the same OpenAI-compatible server -- so you can
score CPU (llama.cpp) vs NPU (genie_server.py) with identical tasks:

    python eval_agent.py --base-url http://127.0.0.1:8080 --model gemma-4-E4B-it-Q4_K_M.gguf
    python eval_agent.py --base-url http://127.0.0.1:8081 --model qwen3-4b-genie --compact-system-prompt

Checks per task (see eval_tasks.json):
  json_valid       -- the model's FIRST reply parses as a JSON action.
  first_tool       -- the first action calls one of the allowed `tools`.
  answer_contains  -- the final answer contains ALL `substrings` (case-insensitive).

Exit code is non-zero if any task fails, so it drops into CI / a pre-commit hook.

Use ``--toolset devrel --tasks devrel_eval_tasks.json`` to score the DevRel
onboarding router instead of the base portable-agent tools.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import agent  # the module under test -- reuse its loop, client, and parser


def _first_action(client: agent.ModelClient, system_prompt: str,
                  prompt: str) -> tuple[str, agent.Action]:
    """One model call on the opening messages -> (raw_reply, parsed Action).

    Cheap (a single request) and lets us inspect the FIRST tool/JSON decision
    without running the whole loop.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    reply = client.complete(messages)
    return reply, agent.parse_action(reply)


def _check(check: dict, *, reply: str, action: agent.Action,
           final_answer: str | None) -> tuple[bool, str]:
    """Apply one check. Returns (passed, reason)."""
    kind = check.get("type")

    if kind == "json_valid":
        ok = agent.extract_json(reply) is not None
        return ok, "ok" if ok else "first reply was not valid JSON"

    if kind == "first_tool":
        allowed = check.get("tools", [])
        got = action.tool if not action.is_answer else "(answered, no tool)"
        ok = got in allowed
        return ok, "ok" if ok else f"expected tool in {allowed}, got {got!r}"

    if kind == "answer_contains":
        subs = check.get("substrings", [])
        hay = (final_answer or "").lower()
        missing = [s for s in subs if s.lower() not in hay]
        ok = not missing
        return ok, "ok" if ok else f"answer missing {missing}"

    return False, f"unknown check type {kind!r}"


def run_task(task: dict, client: agent.ModelClient, system_prompt: str,
             config: agent.AgentConfig) -> tuple[bool, list[str]]:
    """Run one task and evaluate all its checks. Returns (passed, reasons)."""
    prompt = task["prompt"]
    checks = task.get("checks", [])

    # Only pay for a full agent run if a check actually needs the final answer.
    needs_answer = any(c.get("type") == "answer_contains" for c in checks)
    needs_first = any(c.get("type") in ("json_valid", "first_tool") for c in checks)

    reply, action = ("", agent.Action())
    if needs_first:
        reply, action = _first_action(client, system_prompt, prompt)

    final_answer = None
    if needs_answer:
        final_answer = agent.run_agent(prompt, client, system_prompt, config)

    reasons, passed = [], True
    for c in checks:
        ok, reason = _check(c, reply=reply, action=action, final_answer=final_answer)
        passed = passed and ok
        reasons.append(f"{c.get('type')}: {reason}")
    return passed, reasons


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Score agent.py against a curated task set (CPU or NPU).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--tasks", type=Path, default=Path(__file__).with_name("eval_tasks.json"),
                   help="Task file (JSON).")
    p.add_argument("--toolset", choices=("base", "devrel"), default="base",
                   help="Register the base tools or the DevRel onboarding tools.")
    p.add_argument("--profile", help="Named preset from agent_profiles.json (e.g. cpu, npu). "
                                      "Sets base_url/model/compact unless overridden by a flag.")
    # None defaults so an explicit flag can be told apart from "use the profile".
    p.add_argument("--base-url", default=None, help="OpenAI-compatible server base URL. (default: http://127.0.0.1:8080)")
    p.add_argument("--model", default=None, help="Model name the server reports. (default: gemma-4-E4B-it-Q4_K_M.gguf)")
    p.add_argument("--max-steps", type=int, default=6)
    p.add_argument("--max-tokens", type=int, default=256)
    p.add_argument("--temperature", type=float, default=0.0,
                   help="0.0 by default for reproducible scoring.")
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--compact-system-prompt", action=argparse.BooleanOptionalAction, default=None,
                   help="Match how you run agent.py on small-context servers (NPU). "
                        "Defaults to the profile's setting, else off.")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Show each failing check's reason (passing tasks stay quiet).")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    tasks = json.loads(args.tasks.read_text(encoding="utf-8")).get("tasks", [])

    if args.toolset == "devrel":
        from devrel_tools import DEVREL_PROMPT, register_devrel_tools, route_devrel_prompt

        register_devrel_tools()
        for task in tasks:
            task["prompt"] = route_devrel_prompt(task["prompt"])
    else:
        DEVREL_PROMPT = ""

    # Resolve profile -> base_url/model/compact, with explicit flags winning.
    profiles = agent.load_profiles()
    profile = {}
    if args.profile:
        if args.profile not in profiles:
            raise SystemExit(f"error: unknown profile '{args.profile}'. "
                             f"Known: {', '.join(profiles) or '(none)'}.")
        profile = profiles[args.profile]

    def pick(cli_val, key, default):
        if cli_val is not None:
            return cli_val
        return profile.get(key, default)

    base_url = pick(args.base_url, "base_url", "http://127.0.0.1:8080")
    model = pick(args.model, "model", "gemma-4-E4B-it-Q4_K_M.gguf")
    compact = pick(args.compact_system_prompt, "compact_system_prompt", False)
    if args.toolset == "devrel":
        from devrel_local import ensure_local_url

        base_url = ensure_local_url(base_url)

    config = agent.AgentConfig(
        base_url=base_url, model=model, max_steps=args.max_steps,
        max_tokens=args.max_tokens, temperature=args.temperature,
        timeout=args.timeout, verbose=False,
    )
    client = agent.ModelClient(config)
    system_prompt = agent.build_system_prompt(compact=bool(compact)) + DEVREL_PROMPT

    print(f"eval: {len(tasks)} tasks vs {config.model} @ {config.base_url}\n")
    passed_count = 0
    for task in tasks:
        passed, reasons = run_task(task, client, system_prompt, config)
        passed_count += passed
        status = "\033[32mPASS\033[0m" if passed else "\033[31mFAIL\033[0m"
        print(f"{status} {task['name']}")
        # Show reasons for failures always; for passes only with -v.
        for r in reasons:
            failed = not r.endswith(": ok")
            if failed or args.verbose:
                print(f"       - {r}")

    total = len(tasks)
    pct = (100.0 * passed_count / total) if total else 0.0
    print(f"\nScore: {passed_count}/{total} passed ({pct:.1f}%)")
    print(f"Usage: {client.usage.summary()}")
    sys.exit(0 if passed_count == total else 1)


if __name__ == "__main__":
    main()
