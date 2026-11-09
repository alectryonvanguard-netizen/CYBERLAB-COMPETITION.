"""
.engine admin server: JSON API + full web dashboard.

Opens at http://<this-machine>:9090 and needs the access key. It is the
complete control surface (register, edit, start/stop, logs, GPU, metrics) and
is also what the phone companion talks to.
"""
import os
import json
import time
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from engine_infra import read_auth, check_auth, tail_file, MAX_FAILS, LOCK_SECONDS

ADMIN_PORTS = (9090, 9091, 9092)
TOKEN_TTL = 12 * 3600
MAX_PAGE_BYTES = 2_000_000


class AdminServer:
    def __init__(self, core):
        self.core = core
        self.tokens = {}
        self.fails = {}
        self.httpd = None
        self.lock = threading.Lock()

    def start(self):
        handler = self._make_handler()
        for port in ADMIN_PORTS:
            try:
                self.httpd = ThreadingHTTPServer(("0.0.0.0", port), handler)
                self.core.admin_port = port
                break
            except OSError:
                continue
        if self.httpd is None:
            self.core.log("Dashboard could not bind a port.")
            return
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.core.log(f"Dashboard on port {self.core.admin_port}: "
                      f"http://localhost:{self.core.admin_port}")

    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass

    # ---------------------------------------------------------- auth
    def login(self, ip, password):
        now = time.time()
        with self.lock:
            count, locked_until = self.fails.get(ip, (0, 0))
            if now < locked_until:
                return 429, {"error": f"Too many attempts. Try again in {int(locked_until - now) + 1}s."}
            auth = read_auth(self.core.auth_path())
            if not auth:
                return 503, {"error": "No access key yet. Create it in the app, or run: "
                                      "python engine_core.py setpassword"}
            if check_auth(auth, password or ""):
                self.fails.pop(ip, None)
                self.tokens = {t: e for t, e in self.tokens.items() if e > now}
                token = secrets.token_urlsafe(24)
                self.tokens[token] = now + TOKEN_TTL
                return 200, {"token": token}
            count += 1
            if count >= MAX_FAILS:
                self.fails[ip] = (0, now + LOCK_SECONDS)
            else:
                self.fails[ip] = (count, 0)
            return 401, {"error": "Wrong access key."}

    def valid_token(self, token):
        with self.lock:
            return self.tokens.get(token, 0) > time.time()

    # ---------------------------------------------------------- handler
    def _make_handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _send(self, code, body, ctype):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, code, obj):
                self._send(code, json.dumps(obj).encode(), "application/json")

            def _authed(self):
                h = self.headers.get("Authorization", "")
                return h.startswith("Bearer ") and server.valid_token(h[7:])

            def _read_json(self):
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_PAGE_BYTES + 10000:
                    raise ValueError("Request too large.")
                raw = self.rfile.read(length) if length else b"{}"
                return json.loads(raw or b"{}")

            def do_GET(self):
                url = urlparse(self.path)
                if url.path in ("/", "/index.html"):
                    self._send(200, DASHBOARD_HTML.encode("utf-8"), "text/html; charset=utf-8")
                    return
                if not url.path.startswith("/api/"):
                    self._json(404, {"error": "Not found."})
                    return
                if not self._authed():
                    self._json(401, {"error": "Not signed in."})
                    return
                q = parse_qs(url.query)
                core = server.core
                try:
                    if url.path == "/api/state":
                        self._json(200, core.snapshot())
                    elif url.path == "/api/logs":
                        name = (q.get("name") or ["engine"])[0]
                        lines = min(int((q.get("lines") or ["200"])[0]), 1000)
                        self._json(200, {"text": self._logs(name, lines)})
                    elif url.path == "/api/site":
                        name = (q.get("name") or [""])[0]
                        if core.registry.get(name, {}).get("type") != "site":
                            self._json(404, {"error": "Not a site."})
                            return
                        try:
                            with open(core.site_index_path(name), "r", encoding="utf-8") as f:
                                content = f.read()
                        except OSError:
                            content = ""
                        self._json(200, {"content": content})
                    else:
                        self._json(404, {"error": "Not found."})
                except Exception as e:
                    self._json(500, {"error": str(e)})

            def _logs(self, name, lines):
                core = server.core
                if name == "engine":
                    return "\n".join(core.log_ring[-lines:])
                if name == "access":
                    return tail_file(os.path.join(core.data_dir(), "logs", "access.log"), lines)
                if name in core.registry and core.procs:
                    return tail_file(core.procs.log_path(name), lines)
                return ""

            def do_POST(self):
                url = urlparse(self.path)
                core = server.core
                try:
                    body = self._read_json()
                except Exception:
                    self._json(400, {"error": "Bad request."})
                    return
                if url.path == "/api/login":
                    code, obj = server.login(self.client_address[0], body.get("password"))
                    self._json(code, obj)
                    return
                if not self._authed():
                    self._json(401, {"error": "Not signed in."})
                    return
                try:
                    if url.path == "/api/register":
                        ok, msg = core.register(
                            body.get("name"), body.get("target", ""), body.get("command", ""),
                            body.get("cwd", ""), body.get("autostart", True))
                        self._json(200 if ok else 400, {"ok": ok, "message": msg, "error": None if ok else msg})
                    elif url.path == "/api/unregister":
                        core.drop_node(str(body.get("name", "")))
                        self._json(200, {"ok": True})
                    elif url.path in ("/api/app/start", "/api/app/stop", "/api/app/restart"):
                        name = str(body.get("name", ""))
                        if not core.procs or not core.registry.get(name, {}).get("command"):
                            self._json(400, {"error": "This entry has no start command."})
                            return
                        action = url.path.rsplit("/", 1)[1]
                        ok, msg = getattr(core.procs, action)(name)
                        self._json(200 if ok else 400, {"ok": ok, "message": msg, "error": None if ok else msg})
                    elif url.path == "/api/site":
                        name = str(body.get("name", ""))
                        content = str(body.get("content", ""))
                        if core.registry.get(name, {}).get("type") != "site":
                            self._json(404, {"error": "Not a site."})
                            return
                        if len(content.encode("utf-8")) > MAX_PAGE_BYTES:
                            self._json(400, {"error": "Page is too large (2 MB max)."})
                            return
                        path = core.site_index_path(name)
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(content)
                        core.log(f"Saved {name}.engine")
                        self._json(200, {"ok": True})
                    else:
                        self._json(404, {"error": "Not found."})
                except Exception as e:
                    self._json(500, {"error": str(e)})

        return Handler


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>.engine</title>
<style>
  :root { --bg:#05080f; --panel:#0a1220; --line:rgba(0,240,255,.28); --acc:#00f0ff;
          --good:#00ff9c; --warn:#ffd60a; --bad:#ff4d6d; --txt:#d6f6ff; --mut:#5f7a94; }
  * { box-sizing:border-box; }
  body { margin:0; color:var(--txt); background-color:var(--bg);
         background-image:linear-gradient(rgba(0,240,255,.045) 1px, transparent 1px),
                          linear-gradient(90deg, rgba(0,240,255,.045) 1px, transparent 1px);
         background-size:36px 36px; font-family:ui-monospace,Menlo,Consolas,monospace; }
  .wrap { max-width:1100px; margin:0 auto; padding:20px 16px 60px; }
  h1 { margin:0; color:var(--acc); font-size:1.7rem; }
  h2 { margin:0 0 12px; font-size:.8rem; color:var(--mut); letter-spacing:.12em; font-weight:normal; }
  .top { display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:18px; }
  .top .sp { flex:1; }
  .chip { padding:4px 10px; border:1px solid var(--line); border-radius:6px; font-size:.8rem; }
  .good { color:var(--good); } .warn { color:var(--warn); } .bad { color:var(--bad); } .mut { color:var(--mut); }
  .panel, .card { background:var(--panel); border:1px solid var(--line); border-radius:10px; }
  .panel { padding:16px; margin-bottom:16px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin-bottom:16px; }
  .card { padding:12px 14px; }
  .card .lbl { font-size:.7rem; color:var(--mut); letter-spacing:.1em; }
  .card .val { font-size:1.5rem; color:var(--acc); margin:4px 0; }
  .card .sub { font-size:.72rem; color:var(--mut); }
  .track { height:6px; background:#10202e; border-radius:3px; margin-top:6px; overflow:hidden; }
  .fill { height:100%; background:var(--good); } .fill.mid { background:var(--warn); } .fill.hi { background:var(--bad); }
  input, select, textarea { width:100%; background:#05080f; color:var(--txt); border:1px solid var(--line);
         border-radius:6px; padding:10px; font:inherit; }
  textarea { min-height:55vh; resize:vertical; }
  button { background:var(--acc); color:#05080f; border:0; border-radius:6px; padding:9px 14px;
           font:inherit; cursor:pointer; }
  button.alt { background:transparent; color:var(--acc); border:1px solid var(--line); padding:6px 10px; font-size:.8rem; }
  button.danger { background:transparent; color:var(--bad); border:1px solid rgba(255,77,109,.5); padding:6px 10px; font-size:.8rem; }
  .form { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:10px; align-items:end; }
  label { font-size:.7rem; color:var(--mut); display:block; margin-bottom:4px; }
  table { width:100%; border-collapse:collapse; font-size:.85rem; }
  th { text-align:left; font-weight:normal; color:var(--mut); font-size:.7rem; letter-spacing:.1em; padding:6px; }
  td { padding:8px 6px; border-top:1px solid rgba(0,240,255,.1); vertical-align:middle; }
  td.act { white-space:nowrap; text-align:right; } td.act > * { margin-left:4px; }
  .scroll { overflow-x:auto; }
  a { color:var(--acc); }
  pre { margin:0; max-height:300px; overflow:auto; font-size:.75rem; color:var(--mut); white-space:pre-wrap; }
  #login { min-height:100vh; display:grid; place-items:center; padding:16px; }
  #login .panel { width:100%; max-width:380px; }
  #msg { margin-top:8px; font-size:.8rem; min-height:1em; }
  dialog { background:var(--panel); color:var(--txt); border:1px solid var(--line); border-radius:10px;
           width:min(900px,95vw); padding:16px; }
  dialog::backdrop { background:rgba(0,0,0,.7); }
</style>
</head>
<body>
<div id="login">
  <div class="panel">
    <h1>&gt; .engine</h1>
    <p class="mut" style="font-size:.8rem">SECURE TERMINAL // AUTH REQUIRED</p>
    <label>ACCESS KEY</label>
    <input id="pw" type="password" autocomplete="current-password">
    <div style="margin-top:12px"><button id="loginBtn" style="width:100%">[ UNLOCK ]</button></div>
    <div id="loginErr" class="bad" style="margin-top:10px;font-size:.8rem"></div>
  </div>
</div>

<div id="app" class="wrap" hidden>
  <div class="top">
    <h1>&gt; .engine</h1>
    <span id="status" class="chip good">[ ONLINE ]</span>
    <span id="ports" class="mut" style="font-size:.78rem"></span>
    <span class="sp"></span>
    <span id="uptime" class="mut" style="font-size:.78rem"></span>
    <button class="alt" id="logout">Lock</button>
  </div>

  <h2>// SYSTEM</h2>
  <div class="grid" id="meters"></div>

  <h2>// TRAFFIC</h2>
  <div class="grid" id="totals"></div>

  <div class="panel">
    <h2>// REGISTER A SITE OR APP</h2>
    <div class="form">
      <div><label>NAME</label><input id="rName" placeholder="shop"></div>
      <div><label>TARGET (blank = new site, port = app, folder = site)</label><input id="rTarget" placeholder="8001  or  /var/www/shop"></div>
      <div><label>START COMMAND (optional, engine runs and restarts it)</label><input id="rCmd" placeholder="python app.py"></div>
      <div><label>WORKING FOLDER (optional)</label><input id="rCwd" placeholder="/home/me/app"></div>
      <div><button id="rBtn" style="width:100%">[ REGISTER ]</button></div>
    </div>
    <div id="msg"></div>
  </div>

  <div class="panel">
    <h2>// SITES AND APPS</h2>
    <div class="scroll"><table>
      <thead><tr><th>NAME</th><th>TYPE</th><th>STATUS</th><th>REQUESTS</th><th>TRAFFIC</th><th></th></tr></thead>
      <tbody id="rows"></tbody>
    </table></div>
  </div>

  <div class="panel">
    <h2>// LOGS</h2>
    <select id="logSel" style="max-width:260px;margin-bottom:10px"></select>
    <pre id="logBox"></pre>
  </div>
</div>

<dialog id="editor">
  <h2 id="edTitle">// EDIT index.html</h2>
  <textarea id="edText" spellcheck="false"></textarea>
  <div style="margin-top:10px;display:flex;gap:8px;align-items:center">
    <button id="edSave">[ SAVE ]</button><button class="alt" id="edClose">Close</button>
    <span id="edMsg" class="good" style="font-size:.8rem"></span>
  </div>
</dialog>

<script>
const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
let token = sessionStorage.getItem("engine_token") || "";
let state = null, logName = "engine", editing = "", timer = null;

async function api(path, body) {
  const opt = { headers: { "Content-Type": "application/json" } };
  if (token) opt.headers.Authorization = "Bearer " + token;
  if (body !== undefined) { opt.method = "POST"; opt.body = JSON.stringify(body); }
  const r = await fetch(path, opt);
  let data = {}; try { data = await r.json(); } catch (e) {}
  if (r.status === 401 && path !== "/api/login") { lock(); throw new Error("Session ended."); }
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

function fmtBytes(n) {
  if (n < 1024) return n + " B";
  if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
  if (n < 1073741824) return (n / 1048576).toFixed(1) + " MB";
  return (n / 1073741824).toFixed(2) + " GB";
}
function fmtUp(s) {
  const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
  return (d ? d + "d " : "") + h + "h " + m + "m";
}
function card(label, value, sub, pct) {
  const c = el("div", "card");
  c.append(el("div", "lbl", label), el("div", "val", value));
  if (pct != null) {
    const t = el("div", "track"), f = el("div", "fill" + (pct > 85 ? " hi" : pct > 60 ? " mid" : ""));
    f.style.width = Math.min(100, pct) + "%"; t.append(f); c.append(t);
  }
  if (sub) c.append(el("div", "sub", sub));
  return c;
}
function pctText(p) { return p == null ? "n/a" : p.toFixed(0) + "%"; }

function render() {
  const s = state, m = s.metrics;
  $("#ports").textContent = "proxy:" + (s.proxy_port || "-") + "  dns:" + (s.dns_port || "-") + "  dashboard:" + (s.admin_port || "-") + "  ip:" + s.lan_ip;
  $("#uptime").textContent = "uptime " + fmtUp(s.uptime) + "  v" + s.version;

  const meters = $("#meters"); meters.replaceChildren();
  meters.append(card("CPU", pctText(m.cpu), (m.cores || "?") + " cores", m.cpu));
  if (m.mem) meters.append(card("MEMORY", pctText(m.mem.percent), fmtBytes(m.mem.used) + " / " + fmtBytes(m.mem.total), m.mem.percent));
  if (m.disk) meters.append(card("DISK", pctText(m.disk.percent), fmtBytes(m.disk.used) + " / " + fmtBytes(m.disk.total), m.disk.percent));
  if (!m.gpus.length) meters.append(card("GPU", "none", "no NVIDIA GPU detected"));
  m.gpus.forEach((g, i) => {
    meters.append(card("GPU " + i + "  " + g.temp + "°C", pctText(g.util), g.name, g.util));
    meters.append(card("VRAM " + i, pctText(100 * g.mem_used / g.mem_total), g.mem_used.toFixed(0) + " / " + g.mem_total.toFixed(0) + " MB", 100 * g.mem_used / g.mem_total));
  });

  const t = $("#totals"); t.replaceChildren();
  t.append(card("REQUESTS", String(s.totals.requests)), card("TRAFFIC", fmtBytes(s.totals.bytes)),
           card("ACTIVE TUNNELS", String(s.totals.tunnels)), card("ENTRIES", String(s.entries.length) + " / 15"));

  const rows = $("#rows"); rows.replaceChildren();
  if (!s.entries.length) { const tr = el("tr"), td = el("td", "mut", "Nothing registered yet."); td.colSpan = 6; tr.append(td); rows.append(tr); }
  s.entries.forEach((e) => {
    const tr = el("tr");
    const nameTd = el("td");
    const a = el("a", "", e.name + ".engine"); a.href = e.url; a.target = "_blank";
    nameTd.append(a);
    const kind = e.type === "site" ? "site" : (e.command ? "managed app :" + e.port : "app :" + e.port);
    const st = el("td", e.ok ? "good" : "warn", e.status);
    if (e.process && e.process.running) st.textContent += "  (pid " + e.process.pid + ", " + fmtUp(e.process.uptime) + (e.process.restarts ? ", " + e.process.restarts + " restarts" : "") + ")";
    const act = el("td", "act");
    const open = el("a", "", "Open"); open.href = "http://" + location.hostname + ":" + s.proxy_port + "/_/" + e.name + "/"; open.target = "_blank";
    const ob = el("button", "alt"); ob.append(open); act.append(ob);
    if (e.type === "site") { const b = el("button", "alt", "Edit"); b.onclick = () => openEditor(e.name); act.append(b); }
    if (e.command) {
      const run = e.process && e.process.running;
      const b1 = el("button", "alt", run ? "Stop" : "Start"); b1.onclick = () => action(run ? "stop" : "start", e.name);
      const b2 = el("button", "alt", "Restart"); b2.onclick = () => action("restart", e.name);
      act.append(b1, b2);
    }
    const del = el("button", "danger", "Unbind"); del.onclick = async () => { if (confirm("Unbind " + e.name + ".engine ?")) { await api("/api/unregister", { name: e.name }); tick(); } };
    act.append(del);
    tr.append(nameTd, el("td", "mut", kind), st, el("td", "", String(e.requests)), el("td", "", fmtBytes(e.bytes)), act);
    rows.append(tr);
  });

  const sel = $("#logSel"), keep = sel.value || logName;
  const names = ["engine", "access"].concat(s.entries.filter((e) => e.command).map((e) => e.name));
  if (sel.options.length !== names.length) {
    sel.replaceChildren(); names.forEach((n) => { const o = el("option", "", n === "engine" ? "engine log" : n === "access" ? "access log" : "app: " + n); o.value = n; sel.append(o); });
    sel.value = names.includes(keep) ? keep : "engine";
  }
}

async function action(kind, name) {
  try { await api("/api/app/" + kind, { name }); } catch (e) { alert(e.message); }
  tick();
}
async function loadLogs() {
  try { const r = await api("/api/logs?name=" + encodeURIComponent(logName) + "&lines=200"); const box = $("#logBox"); const atEnd = box.scrollTop + box.clientHeight >= box.scrollHeight - 20; box.textContent = r.text || "(empty)"; if (atEnd) box.scrollTop = box.scrollHeight; } catch (e) {}
}
async function tick() {
  try { state = await api("/api/state"); render(); $("#status").textContent = "[ ONLINE ]"; $("#status").className = "chip good"; loadLogs(); }
  catch (e) { $("#status").textContent = "[ OFFLINE ]"; $("#status").className = "chip bad"; }
}
function show() { $("#login").hidden = true; $("#app").hidden = false; tick(); clearInterval(timer); timer = setInterval(tick, 2000); }
function lock() { token = ""; sessionStorage.removeItem("engine_token"); clearInterval(timer); $("#app").hidden = true; $("#login").hidden = false; }

async function doLogin() {
  $("#loginErr").textContent = "";
  try { const r = await api("/api/login", { password: $("#pw").value }); token = r.token; sessionStorage.setItem("engine_token", token); $("#pw").value = ""; show(); }
  catch (e) { $("#loginErr").textContent = e.message; }
}
$("#loginBtn").onclick = doLogin;
$("#pw").addEventListener("keydown", (e) => { if (e.key === "Enter") doLogin(); });
$("#logout").onclick = lock;
$("#logSel").onchange = (e) => { logName = e.target.value; loadLogs(); };

$("#rBtn").onclick = async () => {
  const m = $("#msg"); m.className = ""; m.textContent = "";
  try {
    const r = await api("/api/register", { name: $("#rName").value, target: $("#rTarget").value, command: $("#rCmd").value, cwd: $("#rCwd").value, autostart: true });
    m.className = "good"; m.textContent = r.message;
    ["#rName", "#rTarget", "#rCmd", "#rCwd"].forEach((i) => $(i).value = ""); tick();
  } catch (e) { m.className = "bad"; m.textContent = e.message; }
};

async function openEditor(name) {
  editing = name; $("#edMsg").textContent = ""; $("#edTitle").textContent = "// EDIT " + name + ".engine  (index.html)";
  try { const r = await api("/api/site?name=" + encodeURIComponent(name)); $("#edText").value = r.content; $("#editor").showModal(); } catch (e) { alert(e.message); }
}
$("#edSave").onclick = async () => { try { await api("/api/site", { name: editing, content: $("#edText").value }); $("#edMsg").textContent = "Saved. Reload the site."; } catch (e) { $("#edMsg").textContent = e.message; } };
$("#edClose").onclick = () => $("#editor").close();

if (token) { api("/api/state").then(() => show()).catch(() => lock()); }
</script>
</body>
</html>
"""
