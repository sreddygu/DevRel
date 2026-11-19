import csv
import os
import sqlite3
from pathlib import Path


def main() -> None:
    db_path = os.environ.get("VSAAS_DB_PATH", "data/events.db")
    csv_path = os.environ.get("VSAAS_EVENTS_CSV_PATH", "data/events_recent.csv")
    os.makedirs(Path(csv_path).parent, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, ts_ms, camera_id, event_type, severity, summary, payload_json "
            "FROM events ORDER BY ts_ms DESC LIMIT 200"
        )
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(columns)
            writer.writerows(rows)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
