"""
RFID Photo Downloader
Version: 1.2.0
Description: Production-ready bulk downloader featuring automated HTTP 429 rate-limit backoff handling.
"""

import os
import requests
import time
from datetime import datetime

# --- SCRIPT VERSIONING ---
__version__ = "1.2.0"

# Expanded to include BMP images!
IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/x-ms-bmp": ".bmp"
}


def download_rfid_photo(photo_id, output_dir, base_url="http://192.168.7.216:8000/public/rfid-tap/photo"):
    """
    Defensively downloads an RFID photo with intelligent rate-limit handling (HTTP 429).
    """
    clean_id = photo_id.strip("{}")
    url = f"{base_url}/{clean_id}"

    # Retry logic parameters for handling 429 errors
    max_retries = 3
    retry_delay = 5  # Start with a 5-second cooldown

    for attempt in range(max_retries + 1):
        try:
            with requests.get(url, stream=True, timeout=5) as response:

                # Dynamic handling of Rate Limiting (Too Many Requests)
                if response.status_code == 429:
                    if attempt < max_retries:
                        print(
                            f"🛑 Rate Limited (429) on ID {clean_id}. Cooling down for {retry_delay}s... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Double the wait time for the next attempt if it fails again
                        continue
                    else:
                        print(f"🚨 Failed permanently on ID {clean_id} due to rate limiting.")
                        return "RATE_LIMITED"

                if response.status_code == 404:
                    return "NOT_FOUND"
                elif response.status_code != 200:
                    print(f"⚠️ Server Alert for ID {clean_id}: HTTP {response.status_code}")
                    return "SERVER_ERROR"

                # Check if payload is a valid image type
                content_type = response.headers.get("Content-Type", "").lower()
                extension = None
                for mime_type, ext in IMAGE_EXTENSIONS.items():
                    if mime_type in content_type:
                        extension = ext
                        break

                if not extension:
                    print(f"⚠️ Defensive Drop for ID {clean_id}: Invalid content type '{content_type}'")
                    return "INVALID_TYPE"

                file_path = os.path.join(output_dir, f"{clean_id}{extension}")
                expected_length = int(response.headers.get("Content-Length", 0))
                bytes_downloaded = 0

                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            bytes_downloaded += len(chunk)

                if expected_length > 0 and bytes_downloaded != expected_length:
                    print(f"❌ Integrity Error for ID {clean_id}: Size mismatch.")
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return "CORRUPTED"

                print(f"✅ Success: Downloaded {clean_id}{extension} ({bytes_downloaded} bytes)")
                return "SUCCESS"

        except requests.exceptions.Timeout:
            print(f"⏳ Timeout Error for ID {clean_id}")
            return "TIMEOUT"
        except requests.exceptions.RequestException as e:
            print(f"🚨 Network Error for ID {clean_id}: {e}")
            return "NETWORK_ERROR"

    return "FAILED"


if __name__ == "__main__":
    today_str = datetime.now().strftime("%Y-%m-%d")
    versioned_dir = f"downloaded_photos_v{__version__}_{today_str}"
    os.makedirs(versioned_dir, exist_ok=True)

    print("=========================================")
    print(f" 🛡️ Smart & Defensive RFID Downloader v{__version__}")
    print(f" 📁 Target Folder: {versioned_dir}")
    print("=========================================\n")

    start_number = 1
    end_number = 5000

    metrics = {"SUCCESS": 0, "NOT_FOUND": 0, "SERVER_ERROR": 0, "INVALID_TYPE": 0, "CORRUPTED": 0, "TIMEOUT": 0,
               "NETWORK_ERROR": 0, "RATE_LIMITED": 0}

    for i in range(start_number, end_number + 1):
        dynamic_id = f"2026-AUP{i:04d}"

        result = download_rfid_photo(dynamic_id, versioned_dir)
        metrics[result] += 1

        # Increased base delay to 0.2 seconds to help appease the server's rate limiter
        time.sleep(0.2)

    print("\n=========================================")
    print("📊 FINAL DOWNLOAD METRICS")
    print("=========================================")
    for status, count in metrics.items():
        if count > 0:
            print(f" • {status}: {count}")
    print("=========================================")