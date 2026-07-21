import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip().lstrip("v")
frontend_version = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))["version"]
pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
python_version = match.group(1) if match else None
if len({version, frontend_version, python_version}) != 1:
    raise SystemExit(
        f"Surumler tutarsiz: VERSION.txt={version}, frontend={frontend_version}, pyproject={python_version}"
    )
print(version)
