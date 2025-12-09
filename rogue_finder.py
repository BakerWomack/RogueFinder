import subprocess
import time
import os
import sys
import argparse
import locale

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

def notify(title, message):
    try:
        from win10toast import ToastNotifier
        ToastNotifier().show_toast(title, message, duration=8, threaded=True)
    except Exception:
        print(title, message)

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

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--interval", "-i", type=int, default=10)
    p.add_argument("--once", action="store_true")
    p.add_argument("--setup", action="store_true")
    args = p.parse_args()
    base = os.path.abspath(os.path.dirname(__file__))
    state_path = os.path.join(base, ".last_bssid")
    baseline_ssid, baseline_bssids = load_state(state_path)
    
    ssid, bssid = get_wifi_info()
    if bssid:
        bssid = normalize_bssid(bssid)
    
    if args.setup:
        if ssid:
            baseline_ssid = ssid
            all_aps = scan_all_aps()
            if baseline_ssid in all_aps:
                baseline_bssids = {normalize_bssid(b) for b in all_aps[baseline_ssid] if normalize_bssid(b)}
            else:
                baseline_bssids = {bssid} if bssid else set()
            save_state(state_path, baseline_ssid, baseline_bssids)
        else:
            all_aps = scan_all_aps()
            if all_aps:
                baseline_ssid = list(all_aps.keys())[0]
                baseline_bssids = {normalize_bssid(b) for b in all_aps[baseline_ssid] if normalize_bssid(b)}
                save_state(state_path, baseline_ssid, baseline_bssids)
        sys.exit(0)
    
    if args.once:
        rogue_detected = False
        if ssid and baseline_ssid and ssid == baseline_ssid and bssid:
            if bssid not in baseline_bssids:
                notify("Rogue AP detected", f"SSID {ssid} has unknown BSSID {bssid}")
                rogue_detected = True
        
        all_aps = scan_all_aps()
        if baseline_ssid in all_aps:
            for ap_bssid in all_aps[baseline_ssid]:
                normalized_ap_bssid = normalize_bssid(ap_bssid)
                if normalized_ap_bssid and normalized_ap_bssid not in baseline_bssids:
                    notify("Rogue AP detected", f"Found unknown AP: SSID {baseline_ssid} with BSSID {normalized_ap_bssid}")
                    rogue_detected = True
        for found_ssid in all_aps:
            if found_ssid != baseline_ssid:
                similarity = ssid_similarity(baseline_ssid, found_ssid)
                if similarity >= 0.7:
                    notify("Similar SSID detected", f"Found similar SSID: '{found_ssid}' (similar to '{baseline_ssid}')")
                    rogue_detected = True
        
        sys.exit(0)
    
    try:
        while True:
            ssid, bssid = get_wifi_info()
            if bssid:
                bssid = normalize_bssid(bssid)
            
            if ssid and baseline_ssid and ssid == baseline_ssid:
                if bssid and bssid not in baseline_bssids:
                    notify("Rogue AP detected", f"SSID {ssid} changed BSSID to {bssid}")
                    if args.setup:
                        baseline_bssids.add(bssid)
                        save_state(state_path, baseline_ssid, baseline_bssids)
                elif bssid and bssid in baseline_bssids:
                    pass
            elif ssid and baseline_ssid is None:
                if args.setup:
                    baseline_ssid = ssid
                    baseline_bssids = {bssid} if bssid else set()
                    save_state(state_path, baseline_ssid, baseline_bssids)
            
            if baseline_ssid:
                all_aps = scan_all_aps()
                if baseline_ssid in all_aps:
                    for ap_bssid in all_aps[baseline_ssid]:
                        normalized_ap_bssid = normalize_bssid(ap_bssid)
                        if normalized_ap_bssid and normalized_ap_bssid not in baseline_bssids:
                            notify("Rogue AP detected", f"Found unknown AP: SSID {baseline_ssid} with BSSID {normalized_ap_bssid}")
                            if args.setup:
                                baseline_bssids.add(normalized_ap_bssid)
                                save_state(state_path, baseline_ssid, baseline_bssids)
                for found_ssid in all_aps:
                    if found_ssid != baseline_ssid:
                        similarity = ssid_similarity(baseline_ssid, found_ssid)
                        if similarity >= 0.7:
                            notify("Similar SSID detected", f"Found similar SSID: '{found_ssid}' (similar to '{baseline_ssid}')")
            
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
