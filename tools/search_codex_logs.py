import sqlite3
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: search_codex_logs.py <sqlite-path> <keyword> [limit]")
        return 2

    path = Path(sys.argv[1])
    keyword = sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 50

    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT id, ts, level, target, feedback_log_body, module_path, file, line, thread_id
        FROM logs
        WHERE COALESCE(feedback_log_body, '') LIKE ?
           OR COALESCE(target, '') LIKE ?
           OR COALESCE(module_path, '') LIKE ?
           OR COALESCE(file, '') LIKE ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit),
    ).fetchall()

    for row in rows:
        body = (row["feedback_log_body"] or "").replace("\r", "\\r").replace("\n", "\\n")
        if len(body) > 700:
            body = body[:700] + "..."
        print(
            f"id={row['id']} ts={row['ts']} level={row['level']} "
            f"target={row['target']} file={row['file']} line={row['line']} "
            f"thread={row['thread_id']}\n  {body}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
