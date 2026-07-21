import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from restore_service import inspect_backup  # noqa: E402


parser = argparse.ArgumentParser(description="ShoeHunter JSON yedegini dogrular")
parser.add_argument("path")
args = parser.parse_args()
summary = inspect_backup(args.path)
print(f"Yedek gecerli: sema {summary['schema_version']}")
for name, count in summary["collections"].items():
    print(f"{name}: {count}")
