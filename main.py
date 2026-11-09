import os
import json
import hmac
import hashlib
import secrets
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
    from engine_core import (InfrastructureCore, MAX_APPS, default_registry_path,
                         probe_port, valid_name)
    IMPORT_ERROR = None
except Exception:
    IMPORT_ERROR = traceback.format_exc()
    InfrastructureCore = None
    MAX_APPS = 15
    default_registry_path = None

# =====================================================================
# SECURITY: the owner creates the access key on first launch.
# Only a salted PBKDF2 hash is stored on the device, never the password.
# =====================================================================
ITERATIONS = 150000
MIN_LENGTH = 8
MAX_FAILS = 5
LOCK_SECONDS = 30


def password_checks(pw):
    """Returns [(requirement text, satisfied?)] for the password rules."""
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


# =====================================================================
# ANDROID: background service, notifications, battery exemption
# =====================================================================
SERVICE_CLASS = "org.cipheraegis.enginecore.ServiceEngine"


def _activity():
    from jnius import autoclass
    return autoclass("org.kivy.android.PythonActivity").mActivity


def start_engine_service():
    """Returns None on success, or a short error text."""
    try:
        from jnius import autoclass
        autoclass(SERVICE_CLASS).start(_activity(), "")
        return None
    except Exception as first:
        try:
            from android import AndroidService
            AndroidService(".engine", "Domain engine is running").start("")
            return None
        except Exception as second:
            return f"{type(first).__name__}: {first} | {type(second).__name__}: {second}"[:200]


def stop_engine_service():
    try:
        from jnius import autoclass
        autoclass(SERVICE_CLASS).stop(_activity())
        return None
    except Exception as e:
        return f"{type(e).__name__}: {e}"[:200]


def request_notifications():
    try:
        from android.permissions import request_permissions
        request_permissions(["android.permission.POST_NOTIFICATIONS"])
    except Exception:
        pass


def battery_unrestricted():
    """True if the app may run in the background without battery limits."""
    try:
        from jnius import autoclass
        Context = autoclass("android.content.Context")
        activity = _activity()
        pm = activity.getSystemService(Context.POWER_SERVICE)
        return bool(pm.isIgnoringBatteryOptimizations(activity.getPackageName()))
    except Exception:
        return True  # unknown: do not nag


