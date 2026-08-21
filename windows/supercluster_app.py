import sys
import os
import socket
import json
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
from http.server import HTTPServer, SimpleHTTPRequestHandler

# --- Constantes ---
MULTICAST_IP = "239.255.255.250"
DISCOVERY_PORT = 9999
TCP_PORT = 8080
WEB_PORT = 5000
DISCOVERY_MSG = "SUPERCLUSTER_DISCOVERY"
TIMEOUT = 3

# Fix working directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class ApkHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = '/web_index.html'
        elif self.path == '/download':
            base_dir = os.path.dirname(os.getcwd())
            apk_path = os.path.join(base_dir, 'apk', 'SuperCluster.apk')
            if os.path.exists(apk_path):
                with open(apk_path, 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/vnd.android.package-archive')
                    self.send_header('Content-Disposition', 'attachment; filename="SuperCluster.apk"')
                    self.end_headers()
                    self.wfile.write(f.read())
                return
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(f"APK not found at {apk_path}".encode())
                return
        return SimpleHTTPRequestHandler.do_GET(self)
    def log_message(self, format, *args): pass

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except: return "127.0.0.1"

class SuperClusterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🚀 SuperCluster AI - Contrôleur")
        self.root.geometry("900x650")
        self.root.configure(bg='#1e1e2e')
        self.nodes = []
        self.lock = threading.Lock()
        self.running = True

        # UI Setup
        title_frame = tk.Frame(root, bg='#2d2d44', height=60)
        title_frame.pack(fill=tk.X)
        tk.Label(title_frame, text="🧠 SuperCluster AI - Controller", font=('Segoe UI', 18, 'bold'), fg='white', bg='#2d2d44').pack(pady=10)

        self.status_var = tk.StringVar(value="🔍 Recherche...")
        tk.Label(root, textvariable=self.status_var, bg='#181825', fg='#a6adc8', anchor='w', padx=10).pack(fill=tk.X, side=tk.BOTTOM)

        main_panel = tk.Frame(root, bg='#1e1e2e')
        main_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Chat
        chat_frame = tk.Frame(main_panel, bg='#1e1e2e')
        chat_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.chat_area = scrolledtext.ScrolledText(chat_frame, bg='#1a1b26', fg='#cdd6f4', font=('Segoe UI', 11))
        self.chat_area.pack(fill=tk.BOTH, expand=True)
        self.chat_area.config(state=tk.DISABLED)

        input_frame = tk.Frame(chat_frame, bg='#1e1e2e')
        input_frame.pack(fill=tk.X, pady=10)
        self.prompt_entry = tk.Entry(input_frame, bg='#313244', fg='#cdd6f4', font=('Segoe UI', 11))
        self.prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,10))
        self.prompt_entry.bind('<Return>', self.send_prompt)
        tk.Button(input_frame, text="🚀 Envoyer", bg='#89b4fa', command=self.send_prompt).pack(side=tk.RIGHT)

        # Dashboard
        dash_frame = tk.Frame(main_panel, bg='#181825', width=280)
        dash_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10,0))
        self.node_listbox = tk.Listbox(dash_frame, bg='#1a1b26', fg='#cdd6f4', font=('Segoe UI', 10))
        self.node_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        tk.Button(dash_frame, text="🔄 Rafraîchir", command=self.discover_nodes).pack(fill=tk.X, padx=5, pady=2)
        tk.Button(dash_frame, text="⬇️ APK", bg='#a6e3a1', command=lambda: webbrowser.open(f"http://{get_local_ip()}:{WEB_PORT}")).pack(fill=tk.X, padx=5, pady=2)

        self.node_count_label = tk.Label(dash_frame, text="Nœuds: 0", fg='#cdd6f4', bg='#181825')
        self.node_count_label.pack(pady=5)

        # Start servers
        threading.Thread(target=HTTPServer(('0.0.0.0', WEB_PORT), ApkHandler).serve_forever, daemon=True).start()
        self.discover_nodes()
        self.start_auto_discover()

    def discover_nodes(self):
        self.status_var.set("🔍 Recherche des nœuds...")
        threading.Thread(target=self._run_discovery, daemon=True).start()

    def _run_discovery(self):
        ips = set()
        # 1. Multicast Discovery
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1)
            sock.sendto(DISCOVERY_MSG.encode(), (MULTICAST_IP, DISCOVERY_PORT))
            while True:
                data, addr = sock.recvfrom(1024)
                if data.decode().startswith("SUPERCLUSTER_ACK"): ips.add(addr[0])
        except: pass

        # 2. Broadcast Discovery (Fallback)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(1)
            sock.sendto(DISCOVERY_MSG.encode(), ('<broadcast>', DISCOVERY_PORT))
            while True:
                data, addr = sock.recvfrom(1024)
                if data.decode().startswith("SUPERCLUSTER_ACK"): ips.add(addr[0])
        except: pass

        new_nodes = []
        for ip in ips:
            stats = self._get_node_stats(ip)
            if stats: new_nodes.append((ip, stats.get('load', 0), stats.get('ram', 0)))

        self.root.after(0, lambda: self._update_ui(new_nodes))

    def _get_node_stats(self, ip):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect((ip, TCP_PORT))
                s.send((json.dumps({"command": "GET_STATS"}) + "\n").encode())
                return json.loads(s.recv(1024).decode())
        except: return None

    def _update_ui(self, new_nodes):
        with self.lock: self.nodes = new_nodes
        self.node_listbox.delete(0, tk.END)
        self.node_count_label.config(text=f"Nœuds: {len(new_nodes)}")
        for ip, load, ram in new_nodes:
            self.node_listbox.insert(tk.END, f"🟢 {ip} | Load: {load}% | RAM: {ram/1e9:.1f}GB")
        self.status_var.set(f"✅ {len(new_nodes)} nœuds trouvés")

    def start_auto_discover(self):
        def loop():
            while self.running: time.sleep(10); self.discover_nodes()
        threading.Thread(target=loop, daemon=True).start()

    def send_prompt(self, event=None):
        prompt = self.prompt_entry.get().strip()
        if not prompt or not self.nodes: return
        target_ip = self.nodes[0][0]
        self.prompt_entry.delete(0, tk.END)
        self.add_msg(f"Vous -> {target_ip}", prompt, "#89b4fa")
        threading.Thread(target=self._send_to_node, args=(target_ip, prompt), daemon=True).start()

    def _send_to_node(self, ip, prompt):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(30)
                s.connect((ip, TCP_PORT))
                s.send((json.dumps({"command": "PROMPT", "data": prompt}) + "\n").encode())
                resp = json.loads(s.recv(4096).decode()).get("response", "No response")
                self.root.after(0, lambda: self.add_msg("🤖 IA", resp, "#a6e3a1"))
        except Exception as e:
            self.root.after(0, lambda: self.add_msg("❌ Erreur", str(e), "#f38ba8"))

    def add_msg(self, sender, text, color):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, f"{sender}: ", "bold")
        self.chat_area.insert(tk.END, f"{text}\n\n")
        self.chat_area.tag_config("bold", foreground=color, font=('Segoe UI', 10, 'bold'))
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = SuperClusterApp(root)
    root.mainloop()
