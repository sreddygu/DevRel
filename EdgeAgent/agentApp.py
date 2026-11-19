#!/usr/bin/env python3
"""agentApp.py -- a Flask HTTP UI around agent.py.

Same agent, same tools, same THINK -> ACT -> OBSERVE loop you get from the CLI --
just driven from a browser instead of a terminal. This is a *thin wrapper*: it
imports agent.py and reuses its config plumbing, ModelClient, and run_agent()
verbatim, so there is exactly one agent implementation to maintain.

    python agentApp.py                               # serve on 127.0.0.1:8090
    python agentApp.py --profile npu                 # start on the NPU profile
    python agentApp.py --profile cpu --coding        # enable write tools
    python agentApp.py --profile npu --coding --allow-exec --yes  # auto-approve run_command
    python agentApp.py --port 9000 --host 0.0.0.0    # expose on the LAN (careful)

Then open http://127.0.0.1:8090 in a browser. Profile + coding/allow-exec/auto-yes
are ALSO selectable live in the UI (the "settings" panel) -- the launch flags just
set the initial state.

Design notes (why it looks the way it does):
- **Flask** for the HTTP layer (the one pip dependency in this project; the CLI
  agent.py stays stdlib-only). Templates/JS are inline so it's still one file.
- **No-cache headers on every response** -- browsers were serving a stale copy
  of the page after edits; this stops that.
- **The trace is captured, not reprinted.** run_agent() emits the colored
  THINK/ACT/OBSERVE lines to stdout via agent._emit; we redirect stdout for the
  duration of a turn, strip ANSI, and ship the text to the browser. agent.py is
  untouched.
- **Turns are serialized with a lock.** stdout redirection, the run_command
  approval hook, and agent.py's global TOOLS/_WORKSPACE are all process-global,
  so two concurrent browser requests would trample each other. One turn at a
  time is fine for a single-user teaching tool.
- **run_command approval** can't read a terminal here, so the CLI's input()
  y/N gate is replaced by a policy toggle (--yes or the UI checkbox): auto-approve
  when on, otherwise auto-decline (safe default). The decision is visible in the trace.
"""
from __future__ import annotations

import argparse
import builtins
import copy
import io
import re
import sys
import threading

from flask import Flask, Response, jsonify, request

import agent  # the CLI module -- reused wholesale, never reimplemented


# --------------------------------------------------------------------------- #
# Shared run state (one conversation, like the CLI's interactive session)
# --------------------------------------------------------------------------- #
CONFIG: agent.AgentConfig
CLIENT: agent.ModelClient
SYSTEM_PROMPT: str
AUTO_YES: bool = False
PROFILES: dict = {}
SELECTED_PROFILE: str | None = None  # which profile name is active (None = flags/defaults)
BASE_ARGS: argparse.Namespace       # launch-time flags, reused as the reconfigure base

_lock = threading.Lock()          # serialize turns + reconfig (stdout/TOOLS are global)
_history: list[dict[str, str]] = []  # {user, assistant} turns, trimmed like the CLI

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def apply_config(profile: str | None, coding: bool, allow_exec: bool,
                 auto_yes: bool) -> dict[str, object]:
    """Rebuild CONFIG/CLIENT/SYSTEM_PROMPT/TOOLS for a new UI selection.

    Switching profile means a different model + server, so we start a fresh
    conversation (clear history) and a fresh usage tally (new ModelClient).
    resolve_config() is reused verbatim -- we just point args.profile at the
    chosen preset and let the same precedence (flag > profile > env > default)
    apply. allow_exec implies coding, mirroring the CLI.
    """
    global CONFIG, CLIENT, SYSTEM_PROMPT, AUTO_YES, SELECTED_PROFILE
    if profile is not None and profile not in PROFILES:
        raise ValueError(f"unknown profile '{profile}'. Known: {', '.join(PROFILES) or '(none)'}")
    coding = bool(coding or allow_exec)

    with _lock:
        # Start from the launch-time flags, then overlay the UI choices so any
        # --base-url/--model/etc. the operator passed still act as overrides.
        args = copy.copy(BASE_ARGS)
        args.profile = profile
        args.coding = coding
        args.allow_exec = bool(allow_exec)
        args.verbose = True  # always capture the trace; the browser toggles display

        CONFIG, compact = agent.resolve_config(args, PROFILES)
        # Rebuild the tool registry explicitly for BOTH directions -- _setup_coding
        # only ADDS coding tools (early-returns when off), so toggling coding off
        # needs a fresh read-only registry here.
        agent._WORKSPACE = None
        if coding:
            agent._setup_coding(CONFIG)
        else:
            agent.TOOLS = agent._build_registry(coding=False, allow_exec=False)
        CLIENT = agent.ModelClient(CONFIG)
        SYSTEM_PROMPT = agent.build_system_prompt(compact=compact)
        AUTO_YES = bool(auto_yes)
        SELECTED_PROFILE = profile
        _history.clear()
    return info()


