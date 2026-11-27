"""
genie_client.mojo

Thin IPC client that talks to the Genie server (genie_server.py, port 8081)
over HTTP. Sends a prompt, reads back the completion.

Architecture:
  Mojo (ARM CPU) → HTTP → genie_server.py → genie-t2t-run → Hexagon NPU

The server exposes an OpenAI-compatible /v1/chat/completions endpoint.
This module handles only the network round-trip; the agent loop lives in
agent.mojo.

Usage:
  var client = GenieClient("127.0.0.1", 8081, "gemma-4-e4b-genie")
  var reply = client.complete("Explain edge AI in two sentences.")
  print(reply)
"""

from python import Python


struct GenieClient:
    var host: String
    var port: Int
    var model: String
    var max_tokens: Int
    var timeout_s: Int

    fn __init__(
        out self,
        host: String,
        port: Int,
        model: String,
        max_tokens: Int = 256,
        timeout_s: Int = 60,
    ):
        self.host = host
        self.port = port
        self.model = model
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s

    fn complete(self, prompt: String) raises -> String:
        """Send a single user turn and return the assistant reply."""
        var json = Python.import_module("json")
        var urllib_req = Python.import_module("urllib.request")

        var url = String("http://") + self.host + ":" + String(self.port) + "/v1/chat/completions"

        var payload_dict = Python.dict()
        payload_dict["model"] = self.model
        payload_dict["max_tokens"] = self.max_tokens
        payload_dict["stream"] = False

        var msg = Python.dict()
        msg["role"] = "user"
        msg["content"] = prompt

        var messages = Python.list()
        messages.append(msg)
        payload_dict["messages"] = messages

        var payload_bytes = json.dumps(payload_dict).encode("utf-8")

        var headers = Python.dict()
        headers["Content-Type"] = "application/json"

        var req = urllib_req.Request(url, data=payload_bytes, headers=headers)
        var resp = urllib_req.urlopen(req, timeout=self.timeout_s)
        var data = json.loads(resp.read())

        return String(data["choices"][0]["message"]["content"])
