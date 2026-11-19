"""
agent.mojo

Minimal agent loop: read user input → call Genie (NPU) → parse tool call →
execute tool → feed result back → repeat.

Run:
  mojo run src/agent.mojo                          # uses defaults (127.0.0.1:8081)
  mojo run src/agent.mojo -- --host 192.168.29.185 # point at IQ9 from PC

Requires:
  genie_server.py running and serving the model on the configured port.
  Start it on IQ9 with: scripts/start_genie.sh
"""

from python import Python
from genie_client import GenieClient


# --------------------------------------------------------------------------- #
# Tool definitions
# --------------------------------------------------------------------------- #

fn tool_get_device_info() raises -> String:
    var platform = Python.import_module("platform")
    var machine = str(platform.machine())
    var system = str(platform.system())
    var node = str(platform.node())
    return String("system=") + system + " machine=" + machine + " node=" + node


fn tool_echo(text: String) -> String:
    return text


fn dispatch_tool(name: String, args: String) raises -> String:
    if name == "get_device_info":
        return tool_get_device_info()
    elif name == "echo":
        return tool_echo(args)
    return String("unknown tool: ") + name


# --------------------------------------------------------------------------- #
# Prompt helpers
# --------------------------------------------------------------------------- #

fn build_system_prompt() -> String:
    return (
        "You are a helpful AI assistant running on a Qualcomm IQ device. "
        "You may call tools by replying with TOOL:<name>:<args> on its own line. "
        "Available tools: get_device_info (no args), echo:<text>. "
        "When you have a final answer, reply normally without a TOOL: prefix."
    )


fn parse_tool_call(response: String) -> (String, String):
    """Return (tool_name, tool_args) if response starts with TOOL:, else ("", "")."""
    if response.startswith("TOOL:"):
        var rest = response[5:]
        var colon_pos = rest.find(":")
        if colon_pos >= 0:
            return rest[:colon_pos], rest[colon_pos + 1 :]
        return rest, ""
    return "", ""


# --------------------------------------------------------------------------- #
# Agent loop
# --------------------------------------------------------------------------- #

fn run_agent(client: GenieClient, user_input: String) raises:
    var system = build_system_prompt()
    var history = String("System: ") + system + "\nUser: " + user_input + "\n"

    alias MAX_STEPS = 4

    for step in range(MAX_STEPS):
        var response = client.complete(history + "Assistant:")
        print("Assistant:", response)

        var tool_name: String
        var tool_args: String
        tool_name, tool_args = parse_tool_call(response.strip())

        if not tool_name:
            return  # final answer

        var tool_result = dispatch_tool(tool_name, tool_args)
        print("Tool result:", tool_result)

        history = (
            history
            + "Assistant: "
            + response
            + "\nTool result: "
            + tool_result
            + "\nAssistant:"
        )

    print("Stopped after", MAX_STEPS, "steps.")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

fn main() raises:
    var sys = Python.import_module("sys")

    var host = String("127.0.0.1")
    var port = 8081
    var model = String("gemma-4-e4b-genie")

    # Minimal arg parsing: --host <h> --port <p> --model <m>
    var argv = sys.argv
    var i = 1
    while i < len(argv) - 1:
        var flag = str(argv[i])
        if flag == "--host":
            host = str(argv[i + 1])
            i += 2
        elif flag == "--port":
            port = int(str(argv[i + 1]))
            i += 2
        elif flag == "--model":
            model = str(argv[i + 1])
            i += 2
        else:
            i += 1

    var client = GenieClient(host, port, model)

    print("Mojo agent — connecting to", host + ":" + str(port), "model:", model)
    print("Type a prompt and press Enter. Ctrl+C to quit.\n")

    while True:
        Python.import_module("sys").stdout.write("You: ")
        Python.import_module("sys").stdout.flush()
        var line = str(Python.import_module("builtins").input())
        if not line.strip():
            continue
        run_agent(client, line)
        print()
