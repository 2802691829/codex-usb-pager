import sqlite3
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: inspect_codex_sqlite.py <sqlite-path>")
        return 2

    path = Path(sys.argv[1])
    con = sqlite3.connect(path)
    tables = [row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print(f"database={path}")
    for table in tables:
        print(f"\n[{table}]")
        cols = con.execute(f"PRAGMA table_info({table})").fetchall()
        for col in cols:
            print("  " + " ".join(str(part) for part in col))
        try:
            count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  rows={count}")
        except sqlite3.DatabaseError as exc:
            print(f"  count_error={exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
