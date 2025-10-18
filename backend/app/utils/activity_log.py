import datetime
import json
from pathlib import Path
from typing import Any, List


ROOT_DIR = Path(__file__).resolve().parents[3]
LOG_PATH = ROOT_DIR / "logs" / "ACTIVITY_LOG.md"


def log_activity(file_paths: List[str], summary: str, notes: Any = "") -> None:
    """
    Append an activity entry to the central log with a UTC timestamp.
    """
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    files_changed = ", ".join(file_paths) if file_paths else "(none)"
    if isinstance(notes, (dict, list)):
        notes_value = json.dumps(notes, sort_keys=True)
    else:
        notes_value = str(notes) if notes else "n/a"

    entry = (
        "\n\n---\n\n"
        f"- **Timestamp (UTC)**: {timestamp}\n"
        "- **Author/Agent**: Codex\n"
        f"- **Prompt (summary)**: {summary}\n"
        f"- **Files changed**: {files_changed}\n"
        f"- **Notes/Reasons**: {notes_value}\n"
    )

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(entry)
