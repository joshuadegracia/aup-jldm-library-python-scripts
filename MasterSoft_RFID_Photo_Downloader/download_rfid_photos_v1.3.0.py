"""
RFID Photo Downloader
Version: 1.3.0
Description: Verbose, server-polite bulk downloader optimized for compilation into an EXE.
"""

import os
import sys
import requests
import time
from datetime import datetime

# --- SCRIPT VERSIONING ---
__version__ = "1.3.0"

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
    Highly verbose and defensive downloader that monitors server strain metrics.
    """
    clean_id = photo_id.strip("{}")
    url = f"{base_url}/{clean_id}"

    max_retries = 3
    retry_delay = 10  # Start with a stricter 10s cooldown for 429s

    print(f"🔍 [CONNECTING] Querying target URL: {url}")

    for attempt in range(max_retries + 1):
        try:
            start_time = time.time()
            with requests.get(url, stream=True, timeout=8) as response:
                latency = time.time() - start_time

                print(f"   ↳ [RESPONSE] HTTP Status: {response.status_code} | Latency: {latency:.2f}s")

                if response.status_code == 429:
                    if attempt < max_retries:
                        print(
                            f"🛑 [SERVER OVERLOAD] 429 Rate Limit Hit. Backing off for {retry_delay}s... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        print(f"🚨 [FATAL] Exceeded maximum retries for ID {clean_id} due to rate limiting.")
                        return "RATE_LIMITED", 0

                if response.status_code == 404:
                    print(f"ℹ️  [SKIP] ID {clean_id} does not exist on server (404 Not Found).")
                    return "NOT_FOUND", 0
                elif response.status_code != 200:
                    print(f"⚠️  [SERVER ERROR] Received unexpected HTTP {response.status_code} for ID {clean_id}")
                    return "SERVER_ERROR", 0

                content_type = response.headers.get("Content-Type", "").lower()
                expected_length = int(response.headers.get("Content-Length", 0))
                print(f"   ↳ [HEADERS] Type: '{content_type}' | Expected Size: {expected_length} bytes")

                extension = None
                for mime_type, ext in IMAGE_EXTENSIONS.items():
                    if mime_type in content_type:
                        extension = ext
                        break

                if not extension:
                    print(f"⚠️  [DEFENSIVE DROP] Content type evaluation failed for '{content_type}'")
                    return "INVALID_TYPE", 0

                file_path = os.path.join(output_dir, f"{clean_id}{extension}")
                bytes_downloaded = 0

                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            bytes_downloaded += len(chunk)

                if expected_length > 0 and bytes_downloaded != expected_length:
                    print(f"❌ [INTEGRITY CRASH] Mismatch detected. Got {bytes_downloaded}/{expected_length} bytes.")
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return "CORRUPTED", 0

                print(f"✅ [SUCCESS] File committed to disk: {clean_id}{extension} ({bytes_downloaded} bytes)")
                return "SUCCESS", bytes_downloaded

        except requests.exceptions.Timeout:
            print(f"⏳ [TIMEOUT] Server dropped connection threshold for ID {clean_id}")
            return "TIMEOUT", 0
        except requests.exceptions.RequestException as e:
            print(f"🚨 [NETWORK DOWN] Connection anomaly: {e}")
            return "NETWORK_ERROR", 0

    return "FAILED", 0


if __name__ == "__main__":
    # Ensure smooth execution paths when compiled as an EXE
    base_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)

    today_str = datetime.now().strftime("%Y-%m-%d")
    versioned_dir = os.path.join(base_path, f"downloaded_photos_v{__version__}_{today_str}")
    os.makedirs(versioned_dir, exist_ok=True)

    print("=========================================================================")
    print(f" 🛡️  DEFENSIVE & VERBOSE RFID DOWNLOADER ENGINE v{__version__}")
    print(f" 📁 Deployment Directory: {versioned_dir}")
    print("=========================================================================\n")

    start_number = 1
    end_number = 5000

    metrics = {"SUCCESS": 0, "NOT_FOUND": 0, "SERVER_ERROR": 0, "INVALID_TYPE": 0, "CORRUPTED": 0, "TIMEOUT": 0,
               "NETWORK_ERROR": 0, "RATE_LIMITED": 0, "FAILED": 0}

    for i in range(start_number, end_number + 1):
        dynamic_id = f"2026-AUP{i:04d}"
        print(f"🔹 Processing Record [{i}/{end_number}]")

        result, file_size = download_rfid_photo(dynamic_id, versioned_dir)
        metrics[result] += 1

        # --- POLITE INTELLIGENT INTERVALS ---
        # Base sleep time is 1.5 seconds so the server never chokes.
        # If it was a heavy BMP file (over 200KB), we give the server an extra 1.5 seconds of rest.
        sleep_interval = 1.5
        if file_size > 200000:
            print(f"   ↳ 🐌 Heavy payload detected ({file_size} bytes). Applying cool-down penalty...")
            sleep_interval += 1.5

        print(f"   ↳ ⏱️  Pausing engine for {sleep_interval} seconds to maintain server health...\n")
        time.sleep(sleep_interval)

    print("\n=========================================")
    print("📊 FINAL SESSION METRICS SUMMARY")
    print("=========================================")
    for status, count in metrics.items():
        if count > 0:
            print(f" • {status.ljust(15)}: {count}")
    print("=========================================")

    # Keeps the console window open when running as an EXE
    input("\nExecution completed. Press Enter to exit close window...")