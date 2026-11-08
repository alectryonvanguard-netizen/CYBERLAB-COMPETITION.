import os
import json
import socket
import threading
import time
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock

ACCESS_PASSWORD = "MySecurePassword123"  # Set your private gatekeeper password here
PROXY_PORT = 8080
MAX_APPS = 15

class EnginePlatform(App):
    def build(self):
        self.title = ".engine"
        if 'ANDROID_ARGUMENT' in os.environ:
            from android.storage import app_storage_path
            self.registry_file = os.path.join(app_storage_path(), "engine_registry.json")
            try:
                from android import python_act
                python_act.start_service(title=".engine Proxy Engine", text="Listening on port 8080")
            except: pass
        else:
            self.registry_file = "engine_registry.json"

        self.registry = self.load_registry()
        self.is_server_running = False
        self.total_requests = 0
        self.bytes_transferred = 0
        self.log_messages = []

        self.window = BoxLayout(orientation='vertical', padding=15, spacing=10)
        self.show_login_screen()
        return self.window

    def load_registry(self):
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, "r") as f: return json.load(f)
            except: return {}
        return {}

    def save_registry(self):
        try:
            with open(self.registry_file, "w") as f: json.dump(self.registry, f, indent=4)
        except: pass

    def show_login_screen(self):
        self.window.clear_widgets()
        self.window.add_widget(Label(text=".engine SYSTEM CORE", font_size='24sp', bold=True, color=(0, 1, 0, 1), size_hint_y=0.2))
        self.window.add_widget(Label(text="Enter Gatekeeper Password:", size_hint_y=0.1))
        
        self.password_input = TextInput(password=True, multiline=False, halign='center', size_hint_y=0.1, background_color=(0.15, 0.15, 0.15, 1), foreground_color=(1, 1, 1, 1))
        self.window.add_widget(self.password_input)
        
        auth_btn = Button(text="INITIALIZE HARDWARE TUNNEL", background_color=(0, 0.7, 0, 1), size_hint_y=0.12, bold=True)
        auth_btn.bind(on_press=self.verify_password)
        self.window.add_widget(auth_btn)
        self.window.add_widget(BoxLayout(size_hint_y=0.48))

    def verify_password(self, instance):
        if self.password_input.text == ACCESS_PASSWORD:
            self.show_dashboard_screen()
            self.start_proxy_engine()
            Clock.schedule_interval(self.refresh_live_metrics, 1.0)
        else:
            self.password_input.text = ""
            self.password_input.hint_text = "INVALID SECURITY CREDENTIALS"

    def show_dashboard_screen(self):
        self.window.clear_widgets()
        
        metrics_bar = GridLayout(cols=3, size_hint_y=0.15, spacing=5)
        self.req_label = Label(text="Requests: 0")
        self.bandwidth_label = Label(text="Traffic: 0 KB")
        self.status_label = Label(text="Core Status: 24/7 ONLINE", color=(0, 1, 0, 1))
        metrics_bar.add_widget(self.req_label)
        metrics_bar.add_widget(self.bandwidth_label)
        metrics_bar.add_widget(self.status_label)
        self.window.add_widget(metrics_bar)

        form_frame = BoxLayout(orientation='horizontal', size_hint_y=0.12, spacing=5)
        self.subdomain_input = TextInput(hint_text="Subdomain Name", multiline=False, background_color=(0.2, 0.2, 0.2, 1), foreground_color=(1, 1, 1, 1))
        self.port_input = TextInput(hint_text="Target Port", multiline=False, background_color=(0.2, 0.2, 0.2, 1), foreground_color=(1, 1, 1, 1))
        reg_btn = Button(text="BIND APP", background_color=(0, 0.5, 1, 1), bold=True, size_hint_x=0.4)
        reg_btn.bind(on_press=self.register_app_domain)
        form_frame.add_widget(self.subdomain_input)
        form_frame.add_widget(self.port_input)
        form_frame.add_widget(reg_btn)
        self.window.add_widget(form_frame)

        self.apps_counter = Label(text=f"Active Network Nodes: {len(self.registry)} / {MAX_APPS}", size_hint_y=0.05, color=(1, 1, 0, 1), bold=True)
        self.window.add_widget(self.apps_counter)

        self.scroll_layout = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.scroll_layout.bind(minimum_height=self.scroll_layout.setter('height'))
        scroll_view = ScrollView(size_hint=(1, 0.38))
        scroll_view.add_widget(self.scroll_layout)
        self.window.add_widget(scroll_view)

        self.window.add_widget(Label(text="Live Console Logs:", size_hint_y=0.05, halign='left'))
        self.log_layout = GridLayout(cols=1, spacing=2, size_hint_y=None)
        self.log_layout.bind(minimum_height=self.log_layout.setter('height'))
        log_scroll = ScrollView(size_hint=(1, 0.25))
        log_scroll.add_widget(self.log_layout)
        self.window.add_widget(log_scroll)

        self.update_routing_display()

    def register_app_domain(self, instance):
        name = self.subdomain_input.text.strip().lower().replace(".engine", "")
        port = self.port_input.text.strip()
        
        if len(self.registry) >= MAX_APPS:
            self.log_action("ERROR: Registry limit reached.")
            return
        if name and port.isdigit():
            self.registry[name] = int(port)
            self.save_registry()
            self.subdomain_input.text = ""
            self.port_input.text = ""
            self.update_routing_display()
            self.log_action(f"NODE CONNECTED: {name}.engine -> Port {port}")

    def remove_app_domain(self, name):
        if name in self.registry:
            del self.registry[name]
            self.save_registry()
            self.update_routing_display()
            self.log_action(f"NODE DISCONNECTED: {name}.engine")

    def update_routing_display(self):
        self.scroll_layout.clear_widgets()
        for name, port in self.registry.items():
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height=45, spacing=10)
            row.add_widget(Label(text=f"{name}.engine  ->  127.0.0.1:{port}", halign='left'))
            del_btn = Button(text="DROP", background_color=(1, 0.2, 0.2, 1), size_hint_x=0.25)
            del_btn.bind(on_press=lambda inst, n=name: self.remove_app_domain(n))
            row.add_widget(del_btn)
            self.scroll_layout.add_widget(row)
        self.apps_counter.text = f"Active Network Nodes: {len(self.registry)} / {MAX_APPS}"

    def log_action(self, message):
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_messages.append(formatted_message)
        if len(self.log_messages) > 30: self.log_messages.pop(0)
        try:
            self.log_layout.clear_widgets()
            for msg in reversed(self.log_messages):
                self.log_layout.add_widget(Label(text=msg, font_size='11sp', size_hint_y=None, height=22, color=(0.7, 0.7, 0.7, 1)))
        except: pass

    def refresh_live_metrics(self, dt):
        try:
            self.req_label.text = f"Requests: {self.total_requests}"
            self.bandwidth_label.text = f"Traffic: {round(self.bytes_transferred / 1024, 1)} KB"
        except: pass

    def start_proxy_engine(self):
        if not self.is_server_running:
            self.is_server_running = True
            threading.Thread(target=self.run_network_socket, daemon=True).start()
            self.log_action(f"Engine Core active on proxy pipeline port {PROXY_PORT}")

    def run_network_socket(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("0.0.0.0", PROXY_PORT))
            server.listen(100)
        except Exception as e:
            self.log_action(f"CRITICAL SOCKET ERROR: {e}")
            return

        while self.is_server_running:
            try:
                client_sock, _ = server.accept()
                threading.Thread(target=self.proxy_traffic, args=(client_sock,), daemon=True).start()
            except: break

    def proxy_traffic(self, client_socket):
        self.total_requests += 1
        try:
            request_data = client_socket.recv(4096)
            if not request_data:
                client_socket.close()
                return
            
            self.bytes_transferred += len(request_data)
            app_target = None
            lines = request_data.split(b"\r\n")
            for line in lines:
                if line.startswith(b"Host:"):
                    host_string = line.split(b" ").decode('utf-8').strip()
                    if ":" in host_string:
                        host_string = host_string.split(":")[0]
                    if host_string.endswith(".engine"):
                        app_target = host_string.replace(".engine", "")
                    break

            if app_target and app_target in self.registry:
                port = self.registry[app_target]
                app_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                app_socket.connect(("127.0.0.1", port))
                app_socket.sendall(request_data)
                
                while True:
                    chunk = app_socket.recv(4096)
                    if len(chunk) > 0:
                        client_socket.sendall(chunk)
                        self.bytes_transferred += len(chunk)
                    else: break
                app_socket.close()
                self.log_action(f"200 OK: Routed {app_target}.engine")
            else:
                client_socket.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\n\r\n.engine Error: App Node offline.")