def run_turn(message: str) -> dict[str, object]:
    """Run one agent turn and return {answer, trace, usage}.

    Mirrors the CLI's interactive loop body: feed prior history in, record the
    turn after, and trim to the most recent max_history/2 exchanges. The trace
    is whatever run_agent printed (captured off stdout, ANSI stripped).
    """
    with _lock:
        buf = io.StringIO()
        real_input, real_stdout = builtins.input, sys.stdout
        # run_command's y/N gate reads input(); in a browser there's no terminal,
        # so answer it from the launch-time --yes policy (default: decline).
        builtins.input = lambda *a, **k: ("y" if AUTO_YES else "n")
        sys.stdout = buf
        try:
            answer = agent.run_agent(message, CLIENT, SYSTEM_PROMPT, CONFIG,
                                     history=_history)
        finally:
            sys.stdout, builtins.input = real_stdout, real_input

        _history.append({"role": "user", "content": message})
        _history.append({"role": "assistant", "content": answer})
        max_turns = max(CONFIG.max_history // 2, 1)
        if len(_history) > max_turns * 2:
            del _history[: -max_turns * 2]

        return {
            "answer": answer,
            "trace": _strip_ansi(buf.getvalue()).rstrip(),
            "usage": CLIENT.usage.summary(),
        }


def tools_list() -> list[dict[str, str]]:
    return [{"signature": t.signature(), "summary": t.summary}
            for t in agent.TOOLS.values()]


def info() -> dict[str, object]:
    return {
        "model": CONFIG.model,
        "base_url": CONFIG.base_url,
        "coding": CONFIG.coding or CONFIG.allow_exec,
        "allow_exec": CONFIG.allow_exec,
        "auto_yes": AUTO_YES,
        "profile": SELECTED_PROFILE,
        "profiles": [
            {"name": n,
             "model": p.get("model", "?"),
             "base_url": p.get("base_url", "?"),
             "description": p.get("description", "")}
            for n, p in PROFILES.items()
        ],
    }


# --------------------------------------------------------------------------- #
# Flask app + routes
# --------------------------------------------------------------------------- #
app = Flask(__name__)


@app.after_request
def _no_cache(resp: Response) -> Response:
    """Stop the browser serving a stale page after edits (the bug that bit us)."""
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.get("/")
def index() -> Response:
    return Response(PAGE, mimetype="text/html")


@app.get("/api/tools")
def api_tools():
    return jsonify(tools=tools_list())


@app.get("/api/info")
def api_info():
    return jsonify(info())


@app.get("/api/profiles")
def api_profiles():
    return jsonify(profiles=info()["profiles"], selected=SELECTED_PROFILE)


@app.post("/api/chat")
def api_chat():
    msg = str((request.get_json(silent=True) or {}).get("message", "")).strip()
    if not msg:
        return jsonify(error="empty message"), 400
    try:
        return jsonify(run_turn(msg))
    except Exception as exc:  # noqa: BLE001 -- surface, don't crash the server
        return jsonify(error=f"{type(exc).__name__}: {exc}"), 500


@app.post("/api/reset")
def api_reset():
    with _lock:
        _history.clear()
    return jsonify(ok=True)


@app.post("/api/config")
def api_config():
    body = request.get_json(silent=True) or {}
    try:
        result = apply_config(
            profile=body.get("profile") or None,
            coding=bool(body.get("coding")),
            allow_exec=bool(body.get("allow_exec")),
            auto_yes=bool(body.get("auto_yes")),
        )
        return jsonify(ok=True, info=result)
    except Exception as exc:  # noqa: BLE001 -- surface bad selections
        return jsonify(error=f"{type(exc).__name__}: {exc}"), 400


# --------------------------------------------------------------------------- #
# The page (single file, no framework, no external assets)
# --------------------------------------------------------------------------- #
PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>EdgeAgent</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; font:14px/1.5 system-ui,sans-serif; background:#0f1115; color:#e6e6e6; }
  header { padding:10px 16px; background:#161922; border-bottom:1px solid #262b38;
           display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
  header b { color:#8ab4f8; }
  .meta { color:#8a90a0; font-size:12px; }
  main { max-width:900px; margin:0 auto; padding:16px; }
  #log { display:flex; flex-direction:column; gap:14px; margin-bottom:16px; }
  .turn { border:1px solid #262b38; border-radius:8px; overflow:hidden; }
  .u { background:#1b2130; padding:10px 12px; }
  .u .who { color:#8ab4f8; font-weight:600; font-size:12px; }
  .a { padding:10px 12px; background:#12151c; white-space:pre-wrap; }
  .a .who { color:#63d19e; font-weight:600; font-size:12px; }
  details { border-top:1px dashed #2c3242; }
  summary { cursor:pointer; padding:6px 12px; color:#c9a15a; font-size:12px; user-select:none; }
  pre.trace { margin:0; padding:10px 12px; background:#0a0c10; color:#b8c0cc;
              font:12px/1.45 ui-monospace,Menlo,Consolas,monospace; white-space:pre-wrap;
              max-height:340px; overflow:auto; }
  .usage { color:#6b7280; font-size:11px; padding:4px 12px 8px; }
  form { display:flex; gap:8px; position:sticky; bottom:0; padding:12px 0; background:#0f1115; }
  textarea { flex:1; resize:vertical; min-height:44px; background:#161922; color:#e6e6e6;
             border:1px solid #303645; border-radius:8px; padding:10px; font:inherit; }
  button { background:#2b5cff; color:#fff; border:0; border-radius:8px; padding:0 16px;
           font-weight:600; cursor:pointer; }
  button.ghost { background:#232838; color:#c9cfdb; }
  button:disabled { opacity:.5; cursor:default; }
  label.tr { color:#8a90a0; font-size:12px; display:flex; align-items:center; gap:4px; }
  .err { color:#ff7a7a; }
  #settings { display:none; gap:14px; flex-wrap:wrap; align-items:center;
              padding:10px 16px; background:#12151c; border-bottom:1px solid #262b38; }
  #settings.open { display:flex; }
  #settings select { background:#161922; color:#e6e6e6; border:1px solid #303645;
                     border-radius:6px; padding:4px 6px; font:inherit; }
  #settings button { padding:4px 14px; }
  #applymsg.ok { color:#63d19e; } #applymsg.bad { color:#ff7a7a; }
</style></head>
<body>
<header>
  <b>Agent</b>
  <span class="meta" id="meta">loading…</span>
  <span style="flex:1"></span>
  <label class="tr"><input type="checkbox" id="showtrace" checked> show trace</label>
  <button class="ghost" id="tools">tools</button>
  <button class="ghost" id="reset">reset</button>
  <button class="ghost" id="settingsbtn">⚙ settings</button>
</header>
<div id="settings">
  <label class="tr">profile
    <select id="profile"><option value="">(flags/defaults)</option></select>
  </label>
  <label class="tr"><input type="checkbox" id="coding"> coding (write_file, apply_patch)</label>
  <label class="tr"><input type="checkbox" id="allowexec"> allow-exec (run_command)</label>
  <label class="tr"><input type="checkbox" id="autoyes"> auto-approve commands (--yes)</label>
  <button id="apply">Apply</button>
  <span class="meta" id="applymsg"></span>
</div>
<main>
  <div id="log"></div>
  <form id="f">
    <textarea id="msg" placeholder="Ask the agent…  (Enter to send, Shift+Enter for newline)"></textarea>
    <button id="send" type="submit">Send</button>
  </form>
</main>
<script>
const log = document.getElementById('log');
const msg = document.getElementById('msg');
const form = document.getElementById('f');
const send = document.getElementById('send');
const showtrace = document.getElementById('showtrace');

function el(tag, cls, txt){ const e=document.createElement(tag); if(cls)e.className=cls; if(txt!=null)e.textContent=txt; return e; }

function addUser(text){
  const t = el('div','turn');
  const u = el('div','u'); u.append(el('div','who','you'), el('div',null,text));
  t.append(u); log.append(t); window.scrollTo(0,document.body.scrollHeight);
  return t;
}
function addAgent(turnEl, data){
  if(data.error){
    const a = el('div','a'); a.append(el('div','who','agent'), el('div','err',data.error));
    turnEl.append(a); return;
  }
  const a = el('div','a'); a.append(el('div','who','agent'), el('div',null,data.answer||'(no answer)'));
  turnEl.append(a);
  if(data.trace){
    const d = el('details'); if(showtrace.checked) d.open = true;
    d.append(el('summary',null,'THINK · ACT · OBSERVE trace'));
    d.append(el('pre','trace',data.trace));
    turnEl.append(d);
  }
  if(data.usage) turnEl.append(el('div','usage',data.usage));
  window.scrollTo(0,document.body.scrollHeight);
}

async function ask(text){
  const turnEl = addUser(text);
  send.disabled = true; msg.disabled = true;
  const thinking = el('div','a'); thinking.append(el('div','who','agent'), el('div',null,'…'));
  turnEl.append(thinking);
  try{
    const r = await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
                                       body:JSON.stringify({message:text})});
    const data = await r.json();
    thinking.remove();
    addAgent(turnEl, data);
  }catch(e){
    thinking.remove();
    addAgent(turnEl, {error:'request failed: '+e});
  }finally{
    send.disabled = false; msg.disabled = false; msg.focus();
  }
}

form.addEventListener('submit', e=>{ e.preventDefault(); const t=msg.value.trim(); if(!t)return; msg.value=''; ask(t); });
msg.addEventListener('keydown', e=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); form.requestSubmit(); }});

document.getElementById('reset').addEventListener('click', async ()=>{
  await fetch('/api/reset',{method:'POST'}); log.innerHTML=''; msg.focus();
});
document.getElementById('tools').addEventListener('click', async ()=>{
  const r = await fetch('/api/tools'); const {tools} = await r.json();
  const turnEl = el('div','turn'); const a = el('div','a');
  a.append(el('div','who','tools'));
  a.append(el('div',null, tools.map(t=>'• '+t.signature+'  —  '+t.summary).join('\n')));
  turnEl.append(a); log.append(turnEl); window.scrollTo(0,document.body.scrollHeight);
});

// ---- settings panel ----
const S = {
  panel: document.getElementById('settings'),
  btn: document.getElementById('settingsbtn'),
  profile: document.getElementById('profile'),
  coding: document.getElementById('coding'),
  allowexec: document.getElementById('allowexec'),
  autoyes: document.getElementById('autoyes'),
  apply: document.getElementById('apply'),
  msg: document.getElementById('applymsg'),
};

function renderMeta(i){
  const bits = [i.model+' @ '+i.base_url];
  if(i.profile) bits.unshift('['+i.profile+']');
  if(i.coding) bits.push('coding'+(i.allow_exec ? (i.auto_yes?' +exec(auto-yes)':' +exec(auto-decline)') : ''));
  else bits.push('read-only');
  document.getElementById('meta').textContent = bits.join('  ·  ');
}

// allow-exec implies coding; auto-yes only meaningful with allow-exec (mirror the CLI).
function syncDeps(){
  if(S.allowexec.checked) S.coding.checked = true;
  S.coding.disabled = S.allowexec.checked;      // can't turn coding off while exec is on
  S.autoyes.disabled = !S.allowexec.checked;
  if(!S.allowexec.checked) S.autoyes.checked = false;
}
S.allowexec.addEventListener('change', syncDeps);

function loadInfo(i){
  // profiles dropdown
  S.profile.innerHTML = '<option value="">(flags/defaults)</option>';
  (i.profiles||[]).forEach(p=>{
    const o = document.createElement('option');
    o.value = p.name;
    o.textContent = p.name + ' — ' + p.model + (p.description ? ' ('+p.description+')' : '');
    S.profile.append(o);
  });
  S.profile.value = i.profile || '';
  S.coding.checked = !!i.coding;
  S.allowexec.checked = !!i.allow_exec;
  S.autoyes.checked = !!i.auto_yes;
  syncDeps();
  renderMeta(i);
}

S.btn.addEventListener('click', ()=> S.panel.classList.toggle('open'));

S.apply.addEventListener('click', async ()=>{
  S.apply.disabled = true; S.msg.className = 'meta'; S.msg.textContent = 'applying…';
  try{
    const r = await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({profile:S.profile.value, coding:S.coding.checked,
                           allow_exec:S.allowexec.checked, auto_yes:S.autoyes.checked})});
    const data = await r.json();
    if(data.error){ S.msg.className='meta bad'; S.msg.textContent = data.error; }
    else{
      loadInfo(data.info); log.innerHTML='';   // new model = fresh conversation
      S.msg.className='meta ok'; S.msg.textContent = 'applied · conversation reset';
      msg.focus();
    }
  }catch(e){ S.msg.className='meta bad'; S.msg.textContent = 'request failed: '+e; }
  finally{ S.apply.disabled = false; }
});

fetch('/api/info').then(r=>r.json()).then(loadInfo);
msg.focus();
</script>
</body></html>
"""


# --------------------------------------------------------------------------- #
# CLI / startup
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Browser UI for the tiny ReAct agent (agent.py). Same agent, "
                    "same tools, same THINK/ACT/OBSERVE loop -- served over HTTP.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # Web-server flags.
    p.add_argument("--host", default="127.0.0.1",
                   help="Interface to bind. Use 0.0.0.0 to expose on the LAN (careful).")
    p.add_argument("--port", type=int, default=8090, help="Port to serve on.")
    p.add_argument("--yes", action="store_true",
                   help="Auto-approve run_command (no terminal to ask in). Default: auto-decline.")
    # Agent flags -- mirror agent.py so resolve_config() can be reused verbatim.
    p.add_argument("--profile", help="Named preset from agent_profiles.json (e.g. cpu, npu).")
    p.add_argument("--base-url", default=None, help="OpenAI-compatible server URL.")
    p.add_argument("--model", default=None, help="Model name the server reports.")
    p.add_argument("--max-steps", type=int, default=None)
    p.add_argument("--max-tokens", type=int, default=None)
    p.add_argument("--temperature", type=float, default=None)
    p.add_argument("--timeout", type=float, default=None)
    p.add_argument("--max-history", type=int, default=None)
    p.add_argument("--coding", action="store_true",
                   help="Enable sandboxed write tools (write_file, apply_patch).")
    p.add_argument("--allow-exec", action="store_true",
                   help="Also enable run_command (approval via --yes). Implies --coding.")
    p.add_argument("--workspace", default=None, help="Workspace dir for coding tools.")
    p.add_argument("--compact-system-prompt", action=argparse.BooleanOptionalAction, default=None,
                   help="Shorter system prompt (helps small-context servers).")
    return p.parse_args()


def main() -> None:
    global AUTO_YES, PROFILES, BASE_ARGS
    args = parse_args()
    BASE_ARGS = args
    AUTO_YES = args.yes
    PROFILES = agent.load_profiles()

    # Initialize through the same path the UI uses, so there's one config code
    # path. resolve_config reads args.verbose; the web UI always captures the
    # trace (the browser's "show trace" checkbox controls display, not capture).
    args.verbose = True
    apply_config(profile=args.profile, coding=args.coding,
                 allow_exec=args.allow_exec, auto_yes=args.yes)

    url = f"http://{args.host}:{args.port}"
    print(f"agentApp (Flask) serving on {url}")
    print(f"  model   : {CONFIG.model} @ {CONFIG.base_url}")
    mode = "read-only"
    if CONFIG.coding or CONFIG.allow_exec:
        mode = "coding" + (f" + exec ({'auto-yes' if AUTO_YES else 'auto-decline'})"
                           if CONFIG.allow_exec else "")
    print(f"  mode    : {mode}")
    print(f"  profiles: {', '.join(PROFILES) or '(none)'}  -- switch live in the UI (settings panel)")
    print("  open the URL in a browser; Ctrl+C to stop.")
    # threaded=True so a slow model turn doesn't block /api/info etc.; the shared
    # agent state is already guarded by _lock. debug/reloader OFF -- the reloader
    # would spawn a second process and re-run apply_config.
    app.run(host=args.host, port=args.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
