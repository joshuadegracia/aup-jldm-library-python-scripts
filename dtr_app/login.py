import customtkinter as ctk
import requests
import urllib3
import threading
import time

# I-disable ang mga SSL warnings sa terminal dahil sa localhost self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class LoadingModal(ctk.CTkFrame):
    """Isang custom overlay modal na humaharang sa screen na may running text spinner."""

    def __init__(self, master):
        # FIX: Pinalitan ang 'rgba(...)' ng solid hex color string para maging 100% compatible sa Tkinter engine
        super().__init__(master, fg_color="#212529")
        self.place(relx=0, rely=0, relwidth=1, relheight=1)  # Sakop ang buong login window view

        # Loader Card Box
        self.box = ctk.CTkFrame(self, fg_color="white", border_color="#DEE2E6", border_width=1, corner_radius=8,
                                width=260, height=130)
        self.box.place(relx=0.5, rely=0.5, anchor="center")
        self.box.pack_propagate(False)

        # Animated Spinner Text Element
        self.spinner_lbl = ctk.CTkLabel(self.box, text="⠋", font=("Arial", 28, "bold"), text_color="#0d6efd")
        self.spinner_lbl.pack(pady=(25, 5))

        self.status_lbl = ctk.CTkLabel(self.box, text="Authenticating session...", font=("Arial", 12, "bold"),
                                       text_color="#495057")
        self.status_lbl.pack()

        self.is_running = True
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        threading.Thread(target=self.animate_spinner_loop, daemon=True).start()

    def animate_spinner_loop(self):
        idx = 0
        while self.is_running:
            try:
                if self.winfo_exists() and self.spinner_lbl.winfo_exists():
                    self.spinner_lbl.configure(text=self.spinner_chars[idx])
                    idx = (idx + 1) % len(self.spinner_chars)
            except:
                break
            time.sleep(0.08)  # Mabilis na spin speed cycle

    def close_modal(self):
        self.is_running = False
        try:
            self.destroy()
        except:
            pass


class LoginView(ctk.CTkFrame):
    def __init__(self, master, on_login_success):
        super().__init__(master, fg_color="#F8F9FA")  # Bootstrap bg-light
        self.on_login_success = on_login_success

        # Centered Bootstrap Form Card Wrapper
        self.card = ctk.CTkFrame(self, fg_color="white", border_color="#DEE2E6", border_width=1, corner_radius=8,
                                 width=380, height=420)
        self.card.place(relx=0.5, rely=0.5, anchor="center")
        self.card.pack_propagate(False)

        # Branding Header Text
        title_lbl = ctk.CTkLabel(self.card, text="AUP JLDM Library DTR", font=("Arial", 18, "bold"),
                                 text_color="#212529")
        title_lbl.pack(pady=(35, 5))

        subtitle_lbl = ctk.CTkLabel(self.card, text="Sign in to your account credentials", font=("Arial", 12),
                                    text_color="#6C757D")
        subtitle_lbl.pack(pady=(0, 25))

        # Input Boxes Block
        username_lbl = ctk.CTkLabel(self.card, text="Username or ID Number", font=("Arial", 11, "bold"),
                                    text_color="#212529")
        username_lbl.pack(anchor="w", padx=30, pady=(5, 2))
        self.username_entry = ctk.CTkEntry(self.card, placeholder_text="Enter ID Number...", width=320, height=35,
                                           corner_radius=4)
        self.username_entry.pack(padx=30)

        password_lbl = ctk.CTkLabel(self.card, text="Password String", font=("Arial", 11, "bold"), text_color="#212529")
        password_lbl.pack(anchor="w", padx=30, pady=(15, 2))
        self.password_entry = ctk.CTkEntry(self.card, placeholder_text="Enter password...", show="*", width=320,
                                           height=35, corner_radius=4)
        self.password_entry.pack(padx=30)

        # Live Validation feedback element
        self.alert_lbl = ctk.CTkLabel(self.card, text="", font=("Arial", 11, "bold"), text_color="#842029",
                                      wraplength=300)
        self.alert_lbl.pack(pady=(15, 0))

        # Action Buttons
        self.login_btn = ctk.CTkButton(
            self.card, text="Sign In Account", font=("Arial", 13, "bold"),
            fg_color="#0d6efd", hover_color="#0b5ed7", height=38, corner_radius=4,
            command=self.start_login_thread
        )
        self.login_btn.pack(fill="x", padx=30, pady=(10, 20))

        self.loader_modal = None

    def start_login_thread(self):
        """Umiwas sa UI freeze sa pamamagitan ng pagtakbo ng API post sa background."""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            self.alert_lbl.configure(text="Complete all missing input parameters.")
            return

        self.alert_lbl.configure(text="")

        # I-spawn ang loading window popup modal
        self.loader_modal = LoadingModal(self)

        # Patakbuhin ang network request sa background thread para gumana ang spinner animation
        threading.Thread(target=self.execute_api_auth, args=(username, password), daemon=True).start()

    def execute_api_auth(self, username, password):
        login_url = "https://localhost/webapps/module/dtr/api/auth/login"
        payload = {"idnumber": username, "password": password}

        error_to_display = None
        success_payload = None

        try:
            response = requests.post(login_url, json=payload, timeout=8, verify=False)

            if response.status_code == 200:
                response_data = response.json()

                if response_data.get("status") == "success":
                    user_obj = response_data.get("user", {})
                    success_payload = {
                        "firstname": user_obj.get("firstname", username),
                        "lastname": user_obj.get("lastname", ""),
                        "job_title": user_obj.get("job_title", "Library Staff")
                    }
                else:
                    error_to_display = response_data.get("message", "Invalid login credentials.")
            else:
                error_to_display = f"Server Error: Status Code {response.status_code}"

        except requests.exceptions.Timeout:
            error_to_display = "Connection Timeout. Is the backend running?"
        except requests.exceptions.ConnectionError:
            error_to_display = "Cannot connect to localhost backend API server."
        except Exception as e:
            error_to_display = "Unexpected Error occurred."
            print(f"Login debug logs: {e}")

        # I-schedule ang GUI updates pabalik sa Tkinter Main Loop Thread safely
        self.after(0, lambda: self.finalize_ui_login_state(error_to_display, success_payload))

    def finalize_ui_login_state(self, error_msg, user_payload):
        # Isara muna ang popup overlay modal
        if self.loader_modal and self.loader_modal.winfo_exists():
            self.loader_modal.close_modal()

        if user_payload:
            # Pag login successful, lipat na sa dashboard
            self.on_login_success(user_payload)
        else:
            # Pag may error, ipakita sa alert line
            if self.winfo_exists() and self.alert_lbl.winfo_exists():
                self.alert_lbl.configure(text=f"{error_msg}")