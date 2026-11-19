import net from "node:net";

const pipeName = process.env.ROBOAGENT_PIPE_NAME ?? "roboagent-pi-mock";
const pipePath = `\\\\.\\pipe\\${pipeName}`;

const server = net.createServer((socket) => {
  let pending = "";
  socket.setEncoding("utf8");
  socket.on("data", (chunk) => {
    pending += chunk;
    const lines = pending.split("\n");
    pending = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const request = JSON.parse(line);
      if (request.phase === "user") {
        socket.write(`${JSON.stringify({
          protocol: "roboagent-pi/1",
          request_id: request.request_id,
          kind: "tool_call",
          tool_call: { name: "read_file", arguments: { path: "README.md", startLine: 1, endLine: 12 } },
        })}\n`);
      } else if (request.phase === "tool_result") {
        socket.write(`${JSON.stringify({
          protocol: "roboagent-pi/1",
          request_id: request.request_id,
          kind: "final",
          text: "The RoboAgent host requires QNN_SDK_ROOT, Path entries for the backend and ARM64 QNN libraries, and ADSP_LIBRARY_PATH.",
        })}\n`);
      } else {
        socket.write(`${JSON.stringify({ protocol: "roboagent-pi/1", request_id: request.request_id, kind: "error", error: "Unexpected phase." })}\n`);
      }
    }
  });
});

server.listen(pipePath, () => console.log(`MOCK_LISTENING ${pipePath}`));
