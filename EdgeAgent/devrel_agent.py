#!/usr/bin/env python3
"""DevRel onboarding agent using the portable loop plus read-only DevRel tools."""

from __future__ import annotations

import argparse
import os

import agent
from devrel_local import ensure_local_url
from devrel_tools import DEVREL_PROMPT, register_devrel_tools, route_devrel_prompt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DevRel bring-up and onboarding agent for Qualcomm and portable AI stacks.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("prompt", nargs="?", help="One-shot request. Omit for interactive mode.")
    parser.add_argument("-i", "--interactive", action="store_true")
    parser.add_argument("--profile", help="Named model profile from agent_profiles.json.")
    parser.add_argument("--list-profiles", action="store_true")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--max-history", type=int, default=None)
    parser.add_argument("--compact-system-prompt", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--coding", action="store_true")
    parser.add_argument("--allow-exec", action="store_true")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profiles = agent.load_profiles()
    if args.list_profiles:
        agent._print_profiles(profiles)
        return
    config, compact = agent.resolve_config(args, profiles)
    try:
        config.base_url = ensure_local_url(config.base_url)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from exc
    os.environ["DEVREL_MODEL_BASE_URL"] = config.base_url
    agent._setup_coding(config)
    register_devrel_tools()

    client = agent.ModelClient(config)
    system_prompt = agent.build_system_prompt(compact=compact) + DEVREL_PROMPT
    interactive = args.interactive or not args.prompt
    if not interactive:
        print(agent.run_agent(route_devrel_prompt(args.prompt), client, system_prompt, config))
        return

    print(f"\nDevRel agent ready (model={config.model} @ {config.base_url}).")
    agent._print_tools()
    print("\nCommands: /verbose, /tools, /reset, /help, /exit.")
    history: list[dict[str, str]] = []
    max_turns = max(config.max_history // 2, 1)
    while True:
        try:
            prompt = input("devrel> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not prompt:
            continue
        command = prompt.lower()
        if command in {"/exit", "/quit"}:
            break
        if command in {"/verbose", "/v", "/trace"}:
            config.verbose = not config.verbose
            print(f"Trace is {'ON' if config.verbose else 'OFF'}.")
            continue
        if command == "/tools":
            agent._print_tools()
            continue
        if command == "/reset":
            history.clear()
            print("Conversation memory cleared.")
            continue
        if command == "/help":
            print("/verbose  /tools  /reset  /help  /exit")
            continue

        answer = agent.run_agent(
            route_devrel_prompt(prompt), client, system_prompt, config, history=history
        )
        print(answer)
        history.extend(
            [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": answer},
            ]
        )
        history = history[-(2 * max_turns):]


if __name__ == "__main__":
    main()
