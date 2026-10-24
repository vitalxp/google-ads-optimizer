from ads_optimizer import pending_mutations as pm


def test_pending_put_get_pop(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(pm, "_DATA_PATH", tmp_path / "pending.json")
    pid = pm.put(action="set_campaign_status", payload={"campaign_id": "1"}, preview={"p": 1})
    item = pm.get(pid)
    assert item is not None
    assert item["action"] == "set_campaign_status"
    assert item["payload"]["campaign_id"] == "1"
    popped = pm.pop(pid)
    assert popped is not None
    assert pm.get(pid) is None
