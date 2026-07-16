import sys
import serial.tools.list_ports

try:
    import hid

    HID_AVAILABLE = True
except ImportError:
    HID_AVAILABLE = False

print("===============================================")
print("          USB RELAY DEVICE DETECTOR            ")
print("===============================================")

# 1. SCANNING FOR VIRTUAL COM PORTS (Most likely for this specific Robojax board)
print("\nScanning Virtual COM Ports...")
ports = serial.tools.list_ports.comports()
found_serial = False

for port in ports:
    # Common USB-Serial chip manufacturers/descriptions (CH340, Prolific, FTDI, Silicon Labs)
    desc = port.description.lower()
    hwid = port.hwid.lower()

    # We look for signs of a serial adapter
    if "usb" in desc or "serial" in desc or "ch340" in desc or "com" in desc:
        print(f"\n[FOUND SERIAL DEVICE]")
        print(f"  -> Port: {port.device}")
        print(f"  -> Description: {port.description}")
        print(f"  -> Hardware ID: {port.hwid}")
        print(f"  -> Manufacturer: {port.manufacturer}")
        print(f"  * ACTION: Use '{port.device}' in your serial python script!")
        found_serial = True

if not found_serial:
    print("  No obvious USB-Serial devices found.")

# 2. SCANNING FOR RAW USB-HID DEVICES (Alternative check for driverless HID mode)
print("\nScanning USB-HID Devices...")
if not HID_AVAILABLE:
    print("  (hidapi library not installed. Run 'pip install hidapi' to scan HID devices)")
else:
    found_hid = False
    for device in hid.enumerate():
        # Check standard default ATtiny45 / V-USB VID/PID values (0x16C0 / 0x05DF)
        if device['vendor_id'] == 0x16c0 and device['product_id'] == 0x05df:
            print(f"\n[FOUND HID RELAY DEVICE]")
            print(f"  -> Path: {device['path']}")
            print(f"  -> Mfr: {device['manufacturer_string']}")
            print(f"  -> Product: {device['product_string']}")
            print(f"  -> Serial Number: {device['serial_number']}")
            print(f"  * ACTION: Use VID 0x16C0 and PID 0x05DF in your HID script.")
            found_hid = True

    if not found_hid:
        print("  No matching HID relay devices found.")

print("\n===============================================")