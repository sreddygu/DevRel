import json, urllib.request
BASE="http://127.0.0.1:8080"
MODEL="gemma-4-E4B-it-Q4_K_M.gguf"
msgs=[{"role":"system","content":"You are a helpful assistant. No tool calls. Answer plainly."}]
while True:
    u=input("> ").strip()
    if u in ("/exit","/quit","exit","quit"): break
    msgs.append({"role":"user","content":u})
    req=urllib.request.Request(
        f"{BASE}/v1/chat/completions",
        data=json.dumps({"model":MODEL,"messages":msgs,"max_tokens":256,"temperature":0.2}).encode(),
        headers={"Content-Type":"application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        obj=json.load(r)
    a=(obj["choices"][0]["message"].get("content") or "").strip()
    print(a)
    msgs.append({"role":"assistant","content":a})