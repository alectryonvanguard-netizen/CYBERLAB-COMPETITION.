import os
import json
import socket
import hmac
import hashlib
import threading
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex as hx

# =====================================================================
# CONFIG
# =====================================================================
DNS_PORT = 5353
PROXY_PORT = 8080
MAX_APPS = 15

SECURE_SALT = b"CipherAegisSaltEngineCore2026"
# PBKDF2-HMAC-SHA256 (100k rounds) of the access password "MySecurePassword123".
# To change it, run:
#   python -c "import hashlib;print(hashlib.pbkdf2_hmac('sha256', b'NEWPASS', b'CipherAegisSaltEngineCore2026', 100000).hex())"
PASSWORD_HASH = "61a9387feefbf65175e963d05afb33a93f43d88cc8f665720a5f859c191beb83"


def compute_secure_hash(raw_password: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", raw_password.encode(), SECURE_SALT, 100000).hex()


# =====================================================================
# THEME
# =====================================================================
BG = hx("#0A0E1A")
CARD = hx("#121A2E")
CARD_HI = hx("#1B2742")
ACCENT = hx("#22D3EE")
GOOD = hx("#34D399")
WARN = hx("#FBBF24")
DANGER = hx("#F87171")
TEXT = hx("#E5E9F5")
MUTED = hx("#8A94B2")


def make_label(text, size=14, color=TEXT, bold=False, halign="left", **kw):
    lbl = Label(text=text, font_size=sp(size), color=color, bold=bold,
                halign=halign, valign="middle", **kw)
    lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
    return lbl


class Card(BoxLayout):
    def __init__(self, bg=CARD, radius=16, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            self._color = Color(*bg)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(radius)])
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *args):
        self._rect.pos = self.pos
        self._rect.size = self.size


class RoundButton(Button):
    def __init__(self, bg=ACCENT, fg=BG, radius=12, **kw):
        kw.setdefault("background_normal", "")
        kw.setdefault("background_down", "")
        kw.setdefault("background_color", (0, 0, 0, 0))
        kw.setdefault("color", fg)
        kw.setdefault("bold", True)
        kw.setdefault("font_size", sp(14))
        super().__init__(**kw)
        self._bg = bg
        with self.canvas.before:
            self._color = Color(*bg)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(radius)])
        self.bind(pos=self._sync, size=self._sync,
                  on_press=self._dim, on_release=self._undim)

    def _sync(self, *args):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _dim(self, *args):
        r, g, b, a = self._bg
        self._color.rgba = (r * 0.7, g * 0.7, b * 0.7, a)

    def _undim(self, *args):
        self._color.rgba = self._bg


class Field(BoxLayout):
    def __init__(self, hint="", password=False, **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(48))
        super().__init__(padding=[dp(14), 0], **kw)
        with self.canvas.before:
            Color(*CARD_HI)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
        self.bind(pos=self._sync, size=self._sync)
        self.input = TextInput(
            hint_text=hint, password=password, multiline=False,
            background_normal="", background_active="",
            background_color=(0, 0, 0, 0),
            foreground_color=TEXT, hint_text_color=MUTED,
            cursor_color=ACCENT, font_size=sp(15),
            padding=[0, dp(14), 0, dp(10)],
        )
        self.add_widget(self.input)

    def _sync(self, *args):
        self._rect.pos = self.pos
        self._rect.size = self.size


class StatCard(Card):
    def __init__(self, title, value, accent=ACCENT, **kw):
        super().__init__(orientation="vertical", padding=dp(12), spacing=dp(2), **kw)
        self.value_label = make_label(value, size=17, color=accent, bold=True)
        self.add_widget(self.value_label)
        self.add_widget(make_label(title, size=11, color=MUTED))


