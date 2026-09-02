#!/usr/bin/env python3
"""Console diagnostica locale e leggera per Peppe."""

from __future__ import annotations

import json
import re
import secrets
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = "127.0.0.1"
PORT = 8091
TOKEN = secrets.token_urlsafe(24)
UNITS = {
    "llm": "local-ai-llama.service",
    "web": "local-ai-assistant.service",
    "voice": "local-ai-peppe.service",
    "audio": "local-ai-audio.service",
}
LOG_UNITS = {**UNITS, "console": "local-ai-control.service"}
LLAMA_URL = "http://127.0.0.1:8080"
ASSISTANT_URL = "http://127.0.0.1:8090"
_cache: dict[str, tuple[float, object]] = {}
_cache_lock = threading.Lock()
_cpu_previous: tuple[int, int] | None = None


def run(command: list[str], timeout: float = 4) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(command, 1, str(exc))


def cached(name: str, seconds: float, loader):
    now = time.monotonic()
    with _cache_lock:
        item = _cache.get(name)
        if item and now - item[0] < seconds:
            return item[1]
    value = loader()
    with _cache_lock:
        _cache[name] = (now, value)
    return value


def systemctl(*args: str) -> subprocess.CompletedProcess[str]:
    return run(["systemctl", "--user", *args], timeout=30)


def integer(value: str | None) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def unit_states() -> dict[str, dict]:
    """Una sola interrogazione systemd per tutti i componenti."""
    command = ["systemctl", "--user", "show", *UNITS.values(), "--no-pager",
               "--property=Id,ActiveState,MainPID,MemoryCurrent,ExecStart"]
    output = run(command).stdout
    by_unit: dict[str, dict] = {}
    for block in output.strip().split("\n\n"):
        values = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        unit = values.get("Id", "")
        if unit:
            by_unit[unit] = values
    result = {}
    for name, unit in UNITS.items():
        values = by_unit.get(unit, {})
        result[name] = {
            "active": values.get("ActiveState") == "active",
            "pid": integer(values.get("MainPID")),
            "memory_bytes": integer(values.get("MemoryCurrent")),
            "exec": values.get("ExecStart", ""),
        }
    return result


def meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            values[key] = int(value.strip().split()[0]) * 1024
    except (OSError, ValueError):
        pass
    return values


def cpu_percent() -> float:
    global _cpu_previous
    try:
        fields = [int(value) for value in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
    except (OSError, ValueError, IndexError):
        return 0.0
    total, idle = sum(fields), fields[3] + (fields[4] if len(fields) > 4 else 0)
    previous, _cpu_previous = _cpu_previous, (total, idle)
    if previous is None or total <= previous[0]:
        return 0.0
    return round(100 * (1 - (idle - previous[1]) / (total - previous[0])), 1)


def gpu_info() -> dict:
    result = run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                  "--format=csv,noheader,nounits"], timeout=3)
    if result.returncode:
        return {"available": False}
    try:
        name, used, total, usage, temperature = [part.strip() for part in result.stdout.splitlines()[0].split(",")]
        return {"available": True, "name": name, "used_mib": int(used),
                "total_mib": int(total), "percent": int(usage),
                "temperature_c": int(temperature)}
    except (ValueError, IndexError):
        return {"available": False}


def fetch_json(path: str, timeout: float = 1.5) -> dict:
    try:
        with urllib.request.urlopen(LLAMA_URL + path, timeout=timeout) as response:
            return json.load(response)
    except (OSError, ValueError):
        return {}


def fetch_metrics() -> dict[str, float]:
    try:
        with urllib.request.urlopen(LLAMA_URL + "/metrics", timeout=1.5) as response:
            text = response.read(256_000).decode(errors="replace")
    except OSError:
        return {}
    metrics = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or " " not in line:
            continue
        key, raw = line.rsplit(" ", 1)
        try:
            metrics[key.split("{")[0]] = float(raw)
        except ValueError:
            continue
    return metrics


def metric(metrics: dict[str, float], *suffixes: str) -> float | None:
    for key, value in metrics.items():
        if any(key.endswith(suffix) for suffix in suffixes):
            return value
    return None


