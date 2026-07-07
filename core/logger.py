from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def write_log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_DIR / "shoehunter.log", "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
