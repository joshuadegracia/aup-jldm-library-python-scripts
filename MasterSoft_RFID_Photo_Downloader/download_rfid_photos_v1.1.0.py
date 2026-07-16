"""
RFID Photo Downloader
Version: 1.1.0
Description: Production-ready bulk downloader featuring robust defensive API response handling.
"""

import os
import requests
import time
from datetime import datetime

# --- SCRIPT VERSIONING ---
__version__ = "1.1.0"

# Map of standard image content types to their file extensions
IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif"
}


def download_rfid_photo(photo_id, output_dir, base_url="http://192.168.7.216:8000/public/rfid-tap/photo"):
    """
    Defensively downloads an RFID photo by verifying headers, response types, and content size.
    """
    clean_id = photo_id.strip("{}")
    url = f"{base_url}/{clean_id}"

    try:
        # 1. Short timeout to prevent the script from hanging indefinitely if the server freezes
        with requests.get(url, stream=True, timeout=5) as response:

            # 2. Defensive check for HTTP status codes
            if response.status_code == 404:
                return "NOT_FOUND"
            elif response.status_code != 200:
                print(f"⚠️ Server Alert for ID {clean_id}: HTTP {response.status_code}")
                return "SERVER_ERROR"

            # 3. Defensive Header Verification: Ensure the server actually returned an image
            content_type = response.headers.get("Content-Type", "").lower()
            extension = None
            for mime_type, ext in IMAGE_EXTENSIONS.items():
                if mime_type in content_type:
                    extension = ext
                    break

            if not extension:
                print(f"⚠️ Defensive Drop for ID {clean_id}: Invalid content type '{content_type}' (Not an image)")
                return "INVALID_TYPE"

            # Determine definitive file path based on server response header
            file_path = os.path.join(output_dir, f"{clean_id}{extension}")

            # 4. Read expected content length for validation later
            expected_length = int(response.headers.get("Content-Length", 0))
            bytes_downloaded = 0

            # 5. Stream safely to local storage
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # Filter out keep-alive new chunks
                        f.write(chunk)
                        bytes_downloaded += len(chunk)

            # 6. Defensive Integrity Check: Did we get the whole file?
            if expected_length > 0 and bytes_downloaded != expected_length:
                print(
                    f"❌ Integrity Error for ID {clean_id}: Size mismatch! Expected {expected_length} bytes, got {bytes_downloaded}")
                if os.path.exists(file_path):
                    os.remove(file_path)  # Remove corrupted file fragment
                return "CORRUPTED"

            print(f"✅ Success: Downloaded {clean_id}{extension} ({bytes_downloaded} bytes)")
            return "SUCCESS"

    except requests.exceptions.Timeout:
        print(f"⏳ Timeout Error: Server took too long to respond for ID {clean_id}")
        return "TIMEOUT"
    except requests.exceptions.RequestException as e:
        print(f"🚨 Network Error for ID {clean_id}: {e}")
        return "NETWORK_ERROR"


if __name__ == "__main__":
    today_str = datetime.now().strftime("%Y-%m-%d")
    versioned_dir = f"downloaded_photos_v{__version__}_{today_str}"
    os.makedirs(versioned_dir, exist_ok=True)

    print("=========================================")
    print(f" 🛡️ Defensive RFID Photo Downloader v{__version__}")
    print(f" 📁 Target Folder: {versioned_dir}")
    print("=========================================\n")

    start_number = 1
    end_number = 5000

    # Tracking distinct API outcomes
    metrics = {"SUCCESS": 0, "NOT_FOUND": 0, "SERVER_ERROR": 0, "INVALID_TYPE": 0, "CORRUPTED": 0, "TIMEOUT": 0,
               "NETWORK_ERROR": 0}

    for i in range(start_number, end_number + 1):
        dynamic_id = f"2026-AUP{i:04d}"

        result = download_rfid_photo(dynamic_id, versioned_dir)
        metrics[result] += 1

        # Standard safety delay
        time.sleep(0.05)

    # Final Metrics Summary report
    print("\n=========================================")
    print("📊 FINAL DOWNLOAD METRICS")
    print("=========================================")
    for status, count in metrics.items():
        if count > 0:
            print(f" • {status}: {count}")
    print("=========================================")