"""
.engine admin server: JSON API + web dashboard, over HTTPS when available.

Roles
  admin     the owner (access key): everything.
  customer  a hosting customer (username + password): only their own reports,
            servers and private messages.
  node      a customer's small server (token): reports in, quota and messages out.
"""
import os
import ssl
import json
import time
import base64
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from engine_infra import (read_auth, write_auth, check_auth, tail_file, password_checks,
                          MAX_FAILS, LOCK_SECONDS)
from engine_dashboard import DASHBOARD_HTML

ADMIN_PORTS = (9090, 9091, 9092)
ADMIN_HTTPS_PORTS = (9443, 9444, 9445)
TOKEN_TTL = 12 * 3600
MAX_BODY = 3_000_000
MAX_PAGE_BYTES = 2_000_000


class TLSServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, handler, ctx):
        super().__init__(addr, handler)
        self.ctx = ctx

    def get_request(self):
        sock, addr = self.socket.accept()
        sock.settimeout(10)
        return self.ctx.wrap_socket(sock, server_side=True, do_handshake_on_connect=False), addr

    def handle_error(self, request, client_address):
        pass  # failed handshakes and resets are normal on the internet


class QuietServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass


class AdminServer:
    def __init__(self, core):
        self.core = core
        self.tokens = {}
        self.fails = {}
        self.httpd = None
        self.https_httpd = None
        self.https_port = None
        self.lock = threading.Lock()

    # --------------------------------------------------------------- start
    def start(self):
        handler = self._make_handler()
        for port in (self.core.ports.get("admin") or ADMIN_PORTS):
            try:
                self.httpd = QuietServer(("0.0.0.0", port), handler)
                self.core.admin_port = port
                break
            except OSError:
                continue
        if self.httpd is None:
            self.core.log("Dashboard could not bind a port.")
            return
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

        ctx = None
        try:
            ctx = self.core.tls_server_context()
        except Exception as e:
            self.core.log(f"HTTPS for the dashboard failed: {e}")
        if ctx is not None:
            for port in (self.core.ports.get("admin_https") or ADMIN_HTTPS_PORTS):
                try:
                    self.https_httpd = TLSServer(("0.0.0.0", port), handler, ctx)
                    self.https_port = port
                    break
                except OSError:
                    continue
            if self.https_httpd:
                threading.Thread(target=self.https_httpd.serve_forever, daemon=True).start()
        if self.https_port:
            self.core.log(f"Dashboard (secure): https://localhost:{self.https_port}")
        self.core.log(f"Dashboard: http://localhost:{self.core.admin_port}"
                      + (" (this computer only; others use HTTPS)" if self.https_port else ""))

    def stop(self):
        for srv in (self.httpd, self.https_httpd):
            if srv:
                try:
                    srv.shutdown()
                    srv.server_close()
                except Exception:
                    pass

    # ---------------------------------------------------------------- auth
    def _locked(self, key):
        _count, until = self.fails.get(key, (0, 0))
        return until if time.time() < until else 0

    def _fail(self, key):
        count, _ = self.fails.get(key, (0, 0))
        count += 1
        if count >= MAX_FAILS:
            self.fails[key] = (0, time.time() + LOCK_SECONDS)
        else:
            self.fails[key] = (count, 0)

    def login(self, ip, username, password):
        username = (username or "").strip().lower()
        key = (username or "admin", ip)
        now = time.time()
        with self.lock:
            until = self._locked(key)
            if until:
                return 429, {"error": f"Too many attempts. Try again in {int(until - now) + 1}s."}
            if not username:  # owner access key
                auth = read_auth(self.core.auth_path())
                if not auth:
                    return 503, {"error": "No access key yet. Create it in the app, or run: "
                                          "python engine_core.py setpassword"}
                if not check_auth(auth, password or ""):
                    self._fail(key)
                    self.core.store.audit("admin", "login_failed", "", ip)
                    return 401, {"error": "Wrong access key."}
                session = {"role": "admin", "uid": None, "user": "admin"}
            else:
                user, err = self.core.store.verify_user(username, password or "")
                if not user:
                    self._fail(key)
                    self.core.store.audit(username, "login_failed", err, ip)
                    return 401, {"error": err}
                session = {"role": "customer", "uid": user["id"], "user": user["username"]}
            self.fails.pop(key, None)
            self.tokens = {t: s for t, s in self.tokens.items() if s["exp"] > now}
            token = secrets.token_urlsafe(24)
            self.tokens[token] = {**session, "exp": now + TOKEN_TTL}
        self.core.store.audit(session["user"], "login", session["role"], ip)
        return 200, {"token": token, "role": session["role"], "username": session["user"]}

    def session(self, token):
        with self.lock:
            s = self.tokens.get(token)
            if s and s["exp"] > time.time():
                return s
        return None

    def drop_sessions(self, uid=None, role=None):
        with self.lock:
            self.tokens = {t: s for t, s in self.tokens.items()
                           if not ((uid is not None and s["uid"] == uid) or (role and s["role"] == role))}

    def join_code(self, token):
        core = self.core
        host = core.settings.get("public_host") or core.lan_ip
        if self.https_port and core.tls.available:
            url, ca = f"https://{host}:{self.https_port}", core.tls.ca_pem().decode()
        else:
            url, ca = f"http://{host}:{core.admin_port}", ""
        raw = json.dumps({"u": url, "t": token, "ca": ca}).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    # --------------------------------------------------------------- logic
    def _scope(self, scope):
        scope = scope or "local"
        if scope == "local":
            return None, "local"
        if scope == "all":
            return None, None
        kind, _, ident = scope.partition(":")
        if kind == "user" and ident.isdigit():
            return int(ident), None
        if kind == "node" and ident:
            return None, ident
        return None, "local"

    def _logs(self, name, lines):
        core = self.core
        if name == "engine":
            return "\n".join(core.log_ring[-lines:])
        if name == "access":
            return tail_file(os.path.join(core.data_dir(), "logs", "access.log"), lines)
        if name in core.registry and core.procs:
            return tail_file(core.procs.log_path(name), lines)
        return ""

    def handle(self, method, path, query, body, ip, sess, node_token):
        """Returns (status, object). Called by the HTTP handler."""
        core, store = self.core, self.core.store

        def q(k, d=""):
            return (query.get(k) or [d])[0]

        # ---- node endpoints (token of a customer's small server)
        if path == "/api/node/heartbeat" and method == "POST":
            node = store.node_by_token(node_token)
            if not node:
                return 401, {"error": "Unknown server token."}
            return 200, store.heartbeat(node, body, ip)
        if path == "/api/node/report" and method == "GET":
            node = store.node_by_token(node_token)
            if not node:
                return 401, {"error": "Unknown server token."}
            rep = store.report(q("period", "week"), node_id=node["id"])
            user = store.get_user(node["user_id"]) or {}
            rep["user"] = {"username": user.get("username"), "quota_mb": user.get("quota_mb"),
                           "status": user.get("status")}
            rep["messages"] = store.inbox(node["user_id"], limit=10)
            rep["heat"] = store.heat(node_id=node["id"])
            return 200, rep

        if path == "/api/login" and method == "POST":
            return self.login(ip, body.get("username"), body.get("password"))

        if not sess:
            return 401, {"error": "Not signed in."}
        role, uid = sess["role"], sess["uid"]

        # ---------------------------------------------------- customer portal
        if path.startswith("/api/portal/"):
            if role != "customer":
                return 403, {"error": "Customer area."}
            sub = path[len("/api/portal/"):]
            user = store.get_user(uid)
            if not user:
                return 401, {"error": "Account no longer exists."}
            if sub == "overview" and method == "GET":
                nodes = store.list_nodes(uid)
                for n in nodes:
                    n.pop("sites", None)
                return 200, {"user": user, "nodes": nodes, "unread": store.unread_count(uid),
                             "storage_bytes": store.user_storage(uid),
                             "quota_bytes": user["quota_mb"] * 1024 * 1024}
            if sub == "report" and method == "GET":
                rep = store.report(q("period", "week"), user_id=uid)
                rep["heat"] = store.heat(user_id=uid)
                return 200, rep
            if sub == "messages" and method == "GET":
                return 200, {"messages": store.inbox(uid, limit=100)}
            if sub == "messages/read" and method == "POST":
                store.mark_read(uid, [int(i) for i in body.get("ids", []) if str(i).isdigit()])
                return 200, {"ok": True}
            if sub == "node/create" and method == "POST":
                nid, token, err = store.create_node(uid, str(body.get("name", "my-server")))
                if err:
                    return 400, {"error": err}
                store.audit(user["username"], "node_create", nid, ip)
                return 200, {"id": nid, "token": token, "join_code": self.join_code(token)}
            if sub == "node/reset" and method == "POST":
                node = store.get_node(str(body.get("id", "")))
                if not node or node["user_id"] != uid:
                    return 404, {"error": "No such server."}
                token = store.reset_node_token(node["id"])
                store.audit(user["username"], "node_reset", node["id"], ip)
                return 200, {"id": node["id"], "token": token, "join_code": self.join_code(token)}
            if sub == "node/delete" and method == "POST":
                node = store.get_node(str(body.get("id", "")))
                if not node or node["user_id"] != uid:
                    return 404, {"error": "No such server."}
                store.delete_node(node["id"])
                store.audit(user["username"], "node_delete", node["id"], ip)
                return 200, {"ok": True}
            if sub == "password" and method == "POST":
                good, _err = store.verify_user(user["username"], str(body.get("current", "")))
                if not good:
                    return 400, {"error": "Current password is wrong."}
                ok, err = store.set_password(uid, str(body.get("new", "")))
                if not ok:
                    return 400, {"error": err}
                store.audit(user["username"], "password_change", "", ip)
                return 200, {"ok": True}
            return 404, {"error": "Not found."}

        # -------------------------------------------------------- admin only
        if role != "admin":
            return 403, {"error": "Owner area."}

        if path == "/api/state" and method == "GET":
            limit = min(int(q("limit", "100") or 100), 500)
            return 200, core.snapshot(int(q("offset", "0") or 0), limit, q("q").strip().lower())
        if path == "/api/logs" and method == "GET":
            return 200, {"text": self._logs(q("name", "engine"), min(int(q("lines", "200")), 1000))}
        if path == "/api/site" and method == "GET":
            name = q("name")
            if core.registry.get(name, {}).get("type") != "site":
                return 404, {"error": "Not a site."}
            try:
                with open(core.site_index_path(name), "r", encoding="utf-8") as f:
                    return 200, {"content": f.read()}
            except OSError:
                return 200, {"content": ""}
        if path == "/api/site" and method == "POST":
            name, content = str(body.get("name", "")), str(body.get("content", ""))
            if core.registry.get(name, {}).get("type") != "site":
                return 404, {"error": "Not a site."}
            size = len(content.encode("utf-8"))
            if size > MAX_PAGE_BYTES:
                return 400, {"error": "Page is too large (2 MB max)."}
            ok, why = core.quota_ok(size)
            if not ok:
                return 403, {"error": why}
            p = core.site_index_path(name)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            core.log(f"Saved {name}.engine")
            return 200, {"ok": True}
        if path == "/api/site/protect" and method == "POST":
            ok, msg = core.protect_site(str(body.get("name", "")), str(body.get("user", "")),
                                        str(body.get("password", "")))
            if ok:
                store.audit("admin", "site_protect", str(body.get("name")), ip)
            return (200 if ok else 400), {"ok": ok, "message": msg, "error": None if ok else msg}
        if path == "/api/site/unprotect" and method == "POST":
            core.unprotect_site(str(body.get("name", "")))
            store.audit("admin", "site_unprotect", str(body.get("name")), ip)
            return 200, {"ok": True}
        if path == "/api/register" and method == "POST":
            ok, msg = core.register(body.get("name"), body.get("target", ""), body.get("command", ""),
                                    body.get("cwd", ""), body.get("autostart", True))
            if ok:
                store.audit("admin", "register", msg, ip)
            return (200 if ok else 400), {"ok": ok, "message": msg, "error": None if ok else msg}
        if path == "/api/unregister" and method == "POST":
            name = str(body.get("name", ""))
            core.drop_node(name)
            store.audit("admin", "unregister", name, ip)
            return 200, {"ok": True}
        if path in ("/api/app/start", "/api/app/stop", "/api/app/restart") and method == "POST":
            name = str(body.get("name", ""))
            if not core.procs or not core.registry.get(name, {}).get("command"):
                return 400, {"error": "This entry has no start command."}
            ok, msg = getattr(core.procs, path.rsplit("/", 1)[1])(name)
            return (200 if ok else 400), {"ok": ok, "message": msg, "error": None if ok else msg}

        # ---- reports
        if path == "/api/report" and method == "GET":
            user_id, node_id = self._scope(q("scope"))
            rep = store.report(q("period", "week"), user_id=user_id, node_id=node_id)
            rep["heat"] = store.heat(user_id=user_id, node_id=node_id)
            return 200, rep

        # ---- customers
        if path == "/api/users" and method == "GET":
            return 200, {"users": store.list_users()}
        if path == "/api/users" and method == "POST":
            new_id, err = store.create_user(body.get("username"), body.get("password"),
                                            body.get("email", ""), body.get("quota_mb", 1024),
                                            body.get("max_nodes", 1))
            if err:
                return 400, {"error": err}
            store.audit("admin", "user_create", body.get("username"), ip)
            return 200, {"id": new_id}
        if path == "/api/users/update" and method == "POST":
            fields = {k: body[k] for k in ("email", "quota_mb", "max_nodes", "status") if k in body}
            store.update_user(int(body.get("id", 0)), **fields)
            if fields.get("status") == "suspended":
                self.drop_sessions(uid=int(body.get("id", 0)))
            store.audit("admin", "user_update", f"{body.get('id')} {fields}", ip)
            return 200, {"ok": True}
        if path == "/api/users/password" and method == "POST":
            ok, err = store.set_password(int(body.get("id", 0)), str(body.get("password", "")))
            if not ok:
                return 400, {"error": err}
            self.drop_sessions(uid=int(body.get("id", 0)))
            store.audit("admin", "user_password_reset", str(body.get("id")), ip)
            return 200, {"ok": True}
        if path == "/api/users/delete" and method == "POST":
            self.drop_sessions(uid=int(body.get("id", 0)))
            store.delete_user(int(body.get("id", 0)))
            store.audit("admin", "user_delete", str(body.get("id")), ip)
            return 200, {"ok": True}

        # ---- customers' small servers
        if path == "/api/nodes" and method == "GET":
            nodes = store.list_nodes()
            users = {u["id"]: u["username"] for u in store.list_users()}
            for n in nodes:
                n["owner"] = users.get(n["user_id"], "?")
                n.pop("sites", None)
            return 200, {"nodes": nodes}
        if path == "/api/nodes/create" and method == "POST":
            nid, token, err = store.create_node(int(body.get("user_id", 0)), str(body.get("name", "server")))
            if err:
                return 400, {"error": err}
            store.audit("admin", "node_create", nid, ip)
            return 200, {"id": nid, "token": token, "join_code": self.join_code(token)}
        if path == "/api/nodes/reset" and method == "POST":
            token = store.reset_node_token(str(body.get("id", "")))
            if not token:
                return 404, {"error": "No such server."}
            store.audit("admin", "node_reset", str(body.get("id")), ip)
            return 200, {"token": token, "join_code": self.join_code(token)}
        if path == "/api/nodes/delete" and method == "POST":
            store.delete_node(str(body.get("id", "")))
            store.audit("admin", "node_delete", str(body.get("id")), ip)
            return 200, {"ok": True}

        # ---- private messages
        if path == "/api/messages" and method == "GET":
            return 200, {"messages": store.sent_messages()}
        if path == "/api/messages" and method == "POST":
            subject, text, kind = str(body.get("subject", "")), str(body.get("body", "")), body.get("kind", "info")
            if not subject.strip() or not text.strip():
                return 400, {"error": "Write a subject and a message."}
            to = str(body.get("to", "")).strip().lower()
            if to in ("", "*", "all"):
                n = store.broadcast(subject, text, kind)
            else:
                row = [u for u in store.list_users() if u["username"] == to]
                if not row:
                    return 404, {"error": "No such customer."}
                n = 1 if store.send_message(row[0]["id"], subject, text, kind) else 0
            store.audit("admin", "message", f"to {to or 'all'}: {subject[:60]}", ip)
            return 200, {"sent": n}

        # ---- security + settings
        if path == "/api/settings" and method == "GET":
            return 200, {"settings": core.settings, "tls": {
                "available": core.tls.available, "fingerprint": core.tls.ca_fingerprint(),
                "https_port": core.https_port, "admin_https_port": self.https_port}}
        if path == "/api/settings" and method == "POST":
            for k, v in body.items():
                ok, msg = core.set_setting(k, v)
                if not ok:
                    return 400, {"error": msg}
            store.audit("admin", "settings", json.dumps(body)[:200], ip)
            return 200, {"ok": True, "settings": core.settings}
        if path == "/api/audit" and method == "GET":
            return 200, {"audit": store.audit_tail(300)}
        if path == "/api/admin/password" and method == "POST":
            auth = read_auth(core.auth_path())
            if not auth or not check_auth(auth, str(body.get("current", ""))):
                return 400, {"error": "Current access key is wrong."}
            new = str(body.get("new", ""))
            missing = [t for t, ok in password_checks(new) if not ok]
            if missing:
                return 400, {"error": "New key still needs: " + "; ".join(missing)}
            write_auth(core.auth_path(), new)
            self.drop_sessions(role="admin")
            store.audit("admin", "admin_key_change", "", ip)
            return 200, {"ok": True}

        # ---- provider link (when this server is a customer's small server)
        if path == "/api/mother" and method == "GET":
            data = {"status": core.mother.status(), "state": core.mother_state,
                    "inbox": core.store.get_setting("inbox", []) or []}
            if data["status"]["joined"]:
                data["report"] = core.mother.report(q("period", "week"))
            return 200, data
        if path == "/api/mother/join" and method == "POST":
            ok, msg = core.mother.join(str(body.get("code", "")))
            return (200 if ok else 400), {"ok": ok, "message": msg, "error": None if ok else msg}
        if path == "/api/mother/leave" and method == "POST":
            core.mother.leave()
            return 200, {"ok": True}
        if path == "/api/mother/read" and method == "POST":
            inbox = core.store.get_setting("inbox", []) or []
            for m in inbox:
                m["read"] = True
            core.store.set_setting("inbox", inbox)
            return 200, {"ok": True}
        return 404, {"error": "Not found."}

    # ------------------------------------------------------------- handler
    def _make_handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def setup(self):
                if hasattr(self.request, "do_handshake"):
                    self.request.do_handshake()
                    self.request.settimeout(30)
                super().setup()

            def log_message(self, *args):
                pass

            def _secure(self):
                return isinstance(self.request, ssl.SSLSocket)

            def _send(self, code, body, ctype, extra=None):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy",
                                 "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                 "script-src 'self' 'unsafe-inline'; img-src 'self' data:")
                if self._secure():
                    self.send_header("Strict-Transport-Security", "max-age=31536000")
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def _json(self, code, obj):
                self._send(code, json.dumps(obj).encode(), "application/json")

            def _dispatch(self, method):
                url = urlparse(self.path)
                ip = self.client_address[0]
                loopback = ip.startswith("127.") or ip == "::1"
                if method == "GET" and url.path in ("/", "/index.html"):
                    if server.https_port and not self._secure() and not loopback:
                        host = (self.headers.get("Host") or "localhost").split(":")[0]
                        self._send(301, b"", "text/plain",
                                   {"Location": f"https://{host}:{server.https_port}/"})
                        return
                    self._send(200, DASHBOARD_HTML.encode("utf-8"), "text/html; charset=utf-8")
                    return
                if method == "GET" and url.path == "/ca.crt":
                    pem = server.core.tls.ca_pem()
                    if not pem:
                        self._json(404, {"error": "HTTPS is not set up."})
                        return
                    self._send(200, pem, "application/x-x509-ca-cert",
                               {"Content-Disposition": 'attachment; filename="engine-ca.crt"'})
                    return
                if not url.path.startswith("/api/"):
                    self._json(404, {"error": "Not found."})
                    return
                if server.https_port and not self._secure() and not loopback:
                    self._json(403, {"error": f"Use HTTPS on port {server.https_port}."})
                    return
                body = {}
                if method == "POST":
                    try:
                        length = int(self.headers.get("Content-Length") or 0)
                        if length > MAX_BODY:
                            self._json(413, {"error": "Request too large."})
                            return
                        body = json.loads(self.rfile.read(length) or b"{}") if length else {}
                    except Exception:
                        self._json(400, {"error": "Bad request."})
                        return
                auth = self.headers.get("Authorization", "")
                token = auth[7:] if auth.startswith("Bearer ") else ""
                sess = server.session(token)
                try:
                    code, obj = server.handle(method, url.path, parse_qs(url.query), body, ip,
                                              sess, token)
                except Exception as e:
                    code, obj = 500, {"error": str(e)}
                self._json(code, obj)

            def do_GET(self):
                self._dispatch("GET")

            def do_POST(self):
                self._dispatch("POST")

        return Handler
