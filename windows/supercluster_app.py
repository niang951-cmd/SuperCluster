#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

# Changer de répertoire pour être sûr de trouver web_index.html
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# --- Serveur web pour l'APK (chemin absolu) ---
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
                    self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                    self.send_header('Pragma', 'no-cache')
                    self.send_header('Expires', '0')
                    self.end_headers()
                    self.wfile.write(f.read())
                return
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(f"APK not found at {apk_path}. Please place SuperCluster.apk in D:\\SuperCluster\\apk\\".encode())
                return
        return SimpleHTTPRequestHandler.do_GET(self)

    def log_message(self, format, *args):
        pass

def start_web_server():
    server = HTTPServer(('0.0.0.0', WEB_PORT), ApkHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# --- Application principale ---
class SuperClusterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🚀 SuperCluster AI - Contrôleur")
        self.root.geometry("900x650")
        self.root.configure(bg='#1e1e2e')
        self.nodes = []
        self.connected = False
        self.running = True
        self.lock = threading.Lock()

        title_frame = tk.Frame(root, bg='#2d2d44', height=60)
        title_frame.pack(fill=tk.X, side=tk.TOP)
        tk.Label(title_frame, text="🧠 SuperCluster AI - Cluster Controller",
                font=('Segoe UI', 18, 'bold'), fg='white', bg='#2d2d44').pack(pady=10)

        self.status_var = tk.StringVar(value="🔍 Recherche des nœuds...")
        status_bar = tk.Label(root, textvariable=self.status_var,
                             font=('Segoe UI', 10), bg='#181825', fg='#a6adc8',
                             anchor='w', padx=10, pady=5)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        main_panel = tk.Frame(root, bg='#1e1e2e')
        main_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        chat_frame = tk.Frame(main_panel, bg='#1e1e2e')
        chat_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(chat_frame, text="💬 Chat avec l'IA du cluster",
                font=('Segoe UI', 12), fg='#cdd6f4', bg='#1e1e2e').pack(anchor='w', pady=(0,5))
        self.chat_area = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD,
                                                   font=('Segoe UI', 11),
                                                   bg='#1a1b26', fg='#cdd6f4',
                                                   insertbackground='#cdd6f4',
                                                   height=20, width=50)
        self.chat_area.pack(fill=tk.BOTH, expand=True)
        self.chat_area.config(state=tk.DISABLED)

        input_frame = tk.Frame(chat_frame, bg='#1e1e2e')
        input_frame.pack(fill=tk.X, pady=(10,0))
        self.prompt_entry = tk.Entry(input_frame, font=('Segoe UI', 11),
                                     bg='#313244', fg='#cdd6f4',
                                     insertbackground='#cdd6f4')
        self.prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,10))
        self.prompt_entry.bind('<Return>', self.send_prompt)
        self.send_btn = tk.Button(input_frame, text="🚀 Envoyer",
                                  font=('Segoe UI', 10, 'bold'),
                                  bg='#89b4fa', fg='#1e1e2e',
                                  command=self.send_prompt)
        self.send_btn.pack(side=tk.RIGHT)

        dash_frame = tk.Frame(main_panel, bg='#181825', width=280)
        dash_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10,0))
        dash_frame.pack_propagate(False)
        tk.Label(dash_frame, text="📊 Tableau de bord",
                font=('Segoe UI', 12, 'bold'), fg='#cdd6f4', bg='#181825').pack(pady=(10,5))
        self.node_listbox = tk.Listbox(dash_frame, font=('Segoe UI', 10),
                                       bg='#1a1b26', fg='#cdd6f4',
                                       selectbackground='#45475a',
                                       height=15, width=30)
        self.node_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = tk.Frame(dash_frame, bg='#181825')
        btn_frame.pack(fill=tk.X, pady=5)
        tk.Button(btn_frame, text="🔄 Rafraîchir", font=('Segoe UI', 9),
                  bg='#45475a', fg='#cdd6f4', command=self.discover_nodes).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="⬇️ APK", font=('Segoe UI', 9),
                  bg='#a6e3a1', fg='#1e1e2e', command=self.open_download_page).pack(side=tk.RIGHT, padx=2)

        ip_label = tk.Label(dash_frame, text=f"🌐 Serveur : http://{get_local_ip()}:{WEB_PORT}",
                            font=('Segoe UI', 9), fg='#a6adc8', bg='#181825')
        ip_label.pack(pady=5)
        self.node_count_label = tk.Label(dash_frame, text="Nœuds: 0",
                                         font=('Segoe UI', 10), fg='#cdd6f4', bg='#181825')
        self.node_count_label.pack(pady=5)

        start_web_server()
        self.discover_nodes()
        self.start_auto_discover()

    def get_local_ip(self): return get_local_ip()
    def open_download_page(self): webbrowser.open(f"http://{get_local_ip()}:{WEB_PORT}")

    def discover_nodes(self):
        self.status_var.set("🔍 Recherche des nœuds...")
        threading.Thread(target=self._discover_all, daemon=True).start()

    def _discover_all(self):
        new_nodes = []
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(TIMEOUT)
            # Pas de membership multicast explicite pour envoyer, seulement bind si on veut recevoir
            sock.sendto(DISCOVERY_MSG.encode(), (MULTICAST_IP, DISCOVERY_PORT))

            ips = set()
            start = time.time()
            while time.time() - start < TIMEOUT:
                try:
                    data, addr = sock.recvfrom(1024)
                    msg = data.decode('utf-8', errors='ignore')
                    if msg.startswith("SUPERCLUSTER_ACK"):
                        ips.add(addr[0])
                except socket.timeout: break
            sock.close()

            for ip in ips:
                stats = self._get_node_stats(ip)
                if stats:
                    new_nodes.append((ip, stats.get('load', 999), stats.get('ram', 0)))
        except Exception as e: print(f"Erreur découverte: {e}")
        self.root.after(0, lambda: self._update_nodes(new_nodes))

    def _get_node_stats(self, ip):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2); s.connect((ip, TCP_PORT))
                s.send(json.dumps({"command": "GET_STATS"}).encode())
                resp = s.recv(1024).decode()
                return json.loads(resp)
        except: pass
        return None

    def _update_nodes(self, new_nodes):
        with self.lock:
            self.nodes = sorted(new_nodes, key=lambda x: x[1])
        self.connected = bool(self.nodes)
        self.node_listbox.delete(0, tk.END)
        if self.nodes:
            best = self.nodes[0]
            self.node_count_label.config(text=f"Nœuds: {len(self.nodes)}")
            self.status_var.set(f"✅ {len(self.nodes)} nœuds | Meilleur: {best[0]} (charge {best[1]})")
            for ip, load, ram in self.nodes:
                status = "🟢" if load < 5 else "🟡" if load < 20 else "🔴"
                self.node_listbox.insert(tk.END, f"{status} {ip}  |  charge: {load}  |  RAM: {ram/1e9:.1f} Go")
        else:
            self.node_count_label.config(text="Nœuds: 0")
            self.status_var.set("❌ Aucun nœud trouvé")

    def start_auto_discover(self):
        def refresh():
            while self.running:
                time.sleep(15); self.discover_nodes()
        threading.Thread(target=refresh, daemon=True).start()

    def send_prompt(self, event=None):
        if not self.connected or not self.nodes:
            messagebox.showwarning("Pas de cluster", "Aucun nœud disponible.")
            return
        prompt = self.prompt_entry.get().strip()
        if not prompt: return
        with self.lock:
            target_ip = self.nodes[0][0]
        self.prompt_entry.delete(0, tk.END)
        self.add_chat_message(f"🧑 Vous (vers {target_ip})", prompt, "user")
        self.send_btn.config(state=tk.DISABLED)
        threading.Thread(target=self._send_to_node, args=(target_ip, prompt), daemon=True).start()

    def _send_to_node(self, ip, prompt):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(60)
                s.connect((ip, TCP_PORT))
                s.send(json.dumps({"command": "PROMPT", "data": prompt}).encode())

                # Attendre la réponse (peut être longue)
                chunks = []
                while True:
                    chunk = s.recv(4096)
                    if not chunk: break
                    chunks.append(chunk)

                resp_raw = b"".join(chunks).decode()
                resp_json = json.loads(resp_raw)
                resp = resp_json.get("response", "Erreur de format")

                self.root.after(0, lambda: self.add_chat_message("🤖 IA", resp, "assistant"))
        except Exception as e:
            self.root.after(0, lambda: self.add_chat_message("❌ Erreur", str(e), "error"))
            self.root.after(0, self.discover_nodes)
        finally:
            self.root.after(0, lambda: self.send_btn.config(state=tk.NORMAL))

    def add_chat_message(self, sender, text, msg_type="system"):
        self.chat_area.config(state=tk.NORMAL)
        tag = "user" if msg_type=="user" else "assistant" if msg_type=="assistant" else "system"
        self.chat_area.insert(tk.END, f"{sender} : ", f"{tag}_label")
        self.chat_area.insert(tk.END, f"{text}\n\n", tag)
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)
        self.chat_area.tag_config("user_label", foreground="#89b4fa", font=('Segoe UI', 10, 'bold'))
        self.chat_area.tag_config("assistant_label", foreground="#a6e3a1", font=('Segoe UI', 10, 'bold'))
        self.chat_area.tag_config("system_label", foreground="#f9e2af", font=('Segoe UI', 10, 'bold'))
        self.chat_area.tag_config("user", foreground="#cdd6f4")
        self.chat_area.tag_config("assistant", foreground="#cdd6f4")
        self.chat_area.tag_config("error", foreground="#f38ba8")

    def on_closing(self):
        self.running = False
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SuperClusterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
