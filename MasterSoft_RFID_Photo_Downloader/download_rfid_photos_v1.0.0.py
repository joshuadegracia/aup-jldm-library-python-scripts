"""
RFID Photo Downloader
Version: 1.0.0
Description: Automatically generates sequential student IDs and downloads photos from the local RFID server.
"""

import os
import requests
import time
from datetime import datetime

# --- SCRIPT VERSIONING ---
__version__ = "1.0.0"


def download_rfid_photo(photo_id, output_dir, base_url="http://192.168.7.216:8000/public/rfid-tap/photo"):
    """
    Downloads a photo from the local RFID server and saves it into the versioned directory.
    """
    clean_id = photo_id.strip("{}")
    url = f"{base_url}/{clean_id}"
    file_path = os.path.join(output_dir, f"{clean_id}.jpg")

    try:
        with requests.get(url, stream=True, timeout=5) as response:
            if response.status_code == 200:
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"✅ Success: Saved {clean_id}.jpg")
                return True
            else:
                return False
    except requests.exceptions.RequestException:
        print(f"❌ Connection Error for ID: {clean_id}")
        return False


if __name__ == "__main__":
    # --- COMBINED VERSION & DATE SYSTEM ---
    # Creates folders like: "downloaded_photos_v1.0.0_2026-07-15"
    today_str = datetime.now().strftime("%Y-%m-%d")
    versioned_dir = f"downloaded_photos_v{__version__}_{today_str}"

    os.makedirs(versioned_dir, exist_ok=True)

    print(f"=========================================")
    print(f" 🚀 RFID Photo Downloader Tool v{__version__}")
    print(f" 📁 Target Folder: {versioned_dir}")
    print(f"=========================================\n")
    print("Starting bulk photo download for 5,000 students...")

    start_number = 1
    end_number = 5000
    success_count = 0

    for i in range(start_number, end_number + 1):
        dynamic_id = f"2026-AUP{i:04d}"

        if download_rfid_photo(dynamic_id, versioned_dir):
            success_count += 1

        time.sleep(0.05)

    print(f"\n🎉 Done! Successfully downloaded {success_count} photos to '{versioned_dir}'.")