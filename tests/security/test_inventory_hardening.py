from local_developer_worker.tools import file_inventory


def test_inventory_blocks_private_key_content_without_sensitive_name(tmp_path):
    synthetic_key = "-----BEGIN " + "PRIVATE KEY-----\nsynthetic\n-----END " + "PRIVATE KEY-----"
    (tmp_path / "notes.txt").write_text(synthetic_key)
    record = file_inventory({"repository_root": str(tmp_path)})["data"]["files"][0]
    assert record["potentially_sensitive"] is True
    assert record["readable"] is False
    assert record["ignored_by_policy"] is True
    assert record["hash"] is None
    assert synthetic_key not in str(record)


def test_inventory_marks_symlink_escape(tmp_path):
    external = tmp_path.parent / "outside.txt"
    external_content = "outside-root-content"
    external.write_text(external_content)
    (tmp_path / "link").symlink_to(external)
    record = file_inventory({"repository_root": str(tmp_path)})["data"]["files"][0]
    assert record["blocked"] == "symlink_escape"
    assert record["readable"] is False
    assert external_content not in str(record)
