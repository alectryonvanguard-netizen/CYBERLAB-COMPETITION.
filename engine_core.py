"""
.engine core (standard library only; psutil optional).

Run as a 24/7 server on a desktop, VPS or supercomputer:
    python engine_core.py setpassword            # create the access key (first time)
    python engine_core.py serve                  # run the engine + dashboard
    python engine_core.py site mysite            # new site with a starter page
    python engine_core.py site mysite ./webfolder  # host an existing folder
    python engine_core.py add clipsy 8001        # forward to an app on a port
    python engine_core.py app api "python app.py"  # engine runs + restarts the app
    python engine_core.py remove clipsy
    python engine_core.py list

Use sudo / "Run as administrator" so it can bind ports 53 + 80 and edit the
hosts file. Without that it falls back to ports 5353 + 8080.
"""
import os
import re
import sys
import json
import html
import socket
import mimetypes
import posixpath
import threading
import time
from urllib.parse import unquote

from engine_infra import ProcessManager, system_metrics, password_checks, read_auth, write_auth

VERSION = "1.0.0"
DNS_PORTS = (53, 5353)
PROXY_PORTS = (80, 8080)
MAX_APPS = 15
SUFFIXES = (".engine", ".localhost")

HOSTS_BEGIN = "# >>> .engine managed block >>>"
HOSTS_END = "# <<< .engine managed block <<<"


# ---------------------------------------------------------------- helpers
def is_android():
    return "ANDROID_ARGUMENT" in os.environ


def default_registry_path():
    """One shared data folder for the app screen and the server."""
    if is_android():
        base = os.environ.get("ANDROID_PRIVATE")
    else:
        base = os.environ.get("ENGINE_DATA")
    return os.path.join(base or os.path.dirname(os.path.abspath(__file__)),
                        "engine_registry.json")


def hosts_path():
    override = os.environ.get("ENGINE_HOSTS_FILE")
    if override:
        return override
    if os.name == "nt":
        return r"C:\Windows\System32\drivers\etc\hosts"
    return "/etc/hosts"


def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def split_name(host):
    """'clipsy.engine' -> 'clipsy'; 'clipsy.localhost:8080' -> 'clipsy'."""
    host = host.split(":")[0].strip().lower()
    for suffix in SUFFIXES:
        if host.endswith(suffix) and len(host) > len(suffix):
            return host[:-len(suffix)]
    return None


def valid_name(name):
    return bool(re.fullmatch(r"[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?", name))


def probe_port(port, timeout=0.3):
    """True if something is listening on 127.0.0.1:port (the app is running)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(("127.0.0.1", int(port)))
        return True
    except Exception:
        return False
    finally:
        s.close()


def starter_page(name):
    title = html.escape(name) + ".engine"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ margin:0; min-height:100vh; display:grid; place-items:center;
         background:#05080f; color:#d6f6ff; font-family:system-ui,sans-serif; }}
  main {{ text-align:center; padding:24px; }}
  h1 {{ color:#00f0ff; font-size:2rem; margin:0 0 8px; }}
  p {{ color:#5f7a94; margin:0; }}
  code {{ color:#00ff9c; }}
</style>
</head>
<body>
<main>
  <h1>{title}</h1>
  <p>This site is hosted by <code>.engine</code>. Replace this page from the app or dashboard.</p>
</main>
</body>
</html>
"""


