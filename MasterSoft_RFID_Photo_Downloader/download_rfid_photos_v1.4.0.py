"""
RFID Photo Downloader - GUI Edition
Version: 1.4.0
Description: Graphical Tkinter client featuring multithreaded network loops and dynamic ETA calculators.
"""

import os
import sys
import requests
import time
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# --- SCRIPT VERSIONING ---
__version__ = "1.4.0"

IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
    "image/gif": ".gif", "image/bmp": ".bmp", "image/x-ms-bmp": ".bmp"
}


class DownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"🛡️ RFID Photo Downloader v{__version__}")
        self.root.geometry("650x500")
        self.root.resizable(False, False)

        # Default target configuration
        self.base_url = "http://192.168.7.216:8000/public/rfid-tap/photo"
        self.is_running = False

        self.setup_ui()

    def setup_ui(self):
        # Header Info Banner
        header = tk.Label(self.root, text="RFID Student Photo Bulk Engine", font=("Helvetica", 14, "bold"))
        header.pack(pady=10)

        # Configuration Frame
        config_frame = tk.LabelFrame(self.root, text=" Configuration ", padx=10, pady=10)
        config_frame.pack(fill="x", padx=15, pady=5)

        tk.Label(config_frame, text="Range Start:").grid(row=0, column=0, sticky="w")
        self.start_ent = tk.Entry(config_frame, width=8)
        self.start_ent.insert(0, "1")
        self.start_ent.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        tk.Label(config_frame, text="Range End:").grid(row=0, column=2, sticky="w")
        self.end_ent = tk.Entry(config_frame, width=8)
        self.end_ent.insert(0, "5000")
        self.end_ent.grid(row=0, column=3, padx=5, pady=2, sticky="w")

        # Metrics Status Frame
        self.status_frame = tk.Frame(self.root)
        self.status_frame.pack(fill="x", padx=15, pady=5)

        self.lbl_progress = tk.Label(self.status_frame, text="Progress: 0 / 0", font=("Helvetica", 10))
        self.lbl_progress.pack(side="left")

        self.lbl_eta = tk.Label(self.status_frame, text="ETA: --:--:--", font=("Helvetica", 10, "bold"), fg="blue")
        self.lbl_eta.pack(side="right")

        # Progress Bar
        self.progress = ttk.Progressbar(self.root, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", padx=15, pady=5)

        # Console Log View box
        self.log_box = scrolledtext.ScrolledText(self.root, height=15, font=("Consolas", 9), state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=15, pady=5)

        # Action Button
        self.btn_action = tk.Button(self.root, text="🚀 Start Bulk Download", bg="#4CAF50", fg="white",
                                    font=("Helvetica", 11, "bold"), command=self.toggle_process)
        self.btn_action.pack(pady=10, fill="x", padx=15)

    def log(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert(tk.END, message + "\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")

    def toggle_process(self):
        if self.is_running:
            self.is_running = False
            self.btn_action.config(text="Stopping...", state="disabled")
        else:
            try:
                start = int(self.start_ent.get())
                end = int(self.end_ent.get())
                if start > end: raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Please input valid numeric range values.")
                return

            self.is_running = True
            self.btn_action.config(text="🛑 Stop Download Engine", bg="#f44336")

            # Offload down loop network blocking transactions onto background Threading pools
            threading.Thread(target=self.engine_loop, args=(start, end), daemon=True).start()

    def engine_loop(self, start, end):
        base_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
        today_str = datetime.now().strftime("%Y-%m-%d")
        versioned_dir = os.path.join(base_path, f"downloaded_photos_GUI_v{__version__}_{today_str}")
        os.makedirs(versioned_dir, exist_ok=True)

        total_records = (end - start) + 1
        self.progress["maximum"] = total_records

        self.log(f"=========================================")
        # Note: Dynamic version outputs dynamically rendered using current year targets
        self.log(f"🛡️ Engine Booted. Target Path: {versioned_dir}")
        self.log(f"=========================================\n")

        metrics = {"SUCCESS": 0, "NOT_FOUND": 0, "ERRORS": 0}
        processed = 0

        # Tracking variables for true adaptive time math
        total_time_spent = 0.0

        for i in range(start, end + 1):
            if not self.is_running:
                self.log("\n⚠️ Download process cancelled by user command.")
                break

            dynamic_id = f"2026-AUP{i:04d}"
            self.lbl_progress.config(text=f"Progress: {processed} / {total_records} (Scanning ID: {dynamic_id})")

            step_start = time.time()
            result, f_size = self.network_download(dynamic_id, versioned_dir)
            step_end = time.time()

            # Track processing timing
            step_elapsed = step_end - step_start

            if result == "SUCCESS":
                metrics["SUCCESS"] += 1
                self.log(f"✅ [{processed + 1}/{total_records}] Saved: {dynamic_id} ({f_size} bytes)")
            elif result == "NOT_FOUND":
                metrics["NOT_FOUND"] += 1
            else:
                metrics["ERRORS"] += 1
                self.log(f"⚠️ [{processed + 1}/{total_records}] Connection skipped for ID {dynamic_id} ({result})")

            processed += 1
            self.progress["value"] = processed

            # Base politeness pause buffer
            sleep_interval = 1.5
            if f_size > 200000:
                sleep_interval += 1.5
            time.sleep(sleep_interval)

            # Compile cumulative duration calculations to gauge true system loop speeds
            total_time_spent += (step_elapsed + sleep_interval)
            avg_time_per_unit = total_time_spent / processed
            remaining_units = total_records - processed

            # --- CALCULATING DYNAMIC ETA ---
            eta_seconds = int(remaining_units * avg_time_per_unit)
            hours, remainder = divmod(eta_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.lbl_eta.config(text=f"ETA: {hours:02d}:{minutes:02d}:{seconds:02d}")

        self.log(f"\n=========================================")
        self.log("📊 RUN SUMMARY COMPLETE")
        self.log(f" • Downloads Completed: {metrics['SUCCESS']}")
        self.log(f" • Not Found On Server: {metrics['NOT_FOUND']}")
        self.log(f" • Network Fault drops: {metrics['ERRORS']}")
        self.log(f"=========================================")

        # Reset interface states
        self.is_running = False
        self.btn_action.config(text="🚀 Start Bulk Download", bg="#4CAF50", state="normal")
        self.lbl_progress.config(text=f"Finished: {processed} records evaluated.")
        self.lbl_eta.config(text="ETA: Completed")
        messagebox.showinfo("Done", f"Bulk sequence finished!\n{metrics['SUCCESS']} photos compiled successfully.")

    def network_download(self, photo_id, output_dir):
        url = f"{self.base_url}/{photo_id}"
        max_retries = 3
        retry_delay = 10

        for attempt in range(max_retries + 1):
            try:
                with requests.get(url, stream=True, timeout=6) as response:
                    if response.status_code == 429:
                        if attempt < max_retries:
                            self.log(f"🛑 429 Throttle on {photo_id}. Sleeping {retry_delay}s...")
                            time.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        return "RATE_LIMITED", 0
                    if response.status_code == 404: return "NOT_FOUND", 0
                    if response.status_code != 200: return f"HTTP_{response.status_code}", 0

                    content_type = response.headers.get("Content-Type", "").lower()
                    ext = None
                    for mime, m_ext in IMAGE_EXTENSIONS.items():
                        if mime in content_type:
                            ext = m_ext
                            break
                    if not ext: return "INVALID_MIME", 0

                    file_path = os.path.join(output_dir, f"{photo_id}{ext}")
                    expected = int(response.headers.get("Content-Length", 0))
                    dl_bytes = 0

                    with open(file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                dl_bytes += len(chunk)

                    if expected > 0 and dl_bytes != expected:
                        if os.path.exists(file_path): os.remove(file_path)
                        return "CORRUPTED", 0

                    return "SUCCESS", dl_bytes
            except requests.exceptions.RequestException:
                return "NET_ERROR", 0
        return "FAILED", 0


if __name__ == "__main__":
    window = tk.Tk()
    app = DownloaderGUI(window)
    window.mainloop()