import json


def test_load_entries_missing_file(tmp_path, monkeypatch):
    import flowerlibrary as fl

    data_file = tmp_path / "library_data.json"
    monkeypatch.setattr(fl, "DATA_FILE", data_file)
    monkeypatch.setattr(fl, "DATA_DIR", tmp_path)

    assert fl.load_entries() == []


def test_load_entries_invalid_json_warns(tmp_path, monkeypatch):
    import flowerlibrary as fl

    data_file = tmp_path / "library_data.json"
    data_file.write_text("{bad json", encoding="utf-8")
    monkeypatch.setattr(fl, "DATA_FILE", data_file)
    monkeypatch.setattr(fl, "DATA_DIR", tmp_path)

    warnings = []

    def _warn(title, message):
        warnings.append((title, message))

    monkeypatch.setattr(fl.messagebox, "showwarning", _warn)

    assert fl.load_entries() == []
    assert warnings


def test_save_entries_writes_and_backup(tmp_path, monkeypatch):
    import flowerlibrary as fl

    data_file = tmp_path / "library_data.json"
    data_file.write_text(json.dumps([{"brand": "old"}]), encoding="utf-8")
    monkeypatch.setattr(fl, "DATA_FILE", data_file)
    monkeypatch.setattr(fl, "DATA_DIR", tmp_path)

    entries = [{"brand": "New Brand", "strain": "Test"}]
    fl.save_entries(entries)

    assert data_file.exists()
    assert data_file.with_suffix(".json.bak").exists()
    assert not data_file.with_suffix(".json.tmp").exists()
    assert json.loads(data_file.read_text(encoding="utf-8")) == entries
