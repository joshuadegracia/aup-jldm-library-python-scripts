from datetime import datetime
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox

# --- Pure Python MySQL/MariaDB Driver Fallback ---
try:
    import mysql.connector as mariadb
    from mysql.connector import plugins
except ImportError:
    pass

import openpyxl
from openpyxl.styles import Alignment, Border, Font, Side
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.widgets import DateEntry

# --- Database Connection Settings ---
DB_CONFIG = {
    "host": "192.168.2.104",
    "port": 3308,
    "user": "root",
    "password": "@dm!N2026",
    "database": "jldmlibrary_stat",
    "use_pure": True,  # FORCE Pure-Python implementation (Fixes missing DLL / native password plugin error in PyInstaller .exe)
}


def fetch_sections():
    """Dynamically fetches active sections for the Area dropdown."""
    query = """
        SELECT id, name 
        FROM jldmlibrary_sections 
        WHERE is_active = 1 AND (is_deleted IS NULL OR is_deleted = 0)
        ORDER BY id ASC;
    """
    sections = {}
    try:
        conn = mariadb.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(query)
        for sec_id, name in cursor.fetchall():
            sections[name] = sec_id
        conn.close()
    except Exception as e:
        messagebox.showerror("Database Error", f"Failed to fetch sections:\n{e}")
    return sections


def fetch_date_bounds(section_id):
    """Pulls the MIN and MAX dates present in usage_logs for the selected section."""
    query = """
        SELECT MIN(date), MAX(date) 
        FROM usage_logs 
        WHERE section_id = %s 
          AND (is_deleted IS NULL OR is_deleted = 0);
    """
    try:
        conn = mariadb.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(query, (section_id,))
        row = cursor.fetchone()
        conn.close()

        if row and row[0] and row[1]:
            d_min = (
                row[0]
                if isinstance(row[0], datetime)
                else datetime.strptime(str(row[0]), "%Y-%m-%d")
            )
            d_max = (
                row[1]
                if isinstance(row[1], datetime)
                else datetime.strptime(str(row[1]), "%Y-%m-%d")
            )
            return d_min.date(), d_max.date()
    except Exception:
        pass

    today = datetime.now().date()
    return datetime(2023, 8, 1).date(), today


def fetch_report_data(section_id, start_date, end_date):
    """Pulls entity codes and aggregated counts from MariaDB."""
    query = """
        SELECT 
            entity, 
            COUNT(*) AS total_count
        FROM usage_logs
        WHERE section_id = %s
          AND date BETWEEN %s AND %s
          AND (is_deleted IS NULL OR is_deleted = 0)
        GROUP BY entity
        ORDER BY entity ASC;
    """

    students = []
    employees = []

    try:
        conn = mariadb.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(query, (section_id, start_date, end_date))
        rows = cursor.fetchall()
        conn.close()

        for entity_code, count in rows:
            if not entity_code:
                continue

            if entity_code.upper() in ["FAC", "STAFF"]:
                employees.append((entity_code, count))
            else:
                students.append((entity_code, count))

    except Exception as e:
        messagebox.showerror("Database Error", f"Query Execution Failed:\n{e}")

    return students, employees


def format_dynamic_date_range(start_str, end_str):
    """Formats date range (e.g., 'August 2023 to July 2026')."""
    try:
        d1 = datetime.strptime(start_str, "%Y-%m-%d")
        d2 = datetime.strptime(end_str, "%Y-%m-%d")
        if d1.year == d2.year:
            return f"{d1.strftime('%B')} to {d2.strftime('%B %Y')}"
        return f"{d1.strftime('%B %Y')} to {d2.strftime('%B %Y')}"
    except ValueError:
        return f"{start_str} to {end_str}"


def sanitize_with_underscores(name):
    """Replaces non-alphanumeric chars with underscores."""
    cleaned = re.sub(r"[^a-zA-Z0-9]", "_", name)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_")


def create_underscore_tab_name(section_name):
    """Creates an underscore-only tab name (max 31 chars for Excel)."""
    clean_sec = sanitize_with_underscores(section_name)
    clean_sec = clean_sec.replace("JLDM_Lib_", "").replace("JLDM_Lib", "")

    suffix = "_Stats"
    max_len = 31 - len(suffix)

    if len(clean_sec) > max_len:
        clean_sec = clean_sec[:max_len].strip("_")

    return f"{clean_sec}{suffix}"


