from __future__ import annotations


def test_stop_not_publish(tmp_path):
    from open_table_connector.sdk.preview_sessions import PreviewSessionStore

    store = PreviewSessionStore(tmp_path)
    record = store.create({"state": "running", "url": "http://127.0.0.1:1"})
    assert store.load(record["session_id"])["state"] == "running"
    store.update(record["session_id"], {"state": "stopped"})
    assert store.load(record["session_id"])["state"] == "stopped"