# =====================================================================
# CORE NETWORK ENGINE
# =====================================================================
class InfrastructureCore:
    def __init__(self, log_callback):
        self.log = log_callback
        self.registry_file = "engine_registry.json"
        self.registry = self.load_registry_matrix()

        self.total_requests = 0
        self.bytes_transferred = 0
        self.active_tunnels = 0

        self.is_running = False
        self.lock = threading.Lock()

    def set_storage_path(self, path):
        self.registry_file = path
        self.registry = self.load_registry_matrix()

    def load_registry_matrix(self):
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def commit_registry_matrix(self):
        with self.lock:
            try:
                with open(self.registry_file, "w") as f:
                    json.dump(self.registry, f, indent=4)
            except Exception as e:
                self.log(f"STORAGE ERROR: {e}")

    def add_node(self, subdomain, port):
        if subdomain not in self.registry and len(self.registry) >= MAX_APPS:
            return False
        self.registry[subdomain] = {"port": port, "created_at": time.time()}
        self.commit_registry_matrix()
        return True

    def drop_node(self, subdomain):
        if subdomain in self.registry:
            del self.registry[subdomain]
            self.commit_registry_matrix()

    # ---------------- DNS ----------------
    def start_dns_daemon(self):
        dns_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dns_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            dns_sock.bind(("0.0.0.0", DNS_PORT))
            self.log(f"DNS listening on port {DNS_PORT}")
        except Exception as e:
            self.log(f"DNS BIND FAILED: {e}")
            return

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

            if qtype == b"\x00\x01":  # A record -> loopback
                counters = b"\x00\x01\x00\x01\x00\x00\x00\x00"
                answer = (b"\xc0\x0c" + b"\x00\x01\x00\x01" + b"\x00\x00\x00\x3c"
                          + b"\x00\x04" + b"\x7f\x00\x00\x01")
            else:  # AAAA etc -> empty answer
                counters = b"\x00\x01\x00\x00\x00\x00\x00\x00"
                answer = b""

            payload = transaction_id + b"\x81\x80" + counters + question + answer
            sock.sendto(payload, addr)
        except Exception:
            pass

    # ---------------- PROXY ----------------
    def start_proxy_daemon(self):
        proxy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        proxy_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            proxy_sock.bind(("0.0.0.0", PROXY_PORT))
            proxy_sock.listen(200)
            self.log(f"Proxy listening on port {PROXY_PORT}")
        except Exception as e:
            self.log(f"PROXY BIND FAILED: {e}")
            return

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

    def orchestrate_tunnel(self, client_conn, client_addr):
        self.total_requests += 1
        upstream_conn = None
        try:
            header_buffer = client_conn.recv(4096)
            if not header_buffer:
                return

            with self.lock:
                self.bytes_transferred += len(header_buffer)

            target_subdomain = None
            for line in header_buffer.split(b"\r\n"):
                if line.lower().startswith(b"host:"):
                    host_value = line.split(b":", 1)[1].decode("utf-8").strip()
                    if ":" in host_value:
                        host_value = host_value.split(":")[0]
                    if host_value.endswith(".engine"):
                        target_subdomain = host_value[:-len(".engine")]
                    break

            if target_subdomain and target_subdomain in self.registry:
                target_port = self.registry[target_subdomain]["port"]

                upstream_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                upstream_conn.settimeout(5)
                upstream_conn.connect(("127.0.0.1", target_port))
                upstream_conn.sendall(header_buffer)

                upstream_conn.setblocking(False)
                client_conn.setblocking(False)

                self.log(f"200 {target_subdomain}.engine -> :{target_port}")

                runtime_active = True
                while runtime_active and self.is_running:
                    active_cycle = False
                    try:
                        chunk = client_conn.recv(4096)
                        if chunk:
                            upstream_conn.sendall(chunk)
                            with self.lock:
                                self.bytes_transferred += len(chunk)
                            active_cycle = True
                        else:
                            runtime_active = False
                    except BlockingIOError:
                        pass

                    try:
                        chunk = upstream_conn.recv(4096)
                        if chunk:
                            client_conn.sendall(chunk)
                            with self.lock:
                                self.bytes_transferred += len(chunk)
                            active_cycle = True
                        else:
                            runtime_active = False
                    except BlockingIOError:
                        pass

                    if not active_cycle:
                        time.sleep(0.005)
            else:
                err = (b"HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\n"
                       b"Connection: close\r\n\r\n.engine: no app is bound to this name.")
                client_conn.sendall(err)
                name = f"{target_subdomain}.engine" if target_subdomain else "(no .engine host)"
                self.log(f"404 unregistered lookup: {name}")
        except Exception as e:
            self.log(f"Tunnel closed: {e}")
        finally:
            if upstream_conn is not None:
                try:
                    upstream_conn.close()
                except Exception:
                    pass
            try:
                client_conn.close()
            except Exception:
                pass
            with self.lock:
                self.active_tunnels -= 1


