"""Telemetry service for field testing data collection.

Records OCR scan events, match feedback, and generates weekly summary stats.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger("shoehunter.telemetry")

async def ensure_telemetry_indexes(db) -> None:
    """Create MongoDB indexes for telemetry collections."""
    await db.telemetry_scans.create_index("created_at", expireAfterSeconds=60 * 60 * 24 * 30)  # Keep for 30 days
    await db.telemetry_scans.create_index("session_id")
    await db.telemetry_feedback.create_index("created_at", expireAfterSeconds=60 * 60 * 24 * 30)
    await db.telemetry_feedback.create_index("scan_id")


async def record_scan_event(db, payload: dict[str, Any]) -> str:
    """Record a barcode/OCR scan event."""
    document = {
        "created_at": datetime.now(UTC),
        "session_id": payload.get("session_id", "unknown"),
        "scan_type": payload.get("scan_type"),  # 'barcode', 'qr', 'ocr'
        "source_identifiers": payload.get("source_identifiers", {}),
        "ocr_confidence": payload.get("ocr_confidence"),
        "selected_fields_count": payload.get("selected_fields_count", 0),
        "total_fields_count": payload.get("total_fields_count", 0),
    }
    result = await db.telemetry_scans.insert_one(document)
    return str(result.inserted_id)


async def record_match_feedback(db, payload: dict[str, Any]) -> str:
    """Record user feedback on whether the radar found the right product."""
    document = {
        "created_at": datetime.now(UTC),
        "scan_id": payload.get("scan_id"),
        "radar_id": payload.get("radar_id"),
        "feedback": payload.get("feedback"),  # 'correct', 'incorrect_product', 'not_found'
        "notes": payload.get("notes", ""),
    }
    result = await db.telemetry_feedback.insert_one(document)
    return str(result.inserted_id)


async def get_weekly_summary(db) -> dict[str, Any]:
    """Calculate summary statistics for the last 7 days."""
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)
    
    total_scans = await db.telemetry_scans.count_documents({"created_at": {"$gte": seven_days_ago}})
    ocr_scans = await db.telemetry_scans.count_documents({"created_at": {"$gte": seven_days_ago}, "scan_type": "ocr"})
    barcode_scans = await db.telemetry_scans.count_documents({"created_at": {"$gte": seven_days_ago}, "scan_type": {"$in": ["barcode", "qr"]}})
    
    # Feedback stats
    feedback_cursor = db.telemetry_feedback.aggregate([
        {"$match": {"created_at": {"$gte": seven_days_ago}}},
        {"$group": {"_id": "$feedback", "count": {"$sum": 1}}}
    ])
    feedback_stats = {doc["_id"]: doc["count"] async for doc in feedback_cursor}
    total_feedback = sum(feedback_stats.values())
    
    return {
        "period": "last_7_days",
        "scans": {
            "total": total_scans,
            "ocr": ocr_scans,
            "barcode_qr": barcode_scans,
        },
        "feedback": {
            "total_responses": total_feedback,
            "correct_match": feedback_stats.get("correct", 0),
            "incorrect_match": feedback_stats.get("incorrect_product", 0),
            "not_found": feedback_stats.get("not_found", 0),
        }
    }
