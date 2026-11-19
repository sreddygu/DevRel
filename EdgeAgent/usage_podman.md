# Usage (Podman)

> Running `agent.py` in a container. For native (non-container) CPU/NPU bring-up,
> see [`usage.md`](usage.md); for the project overview, see [`README.md`](README.md).

This project can be run in a Podman container for the **agent** itself.

Important constraints:
- The container does **not** run the model. It talks HTTP to a server you start separately.
- The **NPU/Genie stack is not containerized**. Run `genie_server.py` natively on Windows; then point the containerized agent at it.
- Tools like `read_file` / `run_shell` see the **container**, not your host, unless you mount files in.

## 1) Prereqs

- Podman installed and working (`podman version`)
- A model server running on the host:
  - CPU: `llama-server` on `http://127.0.0.1:8080`
  - NPU: `genie_server.py` on `http://127.0.0.1:8081`

### Important (Windows + Podman VM networking)

If Podman is using a VM/WSL machine, the container cannot reach services that
only listen on `127.0.0.1` on Windows.

To allow container → host connectivity, start your host servers listening on
**all interfaces**:
- CPU `llama-server`: use `--host 0.0.0.0`
- NPU `genie_server.py`: use `--host 0.0.0.0`

Then point the container at:
- `http://host.containers.internal:8080` (CPU)
- `http://host.containers.internal:8081` (NPU)

If you still get `Connection refused`, check Windows Defender Firewall and allow
inbound TCP on the port for the server executable.

If `host.containers.internal` still doesn’t work in your setup, use your Windows
host LAN IP instead:

```powershell
ipconfig | Select-String "IPv4 Address"
```

Then point the container at `http://<YOUR_IP>:8080` (CPU) / `http://<YOUR_IP>:8081` (NPU).

## 2) Build the agent image

From the repository's `projects\EdgeAgent` directory:

```powershell
podman build -t edge-agent .
```

## 3) Run against CPU server (llama.cpp)

### Option A: Linux / `--network=host` (simplest when available)

```powershell
podman run --rm -it --network=host edge-agent `
  --base-url http://127.0.0.1:8080 `
  --model gemma-4-E4B-it-Q4_K_M.gguf `
  -v "What is 12.5% of 840?"
```

### Option B: Windows/macOS Podman VM (recommended)

On Podman Desktop (VM-backed), `127.0.0.1` inside the container is **not** your host.
Use the Podman host alias:

- `http://host.containers.internal:8080` (preferred on Podman)

```powershell
podman run --rm -it edge-agent `
  --base-url http://host.containers.internal:8080 `
  --model gemma-4-E4B-it-Q4_K_M.gguf `
  -v "What is 12.5% of 840?"
```

If that hostname does not resolve in your setup, you may need to use the Podman VM gateway IP instead.

## 4) Run against NPU server (Genie shim)

1) Start `genie_server.py` **natively** on Windows (see [`usage.md`](usage.md)).
2) Run the agent container pointing at the host’s `:8081`:

```powershell
podman run --rm -it edge-agent `
  --base-url http://host.containers.internal:8081 `
  --model qwen3-4b-genie `
  --compact-system-prompt `
  -v "What is 2^10?"
```

## 5) Mount host files for tools (optional)

If you want `read_file` to see a host file, mount it read-only into the container and read the mounted path.

Example: mount this project read-only at `/work`:

```powershell
podman run --rm -it -v ${PWD}:/work:ro edge-agent `
  --base-url http://host.containers.internal:8080 `
  -v "Read /work/README.md and tell me the project name."
```
