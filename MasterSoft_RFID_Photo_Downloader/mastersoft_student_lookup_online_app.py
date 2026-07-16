"""
================================================================================
Application: AUP JLDM Library - Student Lookup
Filename:    mastersoft_student_lookup_app.py
Version:     2.3.0 (Enterprise Hardware & Latency Metrics Enabled)
Author:      Joshua W. de Gracia, Systems Administrator, JLDM Library 2019-2026
================================================================================
"""

import sys
import os
import threading
import time
import base64
import json
from datetime import datetime
from io import BytesIO
import requests
from PIL import Image
import customtkinter as ctk
import psutil
import ctypes
from ctypes import wintypes

# --- Styling & Environment Configurations ---
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

if sys.platform == "win32":
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        SIZE_T = ctypes.c_uint64
    else:
        SIZE_T = ctypes.c_uint32

    class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", SIZE_T),
            ("WorkingSetSize", SIZE_T),
            ("QuotaPeakPagedPoolUsage", SIZE_T),
            ("QuotaPagedPoolUsage", SIZE_T),
            ("QuotaPeakNonPagedPoolUsage", SIZE_T),
            ("QuotaNonPagedPoolUsage", SIZE_T),
            ("PagefileUsage", SIZE_T),
            ("PeakPagefileUsage", SIZE_T),
            ("PrivateUsage", SIZE_T),
        ]

    GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
    GetCurrentProcess.argtypes = []
    GetCurrentProcess.restype = wintypes.HANDLE

    GetProcessMemoryInfo = ctypes.windll.psapi.GetProcessMemoryInfo
    GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX),
        wintypes.DWORD
    ]
    GetProcessMemoryInfo.restype = wintypes.BOOL

class StudentLookupApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AUP JLDM Library - RAO RFID Student Lookup")
        self.geometry("850x710")
        self.resizable(False, False)
        self.configure(fg_color="#F8F9FA")

        self.API_BASE_URL = "https://jldmlibrary.aup.edu.ph/webapps/module/rao/mastersoft-rfid-look-up/search"
        self.HEARTBEAT_URL = "https://jldmlibrary.aup.edu.ph"

        self.network_backdrop = None
        self.is_connected = True
        self.app_closing = False

        self.setup_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Background Worker Threads
        threading.Thread(target=self.start_realtime_network_monitor, daemon=True).start()
        threading.Thread(target=self.start_ram_monitor, daemon=True).start()
        threading.Thread(target=self.start_disk_monitor, daemon=True).start()

    def setup_ui(self):
        self.card = ctk.CTkFrame(self, fg_color="white", corner_radius=16, border_color="#E9ECEF", border_width=1)
        self.card.pack(padx=30, pady=(25, 10), fill="both", expand=True)

        self.title_label = ctk.CTkLabel(
            self.card, text="AUP JLDM Library",
            font=ctk.CTkFont(family="Arial", size=28, weight="bold"), text_color="#0D233A"
        )
        self.title_label.pack(anchor="w", padx=30, pady=(30, 2))

        # --- Clean Subtitle Split (Bold only on the API string) ---
        self.subtitle_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.subtitle_frame.pack(anchor="w", padx=30, pady=(0, 2))

        self.subtitle_part1 = ctk.CTkLabel(
            self.subtitle_frame, text="Student lookup powered by the ",
            font=ctk.CTkFont(family="Arial", size=13), text_color="#6C757D"
        )
        self.subtitle_part1.pack(side="left")

        self.subtitle_part2 = ctk.CTkLabel(
            self.subtitle_frame, text="Records and Admissions Office API.",
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"), text_color="#6C757D"
        )
        self.subtitle_part2.pack(side="left")

        self.security_notice = ctk.CTkLabel(
            self.card, text="INTERNAL CAMPUS ONLY: Connection limited to JLDM Secure Domain Interfaces.",
            font=ctk.CTkFont(family="Arial", size=11, weight="bold"), text_color="#B22222"
        )
        self.security_notice.pack(anchor="w", padx=30, pady=(0, 20))

        self.search_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.search_frame.pack(fill="x", padx=30, pady=10)

        self.reset_button = ctk.CTkButton(
            self.search_frame, text="Reset", height=45, width=90,
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            fg_color="#6C757D", hover_color="#5A6268", text_color="white",
            corner_radius=8, command=self.reset_form
        )
        self.reset_button.pack(side="right", padx=(10, 0))

        self.search_button = ctk.CTkButton(
            self.search_frame, text="Find student", height=45, width=120,
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            fg_color="#3B5998", hover_color="#2D4373", text_color="white",
            corner_radius=8, command=self.start_lookup_thread
        )
        self.search_button.pack(side="right")

        self.search_entry = ctk.CTkEntry(
            self.search_frame, placeholder_text="Enter Student Number / RFID (e.g., 1960415503)",
            height=45, font=ctk.CTkFont(family="Arial", size=14),
            fg_color="white", border_color="#CED4DA", text_color="#212529"
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 15))
        self.search_entry.bind("<Return>", lambda event: self.start_lookup_thread())

        self.status_label = ctk.CTkLabel(
            self.card, text="", font=ctk.CTkFont(family="Arial", size=13, weight="bold"), text_color="#6C757D"
        )
        self.status_label.pack(anchor="w", padx=30, pady=(5, 15))

        self.divider = ctk.CTkFrame(self.card, height=1, fg_color="#DEE2E6")
        self.divider.pack(fill="x", padx=30, pady=5)

        self.content_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=30, pady=20)

        self.image_label = ctk.CTkLabel(self.content_frame, text="", fg_color="#E9ECEF", width=200, height=230, corner_radius=12)
        self.image_label.pack(side="left", anchor="n", padx=(0, 30))
        self.clear_image_placeholder()

        self.info_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.info_frame.pack(side="left", fill="both", expand=True)

        self.info_frame.columnconfigure(0, weight=1)
        self.info_frame.columnconfigure(1, weight=2)

        self.data_rows = {}
        fields = ["Student Number", "RFID UID", "Last Name", "First Name", "Middle Name", "Program", "College"]

        for idx, field in enumerate(fields):
            lbl = ctk.CTkLabel(self.info_frame, text=field, font=ctk.CTkFont(family="Arial", size=13, weight="bold"), text_color="#6C757D", anchor="w")
            lbl.grid(row=idx*2, column=0, sticky="w", pady=(8, 2))

            val = ctk.CTkEntry(
                self.info_frame, font=ctk.CTkFont(family="Arial", size=14),
                text_color="#212529", fg_color="white", border_color="white", border_width=0, height=25, state="readonly"
            )
            val.grid(row=idx*2, column=1, sticky="ew", pady=(8, 2))

            val.bind("<FocusIn>", lambda event, entry=val: self.auto_select_field(entry))
            val.bind("<Button-1>", lambda event, entry=val: self.auto_select_field(entry))

            self.data_rows[field] = val
            self.set_entry_text(val, "-")

            if idx < len(fields) - 1:
                row_div = ctk.CTkFrame(self.info_frame, height=1, fg_color="#F1F3F5")
                row_div.grid(row=idx*2+1, column=0, columnspan=2, sticky="ew", pady=(4, 4))

        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.pack(side="bottom", fill="x", padx=30, pady=(5, 15))

        current_year = datetime.now().year
        footer_text = f"Joshua W. de Gracia, Systems Administrator, JLDM Library 2019-{current_year}"
        self.footer_label = ctk.CTkLabel(self.footer_frame, text=footer_text, font=ctk.CTkFont(family="Arial", size=11), text_color="#ADB5BD")
        self.footer_label.pack(side="left")

        # --- Performance & Metric Badges Frame ---
        self.metrics_container = ctk.CTkFrame(self.footer_frame, fg_color="transparent")
        self.metrics_container.pack(side="right")

        self.ram_badge = ctk.CTkLabel(
            self.metrics_container, text="RAM: 0.0 MB", font=ctk.CTkFont(family="Arial", size=11, weight="bold"),
            text_color="#495057", fg_color="#E9ECEF", corner_radius=6, height=20, padx=8
        )
        self.ram_badge.pack(side="left", padx=(0, 6))

        # Core Ping Tracker Badge
        self.pulse_badge = ctk.CTkLabel(
            self.metrics_container, text="Ping: Checking...", font=ctk.CTkFont(family="Arial", size=11, weight="bold"),
            text_color="#FFFFFF", fg_color="#6C757D", corner_radius=6, height=20, padx=8
        )
        self.pulse_badge.pack(side="left", padx=(0, 6))

        # --- Enterprise Style Storage Drive Activity Indicators ---
        self.disk_frame = ctk.CTkFrame(self.metrics_container, fg_color="#E9ECEF", corner_radius=6, height=20, width=90)
        self.disk_frame.pack(side="left")
        self.disk_frame.pack_propagate(False)

        self.disk_lbl = ctk.CTkLabel(self.disk_frame, text="DISK", font=ctk.CTkFont(family="Arial", size=10, weight="bold"), text_color="#495057")
        self.disk_lbl.pack(side="left", padx=(6, 4))

        # Green LED Label for Read Activities
        self.read_led = ctk.CTkLabel(self.disk_frame, text="R", font=ctk.CTkFont(family="Arial", size=9, weight="bold"), text_color="#CED4DA", fg_color="#6C757D", corner_radius=4, width=16, height=14)
        self.read_led.pack(side="left", padx=1)
        self.read_led.pack_propagate(False)

        # Red LED Label for Write Activities
        self.write_led = ctk.CTkLabel(self.disk_frame, text="W", font=ctk.CTkFont(family="Arial", size=9, weight="bold"), text_color="#CED4DA", fg_color="#6C757D", corner_radius=4, width=16, height=14)
        self.write_led.pack(side="left", padx=(1, 6))
        self.write_led.pack_propagate(False)

    def set_entry_text(self, entry_widget, text):
        entry_widget.configure(state="normal")
        entry_widget.delete(0, "end")
        entry_widget.insert(0, text)
        entry_widget.configure(state="readonly")

    def auto_select_field(self, entry_widget):
        entry_widget.select_range(0, "end")
        entry_widget.icursor("end")

    def clear_image_placeholder(self):
        self.image_label.configure(text="No Image", image=None)

    def update_status(self, text, color="#6C757D"):
        self.status_label.configure(text=text, text_color=color)

    def start_ram_monitor(self):
        while not self.app_closing:
            try:
                if sys.platform == "win32":
                    counters = PROCESS_MEMORY_COUNTERS_EX()
                    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
                    if GetProcessMemoryInfo(GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                        ram_mb = counters.WorkingSetSize / (1024 * 1024)
                    else:
                        ram_mb = 0.0
                else:
                    with open('/proc/self/status') as f:
                        mem_usage = f.read().split('VmRSS:')[1].split('\n')[0][:-3]
                    ram_mb = int(mem_usage.strip()) / 1024

                if ram_mb > 0.0:
                    self.after(0, lambda m=ram_mb: self.ram_badge.configure(text=f"RAM: {m:.1f} MB"))
            except Exception:
                pass
            time.sleep(2.0)

    def start_realtime_network_monitor(self):
        while not self.app_closing:
            try:
                start_time = time.perf_counter()
                response = requests.get(self.HEARTBEAT_URL, timeout=3.0)
                end_time = time.perf_counter()

                # Calculate server ping speed in milliseconds
                ping_latency = int((end_time - start_time) * 1000)

                if response.status_code == 200:
                    self.after(0, self.update_pulse_badge, True, f"Ping: {ping_latency}ms")
                    if not self.is_connected:
                        self.is_connected = True
                        self.after(0, self.dismiss_network_modal)
                else:
                    self.after(0, self.update_pulse_badge, False, "Ping: Error")
                    if self.is_connected:
                        self.is_connected = False
                        self.after(0, self.show_network_modal)
            except Exception:
                self.after(0, self.update_pulse_badge, False, "Ping: Offline")
                if self.is_connected:
                    self.is_connected = False
                    self.after(0, self.show_network_modal)
            time.sleep(4.0)

    def update_pulse_badge(self, is_online, text_label):
        """Dynamically updates the connectivity badge color and latency metrics."""
        if is_online:
            self.pulse_badge.configure(text=text_label, fg_color="#28A745", text_color="#FFFFFF")
        else:
            self.pulse_badge.configure(text=text_label, fg_color="#DC3545", text_color="#FFFFFF")

    def start_disk_monitor(self):
        """High-frequency background hardware poller checking for active storage channel reads/writes."""
        try:
            disk_stats = psutil.disk_io_counters()
            last_read = disk_stats.read_bytes if disk_stats else 0
            last_write = disk_stats.write_bytes if disk_stats else 0
        except Exception:
            last_read, last_write = 0, 0

        while not self.app_closing:
            try:
                time.sleep(0.2) # Sample rate of 5 ticks per second for real-time responsiveness
                disk_stats = psutil.disk_io_counters()
                if not disk_stats:
                    continue

                current_read = disk_stats.read_bytes
                current_write = disk_stats.write_bytes

                read_active = current_read > last_read
                write_active = current_write > last_write

                last_read = current_read
                last_write = current_write

                self.after(0, self.update_disk_leds, read_active, write_active)
            except Exception:
                pass

    def update_disk_leds(self, read_active, write_active):
        """Handles visual transition states for the chassis-style drive lights."""
        if read_active:
            self.read_led.configure(fg_color="#28A745", text_color="#FFFFFF") # Active Green
        else:
            self.read_led.configure(fg_color="#6C757D", text_color="#CED4DA") # Inactive Grey

        if write_active:
            self.write_led.configure(fg_color="#DC3545", text_color="#FFFFFF") # Active Red
        else:
            self.write_led.configure(fg_color="#6C757D", text_color="#CED4DA") # Inactive Grey

    def show_network_modal(self):
        if self.network_backdrop:
            return
        self.network_backdrop = ctk.CTkFrame(self, fg_color="#1E2022", corner_radius=16)
        self.network_backdrop.place(x=0, y=0, relwidth=1, relheight=1)

        modal_card = ctk.CTkFrame(self.network_backdrop, width=480, height=280, fg_color="white", corner_radius=12, border_color="#DEE2E6", border_width=1)
        modal_card.place(relx=0.5, rely=0.5, anchor="center")

        modal_header = ctk.CTkFrame(modal_card, height=60, fg_color="#F8F9FA", corner_radius=12)
        modal_header.pack(fill="x", side="top")

        header_title = ctk.CTkLabel(modal_header, text="Network Access Alert", font=ctk.CTkFont(family="Arial", size=16, weight="bold"), text_color="#DC3545")
        header_title.pack(side="left", padx=20)

        body_container = ctk.CTkFrame(modal_card, fg_color="transparent")
        body_container.pack(fill="both", expand=True, padx=25, pady=20)

        alert_desc = ctk.CTkLabel(
            body_container,
            text="Secure Connection Required!\n\nThe application is unable to establish an authenticated handshake with the secure JLDM API server.",
            font=ctk.CTkFont(family="Arial", size=13), text_color="#495057", justify="left", wraplength=420
        )
        alert_desc.pack(anchor="w", pady=(5, 20))

        self.modal_progress = ctk.CTkProgressBar(body_container, width=430, mode="indeterminate", height=6)
        self.modal_progress.pack(anchor="w", pady=(5, 5))
        self.modal_progress.start()

        self.search_entry.configure(state="disabled")
        self.reset_button.configure(state="disabled")

    def dismiss_network_modal(self):
        if self.network_backdrop:
            self.modal_progress.stop()
            self.network_backdrop.destroy()
            self.network_backdrop = None
        self.search_entry.configure(state="normal")
        self.reset_button.configure(state="normal")
        self.update_status("Connection verified. Ready for lookup.", "#28A745")

    def start_lookup_thread(self):
        search_query = self.search_entry.get().strip()
        if not search_query:
            self.update_status("Please enter a valid search ID.", "#DC3545")
            return

        self.update_status("Fetching student data...", "#3B5998")
        self.search_button.configure(state="disabled")

        threading.Thread(target=self.fetch_student_data, args=(search_query,), daemon=True).start()

    def fetch_student_data(self, search_query):
        form_payload = {"rfid": search_query}
        try:
            response = requests.post(self.API_BASE_URL, data=form_payload, timeout=7)
            if response.status_code == 200:
                try:
                    response_json = response.json()
                    if response_json.get("success") is True:
                        student_data = response_json.get("student", {})
                        base64_photo = response_json.get("photo")
                        self.after(0, self.populate_data, student_data, base64_photo)
                        return
                    else:
                        msg = response_json.get("message", "Student not found.")
                        self.after(0, self.handle_error, f"API Error: {msg}", "#DC3545")
                        return
                except json.JSONDecodeError:
                    self.after(0, self.handle_error, "Failed to parse JSON string payload.", "#DC3545")
                    return
            else:
                self.after(0, self.handle_error, f"Server returned error code {response.status_code}", "#DC3545")
                return
        except Exception as e:
            self.after(0, self.handle_error, f"Connection exception: {type(e).__name__}", "#DC3545")

    def populate_data(self, student, base64_photo=None):
        self.search_button.configure(state="normal")
        self.update_status("Student found.", "#28A745")

        self.set_entry_text(self.data_rows["Student Number"], str(student.get("student_number", "-")))
        self.set_entry_text(self.data_rows["RFID UID"], str(student.get("rfid_uid", "-")))
        self.set_entry_text(self.data_rows["Last Name"], str(student.get("last_name", "-")).upper())
        self.set_entry_text(self.data_rows["First Name"], str(student.get("first_name", "-")).upper())
        self.set_entry_text(self.data_rows["Middle Name"], str(student.get("middle_name", "-")).upper())
        self.set_entry_text(self.data_rows["Program"], str(student.get("program", "-")))
        self.set_entry_text(self.data_rows["College"], str(student.get("college", "-")))

        image_url = student.get("photo_url")
        threading.Thread(target=self.load_profile_image, args=(image_url, base64_photo), daemon=True).start()

    def load_profile_image(self, url, base64_photo=None):
        if base64_photo and base64_photo.startswith("data:image"):
            try:
                if "," in base64_photo:
                    base64_data = base64_photo.split(",")[1]
                else:
                    base64_data = base64_photo
                img_bytes = base64.b64decode(base64_data)
                pil_img = Image.open(BytesIO(img_bytes))
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(200, 230))
                self.after(0, lambda: self.image_label.configure(image=ctk_img, text=""))
                return
            except Exception:
                pass

        if url:
            try:
                res = requests.get(url, timeout=5)
                if res.status_code == 200:
                    img_data = BytesIO(res.content)
                    pil_img = Image.open(img_data)
                    ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(200, 230))
                    self.after(0, lambda: self.image_label.configure(image=ctk_img, text=""))
                    return
            except Exception:
                pass

        self.after(0, self.clear_image_placeholder)

    def handle_error(self, message, color):
        self.search_button.configure(state="normal")
        self.update_status(message, color)
        self.clear_image_placeholder()
        for row in self.data_rows.values():
            self.set_entry_text(row, "-")

    def reset_form(self):
        self.search_entry.configure(state="normal")
        self.search_entry.delete(0, "end")
        self.search_button.configure(state="normal")
        self.reset_button.configure(state="normal")
        self.update_status("", "#6C757D")
        self.clear_image_placeholder()
        for row in self.data_rows.values():
            self.set_entry_text(row, "-")

    def on_close(self):
        self.app_closing = True
        self.destroy()

if __name__ == "__main__":
    app = StudentLookupApp()
    app.mainloop()