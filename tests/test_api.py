"""Flask endpoint tests: a corrupt workbook or a bad request must come back
as JSON the Electron frontend can parse, never an HTML 500 traceback.
"""

from backend.main import app


def _client():
    app.config["TESTING"] = True
    return app.test_client()


def test_ping():
    client = _client()
    resp = client.post("/ping")
    assert resp.status_code == 200
    assert resp.is_json
    assert resp.get_json() == {"status": "ok"}


def test_generate_empty_allocations_returns_400_json():
    client = _client()
    resp = client.post("/generate", json={"chapter_allocations": {}})
    assert resp.status_code == 400
    assert resp.is_json
    body = resp.get_json()
    assert body["success"] is False
    assert body["errors"]


def test_generate_allocations_sum_mismatch_returns_400_json():
    client = _client()
    resp = client.post("/generate", json={"chapter_allocations": {"Algebra": 59}})
    assert resp.status_code == 400
    assert resp.is_json
    body = resp.get_json()
    assert body["success"] is False
    assert any("59" in e for e in body["errors"])


def test_grade_missing_file_returns_400_json():
    client = _client()
    resp = client.post("/grade", json={"entry_sheet_path": "C:/does/not/exist.xlsx"})
    assert resp.status_code == 400
    assert resp.is_json
    body = resp.get_json()
    assert body["success"] is False


def test_grade_corrupt_file_returns_json_not_html(tmp_path):
    bad_file = tmp_path / "corrupt.xlsx"
    bad_file.write_text("this is not a real workbook")

    client = _client()
    resp = client.post("/grade", json={"entry_sheet_path": str(bad_file)})

    assert resp.status_code == 400
    assert resp.is_json, resp.data
    body = resp.get_json()
    assert body["success"] is False
    assert any("Failed to open Excel file" in e for e in body["errors"])
