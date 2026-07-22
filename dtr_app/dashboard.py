import customtkinter as ctk
import requests
from PIL import Image
import io
import threading
import time
from datetime import datetime


class EmployeeRow(ctk.CTkFrame):
    def __init__(self, master, employee_data):
        super().__init__(master, fg_color="white", border_color="#DEE2E6", border_width=1, corner_radius=6)
        self.pack(fill="x", pady=6, ipady=4)

        self.emp = employee_data
        self.is_on_duty = self.emp.get("status") == "ON-Duty"
        self.grid_columnconfigure(1, weight=1)

        self.avatar_label = ctk.CTkLabel(self, text="👤", font=("Arial", 24), width=50, height=50, fg_color="#E9ECEF",
                                         corner_radius=4)
        self.avatar_label.grid(row=0, column=0, padx=12, pady=10, rowspan=3)
        threading.Thread(target=self.load_avatar, daemon=True).start()

        self.title_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.title_frame.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=(8, 0))

        self.name_label = ctk.CTkLabel(self.title_frame, text=self.emp.get("name"), font=("Arial", 14, "bold"),
                                       text_color="#212529")
        self.name_label.pack(side="left")

        self.timer_label = None
        if self.is_on_duty:
            self.timer_frame = ctk.CTkFrame(self.title_frame, fg_color="#E2F0D9", corner_radius=4)
            self.timer_frame.pack(side="left", padx=8)
            self.timer_label = ctk.CTkLabel(self.timer_frame, text="00:00:00", font=("Courier New", 11, "bold"),
                                            text_color="#385723")
            self.timer_label.pack(padx=6, pady=2)
            self.update_elapsed_time()

        self.job_label = ctk.CTkLabel(self, text=self.emp.get("job_title"), font=("Arial", 11, "bold"),
                                      text_color="#6C757D")
        self.job_label.grid(row=1, column=1, sticky="nw", padx=(0, 10))

        log_text = f" In: {self.emp.get('time_in')}   Out: {self.emp.get('time_out')}"
        self.logs_label = ctk.CTkLabel(self, text=log_text, font=("Arial", 11), text_color="#495057")
        self.logs_label.grid(row=2, column=1, sticky="w", padx=(0, 10), pady=(2, 8))

        badge_bg = "#D1E7DD" if self.is_on_duty else "#F8D7DA"
        badge_text = "#0F5132" if self.is_on_duty else "#842029"
        self.badge = ctk.CTkLabel(self, text=self.emp.get("status").upper(), font=("Arial", 11, "bold"),
                                  fg_color=badge_bg, text_color=badge_text, corner_radius=4, width=85, height=28)
        self.badge.grid(row=0, column=2, rowspan=3, padx=16, sticky="e")

    def load_avatar(self):
        try:
            response = requests.get(self.emp.get("photo"), timeout=5, verify=False)
            if response.status_code == 200:
                img = Image.open(io.BytesIO(response.content)).resize((50, 50), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, size=(50, 50))
                if self.winfo_exists():
                    self.avatar_label.configure(image=ctk_img, text="")
        except:
            pass

    def update_elapsed_time(self):
        if not self.is_on_duty or not self.winfo_exists(): return
        try:
            parts = self.emp.get("time_in").split(" ")
            h, m, s = map(int, parts[-2].split(":"))
            if "PM" in parts[-1].upper() and h < 12: h += 12
            if "AM" in parts[-1].upper() and h == 12: h = 0
            now = datetime.now()
            diff = now - datetime(now.year, now.month, now.day, h, m, s)
            if diff.days >= 0:
                tot = int(diff.total_seconds())
                if self.timer_label and self.timer_label.winfo_exists():
                    self.timer_label.configure(text=f"{tot // 3600:02d}:{(tot % 3600) // 60:02d}:{tot % 60:02d}")
        except:
            pass
        self.after(1000, self.update_elapsed_time)


