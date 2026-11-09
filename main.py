import os
import json
import time
import threading
import traceback
from urllib.parse import urlparse

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

# If a required module is missing from the app, show a clean message instead
# of closing silently. Details go to a private log file only.
try:
    from engine_core import InfrastructureCore, MAX_APPS, default_registry_path
    from engine_infra import (password_checks, read_auth, write_auth, check_auth,
                              MAX_FAILS, LOCK_SECONDS, RemoteClient)
    IMPORT_ERROR = None
except Exception:
    IMPORT_ERROR = traceback.format_exc()
    InfrastructureCore = None
    MAX_APPS = 15
    default_registry_path = None

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


def level_color(pct):
    return GOOD if pct < 60 else (WARN if pct < 85 else DANGER)


def fmt_bytes(n):
    n = float(n or 0)
    if n < 1024:
        return f"{int(n)} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.2f} GB"


def fmt_uptime(s):
    s = int(s or 0)
    d, h, m = s // 86400, s % 86400 // 3600, s % 3600 // 60
    return (f"{d}d " if d else "") + f"{h}h {m}m"


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


def open_url(url):
    try:
        if platform == "android":
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        else:
            import webbrowser
            webbrowser.open(url)
    except Exception:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass


# =====================================================================
# WIDGETS
# =====================================================================
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


class Bar(Widget):
    def __init__(self, **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(6))
        super().__init__(**kw)
        self._frac = 0.0
        self._col = list(GOOD)
        self.bind(pos=self._draw, size=self._draw)

    def set(self, frac, color):
        self._frac = max(0.0, min(1.0, frac))
        self._col = list(color)
        self._draw()

    def _draw(self, *args):
        self.canvas.clear()
        with self.canvas:
            Color(0.06, 0.12, 0.18, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(3)])
            Color(*self._col)
            RoundedRectangle(pos=self.pos, size=(self.width * self._frac, self.height),
                             radius=[dp(3)])


class StatCard(Panel):
    def __init__(self, title, value, accent=ACCENT, **kw):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(2), **kw)
        self.value_label = make_label(value, size=17, color=accent)
        self.add_widget(self.value_label)
        self.add_widget(make_label(title, size=10, color=MUTED))