def request_battery_exemption():
    try:
        from jnius import autoclass
        Intent = autoclass("android.content.Intent")
        Settings = autoclass("android.provider.Settings")
        Uri = autoclass("android.net.Uri")
        activity = _activity()
        intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
        intent.setData(Uri.parse("package:" + activity.getPackageName()))
        activity.startActivity(intent)
    except Exception:
        pass


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
        self.core.set_storage_path(default_registry_path())
        data_folder = os.path.dirname(default_registry_path())
        self.status_file = os.path.join(data_folder, "engine_status.json")
        self._started_at = 0
        self._engine_online = False
        self._last_probe = 0
        self.status_labels = {}

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

        self._fails = 0
        self._locked_until = 0
        self.auth_file = os.path.join(data_folder, "engine_auth.json")
        self.auth = read_auth(self.auth_file)
        if self.auth:
            self.render_secure_gateway()
        else:
            self.render_setup()
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
        if platform == "android":
            request_notifications()
            self._started_at = time.time()
            err = start_engine_service()
            if err:
                record_error(self, err)
                self.post_log_message("Background service unavailable.")
            Clock.schedule_once(self._ask_battery, 2.0)
        else:
            self.core.start()
        self.render_system_console()
        Clock.schedule_interval(self.update_telemetry_metrics, 0.5)

    def _ask_battery(self, dt):
        if not battery_unrestricted():
            request_battery_exemption()

    @guarded
    def toggle_engine(self, instance):
        if self._engine_online:
            err = stop_engine_service()
        else:
            self._started_at = time.time()
            err = start_engine_service()
        if err:
            record_error(self, err)
            self.post_log_message("Service command failed.")

    # ---------------- FIRST-TIME SETUP ----------------
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

    # ---------------- CONSOLE ----------------
    def render_system_console(self):
        rw = self.shell
        rw.clear_widgets()

        header = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        header.add_widget(make_label("> .engine", size=24, color=ACCENT))
        self.status_label = make_label("[ STARTING ]", size=12, color=WARN, halign="right",
                                       size_hint_x=None, width=dp(104))
        header.add_widget(self.status_label)
        self.power_button = None
        if platform == "android":
            self.power_button = NeonButton(text="STOP", bg=DANGER, size_hint_x=None,
                                           width=dp(64), font_size=sp(12),
                                           on_release=self.toggle_engine)
            header.add_widget(self.power_button)
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

        bind_panel = Panel(orientation="vertical", padding=dp(12), spacing=dp(8),
                           size_hint_y=None, height=dp(150))
        row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        self.subdomain_field = Field(hint="name (e.g. shop)", size_hint_x=0.4)
        self.port_field = Field(hint="port / folder / blank", size_hint_x=0.6)
        row.add_widget(self.subdomain_field)
        row.add_widget(self.port_field)
        bind_panel.add_widget(row)
        bind_panel.add_widget(make_label(
            "port = app you run   |   folder = site   |   blank = new site",
            size=10, color=MUTED, size_hint_y=None, height=dp(16)))
        bind_panel.add_widget(NeonButton(text="[ REGISTER ]", size_hint_y=None, height=dp(46),
                                         on_release=self.execute_node_binding))
        rw.add_widget(bind_panel)

        self.nodes_tracker_label = make_label(
            f"// REGISTERED  0/{MAX_APPS}", size=12, color=MUTED,
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
        target = self.port_field.input.text.strip()

        if not valid_name(name):
            self.core.log("Name: letters, numbers and dashes only.")
            return

        if target == "":
            ok, what = self.core.add_site(name), "site"
        elif target.isdigit():
            port_num = int(target)
            if not (1024 <= port_num <= 65535):
                self.core.log("Port must be between 1024 and 65535.")
                return
            ok, what = self.core.add_node(name, port_num), f"app on port {port_num}"
        else:
            folder = os.path.abspath(os.path.expanduser(target))
            if not os.path.isdir(folder):
                self.core.log("Folder not found.")
                return
            ok, what = self.core.add_site(name, folder), "site"

        if ok:
            self.subdomain_field.input.text = ""
            self.port_field.input.text = ""
            self.refresh_routing_display_tree()
            self.core.log(f"Registered {name}.engine ({what})")
        else:
            self.core.log("Limit reached: 15 entries maximum.")

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
        self.editor_msg.text = "Saved. Reload the page in Chrome."
        self.core.log(f"Saved {self._editing}.engine")

    @guarded
    def close_editor(self, instance):
        self._rendered_log_key = None
        self.render_system_console()

    @guarded
    def execute_node_purge(self, subdomain):
        self.core.drop_node(subdomain)
        self.refresh_routing_display_tree()
        self.core.log(f"Unbound {subdomain}.engine")

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
            row = Panel(orientation="horizontal", padding=[dp(14), dp(8)], spacing=dp(8),
                        size_hint_y=None, height=dp(84))
            info = BoxLayout(orientation="vertical")
            info.add_widget(make_label(f"{name}.engine", size=14, color=ACCENT))
            info.add_widget(make_label(self.core.url_for(name), size=11, color=MUTED,
                                       shorten=True))
            state = make_label("...", size=11, color=MUTED)
            self.status_labels[name] = state
            info.add_widget(state)
            row.add_widget(info)

            actions = BoxLayout(orientation="vertical", spacing=dp(6),
                                size_hint_x=None, width=dp(78))
            if is_site:
                actions.add_widget(NeonButton(
                    text="EDIT", font_size=sp(11),
                    on_release=lambda inst, n=name: self.open_editor(n)))
            actions.add_widget(NeonButton(
                text="UNBIND", bg=DANGER, font_size=sp(11),
                on_release=lambda inst, n=name: self.execute_node_purge(n)))
            row.add_widget(actions)
            self.routing_grid.add_widget(row)

        self.nodes_tracker_label.text = (
            f"// REGISTERED  {len(self.core.registry)}/{MAX_APPS}")
        self._probe_apps()

    def _probe_apps(self):
        """Sites: is the folder there? Apps: is the app really running on its port?"""
        for name, cfg in self.core.registry.items():
            label = self.status_labels.get(name)
            if label is None:
                continue
            if cfg.get("type") == "site":
                up = os.path.isdir(cfg.get("path", ""))
                label.text = "SITE  |  " + ("LIVE" if up else "FOLDER MISSING")
            else:
                up = probe_port(cfg["port"])
                label.text = f"APP :{cfg['port']}  |  " + ("LIVE" if up else "OFFLINE")
            label.color = GOOD if up else WARN

    def _read_stats(self):
        if platform == "android":
            data = None
            try:
                with open(self.status_file, "r") as f:
                    data = json.load(f)
            except Exception:
                pass
            if data and time.time() - data.get("ts", 0) < 5:
                data["online"] = True
                data["starting"] = False
                return data
            data = data or {}
            return {"online": False,
                    "starting": time.time() - self._started_at < 20,
                    "bytes": data.get("bytes", 0), "requests": data.get("requests", 0),
                    "tunnels": 0, "proxy_port": data.get("proxy_port"),
                    "dns_port": data.get("dns_port"),
                    "lan_ip": data.get("lan_ip", self.core.lan_ip),
                    "logs": data.get("logs", [])}
        return {"online": True, "starting": False,
                "bytes": self.core.bytes_transferred,
                "requests": self.core.total_requests,
                "tunnels": self.core.active_tunnels,
                "proxy_port": self.core.proxy_port, "dns_port": self.core.dns_port,
                "lan_ip": self.core.lan_ip, "logs": []}

    def update_telemetry_metrics(self, dt):
        try:
            stats = self._read_stats()
            b = stats["bytes"]
            if b < 1024 * 1024:
                metric = f"{round(b / 1024, 1)} KB"
            else:
                metric = f"{round(b / (1024 * 1024), 2)} MB"
            self.traffic_card.value_label.text = metric
            self.requests_card.value_label.text = str(stats["requests"])
            self.tunnels_card.value_label.text = str(stats["tunnels"])
            self.net_label.text = (
                f"proxy:{stats['proxy_port'] or '-'}  dns:{stats['dns_port'] or '-'}"
                f"  ip:{stats['lan_ip']}")

            self._engine_online = stats["online"]
            if stats["online"]:
                self.status_label.text, self.status_label.color = "[ ONLINE ]", GOOD
            elif stats["starting"]:
                self.status_label.text, self.status_label.color = "[ STARTING ]", WARN
            else:
                self.status_label.text, self.status_label.color = "[ STOPPED ]", DANGER
            if self.power_button is not None:
                self.power_button.text = "STOP" if stats["online"] else "START"

            if platform == "android" and stats["proxy_port"] != self.core.proxy_port:
                self.core.proxy_port = stats["proxy_port"]
                self.refresh_routing_display_tree()

            now = time.time()
            if now - self._last_probe >= 3:
                self._last_probe = now
                self._probe_apps()

            merged = sorted(set(stats["logs"] + self.log_buffer))[-40:]
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

    def on_stop(self):
        if getattr(self, "core", None) is not None:
            self.core.stop()


if __name__ == "__main__":
    EnginePlatform().run()