class DashboardView(ctk.CTkFrame):
    def __init__(self, master, user_data, on_logout):
        super().__init__(master, fg_color="#F8F9FA")
        self.user = user_data
        self.on_logout_callback = on_logout
        self.sync_active = True
        self.menu_open = False

        self.employee_widgets = {}

        # --- TOP FIXED TOOLBAR NAV BAR ---
        self.navbar = ctk.CTkFrame(self, fg_color="#343A40", height=55, corner_radius=0)
        self.navbar.pack(fill="x", side="top")
        self.navbar.pack_propagate(False)

        self.hamburger_btn = ctk.CTkButton(
            self.navbar, text="☰", font=("Arial", 18, "bold"), fg_color="transparent",
            hover_color="#495057", width=45, height=45, command=self.toggle_drawer_menu
        )
        self.hamburger_btn.pack(side="left", padx=5, pady=5)

        self.nav_title = ctk.CTkLabel(self.navbar, text="AUP JLDM Library DTR", font=("Arial", 16, "bold"),
                                      text_color="white")
        self.nav_title.pack(side="left", padx=5)

        # FIXED PERMANENT NAVBAR LOGOUT BUTTON (Madaling makita sa Itaas!)
        self.top_logout_btn = ctk.CTkButton(
            self.navbar, text="Logout", font=("Arial", 12, "bold"),
            fg_color="#dc3545", hover_color="#bb2d3b", width=80, height=32, corner_radius=4,
            command=self.trigger_logout
        )
        self.top_logout_btn.pack(side="right", padx=15, pady=11)

        # --- WORKSPACE ROOT BASE LAYER ---
        self.workspace = ctk.CTkFrame(self, fg_color="transparent")
        self.workspace.pack(fill="both", expand=True)

        # FIXED DRAWER MOUNT: Naka-mount na agad sa simula para iwas TclError packing errors
        self.drawer = ctk.CTkFrame(self.workspace, fg_color="#212529", width=220, corner_radius=0)
        # HINDI muna natin ipa-pack sa viewport window, kontrolado ng conditional toggles natin mamaya.

        # FIX: Pinaghiwalay ang workspace frame para hindi gumamit ng 'before=' operations
        self.content_container = ctk.CTkFrame(self.workspace, fg_color="transparent")
        self.content_container.pack(fill="both", expand=True, side="right")

        self.main_content = ctk.CTkScrollableFrame(self.content_container, fg_color="transparent", corner_radius=0)
        self.main_content.pack(fill="both", expand=True)

        controls_frame = ctk.CTkFrame(self.main_content, fg_color="transparent")
        controls_frame.pack(fill="x", pady=(5, 10))

        welcome_card = ctk.CTkFrame(controls_frame, fg_color="white", border_color="#DEE2E6", border_width=1,
                                    corner_radius=6, height=45)
        welcome_card.pack(fill="x", side="top", pady=(0, 8))
        welcome_card.pack_propagate(False)

        welcome_text = f"Welcome back, {self.user.get('firstname')}! [{self.user.get('job_title')}]"
        welcome_lbl = ctk.CTkLabel(welcome_card, text=welcome_text, font=("Arial", 13, "bold"), text_color="#212529")
        welcome_lbl.pack(side="left", padx=14, pady=8)

        self.search_entry = ctk.CTkEntry(
            controls_frame, placeholder_text="🔍 Search employee name or work assignment title...",
            height=38, corner_radius=6, fg_color="white", border_color="#DEE2E6"
        )
        self.search_entry.pack(fill="x", side="top", pady=2)
        self.search_entry.bind("<KeyRelease>", lambda e: self.apply_filter_search())

        self.rows_container = ctk.CTkFrame(self.main_content, fg_color="transparent")
        self.rows_container.pack(fill="both", expand=True)

        # --- SLIDING DRAWER INTERNAL COMPONENTS ---
        drawer_header = ctk.CTkLabel(self.drawer, text="MAIN MENUS", font=("Arial", 12, "bold"), text_color="#6C757D")
        drawer_header.pack(anchor="w", padx=15, pady=20)

        btn_opts = {"font": ("Arial", 13, "bold"), "fg_color": "transparent", "hover_color": "#343A40", "anchor": "w",
                    "height": 40, "corner_radius": 4}

        self.menu_dash = ctk.CTkButton(self.drawer, text="DTR Control Center", **btn_opts,
                                       command=self.toggle_drawer_menu)
        self.menu_dash.pack(fill="x", padx=10, pady=2)

        self.menu_sync = ctk.CTkButton(self.drawer, text="Force Clear Sync", **btn_opts,
                                       command=lambda: threading.Thread(target=self.fetch_api_data,
                                                                        daemon=True).start())
        self.menu_sync.pack(fill="x", padx=10, pady=2)

        self.api_url = "https://jldmlibrary.aup.edu.ph/webapps/module/dtr/internal/workstatus"
        threading.Thread(target=self.sync_loop_worker, daemon=True).start()

    def toggle_drawer_menu(self):
        if self.menu_open:
            self.drawer.pack_forget()
            self.menu_open = False
        else:
            # FIXED POSITIONING: Palaging naka-pack sa kaliwang bahagi ng base parent side nang ligtas
            self.drawer.pack(fill="y", side="left")
            self.menu_open = True

    def sync_loop_worker(self):
        while self.sync_active:
            self.fetch_api_data()
            time.sleep(10)

    def fetch_api_data(self):
        try:
            res = requests.get(f"{self.api_url}?_cb={int(time.time())}", timeout=8, verify=False)
            if res.status_code == 200:
                emps = res.json().get("data", [])
                if self.sync_active:
                    self.after(0, lambda: self.update_or_create_rows(emps))
        except Exception as e:
            print(f"Sync issue: {e}")

    def update_or_create_rows(self, list_data):
        if not self.sync_active or not self.rows_container.winfo_exists(): return

        current_api_ids = set()

        for emp in list_data:
            emp_name = emp.get("name", "")
            current_api_ids.add(emp_name)

            if emp_name not in self.employee_widgets:
                row_widget = EmployeeRow(self.rows_container, employee_data=emp)
                self.employee_widgets[emp_name] = row_widget
            else:
                widget = self.employee_widgets[emp_name]
                if widget.emp.get("status") != emp.get("status") or widget.emp.get("time_in") != emp.get("time_in"):
                    widget.emp = emp
                    widget.is_on_duty = emp.get("status") == "ON-Duty"

                    log_text = f" In: {emp.get('time_in')}   Out: {emp.get('time_out')}"
                    widget.logs_label.configure(text=log_text)

                    badge_bg = "#D1E7DD" if widget.is_on_duty else "#F8D7DA"
                    badge_text = "#0F5132" if widget.is_on_duty else "#842029"
                    widget.badge.configure(text=emp.get("status").upper(), fg_color=badge_bg, text_color=badge_text)

        for old_id in list(self.employee_widgets.keys()):
            if old_id not in current_api_ids:
                if self.employee_widgets[old_id].winfo_exists():
                    self.employee_widgets[old_id].destroy()
                del self.employee_widgets[old_id]

        self.apply_filter_search()

    def apply_filter_search(self):
        if not self.sync_active: return
        query = self.search_entry.get().strip().lower()

        for emp_name, widget in self.employee_widgets.items():
            if not widget.winfo_exists(): continue

            name = emp_name.lower()
            job = widget.emp.get("job_title", "").lower()

            if query in name or query in job:
                if not widget.winfo_manager():
                    widget.pack(fill="x", pady=6, ipady=4)
            else:
                widget.pack_forget()

    def trigger_logout(self):
        self.sync_active = False
        self.on_logout_callback()