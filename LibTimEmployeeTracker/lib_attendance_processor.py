import pandas as pd

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
SHEET_ID = "1SaL7lvAb2JqrhLnQR37qKkbpdxJ2aLE00bDJDQ6l5mo"
GID = "0"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"


def parse_duration_to_hours(time_str: str) -> float:
    """Converts a duration string 'HH:MM:SS' into a decimal float (e.g., '04:30:00' -> 4.5)."""
    if pd.isna(time_str) or not isinstance(time_str, str):
        return 0.0

    time_str = time_str.strip()
    if ":" not in time_str:
        return 0.0

    try:
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2]) if len(parts) > 2 else 0
        return round(hours + (minutes / 60.0) + (seconds / 3600.0), 2)
    except ValueError:
        return 0.0


def main():
    print("📥 Loading Google Sheet data...")

    # Skip top 1 row (title row) so the actual headers (Date, Name, IN, etc.) are loaded
    df = pd.read_csv(CSV_URL, skiprows=1)

    # Clean whitespace from column names and string values
    df.columns = df.columns.str.strip()
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str).str.strip()

    # Identify records that are leave/off notices vs normal clock-in records
    leave_mask = df["IN"].str.contains(
        "LEAVE|OFF|S I C K", case=False, na=False
    ) | df["Name"].str.contains("LEAVE|OFF", case=False, na=False)

    df_attendance = df[~leave_mask].copy()
    df_leaves = df[leave_mask].copy()

    # Process duration from total columns (handles both morning & afternoon logouts)
    # The sheet stores first-half duration in 'TOTAL' and full-day total in the 2nd 'TOTAL'
    total_cols = [col for col in df.columns if col.startswith("TOTAL")]

    # Calculate net hours worked per entry
    def calculate_row_hours(row):
        # Priority: Check final total column, else take morning half total
        if len(total_cols) >= 2 and row[total_cols[-1]] != "nan":
            val = parse_duration_to_hours(row[total_cols[-1]])
            if val > 0:
                return val
        if len(total_cols) >= 1 and row[total_cols[0]] != "nan":
            return parse_duration_to_hours(row[total_cols[0]])
        return 0.0

    df_attendance["Hours_Worked"] = df_attendance.apply(
        calculate_row_hours, axis=1
    )

    # -----------------------------------------------------------------------------
    # Print Reports
    # -----------------------------------------------------------------------------
    print("\n" + "=" * 60)
    print(" 📋 CLEANED LOG ENTRIES (Sample)")
    print("=" * 60)
    print(
        df_attendance[["Date", "Name", "IN", "OUT", "Hours_Worked"]]
        .head(10)
        .to_string(index=False)
    )  #

    print("\n" + "=" * 60)
    print(" 🏖️ LEAVE & OFF RECORDS DETECTED")
    print("=" * 60)
    if not df_leaves.empty:
        for _, row in df_leaves.iterrows():
            status = row["IN"] if row["IN"] != "nan" else row["Name"]
            print(f" • {row['Date']} | {row['Name']}: {status}")  #
    else:
        print("No leave entries recorded.")

    print("\n" + "=" * 60)
    print(" 📊 TOTAL HOURS WORKED BY EMPLOYEE")
    print("=" * 60)
    summary = (
        df_attendance.groupby("Name")["Hours_Worked"]
        .agg(Total_Hours="sum", Shift_Count="count")
        .reset_index()
    )
    summary = summary.sort_values(by="Total_Hours", ascending=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()