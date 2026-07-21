import json
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from engines import get_engine_for_url


@pytest.mark.live
@pytest.mark.asyncio
async def test_configured_store_contracts():
    if os.environ.get("LIVE_STORE_TESTS") != "1":
        pytest.skip("Canli magaza testleri varsayilan olarak kapalidir")
    urls = json.loads(os.environ.get("LIVE_STORE_URLS", "[]"))
    if not urls:
        pytest.skip("LIVE_STORE_URLS yapilandirilmadi")
    for url in urls:
        engine = get_engine_for_url(url)
        data = await engine.get_product_data(url)
        assert data.get("title"), f"{engine.slug}: baslik okunamadi"
        price = data.get("current_price")
        assert price is None or 50 < price < 200000, f"{engine.slug}: fiyat aralik disi"
        assert data.get("stock_status") in {
            "in_stock",
            "out_of_stock",
            "unknown",
            "blocked",
            "not_found",
            "error",
        }
