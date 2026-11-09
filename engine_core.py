"""
.engine core (standard library only, no Kivy needed).

Run as a 24/7 server on a desktop, VPS or supercomputer:
    python engine_core.py serve
    python engine_core.py site mysite            # new site with a starter page
    python engine_core.py site mysite ./webfolder  # host an existing folder
    python engine_core.py add clipsy 8001        # forward to an app on a port
    python engine_core.py remove clipsy
    python engine_core.py list

Use sudo / "Run as administrator" so it can bind port 53 + 80 and edit the
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

DNS_PORTS = (53, 5353)
PROXY_PORTS = (80, 8080)
MAX_APPS = 15
SUFFIXES = (".engine", ".localhost")

HOSTS_BEGIN = "# >>> .engine managed block >>>"
HOSTS_END = "# <<< .engine managed block <<<"


def is_android():
    return "ANDROID_ARGUMENT" in os.environ


def default_registry_path():
    """One shared data folder for the app screen and the background service."""
    if is_android():
        base = os.environ.get("ANDROID_PRIVATE")
    else:
        base = os.environ.get("ENGINE_DATA")
    return os.path.join(base or os.path.dirname(os.path.abspath(__file__)),
                        "engine_registry.json")


def valid_name(name):
    return bool(re.fullmatch(r"[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?", name))


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
  <p>This site is hosted by <code>.engine</code>. Replace this page from the app.</p>
</main>
</body>
</html>
"""


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


