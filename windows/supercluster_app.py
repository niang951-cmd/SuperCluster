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
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Config ---
MULTICAST_IP = "239.255.255.250"
DISCOVERY_PORT = 9999
TCP_PORT = 8080
WEB_PORT = 5000
DISCOVERY_MSG = "SUPERCLUSTER_DISCOVERY"
MAX_WORKERS = 600 # Higher capacity for ultra-massive clusters
MODEL_SIZE_MB = 64 # Much smaller model to support 100+ tiny devices

os.chdir(os.path.dirname(os.path.abspath(__file__)))

class SuperClusterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🚀 SuperCluster AI - ULTRA-SCALE (Tiny Model Mode)")
        self.root.geometry("1300x850")
        self.root.configure(bg='#1e1e2e')
        self.nodes = {}
        self.lock = threading.Lock()
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        self.setup_ui()

        threading.Thread(target=HTTPServer(('0.0.0.0', WEB_PORT), SimpleHTTPRequestHandler).serve_forever, daemon=True).start()
        self.discover_nodes()
        self.start_auto_refresh()

    def setup_ui(self):
        header = tk.Frame(self.root, bg='#2d2d44', height=70); header.pack(fill=tk.X)
        tk.Label(header, text="🧠 SuperCluster - Massively Distributed (Tiny Model)", font=('Segoe UI', 16, 'bold'), fg='#a6e3a1', bg='#2d2d44').pack(side=tk.LEFT, padx=20)

        self.status_var = tk.StringVar(value="🔍 Initializing...")
        tk.Label(self.root, textvariable=self.status_var, bg='#181825', fg='#a6adc8', anchor='w', padx=10).pack(fill=tk.X, side=tk.BOTTOM)

        main_panel = tk.Frame(self.root, bg='#1e1e2e'); main_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        left_col = tk.Frame(main_panel, bg='#1e1e2e'); left_col.place(relx=0, rely=0, relwidth=0.55, relheight=1.0)
        self.chat_area = scrolledtext.ScrolledText(left_col, bg='#1a1b26', fg='#cdd6f4', font=('Consolas', 11))
        self.chat_area.pack(fill=tk.BOTH, expand=True); self.chat_area.config(state=tk.DISABLED)

        input_frame = tk.Frame(left_col, bg='#1e1e2e', pady=10); input_frame.pack(fill=tk.X)
        self.prompt_entry = tk.Entry(input_frame, bg='#313244', fg='#cdd6f4', font=('Segoe UI', 12))
        self.prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,10)); self.prompt_entry.bind('<Return>', self.send_prompt)
        tk.Button(input_frame, text="🚀 EXECUTE", bg='#89b4fa', command=self.send_prompt, width=15).pack(side=tk.RIGHT)

        right_col = tk.Frame(main_panel, bg='#181825'); right_col.place(relx=0.57, rely=0, relwidth=0.43, relheight=1.0)
        stats_frame = tk.Frame(right_col, bg='#2d2d44', pady=10); stats_frame.pack(fill=tk.X)
        self.node_count_label = tk.Label(stats_frame, text="NODES: 0", font=('Segoe UI', 12, 'bold'), fg='#f9e2af', bg='#2d2d44'); self.node_count_label.pack(side=tk.LEFT, padx=15)
        self.total_ram_label = tk.Label(stats_frame, text="TOTAL RAM: 0 GB", font=('Segoe UI', 12, 'bold'), fg='#89b4fa', bg='#2d2d44'); self.total_ram_label.pack(side=tk.RIGHT, padx=15)

        self.tree = ttk.Treeview(right_col, columns=('ip', 'load', 'ram', 'model'), show='headings')
        self.tree.heading('ip', text='IP'); self.tree.heading('load', text='Load'); self.tree.heading('ram', text='RAM'); self.tree.heading('model', text='State')
        self.tree.column('ip', width=100); self.tree.column('load', width=50); self.tree.column('ram', width=80); self.tree.column('model', width=80)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        ctrl = tk.Frame(right_col, bg='#181825', pady=5); ctrl.pack(fill=tk.X)
        tk.Button(ctrl, text="🔥 DEEP SCAN", bg='#45475a', fg='white', command=self.discover_nodes).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Button(ctrl, text="💾 LOAD TINY-MODEL", bg='#f9e2af', command=self.load_model_to_all).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

    def discover_nodes(self):
        self.status_var.set("🚀 Searching for nodes...")
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self):
        found_ips = set()
        local_ip = get_local_ip()
        subnets = ['.'.join(local_ip.split('.')[:-1]) + '.', '192.168.0.', '192.168.1.', '10.0.0.']

        def check_node(ip):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.15)
                    if s.connect_ex((ip, TCP_PORT)) == 0: found_ips.add(ip)
            except: pass

        all_ips = [s + str(i) for s in subnets for i in range(1, 255)]
        list(self.executor.map(check_node, all_ips))

        active = {}
        futures = {self.executor.submit(self._get_stats, ip): ip for ip in found_ips}
        for f in as_completed(futures):
            res = f.result()
            if res: active[futures[f]] = res

        with self.lock: self.nodes = active
        self.root.after(0, self._ui_update)

    def _get_stats(self, ip):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.2); s.connect((ip, TCP_PORT))
                s.send((json.dumps({"command": "GET_STATS"}) + "\n").encode())
                return json.loads(s.recv(1024).decode())
        except: return None

    def _ui_update(self):
        self.tree.delete(*self.tree.get_children()); total_ram = 0
        for ip, s in sorted(self.nodes.items()):
            ram = s.get('ram', 0); total_ram += ram
            m_status = "LOADED" if s.get('model_loaded') else "EMPTY"
            self.tree.insert('', tk.END, values=(ip, f"{s.get('load')}%", f"{ram/1e9:.1f} GB", m_status))
        self.node_count_label.config(text=f"NODES: {len(self.nodes)}")
        self.total_ram_label.config(text=f"TOTAL RAM: {total_ram/1e9:.2f} GB")
        self.status_var.set(f"✅ Cluster Ready: {len(self.nodes)} nodes")

    def load_model_to_all(self):
        self.add_msg("System", f"Loading {MODEL_SIZE_MB}MB Model to all nodes...", "#f9e2af")
        for ip in list(self.nodes.keys()): self.executor.submit(self._send_load_cmd, ip)

    def _send_load_cmd(self, ip):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5); s.connect((ip, TCP_PORT))
                s.send((json.dumps({"command": "LOAD_MODEL", "size_mb": MODEL_SIZE_MB}) + "\n").encode())
                if json.loads(s.recv(1024).decode()).get('response') == "LOADED_OK":
                    self.root.after(0, lambda: self.add_msg("System", f"Node {ip}: READY", "#a6e3a1"))
        except: pass

    def send_prompt(self, event=None):
        prompt = self.prompt_entry.get().strip()
        if not prompt or not self.nodes: return
        self.prompt_entry.delete(0, tk.END); self.add_msg("User", prompt, "#89b4fa")
        target = min(self.nodes.items(), key=lambda x: x[1].get('load', 100))[0]
        threading.Thread(target=self._exec_on_node, args=(target, prompt), daemon=True).start()

    def _exec_on_node(self, ip, prompt):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(30); s.connect((ip, TCP_PORT))
                s.send((json.dumps({"command": "PROMPT", "data": prompt}) + "\n").encode())
                resp = json.loads(s.recv(2048).decode()).get("response", "Error")
                self.root.after(0, lambda: self.add_msg(f"Node {ip}", resp, "#a6e3a1"))
        except Exception as e: self.root.after(0, lambda: self.add_msg("Error", f"{ip}: {str(e)}", "#f38ba8"))

    def start_auto_refresh(self):
        def loop():
            while self.running:
                time.sleep(20); self.discover_nodes()
        threading.Thread(target=loop, daemon=True).start()

    def add_msg(self, sender, text, color):
        self.chat_area.config(state=tk.NORMAL); self.chat_area.insert(tk.END, f"{sender}: ", "b")
        self.chat_area.insert(tk.END, f"{text}\n\n"); self.chat_area.tag_config("b", foreground=color, font=('Segoe UI', 10, 'bold'))
        self.chat_area.see(tk.END); self.chat_area.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk(); app = SuperClusterApp(root); root.mainloop()
