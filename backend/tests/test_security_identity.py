import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from product_identity import (  # noqa: E402
    canonicalize_product_url,
    identity_from_title,
    match_identities,
    normalize_size,
)
from security import URLValidationError, hash_password, validate_remote_url, verify_password  # noqa: E402


def test_exact_model_code_is_an_automatic_match():
    expected = identity_from_title("Adidas Adizero Evo SL JH6206 Erkek")
    candidate = identity_from_title("adidas JH6206 Adizero Evo SL erkek kosu ayakkabisi")
    match = match_identities(expected, candidate)
    assert match["decision"] == "auto"
    assert match["confidence"] >= 0.99


def test_protected_model_tokens_do_not_merge():
    standard = identity_from_title("Brooks Glycerin 22 Erkek")
    gts = identity_from_title("Brooks Glycerin GTS 22 Erkek")
    match = match_identities(standard, gts)
    assert match["decision"] == "rejected"
    assert "protected_model_token_mismatch" in match["evidence"]


def test_gender_mismatch_is_rejected():
    men = identity_from_title("New Balance 1080 v14 Erkek")
    women = identity_from_title("New Balance 1080 v14 Kadin")
    match = match_identities(men, women)
    assert match["decision"] == "rejected"
    assert "gender_mismatch" in match["evidence"]


def test_missing_generation_and_different_model_are_rejected():
    expected = identity_from_title("Nike Zegama 2", brand="Nike")

    missing_generation = match_identities(
        expected,
        identity_from_title("Nike Zegama Trail Ayakkabi", brand="Nike"),
    )
    wrong_model = match_identities(
        expected,
        identity_from_title("Nike Initiator 2 Ayakkabi", brand="Nike"),
    )

    assert missing_generation["decision"] == "rejected"
    assert "generation_missing" in missing_generation["evidence"]
    assert wrong_model["decision"] == "rejected"
    assert "model_token_mismatch" in wrong_model["evidence"]


def test_different_explicit_style_codes_are_rejected_before_generic_title_similarity():
    expected = identity_from_title("Adidas Trail Running JR5220")
    candidate = identity_from_title(
        "adidas Terrex Agravic SL Trail Running Ayakkabi",
        url="https://www.adidas.com.tr/tr/terrex-agravic-sl/KH8800.html",
    )

    result = match_identities(expected, candidate)

    assert result["decision"] == "rejected"
    assert result["evidence"] == ["model_code_mismatch"]


def test_candidate_brand_is_inferred_and_mismatch_is_rejected():
    expected = identity_from_title("Adidas Trail Running Ayakkabi")
    candidate = identity_from_title("Nike Pegasus Trail Running Ayakkabi")

    assert expected.brand == "adidas"
    assert candidate.brand == "nike"
    assert match_identities(expected, candidate)["evidence"] == ["brand_mismatch"]


def test_size_normalization_handles_turkish_and_fractions():
    assert normalize_size("EU 43 1/3") == "43 1/3"
    assert normalize_size("44,0") == "44"


def test_canonical_url_keeps_product_identity_query_only():
    url = "https://www.decathlon.com.tr/p/urun/_/R-p-351055?mc=8851718&c=MAVI&utm_source=test"
    assert canonicalize_product_url(url) == "https://www.decathlon.com.tr/p/urun/_/R-p-351055?mc=8851718"


def test_amazon_url_is_canonicalized_by_asin():
    first = "https://www.amazon.com.tr/Nike-Zegama/dp/B097NQRKVK/ref=sr_1_2?keywords=zegama"
    second = "https://www.amazon.com.tr/Nike-Zegama/dp/B097NQRKVK/ref=sr_1_7"

    assert canonicalize_product_url(first) == "https://www.amazon.com.tr/dp/B097NQRKVK"
    assert canonicalize_product_url(second) == "https://www.amazon.com.tr/dp/B097NQRKVK"


def test_password_hash_round_trip():
    password_hash = hash_password("GucluParola2026")
    assert verify_password("GucluParola2026", password_hash)
    assert not verify_password("yanlis", password_hash)


def test_ssrf_rejects_non_https_and_unknown_domains():
    async def run():
        try:
            await validate_remote_url("http://127.0.0.1:8000/api", ["example.com"], resolve_dns=False)
        except URLValidationError:
            pass
        else:
            raise AssertionError("Local HTTP URL should be rejected")

        try:
            await validate_remote_url("https://example.com.evil.test/product", ["example.com"], resolve_dns=False)
        except URLValidationError:
            pass
        else:
            raise AssertionError("Suffix-confusion domain should be rejected")

        accepted = await validate_remote_url("https://shop.example.com/product", ["example.com"], resolve_dns=False)
        assert accepted.startswith("https://shop.example.com/")

    asyncio.run(run())
