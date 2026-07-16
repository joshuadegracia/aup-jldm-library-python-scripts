import hid
import time
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext

# --- Hardware Configuration ---
VID = 0x16C0
PID = 0x05DF

# Standard 8-byte feature report payloads
ON_PACKET = [0x00, 0xFF, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]
OFF_PACKET = [0x00, 0xFD, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]


class TurnstileRelayApp:
    def __init__(self, root):
        self.root = root
        self.root.title("USB Turnstile Controller - Verbose Console")
        self.root.geometry("620x520")
        self.root.minsize(550, 450)

        # Keep track of active device connection
        self.device = None
        self.is_connected = False

        # Apply standard layout styling
        self.setup_ui()

        # Print initial system status
        self.log("System initialized. Ready to connect.")
        self.auto_connect()

    def setup_ui(self):
        # Master Style configurations
        style = ttk.Style()
        style.theme_use('clam')

        # Main Container Frame
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ================= CONNECTION FRAME =================
        conn_frame = ttk.LabelFrame(main_frame, text=" Connection Control ", padding="10")
        conn_frame.pack(fill=tk.X, pady=(0, 10))

        self.status_label = ttk.Label(
            conn_frame,
            text="STATUS: DISCONNECTED",
            foreground="red",
            font=("Arial", 10, "bold")
        )
        self.status_label.pack(side=tk.LEFT, padx=5)

        self.btn_reconnect = ttk.Button(conn_frame, text="Re-Scan & Connect", command=self.auto_connect)
        self.btn_reconnect.pack(side=tk.RIGHT, padx=5)

        # ================= HARDWARE CONTROLS FRAME =================
        control_frame = ttk.LabelFrame(main_frame, text=" Hardware Commands ", padding="10")
        control_frame.pack(fill=tk.X, pady=10)

        # Individual ON / OFF state triggers
        btn_on = ttk.Button(control_frame, text="MANUAL ON (Keep Open)", command=self.turn_on)
        btn_on.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        btn_off = ttk.Button(control_frame, text="MANUAL OFF (Lock Gate)", command=self.turn_off)
        btn_off.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Divider or Space
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=5)

        # ================= PULSE SEQUENCER FRAME =================
        pulse_frame = ttk.LabelFrame(main_frame, text=" Auto-Pulse Sequencer (Automatic Lock) ", padding="15")
        pulse_frame.pack(fill=tk.X, pady=10)

        # Timer input slider/spinbox
        label_timer = ttk.Label(pulse_frame, text="Hold Open Duration (Seconds):", font=("Arial", 9))
        label_timer.pack(side=tk.LEFT, padx=(0, 5))

        self.spin_duration = ttk.Spinbox(pulse_frame, from_=0.5, to=60.0, increment=0.5, width=5)
        self.spin_duration.set(3.0)  # Default 3 seconds as requested
        self.spin_duration.pack(side=tk.LEFT, padx=5)

        # Trigger Pulse Action Button
        self.btn_pulse = ttk.Button(
            pulse_frame,
            text="⚡ TRIGGER PASSAGE",
            command=self.trigger_pulse_thread,
            style="Accent.TButton"
        )
        self.btn_pulse.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

        # ================= VERBOSE LOG CONSOLE =================
        log_frame = ttk.LabelFrame(main_frame, text=" Live Verbose Telemetry ", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.console_log = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            state='disabled',
            background="#1e1e1e",
            foreground="#d4d4d4",
            font=("Consolas", 9)
        )
        self.console_log.pack(fill=tk.BOTH, expand=True)

    # ================= VERBOSE LOGGER FUNCTION =================
    def log(self, message):
        """Appends formatted verbose timestamp logs to terminal and UI Console"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        formatted_message = f"[{timestamp}] {message}\n"

        # Write to standard out terminal
        print(formatted_message.strip())

        # Safely insert into Tkinter UI thread
        self.console_log.configure(state='normal')
        self.console_log.insert(tk.END, formatted_message)
        self.console_log.configure(state='disabled')
        self.console_log.see(tk.END)

    # ================= HARDWARE LOGIC =================
    def auto_connect(self):
        """Locates and initiates secure link with USB device"""
        self.log(f"Scanning host USB bus for Target VID: {hex(VID)} | PID: {hex(PID)}...")
        try:
            if self.device:
                self.device.close()
                self.log("Closed active legacy handles.")

            self.device = hid.device()
            self.device.open(VID, PID)
            self.is_connected = True

            # Extract basic descriptor info for user logs
            mfr = self.device.get_manufacturer_string()
            prod = self.device.get_product_string()

            self.status_label.config(text="STATUS: CONNECTED", foreground="green")
            self.log(f"Link Established! Manufacturer: '{mfr}' | Product: '{prod}'")

        except Exception as e:
            self.is_connected = False
            self.status_label.config(text="STATUS: DISCONNECTED", foreground="red")
            self.log(f"Connection Failed. Target hardware unresponsive: {e}")

    def send_packet(self, packet):
        """Low-level driver handler utilizing USB Feature Reports"""
        if not self.is_connected:
            self.log("TX HALTED: Hardware interface not verified. Retrying auto-connect...")
            self.auto_connect()
            if not self.is_connected:
                return False

        try:
            hex_print = " ".join([f"0x{b:02X}" for b in packet])
            self.log(f"TX Control Transfer -> {hex_print}")
            self.device.send_feature_report(packet)
            return True
        except Exception as e:
            self.log(f"TX FAILED: USB Pipeline error: {e}")
            self.is_connected = False
            self.status_label.config(text="STATUS: DISCONNECTED", foreground="red")
            return False

    def turn_on(self):
        self.log("Manual override command initiated: FORCE ON.")
        self.send_packet(ON_PACKET)

    def turn_off(self):
        self.log("Manual override command initiated: FORCE OFF.")
        self.send_packet(OFF_PACKET)

    # ================= SEQUENCING THREADS =================
    def trigger_pulse_thread(self):
        """Launches background thread so UI doesn't lock up during time.sleep()"""
        try:
            duration = float(self.spin_duration.get())
        except ValueError:
            self.log("INPUT ERROR: Invalid pulse float value. Defaulting to 3.0s")
            duration = 3.0

        thread = threading.Thread(target=self.run_pulse_sequence, args=(duration,), daemon=True)
        thread.start()

    def run_pulse_sequence(self, duration):
        self.btn_pulse.config(state=tk.DISABLED)  # Prevent user spamming trigger while active
        self.log(f"SEQUENCE ACTIVE: Opening turnstile gate for {duration} seconds.")

        # Step 1: Fire Relay 1
        if self.send_packet(ON_PACKET):
            self.log(f"RELAY CLOSED (Gate Signal Triggered). Holding state for {duration}s...")

            # Step 2: Hold open
            time.sleep(duration)

            # Step 3: De-energize Relay 1
            self.log("Countdown complete. Releasing turnstile gate switch...")
            self.send_packet(OFF_PACKET)
            self.log("RELAY OPENED (Gate locked).")
        else:
            self.log("SEQUENCE ABORTED: Communication failure occurred during sequence.")

        self.btn_pulse.config(state=tk.NORMAL)


if __name__ == "__main__":
    root = tk.Tk()
    app = TurnstileRelayApp(root)
    root.mainloop()