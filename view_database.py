"""
InternTrack - Quick SQLite Database Viewer
Run this script anytime to inspect all tables and records in your database:
    python view_database.py
"""

import os
import sys
import sqlite3

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def display_database():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "database", "interntrack_v2.db")
    
    if not os.path.exists(db_path):
        print(f"[!] Database file not found at: {db_path}")
        return

    print("=" * 80)
    print("  InternTrack SQLite Database Explorer")
    print(f"  File: {db_path} ({os.path.getsize(db_path):,} bytes)")
    print("=" * 80)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get list of user tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]

    if not tables:
        print("[!] No tables found in database.")
        conn.close()
        return

    print(f"\n[+] Total Tables: {len(tables)}")
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t};")
        cnt = cursor.fetchone()[0]
        print(f"    - {t:<22} : {cnt} records")
    print()

    for table in tables:
        print("=" * 80)
        cursor.execute(f"PRAGMA table_info({table});")
        columns = [col[1] for col in cursor.fetchall()]
        
        cursor.execute(f"SELECT COUNT(*) FROM {table};")
        count = cursor.fetchone()[0]

        print(f">> Table: {table} ({count} total records)")
        print("-" * 80)

        if count == 0:
            print("   (empty table)")
            print()
            continue

        # Fetch records (limit preview to 10 rows for readability)
        cursor.execute(f"SELECT * FROM {table} LIMIT 10;")
        rows = cursor.fetchall()

        # Format column display
        col_names = list(columns)

        # Truncate large binary / text data (e.g. BLOB images)
        formatted_rows = []
        for row in rows:
            formatted_row = []
            for item in row:
                if isinstance(item, (bytes, bytearray)):
                    formatted_row.append(f"<BLOB {len(item):,} bytes>")
                elif item is None:
                    formatted_row.append("NULL")
                else:
                    str_item = str(item)
                    if len(str_item) > 30:
                        str_item = str_item[:27] + "..."
                    formatted_row.append(str_item)
            formatted_rows.append(formatted_row)

        # Calculate max column widths
        widths = [len(col) for col in col_names]
        for row in formatted_rows:
            for i, val in enumerate(row):
                widths[i] = max(widths[i], len(val))

        # Print header
        header_line = " | ".join(col.ljust(widths[i]) for i, col in enumerate(col_names))
        sep_line = "-+-".join("-" * widths[i] for i in range(len(col_names)))
        print(f" {header_line}")
        print(f" {sep_line}")

        # Print data rows
        for row in formatted_rows:
            row_line = " | ".join(row[i].ljust(widths[i]) for i in range(len(row)))
            print(f" {row_line}")

        if count > 10:
            print(f" ... and {count - 10} more rows.")
        print()

    conn.close()
    print("=" * 80)
    print("  Done. All database records displayed successfully.")
    print("=" * 80)

if __name__ == '__main__':
    display_database()
