from pathlib import Path


VERSION_FILE = Path(__file__).resolve().parents[1] / "VERSION.txt"


def app_version():
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"
