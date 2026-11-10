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
    python engine_core.py join <code>            # report to your provider's mother server
    python engine_core.py leave                  # stop reporting
    python engine_core.py status
    python engine_core.py list

Use sudo / "Run as administrator" so it can bind ports 53 + 80 and edit the
hosts file. Without that it falls back to ports 5353 + 8080.
"""
import os
import re
import ssl
import sys
import json
import html
import socket
import base64
import hashlib
import secrets
import mimetypes
import collections
import select
import posixpath
import threading
import time
from urllib.parse import unquote

from engine_infra import (ProcessManager, system_metrics, password_checks, read_auth, write_auth,
                          hash_password, secure_file)
from engine_accounts import Store, HEARTBEAT_SECONDS
from engine_tls import TLSManager, secure_request

VERSION = "1.2.0"
DNS_PORTS = (53, 5353)
PROXY_PORTS = (80, 8080)
HTTPS_PORTS = (443, 8443)
MAX_APPS = 4600  # most sites one mother server will hold
HOSTS_LIMIT = 200  # above this many names the hosts file is skipped (use DNS)
DEFAULT_SETTINGS = {"force_https": False, "hsts": True, "rate_limit_per_min": 0,
                    "max_conn_per_ip": 200, "public_host": ""}
SUFFIXES = (".engine", ".localhost")
IDLE_TIMEOUT = 120  # seconds an idle proxied connection may stay open

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


def hmac_equal(a, b):
    import hmac
    return hmac.compare_digest(a, b)


def dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


class MotherLink:
    """Lets this (small) server report to a mother server: usage, storage,
    status. It receives the customer's quota, account state and private messages."""

    def __init__(self, core):
        self.core = core
        self.config = None
        self.running = False
        self.last_ok = None
        self.error = ""
        self.wake = threading.Event()

    def path(self):
        return os.path.join(self.core.data_dir(), "engine_mother.json")

    def load(self):
        try:
            with open(self.path(), "r") as f:
                cfg = json.load(f)
            if cfg.get("url") and cfg.get("token"):
                self.config = cfg
                return True
        except Exception:
            pass
        self.config = None
        return False

    def join(self, code):
        try:
            code = code.strip()
            data = json.loads(base64.urlsafe_b64decode((code + "=" * (-len(code) % 4)).encode()).decode())
            cfg = {"url": str(data["u"]).rstrip("/"), "token": str(data["t"]),
                   "ca": str(data.get("ca", ""))}
        except Exception:
            return False, "That join code is not valid."
        if not cfg["url"].startswith(("http://", "https://")) or not cfg["token"].startswith("eng_"):
            return False, "That join code is not valid."
        with open(self.path(), "w") as f:
            json.dump(cfg, f)
        secure_file(self.path())
        self.config, self.error = cfg, ""
        if self.core.is_running:
            self.start()
        self.wake.set()
        return True, "Joined. This server now reports to your provider."

    def leave(self):
        self.running = False
        self.wake.set()
        self.config = None
        self.last_ok = None
        try:
            os.remove(self.path())
        except OSError:
            pass
        self.core.mother_state.update({"suspended": False, "over_quota": False, "quota_bytes": 0})

    def status(self):
        joined = self.config is not None or os.path.exists(self.path())
        return {"joined": joined,
                "url": (self.config or {}).get("url"),
                "connected": bool(self.last_ok and time.time() - self.last_ok < HEARTBEAT_SECONDS * 3),
                "last_ok": self.last_ok, "error": self.error}

    def start(self):
        if self.running or not self.load():
            return
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False
        self.wake.set()

    def _call(self, path, method="GET", body=None):
        cfg = self.config
        headers = {"Authorization": "Bearer " + cfg["token"], "Content-Type": "application/json"}
        data = json.dumps(body).encode() if body is not None else None
        ca = cfg.get("ca", "").encode() or None
        status, raw = secure_request(cfg["url"] + path, method, headers, data,
                                     ca_pem=ca, verify=True, timeout=12)
        try:
            obj = json.loads(raw.decode() or "{}")
        except Exception:
            obj = {}
        return status, obj

    def beat(self):
        core = self.core
        core.store.flush_usage()
        inbox = core.store.get_setting("inbox", []) or []
        last_id = max([m.get("id", 0) for m in inbox] or [0])
        m = system_metrics(core.data_dir())
        payload = {
            "version": VERSION,
            "entries": len(core.registry),
            "storage_bytes": core.storage_bytes(force=True),
            "metrics": {"cpu": m["cpu"], "mem": (m["mem"] or {}).get("percent"),
                        "disk": (m["disk"] or {}).get("percent")},
            "sites": [{"name": n, "type": c.get("type", "app")}
                      for n, c in list(core.registry.items())[:300]],
            "usage": core.store.local_rows(2),
            "last_message_id": last_id,
        }
        status, resp = self._call("/api/node/heartbeat", "POST", payload)
        if status != 200:
            raise RuntimeError(resp.get("error") or f"mother server answered {status}")
        was_suspended = core.mother_state.get("suspended")
        core.mother_state.update({"suspended": bool(resp.get("suspended")),
                                  "over_quota": bool(resp.get("over_quota")),
                                  "quota_bytes": int(resp.get("quota_bytes") or 0),
                                  "storage_bytes": int(resp.get("storage_bytes") or 0)})
        new = resp.get("messages") or []
        if new:
            merged = {mm["id"]: mm for mm in inbox}
            for mm in new:
                merged.setdefault(mm["id"], {**mm, "read": False})
            keep = sorted(merged.values(), key=lambda x: x["id"], reverse=True)[:50]
            core.store.set_setting("inbox", keep)
        if bool(resp.get("suspended")) != bool(was_suspended):
            core.log("Account suspended by provider." if resp.get("suspended") else "Account active again.")
        self.last_ok, self.error = time.time(), ""

    def _loop(self):
        while self.running:
            try:
                self.beat()
            except Exception as e:
                self.error = str(e)[:120]
            self.wake.wait(HEARTBEAT_SECONDS)
            self.wake.clear()

    def report(self, period):
        if not self.load():
            return None
        status, obj = self._call("/api/node/report?period=" + period)
        return obj if status == 200 else None


