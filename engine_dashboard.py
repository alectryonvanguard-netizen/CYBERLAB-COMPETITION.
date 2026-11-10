"""The .engine web dashboard (one page). Served by engine_admin.py."""

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>.engine</title>
<style>
  :root { --bg:#05080f; --panel:#0a1220; --line:rgba(0,240,255,.26); --acc:#00f0ff; --good:#00ff9c;
          --warn:#ffd60a; --bad:#ff4d6d; --txt:#d6f6ff; --mut:#5f7a94; }
  * { box-sizing:border-box; }
  body { margin:0; color:var(--txt); background-color:var(--bg);
         background-image:linear-gradient(rgba(0,240,255,.045) 1px, transparent 1px),
                          linear-gradient(90deg, rgba(0,240,255,.045) 1px, transparent 1px);
         background-size:36px 36px; font-family:ui-monospace,Menlo,Consolas,monospace; }
  .wrap { max-width:1150px; margin:0 auto; padding:16px 14px 60px; }
  h1 { margin:0; color:var(--acc); font-size:1.6rem; }
  h2 { margin:18px 0 10px; font-size:.78rem; color:var(--mut); letter-spacing:.12em; font-weight:normal; }
  .top { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:12px; }
  .sp { flex:1; }
  .nav { display:flex; gap:6px; overflow-x:auto; padding-bottom:6px; margin-bottom:6px; }
  .nav button { background:transparent; color:var(--mut); border:1px solid var(--line); white-space:nowrap; }
  .nav button.on { background:var(--acc); color:#05080f; }
  .chip { padding:4px 10px; border:1px solid var(--line); border-radius:6px; font-size:.78rem; }
  .good { color:var(--good); } .warn { color:var(--warn); } .bad { color:var(--bad); } .mut { color:var(--mut); }
  .panel, .card { background:var(--panel); border:1px solid var(--line); border-radius:10px; }
  .panel { padding:14px; margin-bottom:14px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(165px,1fr)); gap:10px; margin-bottom:12px; }
  .card { padding:11px 13px; }
  .card .lbl { font-size:.68rem; color:var(--mut); letter-spacing:.1em; }
  .card .val { font-size:1.4rem; color:var(--acc); margin:3px 0; }
  .card .sub { font-size:.7rem; color:var(--mut); }
  .track { height:6px; background:#10202e; border-radius:3px; margin-top:6px; overflow:hidden; }
  .fill { height:100%; background:var(--good); } .fill.mid { background:var(--warn); } .fill.hi { background:var(--bad); }
  input, select, textarea { width:100%; background:#05080f; color:var(--txt); border:1px solid var(--line);
         border-radius:6px; padding:9px; font:inherit; }
  input[type=checkbox] { width:auto; }
  textarea { min-height:140px; resize:vertical; }
  button { background:var(--acc); color:#05080f; border:0; border-radius:6px; padding:8px 13px; font:inherit; cursor:pointer; }
  button.alt { background:transparent; color:var(--acc); border:1px solid var(--line); padding:5px 9px; font-size:.78rem; }
  button.danger { background:transparent; color:var(--bad); border:1px solid rgba(255,77,109,.5); padding:5px 9px; font-size:.78rem; }
  .form { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:10px; align-items:end; }
  label { font-size:.68rem; color:var(--mut); display:block; margin-bottom:4px; }
  .tools { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin:8px 0; }
  .tools select, .tools input { width:auto; min-width:140px; }
  table { width:100%; border-collapse:collapse; font-size:.82rem; }
  th { text-align:left; font-weight:normal; color:var(--mut); font-size:.68rem; letter-spacing:.1em; padding:6px; }
  td { padding:7px 6px; border-top:1px solid rgba(0,240,255,.1); vertical-align:middle; }
  td.act { white-space:nowrap; text-align:right; } td.act > * { margin-left:4px; }
  .scroll { overflow-x:auto; }
  a { color:var(--acc); }
  pre { margin:0; max-height:280px; overflow:auto; font-size:.74rem; color:var(--mut); white-space:pre-wrap; }
  .chart { width:100%; height:auto; display:block; }
  .legend { font-size:.7rem; color:var(--mut); margin:4px 0 10px; }
  .msg { padding:10px 12px; border:1px solid var(--line); border-radius:8px; margin-bottom:8px; }
  .msg.unread { border-color:var(--acc); } .msg .h { color:var(--acc); }
  .banner { padding:10px 14px; border-radius:8px; margin-bottom:12px; border:1px solid var(--bad); color:var(--bad); }
  .banner.warn { border-color:var(--warn); color:var(--warn); }
  #login { min-height:100vh; display:grid; place-items:center; padding:16px; }
  #login .panel { width:100%; max-width:390px; }
  .seg { display:flex; gap:6px; margin:10px 0; }
  .seg button { flex:1; background:transparent; color:var(--mut); border:1px solid var(--line); }
  .seg button.on { background:var(--acc); color:#05080f; }
  dialog { background:var(--panel); color:var(--txt); border:1px solid var(--line); border-radius:10px;
           width:min(920px,95vw); padding:16px; max-height:92vh; overflow:auto; }
  dialog::backdrop { background:rgba(0,0,0,.72); }
  code, .code { background:#05080f; border:1px solid var(--line); border-radius:6px; padding:8px; display:block;
                word-break:break-all; font-size:.72rem; user-select:all; }
</style>
</head>
<body>
<div id="login">
  <div class="panel">
    <h1>&gt; .engine</h1>
    <p class="mut" style="font-size:.78rem">SECURE TERMINAL // AUTH REQUIRED</p>
    <div class="seg"><button id="segOwner" class="on">Owner</button><button id="segCust">Customer</button></div>
    <div id="userRow" hidden><label>USERNAME</label><input id="lUser" autocomplete="username"></div>
    <label style="margin-top:10px" id="pwLabel">ACCESS KEY</label>
    <input id="lPw" type="password" autocomplete="current-password">
    <div style="margin-top:12px"><button id="lBtn" style="width:100%">[ UNLOCK ]</button></div>
    <div id="lErr" class="bad" style="margin-top:10px;font-size:.78rem"></div>
  </div>
</div>

<div id="app" class="wrap" hidden>
  <div class="top">
    <h1>&gt; .engine</h1><span id="who" class="chip mut"></span>
    <span class="sp"></span><span id="status" class="chip good">[ ONLINE ]</span>
    <button class="alt" id="lock">Lock</button>
  </div>
  <div class="nav" id="nav"></div>
  <div id="view"></div>
</div>
<dialog id="dlg"><div id="dlgBody"></div><div style="margin-top:12px"><button class="alt" id="dlgClose">Close</button></div></dialog>

<script>
const NS = "http://www.w3.org/2000/svg";
const $ = (s, r) => (r || document).querySelector(s);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
const S = { token: sessionStorage.getItem("engine_token") || "", role: sessionStorage.getItem("engine_role") || "", user: sessionStorage.getItem("engine_user") || "" };
let tab = "", period = "week", timer = null, updater = null, loginMode = "owner";

async function api(path, body) {
  const opt = { headers: { "Content-Type": "application/json" } };
  if (S.token) opt.headers.Authorization = "Bearer " + S.token;
  if (body !== undefined) { opt.method = "POST"; opt.body = JSON.stringify(body); }
  const r = await fetch(path, opt);
  let data = {}; try { data = await r.json(); } catch (e) {}
  if (r.status === 401 && path !== "/api/login") { lock(); throw new Error("Session ended."); }
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}
const fmtBytes = (n) => { n = n || 0; if (n < 1024) return n + " B"; if (n < 1048576) return (n / 1024).toFixed(1) + " KB"; if (n < 1073741824) return (n / 1048576).toFixed(1) + " MB"; return (n / 1073741824).toFixed(2) + " GB"; };
const fmtUp = (s) => { const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60); return (d ? d + "d " : "") + h + "h " + m + "m"; };
const fmtNum = (n) => (n || 0).toLocaleString();
const fmtDate = (t) => t ? new Date(t * 1000).toLocaleString() : "never";
const pctText = (p) => p == null ? "n/a" : p.toFixed(0) + "%";
const clear = (n) => { n.replaceChildren(); return n; };

function card(label, value, sub, pct) {
  const c = el("div", "card");
  c.append(el("div", "lbl", label), el("div", "val", value));
  if (pct != null) { const t = el("div", "track"), f = el("div", "fill" + (pct > 85 ? " hi" : pct > 60 ? " mid" : "")); f.style.width = Math.min(100, pct) + "%"; t.append(f); c.append(t); }
  if (sub) c.append(el("div", "sub", sub));
  return c;
}
const title = (t) => el("h2", "", "// " + t);
const btn = (text, cls, fn) => { const b = el("button", cls || "", text); b.onclick = fn; return b; };
function field(label, input) { const d = el("div"); d.append(el("label", "", label), input); return d; }
function inp(ph, type, val) { const i = el("input"); i.placeholder = ph || ""; if (type) i.type = type; if (val !== undefined) i.value = val; return i; }
function sel(options, val, fn) { const s = el("select"); options.forEach(([v, t]) => { const o = el("option", "", t); o.value = v; s.append(o); }); s.value = val; s.onchange = () => fn(s.value); return s; }
function table(heads, rows, emptyText) {
  const wrap = el("div", "scroll"), t = el("table"), th = el("thead"), tr = el("tr");
  heads.forEach((h) => tr.append(el("th", "", h))); th.append(tr); t.append(th);
  const tb = el("tbody");
  if (!rows.length) { const r = el("tr"), td = el("td", "mut", emptyText || "Nothing here yet."); td.colSpan = heads.length; r.append(td); tb.append(r); }
  rows.forEach((cells) => { const r = el("tr"); cells.forEach((c) => { const td = el("td"); if (c instanceof Node) { td.append(c); if (c.classList && c.classList.contains("acts")) td.className = "act"; } else td.textContent = c == null ? "" : String(c); r.append(td); }); tb.append(r); });
  t.append(tb); wrap.append(t); return wrap;
}
const acts = (...b) => { const d = el("span", "acts"); d.append(...b); return d; };
function note(root, text, good) { const m = el("div", good ? "good" : "bad", text); m.style.margin = "8px 0"; root.append(m); setTimeout(() => m.remove(), 6000); }
function showDialog(heading, node) { const b = clear($("#dlgBody")); b.append(el("h2", "", "// " + heading), node); $("#dlg").showModal(); }
$("#dlgClose").onclick = () => $("#dlg").close();

// ------------------------------------------------------------- charts
function shortLabel(l) { return l.length === 10 ? l.slice(5) : l.slice(2); }
function svg(w, h) { const s = document.createElementNS(NS, "svg"); s.setAttribute("viewBox", "0 0 " + w + " " + h); s.setAttribute("class", "chart"); return s; }
function shape(name, attrs, style) { const e = document.createElementNS(NS, name); for (const k in attrs) e.setAttribute(k, attrs[k]); if (style) for (const k in style) e.style[k] = style[k]; return e; }
function barChart(labels, values, fmt, colour) {
  const W = 640, H = 170, pad = 8, base = H - 22, n = labels.length, max = Math.max(1, ...values), bw = (W - pad * 2) / n;
  const s = svg(W, H);
  s.append(shape("line", { x1: pad, x2: W - pad, y1: base, y2: base }, { stroke: "rgba(0,240,255,.25)" }));
  values.forEach((v, i) => {
    const h = Math.max(1, (base - 12) * v / max), r = shape("rect", { x: pad + i * bw + bw * 0.14, y: base - h, width: bw * 0.72, height: h, rx: 2 }, { fill: colour || "var(--acc)" });
    const t = document.createElementNS(NS, "title"); t.textContent = labels[i] + ": " + fmt(v); r.append(t); s.append(r);
    const step = n > 14 ? 5 : 1;
    if (i % step === 0) { const tx = shape("text", { x: pad + i * bw + bw / 2, y: H - 6, "text-anchor": "middle", "font-size": 9 }, { fill: "var(--mut)" }); tx.textContent = shortLabel(labels[i]); s.append(tx); }
  });
  return s;
}
function lineChart(labels, values, fmt) {
  const W = 640, H = 120, pad = 8, base = H - 18, n = labels.length, max = Math.max(1, ...values);
  const s = svg(W, H), pts = values.map((v, i) => [pad + i * (W - pad * 2) / Math.max(1, n - 1), base - (base - 10) * v / max]);
  s.append(shape("polygon", { points: [[pad, base]].concat(pts, [[W - pad, base]]).map((p) => p.join(",")).join(" ") }, { fill: "rgba(0,240,255,.12)" }));
  s.append(shape("polyline", { points: pts.map((p) => p.join(",")).join(" "), fill: "none", "stroke-width": 2 }, { stroke: "var(--acc)" }));
  const last = el("title"); const t = document.createElementNS(NS, "title"); t.textContent = "now: " + fmt(values[values.length - 1] || 0); s.append(t);
  return s;
}
function heatMatrix(days, map) {
  const cell = 13, gap = 3, cols = Math.ceil(days.length / 7), W = cols * (cell + gap) + 4, H = 7 * (cell + gap) + 4;
  const max = Math.max(1, ...Object.values(map)), s = svg(W, H);
  s.style.maxWidth = (W * 2) + "px";
  days.forEach((d, i) => {
    const v = map[d] || 0, a = v ? 0.18 + 0.82 * Math.sqrt(v / max) : 0;
    const r = shape("rect", { x: 2 + Math.floor(i / 7) * (cell + gap), y: 2 + (i % 7) * (cell + gap), width: cell, height: cell, rx: 3 }, { fill: v ? "rgba(0,240,255," + a.toFixed(2) + ")" : "#0b1a26" });
    const t = document.createElementNS(NS, "title"); t.textContent = d + ": " + fmtNum(v) + " requests"; r.append(t); s.append(r);
  });
  return s;
}
function periodBar(onChange) {
  const box = el("div", "tools");
  [["week", "Week"], ["month", "Month"], ["year", "Year"]].forEach(([v, t]) => { const b = btn(t, "alt", () => { period = v; mark(); onChange(); }); b.dataset.p = v; box.append(b); });
  const mark = () => box.querySelectorAll("button").forEach((b) => { b.style.background = b.dataset.p === period ? "var(--acc)" : "transparent"; b.style.color = b.dataset.p === period ? "#05080f" : "var(--acc)"; });
  mark(); return box;
}
function renderReport(root, rep) {
  clear(root);
  const g = el("div", "grid"), t = rep.totals, ch = t.change_pct;
  g.append(card("REQUESTS", fmtNum(t.requests), ch == null ? "no earlier period yet" : (ch >= 0 ? "+" : "") + ch + "% vs previous"),
           card("BANDWIDTH", fmtBytes(t.bytes)),
           card("UPTIME", rep.uptime_pct == null ? "n/a" : rep.uptime_pct.toFixed(1) + "%", rep.nodes_online + " of " + rep.nodes + " servers online", rep.uptime_pct));
  const q = rep.storage.quota;
  g.append(card("STORAGE", fmtBytes(rep.storage.used), q ? "of " + fmtBytes(q) : "no quota set", q ? 100 * rep.storage.used / q : null));
  root.append(g);
  const labels = rep.series.labels;
  root.append(title("REQUESTS PER " + (rep.period === "year" ? "MONTH" : "DAY")), barChart(labels, rep.series.requests, fmtNum));
  root.append(title("BANDWIDTH PER " + (rep.period === "year" ? "MONTH" : "DAY")), barChart(labels, rep.series.bytes, fmtBytes, "var(--good)"));
  if (rep.heat) { root.append(title("ACTIVITY MATRIX (LAST 20 WEEKS)"), heatMatrix(rep.heat.days, rep.heat.requests)); }
  root.append(title("STORAGE (LAST 30 DAYS)"), lineChart(rep.storage.history.labels, rep.storage.history.bytes, fmtBytes));
  root.append(title("TOP SITES"), table(["SITE", "REQUESTS", "BANDWIDTH"], rep.top_sites.map((s) => [s.site + ".engine", fmtNum(s.requests), fmtBytes(s.bytes)]), "No traffic recorded yet."));
}

// ------------------------------------------------------------- views (owner)
const VIEWS = {};
VIEWS.overview = (root) => {
  let scope = "local";
  const meters = el("div", "grid"), totals = el("div", "grid"), charts = el("div");
  const tools = el("div", "tools"); tools.append(periodBar(() => update()), sel([["local", "This server"], ["all", "All customers"]], scope, (v) => { scope = v; update(); }));
  root.append(title("SYSTEM"), meters, title("TRAFFIC"), totals, tools, charts);
  async function update() {
    const s = await api("/api/state?limit=1"), m = s.metrics;
    clear(meters).append(card("CPU", pctText(m.cpu), (m.cores || "?") + " cores", m.cpu));
    if (m.mem) meters.append(card("MEMORY", pctText(m.mem.percent), fmtBytes(m.mem.used) + " / " + fmtBytes(m.mem.total), m.mem.percent));
    if (m.disk) meters.append(card("DISK", pctText(m.disk.percent), fmtBytes(m.disk.used) + " / " + fmtBytes(m.disk.total), m.disk.percent));
    if (!m.gpus.length) meters.append(card("GPU", "none", "no NVIDIA GPU detected"));
    m.gpus.forEach((g, i) => { meters.append(card("GPU " + i + "  " + g.temp + "C", pctText(g.util), g.name, g.util), card("VRAM " + i, pctText(100 * g.mem_used / g.mem_total), g.mem_used.toFixed(0) + " / " + g.mem_total.toFixed(0) + " MB", 100 * g.mem_used / g.mem_total)); });
    clear(totals).append(card("REQUESTS", fmtNum(s.totals.requests)), card("TRAFFIC", fmtBytes(s.totals.bytes)), card("TUNNELS", String(s.totals.tunnels)),
      card("SITES", fmtNum(s.entry_count) + " / 4600"), card("SITE STORAGE", fmtBytes(s.storage_bytes)),
      card("HTTPS", s.https_port ? "on :" + s.https_port : "off", s.tls.available ? "certificates ready" : "install cryptography"),
      card("UPTIME", fmtUp(s.uptime), s.lan_ip + "  v" + s.version));
    renderReport(charts, await api("/api/report?scope=" + scope + "&period=" + period));
  }
  update(); return update;
};

VIEWS.sites = (root) => {
  let offset = 0, q = "", logName = "engine"; const LIM = 50;
  const form = el("div", "panel"), f = el("div", "form");
  const n = inp("shop"), tg = inp("8001 or /var/www/shop"), cmd = inp("python app.py"), cwd = inp("/home/me/app");
  f.append(field("NAME", n), field("TARGET (blank = new site, port = app, folder = site)", tg), field("START COMMAND (optional)", cmd), field("WORKING FOLDER (optional)", cwd),
    btn("[ REGISTER ]", "", async () => { try { const r = await api("/api/register", { name: n.value, target: tg.value, command: cmd.value, cwd: cwd.value, autostart: true }); [n, tg, cmd, cwd].forEach((i) => i.value = ""); note(form, r.message, true); update(); } catch (e) { note(form, e.message); } }));
  form.append(title("REGISTER A SITE OR APP"), f);
  const tools = el("div", "tools"), search = inp("search names", "search"); search.oninput = () => { q = search.value.trim().toLowerCase(); offset = 0; update(); };
  const info = el("span", "mut"), list = el("div"), logBox = el("pre"), logSel = el("select");
  tools.append(search, btn("Prev", "alt", () => { offset = Math.max(0, offset - LIM); update(); }), btn("Next", "alt", () => { offset += LIM; update(); }), info);
  logSel.onchange = () => { logName = logSel.value; loadLogs(); };
  const logs = el("div", "panel"); logs.append(title("LOGS"), logSel, el("div"), logBox);
  root.append(form, el("div", "panel")); const tp = root.lastChild; tp.append(title("SITES AND APPS"), tools, list); root.append(logs);
  async function loadLogs() { try { const r = await api("/api/logs?name=" + encodeURIComponent(logName) + "&lines=200"); const atEnd = logBox.scrollTop + logBox.clientHeight >= logBox.scrollHeight - 20; logBox.textContent = r.text || "(empty)"; if (atEnd) logBox.scrollTop = logBox.scrollHeight; } catch (e) {} }
  async function update() {
    const s = await api("/api/state?limit=" + LIM + "&offset=" + offset + "&q=" + encodeURIComponent(q));
    info.textContent = s.matching + " of " + s.entry_count + " shown " + (s.matching ? (offset + 1) + "-" + Math.min(offset + LIM, s.matching) : "");
    const rows = s.entries.map((e) => {
      const kind = (e.type === "site" ? "site" : (e.command ? "managed app :" + e.port : "app :" + e.port)) + (e.protected ? "  [locked]" : "");
      const a = el("a", "", e.name + ".engine"); a.href = e.https_url || e.url; a.target = "_blank";
      const st = el("span", e.ok ? "good" : "warn", e.status); if (e.process && e.process.running) st.textContent += " (pid " + e.process.pid + ")";
      const open = el("a", "", "Open"); open.href = "http://" + location.hostname + ":" + s.proxy_port + "/_/" + e.name + "/"; open.target = "_blank";
      const b = [btn("Open", "alt", () => window.open(open.href, "_blank"))];
      if (e.type === "site") b.push(btn("Edit", "alt", () => openEditor(e.name)));
      if (e.command) { const run = e.process && e.process.running; b.push(btn(run ? "Stop" : "Start", "alt", () => ctl(run ? "stop" : "start", e.name)), btn("Restart", "alt", () => ctl("restart", e.name))); }
      b.push(btn(e.protected ? "Unlock" : "Lock", "alt", async () => { try { if (e.protected) await api("/api/site/unprotect", { name: e.name }); else { const u = prompt("Visitor username for " + e.name + ".engine"); if (!u) return; const p = prompt("Visitor password (8+ characters)"); if (!p) return; await api("/api/site/protect", { name: e.name, user: u, password: p }); } update(); } catch (er) { alert(er.message); } }));
      b.push(btn("Unbind", "danger", async () => { if (confirm("Unbind " + e.name + ".engine ?")) { await api("/api/unregister", { name: e.name }); update(); } }));
      return [a, kind, st, fmtNum(e.requests), fmtBytes(e.bytes), acts(...b)];
    });
    clear(list).append(table(["NAME", "TYPE", "STATUS", "REQUESTS", "TRAFFIC", ""], rows, "Nothing registered yet."));
    const names = ["engine", "access"].concat(s.entries.filter((e) => e.command).map((e) => e.name));
    if (logSel.options.length !== names.length) { clear(logSel); names.forEach((x) => { const o = el("option", "", x === "engine" ? "engine log" : x === "access" ? "access log" : "app: " + x); o.value = x; logSel.append(o); }); logSel.value = names.includes(logName) ? logName : "engine"; }
    loadLogs();
  }
  async function ctl(kind, name) { try { await api("/api/app/" + kind, { name }); } catch (e) { alert(e.message); } update(); }
  async function openEditor(name) {
    try {
      const r = await api("/api/site?name=" + encodeURIComponent(name)), box = el("div"), ta = el("textarea"), msg = el("div", "good");
      ta.style.minHeight = "50vh"; ta.value = r.content; ta.spellcheck = false;
      box.append(ta, btn("[ SAVE ]", "", async () => { try { await api("/api/site", { name, content: ta.value }); msg.className = "good"; msg.textContent = "Saved. Reload the site."; } catch (e) { msg.className = "bad"; msg.textContent = e.message; } }), msg);
      showDialog("EDIT " + name + ".engine (index.html)", box);
    } catch (e) { alert(e.message); }
  }
  update(); return update;
};

VIEWS.customers = (root) => {
  const form = el("div", "panel"), f = el("div", "form"), list = el("div", "panel");
  const u = inp("alice"), p = inp("Str0ng!Pass1", "password"), em = inp("alice@example.com"), qt = inp("1024", "number", 1024), mn = inp("1", "number", 1);
  f.append(field("USERNAME", u), field("PASSWORD", p), field("EMAIL", em), field("STORAGE QUOTA (MB)", qt), field("MAX SERVERS", mn),
    btn("[ CREATE CUSTOMER ]", "", async () => { try { await api("/api/users", { username: u.value, password: p.value, email: em.value, quota_mb: +qt.value, max_nodes: +mn.value }); [u, p, em].forEach((i) => i.value = ""); note(form, "Customer created.", true); update(); } catch (e) { note(form, e.message); } }));
  form.append(title("NEW CUSTOMER"), f); list.append(title("CUSTOMERS"));
  const body = el("div"); list.append(body); root.append(form, list);
  async function update() {
    const r = await api("/api/users");
    const rows = r.users.map((c) => {
      const used = c.storage_bytes, quota = c.quota_mb * 1048576;
      return [c.username, c.email, c.status === "active" ? el("span", "good", "active") : el("span", "bad", "suspended"), c.nodes + " / " + c.max_nodes,
        fmtBytes(used) + " / " + fmtBytes(quota) + (quota && used > quota ? "  OVER" : ""), fmtDate(c.last_seen),
        acts(btn("Report", "alt", () => showReport("user:" + c.id, c.username)),
             btn("Message", "alt", async () => { const s = prompt("Subject"); if (!s) return; const b = prompt("Message to " + c.username); if (!b) return; try { await api("/api/messages", { to: c.username, subject: s, body: b }); alert("Sent."); } catch (e) { alert(e.message); } }),
             btn("Limits", "alt", async () => { const mb = prompt("Storage quota in MB", c.quota_mb); if (mb === null) return; const mx = prompt("Max servers", c.max_nodes); if (mx === null) return; await api("/api/users/update", { id: c.id, quota_mb: +mb, max_nodes: +mx }); update(); }),
             btn(c.status === "active" ? "Suspend" : "Activate", "alt", async () => { await api("/api/users/update", { id: c.id, status: c.status === "active" ? "suspended" : "active" }); update(); }),
             btn("Password", "alt", async () => { const np = prompt("New password for " + c.username); if (!np) return; try { await api("/api/users/password", { id: c.id, password: np }); alert("Changed."); } catch (e) { alert(e.message); } }),
             btn("Delete", "danger", async () => { if (confirm("Delete " + c.username + " and all their usage data?")) { await api("/api/users/delete", { id: c.id }); update(); } }))];
    });
    clear(body).append(table(["USERNAME", "EMAIL", "STATUS", "SERVERS", "STORAGE", "LAST SEEN", ""], rows, "No customers yet."));
  }
  async function showReport(scope, name) {
    const box = el("div"), area = el("div");
    box.append(periodBar(() => load()), area);
    async function load() { renderReport(area, await api("/api/report?scope=" + scope + "&period=" + period)); }
    showDialog("REPORT: " + name, box); load();
  }
  update(); return update;
};

VIEWS.servers = (root) => {
  const form = el("div", "panel"), f = el("div", "form"), out = el("div"), list = el("div", "panel"), userSel = el("select");
  const nm = inp("alice-server");
  f.append(field("CUSTOMER", userSel), field("SERVER NAME", nm), btn("[ CREATE JOIN CODE ]", "", async () => {
    try { const r = await api("/api/nodes/create", { user_id: +userSel.value, name: nm.value || "server" }); showCode(out, r.join_code); update(); } catch (e) { note(form, e.message); } }));
  form.append(title("NEW SMALL SERVER FOR A CUSTOMER"), f, out); list.append(title("ALL SMALL SERVERS")); const body = el("div"); list.append(body); root.append(form, list);
  async function update() {
    const [us, ns] = await Promise.all([api("/api/users"), api("/api/nodes")]);
    if (userSel.options.length !== us.users.length) { clear(userSel); us.users.forEach((c) => { const o = el("option", "", c.username); o.value = c.id; userSel.append(o); }); }
    const rows = ns.nodes.map((n) => [n.name, n.owner, n.online ? el("span", "good", "online") : el("span", "bad", "offline"), fmtDate(n.last_seen), n.entries, fmtBytes(n.storage_bytes),
      (n.cpu == null ? "-" : n.cpu.toFixed(0) + "% cpu  " + (n.mem == null ? "-" : n.mem.toFixed(0)) + "% ram"), n.version || "",
      acts(btn("Report", "alt", async () => { const box = el("div"), area = el("div"); box.append(periodBar(() => load()), area); async function load() { renderReport(area, await api("/api/report?scope=node:" + n.id + "&period=" + period)); } showDialog("SERVER: " + n.name, box); load(); }),
           btn("New code", "alt", async () => { if (!confirm("The old code stops working. Continue?")) return; const r = await api("/api/nodes/reset", { id: n.id }); showCode(out, r.join_code); }),
           btn("Delete", "danger", async () => { if (confirm("Delete " + n.name + "?")) { await api("/api/nodes/delete", { id: n.id }); update(); } }))]);
    clear(body).append(table(["SERVER", "OWNER", "STATE", "LAST SEEN", "SITES", "STORAGE", "LOAD", "VERSION", ""], rows, "No small servers yet."));
  }
  update(); return update;
};
function showCode(root, code) {
  clear(root); const box = el("div", "panel");
  box.append(el("p", "warn", "Give this join code to the customer. It is shown once. On their server run:  python engine_core.py join <code>"), el("div", "code", code));
  root.append(box);
}

VIEWS.messages = (root) => {
  const form = el("div", "panel"), f = el("div", "form"), list = el("div", "panel");
  const to = inp("customer username, or leave blank for everyone"), sub = inp("Subject"), body = el("textarea"), kind = sel([["info", "Information"], ["warning", "Warning"], ["billing", "Billing"]], "info", () => {});
  f.append(field("TO", to), field("TYPE", kind), field("SUBJECT", sub));
  form.append(title("SEND A PRIVATE MESSAGE"), f, field("MESSAGE", body), btn("[ SEND ]", "", async () => { try { const r = await api("/api/messages", { to: to.value, subject: sub.value, body: body.value, kind: kind.value }); sub.value = body.value = ""; note(form, "Sent to " + r.sent + " customer(s).", true); update(); } catch (e) { note(form, e.message); } }));
  list.append(title("SENT")); const out = el("div"); list.append(out); root.append(form, list);
  async function update() { const r = await api("/api/messages"); clear(out).append(table(["TO", "TYPE", "SUBJECT", "SENT", "READ"], r.messages.map((m) => [m.to, m.kind, m.subject, fmtDate(m.created), m.read ? "yes" : "no"]), "No messages yet.")); }
  update(); return update;
};

VIEWS.security = (root) => {
  const status = el("div"), settings = el("div", "panel"), audit = el("div", "panel"), keyBox = el("div", "panel");
  const fh = el("input"); fh.type = "checkbox"; const hs = el("input"); hs.type = "checkbox";
  const rl = inp("0 = off", "number"), mc = inp("200", "number"), ph = inp("mother.example.com");
  settings.append(title("SETTINGS"));
  const f = el("div", "form");
  const lab = (t, i) => { const d = el("div"); const l = el("label"); l.append(i, " " + t); l.style.fontSize = ".8rem"; l.style.color = "var(--txt)"; d.append(l); return d; };
  f.append(lab("Force HTTPS for all sites", fh), lab("HSTS header on HTTPS sites", hs), field("REQUESTS PER MINUTE PER VISITOR IP (0 = off)", rl), field("MAX OPEN CONNECTIONS PER IP", mc), field("PUBLIC HOST NAME (used in join codes and certificates)", ph),
    btn("[ SAVE SETTINGS ]", "", async () => { try { await api("/api/settings", { force_https: fh.checked, hsts: hs.checked, rate_limit_per_min: +rl.value || 0, max_conn_per_ip: +mc.value || 0, public_host: ph.value }); note(settings, "Saved.", true); } catch (e) { note(settings, e.message); } }));
  settings.append(f);
  const cur = inp("current access key", "password"), nw = inp("new access key", "password");
  keyBox.append(title("CHANGE THE OWNER ACCESS KEY"), (() => { const g = el("div", "form"); g.append(field("CURRENT", cur), field("NEW", nw), btn("[ CHANGE KEY ]", "", async () => { try { await api("/api/admin/password", { current: cur.value, new: nw.value }); alert("Changed. Sign in again."); lock(); } catch (e) { note(keyBox, e.message); } })); return g; })());
  audit.append(title("AUDIT LOG (WHO DID WHAT)")); const aud = el("div"); audit.append(aud);
  root.append(el("div", "panel"), settings, keyBox, audit); const sp = root.firstChild; sp.append(title("HTTPS AND CERTIFICATES"), status);
  async function update() {
    const s = await api("/api/settings"), t = s.tls;
    clear(status).append((() => { const g = el("div", "grid"); g.append(card("HTTPS", t.https_port ? "on :" + t.https_port : (t.available ? "starting" : "off"), t.available ? "TLS 1.2 / 1.3" : "pip install cryptography"), card("DASHBOARD", t.admin_https_port ? "https :" + t.admin_https_port : "http only"), card("CA FINGERPRINT", (t.fingerprint || "").slice(0, 16) || "n/a", "SHA-256 of the private CA")); return g; })());
    const dl = el("a", "", "Download the CA certificate (install it once on every device that should trust your sites)"); dl.href = "/ca.crt"; status.append(dl);
    if (document.activeElement !== rl && document.activeElement !== mc && document.activeElement !== ph) { fh.checked = !!s.settings.force_https; hs.checked = !!s.settings.hsts; rl.value = s.settings.rate_limit_per_min; mc.value = s.settings.max_conn_per_ip; ph.value = s.settings.public_host; }
    const a = await api("/api/audit"); clear(aud).append(table(["WHEN", "WHO", "ACTION", "DETAIL", "FROM"], a.audit.map((x) => [fmtDate(x.ts), x.actor, x.action, x.detail, x.ip]), "No events yet."));
  }
  update(); return update;
};

VIEWS.provider = (root) => {
  let loaded = false; const box = el("div"); root.append(box);
  async function update() {
    const r = await api("/api/mother?period=" + period);
    if (loaded && !r.status.joined) { loaded = false; }
    clear(box);
    if (!r.status.joined) {
      const p = el("div", "panel"), ta = el("textarea"); ta.placeholder = "Paste the join code from your provider";
      p.append(title("JOIN A MOTHER SERVER"), el("p", "mut", "If this server is hosted for you by a provider, paste the join code they gave you."), ta,
        btn("[ JOIN ]", "", async () => { try { const x = await api("/api/mother/join", { code: ta.value }); note(p, x.message, true); setTimeout(update, 800); } catch (e) { note(p, e.message); } }));
      box.append(p); return;
    }
    const st = r.status, ms = r.state;
    if (ms.suspended) box.append(el("div", "banner", "This account is suspended by your provider. Your sites are paused."));
    else if (ms.over_quota) box.append(el("div", "banner warn", "Storage quota exceeded. New saves are blocked until you free space."));
    const g = el("div", "grid"); g.append(card("PROVIDER LINK", st.connected ? "connected" : "not connected", st.url || ""), card("LAST REPORT SENT", st.last_ok ? new Date(st.last_ok * 1000).toLocaleTimeString() : "never", st.error || ""),
      card("QUOTA", ms.quota_bytes ? fmtBytes(ms.quota_bytes) : "none", "used " + fmtBytes(ms.storage_bytes || 0), ms.quota_bytes ? 100 * (ms.storage_bytes || 0) / ms.quota_bytes : null));
    box.append(g, btn("Leave provider", "danger", async () => { if (confirm("Stop reporting to the provider?")) { await api("/api/mother/leave", {}); update(); } }));
    box.append(title("MY REPORT FROM THE PROVIDER"), periodBar(() => update())); const area = el("div"); box.append(area);
    if (r.report) renderReport(area, r.report); else area.append(el("p", "mut", "The report will appear after the first successful connection."));
    box.append(title("PRIVATE MESSAGES")); const unread = r.inbox.filter((m) => !m.read).length;
    r.inbox.forEach((m) => { const d = el("div", "msg" + (m.read ? "" : " unread")); d.append(el("div", "h", m.subject + "   [" + m.kind + "]"), el("div", "", m.body), el("div", "mut", fmtDate(m.created))); box.append(d); });
    if (!r.inbox.length) box.append(el("p", "mut", "No messages."));
    if (unread) box.append(btn("Mark all read", "alt", async () => { await api("/api/mother/read", {}); update(); }));
  }
  update(); return update;
};

// ------------------------------------------------------------- views (customer)
VIEWS.c_overview = (root) => {
  const top = el("div"), area = el("div"); root.append(top, periodBar(() => update()), area);
  async function update() {
    const o = await api("/api/portal/overview");
    clear(top);
    if (o.user.status !== "active") top.append(el("div", "banner", "Your account is suspended."));
    else if (o.quota_bytes && o.storage_bytes > o.quota_bytes) top.append(el("div", "banner warn", "You are over your storage quota (" + fmtBytes(o.storage_bytes) + " of " + fmtBytes(o.quota_bytes) + ")."));
    if (o.unread) top.append(el("div", "banner warn", "You have " + o.unread + " unread private message(s)."));
    renderReport(area, await api("/api/portal/report?period=" + period));
  }
  update(); return update;
};
VIEWS.c_servers = (root) => {
  const form = el("div", "panel"), out = el("div"), list = el("div", "panel"); const nm = inp("my-server");
  const f = el("div", "form"); f.append(field("SERVER NAME", nm), btn("[ ADD A SERVER ]", "", async () => { try { const r = await api("/api/portal/node/create", { name: nm.value || "my-server" }); showCode(out, r.join_code); update(); } catch (e) { note(form, e.message); } }));
  form.append(title("ADD A SMALL SERVER"), f, out); list.append(title("MY SERVERS")); const body = el("div"); list.append(body); root.append(form, list);
  async function update() {
    const o = await api("/api/portal/overview");
    const rows = o.nodes.map((n) => [n.name, n.online ? el("span", "good", "online") : el("span", "bad", "offline"), fmtDate(n.last_seen), n.entries, fmtBytes(n.storage_bytes), (n.cpu == null ? "-" : n.cpu.toFixed(0) + "% cpu"),
      acts(btn("New code", "alt", async () => { if (!confirm("The old code stops working. Continue?")) return; const r = await api("/api/portal/node/reset", { id: n.id }); showCode(out, r.join_code); }),
           btn("Delete", "danger", async () => { if (confirm("Delete " + n.name + "?")) { await api("/api/portal/node/delete", { id: n.id }); update(); } }))]);
    clear(body).append(table(["SERVER", "STATE", "LAST SEEN", "SITES", "STORAGE", "LOAD", ""], rows, "You have no servers yet."));
  }
  update(); return update;
};
VIEWS.c_messages = (root) => {
  const box = el("div"); root.append(title("PRIVATE MESSAGES FROM YOUR PROVIDER"), box);
  async function update() {
    const r = await api("/api/portal/messages"); clear(box);
    if (!r.messages.length) box.append(el("p", "mut", "No messages."));
    r.messages.forEach((m) => { const d = el("div", "msg" + (m.read ? "" : " unread")); d.append(el("div", "h", m.subject + "   [" + m.kind + "]"), el("div", "", m.body), el("div", "mut", fmtDate(m.created))); box.append(d); });
    const ids = r.messages.filter((m) => !m.read).map((m) => m.id); if (ids.length) { api("/api/portal/messages/read", { ids }).catch(() => {}); }
  }
  update(); return null;
};
VIEWS.c_account = (root) => {
  const p = el("div", "panel"), g = el("div", "form"), cur = inp("current password", "password"), nw = inp("new password", "password");
  g.append(field("CURRENT PASSWORD", cur), field("NEW PASSWORD", nw), btn("[ CHANGE PASSWORD ]", "", async () => { try { await api("/api/portal/password", { current: cur.value, new: nw.value }); cur.value = nw.value = ""; note(p, "Password changed.", true); } catch (e) { note(p, e.message); } }));
  p.append(title("ACCOUNT"), el("p", "mut", "Signed in as " + S.user), g); root.append(p); return null;
};

const NAV = { admin: [["overview", "Overview"], ["sites", "Sites"], ["customers", "Customers"], ["servers", "Servers"], ["messages", "Messages"], ["security", "Security"], ["provider", "Provider"]],
              customer: [["c_overview", "Overview"], ["c_servers", "My servers"], ["c_messages", "Messages"], ["c_account", "Account"]] };

function go(name) {
  tab = name; clearInterval(timer); updater = null;
  document.querySelectorAll("#nav button").forEach((b) => b.classList.toggle("on", b.dataset.t === name));
  const root = clear($("#view"));
  Promise.resolve().then(() => VIEWS[name](root)).then((u) => { updater = u; timer = setInterval(async () => { if (!$("#dlg").open && updater) { try { await updater(); $("#status").textContent = "[ ONLINE ]"; $("#status").className = "chip good"; } catch (e) { $("#status").textContent = "[ OFFLINE ]"; $("#status").className = "chip bad"; } } }, 5000); }).catch((e) => root.append(el("p", "bad", e.message)));
}
function show() {
  $("#login").hidden = true; $("#app").hidden = false; $("#who").textContent = S.user + " (" + S.role + ")";
  const nav = clear($("#nav")); (NAV[S.role] || NAV.customer).forEach(([t, label]) => { const b = el("button", "", label); b.dataset.t = t; b.onclick = () => go(t); nav.append(b); });
  go(S.role === "admin" ? "overview" : "c_overview");
}
function lock() { S.token = ""; sessionStorage.clear(); clearInterval(timer); $("#app").hidden = true; $("#login").hidden = false; }
async function doLogin() {
  $("#lErr").textContent = "";
  try {
    const r = await api("/api/login", { username: loginMode === "customer" ? $("#lUser").value : "", password: $("#lPw").value });
    S.token = r.token; S.role = r.role; S.user = r.username; sessionStorage.setItem("engine_token", S.token); sessionStorage.setItem("engine_role", S.role); sessionStorage.setItem("engine_user", S.user);
    $("#lPw").value = ""; show();
  } catch (e) { $("#lErr").textContent = e.message; }
}
function setMode(m) { loginMode = m; $("#segOwner").classList.toggle("on", m === "owner"); $("#segCust").classList.toggle("on", m === "customer"); $("#userRow").hidden = m !== "customer"; $("#pwLabel").textContent = m === "owner" ? "ACCESS KEY" : "PASSWORD"; }
$("#segOwner").onclick = () => setMode("owner"); $("#segCust").onclick = () => setMode("customer");
$("#lBtn").onclick = doLogin; $("#lPw").addEventListener("keydown", (e) => { if (e.key === "Enter") doLogin(); });
$("#lock").onclick = lock;
if (S.token && S.role) { api(S.role === "admin" ? "/api/state?limit=1" : "/api/portal/overview").then(show).catch(lock); }
</script>
</body>
</html>
"""
