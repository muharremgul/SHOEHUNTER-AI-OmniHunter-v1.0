"""Run the local label scanner against one or more image paths."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from label_scan import scan_product_label


def main() -> int:
    parser = argparse.ArgumentParser(description="ShoeHunter etiket okuma tanilama araci")
    parser.add_argument("images", nargs="+", type=Path)
    args = parser.parse_args()
    rows = []
    for path in args.images:
        try:
            result = scan_product_label(path.read_bytes(), "image/jpeg")
            rows.append(
                {
                    "file": path.name,
                    "ok": True,
                    "suggested_watch": result["suggested_watch"],
                    "barcodes": result["barcodes"],
                    "product_codes": result["product_codes"],
                    "prices": result["prices"],
                    "confidence": result["confidence"],
                    "ocr_rotation": result["image"]["ocr_rotation"],
                    "warnings": result["warnings"],
                }
            )
        except Exception as exc:
            rows.append({"file": path.name, "ok": False, "error": str(exc)})
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0 if all(row["ok"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
