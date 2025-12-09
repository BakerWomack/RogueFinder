import subprocess
import time
import os
import sys
import locale
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
import pystray
from PIL import Image, ImageDraw
from win10toast import ToastNotifier

def get_wifi_info():
    try:
        encoding = locale.getpreferredencoding() or 'utf-8'
        out = subprocess.check_output(["netsh","wlan","show","interfaces"], encoding=encoding, errors="ignore")
    except Exception:
        return None, None
    ssid = None
    bssid = None
    for line in out.splitlines():
        if ":" not in line:
            continue
        key, val = [s.strip() for s in line.split(":", 1)]
        kl = key.lower()
        if kl.startswith("ssid") and ssid is None:
            ssid = val
        elif kl.startswith("bssid"):
            bssid = val
    return ssid, bssid

def normalize_bssid(bssid):
    if not bssid:
        return None
    bssid_str = bssid.split(",")[0].strip()
    bssid_str = bssid_str.replace(" ", "").replace("-", ":").upper()
    return bssid_str if bssid_str else None

def ssid_similarity(ssid1, ssid2):
    if not ssid1 or not ssid2:
        return 0.0
    s1 = ssid1.strip().lower()
    s2 = ssid2.strip().lower()
    if s1 == s2:
        return 1.0
    if s1 in s2 or s2 in s1:
        return 0.9
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0
    max_len = max(len1, len2)
    matches = sum(c1 == c2 for c1, c2 in zip(s1, s2))
    base_similarity = matches / max_len
    if abs(len1 - len2) <= 2:
        base_similarity += 0.1
    return min(base_similarity, 1.0)

def scan_all_aps():
    try:
        encoding = locale.getpreferredencoding() or 'utf-8'
        try:
            subprocess.run(["powershell", "-Command", "(netsh wlan show networks mode=bssid | Out-String)"], 
                          encoding=encoding, errors="ignore", capture_output=True, timeout=10)
        except:
            pass
        time.sleep(1)
        try:
            subprocess.run(["netsh","wlan","show","networks"], encoding=encoding, errors="ignore", capture_output=True, timeout=3)
        except:
            pass
        time.sleep(0.5)
        out = subprocess.check_output(["netsh","wlan","show","networks","mode=bssid"], encoding=encoding, errors="ignore")
    except Exception:
        return {}
    
    ap_dict = {}
    current_ssid = None
    
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        
        if line.upper().startswith("SSID"):
            if ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    ssid_name = parts[1].strip()
                    if ssid_name and ssid_name.upper() != "NONE":
                        current_ssid = ssid_name
                        if current_ssid not in ap_dict:
                            ap_dict[current_ssid] = []
        
        elif ":" in line:
            key, val = [s.strip() for s in line.split(":", 1)]
            kl = key.lower()
            if kl.startswith("bssid") and val and current_ssid:
                bssid_str = val.split(",")[0].strip()
                bssid = normalize_bssid(bssid_str)
                if bssid and bssid not in ap_dict[current_ssid]:
                    ap_dict[current_ssid].append(bssid)
    
    return ap_dict

def load_state(path):
    if not os.path.exists(path):
        return None, set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [l.rstrip("\n") for l in f.readlines()]
        if not lines:
            return None, set()
        ssid = lines[0] if len(lines) > 0 and lines[0] else None
        bssids = set()
        for line in lines[1:]:
            if line.strip():
                bssid_str = line.strip().split(",")[0].strip()
                bssid = normalize_bssid(bssid_str)
                if bssid:
                    bssids.add(bssid)
        return ssid or None, bssids
    except Exception:
        return None, set()

def save_state(path, ssid, bssids):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write((ssid or "") + "\n")
            for bssid in sorted(bssids):
                if bssid:
                    f.write(bssid + "\n")
    except Exception:
        pass

class RogueFinderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("RogueFinder - WiFi Security Monitor")
        self.root.geometry("500x400")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        self.base = os.path.abspath(os.path.dirname(__file__))
        self.state_path = os.path.join(self.base, ".last_bssid")
        self.baseline_ssid, self.baseline_bssids = load_state(self.state_path)
        
        self.monitoring = False
        self.monitor_thread = None
        self.interval = 10
        self.toast = ToastNotifier()
        
        self.setup_ui()
        self.setup_tray()
        
        if not self.baseline_ssid or not self.baseline_bssids:
            self.log_message("⚠️ No baseline configured. Run 'python rogue_finder.py --setup' first.")
        else:
            self.log_message(f"✅ Monitoring SSID: {self.baseline_ssid}")
            self.log_message(f"✅ Known BSSIDs: {len(self.baseline_bssids)}")
            self.start_monitoring()
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        status_frame.columnconfigure(1, weight=1)
        
        ttk.Label(status_frame, text="SSID:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.ssid_label = ttk.Label(status_frame, text=self.baseline_ssid or "Not configured")
        self.ssid_label.grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(status_frame, text="Known BSSIDs:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        self.bssid_count_label = ttk.Label(status_frame, text=str(len(self.baseline_bssids)))
        self.bssid_count_label.grid(row=1, column=1, sticky=tk.W)
        
        ttk.Label(status_frame, text="Status:").grid(row=2, column=0, sticky=tk.W, padx=(0, 5))
        self.status_label = ttk.Label(status_frame, text="Stopped", foreground="red")
        self.status_label.grid(row=2, column=1, sticky=tk.W)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.start_button = ttk.Button(button_frame, text="Start Monitoring", command=self.start_monitoring)
        self.start_button.grid(row=0, column=0, padx=(0, 5))
        
        self.stop_button = ttk.Button(button_frame, text="Stop Monitoring", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=(0, 5))
        
        ttk.Button(button_frame, text="Setup Baseline", command=self.setup_baseline).grid(row=0, column=2)
        
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="10")
        log_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.log_text.config(state=tk.DISABLED)
    
    def log_message(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def setup_baseline(self):
        ssid, bssid = get_wifi_info()
        if bssid:
            bssid = normalize_bssid(bssid)
        
        if ssid:
            self.baseline_ssid = ssid
            all_aps = scan_all_aps()
            if self.baseline_ssid in all_aps:
                self.baseline_bssids = {normalize_bssid(b) for b in all_aps[self.baseline_ssid] if normalize_bssid(b)}
            else:
                self.baseline_bssids = {bssid} if bssid else set()
            save_state(self.state_path, self.baseline_ssid, self.baseline_bssids)
            self.log_message(f"✅ Baseline configured for SSID: {self.baseline_ssid}")
            self.log_message(f"✅ Known BSSIDs: {len(self.baseline_bssids)}")
            self.update_status()
        else:
            self.log_message("❌ Not connected to WiFi. Please connect first.")
    
    def update_status(self):
        self.ssid_label.config(text=self.baseline_ssid or "Not configured")
        self.bssid_count_label.config(text=str(len(self.baseline_bssids)))
    
    def start_monitoring(self):
        if not self.baseline_ssid or not self.baseline_bssids:
            self.log_message("❌ No baseline configured. Please setup baseline first.")
            return
        
        if self.monitoring:
            return
        
        self.monitoring = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_label.config(text="Monitoring...", foreground="green")
        self.log_message("🟢 Monitoring started")
        
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        self.monitoring = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="Stopped", foreground="red")
        self.log_message("🔴 Monitoring stopped")
    
    def monitor_loop(self):
        while self.monitoring:
            try:
                ssid, bssid = get_wifi_info()
                if bssid:
                    bssid = normalize_bssid(bssid)
                
                if ssid and self.baseline_ssid and ssid == self.baseline_ssid:
                    if bssid and bssid not in self.baseline_bssids:
                        message = f"SSID {ssid} changed BSSID to {bssid}"
                        self.log_message(f"⚠️ ROGUE AP: {message}")
                        self.toast.show_toast("Rogue AP Detected", message, duration=10, threaded=True)
                
                if self.baseline_ssid:
                    all_aps = scan_all_aps()
                    if self.baseline_ssid in all_aps:
                        for ap_bssid in all_aps[self.baseline_ssid]:
                            normalized_ap_bssid = normalize_bssid(ap_bssid)
                            if normalized_ap_bssid and normalized_ap_bssid not in self.baseline_bssids:
                                message = f"Found unknown AP: SSID {self.baseline_ssid} with BSSID {normalized_ap_bssid}"
                                self.log_message(f"⚠️ ROGUE AP: {message}")
                                self.toast.show_toast("Rogue AP Detected", message, duration=10, threaded=True)
                    for found_ssid in all_aps:
                        if found_ssid != self.baseline_ssid:
                            similarity = ssid_similarity(self.baseline_ssid, found_ssid)
                            if similarity >= 0.7:
                                message = f"Found similar SSID: '{found_ssid}' (similar to '{self.baseline_ssid}')"
                                self.log_message(f"⚠️ SIMILAR SSID: {message}")
                                self.toast.show_toast("Similar SSID Detected", message, duration=10, threaded=True)
                
                time.sleep(self.interval)
            except Exception as e:
                self.log_message(f"❌ Error: {str(e)}")
                time.sleep(self.interval)
    
    def create_tray_icon(self):
        image = Image.new('RGB', (64, 64), color='red')
        draw = ImageDraw.Draw(image)
        draw.ellipse([16, 16, 48, 48], fill='red', outline='white', width=2)
        return image
    
    def setup_tray(self):
        icon = self.create_tray_icon()
        menu = pystray.Menu(
            pystray.MenuItem("Show", self.show_window),
            pystray.MenuItem("Exit", self.quit_app)
        )
        self.tray = pystray.Icon("RogueFinder", icon, "RogueFinder - WiFi Security Monitor", menu)
        self.tray_thread = threading.Thread(target=self.tray.run, daemon=True)
        self.tray_thread.start()
    
    def hide_window(self):
        self.root.withdraw()
    
    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
    
    def quit_app(self):
        self.monitoring = False
        self.tray.stop()
        self.root.quit()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = RogueFinderGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()

