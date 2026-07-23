import os
import sys
import time
import json
import threading
import psycopg2
import customtkinter as ctk
from tkinter import messagebox
from tabulate import tabulate

# ---------------------------------------------------------
# THEMING & PREDEFINED CONFIGURATION
# ---------------------------------------------------------
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

DB_CONFIG = {
    "dbname": "aupdb",
    "user": "jldmlibstat",
    "password": "JLuAmD@7191",
    "host": "172.17.18.30",
    "port": "5432"
}

GRANTEE_USER = "jldmlibstat"
OUTPUT_DIR = r"C:\Users\Administrator\Downloads\SQL_Exports"
HISTORY_FILE = os.path.join(OUTPUT_DIR, "export_history.json")

CHUNK_SIZE = 50000
BATCH_SIZE = 500


# ---------------------------------------------------------
# MAIN DESKTOP GUI APPLICATION
# ---------------------------------------------------------
class AUPDBExtractorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AUPDB Extractor - Desktop Studio")
        self.geometry("1000x650")
        self.minsize(800, 500)
        self.resizable(True, True)

        self.history = self.load_history()
        self.table_map = {}

        self.setup_ui()
        self.after(100, self.check_db_connection_on_load)

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- HEADER PANEL ---
        header_frame = ctk.CTkFrame(self, corner_radius=10)
        header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 10))
        header_frame.grid_columnconfigure(0, weight=1)

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="AUPDB Extractor",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        title_lbl.grid(row=0, column=0, sticky="w", padx=15, pady=12)

        host_badge = ctk.CTkLabel(
            header_frame,
            text=f"Server: {DB_CONFIG['host']}",
            fg_color="#1f2937",
            text_color="#10b981",
            corner_radius=6,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        host_badge.grid(row=0, column=1, sticky="e", padx=15, pady=12)

        # --- MAIN CONTAINER (2 COLUMNS) ---
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))

        main_container.grid_columnconfigure(0, weight=1)  # Controls
        main_container.grid_columnconfigure(1, weight=3)  # Console (wider)
        main_container.grid_rowconfigure(0, weight=1)

        # --- LEFT COLUMN: CONTROLS ---
        left_col = ctk.CTkFrame(main_container, corner_radius=10)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)

        ctrl_title = ctk.CTkLabel(
            left_col,
            text="Export Controls",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        ctrl_title.pack(anchor="w", padx=15, pady=(15, 10))

        dropdown_lbl = ctk.CTkLabel(left_col, text="Select Table to Action:", font=ctk.CTkFont(size=12))
        dropdown_lbl.pack(anchor="w", padx=15, pady=(5, 0))

        self.table_dropdown = ctk.CTkOptionMenu(
            left_col,
            values=["Connecting to DB..."],
            height=38,
            dynamic_resizing=False
        )
        self.table_dropdown.pack(fill="x", padx=15, pady=(5, 15))

        path_lbl = ctk.CTkLabel(left_col, text="Target Output Path:", font=ctk.CTkFont(size=12))
        path_lbl.pack(anchor="w", padx=15, pady=(5, 0))

        path_entry = ctk.CTkEntry(left_col, height=35)
        path_entry.insert(0, OUTPUT_DIR)
        path_entry.configure(state="readonly")
        path_entry.pack(fill="x", padx=15, pady=(5, 20))

        # Terminal Preview Button
        self.btn_preview = ctk.CTkButton(
            left_col,
            text="VIEW IN TERMINAL (20 ROWS)",
            height=40,
            fg_color="#374151",
            hover_color="#4b5563",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.fetch_terminal_preview_thread
        )
        self.btn_preview.pack(fill="x", padx=15, pady=(0, 10))

        # Start Export Button
        self.btn_export = ctk.CTkButton(
            left_col,
            text="START EXPORT",
            height=45,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_export_thread
        )
        self.btn_export.pack(fill="x", padx=15, pady=(5, 15))

        # --- RIGHT COLUMN: TERMINAL CONSOLE ---
        right_col = ctk.CTkFrame(main_container, corner_radius=10)
        right_col.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        right_col.grid_columnconfigure(0, weight=1)
        right_col.grid_rowconfigure(2, weight=1)

        console_title = ctk.CTkLabel(
            right_col,
            text="Activity Log & Data Terminal",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        console_title.grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(right_col, height=12, progress_color="#10b981")
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))

        # Marine Green Console Box (Disable wrap for clean ASCII alignment)
        self.console = ctk.CTkTextbox(
            right_col,
            fg_color="#050a0e",
            text_color="#12d58a",
            font=ctk.CTkFont(family="Consolas", size=12),
            corner_radius=8,
            wrap="none"  # Horizontal scroll enabled for wide tables!
        )
        self.console.grid(row=2, column=0, sticky="nsew", padx=15, pady=(0, 15))

        self.log("[SYSTEM INITIALIZED] Desktop GUI environment loaded.")

    # ---------------------------------------------------------
    # HELPER LOGGING & HISTORY
    # ---------------------------------------------------------
    def log(self, text):
        timestamp = time.strftime("[%H:%M:%S]")
        self.console.insert("end", f"{timestamp} {text}\n")
        self.console.see("end")

    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_history(self):
        try:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            with open(HISTORY_FILE, "w") as f:
                json.dump(self.history, f, indent=4)
        except Exception:
            pass

    # ---------------------------------------------------------
    # HIGH-SPEED TERMINAL TABLE PREVIEW ENGINE
    # ---------------------------------------------------------
    def fetch_terminal_preview_thread(self):
        selected_option = self.table_dropdown.get()
        if selected_option in ["Connecting to DB...", "-- EXPORT ALL TABLES --"]:
            messagebox.showwarning("Selection Required",
                                   "Please select a specific table from the dropdown to preview data.")
            return

        self.btn_preview.configure(state="disabled", text="FETCHING DATA...")
        threading.Thread(target=self.print_terminal_preview, args=(selected_option,), daemon=True).start()

    def print_terminal_preview(self, selected_option):
        schema_name, table_name = self.table_map[selected_option]
        full_table_name = f'"{schema_name}"."{table_name}"'

        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                # Fetch first 20 records for light & instant rendering
                cur.execute(f"SELECT * FROM {full_table_name} LIMIT 20;")
                colnames = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
            conn.close()

            # Truncate long cell values to keep terminal tidy
            clean_rows = []
            for row in rows:
                clean_row = []
                for val in row:
                    str_val = str(val) if val is not None else "NULL"
                    if len(str_val) > 25:
                        str_val = str_val[:22] + "..."
                    clean_row.append(str_val)
                clean_rows.append(clean_row)

            # Format into clean ASCII Table using tabulate
            table_ascii = tabulate(clean_rows, headers=colnames, tablefmt="psql")

            self.log(f"\n--- DATA PREVIEW: {full_table_name} (FIRST 20 ROWS) ---")
            self.console.insert("end", f"{table_ascii}\n\n")
            self.console.see("end")

        except Exception as e:
            self.log(f"ERROR: Preview failed for {full_table_name} - {str(e)}")
            messagebox.showerror("Preview Error", str(e))

        finally:
            self.btn_preview.configure(state="normal", text="VIEW IN TERMINAL (20 ROWS)")

    # ---------------------------------------------------------
    # DEFENSIVE DB CHECK ON LOAD
    # ---------------------------------------------------------
    def check_db_connection_on_load(self):
        try:
            conn = psycopg2.connect(**DB_CONFIG, connect_timeout=3)
            query = """
                SELECT table_schema, table_name
                FROM information_schema.table_privileges
                WHERE grantee = %s
                GROUP BY table_schema, table_name
                ORDER BY table_schema, table_name;
            """
            with conn.cursor() as cur:
                cur.execute(query, (GRANTEE_USER,))
                tables = cur.fetchall()
            conn.close()

            options = ["-- EXPORT ALL TABLES --"]
            self.table_map = {}
            for schema, tbl in tables:
                display_name = f"{schema}.{tbl}"
                options.append(display_name)
                self.table_map[display_name] = (schema, tbl)

            self.table_dropdown.configure(values=options)
            self.table_dropdown.set(options[0])
            self.log(f"Connected to PostgreSQL. Loaded {len(tables)} accessible tables.")

        except Exception as e:
            self.log("ERROR: Unable to reach PostgreSQL database.")
            messagebox.showerror(
                "Database Connection Failed",
                f"Unable to establish connection to PostgreSQL Server.\n\n"
                f"Host IP: 172.17.18.30\n"
                f"Error Details:\n{str(e)}\n\n"
                f"Please verify network connectivity or run this application on the server."
            )

    # ---------------------------------------------------------
    # THREADED EXPORT WORKER
    # ---------------------------------------------------------
    def start_export_thread(self):
        selected_option = self.table_dropdown.get()
        if selected_option == "Connecting to DB...":
            messagebox.showwarning("Warning", "Database is not connected.")
            return

        self.btn_export.configure(state="disabled", text="EXPORTING...")
        threading.Thread(target=self.run_export, args=(selected_option,), daemon=True).start()

    def run_export(self, selected_option):
        if selected_option == "-- EXPORT ALL TABLES --":
            tables_to_export = list(self.table_map.values())
        else:
            tables_to_export = [self.table_map[selected_option]]

        try:
            conn = psycopg2.connect(**DB_CONFIG)
            self.log("Database connection established.")

            for schema_name, table_name in tables_to_export:
                full_table_name = f'"{schema_name}"."{table_name}"'
                table_key = f"{schema_name}.{table_name}"
                output_file = os.path.join(OUTPUT_DIR, f"{schema_name}_{table_name}_dump.sql")
                start_time = time.time()

                self.log("-----------------------------------------")
                self.log(f"Exporting: {full_table_name}")

                with conn.cursor() as temp_cur:
                    temp_cur.execute(f"SELECT * FROM {full_table_name} LIMIT 1;")
                    columns = ", ".join([f'"{desc[0]}"' for desc in temp_cur.description])

                    temp_cur.execute(f"SELECT COUNT(*) FROM {full_table_name};")
                    current_rows = temp_cur.fetchone()[0]

                prev_rows = self.history.get(table_key, None)
                if prev_rows is not None:
                    growth = current_rows - prev_rows
                    growth_str = f"+{growth:,}" if growth >= 0 else f"{growth:,}"
                    self.log(f"Total Rows: {current_rows:,} | Growth: {growth_str} rows")
                else:
                    self.log(f"Total Rows: {current_rows:,} (First export)")

                if current_rows == 0:
                    self.log("Table is empty. Skipping...")
                    continue

                stream_cursor = conn.cursor(name="desktop_stream_cursor")
                stream_cursor.execute(f"SELECT * FROM {full_table_name};")

                total_extracted = 0
                batch_count = 0
                os.makedirs(OUTPUT_DIR, exist_ok=True)

                with open(output_file, "w", encoding="utf-8") as f:
                    while True:
                        rows = stream_cursor.fetchmany(CHUNK_SIZE)
                        if not rows:
                            break

                        for i in range(0, len(rows), BATCH_SIZE):
                            batch = rows[i:i + BATCH_SIZE]
                            args_str = b",\n  ".join(
                                stream_cursor.mogrify("(" + "%s," * (len(batch[0]) - 1) + "%s)", row)
                                for row in batch
                            ).decode('utf-8', errors='replace')

                            f.write(f"INSERT INTO {full_table_name} ({columns}) VALUES\n  {args_str};\n\n")
                            batch_count += 1

                        total_extracted += len(rows)
                        progress = total_extracted / current_rows
                        self.progress_bar.set(progress)

                        file_mb = os.path.getsize(output_file) / (1024 * 1024)
                        self.log(
                            f"Extracted {total_extracted:,} / {current_rows:,} ({progress * 100:.1f}%) | {file_mb:.1f} MB")

                stream_cursor.close()
                self.history[table_key] = current_rows
                self.save_history()

                elapsed = (time.time() - start_time) / 60
                self.log(f"Finished {schema_name}.{table_name} in {elapsed:.2f} mins.")

            conn.close()
            self.log("ALL EXPORT TASKS COMPLETED SUCCESSFULLY.")

        except Exception as e:
            self.log(f"ERROR: {str(e)}")

        finally:
            self.btn_export.configure(state="normal", text="START EXPORT")


if __name__ == "__main__":
    app = AUPDBExtractorApp()
    app.mainloop()