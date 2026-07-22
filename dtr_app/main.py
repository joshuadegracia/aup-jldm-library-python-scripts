import customtkinter as ctk
from login import LoginView
from dashboard import DashboardView


class AppOrchestrator(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AUP JLDM Library DTR System Core")

        # BOOTSTRAP RESIZABLE WINDOW SETUP
        self.geometry("850x700")
        self.minsize(450, 550)
        self.resizable(True, True)

        self.root_container = ctk.CTkFrame(self, fg_color="transparent")
        self.root_container.pack(fill="both", expand=True)

        self.active_view = None
        self.load_login_gateway()

    def load_login_gateway(self):
        self.clear_active_view()
        self.active_view = LoginView(self.root_container, on_login_success=self.load_dashboard_system)
        self.active_view.pack(fill="both", expand=True)

    def load_dashboard_system(self, session_user):
        self.clear_active_view()
        self.active_view = DashboardView(self.root_container, user_data=session_user, on_logout=self.load_login_gateway)
        self.active_view.pack(fill="both", expand=True)

    def clear_active_view(self):
        if self.active_view is not None:
            if hasattr(self.active_view, 'sync_active'):
                self.active_view.sync_active = False
            self.active_view.destroy()


if __name__ == "__main__":
    app = AppOrchestrator()
    app.mainloop()