from __future__ import annotations


def _reset_local_db(local_db) -> None:
    if local_db._conn is not None:
        local_db._conn.close()
    local_db._conn = None


def test_load_signals_returns_empty_when_cache_table_missing(tmp_path, monkeypatch):
    from integrations import local_db

    _reset_local_db(local_db)
    monkeypatch.setattr("core.constants.LOCAL_DB_PATH", tmp_path / "empty.db")
    try:
        assert local_db.load_signals() == []
    finally:
        _reset_local_db(local_db)


def test_load_signals_by_codes_returns_empty_when_cache_table_missing(tmp_path, monkeypatch):
    from integrations import local_db

    _reset_local_db(local_db)
    monkeypatch.setattr("core.constants.LOCAL_DB_PATH", tmp_path / "empty.db")
    try:
        assert local_db.load_signals_by_codes(["603082"]) == {}
    finally:
        _reset_local_db(local_db)


def test_save_recommendations_preserves_rag_vetoed(tmp_path, monkeypatch):
    from integrations import local_db

    _reset_local_db(local_db)
    monkeypatch.setattr("core.constants.LOCAL_DB_PATH", tmp_path / "recommendations.db")
    try:
        local_db.init_db()
        local_db.save_recommendations(
            [
                {
                    "code": "000001",
                    "name": "平安银行",
                    "recommend_date": 20260518,
                    "rag_vetoed": True,
                }
            ]
        )
        rows = local_db.load_recommendations(limit=1)
        assert rows[0]["rag_vetoed"] == 1
    finally:
        _reset_local_db(local_db)