class InfrastructureCore:
    def __init__(self, log_callback=print, registry_file=None, ports=None):
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
        self.lock = threading.RLock()
        self.log_lock = threading.Lock()
        self._synced_names = None
        self._warned_hosts = False

        self.procs = None if is_android() else ProcessManager(self)
        self.admin = None

        self.ports = {"dns": DNS_PORTS, "proxy": PROXY_PORTS, "https": HTTPS_PORTS, "admin": None}
        if ports:
            self.ports.update(ports)
        self.https_port = None
        self._store = None
        self._tls = None
        self.settings = dict(DEFAULT_SETTINGS)
        self._rate = {}
        self.mother_state = {"suspended": False, "over_quota": False,
                             "quota_bytes": 0, "storage_bytes": 0}
        self._storage_cache = (0.0, 0)
        self._warned_many = False
        self._ip_conns = {}
        self._auth_cache = {}
        self._auth_fails = {}
        self.mother = MotherLink(self)

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
        try:
            self.store.add_usage(name, req, nbytes)
        except Exception:
            pass

    # ------------------------------------------------- store / tls / settings
    @property
    def store(self):
        if self._store is None:
            os.makedirs(self.data_dir(), exist_ok=True)
            self._store = Store(os.path.join(self.data_dir(), "engine.db"))
        return self._store

    @property
    def tls(self):
        if self._tls is None:
            self._tls = TLSManager(self.data_dir(), self.log)
        return self._tls

    def load_settings(self):
        saved = self.store.get_setting("settings", {}) or {}
        self.settings = {**DEFAULT_SETTINGS, **{k: v for k, v in saved.items() if k in DEFAULT_SETTINGS}}

    def set_setting(self, key, value):
        if key not in DEFAULT_SETTINGS:
            return False, "Unknown setting."
        default = DEFAULT_SETTINGS[key]
        if isinstance(default, bool):
            value = bool(value)
        elif isinstance(default, int):
            value = max(0, int(value))
        else:
            value = str(value).strip()[:200]
        if key == "force_https" and value and not self.tls.available:
            return False, "HTTPS needs the 'cryptography' package (pip install cryptography)."
        self.settings[key] = value
        self.store.set_setting("settings", self.settings)
        return True, "Saved."

    def storage_bytes(self, force=False):
        """Total size of all hosted site folders (cached for 60 s)."""
        now = time.time()
        if not force and now - self._storage_cache[0] < 60:
            return self._storage_cache[1]
        total = sum(dir_size(c.get("path", "")) for c in list(self.registry.values())
                    if c.get("type") == "site")
        self._storage_cache = (now, total)
        return total

    def quota_ok(self, extra=0):
        """(allowed?, reason) for writing more files. Quota comes from the mother server."""
        st = self.mother_state
        if st.get("suspended"):
            return False, "This account is suspended."
        quota = st.get("quota_bytes") or 0
        used = st.get("storage_bytes") or self.storage_bytes()
        if quota and used + extra > quota:
            return False, "Storage quota reached."
        return True, ""

    def _rate_limited(self, ip):
        limit = self.settings.get("rate_limit_per_min", 0)
        if not limit:
            return False
        now = time.time()
        with self.lock:
            q = self._rate.setdefault(ip, collections.deque())
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= limit:
                return True
            q.append(now)
            if len(self._rate) > 20000:
                self._rate.clear()
        return False

    AUTH_ITER = 20000

    def protect_site(self, name, user, password):
        """Puts a username + password in front of a site or app (visitors must sign in)."""
        if name not in self.registry:
            return False, "No such site."
        if not re.fullmatch(r"[A-Za-z0-9_.-]{2,32}", user or ""):
            return False, "Username: 2-32 letters, numbers, . _ -"
        if len(password or "") < 8:
            return False, "Password must be at least 8 characters."
        salt = secrets.token_hex(16)
        with self.lock:
            self.registry[name]["auth"] = {"user": user, "salt": salt, "iter": self.AUTH_ITER,
                                           "hash": hash_password(password, salt, self.AUTH_ITER)}
            self.commit_registry_matrix()
        self._auth_cache.clear()
        return True, f"{name}.engine now asks visitors to sign in."

    def unprotect_site(self, name):
        with self.lock:
            if name in self.registry and self.registry[name].pop("auth", None) is not None:
                self.commit_registry_matrix()
                self._auth_cache.clear()

    def _basic_ok(self, header_buffer, auth, ip):
        """True if the request carries the right Basic credentials."""
        now = time.time()
        value = b""
        for line in header_buffer.split(b"\r\n")[1:]:
            if line.lower().startswith(b"authorization:"):
                value = line.split(b":", 1)[1].strip()
                break
        if not value.lower().startswith(b"basic "):
            return False
        key = hashlib.sha256(value).hexdigest()
        if self._auth_cache.get(key, 0) > now:
            return True
        with self.lock:
            fails = self._auth_fails.setdefault(ip, collections.deque())
            while fails and now - fails[0] > 60:
                fails.popleft()
            if len(fails) >= 10:
                return False
        try:
            user, _, pw = base64.b64decode(value[6:]).decode("utf-8").partition(":")
        except Exception:
            return False
        ok = (user == auth["user"] and
              hmac_equal(hash_password(pw, auth["salt"], auth["iter"]), auth["hash"]))
        if ok:
            if len(self._auth_cache) > 5000:
                self._auth_cache.clear()
            self._auth_cache[key] = now + 300
        else:
            with self.lock:
                self._auth_fails[ip].append(now)
        return ok

    # ------------------------------------------------------------ storage
    def set_storage_path(self, path):
        self.registry_file = path
        self.registry = self.load_registry_matrix()

    def _read_registry_file(self):
        """The saved registry, {} if there is none yet, or None if the file is
        unreadable right now (never treated as 'empty')."""
        if not os.path.exists(self.registry_file):
            return {}
        try:
            mtime = os.path.getmtime(self.registry_file)
            with open(self.registry_file, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            self._mtime = mtime
            return data
        except Exception:
            return None

    def load_registry_matrix(self):
        data = self._read_registry_file()
        return data if data is not None else {}

    def reload_if_changed(self):
        """Picks up edits made by another process (for example the command line)."""
        try:
            mtime = os.path.getmtime(self.registry_file)
        except OSError:
            return
        if mtime == self._mtime:
            return
        with self.lock:
            if mtime == self._mtime:
                return
            data = self._read_registry_file()
            if data is not None:  # a half-written or broken file never wipes the list
                self.registry = data

    def commit_registry_matrix(self):
        """Saves atomically: write a temp file, then swap it in. Readers never
        see a partial file, and a crash cannot corrupt the registry."""
        with self.lock:
            try:
                tmp = self.registry_file + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(self.registry, f, indent=1)
                os.replace(tmp, self.registry_file)
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
        with self.lock:
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
        with self.lock:
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
            with self.lock:
                self.registry.pop(subdomain, None)
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

    def https_url(self, name):
        if not self.https_port:
            return None
        suffix = "" if self.https_port == 443 else f":{self.https_port}"
        return f"https://{name}.engine{suffix}"

    def snapshot(self, offset=0, limit=None, q=""):
        self.reload_if_changed()
        port = self.proxy_port
        names = sorted(self.registry)
        if q:
            names = [n for n in names if q.lower() in n]
        page = names[offset:offset + limit] if limit else names[offset:]
        entries = []
        for name in page:
            cfg = self.registry[name]
            label, ok = self.entry_status(name)
            st = self.site_stats.get(name, {})
            entries.append({
                "name": name,
                "type": cfg.get("type", "app"),
                "port": cfg.get("port"),
                "path": cfg.get("path"),
                "command": cfg.get("command"),
                "autostart": cfg.get("autostart", False),
                "protected": bool(cfg.get("auth")),
                "status": label, "ok": ok,
                "url": self.url_for(name, local=False),
                "https_url": self.https_url(name),
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
            "https_port": self.https_port,
            "admin_https_port": getattr(self.admin, "https_port", None) if self.admin else None,
            "totals": {"requests": self.total_requests, "bytes": self.bytes_transferred,
                       "tunnels": self.active_tunnels},
            "metrics": system_metrics(self.data_dir()),
            "entry_count": len(self.registry), "matching": len(names),
            "storage_bytes": self.storage_bytes(),
            "settings": self.settings,
            "tls": {"available": self.tls.available, "ca_fingerprint": self.tls.ca_fingerprint()},
            "mother": self.mother.status(), "mother_state": self.mother_state,
            "entries": entries,
        }

    # ------------------------------------------------------- hosts file
    def sync_hosts_file(self):
        """Makes name.engine resolve on THIS machine (no DNS needed)."""
        if is_android():
            return
        names = frozenset(self.registry)
        if len(names) > HOSTS_LIMIT:
            if not self._warned_many:
                self._warned_many = True
                self.log(f"{len(names)} names: too many for the hosts file. "
                         "Other devices use the engine's DNS (port 53).")
            names_for_file = frozenset()
        else:
            names_for_file = names
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

        if names_for_file:
            kept.append(HOSTS_BEGIN)
            for name in sorted(names_for_file):
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
    def _flush_loop(self):
        while self.is_running:
            time.sleep(10)
            try:
                self.store.flush_usage()
            except Exception:
                pass

    def start(self):
        self.is_running = True
        self.started_at = time.time()
        try:
            self.load_settings()
        except Exception as e:
            self.log(f"Settings could not be loaded: {e}")
        threading.Thread(target=self.start_dns_daemon, daemon=True).start()
        threading.Thread(target=self.start_proxy_daemon, daemon=True).start()
        threading.Thread(target=self._watch_registry, daemon=True).start()
        threading.Thread(target=self._flush_loop, daemon=True).start()
        if not is_android():
            threading.Thread(target=self.start_https_daemon, daemon=True).start()
            try:
                from engine_admin import AdminServer
                self.admin = AdminServer(self)
                self.admin.start()
            except Exception as e:
                self.log(f"Dashboard unavailable: {e}")
            if self.procs:
                self.procs.autostart_all()
                self.procs.start_monitor()
            self.mother.start()

    def stop(self):
        self.is_running = False
        self.mother.stop()
        try:
            self.store.flush_usage()
        except Exception:
            pass
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
        ports = self.ports['dns'][-1:] if is_android() else self.ports['dns']
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
        ports = self.ports['proxy'][-1:] if is_android() else self.ports['proxy']
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

    def tls_server_context(self):
        if not self.tls.available:
            return None
        names = ["localhost", "engine"]
        host = socket.gethostname()
        if re.fullmatch(r"[A-Za-z0-9.-]+", host or ""):
            names.append(host)
        public = self.settings.get("public_host")
        if public and re.fullmatch(r"[A-Za-z0-9.-]+", public):
            names.append(public)
        ips = ["127.0.0.1", self.lan_ip]

        def known(server_name):
            n = split_name(server_name)
            return bool(n and n in self.registry)
        return self.tls.server_context(names, sorted(set(ips)), known)

    def start_https_daemon(self):
        ctx = self.tls_server_context()
        if ctx is None:
            self.log("HTTPS is off: install the 'cryptography' package (pip install cryptography).")
            return
        sock, port = self._bind(socket.SOCK_STREAM, self.ports["https"])
        if sock is None:
            self.log("HTTPS could not bind a port.")
            return
        sock.listen(512)
        self.https_port = port
        self.log(f"HTTPS on port {port}: open https://name.engine"
                 + ("" if port == 443 else f":{port}"))
        sock.settimeout(1.0)
        while self.is_running:
            try:
                conn, addr = sock.accept()
            except socket.timeout:
                continue
            except Exception:
                break
            threading.Thread(target=self._https_session, args=(ctx, conn, addr), daemon=True).start()
        sock.close()

    def _https_session(self, ctx, raw, addr):
        try:
            raw.settimeout(10)
            conn = ctx.wrap_socket(raw, server_side=True)
        except Exception:
            try:
                raw.close()
            except Exception:
                pass
            return
        with self.lock:
            self.active_tunnels += 1
        self.orchestrate_tunnel(conn, addr, https=True)

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

    def serve_static(self, conn, root, header_buffer, name, https=False):
        """Serves files from a folder. Returns the HTTP status code sent."""
        sec = ("X-Content-Type-Options: nosniff\r\n"
               "Referrer-Policy: strict-origin-when-cross-origin\r\n")
        if https and self.settings.get("hsts"):
            sec += "Strict-Transport-Security: max-age=31536000\r\n"

        def reply(code, text, body=b""):
            head = (f"HTTP/1.1 {code} {text}\r\nContent-Type: text/plain; charset=utf-8\r\n{sec}"
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
        if any(p.startswith(".") and p != ".well-known" for p in rel.split("/") if p):
            return reply(403, "Forbidden", b"Forbidden.")
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
        conn.sendall((f"HTTP/1.1 200 OK\r\nContent-Type: {ctype}\r\n{sec}"
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

    def orchestrate_tunnel(self, client_conn, client_addr, https=False):
        self.total_requests += 1
        upstream_conn = None
        counted = False
        ip = client_addr[0]
        try:
            with self.lock:
                self._ip_conns[ip] = self._ip_conns.get(ip, 0) + 1
                counted = True
                too_many = self._ip_conns[ip] > (self.settings.get("max_conn_per_ip") or 10 ** 9)
            if too_many or self._rate_limited(ip):
                client_conn.sendall(b"HTTP/1.1 429 Too Many Requests\r\nRetry-After: 30\r\n"
                                    b"Content-Length: 0\r\nConnection: close\r\n\r\n")
                self.access(ip, "", None, 429)
                return
            client_conn.settimeout(15)  # slow clients cannot hold a thread forever
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
            via_host = bool(target)

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
                if self.mother_state.get("suspended"):
                    page = b"This site is temporarily unavailable."
                    client_conn.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Type: text/plain\r\n"
                                        b"Connection: close\r\n\r\n" + page)
                    self.access(ip, host, target, 503)
                    return
                if via_host and not https and self.settings.get("force_https") and self.https_port:
                    port_part = "" if self.https_port == 443 else f":{self.https_port}"
                    self._redirect(client_conn, f"https://{host.split(':')[0]}{port_part}{req_path}")
                    self.access(ip, host, target, 301)
                    return
                if entry.get("auth"):
                    if via_host and not https and self.https_port:
                        port_part = "" if self.https_port == 443 else f":{self.https_port}"
                        self._redirect(client_conn, f"https://{host.split(':')[0]}{port_part}{req_path}")
                        self.access(ip, host, target, 301)
                        return
                    if not self._basic_ok(header_buffer, entry["auth"], ip):
                        client_conn.sendall(
                            b"HTTP/1.1 401 Unauthorized\r\n"
                            b'WWW-Authenticate: Basic realm="Private site", charset="UTF-8"\r\n'
                            b"Content-Type: text/plain\r\nContent-Length: 13\r\n"
                            b"Connection: close\r\n\r\nSign in first.")
                        self.access(ip, host, target, 401)
                        return
                self._count(target)
                if entry.get("type") == "site":
                    status = self.serve_static(client_conn, entry.get("path", ""),
                                               header_buffer, target, https)
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
                fl, sep2, rest2 = header_buffer.partition(b"\r\n")
                extra = (f"X-Forwarded-For: {ip}\r\n"
                         f"X-Forwarded-Proto: {'https' if https else 'http'}\r\n").encode()
                upstream_conn.sendall(fl + sep2 + extra + rest2)
                upstream_conn.settimeout(None)
                client_conn.settimeout(None)
                self.access(ip, host, target, 200)

                # Event-driven relay: sleeps until data arrives (no busy polling),
                # so hundreds of open connections cost almost no CPU.
                moved = 0
                last_activity = time.time()
                done = False
                while not done and self.is_running:
                    # TLS sockets may hold decrypted bytes that select() cannot see
                    readable = [c for c in (client_conn, upstream_conn)
                                if isinstance(c, ssl.SSLSocket) and c.pending()]
                    if not readable:
                        readable, _, _ = select.select([client_conn, upstream_conn], [], [], 1.0)
                    if not readable:
                        if time.time() - last_activity > IDLE_TIMEOUT:
                            break
                        continue
                    for src in readable:
                        dst = upstream_conn if src is client_conn else client_conn
                        chunk = src.recv(65536)
                        if not chunk:
                            done = True
                            break
                        dst.sendall(chunk)
                        moved += len(chunk)
                        last_activity = time.time()
                with self.lock:
                    self.bytes_transferred += moved
                self._count(target, nbytes=moved, req=0)
            else:
                client_conn.sendall(
                    b"HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\n"
                    b"Connection: close\r\n\r\n.engine: no app is bound to this name.")
                self.log(f"404 unbound name: {host or '(no host)'}")
                self.access(ip, host, None, 404)
        except (socket.timeout, ConnectionError, ssl.SSLError):
            pass  # slow, reset or dropped clients: normal on the internet
        except Exception as e:
            self.log(f"Tunnel closed: {e}")
        finally:
            if counted:
                with self.lock:
                    n = self._ip_conns.get(ip, 1) - 1
                    if n <= 0:
                        self._ip_conns.pop(ip, None)
                    else:
                        self._ip_conns[ip] = n
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
    elif cmd == "join" and len(argv) == 3:
        print(core.mother.join(argv[2])[1])
    elif cmd == "leave":
        core.mother.leave()
        print("This server no longer reports to a mother server.")
    elif cmd == "status":
        print(json.dumps({"mother": core.mother.status(), "entries": len(core.registry),
                          "tls_available": core.tls.available,
                          "ca_fingerprint": core.tls.ca_fingerprint()}, indent=2))
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
