import net from "node:net";

const pipeName = process.env.ROBOAGENT_PIPE_NAME ?? "roboagent-english-mock";
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
      socket.write(`${JSON.stringify({
        protocol: "roboagent-pi/1",
        request_id: request.request_id,
        kind: "final",
        text: "这是非英语回复。 Esta resposta também está em português.",
        metrics: { prompt_tokens: 12, generated_tokens: 9 },
      })}\n`);
    }
  });
});

server.listen(pipePath, () => {
  process.stdout.write("MOCK_ENGLISH_LISTENING\n");
});
