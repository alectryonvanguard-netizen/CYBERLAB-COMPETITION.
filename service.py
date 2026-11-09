"""
.engine background service (Android foreground service).

Runs the DNS + proxy engine independently of the app screen, so it keeps
working when the app is closed or the screen is off. The app screen reads
engine_status.json, which this service refreshes every second.
"""
import os
import json
import time

from engine_core import InfrastructureCore, default_registry_path


def hold_wakelock():
    """Keep the CPU awake so the proxy keeps answering with the screen off."""
    try:
        from jnius import autoclass
        Context = autoclass("android.content.Context")
        PowerManager = autoclass("android.os.PowerManager")
        service = autoclass("org.kivy.android.PythonService").mService
        pm = service.getSystemService(Context.POWER_SERVICE)
        lock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "engine:proxy")
        lock.acquire()
        return lock
    except Exception:
        return None


def main():
    registry = default_registry_path()
    status_file = os.path.join(os.path.dirname(registry), "engine_status.json")
    logs = []

    def log(text):
        logs.append(f"{time.strftime('%H:%M:%S')}  {text}")
        del logs[:-40]

    wake_lock = hold_wakelock()  # keep a reference so it is not released
    core = InfrastructureCore(log, registry)
    core.start()
    log("Background service started.")

    while True:
        snapshot = {
            "ts": time.time(),
            "bytes": core.bytes_transferred,
            "requests": core.total_requests,
            "tunnels": core.active_tunnels,
            "proxy_port": core.proxy_port,
            "dns_port": core.dns_port,
            "lan_ip": core.lan_ip,
            "logs": logs,
        }
        try:
            tmp = status_file + ".tmp"
            with open(tmp, "w") as f:
                json.dump(snapshot, f)
            os.replace(tmp, status_file)
        except Exception:
            pass
        time.sleep(1)


main()