# =====================================================================
# UI
# =====================================================================
class EnginePlatform(App):
    def build(self):
        self.title = ".engine"
        Window.clearcolor = BG

        self.log_buffer = []
        self._rendered_log_key = None
        self.core = InfrastructureCore(self.post_log_message)
        self.core.set_storage_path(os.path.join(self.user_data_dir, "engine_registry.json"))

        self.root_window = BoxLayout(
            orientation="vertical",
            padding=[dp(16), dp(28), dp(16), dp(16)],
            spacing=dp(12),
        )
        self.render_secure_gateway()
        return self.root_window

    def post_log_message(self, text):
        entry = f"{time.strftime('%H:%M:%S')}  {text}"
        self.log_buffer.append(entry)
        if len(self.log_buffer) > 40:
            self.log_buffer.pop(0)

    # ---------------- LOGIN ----------------
    def render_secure_gateway(self):
        self.root_window.clear_widgets()
        self.root_window.add_widget(BoxLayout(size_hint_y=0.25))

        self.root_window.add_widget(make_label(
            ".engine", size=40, color=ACCENT, bold=True, halign="center",
            size_hint_y=None, height=dp(56)))
        self.root_window.add_widget(make_label(
            "Local domain hosting console", size=14, color=MUTED, halign="center",
            size_hint_y=None, height=dp(24)))

        card = Card(orientation="vertical", padding=dp(16), spacing=dp(12),
                    size_hint_y=None, height=dp(176))
        card.add_widget(make_label("Access key", size=12, color=MUTED,
                                   size_hint_y=None, height=dp(18)))
        self.pass_field = Field(hint="Enter administrator password", password=True)
        self.pass_field.input.bind(on_text_validate=lambda inst: self.process_authorization(None))
        card.add_widget(self.pass_field)
        self.auth_error = make_label("", size=12, color=DANGER,
                                     size_hint_y=None, height=dp(18))
        card.add_widget(self.auth_error)
        card.add_widget(RoundButton(text="UNLOCK", size_hint_y=None, height=dp(46),
                                    on_release=self.process_authorization))
        self.root_window.add_widget(card)

        self.root_window.add_widget(BoxLayout(size_hint_y=0.45))

    def process_authorization(self, instance):
        input_hash = compute_secure_hash(self.pass_field.input.text)
        if hmac.compare_digest(input_hash, PASSWORD_HASH):
            self.core.is_running = True
            threading.Thread(target=self.core.start_dns_daemon, daemon=True).start()
            threading.Thread(target=self.core.start_proxy_daemon, daemon=True).start()
            self.render_system_console()
            Clock.schedule_interval(self.update_telemetry_metrics, 0.5)
        else:
            self.pass_field.input.text = ""
            self.auth_error.text = "Wrong password. Try again."

    # ---------------- CONSOLE ----------------
    def render_system_console(self):
        self.root_window.clear_widgets()

        header = BoxLayout(size_hint_y=None, height=dp(40))
        header.add_widget(make_label(".engine", size=26, color=ACCENT, bold=True))
        header.add_widget(make_label("●  ONLINE", size=12, color=GOOD, bold=True,
                                     halign="right", size_hint_x=0.4))
        self.root_window.add_widget(header)

        stats = GridLayout(cols=3, spacing=dp(8), size_hint_y=None, height=dp(66))
        self.traffic_card = StatCard("Traffic", "0.0 KB", ACCENT)
        self.requests_card = StatCard("Requests", "0", WARN)
        self.tunnels_card = StatCard("Tunnels", "0", GOOD)
        for c in (self.traffic_card, self.requests_card, self.tunnels_card):
            stats.add_widget(c)
        self.root_window.add_widget(stats)

        bind_card = Card(orientation="vertical", padding=dp(12), spacing=dp(10),
                         size_hint_y=None, height=dp(124))
        row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        self.subdomain_field = Field(hint="name (e.g. clipsy)", size_hint_x=0.62)
        self.port_field = Field(hint="port", size_hint_x=0.38)
        row.add_widget(self.subdomain_field)
        row.add_widget(self.port_field)
        bind_card.add_widget(row)
        bind_card.add_widget(RoundButton(text="BIND APP", size_hint_y=None, height=dp(46),
                                         on_release=self.execute_node_binding))
        self.root_window.add_widget(bind_card)

        self.nodes_tracker_label = make_label(
            f"Registered apps   0 / {MAX_APPS}", size=13, color=MUTED, bold=True,
            size_hint_y=None, height=dp(22))
        self.root_window.add_widget(self.nodes_tracker_label)

        self.routing_grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        self.routing_grid.bind(minimum_height=self.routing_grid.setter("height"))
        routing_scroll = ScrollView(size_hint=(1, 0.55), bar_width=0)
        routing_scroll.add_widget(self.routing_grid)
        self.root_window.add_widget(routing_scroll)

        self.root_window.add_widget(make_label(
            "Live log", size=13, color=MUTED, bold=True,
            size_hint_y=None, height=dp(22)))

        log_card = Card(orientation="vertical", padding=dp(10), size_hint=(1, 0.45))
        self.syslog_grid = GridLayout(cols=1, spacing=dp(2), size_hint_y=None)
        self.syslog_grid.bind(minimum_height=self.syslog_grid.setter("height"))
        syslog_scroll = ScrollView(bar_width=0)
        syslog_scroll.add_widget(self.syslog_grid)
        log_card.add_widget(syslog_scroll)
        self.root_window.add_widget(log_card)

        self.refresh_routing_display_tree()

    def execute_node_binding(self, instance):
        name = self.subdomain_field.input.text.strip().lower().replace(".engine", "")
        port_raw = self.port_field.input.text.strip()

        if not name or not port_raw.isdigit():
            self.core.log("Enter a name and a numeric port.")
            return

        port_num = int(port_raw)
        if not (1024 <= port_num <= 65535):
            self.core.log("Port must be between 1024 and 65535.")
            return

        if self.core.add_node(name, port_num):
            self.subdomain_field.input.text = ""
            self.port_field.input.text = ""
            self.refresh_routing_display_tree()
            self.core.log(f"Bound http://{name}.engine -> port {port_num}")
        else:
            self.core.log("Limit reached: 15 apps maximum.")

    def execute_node_purge(self, subdomain):
        self.core.drop_node(subdomain)
        self.refresh_routing_display_tree()
        self.core.log(f"Unbound {subdomain}.engine")

    def refresh_routing_display_tree(self):
        self.routing_grid.clear_widgets()

        if not self.core.registry:
            self.routing_grid.add_widget(make_label(
                "No apps bound yet. Add a name and port above.",
                size=13, color=MUTED, halign="center",
                size_hint_y=None, height=dp(60)))

        for subdomain, config in self.core.registry.items():
            row = Card(orientation="horizontal", padding=[dp(14), dp(8)], spacing=dp(10),
                       size_hint_y=None, height=dp(60))
            info = BoxLayout(orientation="vertical")
            info.add_widget(make_label(f"{subdomain}.engine", size=15, bold=True))
            info.add_widget(make_label(f"127.0.0.1:{config['port']}", size=12, color=MUTED))
            row.add_widget(info)
            row.add_widget(RoundButton(
                text="UNBIND", bg=DANGER, fg=BG, size_hint_x=None, width=dp(86),
                font_size=sp(12),
                on_release=lambda inst, s=subdomain: self.execute_node_purge(s)))
            self.routing_grid.add_widget(row)

        self.nodes_tracker_label.text = (
            f"Registered apps   {len(self.core.registry)} / {MAX_APPS}")

    def update_telemetry_metrics(self, dt):
        try:
            b = self.core.bytes_transferred
            if b < 1024 * 1024:
                metric = f"{round(b / 1024, 1)} KB"
            else:
                metric = f"{round(b / (1024 * 1024), 2)} MB"
            self.traffic_card.value_label.text = metric
            self.requests_card.value_label.text = str(self.core.total_requests)
            self.tunnels_card.value_label.text = str(self.core.active_tunnels)

            key = (len(self.log_buffer), self.log_buffer[-1] if self.log_buffer else "")
            if key != self._rendered_log_key:
                self._rendered_log_key = key
                self.syslog_grid.clear_widgets()
                for entry in reversed(self.log_buffer):
                    self.syslog_grid.add_widget(make_label(
                        entry, size=11, color=MUTED,
                        size_hint_y=None, height=dp(20),
                        shorten=True, shorten_from="right"))
        except Exception:
            pass

    def on_stop(self):
        self.core.is_running = False


if __name__ == "__main__":
    EnginePlatform().run()
