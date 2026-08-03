from local_developer_worker.tools import file_inventory


def test_inventory_blocks_env_file(tmp_path):
    synthetic_secret = "TOKEN=synthetic"
    (tmp_path / ".env").write_text(synthetic_secret)
    output = file_inventory({"repository_root": str(tmp_path)})
    record = next(item for item in output["data"]["files"] if item["path"] == ".env")
    assert record["potentially_sensitive"] is True
    assert record["readable"] is False
    assert record["ignored_by_policy"] is True
    assert record["hash"] is None
    assert synthetic_secret not in str(output)
