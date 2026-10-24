import inspect

import pytest

from ads_optimizer.campaign_ops import (
    create_ad_group_with_rsa,
    evaluate_rsa_for_ad_strength,
    require_confirm,
    validate_rsa_copy,
)


def test_require_confirm_blocks_without_flag() -> None:
    blocked = require_confirm(False, {"action": "x"})
    assert blocked is not None
    assert blocked["needs_confirmation"] is True


def test_require_confirm_allows_when_true() -> None:
    assert require_confirm(True, {"action": "x"}) is None


def test_validate_rsa_copy_ok() -> None:
    hs, ds = validate_rsa_copy(
        ["Transfer Gdansk", "Fixed price", "Book now"],
        ["Private transfer with meet and greet.", "Book online in minutes."],
    )
    assert len(hs) == 3
    assert len(ds) == 2


def test_validate_rsa_copy_rejects_long_headline() -> None:
    with pytest.raises(ValueError, match="too long"):
        validate_rsa_copy(
            [
                "This headline is way too long for RSA thirty",
                "Fixed price transfer",
                "Book now online",
            ],
            ["Private transfer with meet and greet.", "Book online in minutes."],
        )


def test_evaluate_rsa_reports_short_pool() -> None:
    out = evaluate_rsa_for_ad_strength(
        ["A", "B", "C"],
        ["Desc one here.", "Desc two here."],
        keywords=["transfer gdansk"],
    )
    assert out["ok_for_good_excellent"] is False
    assert out["warnings"]
    assert out["rule"] == "rsa-ad-strength"


def test_create_ad_group_with_rsa_still_validates() -> None:
    src = inspect.getsource(create_ad_group_with_rsa)
    assert "validate_rsa_copy" in src
    assert "require_working_url" in src

