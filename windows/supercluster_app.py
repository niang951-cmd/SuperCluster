import sys
import os
import socket
import json
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox, simpledialog
from http.server import HTTPServer, SimpleHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Constantes ---
MULTICAST_IP = "239.255.255.250"
DISCOVERY_PORT = 9999
TCP_PORT = 8080
WEB_PORT = 5000
DISCOVERY_MSG = "SUPERCLUSTER_DISCOVERY"
MAX_WORKERS = 500 # Support pour scan multi-sous-réseaux

os.chdir(os.path.dirname(os.path.abspath(__file__)))

class ApkHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/': self.path = '/web_index.html'
        elif self.path == '/download':
            apk_path = os.path.join(os.path.dirname(os.getcwd()), 'apk', 'SuperCluster.apk')
            if os.path.exists(apk_path):
                with open(apk_path, 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/vnd.android.package-archive')
                    self.send_header('Content-Disposition', 'attachment; filename="SuperCluster.apk"')
                    self.end_headers(); self.wfile.write(f.read())
                return
        return SimpleHTTPRequestHandler.do_GET(self)
    def log_message(self, *args): pass

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
        return ip
    except: return "127.0.0.1"

class SuperClusterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🚀 SuperCluster AI - MEGA CONTROLLER (Pro Discovery)")
        self.root.geometry("1300x850")
        self.root.configure(bg='#1e1e2e')
        self.nodes = {}
        self.lock = threading.Lock()
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        self.is_scanning = False
        self.setup_ui()
        threading.Thread(target=HTTPServer(('0.0.0.0', WEB_PORT), ApkHandler).serve_forever, daemon=True).start()
        self.discover_nodes()
        self.start_auto_refresh()

    def setup_ui(self):
        header = tk.Frame(self.root, bg='#2d2d44', height=70); header.pack(fill=tk.X)
        tk.Label(header, text="🧠 SuperCluster AI - ULTRA-SCALE", font=('Segoe UI', 16, 'bold'), fg='#89b4fa', bg='#2d2d44').pack(side=tk.LEFT, padx=20)

        btn_manual = tk.Button(header, text="➕ ADD IP", bg='#45475a', fg='white', command=self.add_manual_ip)
        btn_manual.pack(side=tk.RIGHT, padx=20)

        self.status_var = tk.StringVar(value="🔍 Initializing...")
        tk.Label(self.root, textvariable=self.status_var, bg='#181825', fg='#a6adc8', anchor='w', padx=10).pack(fill=tk.X, side=tk.BOTTOM)

        main_panel = tk.Frame(self.root, bg='#1e1e2e'); main_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        left_col = tk.Frame(main_panel, bg='#1e1e2e'); left_col.place(relx=0, rely=0, relwidth=0.55, relheight=1.0)
        self.chat_area = scrolledtext.ScrolledText(left_col, bg='#1a1b26', fg='#cdd6f4', font=('Consolas', 11))
        self.chat_area.pack(fill=tk.BOTH, expand=True)
        self.chat_area.config(state=tk.DISABLED)

        input_frame = tk.Frame(left_col, bg='#1e1e2e', pady=10); input_frame.pack(fill=tk.X)
        self.prompt_entry = tk.Entry(input_frame, bg='#313244', fg='#cdd6f4', font=('Segoe UI', 12))
        self.prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,10)); self.prompt_entry.bind('<Return>', self.send_prompt)
        tk.Button(input_frame, text="🚀 DISTRIBUTE", bg='#89b4fa', command=self.send_prompt, padx=15).pack(side=tk.RIGHT)

        right_col = tk.Frame(main_panel, bg='#181825'); right_col.place(relx=0.57, rely=0, relwidth=0.43, relheight=1.0)
        stats_frame = tk.Frame(right_col, bg='#2d2d44', pady=10); stats_frame.pack(fill=tk.X)
        self.node_count_label = tk.Label(stats_frame, text="NODES: 0", font=('Segoe UI', 12, 'bold'), fg='#a6e3a1', bg='#2d2d44'); self.node_count_label.pack(side=tk.LEFT, padx=15)
        self.total_ram_label = tk.Label(stats_frame, text="RAM: 0 GB", font=('Segoe UI', 12, 'bold'), fg='#f9e2af', bg='#2d2d44'); self.total_ram_label.pack(side=tk.RIGHT, padx=15)

        self.tree = ttk.Treeview(right_col, columns=('ip', 'load', 'ram', 'model'), show='headings')
        self.tree.heading('ip', text='Node IP'); self.tree.heading('load', text='Load'); self.tree.heading('ram', text='RAM'); self.tree.heading('model', text='Model')
        self.tree.column('ip', width=120); self.tree.column('load', width=60); self.tree.column('ram', width=80); self.tree.column('model', width=100)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        ctrl = tk.Frame(right_col, bg='#181825', pady=5); ctrl.pack(fill=tk.X)
        tk.Button(ctrl, text="🔥 DEEP SCAN", bg='#45475a', fg='white', command=self.discover_nodes).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Button(ctrl, text="💾 LOAD MODEL", bg='#f9e2af', command=self.load_model_to_all).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Button(ctrl, text="⬇️ APK", bg='#a6e3a1', command=lambda: webbrowser.open(f"http://{get_local_ip()}:{WEB_PORT}")).pack(side=tk.RIGHT, padx=2)

    def add_manual_ip(self):
        ip = simpledialog.askstring("Add Node", "Enter Node IP address:")
        if ip:
            self.status_var.set(f"Checking {ip}...")
            threading.Thread(target=self._manual_check, args=(ip,), daemon=True).start()

    def _manual_check(self, ip):
        stats = self._get_stats(ip)
        if stats:
            with self.lock: self.nodes[ip] = stats
            self.root.after(0, self._ui_update)
            self.add_msg("System", f"Manual Node {ip} added successfully!", "#a6e3a1")
        else:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Could not connect to {ip} on port {TCP_PORT}"))

    def discover_nodes(self):
        if self.is_scanning: return
        self.is_scanning = True
        self.status_var.set("🚀 Robust multi-subnet scan in progress...")
        threading.Thread(target=self._run_massive_scan, daemon=True).start()

    def _run_massive_scan(self):
        found_ips = set()
        local_ip = get_local_ip()
        parts = local_ip.split('.')

        # Scan current subnet + common subnets (.0, .1, .2, .100)
        subnets = {'.'.join(parts[:-1]) + '.'}
        for s in ['192.168.0.', '192.168.1.', '192.168.2.', '10.0.0.']: subnets.add(s)

        def udp_task(target, br=False):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(2.0)
                if br: s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                s.sendto(DISCOVERY_MSG.encode(), (target, DISCOVERY_PORT))
                start = time.time()
                while time.time() - start < 2.5:
                    try:
                        d, a = s.recvfrom(1024)
                        if d.decode().startswith("SUPERCLUSTER_ACK"): found_ips.add(a[0])
                    except: break
            except: pass

        # 1. UDP discovery
        threads = [threading.Thread(target=udp_task, args=(MULTICAST_IP,)), threading.Thread(target=udp_task, args=('255.255.255.255', True))]
        for t in threads: t.start()
        for t in threads: t.join()

        # 2. Parallel TCP check for all IPs in detected subnets
        def check_node(ip):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.4) # Timeout plus généreux pour le Wi-Fi
                    if s.connect_ex((ip, TCP_PORT)) == 0: found_ips.add(ip)
            except: pass

        all_target_ips = []
        for subnet in subnets:
            for i in range(1, 255): all_target_ips.append(subnet + str(i))

        list(self.executor.map(check_node, all_target_ips))

        # 3. Fetch full stats
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
                s.settimeout(1.5); s.connect((ip, TCP_PORT))
                s.send((json.dumps({"command": "GET_STATS"}) + "\n").encode())
                return json.loads(s.recv(1024).decode())
        except: return None

    def _ui_update(self):
        self.tree.delete(*self.tree.get_children()); total_ram = 0
        for ip, s in sorted(self.nodes.items()):
            ram = s.get('ram', 0); total_ram += ram
            m_status = "RESIDENT" if s.get('model_loaded') else "EMPTY"
            self.tree.insert('', tk.END, values=(ip, f"{s.get('load')}%", f"{ram/1e9:.1f} GB", m_status))
        self.node_count_label.config(text=f"NODES: {len(self.nodes)}")
        self.total_ram_label.config(text=f"RAM: {total_ram/1e9:.1f} GB")
        self.is_scanning = False; self.status_var.set(f"✅ Cluster Ready: {len(self.nodes)} nodes")

    def load_model_to_all(self):
        self.add_msg("System", "Broadcasting LOAD_MODEL (256MB) to all nodes...", "#f9e2af")
        for ip in list(self.nodes.keys()): self.executor.submit(self._send_load_cmd, ip)

    def _send_load_cmd(self, ip):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(10); s.connect((ip, TCP_PORT))
                s.send((json.dumps({"command": "LOAD_MODEL", "size_mb": 256}) + "\n").encode())
                resp = json.loads(s.recv(1024).decode())
                self.root.after(0, lambda: self.add_msg("System", f"Node {ip}: {resp.get('response')}", "#a6e3a1"))
        except Exception as e:
            self.root.after(0, lambda: self.add_msg("Error", f"Node {ip} fail: {str(e)}", "#f38ba8"))

    def send_prompt(self, event=None):
        prompt = self.prompt_entry.get().strip()
        if not prompt or not self.nodes: return
        self.prompt_entry.delete(0, tk.END); self.add_msg("User", prompt, "#89b4fa")
        # Load balancing: least load
        target = min(self.nodes.items(), key=lambda x: x[1].get('load', 100))[0]
        threading.Thread(target=self._exec_on_node, args=(target, prompt), daemon=True).start()

    def _exec_on_node(self, ip, prompt):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(60); s.connect((ip, TCP_PORT))
                s.send((json.dumps({"command": "PROMPT", "data": prompt}) + "\n").encode())
                resp = json.loads(s.recv(4096).decode()).get("response", "No result")
                self.root.after(0, lambda: self.add_msg(f"Node {ip}", resp, "#a6e3a1"))
        except Exception as e:
            self.root.after(0, lambda: self.add_msg("Error", f"Node {ip}: {str(e)}", "#f38ba8"))

    def start_auto_refresh(self):
        def loop():
            while self.running:
                time.sleep(20)
                if not self.is_scanning: self.discover_nodes()
        threading.Thread(target=loop, daemon=True).start()

    def add_msg(self, sender, text, color):
        self.chat_area.config(state=tk.NORMAL); self.chat_area.insert(tk.END, f"{sender}: ", "b")
        self.chat_area.insert(tk.END, f"{text}\n\n")
        self.chat_area.tag_config("b", foreground=color, font=('Consolas', 10, 'bold'))
        self.chat_area.see(tk.END); self.chat_area.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk(); app = SuperClusterApp(root); root.mainloop()