class InfrastructureCore:
    def __init__(self, log_callback=print, registry_file=None):
        self.log = log_callback
        self.registry_file = registry_file or default_registry_path()
        self._mtime = 0
        self.registry = self.load_registry_matrix()

        self.total_requests = 0
        self.bytes_transferred = 0
        self.active_tunnels = 0

        self.dns_port = None
        self.proxy_port = None
        self.lan_ip = get_lan_ip()

        self.is_running = False
        self.lock = threading.Lock()
        self._synced_names = None
        self._warned_hosts = False

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

    def add_node(self, subdomain, port):
        if subdomain not in self.registry and len(self.registry) >= MAX_APPS:
            return False
        self.registry[subdomain] = {"type": "app", "port": port, "created_at": time.time()}
        self.commit_registry_matrix()
        self.sync_hosts_file()
        return True

    def sites_root(self):
        return os.path.join(os.path.dirname(self.registry_file), "sites")

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

    def drop_node(self, subdomain):
        if subdomain in self.registry:
            del self.registry[subdomain]
            self.commit_registry_matrix()
            self.sync_hosts_file()

    def url_for(self, name, local=None):
        """The address that works on this device. Android cannot resolve .engine
        names, so there it shows the .localhost form."""
        if local is None:
            local = is_android()
        domain = "localhost" if local else "engine"
        suffix = "" if self.proxy_port == 80 else f":{self.proxy_port or PROXY_PORTS[-1]}"
        return f"http://{name}.{domain}{suffix}"

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
        threading.Thread(target=self.start_dns_daemon, daemon=True).start()
        threading.Thread(target=self.start_proxy_daemon, daemon=True).start()
        threading.Thread(target=self._watch_registry, daemon=True).start()

    def stop(self):
        self.is_running = False

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
        proxy_sock.listen(200)
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

    def serve_static(self, conn, root, header_buffer, name):
        def reply(code, text, body=b"", ctype="text/plain; charset=utf-8", head=False):
            head_bytes = (f"HTTP/1.1 {code} {text}\r\nContent-Type: {ctype}\r\n"
                          f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode()
            conn.sendall(head_bytes + (b"" if head else body))

        conn.settimeout(15)
        try:
            first = header_buffer.split(b"\r\n", 1)[0].decode("latin-1")
            method, target, _ = first.split(" ", 2)
        except ValueError:
            reply(400, "Bad Request", b"Bad request.")
            return
        if method not in ("GET", "HEAD"):
            reply(405, "Method Not Allowed", b"Only GET and HEAD are supported.")
            return

        url_path = unquote(target.split("?", 1)[0].split("#", 1)[0])
        rel = posixpath.normpath(url_path).lstrip("/")
        root_real = os.path.realpath(root)
        full = os.path.realpath(os.path.join(root_real, rel))
        if full != root_real and not full.startswith(root_real + os.sep):
            reply(403, "Forbidden", b"Forbidden.")
            return
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.isfile(full):
            reply(404, "Not Found", b"Page not found.")
            self.log(f"404 {name}.engine {url_path}")
            return

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
        if url_path in ("/", "/index.html"):
            self.log(f"200 {name}.engine (site)")

    def orchestrate_tunnel(self, client_conn, client_addr):
        self.total_requests += 1
        upstream_conn = None
        try:
            header_buffer = client_conn.recv(4096)
            if not header_buffer:
                return
            with self.lock:
                self.bytes_transferred += len(header_buffer)

            self.reload_if_changed()

            target = None
            for line in header_buffer.split(b"\r\n"):
                if line.lower().startswith(b"host:"):
                    target = split_name(line.split(b":", 1)[1].decode("utf-8", "ignore"))
                    break

            if target and target in self.registry:
                entry = self.registry[target]
                if entry.get("type") == "site":
                    self.serve_static(client_conn, entry.get("path", ""), header_buffer, target)
                    return
                target_port = entry["port"]
                upstream_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                upstream_conn.settimeout(5)
                upstream_conn.connect(("127.0.0.1", target_port))
                upstream_conn.sendall(header_buffer)
                upstream_conn.setblocking(False)
                client_conn.setblocking(False)
                self.log(f"200 {target}.engine -> :{target_port}")

                active_tunnel = True
                while active_tunnel and self.is_running:
                    busy = False
                    try:
                        chunk = client_conn.recv(4096)
                        if chunk:
                            upstream_conn.sendall(chunk)
                            with self.lock:
                                self.bytes_transferred += len(chunk)
                            busy = True
                        else:
                            active_tunnel = False
                    except BlockingIOError:
                        pass
                    try:
                        chunk = upstream_conn.recv(4096)
                        if chunk:
                            client_conn.sendall(chunk)
                            with self.lock:
                                self.bytes_transferred += len(chunk)
                            busy = True
                        else:
                            active_tunnel = False
                    except BlockingIOError:
                        pass
                    if not busy:
                        time.sleep(0.005)
            else:
                body = b".engine: no app is bound to this name."
                client_conn.sendall(
                    b"HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\n"
                    b"Connection: close\r\n\r\n" + body)
                self.log(f"404 unbound name: {target or '(no .engine host)'}")
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
        core.start()
        _log("Engine running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            core.stop()
    elif cmd == "add" and len(argv) == 4 and argv[3].isdigit():
        name = argv[2].lower().replace(".engine", "")
        if valid_name(name) and core.add_node(name, int(argv[3])):
            print(f"Bound {name}.engine -> app on port {argv[3]}")
        else:
            print("Invalid name or limit reached.")
    elif cmd == "site" and len(argv) in (3, 4):
        name = argv[2].lower().replace(".engine", "")
        folder = os.path.abspath(os.path.expanduser(argv[3])) if len(argv) == 4 else None
        if not valid_name(name):
            print("Name: letters, numbers and dashes only.")
        elif folder and not os.path.isdir(folder):
            print("Folder not found.")
        elif core.add_site(name, folder):
            print(f"Hosting {name}.engine from {folder or 'a new managed folder'}")
        else:
            print(f"Limit reached ({MAX_APPS}).")
    elif cmd == "remove" and len(argv) == 3:
        core.drop_node(argv[2].lower().replace(".engine", ""))
        print("Removed.")
    elif cmd == "list":
        for name, cfg in core.registry.items():
            if cfg.get("type") == "site":
                print(f"{name}.engine -> site {cfg['path']}")
            else:
                print(f"{name}.engine -> app 127.0.0.1:{cfg['port']}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
