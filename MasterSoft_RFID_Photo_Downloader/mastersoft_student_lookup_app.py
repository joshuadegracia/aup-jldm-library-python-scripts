"""
================================================================================
Application: AUP JLDM Library - Student Lookup
Filename:    mastersoft_student_lookup_app.py
Version:     2.0.3
Author:      Joshua W. de Gracia, Systems Administrator, JLDM Library 2019-2026
Description: An enterprise-grade, modern Bootstrap-style desktop UI built with
             CustomTkinter. Features copyable grid fields, a real-time background
             network-guard backdrop modal, a dynamically mapped 32-bit / 64-bit
             native Windows API ctypes RAM monitor (dependency-free), and campus
             internal-only usage policies.
================================================================================
"""

import sys
import os
import threading
import time
from datetime import datetime
from io import BytesIO
import requests
from PIL import Image
import customtkinter as ctk
import ctypes
from ctypes import wintypes

# --- Styling & Environment Configurations ---
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# --- Native Windows Memory Structures & Dynamic Architecture Bindings ---
if sys.platform == "win32":
    # Dynamically determine size_t depending on the environment pointer width (4 bytes = 32-bit, 8 bytes = 64-bit)
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        SIZE_T = ctypes.c_uint64  # 64-bit unsigned integer
    else:
        SIZE_T = ctypes.c_uint32  # 32-bit unsigned integer


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


    # Explicitly configure arguments and return types dynamically
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

        # Window Frame Initialization
        self.title("AUP JLDM Library - Student Lookup")
        self.geometry("850x710")
        self.resizable(False, False)
        self.configure(fg_color="#F8F9FA")

        # Production Endpoint Configuration (Local Server)
        self.API_BASE_URL = "http://192.168.7.216:8000/public/rfid-tap/lookup/"

        # Modal Overlay & Connection State Trackers
        self.network_backdrop = None
        self.is_connected = True
        self.app_closing = False

        self.setup_ui()

        # Bind application close event to gracefully terminate thread
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Start the continuous real-time connection monitor
        threading.Thread(target=self.start_realtime_network_monitor, daemon=True).start()

        # Start the native real-time RAM usage tracking monitor
        threading.Thread(target=self.start_ram_monitor, daemon=True).start()

    def setup_ui(self):
        """Builds the Bootstrap-card style user interface container."""
        # Main Bordered Card Panel
        self.card = ctk.CTkFrame(self, fg_color="white", corner_radius=16, border_color="#E9ECEF", border_width=1)
        self.card.pack(padx=30, pady=(25, 10), fill="both", expand=True)

        # Header Titles
        self.title_label = ctk.CTkLabel(
            self.card, text="AUP JLDM Library",
            font=ctk.CTkFont(family="Arial", size=28, weight="bold"), text_color="#0D233A"
        )
        self.title_label.pack(anchor="w", padx=30, pady=(30, 2))

        self.subtitle_label = ctk.CTkLabel(
            self.card, text="Student lookup powered by the Records and Admissions Office API.",
            font=ctk.CTkFont(family="Arial", size=13), text_color="#6C757D"
        )
        self.subtitle_label.pack(anchor="w", padx=30, pady=(0, 2))

        # Dynamic Security Notice Tag (AUP Campus Network Only Policy)
        self.security_notice = ctk.CTkLabel(
            self.card, text="🔒 INTERNAL USE ONLY: Accessible exclusively within the AUP Campus Network.",
            font=ctk.CTkFont(family="Arial", size=11, weight="bold"), text_color="#B22222"
        )
        self.security_notice.pack(anchor="w", padx=30, pady=(0, 20))

        # Search Bar Action Row
        self.search_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.search_frame.pack(fill="x", padx=30, pady=10)

        # Action Buttons (Packed Right-to-Left)
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

        # Input Field
        self.search_entry = ctk.CTkEntry(
            self.search_frame, placeholder_text="Enter Student Number (e.g., 2026-AUP0869)",
            height=45, font=ctk.CTkFont(family="Arial", size=14),
            fg_color="white", border_color="#CED4DA", text_color="#212529"
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 15))
        self.search_entry.bind("<Return>", lambda event: self.start_lookup_thread())

        # Feedback Dynamic Status Label
        self.status_label = ctk.CTkLabel(
            self.card, text="", font=ctk.CTkFont(family="Arial", size=13, weight="bold"), text_color="#6C757D"
        )
        self.status_label.pack(anchor="w", padx=30, pady=(5, 15))

        # Structural Divider Line
        self.divider = ctk.CTkFrame(self.card, height=1, fg_color="#DEE2E6")
        self.divider.pack(fill="x", padx=30, pady=5)

        # Core Split Display Panel
        self.content_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=30, pady=20)

        # Left Column: Image Container
        self.image_label = ctk.CTkLabel(self.content_frame, text="", fg_color="#E9ECEF", width=200, height=230,
                                        corner_radius=12)
        self.image_label.pack(side="left", anchor="n", padx=(0, 30))
        self.clear_image_placeholder()

        # Right Column: Clean Grid Information Table
        self.info_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.info_frame.pack(side="left", fill="both", expand=True)

        self.info_frame.columnconfigure(0, weight=1)
        self.info_frame.columnconfigure(1, weight=2)

        self.data_rows = {}
        fields = ["Student Number", "RFID UID", "Last Name", "First Name", "Middle Name", "Program", "College"]

        for idx, field in enumerate(fields):
            lbl = ctk.CTkLabel(self.info_frame, text=field, font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
                               text_color="#6C757D", anchor="w")
            lbl.grid(row=idx * 2, column=0, sticky="w", pady=(8, 2))

            # Selectable borderless entries (Optimized for instant copy/highlight action)
            val = ctk.CTkEntry(
                self.info_frame,
                font=ctk.CTkFont(family="Arial", size=14),
                text_color="#212529",
                fg_color="white",
                border_color="white",
                border_width=0,
                height=25,
                state="readonly"
            )
            val.grid(row=idx * 2, column=1, sticky="ew", pady=(8, 2))

            # Highlight and copy action triggers
            val.bind("<FocusIn>", lambda event, entry=val: self.auto_select_field(entry))
            val.bind("<Button-1>", lambda event, entry=val: self.auto_select_field(entry))

            self.data_rows[field] = val
            self.set_entry_text(val, "-")

            if idx < len(fields) - 1:
                row_div = ctk.CTkFrame(self.info_frame, height=1, fg_color="#F1F3F5")
                row_div.grid(row=idx * 2 + 1, column=0, columnspan=2, sticky="ew", pady=(4, 4))

        # --- Footer Layout Structure ---
        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.pack(side="bottom", fill="x", padx=30, pady=(5, 15))

        # System Administration Label (Left side of footer)
        current_year = datetime.now().year
        footer_text = f"Joshua W. de Gracia, Systems Administrator, JLDM Library 2019-{current_year}"
        self.footer_label = ctk.CTkLabel(
            self.footer_frame, text=footer_text,
            font=ctk.CTkFont(family="Arial", size=11), text_color="#ADB5BD"
        )
        self.footer_label.pack(side="left")

        # Dynamic Memory Usage Diagnostic Pill (Right side of footer)
        self.ram_badge = ctk.CTkLabel(
            self.footer_frame, text="RAM: 0.0 MB",
            font=ctk.CTkFont(family="Arial", size=11, weight="bold"),
            text_color="#495057", fg_color="#E9ECEF", corner_radius=6, height=20, padx=8
        )
        self.ram_badge.pack(side="right")

    def set_entry_text(self, entry_widget, text):
        """Helper to cleanly change text without violating system write properties."""
        entry_widget.configure(state="normal")
        entry_widget.delete(0, "end")
        entry_widget.insert(0, text)
        entry_widget.configure(state="readonly")

    def auto_select_field(self, entry_widget):
        """Forces total selection of the targeted text field block for direct Ctrl+C copy action."""
        entry_widget.select_range(0, "end")
        entry_widget.icursor("end")

    def clear_image_placeholder(self):
        """Safely resets profile image frame back to placeholder layout."""
        self.image_label.configure(text="No Image", image=None)

    def update_status(self, text, color="#6C757D"):
        """Interprets and threads feedback securely to status display banner."""
        self.status_label.configure(text=text, text_color=color)

    # --- Diagnostics Thread: Dynamic Architecture Windows API ctypes RAM Engine ---
    def start_ram_monitor(self):
        """Directly queries Windows API (via ctypes) checking architecture sizes dynamically."""
        while not self.app_closing:
            try:
                if sys.platform == "win32":
                    counters = PROCESS_MEMORY_COUNTERS_EX()
                    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
                    # Query process memory using active process handle
                    if GetProcessMemoryInfo(GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                        # WorkingSetSize is the exact amount of physical memory currently used
                        ram_mb = counters.WorkingSetSize / (1024 * 1024)
                    else:
                        ram_mb = 0.0
                else:
                    # Linux platform fallback parsing
                    with open('/proc/self/status') as f:
                        mem_usage = f.read().split('VmRSS:')[1].split('\n')[0][:-3]
                    ram_mb = int(mem_usage.strip()) / 1024

                if ram_mb > 0.0:
                    self.after(0, lambda m=ram_mb: self.ram_badge.configure(text=f"RAM: {m:.1f} MB"))
                else:
                    self.after(0, lambda: self.ram_badge.configure(text="RAM: N/A"))
            except Exception:
                self.after(0, lambda: self.ram_badge.configure(text="RAM: N/A"))

            time.sleep(2.0)  # Updates diagnostics every 2 seconds

    # --- Real-Time Heartbeat Connection Monitor ---
    def start_realtime_network_monitor(self):
        """Continuous polling thread verifying system connectivity status in real-time."""
        while not self.app_closing:
            try:
                requests.head(self.API_BASE_URL, timeout=2.5)

                # Connection is healthy
                if not self.is_connected:
                    self.is_connected = True
                    self.after(0, self.dismiss_network_modal)
            except Exception:
                # Connection dropped
                if self.is_connected:
                    self.is_connected = False
                    self.after(0, self.show_network_modal)

            time.sleep(3.0)

    def show_network_modal(self):
        """Creates a gorgeous Bootstrap-style modal with a darkened background screen overlay."""
        if self.network_backdrop:
            return

            # Dark Backdrop Overlay Frame (covers the entire screen/app window)
        self.network_backdrop = ctk.CTkFrame(self, fg_color="#1E2022", corner_radius=16)
        self.network_backdrop.place(x=0, y=0, relwidth=1, relheight=1)

        # Trap background clicks (modality guard)
        self.network_backdrop.bind("<Button-1>", lambda event: "break")

        # Main Centered Bootstrap Modal Card Container
        modal_card = ctk.CTkFrame(
            self.network_backdrop,
            width=480,
            height=280,
            fg_color="white",
            corner_radius=12,
            border_color="#DEE2E6",
            border_width=1
        )
        modal_card.place(relx=0.5, rely=0.5, anchor="center")
        modal_card.bind("<Button-1>", lambda event: "break")

        # Bootstrap Modal Header Frame (Sleek Bordered Header)
        modal_header = ctk.CTkFrame(modal_card, height=60, fg_color="#F8F9FA", corner_radius=12)
        modal_header.pack(fill="x", side="top")

        header_title = ctk.CTkLabel(
            modal_header, text="Network Connectivity Alert",
            font=ctk.CTkFont(family="Arial", size=16, weight="bold"),
            text_color="#DC3545"
        )
        header_title.pack(side="left", padx=20, pady=15)

        # Modal Body
        body_container = ctk.CTkFrame(modal_card, fg_color="transparent")
        body_container.pack(fill="both", expand=True, padx=25, pady=20)

        alert_desc = ctk.CTkLabel(
            body_container,
            text="Connection Lost!\n\nThe application cannot communicate with the API server. We are attempting to reconnect automatically.\n\nPlease check your physical network cable or local Wi-Fi interface.",
            font=ctk.CTkFont(family="Arial", size=13),
            text_color="#495057",
            justify="left",
            wraplength=420
        )
        alert_desc.pack(anchor="w", pady=(5, 20))

        # Modal Progress Bar
        self.modal_progress = ctk.CTkProgressBar(body_container, width=430, mode="indeterminate", height=6)
        self.modal_progress.pack(anchor="w", pady=(5, 5))
        self.modal_progress.start()

        # Lock active text field controls
        self.search_entry.configure(state="disabled")
        self.reset_button.configure(state="disabled")

    def dismiss_network_modal(self):
        """Destroys overlay backdrop, unlocks standard controls, and alerts user."""
        if self.network_backdrop:
            self.modal_progress.stop()
            self.network_backdrop.destroy()
            self.network_backdrop = None

        self.search_entry.configure(state="normal")
        self.reset_button.configure(state="normal")
        self.update_status("Connection restored. Application is ready.", "#28A745")

    def start_lookup_thread(self):
        """Initiates data query immediately (the background monitor already verifies connectivity)."""
        student_id = self.search_entry.get().strip()
        if not student_id:
            self.update_status("Please enter a valid student number.", "#DC3545")
            return

        self.update_status("Fetching student data...", "#3B5998")
        self.search_button.configure(state="disabled")

        # Pull data directly
        threading.Thread(target=self.fetch_student_data, args=(student_id,), daemon=True).start()

    def fetch_student_data(self, student_id):
        """Asynchronous worker resolving API requests defensively."""
        url = f"{self.API_BASE_URL}{student_id}"

        try:
            response = requests.get(url, timeout=7)

            if response.status_code == 200:
                response_json = response.json()

                if response_json.get("found") is True:
                    student_data = response_json.get("data", {})
                    self.after(0, self.populate_data, student_data)
                else:
                    self.after(0, self.handle_error, "Student not found.", "#DC3545")
            elif response.status_code == 404:
                self.after(0, self.handle_error, "Student not found.", "#DC3545")
            else:
                self.after(0, self.handle_error, f"Server Error ({response.status_code})", "#DC3545")

        except requests.exceptions.Timeout:
            self.after(0, self.handle_error, "Connection Timeout. Target host took too long to reply.", "#DC3545")
        except requests.exceptions.ConnectionError:
            self.after(0, self.handle_error, "Network Error. Target host unreachable or down.", "#DC3545")
        except Exception:
            self.after(0, self.handle_error, "An unexpected application error occurred.", "#DC3545")

    def populate_data(self, data):
        """Maps data properties down to components while protecting against structure mutations."""
        self.search_button.configure(state="normal")
        self.update_status("Student found.", "#28A745")

        # Basic fields parsing directly out of nested 'data' key block
        self.set_entry_text(self.data_rows["Student Number"], str(data.get("student_number", "-")))
        self.set_entry_text(self.data_rows["RFID UID"], str(data.get("rfid_uid", "-")))
        self.set_entry_text(self.data_rows["Program"], str(data.get("program", "-")))
        self.set_entry_text(self.data_rows["College"], str(data.get("college", "-")))

        # --- Name Parsing Logic ---
        full_name = str(data.get("full_name", "")).strip()
        last_name, first_name, middle_name = "-", "-", "-"

        if full_name:
            name_parts = full_name.split()
            if len(name_parts) == 1:
                first_name = name_parts[0]
            elif len(name_parts) == 2:
                first_name = name_parts[0]
                last_name = name_parts[1]
            elif len(name_parts) >= 3:
                last_name = name_parts[-1]
                middle_name = name_parts[-2]
                first_name = " ".join(name_parts[:-2])

        self.set_entry_text(self.data_rows["Last Name"], last_name.upper())
        self.set_entry_text(self.data_rows["First Name"], first_name.upper())
        self.set_entry_text(self.data_rows["Middle Name"], middle_name.upper())

        # Image parsing from 'photo_url'
        image_url = data.get("photo_url")
        if image_url:
            threading.Thread(target=self.load_profile_image, args=(image_url,), daemon=True).start()
        else:
            self.clear_image_placeholder()

    def load_profile_image(self, url):
        """Isolated download worker pulling profile media data asset."""
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                img_data = BytesIO(res.content)
                pil_img = Image.open(img_data)

                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(200, 230))
                self.after(0, lambda: self.image_label.configure(image=ctk_img, text=""))
            else:
                self.after(0, self.clear_image_placeholder)
        except Exception:
            self.after(0, self.clear_image_placeholder)

    def handle_error(self, message, color):
        """Clean UI state fallback reset engine."""
        self.search_button.configure(state="normal")
        self.update_status(message, color)
        self.clear_image_placeholder()
        for row in self.data_rows.values():
            self.set_entry_text(row, "-")

    def reset_form(self):
        """Wipes the search container input, clears the status bar, and resets layout widgets safely."""
        self.search_entry.configure(state="normal")
        self.search_entry.delete(0, "end")
        self.search_button.configure(state="normal")
        self.reset_button.configure(state="normal")
        self.update_status("", "#6C757D")
        self.clear_image_placeholder()
        for row in self.data_rows.values():
            self.set_entry_text(row, "-")

    def on_close(self):
        """Handles closing the application cleanly without leaving orphan threads."""
        self.app_closing = True
        self.destroy()


if __name__ == "__main__":
    app = StudentLookupApp()
    app.mainloop()