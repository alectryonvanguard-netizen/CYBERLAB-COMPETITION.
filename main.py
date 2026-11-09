import os
import hmac
import hashlib
import time
import traceback

from kivy import kivy_data_dir
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex as hx, platform

# If engine_core.py is missing from the APK, show the reason on screen
# instead of closing silently.
try:
    from engine_core import InfrastructureCore, MAX_APPS, default_registry_path
    IMPORT_ERROR = None
except Exception:
    IMPORT_ERROR = traceback.format_exc()
    InfrastructureCore = None
    MAX_APPS = 15
    default_registry_path = None

# =====================================================================
# SECURITY
# =====================================================================
SECURE_SALT = b"CipherAegisSaltEngineCore2026"
# PBKDF2-HMAC-SHA256 (100k rounds) of the access password "MySecurePassword123".
# To change it, run:
#   python -c "import hashlib;print(hashlib.pbkdf2_hmac('sha256', b'NEWPASS', b'CipherAegisSaltEngineCore2026', 100000).hex())"
PASSWORD_HASH = "61a9387feefbf65175e963d05afb33a93f43d88cc8f665720a5f859c191beb83"


def compute_secure_hash(raw_password):
    return hashlib.pbkdf2_hmac("sha256", raw_password.encode(), SECURE_SALT, 100000).hex()


# =====================================================================
# THEME: digital terminal
# =====================================================================
BG = hx("#05080F")
PANEL = hx("#0A1220")
ACCENT = hx("#00F0FF")
GOOD = hx("#00FF9C")
WARN = hx("#FFD60A")
DANGER = hx("#FF4D6D")
TEXT = hx("#D6F6FF")
MUTED = hx("#5F7A94")
GRID = [0.0, 0.94, 1.0, 0.045]
BORDER = list(ACCENT[:3]) + [0.40]
BORDER_DIM = list(ACCENT[:3]) + [0.18]

_mono = os.path.join(kivy_data_dir, "fonts", "RobotoMono-Regular.ttf")
FONT = _mono if os.path.exists(_mono) else "Roboto"


def make_label(text, size=14, color=TEXT, halign="left", **kw):
    lbl = Label(text=text, font_size=sp(size), color=color, font_name=FONT,
                halign=halign, valign="middle", **kw)
    lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
    return lbl


def record_error(app, text):
    """Errors go to a private log file only; users never see technical details."""
    try:
        with open(os.path.join(app.user_data_dir, "engine_errors.log"), "a") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n" + text + "\n")
    except Exception:
        pass


def guarded(fn):
    """Button handlers must never crash the whole app."""
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Exception:
            record_error(self, traceback.format_exc())
            self.post_log_message("Action could not be completed.")
    wrapper.__name__ = fn.__name__
    return wrapper


class GridBackground(Widget):
    """Faint cyan grid behind everything."""
    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *args):
        self.canvas.clear()
        step = dp(36)
        with self.canvas:
            Color(*GRID)
            x = self.x
            while x <= self.right:
                Line(points=[x, self.y, x, self.top], width=1)
                x += step
            y = self.y
            while y <= self.top:
                Line(points=[self.x, y, self.right, y], width=1)
                y += step


class Panel(BoxLayout):
    def __init__(self, fill=PANEL, border=BORDER, radius=8, **kw):
        super().__init__(**kw)
        self._r = dp(radius)
        with self.canvas.before:
            Color(*fill)
            self._fill = RoundedRectangle(pos=self.pos, size=self.size, radius=[self._r])
            Color(*border)
            self._line = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, self._r),
                              width=dp(1))
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *args):
        self._fill.pos = self.pos
        self._fill.size = self.size
        self._line.rounded_rectangle = (self.x, self.y, self.width, self.height, self._r)


class NeonButton(Button):
    def __init__(self, bg=ACCENT, fg=BG, radius=6, **kw):
        kw.setdefault("background_normal", "")
        kw.setdefault("background_down", "")
        kw.setdefault("background_color", (0, 0, 0, 0))
        kw.setdefault("color", fg)
        kw.setdefault("font_name", FONT)
        kw.setdefault("font_size", sp(13))
        super().__init__(**kw)
        self._bg = list(bg)
        with self.canvas.before:
            self._color = Color(*self._bg)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(radius)])
        self.bind(pos=self._sync, size=self._sync,
                  on_press=self._dim, on_release=self._undim)

    def _sync(self, *args):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _dim(self, *args):
        r, g, b, a = self._bg
        self._color.rgba = (r * 0.6, g * 0.6, b * 0.6, a)

    def _undim(self, *args):
        self._color.rgba = self._bg


class Field(Panel):
    def __init__(self, hint="", password=False, **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(48))
        super().__init__(fill=BG, border=BORDER, radius=6, padding=[dp(12), 0], **kw)
        self.input = TextInput(
            hint_text=hint, password=password, multiline=False,
            background_normal="", background_active="",
            background_color=(0, 0, 0, 0),
            foreground_color=TEXT, hint_text_color=MUTED,
            cursor_color=ACCENT, font_name=FONT, font_size=sp(14),
            padding=[0, dp(14), 0, dp(10)],
        )
        self.add_widget(self.input)