class LibraryReportApp:

    def __init__(self, root):
        self.root = root
        self.root.title("JLDM Library Statistics Report")
        self.root.geometry("680x800")
        self.root.configure(bg="#0F171E")

        # Fetch sections from DB
        self.sections_map = fetch_sections()

        # Cache data for Excel export
        self.cached_students = []
        self.cached_employees = []
        self.cached_section_name = ""
        self.cached_date_text = ""

        # --- Top Controls ---
        filter_card = tb.Labelframe(
            root, text=" Report Controls ", bootstyle="info", padding=15
        )
        filter_card.pack(padx=15, pady=10, fill=X)

        # Area Select
        tb.Label(
            filter_card, text="Area:", font=("Helvetica", 10, "bold")
        ).grid(row=0, column=0, padx=5, pady=5, sticky=W)
        self.combo_section = tb.Combobox(
            filter_card,
            values=list(self.sections_map.keys()),
            state="readonly",
            bootstyle="info",
            width=28,
        )

        default_section = (
            "JLDM Lib - Main Entrance"
            if "JLDM Lib - Main Entrance" in self.sections_map
            else (
                list(self.sections_map.keys())[0] if self.sections_map else ""
            )
        )
        self.combo_section.set(default_section)
        self.combo_section.grid(
            row=0, column=1, columnspan=5, padx=5, pady=5, sticky=W
        )
        self.combo_section.bind("<<ComboboxSelected>>", self.on_section_change)

        # Date Pickers
        today_date = datetime.now().date()

        # From Date
        tb.Label(
            filter_card, text="From:", font=("Helvetica", 10, "bold")
        ).grid(row=1, column=0, padx=(5, 2), pady=5, sticky=W)

        self.cal_start = DateEntry(
            filter_card,
            bootstyle="info",
            dateformat="%Y-%m-%d",
            width=12,
            startdate=today_date,
        )
        self.cal_start.grid(row=1, column=1, padx=(0, 2), pady=5, sticky=W)

        btn_today_start = tb.Button(
            filter_card,
            text="Today",
            bootstyle="secondary-outline",
            command=self.set_start_to_today,
            padding=(5, 2),
        )
        btn_today_start.grid(row=1, column=2, padx=(2, 10), pady=5, sticky=W)

        # To Date
        tb.Label(
            filter_card, text="To:", font=("Helvetica", 10, "bold")
        ).grid(row=1, column=3, padx=(5, 2), pady=5, sticky=W)

        self.cal_end = DateEntry(
            filter_card,
            bootstyle="info",
            dateformat="%Y-%m-%d",
            width=12,
            startdate=today_date,
        )
        self.cal_end.grid(row=1, column=4, padx=(0, 2), pady=5, sticky=W)

        btn_today_end = tb.Button(
            filter_card,
            text="Today",
            bootstyle="secondary-outline",
            command=self.set_end_to_today,
            padding=(5, 2),
        )
        btn_today_end.grid(row=1, column=5, padx=(2, 5), pady=5, sticky=W)

        # Action Buttons
        btn_frame = tb.Frame(filter_card)
        btn_frame.grid(row=2, column=0, columnspan=6, pady=(10, 0), sticky=EW)

        btn_generate = tb.Button(
            btn_frame,
            text="Generate",
            bootstyle="success",
            command=self.update_report,
            width=12,
        )
        btn_generate.pack(side=LEFT, padx=5)

        btn_export = tb.Button(
            btn_frame,
            text="Export to .xlsx",
            bootstyle="info-outline",
            command=self.export_to_excel,
            width=14,
        )
        btn_export.pack(side=LEFT, padx=5)

        # Load date bounds
        self.load_date_bounds()

        # --- SOLID BLACK TERMINAL CONSOLE ---
        terminal_container = tk.Frame(root, bg="#000000", padx=2, pady=2)
        terminal_container.pack(padx=15, pady=(0, 15), fill=BOTH, expand=True)

        scroll_y = tb.Scrollbar(terminal_container, orient=VERTICAL)
        scroll_y.pack(side=RIGHT, fill=Y)

        self.terminal = tk.Text(
            terminal_container,
            bg="#000000",
            fg="#00FF66",
            insertbackground="#00FF66",
            selectbackground="#1F3A2B",
            selectforeground="#00FF66",
            font=("Consolas", 11, "bold"),
            yscrollcommand=scroll_y.set,
            wrap="none",
            bd=0,
            padx=15,
            pady=15,
            highlightthickness=1,
            highlightbackground="#00FF66",
        )
        self.terminal.pack(side=LEFT, fill=BOTH, expand=True)
        scroll_y.config(command=self.terminal.yview)

        # Color Tags
        self.terminal.tag_config("cyan", foreground="#00E5FF")
        self.terminal.tag_config("yellow", foreground="#FFEA00")
        self.terminal.tag_config("white", foreground="#F0F0F0")
        self.terminal.tag_config("green_bold", foreground="#00FF66")
        self.terminal.tag_config("red_bold", foreground="#FF3366")

        self.update_report()

    def set_start_to_today(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        self.cal_start.entry.delete(0, tk.END)
        self.cal_start.entry.insert(0, today_str)

    def set_end_to_today(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        self.cal_end.entry.delete(0, tk.END)
        self.cal_end.entry.insert(0, today_str)

    def load_date_bounds(self):
        sec_name = self.combo_section.get()
        sec_id = self.sections_map.get(sec_name, 100)

        min_d, max_d = fetch_date_bounds(sec_id)

        self.cal_start.entry.delete(0, tk.END)
        self.cal_start.entry.insert(0, min_d.strftime("%Y-%m-%d"))

        self.cal_end.entry.delete(0, tk.END)
        self.cal_end.entry.insert(0, max_d.strftime("%Y-%m-%d"))

    def on_section_change(self, event):
        self.load_date_bounds()
        self.update_report()

    def update_report(self):
        sec_name = self.combo_section.get()
        sec_id = self.sections_map.get(sec_name, 100)

        start_date = self.get_date_str(self.cal_start)
        end_date = self.get_date_str(self.cal_end)

        students, employees = fetch_report_data(sec_id, start_date, end_date)

        # Cache variables for Excel export
        self.cached_students = students
        self.cached_employees = employees
        self.cached_section_name = sec_name
        self.cached_date_text = format_dynamic_date_range(start_date, end_date)

        # Render Terminal Output
        self.render_terminal_output(
            sec_name, self.cached_date_text, students, employees
        )

    def get_date_str(self, date_widget):
        val = date_widget.entry.get().strip()
        try:
            dt = datetime.strptime(val, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return datetime.now().strftime("%Y-%m-%d")

    def render_terminal_output(self, section_name, date_text, students, employees):
        """Renders exact ASCII terminal grid box."""
        self.terminal.config(state="normal")
        self.terminal.delete("1.0", tk.END)

        width = 62
        border = "+" + "-" * (width - 2) + "+\n"

        # Header Block
        self.terminal.insert(tk.END, border, "cyan")
        self.terminal.insert(tk.END, f"| Area: {section_name:<51} |\n", "cyan")
        self.terminal.insert(tk.END, f"| Date: {date_text:<51} |\n", "cyan")
        self.terminal.insert(tk.END, border, "cyan")

        # Student Section Rows
        student_total = 0
        for code, count in students:
            self.terminal.insert(
                tk.END, f"| {code:<45} | {count:>10,} |\n", "white"
            )
            student_total += count

        self.terminal.insert(tk.END, border, "yellow")
        self.terminal.insert(
            tk.END, f"| {'TOTAL':<45} | {student_total:>10,} |\n", "yellow"
        )
        self.terminal.insert(tk.END, border, "yellow")

        # Employee Section Rows
        employee_total = 0
        for code, count in employees:
            self.terminal.insert(
                tk.END, f"| {code:<45} | {count:>10,} |\n", "white"
            )
            employee_total += count

        if employees:
            self.terminal.insert(tk.END, border, "green_bold")
            self.terminal.insert(
                tk.END,
                f"| {'TOTAL':<45} | {employee_total:>10,} |\n",
                "green_bold",
            )
            self.terminal.insert(tk.END, border, "green_bold")

        # Grand Total
        grand_total = student_total + employee_total
        self.terminal.insert(
            tk.END, f"| {'G.TOTAL':<45} | {grand_total:>10,} |\n", "red_bold"
        )
        self.terminal.insert(tk.END, border, "red_bold")

        self.terminal.config(state="disabled")

    def export_to_excel(self):
        """Exports data using underscore formatting for filenames and tab names."""
        if not self.cached_students and not self.cached_employees:
            messagebox.showwarning(
                "Warning", "No report data available to export."
            )
            return

        clean_section = sanitize_with_underscores(self.cached_section_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        default_filename = f"{clean_section}_Library_Report_{timestamp}.xlsx"

        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx")],
            title="Save Library Statistics Report As",
            initialfile=default_filename,
        )

        if not file_path:
            return

        if os.path.isdir(file_path):
            file_path = os.path.join(file_path, default_filename)

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = create_underscore_tab_name(self.cached_section_name)
            ws.views.sheetView[0].showGridLines = True

            font_bold = Font(name="Calibri", size=11, bold=True)
            font_regular = Font(name="Calibri", size=11)

            align_left = Alignment(horizontal="left", vertical="center")
            align_right = Alignment(horizontal="right", vertical="center")

            try:
                border_style = Side(border_style="thin", color="000000")
                thin_border = Border(
                    left=border_style,
                    right=border_style,
                    top=border_style,
                    bottom=border_style,
                )
            except Exception:
                thin_border = None

            def apply_row(
                row_idx,
                col1_val,
                col2_val,
                col3_val,
                bold=False,
                num_format=False,
            ):
                c1 = ws.cell(row=row_idx, column=1, value=col1_val)
                c2 = ws.cell(row=row_idx, column=2, value=col2_val)
                c3 = ws.cell(row=row_idx, column=3, value=col3_val)

                for cell in (c1, c2, c3):
                    if thin_border:
                        cell.border = thin_border
                    cell.font = font_bold if bold else font_regular

                c1.alignment = align_left
                c2.alignment = align_left
                c3.alignment = align_right

                if num_format and isinstance(col3_val, (int, float)):
                    c3.number_format = "#,##0"

            current_r = 1

            # Header Rows
            apply_row(
                current_r, "Area:", self.cached_section_name, "", bold=True
            )
            current_r += 1

            apply_row(current_r, "Date:", self.cached_date_text, "", bold=True)
            current_r += 1

            # Spacer
            apply_row(current_r, "", "", "")
            current_r += 1

            # Students
            student_tot = 0
            for code, count in self.cached_students:
                apply_row(current_r, code, "", count, num_format=True)
                student_tot += count
                current_r += 1

            apply_row(
                current_r, "TOTAL", "", student_tot, bold=True, num_format=True
            )
            current_r += 1

            # Spacer
            apply_row(current_r, "", "", "")
            current_r += 1

            # Employees
            employee_tot = 0
            for code, count in self.cached_employees:
                apply_row(current_r, code, "", count, num_format=True)
                employee_tot += count
                current_r += 1

            if self.cached_employees:
                apply_row(
                    current_r,
                    "TOTAL",
                    "",
                    employee_tot,
                    bold=True,
                    num_format=True,
                )
                current_r += 1

                apply_row(current_r, "", "", "")
                current_r += 1

            # Grand Total
            grand_tot = student_tot + employee_tot
            apply_row(
                current_r, "G.TOTAL", "", grand_tot, bold=True, num_format=True
            )

            # Auto Column Widths
            ws.column_dimensions["A"].width = 35
            ws.column_dimensions["B"].width = 30
            ws.column_dimensions["C"].width = 18

            wb.save(file_path)
            messagebox.showinfo(
                "Export Success",
                f"Report successfully exported to:\n{file_path}",
            )

        except Exception as e:
            messagebox.showerror(
                "Export Error", f"Failed to save Excel file:\n{e}"
            )


if __name__ == "__main__":
    root = tb.Window(themename="darkly")
    app = LibraryReportApp(root)
    root.mainloop()