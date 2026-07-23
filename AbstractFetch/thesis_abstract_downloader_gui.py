"""
AbstractFetch - Thesis Downloader & Catalog Organizer (Relational Version)
===================================================================================
Updated with Local Disk Search (/mnt/ / Network Drive) and prefix_ID matching.
"""

import glob
import os
import re
import shutil
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import urllib.parse
import mysql.connector
import pandas as pd

import requests
from openpyxl.styles import PatternFill, Font

try:
    import ttkbootstrap as ttk_bs
    HAS_TTKBOOTSTRAP = True
except ImportError:
    HAS_TTKBOOTSTRAP = False


def sanitize_folder_name(name):
    if not name or str(name).strip() == "":
        return "Uncategorized"
    sanitized = re.sub(r"\s+", "_", str(name).strip())
    sanitized = re.sub(r'[\\/*?:"<>|]', "", sanitized)
    return sanitized


class DatabaseSettingsDialog(tk.Toplevel):
    def __init__(self, parent, db_config):
        super().__init__(parent)
        self.title("Database Connection Settings")
        self.geometry("420x440")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.db_config = db_config

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Database Settings", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 10))

        ttk.Label(frame, text="Host / IP Address:").pack(anchor="w")
        self.ent_host = ttk.Entry(frame)
        self.ent_host.insert(0, self.db_config.get("host", "192.168.2.104"))
        self.ent_host.pack(fill="x", pady=(0, 6))

        ttk.Label(frame, text="Port:").pack(anchor="w")
        self.ent_port = ttk.Entry(frame)
        self.ent_port.insert(0, str(self.db_config.get("port", 3308)))
        self.ent_port.pack(fill="x", pady=(0, 6))

        ttk.Label(frame, text="Username:").pack(anchor="w")
        self.ent_user = ttk.Entry(frame)
        self.ent_user.insert(0, self.db_config.get("user", "root"))
        self.ent_user.pack(fill="x", pady=(0, 6))

        ttk.Label(frame, text="Password:").pack(anchor="w")
        self.ent_pass = ttk.Entry(frame, show="*")
        self.ent_pass.insert(0, self.db_config.get("password", ""))
        self.ent_pass.pack(fill="x", pady=(0, 6))

        ttk.Label(frame, text="Database Name:").pack(anchor="w")
        self.ent_dbname = ttk.Entry(frame)
        self.ent_dbname.insert(0, self.db_config.get("database", "jldmlibrary_thesis"))
        self.ent_dbname.pack(fill="x", pady=(0, 15))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", side="bottom")

        btn_save = ttk.Button(
            btn_frame,
            text="Save Settings",
            command=self.save_settings,
            bootstyle="primary" if HAS_TTKBOOTSTRAP else None,
        )
        btn_save.pack(side="right")

    def save_settings(self):
        self.db_config["host"] = self.ent_host.get().strip()
        self.db_config["port"] = int(self.ent_port.get().strip() or 3308)
        self.db_config["user"] = self.ent_user.get().strip()
        self.db_config["password"] = self.ent_pass.get()
        self.db_config["database"] = self.ent_dbname.get().strip()
        self.destroy()


class ThesisDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AbstractFetch - JLDM Library Thesis Downloader")
        self.root.geometry("800x720")
        self.root.minsize(680, 600)
        self.root.resizable(True, True)

        self.db_config = {
            "host": "192.168.2.104",
            "port": 3308,
            "user": "root",
            "password": "@dm!N2026",
            "database": "jldmlibrary_thesis",
        }

        # Local storage path fallback
        self.local_abstract_storage = "/mnt/JLDMLibFiles/ThesisFiles/abstract"

        self.stop_requested = False
        self.is_running = False
        self.base_url = "https://jldmlibrary.aup.edu.ph/webapps/module/thesis/download-file-matcher/abstract/"

        self.setup_styles()
        self.create_widgets()

    def setup_styles(self):
        if not HAS_TTKBOOTSTRAP:
            style = ttk.Style()
            style.theme_use("clam")
            style.configure("Header.TFrame", background="#0d6efd")
            style.configure("Header.TLabel", background="#0d6efd", foreground="white", font=("Segoe UI", 14, "bold"))
            style.configure("SubHeader.TLabel", background="#0d6efd", foreground="#e0e0e0", font=("Segoe UI", 9))

    def create_widgets(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(3, weight=1)

        # HEADER
        header_frame = ttk.Frame(self.root, style="Header.TFrame", padding=15)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(header_frame, text="AbstractFetch", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header_frame,
            text="Automated Abstract Downloader & Bibliographic Catalog Organizer",
            style="SubHeader.TLabel",
        ).grid(row=1, column=0, sticky="w")

        ttk.Button(header_frame, text="DB Settings", command=self.open_db_settings).grid(
            row=0, column=1, rowspan=2, sticky="e", padx=5
        )

        # CONTROLS
        main_container = ttk.Frame(self.root, padding=15)
        main_container.grid(row=1, column=0, sticky="ew")
        main_container.columnconfigure(1, weight=1)

        ttk.Label(main_container, text="Save Directory:", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="w", pady=5
        )
        self.ent_outdir = ttk.Entry(main_container)
        self.ent_outdir.insert(0, os.path.abspath("./Organized_Thesis_Records"))
        self.ent_outdir.grid(row=0, column=1, sticky="ew", padx=10, pady=5)

        ttk.Button(main_container, text="Browse...", command=self.browse_directory).grid(
            row=0, column=2, sticky="e", pady=5
        )

        ttk.Label(main_container, text="Filter by College:", font=("Segoe UI", 9, "bold")).grid(
            row=1, column=0, sticky="w", pady=5
        )

        college_frame = ttk.Frame(main_container)
        college_frame.grid(row=1, column=1, sticky="ew", padx=10, pady=5)
        college_frame.columnconfigure(0, weight=1)

        self.cbo_college = ttk.Combobox(college_frame, state="readonly")
        self.cbo_college.set("ALL COLLEGES (All Records)")
        self.cbo_college.grid(row=0, column=0, sticky="ew")

        ttk.Button(college_frame, text="Load Colleges", command=self.fetch_colleges_list).grid(
            row=0, column=1, padx=(5, 0)
        )

        ttk.Label(main_container, text="Throttle Delay (sec):", font=("Segoe UI", 9, "bold")).grid(
            row=2, column=0, sticky="w", pady=5
        )
        self.spin_delay = ttk.Spinbox(main_container, from_=0.1, to=10.0, increment=0.5, width=8)
        self.spin_delay.set(0.5)
        self.spin_delay.grid(row=2, column=1, sticky="w", padx=10, pady=5)

        # PROGRESS CARD
        prog_frame = ttk.LabelFrame(self.root, text=" Download Progress ", padding=15)
        prog_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=5)
        prog_frame.columnconfigure(0, weight=1)

        self.lbl_status = ttk.Label(
            prog_frame, text="Ready. Click 'Load Colleges' or 'Start' to begin.", font=("Segoe UI", 9, "bold")
        )
        self.lbl_status.grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.progress_bar = ttk.Progressbar(prog_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=5)

        self.lbl_counter = ttk.Label(prog_frame, text="Processed: 0 / 0 records", font=("Segoe UI", 8))
        self.lbl_counter.grid(row=2, column=0, sticky="e")

        # LOG CONSOLE (FORCED BLACK BG & MARINE GREEN TEXT OVERRIDE)
        log_frame = ttk.LabelFrame(self.root, text=" Live Activity Console ", padding=10)
        log_frame.grid(row=3, column=0, sticky="nsew", padx=15, pady=5)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.txt_log = tk.Text(
            log_frame,
            height=8,
            wrap="word",
            font=("Consolas", 9, "bold"),
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
        )
        # Force explicit background and foreground overriding ttkbootstrap themes
        self.txt_log.config(
            bg="#000000",
            fg="#4C9A2A",
            insertbackground="#4C9A2A",
            selectbackground="#1e3a1e",
            selectforeground="#ffffff",
            background="#000000",
            foreground="#4C9A2A"
        )
        self.txt_log.tag_configure("green_text", foreground="#4C9A2A", background="#000000")
        self.txt_log.tag_configure("red_text", foreground="#FF4D4D", background="#000000")
        self.txt_log.configure(state="disabled")

        scrollbar = ttk.Scrollbar(log_frame, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scrollbar.set)
        self.txt_log.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # ACTION BUTTONS
        btn_frame = ttk.Frame(self.root, padding=15)
        btn_frame.grid(row=4, column=0, sticky="ew")

        self.btn_stop = ttk.Button(btn_frame, text="Stop Download", command=self.stop_process, state="disabled")
        self.btn_stop.pack(side="right", padx=5)

        self.btn_start = ttk.Button(
            btn_frame, text="Start Abstract Downloader", command=self.start_process_thread
        )
        self.btn_start.pack(side="right", padx=5)

    def open_db_settings(self):
        DatabaseSettingsDialog(self.root, self.db_config)

    def browse_directory(self):
        folder = filedialog.askdirectory()
        if folder:
            self.ent_outdir.delete(0, tk.END)
            self.ent_outdir.insert(0, folder)

    def log_msg(self, message, tag="green_text"):
        self.txt_log.configure(state="normal")
        self.txt_log.insert(tk.END, message + "\n", tag)
        self.txt_log.see(tk.END)
        self.txt_log.configure(state="disabled")

    def fetch_colleges_list(self):
        def _fetch():
            try:
                self.log_msg("--> Fetching College list...")
                db = mysql.connector.connect(**self.db_config)
                cursor = db.cursor()

                query = """
                    SELECT DISTINCT COALESCE(c.name, br.college, 'Uncategorized') AS college_name
                    FROM bibliographic_record br
                    LEFT JOIN department d ON br.department = d.id
                    LEFT JOIN colleges c ON d.collegeid = c.id
                    HAVING college_name IS NOT NULL AND college_name != ''
                    ORDER BY college_name ASC
                """
                cursor.execute(query)
                rows = cursor.fetchall()
                colleges = [r[0].strip() for r in rows if r[0] and r[0].strip()]

                cursor.close()
                db.close()

                dropdown_values = ["ALL COLLEGES (All Records)"] + colleges
                self.cbo_college["values"] = dropdown_values
                self.cbo_college.current(0)
                self.log_msg(f"Loaded {len(colleges)} colleges successfully!")
            except Exception as e:
                self.log_msg(f"Error fetching colleges: {str(e)}", tag="red_text")
                messagebox.showerror("Database Error", f"Could not fetch colleges:\n{str(e)}")

        threading.Thread(target=_fetch, daemon=True).start()

    def stop_process(self):
        if self.is_running:
            self.stop_requested = True
            self.lbl_status.configure(text="Stopping process... cleaning up.")
            self.log_msg("Stop requested by user.")

    def start_process_thread(self):
        self.stop_requested = False
        self.is_running = True
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        threading.Thread(target=self.run_downloader_process, daemon=True).start()

    def fetch_abstract_file(self, record_id, raw_filename, target_path, delay_sec):
        # 1. LOCAL DISK SEARCH
        if os.path.exists(self.local_abstract_storage):
            pattern = os.path.join(self.local_abstract_storage, f"{record_id}[_-]*")
            matches = glob.glob(pattern)

            if matches and os.path.isfile(matches[0]):
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(matches[0], target_path)
                return f"Local Disk Copy ({os.path.basename(matches[0])})"

        # 2. HTTP FALLBACK
        if not raw_filename or str(raw_filename).strip() == "":
            return "No File Record in DB"

        filename = str(raw_filename).strip()
        encoded_filename = urllib.parse.quote(filename)
        download_url = f"{self.base_url}{encoded_filename}"

        time.sleep(delay_sec)
        if self.stop_requested:
            return "Cancelled"

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/pdf,*/*",
        })

        try:
            response = session.get(download_url, timeout=15, stream=True)
            if response.status_code == 200:
                if "application/json" in response.headers.get("Content-Type", ""):
                    return "HTTP 404 (Missing on Server Disk)"

                with open(target_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self.stop_requested:
                            return "Cancelled"
                        f.write(chunk)
                return "Downloaded via HTTP"
            return f"HTTP {response.status_code}"
        except Exception as e:
            return f"Error: {str(e)}"

    def generate_batch_validators(self, base_out_dir, college_folders):
        for college in college_folders:
            college_dir = os.path.join(base_out_dir, college)
            local_vbs_path = os.path.join(college_dir, f"validate_{college}.vbs")
            local_vbs_content = (
                'Set objFSO = CreateObject("Scripting.FileSystemObject")\n'
                'Set objShell = CreateObject("WScript.Shell")\n'
                "strCurrentFolder = objShell.CurrentDirectory\n\n"
                "intTotal = 0\nintMissing = 0\nintFound = 0\n\n"
                "Set folder = objFSO.GetFolder(strCurrentFolder)\n\n"
                "For Each subfolder In folder.SubFolders\n"
                '    If Left(subfolder.Name, 7) = "Record_" Then\n'
                "        intTotal = intTotal + 1\n"
                "        boolPdfFound = False\n"
                "        For Each file In subfolder.Files\n"
                '            If LCase(objFSO.GetExtensionName(file.Name)) = "pdf" Then\n'
                "                boolPdfFound = True\n"
                "                Exit For\n"
                "            End If\n"
                "        Next\n"
                "        If boolPdfFound Then\n"
                "            intFound = intFound + 1\n"
                "        Else\n"
                "            intMissing = intMissing + 1\n"
                "        End If\n"
                "    End If\n"
                "Next\n\n"
                f'strMsg = "LOCAL CATALOG AUDIT FOR [{college}]" & vbCrLf\n'
                'strMsg = strMsg & "==========================================" & vbCrLf\n'
                'strMsg = strMsg & "Total Record Folders : " & intTotal & vbCrLf\n'
                'strMsg = strMsg & "PDFs Intact (Found)  : " & intFound & vbCrLf\n'
                'strMsg = strMsg & "PDFs Missing         : " & intMissing & vbCrLf & vbCrLf\n\n'
                "If intMissing > 0 Then\n"
                f'    strMsg = strMsg & "WARNING: " & intMissing & " record(s) are missing PDF files!" & vbCrLf\n'
                f'    strMsg = strMsg & "Please check {college}_missing_abstracts_log.txt"\n'
                f'    MsgBox strMsg, 48, "Validation Warning - [{college}]"\n'
                "Else\n"
                '    strMsg = strMsg & "SUCCESS: All record folders contain valid PDF abstracts!"\n'
                f'    MsgBox strMsg, 64, "Validation Passed - [{college}]"\n'
                "End If\n"
            )
            with open(local_vbs_path, "w", encoding="utf-8") as f:
                f.write(local_vbs_content)

        master_vbs_path = os.path.join(base_out_dir, "VALIDATE_ALL_COLLEGES.vbs")
        master_vbs_content = (
            'Set objFSO = CreateObject("Scripting.FileSystemObject")\n'
            'Set objShell = CreateObject("WScript.Shell")\n'
            "strCurrentFolder = objShell.CurrentDirectory\n\n"
            "intGrandTotal = 0\nintGrandMissing = 0\nintGrandFound = 0\nstrBreakdown = \"\"\n\n"
            "Set rootFolder = objFSO.GetFolder(strCurrentFolder)\n\n"
            "For Each collegeFolder In rootFolder.SubFolders\n"
            "    intCollegeTotal = 0\nintCollegeFound = 0\nintCollegeMissing = 0\n"
            "    For Each recFolder In collegeFolder.SubFolders\n"
            '        If Left(recFolder.Name, 7) = "Record_" Then\n'
            "            intCollegeTotal = intCollegeTotal + 1\n"
            "            boolPdfFound = False\n"
            "            For Each file In recFolder.Files\n"
            '                If LCase(objFSO.GetExtensionName(file.Name)) = "pdf" Then\n'
            "                    boolPdfFound = True\n"
            "                    Exit For\n"
            "                End If\n"
            "            Next\n"
            "            If boolPdfFound Then\n"
            "                intCollegeFound = intCollegeFound + 1\n"
            "            Else\n"
            "                intCollegeMissing = intCollegeMissing + 1\n"
            "            End If\n"
            "        End If\n"
            "    Next\n"
            "    If intCollegeTotal > 0 Then\n"
            "        intGrandTotal = intGrandTotal + intCollegeTotal\n"
            "        intGrandFound = intGrandFound + intCollegeFound\n"
            "        intGrandMissing = intGrandMissing + intCollegeMissing\n"
            "        If intCollegeMissing > 0 Then\n"
            '            strBreakdown = strBreakdown & "  - " & collegeFolder.Name & ": " & intCollegeMissing & " MISSING (" & intCollegeFound & "/" & intCollegeTotal & " intact)" & vbCrLf\n'
            "        Else\n"
            '            strBreakdown = strBreakdown & "  - " & collegeFolder.Name & ": OK (" & intCollegeFound & "/" & intCollegeTotal & " intact)" & vbCrLf\n'
            "        End If\n"
            "    End If\n"
            "Next\n\n"
            'strMsg = "MASTER INSTITUTIONAL THESIS CATALOG AUDIT" & vbCrLf\n'
            'strMsg = strMsg & "==========================================" & vbCrLf\n'
            'strMsg = strMsg & "Total Record Folders Checked : " & intGrandTotal & vbCrLf\n'
            'strMsg = strMsg & "Total PDFs Intact (Found)   : " & intGrandFound & vbCrLf\n'
            'strMsg = strMsg & "Total PDFs Missing          : " & intGrandMissing & vbCrLf & vbCrLf\n'
            'strMsg = strMsg & "COLLEGE BREAKDOWN:" & vbCrLf\n'
            'strMsg = strMsg & "------------------------------------------" & vbCrLf\n'
            'strMsg = strMsg & strBreakdown & vbCrLf\n\n'
            "If intGrandMissing > 0 Then\n"
            '    strMsg = strMsg & "WARNING: Please review missing_abstracts_log.txt inside affected folders."\n'
            '    MsgBox strMsg, 48, "Master Audit Warning"\n'
            "Else\n"
            '    strMsg = strMsg & "SUCCESS: All record folders contain valid PDF abstracts!"\n'
            '    MsgBox strMsg, 64, "Master Audit Passed"\n'
            "End If\n"
        )
        with open(master_vbs_path, "w", encoding="utf-8") as f:
            f.write(master_vbs_content)

    def run_downloader_process(self):
        out_dir = self.ent_outdir.get().strip()
        delay_sec = float(self.spin_delay.get())
        selected_college_choice = self.cbo_college.get().strip()

        os.makedirs(out_dir, exist_ok=True)
        self.log_msg(f"--> Connecting to Database ({self.db_config['host']})...")

        try:
            db = mysql.connector.connect(**self.db_config)
            cursor = db.cursor(dictionary=True)

            base_query = """
                SELECT 
                    br.id AS Record_ID,
                    br.BibID,
                    COALESCE(a.fullname, br.author) AS Author_Name,
                    COALESCE(c.name, br.college, 'Uncategorized') AS College_Code,
                    c.description AS College_Name,
                    COALESCE(d.description, br.department) AS Department_Name,
                    br.title AS Title,
                    br.link AS Abstract_Filename
                FROM bibliographic_record br
                LEFT JOIN authority a ON br.author_id = a.id
                LEFT JOIN department d ON br.department = d.id
                LEFT JOIN colleges c ON d.collegeid = c.id
            """

            if "ALL COLLEGES" in selected_college_choice or not selected_college_choice:
                cursor.execute(base_query)
            else:
                filtered_query = base_query + " WHERE COALESCE(c.name, br.college, 'Uncategorized') = %s"
                cursor.execute(filtered_query, (selected_college_choice,))

            records = cursor.fetchall()
            total_records = len(records)

            self.log_msg(f"--> Found {total_records} records for '{selected_college_choice}'.")
            self.progress_bar["maximum"] = total_records

            college_catalog_data = {}
            college_missing_data = {}

            for idx, row in enumerate(records, 1):
                if self.stop_requested:
                    self.log_msg("Process cancelled by user.")
                    break

                rec_id = row["Record_ID"]
                author_raw = row["Author_Name"]
                college_raw = row.get("College_Code")

                author_clean = sanitize_folder_name(author_raw)
                college_clean = sanitize_folder_name(college_raw)

                if college_clean not in college_catalog_data:
                    college_catalog_data[college_clean] = []
                    college_missing_data[college_clean] = []

                self.progress_bar["value"] = idx
                self.lbl_counter.configure(text=f"Processed: {idx} / {total_records} records")
                self.lbl_status.configure(text=f"[{college_clean}] Processing ID {rec_id}: {author_clean}")

                college_dir = os.path.join(out_dir, college_clean)
                record_folder_name = f"Record_{rec_id}_{author_clean}"
                record_dir = os.path.join(college_dir, record_folder_name)
                os.makedirs(record_dir, exist_ok=True)

                abstract_filename = row.get("Abstract_Filename")
                pdf_filename = f"{author_clean}_Abstract.pdf"
                abstract_dest = os.path.join(record_dir, pdf_filename)

                abstract_status = self.fetch_abstract_file(rec_id, abstract_filename, abstract_dest, delay_sec)

                if abstract_status == "Cancelled":
                    break

                relative_pdf_path = os.path.join(record_folder_name, pdf_filename).replace("\\", "/")
                file_exists_locally = os.path.exists(abstract_dest) and os.path.getsize(abstract_dest) > 0

                if not file_exists_locally:
                    missing_info = f"[Record ID: {rec_id}] Missing ABSTRACT | Author: {author_raw} | Status: {abstract_status}"
                    college_missing_data[college_clean].append(missing_info)
                    self.log_msg(f"  [MISSING] ID #{rec_id} ({author_raw}): {abstract_status}", tag="red_text")
                else:
                    self.log_msg(f"  [OK] ID #{rec_id} ({author_raw}): {abstract_status}")

                row_log = dict(row)
                row_log["college_folder"] = college_clean
                row_log["abstract_status"] = abstract_status
                row_log["local_folder_path"] = (
                    f'=HYPERLINK("{relative_pdf_path}", "Open File")'
                    if file_exists_locally
                    else f'=HYPERLINK("{relative_pdf_path}", "File Missing")'
                )

                college_catalog_data[college_clean].append(row_log)

            # Generate Outputs
            self.log_msg("\n--> Generating Excel Catalogs and Validators...")
            for c_folder, c_records in college_catalog_data.items():
                target_college_dir = os.path.join(out_dir, c_folder)
                os.makedirs(target_college_dir, exist_ok=True)

                # Missing Log
                txt_path = os.path.join(target_college_dir, f"{c_folder}_missing_abstracts_log.txt")
                with open(txt_path, "w", encoding="utf-8") as log_f:
                    log_f.write(f"=== MISSING ABSTRACTS REPORT FOR {c_folder} ===\n\n")
                    for item in college_missing_data.get(c_folder, []):
                        log_f.write(item + "\n")

                # Excel File
                if c_records:
                    excel_path = os.path.join(target_college_dir, f"{c_folder}_thesis_bibliographic_catalog.xlsx")
                    df = pd.DataFrame(c_records)
                    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                        df.to_excel(writer, sheet_name="Catalog", index=False)

            self.generate_batch_validators(out_dir, list(college_catalog_data.keys()))

            cursor.close()
            db.close()

            self.lbl_status.configure(text="Abstract Processing Complete!")
            self.log_msg("\nSUCCESS! Processing Finished.")
            messagebox.showinfo("Done", "Process completed successfully!")

        except Exception as err:
            self.log_msg(f"ERROR: {str(err)}", tag="red_text")
            messagebox.showerror("Error", f"An error occurred:\n{str(err)}")
        finally:
            self.is_running = False
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")


if __name__ == "__main__":
    if HAS_TTKBOOTSTRAP:
        try:
            root = ttk_bs.Window(themename="flatly")
        except Exception:
            root = ttk_bs.Window()
    else:
        root = tk.Tk()
    app = ThesisDownloaderApp(root)
    root.mainloop()