class StatCard(Panel):
    def __init__(self, title, value, accent=ACCENT, **kw):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(2), **kw)
        self.value_label = make_label(value, size=17, color=accent)
        self.add_widget(self.value_label)
        self.add_widget(make_label(title, size=10, color=MUTED))


def unavailable_view(code=""):
    box = BoxLayout(orientation="vertical", padding=dp(32), spacing=dp(12))
    box.add_widget(BoxLayout(size_hint_y=0.3))
    box.add_widget(make_label("> .engine", size=34, color=ACCENT, halign="center",
                              size_hint_y=None, height=dp(56)))
    box.add_widget(make_label(
        "The service could not start.\nClose the app and open it again.\n"
        "If this continues, please contact support.",
        size=13, color=MUTED, halign="center", size_hint_y=None, height=dp(110)))
    if code:
        box.add_widget(make_label("Support code:\n" + code, size=11, color=MUTED,
                                  halign="center", size_hint_y=None, height=dp(70)))
    box.add_widget(BoxLayout())
    return box


# =====================================================================
# APP
# =====================================================================
class EnginePlatform(App):
    def build(self):
        self.title = ".engine"
        Window.clearcolor = BG
        self.log_buffer = []
        try:
            return self._build()
        except Exception:
            err = traceback.format_exc()
            record_error(self, err)
            lines = [l for l in err.strip().splitlines() if l.strip()]
            return unavailable_view(lines[-1][:90] if lines else "")

    def _build(self):
        if IMPORT_ERROR:
            raise RuntimeError(IMPORT_ERROR)

        if platform not in ("android", "ios"):
            Window.size = (560, 860)
        else:
            Window.softinput_mode = "below_target"

        self._rendered_log_key = None

        self.core = InfrastructureCore(self.post_log_message)
        if platform == "android":
            self.core.set_storage_path(os.path.join(self.user_data_dir, "engine_registry.json"))
        else:
            self.core.set_storage_path(default_registry_path())

        root = FloatLayout()
        root.add_widget(GridBackground(size_hint=(1, 1)))
        outer = AnchorLayout(anchor_x="center", anchor_y="top", size_hint=(1, 1))
        self.shell = BoxLayout(
            orientation="vertical",
            padding=[dp(16), dp(28), dp(16), dp(16)],
            spacing=dp(12),
            size_hint=(None, 1),
        )
        self._fit_width(Window, Window.width)
        Window.bind(width=self._fit_width)
        outer.add_widget(self.shell)
        root.add_widget(outer)

        self.render_secure_gateway()
        return root

    def _fit_width(self, window, width):
        self.shell.width = min(width, dp(640))

    def on_pause(self):
        return True  # keep running when the user switches apps

    def on_resume(self):
        pass

    def post_log_message(self, text):
        entry = f"{time.strftime('%H:%M:%S')}  {text}"
        self.log_buffer.append(entry)
        if len(self.log_buffer) > 40:
            self.log_buffer.pop(0)

    # ---------------- LOGIN ----------------
    def render_secure_gateway(self):
        rw = self.shell
        rw.clear_widgets()
        rw.add_widget(BoxLayout(size_hint_y=0.2))

        rw.add_widget(make_label("> .engine", size=38, color=ACCENT, halign="center",
                                 size_hint_y=None, height=dp(60)))
        rw.add_widget(make_label("SECURE TERMINAL  //  AUTH REQUIRED", size=11, color=MUTED,
                                 halign="center", size_hint_y=None, height=dp(22)))

        panel = Panel(orientation="vertical", padding=dp(16), spacing=dp(12),
                      size_hint_y=None, height=dp(200))
        panel.add_widget(make_label("ENTER ACCESS KEY", size=11, color=MUTED,
                                    size_hint_y=None, height=dp(16)))
        self.pass_field = Field(hint="password", password=True)
        self.pass_field.input.bind(on_text_validate=lambda inst: self.process_authorization(None))
        panel.add_widget(self.pass_field)
        self.auth_error = make_label("", size=11, color=DANGER,
                                     size_hint_y=None, height=dp(16))
        panel.add_widget(self.auth_error)
        panel.add_widget(NeonButton(text="[ UNLOCK ]", size_hint_y=None, height=dp(46),
                                    on_release=self.process_authorization))
        rw.add_widget(panel)

        rw.add_widget(BoxLayout(size_hint_y=0.45))

    @guarded
    def process_authorization(self, instance):
        input_hash = compute_secure_hash(self.pass_field.input.text)
        if hmac.compare_digest(input_hash, PASSWORD_HASH):
            self.core.start()
            self.render_system_console()
            Clock.schedule_interval(self.update_telemetry_metrics, 0.5)
        else:
            self.pass_field.input.text = ""
            self.auth_error.text = "ACCESS DENIED"

    # ---------------- CONSOLE ----------------
    def render_system_console(self):
        rw = self.shell
        rw.clear_widgets()

        header = BoxLayout(size_hint_y=None, height=dp(40))
        header.add_widget(make_label("> .engine", size=24, color=ACCENT))
        header.add_widget(make_label("[ ONLINE ]", size=12, color=GOOD, halign="right",
                                     size_hint_x=0.4))
        rw.add_widget(header)

        self.net_label = make_label("starting network...", size=11, color=MUTED,
                                    size_hint_y=None, height=dp(18), shorten=True)
        rw.add_widget(self.net_label)

        stats = GridLayout(cols=3, spacing=dp(8), size_hint_y=None, height=dp(66))
        self.traffic_card = StatCard("TRAFFIC", "0.0 KB", ACCENT)
        self.requests_card = StatCard("REQUESTS", "0", WARN)
        self.tunnels_card = StatCard("TUNNELS", "0", GOOD)
        for c in (self.traffic_card, self.requests_card, self.tunnels_card):
            stats.add_widget(c)
        rw.add_widget(stats)

        bind_panel = Panel(orientation="vertical", padding=dp(12), spacing=dp(10),
                           size_hint_y=None, height=dp(124))
        row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        self.subdomain_field = Field(hint="name (e.g. clipsy)", size_hint_x=0.62)
        self.port_field = Field(hint="port", size_hint_x=0.38)
        row.add_widget(self.subdomain_field)
        row.add_widget(self.port_field)
        bind_panel.add_widget(row)
        bind_panel.add_widget(NeonButton(text="[ BIND APP ]", size_hint_y=None, height=dp(46),
                                         on_release=self.execute_node_binding))
        rw.add_widget(bind_panel)

        self.nodes_tracker_label = make_label(
            f"// REGISTERED APPS  0/{MAX_APPS}", size=12, color=MUTED,
            size_hint_y=None, height=dp(22))
        rw.add_widget(self.nodes_tracker_label)

        self.routing_grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        self.routing_grid.bind(minimum_height=self.routing_grid.setter("height"))
        routing_scroll = ScrollView(size_hint=(1, 0.55), bar_width=0)
        routing_scroll.add_widget(self.routing_grid)
        rw.add_widget(routing_scroll)

        rw.add_widget(make_label("// LIVE LOG", size=12, color=MUTED,
                                 size_hint_y=None, height=dp(22)))

        log_panel = Panel(orientation="vertical", padding=dp(10), size_hint=(1, 0.45),
                          border=BORDER_DIM)
        self.syslog_grid = GridLayout(cols=1, spacing=dp(2), size_hint_y=None)
        self.syslog_grid.bind(minimum_height=self.syslog_grid.setter("height"))
        syslog_scroll = ScrollView(bar_width=0)
        syslog_scroll.add_widget(self.syslog_grid)
        log_panel.add_widget(syslog_scroll)
        rw.add_widget(log_panel)

        self.refresh_routing_display_tree()

    @guarded
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
            self.core.log(f"Bound {name}.engine -> port {port_num}")
        else:
            self.core.log("Limit reached: 15 apps maximum.")

    @guarded
    def execute_node_purge(self, subdomain):
        self.core.drop_node(subdomain)
        self.refresh_routing_display_tree()
        self.core.log(f"Unbound {subdomain}.engine")

    def refresh_routing_display_tree(self):
        self.routing_grid.clear_widgets()

        if not self.core.registry:
            self.routing_grid.add_widget(make_label(
                "no apps bound. add a name and port above.",
                size=12, color=MUTED, halign="center",
                size_hint_y=None, height=dp(60)))

        for subdomain, config in self.core.registry.items():
            row = Panel(orientation="horizontal", padding=[dp(14), dp(8)], spacing=dp(10),
                        size_hint_y=None, height=dp(60))
            info = BoxLayout(orientation="vertical")
            info.add_widget(make_label(f"{subdomain}.engine", size=14, color=ACCENT))
            info.add_widget(make_label(
                f"{self.core.url_for(subdomain)}  >  :{config['port']}",
                size=11, color=MUTED, shorten=True))
            row.add_widget(info)
            row.add_widget(NeonButton(
                text="UNBIND", bg=DANGER, fg=BG, size_hint_x=None, width=dp(84),
                font_size=sp(11),
                on_release=lambda inst, s=subdomain: self.execute_node_purge(s)))
            self.routing_grid.add_widget(row)

        self.nodes_tracker_label.text = (
            f"// REGISTERED APPS  {len(self.core.registry)}/{MAX_APPS}")

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
                f"proxy:{self.core.proxy_port or '-'}  dns:{self.core.dns_port or '-'}"
                f"  ip:{self.core.lan_ip}")

            key = (len(self.log_buffer), self.log_buffer[-1] if self.log_buffer else "")
            if key != self._rendered_log_key:
                self._rendered_log_key = key
                self.syslog_grid.clear_widgets()
                for entry in reversed(self.log_buffer):
                    self.syslog_grid.add_widget(make_label(
                        "> " + entry, size=10, color=MUTED,
                        size_hint_y=None, height=dp(20),
                        shorten=True, shorten_from="right"))
        except Exception:
            pass

    def on_stop(self):
        if getattr(self, "core", None) is not None:
            self.core.stop()


if __name__ == "__main__":
    EnginePlatform().run()
