"""Measure visual-only and OCR/code-fused retrieval on labelled local photos."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from visual_candidates import (  # noqa: E402
    MAX_IMAGE_BYTES,
    MAX_INDEX_RECORDS,
    IndexedVisual,
    fingerprint_image,
    rank_visual_candidates,
)
from visual_catalog_service import configured_embedding_provider  # noqa: E402


@dataclass(frozen=True)
class BenchmarkCase:
    expected_code: str
    category: str | None
    brand: str | None
    image_path: Path


def parse_case(value: str) -> BenchmarkCase:
    label, separator, raw_path = str(value).partition("=")
    if not separator:
        raise argparse.ArgumentTypeError("case biçimi CODE|CATEGORY|BRAND=IMAGE_PATH olmalı")
    parts = [part.strip() for part in label.split("|")]
    code = parts[0] if parts else ""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,79}", code):
        raise argparse.ArgumentTypeError("case ürün kodu geçersiz")
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file() or path.is_symlink():
        raise argparse.ArgumentTypeError("case görseli bulunamadı veya güvenli değil")
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise argparse.ArgumentTypeError("case görseli boyut sınırını aşıyor")
    return BenchmarkCase(
        expected_code=code,
        category=parts[1].lower() if len(parts) > 1 and parts[1] else None,
        brand=parts[2] if len(parts) > 2 and parts[2] else None,
        image_path=path,
    )


def relevant_metadata(metadata, expected_code: str) -> bool:
    text = f"{metadata.model_code or ''} {metadata.display_name}".casefold()
    return expected_code.casefold() in text


def metrics(ranks: list[int | None]) -> dict[str, float | int]:
    total = len(ranks)
    return {
        "cases": total,
        "top1_hits": sum(rank == 1 for rank in ranks),
        "top5_hits": sum(rank is not None and rank <= 5 for rank in ranks),
        "top5_recall": round(sum(rank is not None and rank <= 5 for rank in ranks) / total, 4),
        "mean_reciprocal_rank": round(sum(1 / rank for rank in ranks if rank) / total, 4),
    }


async def run_benchmark(cases: list[BenchmarkCase]) -> dict:
    load_dotenv(ROOT / ".env")
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "shoehunter_ai")]
    try:
        rows = await db.visual_candidate_index.find({}).to_list(MAX_INDEX_RECORDS + 1)
        if len(rows) > MAX_INDEX_RECORDS:
            raise RuntimeError("visual catalog exceeds the safe benchmark limit")
        records = [IndexedVisual.from_index_document(row) for row in rows]
        provider = configured_embedding_provider()
        if provider is None:
            raise RuntimeError("verified visual embedding provider is not enabled")
        results = []
        visual_ranks: list[int | None] = []
        hybrid_ranks: list[int | None] = []
        for case in cases:
            query = fingerprint_image(
                case.image_path.read_bytes(),
                content_type="image/jpeg",
                embedding_provider=provider,
            )
            visual = rank_visual_candidates(
                query,
                records,
                category=case.category,
                include_cross_category=True,
                limit=100,
            )
            hybrid = rank_visual_candidates(
                query,
                records,
                category=case.category,
                include_cross_category=True,
                limit=100,
                model_code_hint=case.expected_code,
                brand_hint=case.brand,
            )
            visual_rank = next(
                (
                    index
                    for index, candidate in enumerate(visual.candidates, 1)
                    if relevant_metadata(candidate.metadata, case.expected_code)
                ),
                None,
            )
            hybrid_rank = next(
                (index for index, candidate in enumerate(hybrid.candidates, 1) if case.expected_code.casefold() in f"{candidate.metadata.model_code or ''} {candidate.metadata.display_name}".casefold()),
                None,
            )
            visual_ranks.append(visual_rank)
            hybrid_ranks.append(hybrid_rank)
            results.append(
                {
                    "expected_code": case.expected_code,
                    "category": case.category,
                    "visual_rank": visual_rank,
                    "hybrid_rank": hybrid_rank,
                    "hybrid_top_candidate": hybrid.candidates[0].metadata.to_dict() if hybrid.candidates else None,
                    "exact_sku_decision": False,
                }
            )
        return {
            "catalog_records": len(records),
            "embedding": provider.descriptor.to_dict(),
            "visual_only": metrics(visual_ranks),
            "ocr_code_fused": metrics(hybrid_ranks),
            "cases": results,
        }
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark private visual catalog retrieval")
    parser.add_argument("--case", action="append", type=parse_case, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run_benchmark(args.case)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
