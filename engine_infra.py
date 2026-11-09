"""
.engine infrastructure helpers (standard library only; psutil is optional):
  - access-key security shared by the app, the server and the dashboard
  - system + GPU metrics
  - application process manager (start / stop / auto-restart)
  - a small HTTP client the phone uses to monitor a desktop engine
"""
import os
import sys
import json
import time
import hmac
import shutil
import signal
import hashlib
import secrets
import collections
import subprocess
import threading
import urllib.error
import urllib.request

try:
    import psutil as _psutil
except Exception:
    _psutil = None

# =====================================================================
# SECURITY
# =====================================================================
ITERATIONS = 150000
MIN_LENGTH = 8
MAX_FAILS = 5
LOCK_SECONDS = 30


def password_checks(pw):
    """Returns [(requirement text, satisfied?)] for the access-key rules."""
    return [
        (f"At least {MIN_LENGTH} characters", len(pw) >= MIN_LENGTH),
        ("An uppercase letter (A-Z)", any(c.isupper() for c in pw)),
        ("A lowercase letter (a-z)", any(c.islower() for c in pw)),
        ("A number (0-9)", any(c.isdigit() for c in pw)),
        ("A symbol (! @ # $ % ...)", any(not c.isalnum() and not c.isspace() for c in pw)),
        ("No spaces", len(pw) > 0 and not any(c.isspace() for c in pw)),
    ]


def hash_password(pw, salt_hex, iterations=ITERATIONS):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex),
                               iterations).hex()


def read_auth(path):
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if all(k in data for k in ("salt", "hash", "iterations")):
            return data
    except Exception:
        pass
    return None


def write_auth(path, pw):
    salt = secrets.token_hex(16)
    data = {"salt": salt, "iterations": ITERATIONS,
            "hash": hash_password(pw, salt, ITERATIONS)}
    with open(path, "w") as f:
        json.dump(data, f)
    return data


def check_auth(auth, pw):
    return hmac.compare_digest(hash_password(pw, auth["salt"], auth["iterations"]),
                               auth["hash"])


# =====================================================================
# SYSTEM + GPU METRICS
# =====================================================================
_cpu_prev = None


def cpu_percent():
    """Whole-machine CPU use in percent, or None if unavailable."""
    global _cpu_prev
    if _psutil is not None:
        try:
            return float(_psutil.cpu_percent(interval=None))
        except Exception:
            pass
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/stat") as f:
                vals = list(map(int, f.readline().split()[1:8]))
            idle, total = vals[3] + vals[4], sum(vals)
        elif os.name == "nt":
            import ctypes

            class FILETIME(ctypes.Structure):
                _fields_ = [("lo", ctypes.c_ulong), ("hi", ctypes.c_ulong)]

            i, k, u = FILETIME(), FILETIME(), FILETIME()
            ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
            ft = lambda f: (f.hi << 32) | f.lo
            idle, total = ft(i), ft(k) + ft(u)  # kernel time includes idle
        else:
            return None
    except Exception:
        return None
    prev, _cpu_prev = _cpu_prev, (idle, total)
    if prev is None or total - prev[1] <= 0:
        return None
    return round(100.0 * (1 - (idle - prev[0]) / (total - prev[1])), 1)