def model_info(states: dict[str, dict]) -> dict:
    exec_line = states.get("llm", {}).get("exec", "")
    model_match = re.search(r"--model[= ]+([^ ;}]+)", exec_line)
    alias_match = re.search(r"--alias[= ]+([^ ;}]+)", exec_line)
    context_match = re.search(r"--ctx-size[= ]+(\d+)", exec_line)
    model_path = model_match.group(1) if model_match else ""
    props = cached("props", 30, lambda: fetch_json("/props"))

    def version_loader() -> str:
        binary = str(Path.home() / ".local/share/local-ai/llama/llama-server")
        result = run([binary, "--version"], timeout=3)
        return next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")[:180]

    return {
        "file": Path(model_path).name if model_path else "non rilevato",
        "alias": alias_match.group(1) if alias_match else props.get("model_alias", ""),
        "context": int(context_match.group(1)) if context_match else None,
        "slots": props.get("total_slots"),
        "version": cached("llama_version", 3600, version_loader),
    }


def overview() -> dict:
    states = cached("units", 4, unit_states)
    memory = meminfo()
    total = memory.get("MemTotal", 0)
    available = memory.get("MemAvailable", 0)
    swap_total = memory.get("SwapTotal", 0)
    swap_free = memory.get("SwapFree", 0)
    disk = shutil.disk_usage("/")
    metrics = cached("metrics", 10, fetch_metrics) if states["llm"]["active"] else {}
    return {
        "timestamp": time.strftime("%H:%M:%S"),
        "services": {name: {key: value for key, value in data.items() if key != "exec"}
                     for name, data in states.items()},
        "model": model_info(states),
        "resources": {
            "cpu_percent": cpu_percent(), "ram_total": total,
            "ram_used": max(0, total - available), "ram_available": available,
            "swap_total": swap_total, "swap_used": max(0, swap_total - swap_free),
            "disk_total": disk.total, "disk_used": disk.used,
            "gpu": cached("gpu", 15, gpu_info),
        },
        "llm": {
            "prompt_tokens_total": metric(metrics, "prompt_tokens_total", "prompt_tokens_total_count"),
            "generated_tokens_total": metric(metrics, "tokens_predicted_total", "predicted_tokens_total"),
            "requests_processing": metric(metrics, "requests_processing"),
        },
    }


def journal(unit_key: str, lines: int) -> list[str]:
    unit = LOG_UNITS.get(unit_key)
    if not unit:
        return []
    lines = max(10, min(lines, 200))
    result = run(["journalctl", "--user", "-u", unit, "-n", str(lines),
                  "--no-pager", "--output=short-iso"], timeout=4)
    return result.stdout.splitlines()[-lines:]


def speech_events() -> list[dict[str, str]]:
    events = []
    for line in journal("voice", 180):
        if not any(marker in line for marker in ("trascrizione", "wake phrase", "risposta:",
                                                  "comando scartato", "sessione chiusa")):
            continue
        message = line.split(": ", 1)[-1]
        kind = "parola"
        if "risposta:" in message:
            kind = "risposta"
        elif "scartato" in message:
            kind = "scartato"
        elif "wake phrase" in message:
            kind = "attivazione"
        events.append({"time": line[:19], "kind": kind, "text": message[-700:]})
    return events[-24:][::-1]


