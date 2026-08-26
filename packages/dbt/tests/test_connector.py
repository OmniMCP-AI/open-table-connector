from open_connectors.dbt import DbtCompileRequest, DbtConnector


def test_dbt_connector_freezes_compiled_artifact_bytes_and_invocation() -> None:
    seen = []

    def runner(argv, project_dir):
        seen.append(argv)
        return {"artifacts": {"manifest.json": b'{"nodes":{}}'}, "status": "completed"}

    operation = DbtConnector(runner).compile(DbtCompileRequest("/tmp/project", select=("model.orders",)))

    assert operation.argv[:2] == ("dbt", "compile")
    assert operation.artifact_hash
    assert operation.manifest_ref == "manifest.json"
    assert seen
