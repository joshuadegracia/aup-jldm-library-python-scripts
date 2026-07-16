import hid
import time

# Your detected device details
VID = 0x16C0
PID = 0x05DF

# For V-USB HID relays, commands MUST go through send_feature_report.
# Standard 8-byte format: [ReportID, Command, RelayIndex, Padding...]
ON_PACKET = [0x00, 0xFF, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]
OFF_PACKET = [0x00, 0xFD, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]

try:
    # Open the HID device
    device = hid.device()
    device.open(VID, PID)

    # Dynamically read the manufacturer and product strings from the USB chip
    try:
        manufacturer = device.get_manufacturer_string()
        product = device.get_product_string()
    except Exception:
        manufacturer = "USB"
        product = "Relay"

    print(f"Successfully connected to {manufacturer} {product}!")
    print("---------------------------------------------")
    print("Commands: 'on' | 'off' | 'pulse' | 'exit'")
    print("---------------------------------------------")

    while True:
        user_input = input("Enter command: ").strip().lower()

        if user_input == "on":
            # Using send_feature_report instead of write
            device.send_feature_report(ON_PACKET)
            print(">> Sent ON command via Feature Report.")

        elif user_input == "off":
            # Using send_feature_report instead of write
            device.send_feature_report(OFF_PACKET)
            print(">> Sent OFF command via Feature Report.")

        elif user_input == "pulse":
            print(">> Sending 500ms pulse to open turnstile...")
            device.send_feature_report(ON_PACKET)
            time.sleep(0.5)
            device.send_feature_report(OFF_PACKET)
            print(">> Pulse complete.")

        elif user_input == "exit":
            device.send_feature_report(OFF_PACKET)
            print("Exiting.")
            break
        else:
            print("Invalid command. Choose 'on', 'off', 'pulse', or 'exit'.")

    device.close()

except Exception as e:
    print(f"Error: {e}")