from ads_optimizer.applicator import _set_update_mask

from tests.helpers import dummy_ads_client


def test_set_update_mask_paths() -> None:
    client = dummy_ads_client()
    operation = client.get_type("AdGroupCriterionOperation")
    _set_update_mask(operation, "status")
    assert list(operation.update_mask.paths) == ["status"]
    _set_update_mask(operation, "cpc_bid_micros")
    assert list(operation.update_mask.paths) == ["cpc_bid_micros"]
