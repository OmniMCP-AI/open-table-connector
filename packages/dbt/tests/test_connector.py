from open_connectors.dbt import DbtCompileRequest, DbtConnector


def test_dbt_connector_freezes_compiled_artifact_bytes_and_invocation() -> None:
    seen = []

    def runner(argv, project_dir):
        seen.append(argv)
        return {"artifacts": {"manifest.json": b'{"nodes":{}}'}, "status": "completed"}

    operation = DbtConnector(runner).compile(
        DbtCompileRequest("/tmp/project", select=("model.orders",), vars={"currency": "USD"})
    )

    assert operation.argv[:2] == ("dbt", "compile")
    assert operation.artifact_hash
    assert operation.manifest_ref == "manifest.json"
    assert operation.run_argv[:2] == ("dbt", "run")
    assert "--vars" in operation.argv
    assert seen


def test_dbt_run_uses_a_real_run_argv_and_preserves_invocation() -> None:
    calls = []

    def runner(argv, project_dir):
        calls.append(argv)
        if argv[1] == "compile":
            return {"artifacts": {"manifest.json": b"manifest"}}
        return {"status": "success", "run_results": b"results"}

    connector = DbtConnector(runner)
    operation = connector.compile(DbtCompileRequest("/tmp/project", select=("model.orders",)))
    result = connector.run(operation)

    assert calls[0][1] == "compile"
    assert calls[1][1] == "run"
    assert result.invocation_id == operation.invocation_id
    assert result.run_results == b"results"
