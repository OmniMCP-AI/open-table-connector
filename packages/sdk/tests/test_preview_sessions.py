from __future__ import annotations


def test_stop_not_publish(tmp_path):
    from open_table_connector.sdk.preview_sessions import PreviewSessionStore

    store = PreviewSessionStore(tmp_path)
    record = store.create({"state": "running", "url": "http://127.0.0.1:1"})
    assert store.load(record["session_id"])["state"] == "running"
    store.update(record["session_id"], {"state": "stopped"})
    assert store.load(record["session_id"])["state"] == "stopped"


def test_watch_missing_runtime_rejects(tmp_path, monkeypatch):
    from open_table_connector.artifacts import WatchRequest
    from open_table_connector.contract import TargetSelector
    from open_table_connector.sdk import Client, ConnectorRegistry
    from open_table_connector.sdk.artifacts import ArtifactAccess
    monkeypatch.setattr(ArtifactAccess, "_adapter", lambda self: None)
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"original")
    result = Client(registry=ConnectorRegistry()).artifacts().watch(WatchRequest("start", TargetSelector(source.as_uri())))
    assert result.outcome.value == "rejected"
    assert result.error.code.value == "unsupported_capability"


def test_watch_refresh_crash_and_stop_use_owned_handles(tmp_path, monkeypatch):
    from open_table_connector.artifacts import WatchRequest
    from open_table_connector.contract import TargetSelector
    from open_table_connector.sdk import Client, ConnectorRegistry
    from open_table_connector.sdk.artifacts import ArtifactAccess
    from open_table_connector.sdk.preview_sessions import PreviewSessionStore
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"original")
    handles = []
    paths = []
    class Handle:
        pid = 123
        exited = None
        def poll(self): return self.exited
        def terminate(self): self.exited = 0
        def wait(self, timeout=None): return self.exited
    class Adapter:
        def start_watch(self, path):
            handle = Handle()
            handles.append(handle)
            paths.append(path)
            return handle, "http://127.0.0.1:12345"
    monkeypatch.setattr(ArtifactAccess, "_adapter", lambda self: Adapter())
    monkeypatch.setattr(ArtifactAccess, "_preview_store", lambda self: PreviewSessionStore(tmp_path / "sessions"))
    access = Client(registry=ConnectorRegistry()).artifacts()
    started = access.watch(WatchRequest("start", TargetSelector(source.as_uri())))
    assert started.value.state == "running"
    session_id = started.value.session_id
    paths[0].write_bytes(b"preview edit")
    source.write_bytes(b"new committed source")
    refreshed = access.watch(WatchRequest("refresh", session_id=session_id))
    assert refreshed.value.state == "running"
    assert handles[0].exited == 0
    assert paths[1].read_bytes() == b"new committed source"
    assert refreshed.value.source_hash != started.value.source_hash
    handles[1].exited = 7
    assert access.watch(WatchRequest("status", session_id=session_id)).value.state == "crashed"
    stopped = access.watch(WatchRequest("stop", session_id=session_id))
    assert stopped.value.state == "stopped"
    assert source.read_bytes() == b"new committed source"
    assert not paths[1].exists()


def test_stale_pid_is_never_signalled(tmp_path):
    from open_table_connector.sdk.preview_sessions import PreviewSessionStore
    store = PreviewSessionStore(tmp_path)
    record = store.create({"state": "running", "pid": 1, "owner_token": "stale"})
    assert store.runtime_state(record["session_id"]) == "orphaned"
    store.stop(record["session_id"])
    assert store.load(record["session_id"])["state"] == "stopped"