def memory_info():
    try:
        if _psutil is not None:
            m = _psutil.virtual_memory()
            return {"total": m.total, "used": m.total - m.available,
                    "percent": round(m.percent, 1)}
        if sys.platform.startswith("linux"):
            info = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    key, val = line.split(":", 1)
                    info[key] = int(val.split()[0]) * 1024
            total, avail = info["MemTotal"], info["MemAvailable"]
            return {"total": total, "used": total - avail,
                    "percent": round(100.0 * (total - avail) / total, 1)}
        if os.name == "nt":
            import ctypes

            class MEMSTATUS(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                            ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                            ("tpage", ctypes.c_ulonglong), ("apage", ctypes.c_ulonglong),
                            ("tvirt", ctypes.c_ulonglong), ("avirt", ctypes.c_ulonglong),
                            ("ext", ctypes.c_ulonglong)]

            ms = MEMSTATUS()
            ms.length = ctypes.sizeof(MEMSTATUS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            return {"total": ms.total, "used": ms.total - ms.avail,
                    "percent": round(100.0 * (ms.total - ms.avail) / ms.total, 1)}
    except Exception:
        pass
    return None


def disk_info(path):
    try:
        u = shutil.disk_usage(path)
        return {"total": u.total, "used": u.used,
                "percent": round(100.0 * u.used / u.total, 1)}
    except Exception:
        return None


_gpu_cache = (0.0, [])


def gpu_info():
    """NVIDIA GPUs via nvidia-smi (cached for 2 s). Empty list if none."""
    global _gpu_cache
    now = time.time()
    if now - _gpu_cache[0] < 2:
        return _gpu_cache[1]
    gpus = []
    exe = shutil.which("nvidia-smi")
    if exe:
        try:
            out = subprocess.run(
                [exe, "--query-gpu=name,utilization.gpu,memory.used,memory.total,"
                      "temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3).stdout
            for line in out.strip().splitlines():
                name, util, mem_used, mem_total, temp = [x.strip() for x in line.split(",")]
                gpus.append({"name": name, "util": float(util),
                             "mem_used": float(mem_used), "mem_total": float(mem_total),
                             "temp": float(temp)})
        except Exception:
            gpus = []
    _gpu_cache = (now, gpus)
    return gpus


def system_metrics(data_path):
    return {"cpu": cpu_percent(), "mem": memory_info(),
            "disk": disk_info(data_path), "gpus": gpu_info(),
            "cores": os.cpu_count()}


# =====================================================================
# FILES
# =====================================================================
def tail_file(path, lines=200, max_bytes=131072):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - max_bytes))
            data = f.read().decode("utf-8", "replace")
        return "\n".join(data.splitlines()[-lines:])
    except OSError:
        return ""


# =====================================================================
# PROCESS MANAGER
# =====================================================================
class ProcessManager:
    """Runs registered apps that have a start command, keeps them alive."""

    CRASH_LIMIT = 5      # crashes ...
    CRASH_WINDOW = 60    # ... inside this many seconds = give up

    def __init__(self, core):
        self.core = core
        self.procs = {}
        self.desired = set()
        self.crashes = {}
        self.gave_up = set()
        self.restarts = {}
        self.lock = threading.RLock()
        self.running = False

    def log_path(self, name):
        folder = os.path.join(self.core.data_dir(), "logs")
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, f"app-{name}.log")

    def is_running(self, name):
        info = self.procs.get(name)
        return bool(info and info["p"].poll() is None)

    def start(self, name):
        with self.lock:
            entry = self.core.registry.get(name)
            if not entry or not entry.get("command"):
                return False, "No start command registered for this app."
            if self.is_running(name):
                return True, "Already running."
            self.gave_up.discard(name)
            logf = open(self.log_path(name), "ab")
            env = os.environ.copy()
            env["PORT"] = str(entry.get("port", ""))
            env["ENGINE_APP_NAME"] = name
            kwargs = {}
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True
            try:
                p = subprocess.Popen(entry["command"], shell=True,
                                     cwd=entry.get("cwd") or None, env=env,
                                     stdout=logf, stderr=subprocess.STDOUT, **kwargs)
            except Exception as e:
                logf.close()
                return False, f"Could not start: {e}"
            self.procs[name] = {"p": p, "started": time.time(), "log": logf}
            self.desired.add(name)
            self.core.log(f"Started {name} (pid {p.pid})")
            return True, "Started."

    def _terminate(self, p, timeout=5):
        if p.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                               capture_output=True, timeout=10)
            else:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except Exception:
            try:
                p.terminate()
            except Exception:
                pass
        try:
            p.wait(timeout=timeout)
        except Exception:
            try:
                if os.name == "nt":
                    p.kill()
                else:
                    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            except Exception:
                pass

    def stop(self, name):
        with self.lock:
            self.desired.discard(name)
            info = self.procs.pop(name, None)
        if info:
            self._terminate(info["p"])
            try:
                info["log"].close()
            except Exception:
                pass
            self.core.log(f"Stopped {name}")
            return True, "Stopped."
        return True, "Not running."

    def restart(self, name):
        self.stop(name)
        return self.start(name)

    def status(self, name):
        info = self.procs.get(name)
        running = bool(info and info["p"].poll() is None)
        return {"running": running,
                "pid": info["p"].pid if running else None,
                "uptime": int(time.time() - info["started"]) if running else 0,
                "restarts": self.restarts.get(name, 0),
                "gave_up": name in self.gave_up}

    def autostart_all(self):
        for name, entry in list(self.core.registry.items()):
            if entry.get("command") and entry.get("autostart", True):
                self.start(name)

    def start_monitor(self):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._monitor, daemon=True).start()

    def _monitor(self):
        while self.running:
            time.sleep(2)
            for name in list(self.desired):
                info = self.procs.get(name)
                if info is not None and info["p"].poll() is None:
                    continue
                code = info["p"].poll() if info else None
                now = time.time()
                times = self.crashes.setdefault(name, collections.deque())
                times.append(now)
                while times and now - times[0] > self.CRASH_WINDOW:
                    times.popleft()
                if len(times) >= self.CRASH_LIMIT:
                    self.desired.discard(name)
                    self.gave_up.add(name)
                    self.core.log(f"{name} keeps crashing; auto-restart stopped.")
                    continue
                self.core.log(f"{name} exited (code {code}); restarting.")
                self.restarts[name] = self.restarts.get(name, 0) + 1
                if info:
                    try:
                        info["log"].close()
                    except Exception:
                        pass
                self.procs.pop(name, None)
                self.start(name)

    def shutdown(self):
        self.running = False
        for name in list(self.procs):
            self.stop(name)


# =====================================================================
# REMOTE CLIENT (phone -> desktop engine)
# =====================================================================
def normalize_base(address):
    address = address.strip().rstrip("/")
    if not address.startswith("http"):
        address = "http://" + address
    host_part = address.split("//", 1)[1]
    if ":" not in host_part:
        address += ":9090"
    return address


class RemoteClient:
    def __init__(self, address):
        self.base = normalize_base(address)
        self.token = None

    def _request(self, path, payload=None, timeout=6):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base + path, data=data,
                                     method="POST" if payload is not None else "GET")
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read().decode() or "{}")
            except Exception:
                body = {}
            return e.code, body

    def login(self, password):
        status, body = self._request("/api/login", {"password": password})
        if status == 200 and body.get("token"):
            self.token = body["token"]
            return True, ""
        return False, body.get("error", "Login failed.")

    def state(self):
        return self._request("/api/state")
