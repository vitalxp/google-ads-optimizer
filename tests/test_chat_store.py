from pathlib import Path

from ads_optimizer import chat_store


def test_chat_store_crud(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(chat_store, "_DATA_DIR", Path(tmp_path) / "chats")

    created = chat_store.create_chat(model="test/model", title="T")
    assert created["id"]
    assert created["title"] == "T"

    listed = chat_store.list_chats()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]

    updated = chat_store.append_messages(
        created["id"],
        [
            {"role": "user", "content": "Привет, обзор аккаунта"},
            {"role": "assistant", "content": "Вот обзор", "model": "test/model"},
        ],
        model="other/model",
    )
    assert updated is not None
    assert updated["model"] == "other/model"
    assert "обзор" in updated["title"].lower() or "Привет" in updated["title"]

    loaded = chat_store.get_chat(created["id"])
    assert loaded is not None
    hist = chat_store.history_for_model(loaded)
    assert hist[0]["role"] == "user"
    assert hist[1]["role"] == "assistant"

    chat_store.update_chat(created["id"], model="third/model")
    assert chat_store.get_chat(created["id"])["model"] == "third/model"

    assert chat_store.delete_chat(created["id"]) is True
    assert chat_store.get_chat(created["id"]) is None
    assert chat_store.list_chats() == []
