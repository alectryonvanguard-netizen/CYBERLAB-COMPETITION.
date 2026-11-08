import os
import hmac
import hashlib
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex as hx, platform

from engine_core import InfrastructureCore, MAX_APPS, default_registry_path

# =====================================================================
# CONFIG
# =====================================================================
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
# UI
# =====================================================================
class EnginePlatform(App):
    def build(self):
        self.title = ".engine"
        Window.clearcolor = BG
        if platform not in ("android", "ios"):
            Window.size = (560, 860)

        self.log_buffer = []
        self._rendered_log_key = None
        self.core = InfrastructureCore(self.post_log_message)
        if platform == "android":
            self.core.set_storage_path(os.path.join(self.user_data_dir, "engine_registry.json"))
        else:
            # same file the headless server / CLI uses on desktop
            self.core.set_storage_path(default_registry_path())

        outer = AnchorLayout(anchor_x="center", anchor_y="top")
        self.root_window = BoxLayout(
            orientation="vertical",
            padding=[dp(16), dp(28), dp(16), dp(16)],
            spacing=dp(12),
            size_hint=(None, 1),
        )
        self._fit_width(Window, Window.width)
        Window.bind(width=self._fit_width)
        outer.add_widget(self.root_window)
        self.render_secure_gateway()
        return outer

    def _fit_width(self, window, width):
        self.root_window.width = min(width, dp(640))

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
            self.core.start()
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

        self.net_label = make_label("Starting network...", size=12, color=MUTED,
                                    size_hint_y=None, height=dp(18), shorten=True)
        self.root_window.add_widget(self.net_label)

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
            info.add_widget(make_label(
                f"{self.core.url_for(subdomain)}   >   :{config['port']}",
                size=12, color=MUTED, shorten=True))
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
            self.net_label.text = (
                f"Proxy :{self.core.proxy_port or '-'}   DNS :{self.core.dns_port or '-'}"
                f"   {self.core.lan_ip}")

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
        self.core.stop()


if __name__ == "__main__":
    EnginePlatform().run()
