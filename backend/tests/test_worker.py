import pytest

import worker


@pytest.mark.asyncio
async def test_discover_due_job_respects_bounded_limit(monkeypatch):
    observed = {}

    async def fake_run_due_discoveries(db, limit=20):
        observed["db"] = db
        observed["limit"] = limit
        return [{"id": "run-1"}]

    monkeypatch.setattr(worker, "run_due_discoveries", fake_run_due_discoveries)
    database = object()

    result = await worker.handle_job(
        database,
        {"job_type": "discover_due", "payload": {"limit": 1}},
    )

    assert observed == {"db": database, "limit": 1}
    assert result == {"runs": 1}


@pytest.mark.asyncio
async def test_discover_due_job_caps_limit_at_twenty(monkeypatch):
    observed = {}

    async def fake_run_due_discoveries(_db, limit=20):
        observed["limit"] = limit
        return []

    monkeypatch.setattr(worker, "run_due_discoveries", fake_run_due_discoveries)

    result = await worker.handle_job(
        object(),
        {"job_type": "discover_due", "payload": {"limit": 999}},
    )

    assert observed["limit"] == 20
    assert result == {"runs": 0}
