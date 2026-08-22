import sys
import os
import socket
import json
import threading
import time
import webbrowser
import requests
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
from http.server import HTTPServer, SimpleHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor

# --- Constantes ---
MULTICAST_IP = "239.255.255.250"
DISCOVERY_PORT = 9999
TCP_PORT = 8080
WEB_PORT = 5000
DISCOVERY_MSG = "SUPERCLUSTER_DISCOVERY"
MAX_WORKERS = 100

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
                self.wfile.write(f"APK not found".encode())
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
        self.root.title("🚀 SuperCluster AI - Local Cluster Controller")
        self.root.geometry("1200x850")
        self.root.configure(bg='#1e1e2e')

        self.nodes = {}
        self.lock = threading.Lock()
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        self.is_scanning = False

        # UI State
        self.ai_mode = tk.StringVar(value="NODE") # "PC" or "NODE"

        self.setup_ui()

        # Start servers
        threading.Thread(target=HTTPServer(('0.0.0.0', WEB_PORT), ApkHandler).serve_forever, daemon=True).start()
        self.discover_nodes()
        self.start_auto_refresh()

    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg='#2d2d44', height=60)
        header.pack(fill=tk.X, side=tk.TOP)
        tk.Label(header, text="🧠 SuperCluster AI - Local Distributed AI", font=('Segoe UI', 18, 'bold'), fg='#89b4fa', bg='#2d2d44').pack(side=tk.LEFT, padx=20, pady=10)

        # Mode Toggle in Header
        mode_frame = tk.Frame(header, bg='#2d2d44')
        mode_frame.pack(side=tk.RIGHT, padx=20)
        tk.Label(mode_frame, text="AI Target:", fg='white', bg='#2d2d44', font=('Segoe UI', 9)).pack(side=tk.LEFT)
        tk.Radiobutton(mode_frame, text="Nodes (Local)", variable=self.ai_mode, value="NODE", bg='#2d2d44', fg='white', selectcolor='#1e1e2e').pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(mode_frame, text="PC (Ollama)", variable=self.ai_mode, value="PC", bg='#2d2d44', fg='white', selectcolor='#1e1e2e').pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar(value="🔍 Scan initial...")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bg='#181825', fg='#a6adc8', anchor='w', padx=10, font=('Consolas', 9))
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        main_content = tk.Frame(self.root, bg='#1e1e2e')
        main_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left Column: Chat
        left_col = tk.Frame(main_content, bg='#1e1e2e')
        left_col.place(relx=0, rely=0, relwidth=0.6, relheight=1.0)

        tk.Label(left_col, text="💬 CLUSTER CHAT", font=('Segoe UI', 10, 'bold'), fg='#cdd6f4', bg='#1e1e2e').pack(anchor='w')
        self.chat_area = scrolledtext.ScrolledText(left_col, bg='#1a1b26', fg='#cdd6f4', font=('Segoe UI', 11), borderwidth=0)
        self.chat_area.pack(fill=tk.BOTH, expand=True, pady=5)
        self.chat_area.config(state=tk.DISABLED)

        input_frame = tk.Frame(left_col, bg='#1e1e2e', pady=10)
        input_frame.pack(fill=tk.X)
        self.prompt_entry = tk.Entry(input_frame, bg='#313244', fg='#cdd6f4', font=('Segoe UI', 12), insertbackground='white')
        self.prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,10))
        self.prompt_entry.bind('<Return>', self.send_prompt)
        tk.Button(input_frame, text="🚀 SEND", font=('Segoe UI', 9, 'bold'), bg='#89b4fa', fg='#1e1e2e', command=self.send_prompt, padx=20).pack(side=tk.RIGHT)

        # Right Column: Nodes
        right_col = tk.Frame(main_content, bg='#181825')
        right_col.place(relx=0.62, rely=0, relwidth=0.38, relheight=1.0)

        stats_frame = tk.Frame(right_col, bg='#2d2d44', pady=5)
        stats_frame.pack(fill=tk.X)
        self.node_count_label = tk.Label(stats_frame, text="NODES: 0", font=('Segoe UI', 11, 'bold'), fg='#a6e3a1', bg='#2d2d44')
        self.node_count_label.pack(side=tk.LEFT, padx=10)
        self.total_ram_label = tk.Label(stats_frame, text="RAM: 0 GB", font=('Segoe UI', 11, 'bold'), fg='#f9e2af', bg='#2d2d44')
        self.total_ram_label.pack(side=tk.RIGHT, padx=10)

        tree_frame = tk.Frame(right_col, bg='#181825')
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        tree_scroll = tk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree = ttk.Treeview(tree_frame, columns=('ip', 'load', 'ram'), show='headings', yscrollcommand=tree_scroll.set)
        self.tree.heading('ip', text='IP')
        self.tree.heading('load', text='Load')
        self.tree.heading('ram', text='RAM')
        self.tree.column('ip', width=100)
        self.tree.column('load', width=50, anchor='center')
        self.tree.column('ram', width=80, anchor='center')
        self.tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tree.yview)

        controls = tk.Frame(right_col, bg='#181825', pady=10)
        controls.pack(fill=tk.X)
        self.scan_btn = tk.Button(controls, text="🔥 DEEP SCAN", command=self.discover_nodes, bg='#45475a', fg='white', font=('Segoe UI', 9, 'bold'))
        self.scan_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Button(controls, text="⬇️ APK", command=lambda: webbrowser.open(f"http://{get_local_ip()}:{WEB_PORT}"), bg='#a6e3a1').pack(side=tk.RIGHT, padx=5)

    def discover_nodes(self):
        if self.is_scanning: return
        self.is_scanning = True
        self.scan_btn.config(state=tk.DISABLED, text="SCAN...")
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self):
        found_ips = set()
        local_ip = get_local_ip()
        subnet = '.'.join(local_ip.split('.')[:-1]) + '.'

        def udp_scan(target, broadcast=False):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(1.5)
                if broadcast: sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.sendto(DISCOVERY_MSG.encode(), (target, DISCOVERY_PORT))
                start = time.time()
                while time.time() - start < 2:
                    try:
                        data, addr = sock.recvfrom(1024)
                        if data.decode().startswith("SUPERCLUSTER_ACK"): found_ips.add(addr[0])
                    except: break
            except: pass
            finally: sock.close()

        threads = [threading.Thread(target=udp_scan, args=(MULTICAST_IP,)), threading.Thread(target=udp_scan, args=('255.255.255.255', True))]
        for t in threads: t.start()
        for t in threads: t.join()

        def check_ip(ip):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.3)
                    if s.connect_ex((ip, TCP_PORT)) == 0: found_ips.add(ip)
            except: pass

        futures = [self.executor.submit(check_ip, subnet + str(i)) for i in range(1, 255)]
        for f in futures: f.result()

        active_nodes = {}
        futures = {self.executor.submit(self._fetch_stats, ip): ip for ip in found_ips}
        for future in futures:
            ip = futures[future]
            stats = future.result()
            if stats: active_nodes[ip] = stats

        with self.lock: self.nodes = active_nodes
        self.root.after(0, self._finalize_scan)

    def _fetch_stats(self, ip):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                s.connect((ip, TCP_PORT))
                s.send((json.dumps({"command": "GET_STATS"}) + "\n").encode())
                return json.loads(s.recv(1024).decode())
        except: return None

    def _finalize_scan(self):
        self.tree.delete(*self.tree.get_children())
        total_ram = 0
        for ip, stats in self.nodes.items():
            load, ram = stats.get('load', 0), stats.get('ram', 0)
            total_ram += ram
            self.tree.insert('', tk.END, values=(ip, f"{load}%", f"{ram/1e9:.1f} GB"))
        self.node_count_label.config(text=f"NODES: {len(self.nodes)}")
        self.total_ram_label.config(text=f"RAM: {total_ram/1e9:.1f} GB")
        self.is_scanning = False
        self.scan_btn.config(state=tk.NORMAL, text="🔥 DEEP SCAN")
        self.status_var.set(f"✅ {len(self.nodes)} nœuds connectés")

    def start_auto_refresh(self):
        def loop():
            while self.running:
                time.sleep(12)
                if not self.is_scanning: self.discover_nodes()
        threading.Thread(target=loop, daemon=True).start()

    def send_prompt(self, event=None):
        prompt = self.prompt_entry.get().strip()
        if not prompt: return
        self.prompt_entry.delete(0, tk.END)
        self.add_msg("User", prompt, "#89b4fa")

        if self.ai_mode.get() == "PC":
            threading.Thread(target=self._process_with_pc_ollama, args=(prompt,), daemon=True).start()
        else:
            if not self.nodes:
                self.add_msg("System", "No nodes connected to process local request.", "#f38ba8")
                return
            # Pick node with least load
            target_ip = min(self.nodes.items(), key=lambda x: x[1].get('load', 100))[0]
            threading.Thread(target=self._process_with_node, args=(target_ip, prompt), daemon=True).start()

    def _process_with_pc_ollama(self, prompt):
        try:
            payload = {"model": "llama3", "prompt": prompt, "stream": False}
            resp = requests.post("http://127.0.0.1:11434/api/generate", json=payload, timeout=60)
            if resp.status_code == 200:
                ai_resp = resp.json().get("response", "No response")
                self.root.after(0, lambda: self.add_msg("🤖 PC (Ollama)", ai_resp, "#a6e3a1"))
            else:
                self.root.after(0, lambda: self.add_msg("❌ PC Error", f"Status: {resp.status_code}", "#f38ba8"))
        except:
            self.root.after(0, lambda: self.add_msg("❌ PC Offline", "Local Ollama service not reachable.", "#f38ba8"))

    def _process_with_node(self, ip, prompt):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(30)
                s.connect((ip, TCP_PORT))
                s.send((json.dumps({"command": "PROMPT", "data": prompt}) + "\n").encode())

                # Attendre la réponse JSON du téléphone
                resp_raw = b""
                while True:
                    chunk = s.recv(4096)
                    if not chunk: break
                    resp_raw += chunk

                resp = json.loads(resp_raw.decode()).get("response", "Error")
                self.root.after(0, lambda: self.add_msg(f"📱 Node {ip}", resp, "#f9e2af"))
        except Exception as e:
            self.root.after(0, lambda: self.add_msg(f"❌ Node {ip} Error", str(e), "#f38ba8"))

    def add_msg(self, sender, text, color):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, f"{sender}: ", "bold")
        self.chat_area.insert(tk.END, f"{text}\n\n")
        self.chat_area.tag_config("bold", foreground=color, font=('Consolas', 10, 'bold'))
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = SuperClusterApp(root)
    root.mainloop()
