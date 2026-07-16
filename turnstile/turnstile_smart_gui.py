import sys
import time
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext

# Standard library imports with safe fallbacks
try:
    import hid

    HID_AVAILABLE = True
except ImportError:
    HID_AVAILABLE = False

try:
    import serial
    import serial.tools.list_ports

    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class SmartTurnstileGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Universal USB Turnstile Controller")
        self.root.geometry("650x550")
        self.root.minsize(580, 480)

        # State tracking variables
        self.connected_device = None  # Will hold the hid.device or serial.Serial handle
        self.connection_type = None  # "HID" or "SERIAL" or None
        self.active_port_or_path = ""  # COM port or USB HID device path

        # Setup modern layout
        self.setup_ui()

        self.log("System initialized. Beginning hardware discovery protocol...")
        self.detect_and_connect()

    def setup_ui(self):
        # Apply standard UI theme styles
        style = ttk.Style()
        style.theme_use('clam')

        # Main Layout Container
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ================= CONNECTION FRAME =================
        conn_frame = ttk.LabelFrame(main_frame, text=" Connection Auto-Detection Engine ", padding="10")
        conn_frame.pack(fill=tk.X, pady=(0, 10))

        self.status_label = ttk.Label(
            conn_frame,
            text="STATUS: DISCONNECTED",
            foreground="red",
            font=("Arial", 10, "bold")
        )
        self.status_label.pack(side=tk.LEFT, padx=5)

        self.btn_reconnect = ttk.Button(conn_frame, text="Re-Scan Bus", command=self.detect_and_connect)
        self.btn_reconnect.pack(side=tk.RIGHT, padx=5)

        # ================= HARDWARE CONTROLS FRAME =================
        control_frame = ttk.LabelFrame(main_frame, text=" Manual Override Controls ", padding="10")
        control_frame.pack(fill=tk.X, pady=10)

        self.btn_on = ttk.Button(control_frame, text="MANUAL ON (Keep Open)", command=self.turn_on)
        self.btn_on.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.btn_off = ttk.Button(control_frame, text="MANUAL OFF (Lock Gate)", command=self.turn_off)
        self.btn_off.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=5)

        # ================= AUTO-PULSE SEQUENCER =================
        pulse_frame = ttk.LabelFrame(main_frame, text=" Auto-Pulse Sequencer ", padding="15")
        pulse_frame.pack(fill=tk.X, pady=10)

        label_timer = ttk.Label(pulse_frame, text="Hold Gate Open for:", font=("Arial", 9))
        label_timer.pack(side=tk.LEFT, padx=(0, 5))

        self.spin_duration = ttk.Spinbox(pulse_frame, from_=0.5, to=60.0, increment=0.5, width=6)
        self.spin_duration.set(3.0)  # Standard 3 seconds
        self.spin_duration.pack(side=tk.LEFT, padx=5)

        label_sec = ttk.Label(pulse_frame, text="seconds", font=("Arial", 9))
        label_sec.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_pulse = ttk.Button(
            pulse_frame,
            text="⚡ TRIGGER PASSAGE",
            command=self.trigger_pulse_thread,
        )
        self.btn_pulse.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

        # ================= REAL-TIME VERBOSE LOG CONSOLE =================
        log_frame = ttk.LabelFrame(main_frame, text=" Real-Time Telemetry & Packets ", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.console_log = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            state='disabled',
            background="#1a1a1a",
            foreground="#21e6c1",  # Tech green/cyan console look
            font=("Consolas", 9)
        )
        self.console_log.pack(fill=tk.BOTH, expand=True)

    # ================= REAL-TIME VERBOSE LOG CONSOLE =================
    def log(self, message):
        """Outputs standard format timestamps to physical terminal and the UI logs"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        formatted_message = f"[{timestamp}] {message}\n"

        print(formatted_message.strip())

        self.console_log.configure(state='normal')
        self.console_log.insert(tk.END, formatted_message)
        self.console_log.configure(state='disabled')
        self.console_log.see(tk.END)

    # ================= DEVICE SCANNING & DETECTION ENGINE =================
    def detect_and_connect(self):
        """Scans the platform for physical HID devices or serial hardware dynamically"""
        self.log("Auto-detection scan started...")
        self.close_active_handles()

        # Step A: Scan for raw USB-HID Devices
        if HID_AVAILABLE:
            self.log("Scanning USB-HID Bus...")
            for device_info in hid.enumerate():
                vid = device_info['vendor_id']
                pid = device_info['product_id']

                # Dynamic matching for your working target values (VID 0x16C0, PID 0x05DF)
                if vid == 0x16C0 and pid == 0x05DF:
                    self.log(f"[FOUND USB-HID RELAY] VID: {hex(vid)} | PID: {hex(pid)}")
                    self.log(f"  -> Path: {device_info['path']}")
                    self.log(f"  -> Product: {device_info['product_string']}")
                    self.log(f"  -> Manufacturer: {device_info['manufacturer_string']}")

                    try:
                        dev = hid.device()
                        dev.open(vid, pid)
                        self.connected_device = dev
                        self.connection_type = "HID"
                        self.active_port_or_path = device_info['path']

                        self.status_label.config(text="STATUS: CONNECTED (USB-HID)", foreground="green")
                        self.log(">> Connected to USB-HID Relay.")
                        return True
                    except Exception as e:
                        self.log(f"  -> Connection attempt failed: {e}")

        # Step B: Scan for COM Ports if HID was not matched
        if SERIAL_AVAILABLE:
            self.log("Scanning Virtual COM Ports...")
            ports = serial.tools.list_ports.comports()
            for p in ports:
                desc = p.description.lower()
                # Safely matching general USB adapter chips (CH340, Prolific, PL2303, FTDI, Silicon Labs)
                if any(k in desc for k in ["usb", "serial", "ch340", "com", "prolific"]):
                    self.log(f"[FOUND SERIAL DEVICE] Port: {p.device} | Description: {p.description}")

                    try:
                        # Attempt standard 9600 baud rate connection
                        ser = serial.Serial(p.device, 9600, timeout=1)
                        self.connected_device = ser
                        self.connection_type = "SERIAL"
                        self.active_port_or_path = p.device

                        self.status_label.config(text=f"STATUS: CONNECTED ({p.device})", foreground="green")
                        self.log(f">> Linked with USB-Serial Relay on {p.device} @ 9600 Baud.")
                        return True
                    except Exception as e:
                        self.log(f"  -> Connection to {p.device} failed: {e}")

        # Fallback if both pipelines are empty
        self.connection_type = None
        self.connected_device = None
        self.status_label.config(text="STATUS: DISCONNECTED", foreground="red")
        self.log("WARNING: No compatible USB Relays (HID or Serial) discovered.")
        return False

    def close_active_handles(self):
        """Safely tears down active connections to avoid system lock-up"""
        if self.connected_device:
            try:
                self.connected_device.close()
                self.log("Closed previous handle references safely.")
            except Exception:
                pass
            self.connected_device = None

    # ================= CORE TX WRAPPERS =================
    def send_packet(self, packet_type):
        """Wrapper to transmit data packet based on the auto-detected device type"""
        if not self.connected_device:
            self.log("TX ABORTED: Hardware interface is disconnected.")
            return False

        try:
            if self.connection_type == "HID":
                # HID expects feature reports
                # ON = 0xFF, OFF = 0xFD
                cmd = 0xFF if packet_type == "ON" else 0xFD
                packet = [0x00, cmd, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]

                hex_str = " ".join([f"0x{b:02X}" for b in packet])
                self.log(f"TX [USB-HID Feature Report] -> {hex_str}")
                self.connected_device.send_feature_report(packet)
                return True

            elif self.connection_type == "SERIAL":
                # Serial expects standard Hex bytes (Robojax configuration)
                # ON = A0 01 01 A2, OFF = A0 01 00 A1
                if packet_type == "ON":
                    packet = bytes([0xA0, 0x01, 0x01, 0xA2])
                else:
                    packet = bytes([0xA0, 0x01, 0x00, 0xA1])

                hex_str = " ".join([f"0x{b:02X}" for b in packet])
                self.log(f"TX [Serial Port {self.active_port_or_path}] -> {hex_str}")
                self.connected_device.write(packet)
                return True

        except Exception as e:
            self.log(f"TX ERROR: Output channel failure: {e}")
            self.detect_and_connect()  # Force re-scan to recover
            return False

    def turn_on(self):
        self.log("Manual trigger: ON command initiated.")
        self.send_packet("ON")

    def turn_off(self):
        self.log("Manual trigger: OFF command initiated.")
        self.send_packet("OFF")

    # ================= WORKER THREAD POOL =================
    def trigger_pulse_thread(self):
        """Runs the pulse sequence inside a background worker thread to keep the Tkinter UI fluid"""
        try:
            duration = float(self.spin_duration.get())
        except ValueError:
            self.log("Input error! Read duration failed. Reverting to 3.0s.")
            duration = 3.0

        # Launch thread
        worker = threading.Thread(target=self.run_pulse_sequence, args=(duration,), daemon=True)
        worker.start()

    def run_pulse_sequence(self, duration):
        self.btn_pulse.config(state=tk.DISABLED)
        self.log(f"STARTING PASSAGE SEQUENCE (Timer: {duration}s)")

        # 1. Close circuit
        if self.send_packet("ON"):
            self.log(f"Switch Active. Keeping turnstile unlocked for {duration} seconds...")

            # 2. Open hold loop
            time.sleep(duration)

            # 3. Open circuit (Relock)
            self.log("Hold duration expired. Releasing switch...")
            self.send_packet("OFF")
            self.log("Passage sequence completed.")
        else:
            self.log("Sequence halted: Outgoing packet error.")

        self.btn_pulse.config(state=tk.NORMAL)


if __name__ == "__main__":
    root = tk.Tk()
    app = SmartTurnstileGUI(root)
    root.mainloop()