INDEX = r'''<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Console Peppe</title>
<style>
:root{color-scheme:dark;--bg:#09111f;--card:#131f32;--line:#2b3b53;--muted:#9eacc2;--green:#43db88;--red:#fb7185;--blue:#66a8ff}*{box-sizing:border-box}body{font:16px system-ui,sans-serif;margin:auto;max-width:1100px;padding:22px;background:var(--bg);color:#eef4ff}h1{margin:0;font-size:30px}h2{font-size:18px;margin:0 0 14px}.muted,small{color:var(--muted)}.top{display:flex;justify-content:space-between;gap:15px;align-items:center;flex-wrap:wrap}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-top:16px}.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:17px;min-width:0}.state{font-weight:750}.on{color:var(--green)}.off{color:var(--red)}button,a.button{font:inherit;font-weight:650;border:0;border-radius:10px;padding:9px 13px;margin:6px 5px 0 0;text-decoration:none;cursor:pointer;display:inline-block}.start{background:var(--green);color:#052e16}.stop{background:var(--red);color:#4c0519}.secondary{background:var(--blue);color:#082f49}.ghost{background:#27364d;color:#e8eef9}.row{display:flex;justify-content:space-between;gap:10px;margin:8px 0}.value{text-align:right;font-variant-numeric:tabular-nums}.bar{height:8px;background:#26344a;border-radius:8px;overflow:hidden;margin:3px 0 10px}.bar i{display:block;height:100%;background:var(--blue);width:0}.services{display:grid;grid-template-columns:1fr 1fr;gap:8px}.service{padding:8px;border:1px solid var(--line);border-radius:9px}pre{background:#070d17;border:1px solid var(--line);border-radius:10px;padding:12px;height:310px;overflow:auto;white-space:pre-wrap;word-break:break-word;font:12px ui-monospace,monospace}.wide{grid-column:1/-1}.event{border-top:1px solid var(--line);padding:9px 0}.badge{font-size:11px;border:1px solid var(--line);border-radius:12px;padding:2px 7px;color:#bcd0ed}.model{word-break:break-all}select,textarea{background:#27364d;color:white;border:1px solid var(--line);padding:8px;border-radius:9px}.chat{height:300px;overflow:auto;background:#070d17;border:1px solid var(--line);border-radius:12px;padding:12px}.bubble{max-width:86%;margin:8px 0;padding:9px 12px;border-radius:12px;white-space:pre-wrap;word-break:break-word}.user{background:#1d4ed8;margin-left:auto}.assistant{background:#27364d;margin-right:auto}.composer{display:grid;grid-template-columns:1fr auto;gap:10px;margin-top:10px;align-items:end}.composer textarea{resize:vertical;min-height:68px;width:100%;font:inherit}.chat-actions{min-width:190px}.busy{opacity:.65;pointer-events:none}@media(max-width:600px){body{padding:14px}.grid{grid-template-columns:1fr}.composer{grid-template-columns:1fr}.chat-actions{min-width:0}}
</style></head><body><div class="top"><div><h1>Console Peppe</h1><small>Assistente e diagnostica locale · aggiornato <span id="updated">…</span></small></div><span class="badge">Tutto in una pagina</span></div>
<div class="grid"><section class="card wide"><div class="top"><div><h2>Parla con Peppe</h2><small>Chat locale · streaming · modalità automatica</small></div><span id="chat-status" class="muted">Pronto</span></div><div id="chat" class="chat"><div class="bubble assistant">Ciao! Scrivimi una richiesta oppure usa il microfono.</div></div><div class="composer"><textarea id="chat-input" placeholder="Scrivi qui…"></textarea><div id="chat-actions" class="chat-actions"><button id="chat-send" class="start">Invia</button><button id="chat-mic" class="secondary">🎙 Parla</button><button id="chat-voice" class="ghost">🔇 Voce: no</button></div></div></section>
<section class="card"><h2>Controlli</h2><div>Sistema AI: <span id="system" class="state">…</span></div><button class="start" onclick="act('/api/system/on')">Accendi</button><button class="stop" onclick="act('/api/system/off')">Spegni</button><div style="margin-top:12px">Ascolto: <span id="voice" class="state">…</span></div><button class="start" onclick="act('/api/voice/on')">Attiva</button><button class="stop" onclick="act('/api/voice/off')">Disattiva</button><p id="message" class="muted"></p></section>
<section class="card"><h2>Componenti</h2><div id="services" class="services"></div></section>
<section class="card"><h2>Modello</h2><div class="row"><span>File</span><span id="model-file" class="value model">…</span></div><div class="row"><span>Alias</span><span id="model-alias" class="value">…</span></div><div class="row"><span>Contesto</span><span id="model-context" class="value">…</span></div><div class="row"><span>Versione motore</span><span id="model-version" class="value model">…</span></div><div class="row"><span>Token prompt totali</span><span id="prompt-tokens" class="value">—</span></div><div class="row"><span>Token generati totali</span><span id="generated-tokens" class="value">—</span></div></section>
<section class="card"><h2>Risorse</h2><div id="resources"></div><small>Aggiornamento ogni 10 s solo con pagina visibile; GPU ogni 15 s.</small></section>
<section class="card wide"><div class="top"><h2>Parole e risposte riconosciute</h2><button class="ghost" onclick="loadSpeech()">Aggiorna</button></div><div id="speech"><span class="muted">Premi Aggiorna per caricare la cronologia.</span></div></section>
<section class="card wide"><div class="top"><h2>Log recenti</h2><div><select id="log-unit"><option value="voice">Voce</option><option value="llm">LLM</option><option value="web">Assistente</option><option value="audio">Audio</option><option value="console">Console</option></select><button class="ghost" onclick="loadLogs()">Carica log</button></div></div><pre id="logs">I log vengono caricati solo su richiesta per non consumare risorse.</pre></section></div>
<script>const token='__TOKEN__',labels={llm:'LLM',web:'Interfaccia',voice:'Ascolto',audio:'Audio'},$=id=>document.getElementById(id);let chatHistory=[],chatVoice=false,chatRunning=false,recorder,chunks=[];function fmt(n){if(n==null)return'—';let u=['B','KiB','MiB','GiB'],i=0;while(n>=1024&&i<3){n/=1024;i++}return n.toFixed(i>1?1:0)+' '+u[i]}function pct(a,b){return b?Math.min(100,Math.round(a/b*100)):0}function state(id,on){let e=$(id);e.textContent=on?'ATTIVO':'SPENTO';e.className='state '+(on?'on':'off')}function bar(name,used,total,extra=''){let p=pct(used,total);return `<div class="row"><span>${name}</span><span class="value">${fmt(used)} / ${fmt(total)} ${extra}</span></div><div class="bar"><i style="width:${p}%"></i></div>`}
async function refresh(){if(document.hidden)return;try{let s=await(await fetch('/api/overview')).json();$('updated').textContent=s.timestamp;state('system',s.services.llm.active&&s.services.web.active);state('voice',s.services.voice.active);$('services').innerHTML=Object.entries(s.services).map(([k,v])=>`<div class="service"><span class="state ${v.active?'on':'off'}">●</span> ${labels[k]}<br><small>${v.pid?'PID '+v.pid+' · '+fmt(v.memory_bytes):(v.active?'attivo · nessun processo residente':'spento')}</small></div>`).join('');$('model-file').textContent=s.model.file;$('model-alias').textContent=s.model.alias||'—';$('model-context').textContent=s.model.context?s.model.context.toLocaleString('it-IT')+' token':'—';$('model-version').textContent=s.model.version||'—';$('prompt-tokens').textContent=s.llm.prompt_tokens_total??'—';$('generated-tokens').textContent=s.llm.generated_tokens_total??'—';let r=s.resources,g=r.gpu,html=`<div class="row"><span>CPU</span><span>${r.cpu_percent}%</span></div>`+bar('RAM',r.ram_used,r.ram_total,'· liberi '+fmt(r.ram_available))+bar('Swap',r.swap_used,r.swap_total)+bar('Disco',r.disk_used,r.disk_total);if(g.available)html+=bar('VRAM',g.used_mib*1048576,g.total_mib*1048576,`· GPU ${g.percent}% · ${g.temperature_c}°C`);$('resources').innerHTML=html}catch(e){$('updated').textContent='non raggiungibile'}}
function chatBubble(kind,text){let d=document.createElement('div');d.className='bubble '+kind;d.textContent=text;$('chat').appendChild(d);$('chat').scrollTop=$('chat').scrollHeight;return d}function chatBusy(on,text=''){let a=$('chat-actions');a.classList.toggle('busy',on);$('chat-status').textContent=text||(on?'Attendi…':'Pronto')}async function readEvents(payload,onEvent){let r=await fetch('/api/assistant/chat',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':token},body:JSON.stringify(payload)});if(!r.ok){let j=await r.json().catch(()=>({}));throw Error(j.error||'Assistente non raggiungibile')}let reader=r.body.getReader(),decoder=new TextDecoder(),buffer='';while(true){let x=await reader.read();buffer+=decoder.decode(x.value||new Uint8Array(),{stream:!x.done});let lines=buffer.split('\n');buffer=lines.pop();for(let line of lines){if(line.trim())onEvent(JSON.parse(line))}if(x.done)break}if(buffer.trim())onEvent(JSON.parse(buffer))}async function sendChat(){let input=$('chat-input'),text=input.value.trim();if(!text||chatRunning)return;chatRunning=true;input.value='';chatBubble('user',text);let prior=[...chatHistory];chatHistory.push({role:'user',content:text});let bubble=chatBubble('assistant','Sto pensando…'),gotText=false,done=null,finalStatus='Pronto';chatBusy(true,'Peppe sta rispondendo');try{await readEvents({message:text,history:prior,stream:true},e=>{if(e.type==='meta')chatBusy(true,'Modalità '+e.profile_label.toLowerCase());else if(e.type==='delta'){if(!gotText){bubble.textContent='';gotText=true}bubble.textContent+=e.text;$('chat').scrollTop=$('chat').scrollHeight}else if(e.type==='done')done=e;else if(e.type==='error')throw Error(e.error)});done=done||{};let answer=done.answer||bubble.textContent||done.error||'Nessuna risposta';bubble.textContent=answer;chatHistory.push({role:'assistant',content:answer});finalStatus=(done.profile_label||'Risposta')+' · '+((done.elapsed_ms||0)/1000).toFixed(1)+' s';if(done.open_url)window.open(done.open_url,'_blank','noopener');if(chatVoice&&done.answer)await speakChat(answer)}catch(e){bubble.textContent='Errore: '+e.message;finalStatus='Assistente non raggiungibile'}finally{chatRunning=false;chatBusy(false,finalStatus)}}async function speakChat(text){let r=await fetch('/api/assistant/speak',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':token},body:JSON.stringify({text})});if(r.ok)new Audio(URL.createObjectURL(await r.blob())).play()}function msg(t){$('message').textContent=t}async function act(path){msg('Operazione in corso…');let r=await fetch(path,{method:'POST',headers:{'X-Control-Token':token}}),j=await r.json();msg(j.ok?'Operazione completata':'Errore: '+(j.error||'sconosciuto'));setTimeout(refresh,700)}async function loadLogs(){let u=$('log-unit').value;$('logs').textContent='Caricamento…';let j=await(await fetch('/api/logs?unit='+encodeURIComponent(u)+'&lines=100')).json();$('logs').textContent=(j.lines||[]).join('\n')||'Nessun log disponibile'}async function loadSpeech(){let j=await(await fetch('/api/speech')).json();$('speech').innerHTML='';if(!j.events.length){$('speech').textContent='Nessun evento recente';return}j.events.forEach(e=>{let d=document.createElement('div');d.className='event';let b=document.createElement('span');b.className='badge';b.textContent=e.kind;let t=document.createElement('small');t.textContent=' '+e.time;let p=document.createElement('div');p.textContent=e.text;d.append(b,t,p);$('speech').appendChild(d)})}$('chat-send').onclick=sendChat;$('chat-input').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat()}};$('chat-voice').onclick=e=>{chatVoice=!chatVoice;e.target.textContent=(chatVoice?'🔊':'🔇')+' Voce: '+(chatVoice?'sì':'no')};$('chat-mic').onclick=async e=>{if(recorder&&recorder.state==='recording'){recorder.stop();e.target.textContent='🎙 Parla';return}try{let stream=await navigator.mediaDevices.getUserMedia({audio:true});chunks=[];recorder=new MediaRecorder(stream);recorder.ondataavailable=x=>chunks.push(x.data);recorder.onstop=async()=>{stream.getTracks().forEach(x=>x.stop());chatBusy(true,'Trascrizione…');let r=await fetch('/api/assistant/transcribe',{method:'POST',headers:{'Content-Type':recorder.mimeType,'X-Control-Token':token},body:new Blob(chunks,{type:recorder.mimeType})}),j=await r.json();$('chat-input').value=j.text||'';chatBusy(false);if(j.text)sendChat()};recorder.start();e.target.textContent='⏹ Ferma'}catch(e){$('chat-status').textContent='Microfono non disponibile'}};refresh();setInterval(refresh,10000);document.addEventListener('visibilitychange',refresh);</script></body></html>'''.replace("__TOKEN__", TOKEN)


