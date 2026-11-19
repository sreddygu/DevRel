# Running EdgeAgent on IQ8

This runbook brings up the minimal agent stack on a Qualcomm IQ8 / QCS8275
device running Qualcomm Linux Reference Distro 2.0 on `aarch64`. The CLI agent
is standard-library-only and talks to an OpenAI-compatible model endpoint; it
does not load a model itself.

The validated fast path uses the preinstalled AURA `llama.cpp` service and its
Qwen2.5 0.5B GGUF model. The larger Gemma E4B profile remains available for a
separate, intentionally provisioned model-server setup.

Do not store the device password, SSH private key, or Wi-Fi credentials in this
repository. Keep them in a password manager or SSH agent.

---

## 0. Verify the Device

From the development PC, connect with a pinned SSH host key:

```bash
ssh -o IdentitiesOnly=yes root@<IQ8_IP>
```

After a reflash, verify the new host-key fingerprint through a trusted channel
before accepting it. On the device:

```bash
hostname
uname -a
python3 --version
free -h
df -h /
```

Expected device characteristics include hostname similar to `iq-8275-evk`,
`aarch64`, Python 3.10 or newer, and approximately 11 GiB RAM.

---

## 1. Copy Only the Minimal Agent Files

The CLI needs only `agent.py` and `agent_profiles.json`. Do not copy the entire
`EdgeAgent` working directory, virtual environments, logs, evidence, or credentials.

From the PC, while in the `projects/EdgeAgent` directory:

```bash
ssh root@<IQ8_IP> 'install -d -m 700 /root/academy-agents'
scp agent.py agent_profiles.json root@<IQ8_IP>:/root/academy-agents/
ssh root@<IQ8_IP> \
  'chmod 600 /root/academy-agents/agent.py /root/academy-agents/agent_profiles.json'
```

Optionally compare checksums:

```bash
sha256sum agent.py agent_profiles.json
ssh root@<IQ8_IP> \
  'cd /root/academy-agents && sha256sum agent.py agent_profiles.json'
```

---

## 2. Use the Preinstalled AURA Model Server

Check the local endpoint on IQ8:

```bash
curl -s http://127.0.0.1:8080/v1/models
```

The validated IQ8 image reports the AURA model at:

```text
/opt/aura-llm/qwen2.5-0.5b.gguf
```

Use the `iq8-aura-cpu` profile. It enables a compact system prompt,
deterministic sampling, and conservative token/step limits appropriate for the
small model:

```bash
cd /root/academy-agents
python3 agent.py --list-profiles
python3 agent.py --profile iq8-aura-cpu -i
```

One-shot examples:

```bash
python3 agent.py --profile iq8-aura-cpu -v \
  'Call sys_info with empty args. Then summarize the device.'

python3 agent.py --profile iq8-aura-cpu -v \
  'Call the calculator tool exactly once with expression set to 840*0.125. Then answer with only the numeric observation.'
```

The 0.5B model is useful for basic local operation but needs explicit tool names
and argument shapes for reliable calls. Use the larger Gemma E4B model when
better instruction following is more important than startup time and memory.

---

## 3. Optional Gemma E4B Server

Use this path only after provisioning both `llama-server` and the Gemma GGUF on
IQ8. Do not stop or replace the shared AURA service unless that is intentional.

```bash
mkdir -p /root/logs
LOG=/root/logs/llama_server_gemma4_$(date +%Y%m%d_%H%M%S).log
setsid /root/llama.cpp/build/bin/llama-server \
  -m /root/models/gemma4/gemma-4-E4B-it-Q4_K_M.gguf \
  --host 127.0.0.1 --port 8082 \
  --threads 4 --threads-batch 4 \
  --ctx-size 1024 --batch-size 256 --ubatch-size 64 \
  --parallel 1 \
  </dev/null >"$LOG" 2>&1 &
```

Run the agent with explicit overrides because the standard `iq8-cpu` profile
uses port 8080:

```bash
python3 agent.py --profile iq8-cpu \
  --base-url http://127.0.0.1:8082 \
  -i
```

Keep model endpoints bound to `127.0.0.1`. Do not expose an unauthenticated
OpenAI-compatible endpoint directly to the office network.

---

## 4. Optional Browser App

Copy `agentApp.py` only if a browser UI is required:

```bash
scp agentApp.py root@<IQ8_IP>:/root/academy-agents/
```

First check whether Flask is available:

```bash
python3 -c 'import flask; print(flask.__version__)'
```

If Flask is missing, install it through the package feed or Python environment
approved for the IQ8 image. Do not assume Debian `apt-get` is available on
Qualcomm Linux Reference Distro.

Launch the app on loopback only:

```bash
cd /root/academy-agents
LOG=/root/logs/agentApp_$(date +%Y%m%d_%H%M%S).log
setsid python3 agentApp.py \
  --profile iq8-aura-cpu \
  --host 127.0.0.1 --port 8090 \
  </dev/null >"$LOG" 2>&1 &
curl -s http://127.0.0.1:8090/api/info
```

The browser app has no authentication. Do not bind it to `0.0.0.0`, and do not
enable `--coding`, `--allow-exec`, or `--yes` for a shared or remotely reachable
session.

View the UI through an SSH tunnel from the PC:

```bash
ssh -N -L 8090:127.0.0.1:8090 root@<IQ8_IP>
```

Then open `http://127.0.0.1:8090` on the PC.

---

## Stop and Troubleshoot

Stop only processes started specifically for this run:

```bash
pkill -f agentApp.py
pkill -f 'llama-server.*--port 8082'
```

Do not stop the port-8080 AURA server if other applications use it.

| Symptom | Suggested check |
|---|---|
| `Could not reach model server` | Run `curl -s http://127.0.0.1:8080/v1/models`. |
| Model repeats a tool call | Use explicit wording with the exact tool name and argument. |
| Invalid calculator expression | Supply a mathematical expression such as `840*0.125`, not natural-language percentages. |
| Incomplete response | Increase `--max-tokens` cautiously or use the Gemma E4B server. |
| Browser app cannot import Flask | Use the IQ8-approved package feed or isolated Python environment. |
| Browser endpoint is reachable from other hosts | Stop it and restart with `--host 127.0.0.1`. |