class InfrastructureCore:
    def __init__(self, log_callback=print, registry_file=None):
        self._ext_log = log_callback
        self.log_ring = []
        self.registry_file = registry_file or default_registry_path()
        self._mtime = 0
        self.registry = self.load_registry_matrix()

        self.total_requests = 0
        self.bytes_transferred = 0
        self.active_tunnels = 0
        self.site_stats = {}

        self.dns_port = None
        self.proxy_port = None
        self.admin_port = None
        self.lan_ip = get_lan_ip()
        self.started_at = None

        self.is_running = False
        self.lock = threading.Lock()
        self.log_lock = threading.Lock()
        self._synced_names = None
        self._warned_hosts = False

        self.procs = None if is_android() else ProcessManager(self)
        self.admin = None

    # ------------------------------------------------------------ logging
    def log(self, text):
        self.log_ring.append(f"{time.strftime('%H:%M:%S')}  {text}")
        del self.log_ring[:-200]
        try:
            self._ext_log(text)
        except Exception:
            pass

    def data_dir(self):
        return os.path.dirname(os.path.abspath(self.registry_file))

    def auth_path(self):
        return os.path.join(self.data_dir(), "engine_auth.json")

    def access(self, ip, host, target, status):
        """Persistent access log with simple size rotation."""
        line = (f"{time.strftime('%Y-%m-%d %H:%M:%S')} {ip} {host or '-'} "
                f"-> {target or '-'} {status}\n")
        path = os.path.join(self.data_dir(), "logs", "access.log")
        with self.log_lock:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                if os.path.exists(path) and os.path.getsize(path) > 5 * 1024 * 1024:
                    os.replace(path, path + ".1")
                with open(path, "a", encoding="utf-8") as f:
                    f.write(line)
            except OSError:
                pass

    def _count(self, name, nbytes=0, req=1):
        with self.lock:
            st = self.site_stats.setdefault(name, {"requests": 0, "bytes": 0, "last": None})
            st["requests"] += req
            st["bytes"] += nbytes
            st["last"] = time.time()

    # ------------------------------------------------------------ storage
    def set_storage_path(self, path):
        self.registry_file = path
        self.registry = self.load_registry_matrix()

    def load_registry_matrix(self):
        if os.path.exists(self.registry_file):
            try:
                self._mtime = os.path.getmtime(self.registry_file)
                with open(self.registry_file, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def reload_if_changed(self):
        try:
            mtime = os.path.getmtime(self.registry_file)
        except OSError:
            return
        if mtime != self._mtime:
            self.registry = self.load_registry_matrix()

    def commit_registry_matrix(self):
        with self.lock:
            try:
                with open(self.registry_file, "w") as f:
                    json.dump(self.registry, f, indent=4)
                self._mtime = os.path.getmtime(self.registry_file)
            except Exception as e:
                self.log(f"STORAGE ERROR: {e}")

    # -------------------------------------------------------- registering
    def add_node(self, subdomain, port, command=None, cwd=None, autostart=True):
        if subdomain not in self.registry and len(self.registry) >= MAX_APPS:
            return False
        entry = {"type": "app", "port": port, "created_at": time.time()}
        if command:
            entry.update({"command": command, "cwd": cwd, "autostart": bool(autostart)})
        self.registry[subdomain] = entry
        self.commit_registry_matrix()
        self.sync_hosts_file()
        return True

    def sites_root(self):
        return os.path.join(self.data_dir(), "sites")

    def add_site(self, subdomain, path=None):
        """Registers a website hosted by the engine itself.
        path=None creates a managed folder with a starter page."""
        if subdomain not in self.registry and len(self.registry) >= MAX_APPS:
            return False
        managed = path is None
        if managed:
            path = os.path.join(self.sites_root(), subdomain)
            os.makedirs(path, exist_ok=True)
            index = os.path.join(path, "index.html")
            if not os.path.exists(index):
                with open(index, "w", encoding="utf-8") as f:
                    f.write(starter_page(subdomain))
        self.registry[subdomain] = {"type": "site", "path": path, "managed": managed,
                                    "created_at": time.time()}
        self.commit_registry_matrix()
        self.sync_hosts_file()
        return True

    def site_index_path(self, subdomain):
        entry = self.registry.get(subdomain, {})
        return os.path.join(entry.get("path", ""), "index.html")

    def free_port(self):
        used = {e.get("port") for e in self.registry.values()}
        for port in range(8001, 9000):
            if port not in used and not probe_port(port):
                return port
        return 0

    def register(self, name, target="", command="", cwd="", autostart=True):
        """Single entry point used by the app, the dashboard and the CLI.
        target: '' = new site | digits = app on that port | folder path = site.
        command (desktop): the engine starts and supervises the app itself."""
        name = (name or "").strip().lower().replace(".engine", "")
        target = (target or "").strip()
        command = (command or "").strip()
        cwd = (cwd or "").strip()
        if not valid_name(name):
            return False, "Name: letters, numbers and dashes only."
        if name not in self.registry and len(self.registry) >= MAX_APPS:
            return False, f"Limit reached ({MAX_APPS} entries)."

        if command:
            if is_android():
                return False, "Managed apps run on the desktop engine."
            port = int(target) if target.isdigit() else self.free_port()
            if not (1 <= port <= 65535):
                return False, "Port must be between 1 and 65535."
            if cwd and not os.path.isdir(cwd):
                return False, "Working folder not found."
            self.add_node(name, port, command, cwd or None, autostart)
            if self.procs and self.is_running:
                self.procs.start(name)
            return True, f"Registered {name}.engine (managed app on port {port})"

        if target == "":
            self.add_site(name)
            return True, f"Registered {name}.engine (new site)"
        if target.isdigit():
            port = int(target)
            if not (1 <= port <= 65535):
                return False, "Port must be between 1 and 65535."
            self.add_node(name, port)
            return True, f"Registered {name}.engine (app on port {port})"
        folder = os.path.abspath(os.path.expanduser(target))
        if not os.path.isdir(folder):
            return False, "Folder not found."
        self.add_site(name, folder)
        return True, f"Registered {name}.engine (site from folder)"

    def drop_node(self, subdomain):
        if subdomain in self.registry:
            if self.procs:
                self.procs.stop(subdomain)
            del self.registry[subdomain]
            self.commit_registry_matrix()
            self.sync_hosts_file()

    # ---------------------------------------------------------- reporting
    def url_for(self, name, local=None):
        """The address that works on this device. Android cannot resolve .engine
        names, so there it shows the .localhost form."""
        if local is None:
            local = is_android()
        domain = "localhost" if local else "engine"
        suffix = "" if self.proxy_port == 80 else f":{self.proxy_port or PROXY_PORTS[-1]}"
        return f"http://{name}.{domain}{suffix}"

    def entry_status(self, name):
        """(label, ok) describing whether an entry is actually serving."""
        cfg = self.registry.get(name, {})
        if cfg.get("type") == "site":
            ok = os.path.isdir(cfg.get("path", ""))
            return ("LIVE" if ok else "FOLDER MISSING"), ok
        if cfg.get("command") and self.procs:
            st = self.procs.status(name)
            if not st["running"]:
                return ("CRASH LOOP" if st["gave_up"] else "STOPPED"), False
            if probe_port(cfg["port"]):
                return "LIVE", True
            return "STARTING", False
        ok = probe_port(cfg.get("port", 0))
        return ("LIVE" if ok else "OFFLINE"), ok

    def snapshot(self):
        self.reload_if_changed()
        port = self.proxy_port
        entries = []
        for name, cfg in self.registry.items():
            label, ok = self.entry_status(name)
            st = self.site_stats.get(name, {})
            entries.append({
                "name": name,
                "type": cfg.get("type", "app"),
                "port": cfg.get("port"),
                "path": cfg.get("path"),
                "command": cfg.get("command"),
                "autostart": cfg.get("autostart", False),
                "status": label, "ok": ok,
                "url": self.url_for(name, local=False),
                "preview": f"http://{self.lan_ip}:{port}/_/{name}/" if port else None,
                "requests": st.get("requests", 0),
                "bytes": st.get("bytes", 0),
                "last": st.get("last"),
                "process": (self.procs.status(name)
                            if self.procs and cfg.get("command") else None),
            })
        return {
            "version": VERSION,
            "uptime": int(time.time() - self.started_at) if self.started_at else 0,
            "lan_ip": self.lan_ip,
            "proxy_port": port, "dns_port": self.dns_port, "admin_port": self.admin_port,
            "totals": {"requests": self.total_requests, "bytes": self.bytes_transferred,
                       "tunnels": self.active_tunnels},
            "metrics": system_metrics(self.data_dir()),
            "entries": entries,
        }

    # ------------------------------------------------------- hosts file
    def sync_hosts_file(self):
        """Makes name.engine resolve on THIS machine (no DNS needed)."""
        if is_android():
            return
        names = frozenset(self.registry)
        path = hosts_path()
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                original = f.read()
        except OSError:
            return

        kept, skipping = [], False
        for line in original.splitlines():
            if line.strip() == HOSTS_BEGIN:
                skipping = True
                continue
            if line.strip() == HOSTS_END:
                skipping = False
                continue
            if not skipping:
                kept.append(line)

        if names:
            kept.append(HOSTS_BEGIN)
            for name in sorted(names):
                kept.append(f"127.0.0.1 {name}.engine")
            kept.append(HOSTS_END)

        updated = "\n".join(kept) + "\n"
        if updated == original:
            self._synced_names = names
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(updated)
            self._synced_names = names
            self.log(f"Hosts file updated ({len(names)} names)")
        except OSError:
            if not self._warned_hosts:
                self._warned_hosts = True
                self.log("Cannot edit hosts file. Run as administrator/root so "
                         "name.engine opens in Chrome on this machine.")

    def _watch_registry(self):
        while self.is_running:
            self.reload_if_changed()
            if frozenset(self.registry) != self._synced_names:
                self.sync_hosts_file()
            time.sleep(2)

    # ------------------------------------------------------------ start
    def start(self):
        self.is_running = True
        self.started_at = time.time()
        threading.Thread(target=self.start_dns_daemon, daemon=True).start()
        threading.Thread(target=self.start_proxy_daemon, daemon=True).start()
        threading.Thread(target=self._watch_registry, daemon=True).start()
        if not is_android():
            try:
                from engine_admin import AdminServer
                self.admin = AdminServer(self)
                self.admin.start()
            except Exception as e:
                self.log(f"Dashboard unavailable: {e}")
            if self.procs:
                self.procs.autostart_all()
                self.procs.start_monitor()

    def stop(self):
        self.is_running = False
        if self.admin:
            self.admin.stop()
        if self.procs:
            self.procs.shutdown()

    def _bind(self, kind, ports):
        for port in ports:
            sock = socket.socket(socket.AF_INET, kind)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", port))
                return sock, port
            except OSError:
                sock.close()
        return None, None

    # -------------------------------------------------------------- DNS
    def start_dns_daemon(self):
        ports = DNS_PORTS[-1:] if is_android() else DNS_PORTS
        dns_sock, port = self._bind(socket.SOCK_DGRAM, ports)
        if dns_sock is None:
            self.log("DNS could not bind any port.")
            return
        self.dns_port = port
        if port == 53:
            self.log("DNS on port 53. Other devices can use this machine as their DNS server.")
        else:
            self.log(f"DNS on port {port}. Other devices need port 53 (run as admin/root).")

        dns_sock.settimeout(1.0)
        while self.is_running:
            try:
                data, addr = dns_sock.recvfrom(512)
            except socket.timeout:
                continue
            except Exception:
                break
            threading.Thread(target=self.process_dns_query,
                             args=(dns_sock, data, addr), daemon=True).start()
        dns_sock.close()

    def process_dns_query(self, sock, data, addr):
        try:
            transaction_id = data[:2]
            query_body = b""
            idx = 12
            while data[idx] != 0:
                length = data[idx]
                query_body += data[idx:idx + length + 1]
                idx += length + 1
            query_body += b"\x00"

            if b"\x06engine" not in query_body:
                return

            qtype = data[idx + 1:idx + 3]
            question = query_body + data[idx + 1:idx + 5]

            if qtype == b"\x00\x01":  # A record
                ip = "127.0.0.1" if addr[0].startswith("127.") else self.lan_ip
                counters = b"\x00\x01\x00\x01\x00\x00\x00\x00"
                answer = (b"\xc0\x0c" + b"\x00\x01\x00\x01" + b"\x00\x00\x00\x3c"
                          + b"\x00\x04" + socket.inet_aton(ip))
            else:  # AAAA etc: empty answer, name exists
                counters = b"\x00\x01\x00\x00\x00\x00\x00\x00"
                answer = b""

            sock.sendto(transaction_id + b"\x81\x80" + counters + question + answer, addr)
        except Exception:
            pass

    # ------------------------------------------------------------ proxy
    def start_proxy_daemon(self):
        ports = PROXY_PORTS[-1:] if is_android() else PROXY_PORTS
        proxy_sock, port = self._bind(socket.SOCK_STREAM, ports)
        if proxy_sock is None:
            self.log("PROXY could not bind any port.")
            return
        proxy_sock.listen(512)
        self.proxy_port = port
        if port == 80:
            self.log("Proxy on port 80: just open http://name.engine")
        else:
            self.log(f"Proxy on port {port}: open http://name.engine:{port}")

        proxy_sock.settimeout(1.0)
        while self.is_running:
            try:
                client_conn, client_addr = proxy_sock.accept()
            except socket.timeout:
                continue
            except Exception:
                break
            with self.lock:
                self.active_tunnels += 1
            threading.Thread(target=self.orchestrate_tunnel,
                             args=(client_conn, client_addr), daemon=True).start()
        proxy_sock.close()

    def _redirect(self, conn, location):
        conn.sendall((f"HTTP/1.1 301 Moved Permanently\r\nLocation: {location}\r\n"
                      "Content-Length: 0\r\nConnection: close\r\n\r\n").encode())

    def serve_index(self, conn):
        items = "".join(
            f'<li><a href="/_/{html.escape(n)}/">{html.escape(n)}.engine</a> '
            f'<small>{html.escape(self.entry_status(n)[0])}</small></li>'
            for n in sorted(self.registry)) or "<li>Nothing registered yet.</li>"
        body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>.engine</title>
<style>body{{margin:0;padding:32px;background:#05080f;color:#d6f6ff;font-family:system-ui,sans-serif}}
h1{{color:#00f0ff}}a{{color:#00f0ff;font-size:1.1rem}}small{{color:#5f7a94;margin-left:8px}}
li{{margin:10px 0}}</style></head><body><h1>&gt; .engine</h1><ul>{items}</ul></body></html>""".encode()
        conn.sendall((f"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                      f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode() + body)

    def serve_static(self, conn, root, header_buffer, name):
        """Serves files from a folder. Returns the HTTP status code sent."""
        def reply(code, text, body=b""):
            head = (f"HTTP/1.1 {code} {text}\r\nContent-Type: text/plain; charset=utf-8\r\n"
                    f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode()
            conn.sendall(head + body)
            return code

        conn.settimeout(15)
        try:
            first = header_buffer.split(b"\r\n", 1)[0].decode("latin-1")
            method, target, _ = first.split(" ", 2)
        except ValueError:
            return reply(400, "Bad Request", b"Bad request.")
        if method not in ("GET", "HEAD"):
            return reply(405, "Method Not Allowed", b"Only GET and HEAD are supported.")

        url_path = unquote(target.split("?", 1)[0].split("#", 1)[0])
        rel = posixpath.normpath(url_path).lstrip("/")
        root_real = os.path.realpath(root)
        full = os.path.realpath(os.path.join(root_real, rel))
        if full != root_real and not full.startswith(root_real + os.sep):
            return reply(403, "Forbidden", b"Forbidden.")
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.isfile(full):
            return reply(404, "Not Found", b"Page not found.")

        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        size = os.path.getsize(full)
        conn.sendall((f"HTTP/1.1 200 OK\r\nContent-Type: {ctype}\r\n"
                      f"Content-Length: {size}\r\nConnection: close\r\n\r\n").encode())
        if method == "GET":
            with open(full, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    conn.sendall(chunk)
            with self.lock:
                self.bytes_transferred += size
            self._count(name, nbytes=size, req=0)
        return 200

    def orchestrate_tunnel(self, client_conn, client_addr):
        self.total_requests += 1
        upstream_conn = None
        ip = client_addr[0]
        try:
            header_buffer = client_conn.recv(8192)
            if not header_buffer:
                return
            with self.lock:
                self.bytes_transferred += len(header_buffer)
            self.reload_if_changed()

            host = ""
            for line in header_buffer.split(b"\r\n"):
                if line.lower().startswith(b"host:"):
                    host = line.split(b":", 1)[1].decode("utf-8", "ignore").strip()
                    break
            target = split_name(host) if host else None

            first, sep, rest = header_buffer.partition(b"\r\n")
            parts = first.decode("latin-1").split(" ")
            req_path = parts[1] if len(parts) >= 3 else "/"
            path_only, q, query = req_path.partition("?")

            if not target:
                # path gateway: http://<ip>:<port>/_/<name>/  (works without DNS)
                m = re.match(r"^/_/([a-z0-9-]+)(/.*)?$", path_only)
                if m and m.group(1) in self.registry:
                    if m.group(2) is None:
                        self._redirect(client_conn, f"/_/{m.group(1)}/" + q + query)
                        self.access(ip, host, m.group(1), 301)
                        return
                    target = m.group(1)
                    parts[1] = m.group(2) + q + query
                    header_buffer = " ".join(parts).encode("latin-1") + sep + rest
                elif path_only in ("/", ""):
                    self.serve_index(client_conn)
                    self.access(ip, host, "(index)", 200)
                    return

            if target and target in self.registry:
                entry = self.registry[target]
                self._count(target)
                if entry.get("type") == "site":
                    status = self.serve_static(client_conn, entry.get("path", ""),
                                               header_buffer, target)
                    self.access(ip, host, target, status)
                    return

                upstream_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                upstream_conn.settimeout(5)
                try:
                    upstream_conn.connect(("127.0.0.1", entry["port"]))
                except OSError:
                    msg = b"This app is not running right now."
                    client_conn.sendall(
                        b"HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/plain\r\n"
                        b"Connection: close\r\n\r\n" + msg)
                    self.log(f"502 {target}.engine app is offline")
                    self.access(ip, host, target, 502)
                    return
                upstream_conn.sendall(header_buffer)
                upstream_conn.setblocking(False)
                client_conn.setblocking(False)
                self.access(ip, host, target, 200)

                moved = 0
                active_tunnel = True
                while active_tunnel and self.is_running:
                    busy = False
                    try:
                        chunk = client_conn.recv(65536)
                        if chunk:
                            upstream_conn.sendall(chunk)
                            moved += len(chunk)
                            busy = True
                        else:
                            active_tunnel = False
                    except BlockingIOError:
                        pass
                    try:
                        chunk = upstream_conn.recv(65536)
                        if chunk:
                            client_conn.sendall(chunk)
                            moved += len(chunk)
                            busy = True
                        else:
                            active_tunnel = False
                    except BlockingIOError:
                        pass
                    if not busy:
                        time.sleep(0.003)
                with self.lock:
                    self.bytes_transferred += moved
                self._count(target, nbytes=moved, req=0)
            else:
                client_conn.sendall(
                    b"HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\n"
                    b"Connection: close\r\n\r\n.engine: no app is bound to this name.")
                self.log(f"404 unbound name: {host or '(no host)'}")
                self.access(ip, host, None, 404)
        except Exception as e:
            self.log(f"Tunnel closed: {e}")
        finally:
            for s in (upstream_conn, client_conn):
                if s is not None:
                    try:
                        s.close()
                    except Exception:
                        pass
            with self.lock:
                self.active_tunnels -= 1


# ---------------------------------------------------------------- CLI
def _log(text):
    print(f"{time.strftime('%H:%M:%S')}  {text}", flush=True)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "serve"
    core = InfrastructureCore(_log)

    if cmd == "serve":
        if not read_auth(core.auth_path()):
            _log("No access key yet: the dashboard stays locked. "
                 "Run: python engine_core.py setpassword")
        core.start()
        _log("Engine running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            core.stop()
    elif cmd == "setpassword":
        import getpass
        pw = getpass.getpass("New access key: ")
        again = getpass.getpass("Repeat access key: ")
        missing = [t for t, ok in password_checks(pw) if not ok]
        if missing:
            print("Not strong enough. Still needed: " + "; ".join(missing))
        elif pw != again:
            print("The two keys do not match.")
        else:
            write_auth(core.auth_path(), pw)
            print("Access key saved.")
    elif cmd == "add" and len(argv) == 4 and argv[3].isdigit():
        print(core.register(argv[2], argv[3])[1])
    elif cmd == "site" and len(argv) in (3, 4):
        print(core.register(argv[2], argv[3] if len(argv) == 4 else "")[1])
    elif cmd == "app" and len(argv) in (4, 5):
        print(core.register(argv[2], argv[4] if len(argv) == 5 else "", command=argv[3])[1])
    elif cmd == "remove" and len(argv) == 3:
        core.drop_node(argv[2].lower().replace(".engine", ""))
        print("Removed.")
    elif cmd == "list":
        for name, cfg in core.registry.items():
            if cfg.get("type") == "site":
                print(f"{name}.engine -> site {cfg['path']}")
            elif cfg.get("command"):
                print(f"{name}.engine -> managed app :{cfg['port']}  ({cfg['command']})")
            else:
                print(f"{name}.engine -> app 127.0.0.1:{cfg['port']}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