class Handler(BaseHTTPRequestHandler):
    def send_data(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; media-src 'self' blob:")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def json(self, data: dict, code: int = 200) -> None:
        self.send_data(code, json.dumps(data, ensure_ascii=False).encode(),
                       "application/json; charset=utf-8")

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/":
            self.send_data(200, INDEX.encode(), "text/html; charset=utf-8")
        elif parsed.path in ("/api/status", "/api/overview"):
            data = overview()
            self.json(data if parsed.path.endswith("overview") else
                      {name: item["active"] for name, item in data["services"].items()})
        elif parsed.path == "/api/logs":
            unit = query.get("unit", ["voice"])[0]
            try:
                lines = int(query.get("lines", ["100"])[0])
            except ValueError:
                lines = 100
            if unit not in LOG_UNITS:
                return self.json({"error": "componente non valido"}, 400)
            self.json({"unit": unit, "lines": journal(unit, lines)})
        elif parsed.path == "/api/speech":
            self.json({"events": speech_events()})
        else:
            self.json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        if not secrets.compare_digest(self.headers.get("X-Control-Token", ""), TOKEN):
            return self.json({"ok": False, "error": "richiesta non autorizzata"}, 403)
        if self.path.startswith("/api/assistant/"):
            return self.proxy_assistant()
        actions = {
            "/api/system/on": ("start", UNITS["audio"], UNITS["llm"], UNITS["web"], UNITS["voice"]),
            "/api/system/off": ("stop", UNITS["voice"], UNITS["web"], UNITS["llm"]),
            "/api/voice/on": ("start", UNITS["audio"], UNITS["web"], UNITS["voice"]),
            "/api/voice/off": ("stop", UNITS["voice"]),
        }
        action = actions.get(self.path)
        if not action:
            return self.json({"ok": False, "error": "not found"}, 404)
        result = systemctl(*action)
        with _cache_lock:
            _cache.pop("units", None)
        self.json({"ok": result.returncode == 0,
                   "error": result.stdout[-600:] if result.returncode else ""},
                  200 if result.returncode == 0 else 500)

    def proxy_assistant(self) -> None:
        routes = {
            "/api/assistant/chat": "/api/chat",
            "/api/assistant/speak": "/api/speak",
            "/api/assistant/transcribe": "/api/transcribe",
        }
        target = routes.get(self.path)
        if not target:
            return self.json({"error": "not found"}, 404)
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 25_000_000)
        except ValueError:
            length = 0
        body = self.rfile.read(length)
        request = urllib.request.Request(
            ASSISTANT_URL + target, data=body, method="POST",
            headers={"Content-Type": self.headers.get("Content-Type", "application/octet-stream")},
        )
        streaming_started = False
        try:
            with urllib.request.urlopen(request, timeout=190) as response:
                content_type = response.headers.get("Content-Type", "application/octet-stream")
                if content_type.lower().startswith("application/x-ndjson"):
                    streaming_started = True
                    self.send_response(response.status)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Cache-Control", "no-store, no-transform")
                    self.send_header("X-Accel-Buffering", "no")
                    self.send_header("Connection", "close")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.close_connection = True
                    for line in response:
                        self.wfile.write(line)
                        self.wfile.flush()
                    return
                content = response.read(25_000_000)
                self.send_data(response.status, content, content_type)
        except urllib.error.HTTPError as exc:
            self.send_data(exc.code, exc.read(1_000_000),
                           exc.headers.get("Content-Type", "application/json; charset=utf-8"))
        except (BrokenPipeError, ConnectionResetError):
            return
        except OSError as exc:
            if not streaming_started:
                self.json({"error": f"assistente non raggiungibile: {exc}"}, 502)

    def log_message(self, _format: str, *_args) -> None:
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    server.serve_forever()