class MeterCard(Panel):
    def __init__(self, title, **kw):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(3), **kw)
        self.add_widget(make_label(title, size=10, color=MUTED))
        self.value = make_label("--", size=16, color=ACCENT)
        self.add_widget(self.value)
        self.bar = Bar()
        self.add_widget(self.bar)

    def set(self, pct, text=None):
        if pct is None:
            self.value.text = text or "n/a"
            self.bar.set(0, GOOD)
        else:
            self.value.text = text or f"{pct:.0f}%"
            self.bar.set(pct / 100.0, level_color(pct))


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

        self.phone = platform in ("android", "ios")
        if self.phone:
            Window.softinput_mode = "below_target"
        else:
            Window.size = (860, 940)

        self._rendered_log_key = None
        self.status_labels = {}
        self._fails = 0
        self._locked_until = 0
        self._last_snapshot = 0
        self._entries_key = None
        self.client = None
        self._remote_state = None
        self._remote_error = None
        self._polling = False
        self._poll_event = None

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

        if self.phone:
            self.render_connect()
        else:
            self.core = InfrastructureCore(self.post_log_message)
            self.core.set_storage_path(default_registry_path())
            self.auth_file = self.core.auth_path()
            self.auth = read_auth(self.auth_file)
            if self.auth:
                self.render_secure_gateway()
            else:
                self.render_setup()
        return root

    def _fit_width(self, window, width):
        self.shell.width = min(width, dp(640 if self.phone else 860))

    def on_pause(self):
        return True

    def on_resume(self):
        pass

    def post_log_message(self, text):
        entry = f"{time.strftime('%H:%M:%S')}  {text}"
        self.log_buffer.append(entry)
        if len(self.log_buffer) > 40:
            self.log_buffer.pop(0)

    # =================================================================
    # DESKTOP: login / first-time setup
    # =================================================================
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
        now = time.time()
        if now < self._locked_until:
            self.auth_error.text = f"LOCKED. TRY AGAIN IN {int(self._locked_until - now) + 1}s"
            return
        entered = self.pass_field.input.text.strip()
        if check_auth(self.auth, entered):
            self._fails = 0
            self._enter_console()
            return
        self._fails += 1
        self.pass_field.input.text = ""
        if self._fails >= MAX_FAILS:
            self._fails = 0
            self._locked_until = now + LOCK_SECONDS
            self.auth_error.text = f"TOO MANY ATTEMPTS. LOCKED FOR {LOCK_SECONDS}s"
        else:
            self.auth_error.text = "ACCESS DENIED"

    def _enter_console(self):
        self.core.start()
        self.render_system_console()
        Clock.schedule_interval(self.update_telemetry_metrics, 0.5)

    def render_setup(self):
        rw = self.shell
        rw.clear_widgets()
        rw.add_widget(BoxLayout(size_hint_y=0.05))
        rw.add_widget(make_label("> .engine", size=34, color=ACCENT, halign="center",
                                 size_hint_y=None, height=dp(52)))
        rw.add_widget(make_label("FIRST-TIME SETUP  //  CREATE ACCESS KEY", size=11,
                                 color=MUTED, halign="center", size_hint_y=None,
                                 height=dp(22)))

        panel = Panel(orientation="vertical", padding=dp(16), spacing=dp(10),
                      size_hint_y=None, height=dp(452))
        panel.add_widget(make_label("NEW PASSWORD", size=11, color=MUTED,
                                    size_hint_y=None, height=dp(16)))
        self.new_field = Field(hint="new password", password=True)
        panel.add_widget(self.new_field)
        panel.add_widget(make_label("CONFIRM PASSWORD", size=11, color=MUTED,
                                    size_hint_y=None, height=dp(16)))
        self.confirm_field = Field(hint="repeat password", password=True)
        panel.add_widget(self.confirm_field)

        self.req_labels = []
        for text, _ in password_checks(""):
            lbl = make_label("[ ] " + text, size=11, color=MUTED,
                             size_hint_y=None, height=dp(18))
            self.req_labels.append(lbl)
            panel.add_widget(lbl)
        self.match_label = make_label("", size=11, color=MUTED,
                                      size_hint_y=None, height=dp(18))
        panel.add_widget(self.match_label)

        self.setup_button = NeonButton(text="[ CREATE KEY ]", size_hint_y=None,
                                       height=dp(46), on_release=self.complete_setup)
        panel.add_widget(self.setup_button)
        rw.add_widget(panel)
        rw.add_widget(BoxLayout())

        self.new_field.input.bind(text=self._refresh_requirements)
        self.confirm_field.input.bind(text=self._refresh_requirements)
        self.confirm_field.input.bind(on_text_validate=lambda inst: self.complete_setup(None))
        self._refresh_requirements()

    def _setup_is_valid(self):
        pw = self.new_field.input.text
        return (all(ok for _, ok in password_checks(pw))
                and pw == self.confirm_field.input.text)

    def _refresh_requirements(self, *args):
        pw = self.new_field.input.text
        for lbl, (text, ok) in zip(self.req_labels, password_checks(pw)):
            lbl.text = ("[x] " if ok else "[ ] ") + text
            lbl.color = GOOD if ok else MUTED
        confirm = self.confirm_field.input.text
        if not confirm:
            self.match_label.text = ""
        elif confirm == pw:
            self.match_label.text = "[x] Passwords match"
            self.match_label.color = GOOD
        else:
            self.match_label.text = "[ ] Passwords do not match"
            self.match_label.color = DANGER
        valid = self._setup_is_valid()
        self.setup_button.disabled = not valid
        self.setup_button.opacity = 1 if valid else 0.4

    @guarded
    def complete_setup(self, instance):
        if not self._setup_is_valid():
            return
        write_auth(self.auth_file, self.new_field.input.text)
        self.auth = read_auth(self.auth_file)
        self._enter_console()

    # =================================================================
    # DESKTOP: full console
    # =================================================================
    def render_system_console(self):
        rw = self.shell
        rw.clear_widgets()
        self._entries_key = None

        hero = Panel(orientation="horizontal", padding=[dp(16), dp(10)], spacing=dp(8),
                     size_hint_y=None, height=dp(80))
        left = BoxLayout(orientation="vertical")
        left.add_widget(make_label("> .engine", size=26, color=ACCENT))
        self.net_label = make_label("starting network...", size=10, color=MUTED, shorten=True)
        left.add_widget(self.net_label)
        hero.add_widget(left)
        right = BoxLayout(orientation="vertical", spacing=dp(6),
                          size_hint_x=None, width=dp(130))
        self.status_label = make_label("[ ONLINE ]", size=12, color=GOOD, halign="right")
        right.add_widget(self.status_label)
        right.add_widget(NeonButton(text="DASHBOARD", font_size=sp(11), size_hint_y=None,
                                    height=dp(32), on_release=self.open_dashboard))
        hero.add_widget(right)
        rw.add_widget(hero)

        stats = GridLayout(cols=3, spacing=dp(8), size_hint_y=None, height=dp(62))
        self.traffic_card = StatCard("TRAFFIC", "0 B", ACCENT)
        self.requests_card = StatCard("REQUESTS", "0", WARN)
        self.tunnels_card = StatCard("TUNNELS", "0", GOOD)
        for c in (self.traffic_card, self.requests_card, self.tunnels_card):
            stats.add_widget(c)
        rw.add_widget(stats)

        meters = GridLayout(cols=4, spacing=dp(8), size_hint_y=None, height=dp(78))
        self.cpu_meter = MeterCard("CPU")
        self.ram_meter = MeterCard("RAM")
        self.gpu_meter = MeterCard("GPU")
        self.disk_meter = MeterCard("DISK")
        for m in (self.cpu_meter, self.ram_meter, self.gpu_meter, self.disk_meter):
            meters.add_widget(m)
        rw.add_widget(meters)

        bind_panel = Panel(orientation="vertical", padding=dp(12), spacing=dp(8),
                           size_hint_y=None, height=dp(214))
        row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        self.subdomain_field = Field(hint="name (e.g. shop)", size_hint_x=0.4)
        self.port_field = Field(hint="port / folder / blank", size_hint_x=0.6)
        row.add_widget(self.subdomain_field)
        row.add_widget(self.port_field)
        bind_panel.add_widget(row)
        self.command_field = Field(hint="start command (optional): python app.py")
        bind_panel.add_widget(self.command_field)
        bind_panel.add_widget(make_label(
            "port = app  |  folder = site  |  blank = new site  |  command = engine runs it",
            size=10, color=MUTED, size_hint_y=None, height=dp(16)))
        bind_panel.add_widget(NeonButton(text="[ REGISTER ]", size_hint_y=None, height=dp(46),
                                         on_release=self.execute_node_binding))
        rw.add_widget(bind_panel)

        self.nodes_tracker_label = make_label(
            f"// SITES AND APPS  0/{MAX_APPS}", size=12, color=MUTED,
            size_hint_y=None, height=dp(22))
        rw.add_widget(self.nodes_tracker_label)

        self.routing_grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        self.routing_grid.bind(minimum_height=self.routing_grid.setter("height"))
        routing_scroll = ScrollView(size_hint=(1, 0.55), bar_width=0)
        routing_scroll.add_widget(self.routing_grid)
        rw.add_widget(routing_scroll)

        rw.add_widget(make_label("// LIVE LOG", size=12, color=MUTED,
                                 size_hint_y=None, height=dp(22)))
        log_panel = Panel(orientation="vertical", padding=dp(10), size_hint=(1, 0.4),
                          border=BORDER_DIM)
        self.syslog_grid = GridLayout(cols=1, spacing=dp(2), size_hint_y=None)
        self.syslog_grid.bind(minimum_height=self.syslog_grid.setter("height"))
        syslog_scroll = ScrollView(bar_width=0)
        syslog_scroll.add_widget(self.syslog_grid)
        log_panel.add_widget(syslog_scroll)
        rw.add_widget(log_panel)

        self.refresh_routing_display_tree()

    @guarded
    def open_dashboard(self, instance):
        open_url(f"http://localhost:{self.core.admin_port or 9090}")

    @guarded
    def execute_node_binding(self, instance):
        ok, message = self.core.register(
            self.subdomain_field.input.text, self.port_field.input.text,
            self.command_field.input.text)
        self.core.log(message)
        if ok:
            self.subdomain_field.input.text = ""
            self.port_field.input.text = ""
            self.command_field.input.text = ""
            self.refresh_routing_display_tree()

    @guarded
    def execute_node_purge(self, subdomain):
        self.core.drop_node(subdomain)
        self.refresh_routing_display_tree()
        self.core.log(f"Unbound {subdomain}.engine")

    @guarded
    def toggle_app(self, name):
        procs = self.core.procs

        def work():
            if procs.is_running(name):
                procs.stop(name)
            else:
                procs.start(name)
        threading.Thread(target=work, daemon=True).start()

    # ---------------- SITE EDITOR ----------------
    @guarded
    def open_editor(self, name):
        path = self.core.site_index_path(name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            content = ""
        self._editing = name
        rw = self.shell
        rw.clear_widgets()
        rw.add_widget(make_label(f"> edit {name}.engine", size=16, color=ACCENT,
                                 size_hint_y=None, height=dp(34)))
        rw.add_widget(make_label("index.html: paste or write your page, then SAVE",
                                 size=11, color=MUTED, size_hint_y=None, height=dp(20)))
        panel = Panel(orientation="vertical", padding=dp(8), size_hint=(1, 1))
        self.editor_input = TextInput(
            text=content, multiline=True, write_tab=False,
            background_normal="", background_active="", background_color=(0, 0, 0, 0),
            foreground_color=TEXT, cursor_color=ACCENT, font_name=FONT, font_size=sp(12))
        panel.add_widget(self.editor_input)
        rw.add_widget(panel)
        self.editor_msg = make_label("", size=11, color=GOOD, size_hint_y=None, height=dp(18))
        rw.add_widget(self.editor_msg)
        buttons = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        buttons.add_widget(NeonButton(text="[ SAVE ]", on_release=self.save_editor))
        buttons.add_widget(NeonButton(text="[ BACK ]", bg=MUTED, on_release=self.close_editor))
        rw.add_widget(buttons)

    @guarded
    def save_editor(self, instance):
        path = self.core.site_index_path(self._editing)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.editor_input.text)
        self.editor_msg.text = "Saved. Reload the page in your browser."
        self.core.log(f"Saved {self._editing}.engine")

    @guarded
    def close_editor(self, instance):
        self._rendered_log_key = None
        self.render_system_console()

    # ---------------- entries list ----------------
    def _entry_line(self, cfg, label):
        kind = "SITE" if cfg.get("type") == "site" else f"APP :{cfg.get('port')}"
        return f"{kind}  |  {label}"

    def refresh_routing_display_tree(self):
        self.routing_grid.clear_widgets()
        self.status_labels = {}

        if not self.core.registry:
            self.routing_grid.add_widget(make_label(
                "nothing registered yet. add a name above.",
                size=12, color=MUTED, halign="center",
                size_hint_y=None, height=dp(60)))

        for name, cfg in self.core.registry.items():
            is_site = cfg.get("type") == "site"
            managed = bool(cfg.get("command"))
            row = Panel(orientation="horizontal", padding=[dp(14), dp(8)], spacing=dp(8),
                        size_hint_y=None, height=dp(84))
            info = BoxLayout(orientation="vertical")
            info.add_widget(make_label(f"{name}.engine", size=14, color=ACCENT))
            info.add_widget(make_label(self.core.url_for(name), size=11, color=MUTED,
                                       shorten=True))
            label, ok = self.core.entry_status(name)
            state = make_label(self._entry_line(cfg, label), size=11,
                               color=GOOD if ok else WARN)
            self.status_labels[name] = state
            info.add_widget(state)
            row.add_widget(info)

            actions = BoxLayout(orientation="vertical", spacing=dp(6),
                                size_hint_x=None, width=dp(86))
            if is_site:
                actions.add_widget(NeonButton(
                    text="EDIT", font_size=sp(11),
                    on_release=lambda inst, n=name: self.open_editor(n)))
            elif managed:
                actions.add_widget(NeonButton(
                    text="START/STOP", font_size=sp(10),
                    on_release=lambda inst, n=name: self.toggle_app(n)))
            actions.add_widget(NeonButton(
                text="UNBIND", bg=DANGER, font_size=sp(11),
                on_release=lambda inst, n=name: self.execute_node_purge(n)))
            row.add_widget(actions)
            self.routing_grid.add_widget(row)

        self.nodes_tracker_label.text = (
            f"// SITES AND APPS  {len(self.core.registry)}/{MAX_APPS}")

    def _apply_snapshot(self, snap):
        self.net_label.text = (
            f"proxy:{snap['proxy_port'] or '-'}  dns:{snap['dns_port'] or '-'}  "
            f"dashboard:{snap['admin_port'] or '-'}  ip:{snap['lan_ip']}")
        m = snap["metrics"]
        self.cpu_meter.set(m["cpu"])
        self.ram_meter.set(m["mem"]["percent"] if m["mem"] else None)
        self.disk_meter.set(m["disk"]["percent"] if m["disk"] else None)
        if m["gpus"]:
            self.gpu_meter.set(m["gpus"][0]["util"])
        else:
            self.gpu_meter.set(None, "none")
        key = tuple(sorted(e["name"] for e in snap["entries"]))
        if key != self._entries_key:
            self._entries_key = key
            self.refresh_routing_display_tree()
        for e in snap["entries"]:
            label = self.status_labels.get(e["name"])
            if label is not None:
                label.text = self._entry_line(self.core.registry.get(e["name"], {}), e["status"])
                label.color = GOOD if e["ok"] else WARN

    def update_telemetry_metrics(self, dt):
        try:
            core = self.core
            self.traffic_card.value_label.text = fmt_bytes(core.bytes_transferred)
            self.requests_card.value_label.text = str(core.total_requests)
            self.tunnels_card.value_label.text = str(core.active_tunnels)

            now = time.time()
            if now - self._last_snapshot >= 2:
                self._last_snapshot = now
                self._apply_snapshot(core.snapshot())

            merged = sorted(set(self.log_buffer))[-40:]
            key = (len(merged), merged[-1] if merged else "")
            if key != self._rendered_log_key:
                self._rendered_log_key = key
                self.syslog_grid.clear_widgets()
                for entry in reversed(merged):
                    self.syslog_grid.add_widget(make_label(
                        "> " + entry, size=10, color=MUTED,
                        size_hint_y=None, height=dp(20),
                        shorten=True, shorten_from="right"))
        except Exception:
            pass

    # =================================================================
    # PHONE: small companion (monitor the desktop engine, open sites)
    # =================================================================
    def _prefs_path(self):
        return os.path.join(self.user_data_dir, "phone.json")

    def _load_prefs(self):
        try:
            with open(self._prefs_path(), "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_prefs(self, data):
        try:
            with open(self._prefs_path(), "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def render_connect(self):
        if self._poll_event is not None:
            self._poll_event.cancel()
            self._poll_event = None
        rw = self.shell
        rw.clear_widgets()
        rw.add_widget(BoxLayout(size_hint_y=0.12))
        rw.add_widget(make_label("> .engine", size=38, color=ACCENT, halign="center",
                                 size_hint_y=None, height=dp(60)))
        rw.add_widget(make_label("COMPANION  //  CONNECT TO YOUR ENGINE", size=11,
                                 color=MUTED, halign="center", size_hint_y=None,
                                 height=dp(22)))

        panel = Panel(orientation="vertical", padding=dp(16), spacing=dp(10),
                      size_hint_y=None, height=dp(274))
        panel.add_widget(make_label("ENGINE ADDRESS", size=11, color=MUTED,
                                    size_hint_y=None, height=dp(16)))
        self.addr_field = Field(hint="192.168.1.20  or  host:9090")
        self.addr_field.input.text = self._load_prefs().get("address", "")
        panel.add_widget(self.addr_field)
        panel.add_widget(make_label("ACCESS KEY", size=11, color=MUTED,
                                    size_hint_y=None, height=dp(16)))
        self.key_field = Field(hint="access key", password=True)
        self.key_field.input.bind(on_text_validate=lambda inst: self.connect(None))
        panel.add_widget(self.key_field)
        self.connect_msg = make_label("", size=11, color=DANGER,
                                      size_hint_y=None, height=dp(16))
        panel.add_widget(self.connect_msg)
        panel.add_widget(NeonButton(text="[ CONNECT ]", size_hint_y=None, height=dp(46),
                                    on_release=self.connect))
        rw.add_widget(panel)
        rw.add_widget(make_label(
            "The full engine runs on your computer.\n"
            "This app monitors it and opens your sites.",
            size=11, color=MUTED, halign="center", size_hint_y=None, height=dp(44)))
        rw.add_widget(BoxLayout())

    @guarded
    def connect(self, instance):
        address = self.addr_field.input.text.strip()
        key = self.key_field.input.text
        if not address or not key:
            self.connect_msg.text = "Enter the address and your access key."
            self.connect_msg.color = DANGER
            return
        self.connect_msg.text = "Connecting..."
        self.connect_msg.color = MUTED

        def work():
            client, ok, err = None, False, ""
            try:
                client = RemoteClient(address)
                ok, err = client.login(key)
            except Exception:
                err = ("Cannot reach the engine. Check the address and that "
                       "your phone is on the same Wi-Fi.")
            Clock.schedule_once(lambda dt: self._connected(client, address, ok, err), 0)
        threading.Thread(target=work, daemon=True).start()

    def _connected(self, client, address, ok, err):
        if not ok:
            self.connect_msg.text = err
            self.connect_msg.color = DANGER
            return
        self.client = client
        self._save_prefs({"address": address})
        self._remote_state = None
        self._remote_error = None
        self._entries_key = None
        self.render_phone_home()
        self._poll_event = Clock.schedule_interval(self._phone_tick, 2.0)
        self._phone_tick(0)

    def render_phone_home(self):
        rw = self.shell
        rw.clear_widgets()

        hero = Panel(orientation="horizontal", padding=[dp(16), dp(10)], spacing=dp(8),
                     size_hint_y=None, height=dp(80))
        left = BoxLayout(orientation="vertical")
        left.add_widget(make_label("> .engine", size=26, color=ACCENT))
        self.host_label = make_label("connecting...", size=10, color=MUTED, shorten=True)
        left.add_widget(self.host_label)
        hero.add_widget(left)
        right = BoxLayout(orientation="vertical", spacing=dp(6),
                          size_hint_x=None, width=dp(112))
        self.status_label = make_label("[ ... ]", size=12, color=WARN, halign="right")
        right.add_widget(self.status_label)
        right.add_widget(NeonButton(text="LOCK", bg=MUTED, font_size=sp(11),
                                    size_hint_y=None, height=dp(32),
                                    on_release=self.disconnect))
        hero.add_widget(right)
        rw.add_widget(hero)

        rw.add_widget(NeonButton(text="[ OPEN FULL DASHBOARD ]", size_hint_y=None,
                                 height=dp(46), on_release=self.open_remote_dashboard))

        stats = GridLayout(cols=3, spacing=dp(8), size_hint_y=None, height=dp(62))
        self.live_card = StatCard("LIVE", "-", GOOD)
        self.requests_card = StatCard("REQUESTS", "-", WARN)
        self.traffic_card = StatCard("TRAFFIC", "-", ACCENT)
        for c in (self.live_card, self.requests_card, self.traffic_card):
            stats.add_widget(c)
        rw.add_widget(stats)

        meters = GridLayout(cols=3, spacing=dp(8), size_hint_y=None, height=dp(78))
        self.cpu_meter = MeterCard("CPU")
        self.ram_meter = MeterCard("RAM")
        self.gpu_meter = MeterCard("GPU")
        for m in (self.cpu_meter, self.ram_meter, self.gpu_meter):
            meters.add_widget(m)
        rw.add_widget(meters)

        rw.add_widget(make_label("// SITES AND APPS", size=12, color=MUTED,
                                 size_hint_y=None, height=dp(22)))
        self.routing_grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        self.routing_grid.bind(minimum_height=self.routing_grid.setter("height"))
        scroll = ScrollView(bar_width=0)
        scroll.add_widget(self.routing_grid)
        rw.add_widget(scroll)

    @guarded
    def disconnect(self, instance):
        self.client = None
        self.render_connect()

    @guarded
    def open_remote_dashboard(self, instance):
        if self.client:
            open_url(self.client.base)

    def _phone_tick(self, dt):
        if self.client is None:
            return
        if not self._polling:
            self._polling = True
            threading.Thread(target=self._phone_fetch, daemon=True).start()
        self._apply_remote()

    def _phone_fetch(self):
        try:
            status, body = self.client.state()
            if status == 200:
                self._remote_state = body
                self._remote_error = None
            elif status == 401:
                self._remote_error = "SESSION"
            else:
                self._remote_error = "ERROR"
        except Exception:
            self._remote_error = "OFFLINE"
        finally:
            self._polling = False

    def _apply_remote(self):
        try:
            if self._remote_error == "SESSION":
                self.client = None
                self.render_connect()
                self.connect_msg.text = "Session ended. Connect again."
                return
            s = self._remote_state
            if s is None or self._remote_error in ("OFFLINE", "ERROR"):
                self.status_label.text = "[ OFFLINE ]" if s is not None else "[ ... ]"
                self.status_label.color = DANGER if s is not None else WARN
                return

            host = urlparse(self.client.base).hostname
            self.status_label.text = "[ CONNECTED ]"
            self.status_label.color = GOOD
            self.host_label.text = f"{host}  up {fmt_uptime(s['uptime'])}  v{s['version']}"

            entries = s["entries"]
            live = sum(1 for e in entries if e["ok"])
            self.live_card.value_label.text = f"{live}/{len(entries)}"
            self.requests_card.value_label.text = str(s["totals"]["requests"])
            self.traffic_card.value_label.text = fmt_bytes(s["totals"]["bytes"])

            m = s["metrics"]
            self.cpu_meter.set(m["cpu"])
            self.ram_meter.set(m["mem"]["percent"] if m["mem"] else None)
            if m["gpus"]:
                self.gpu_meter.set(m["gpus"][0]["util"])
            else:
                self.gpu_meter.set(None, "none")

            key = tuple((e["name"], e["status"], e["type"]) for e in entries)
            if key != self._entries_key:
                self._entries_key = key
                self._fill_phone_list(entries, host, s.get("proxy_port"))
        except Exception:
            pass

    def _fill_phone_list(self, entries, host, proxy_port):
        self.routing_grid.clear_widgets()
        if not entries:
            self.routing_grid.add_widget(make_label(
                "nothing registered yet. add sites on your computer.",
                size=12, color=MUTED, halign="center", size_hint_y=None, height=dp(60)))
        for e in entries:
            row = Panel(orientation="horizontal", padding=[dp(14), dp(8)], spacing=dp(8),
                        size_hint_y=None, height=dp(72))
            info = BoxLayout(orientation="vertical")
            info.add_widget(make_label(f"{e['name']}.engine", size=14, color=ACCENT))
            kind = "SITE" if e["type"] == "site" else f"APP :{e['port']}"
            info.add_widget(make_label(f"{kind}  |  {e['status']}", size=11,
                                       color=GOOD if e["ok"] else WARN))
            row.add_widget(info)
            url = f"http://{host}:{proxy_port}/_/{e['name']}/" if proxy_port else None
            row.add_widget(NeonButton(
                text="OPEN", font_size=sp(12), size_hint_x=None, width=dp(78),
                on_release=lambda inst, u=url: open_url(u) if u else None))
            self.routing_grid.add_widget(row)

    def on_stop(self):
        core = getattr(self, "core", None)
        if core is not None:
            core.stop()


if __name__ == "__main__":
    EnginePlatform().run()
