"""API tests for POST /updates/{id}/translate (review sprint). The LLM call is
mocked at app.llm.llm_json, the same seam the provider tests use."""
from unittest.mock import patch

from app.llm import ExtractorError
from .factories import make_project, make_task, make_update


def _update(db, text="ETLカットオーバーモジュールは40パーセントです。"):
    p = make_project(db)
    t = make_task(db, p)
    return make_update(db, t, raw_text=text, language="ja")


def test_translate_returns_text(client, db):
    u = _update(db)
    with patch("app.llm.llm_json", return_value={"translation": "ETL cutover module is at 40 percent."}) as m:
        r = client.post(f"/updates/{u.id}/translate", json={"target": "en"})
    assert r.status_code == 200
    body = r.json()
    assert body == {"update_id": u.id, "target": "en", "text": "ETL cutover module is at 40 percent."}
    assert "English" in m.call_args.args[0]
    assert m.call_args.args[1] == u.raw_text


def test_translate_target_ja_in_prompt(client, db):
    u = _update(db, text="Checkout rework at 60 percent.")
    with patch("app.llm.llm_json", return_value={"translation": "チェックアウト改修は60パーセントです。"}) as m:
        r = client.post(f"/updates/{u.id}/translate", json={"target": "ja"})
    assert r.status_code == 200
    assert "Japanese" in m.call_args.args[0]


def test_translate_missing_update_404(client, db):
    r = client.post("/updates/99999/translate", json={"target": "en"})
    assert r.status_code == 404


def test_translate_update_without_text_404(client, db):
    u = _update(db, text="")
    r = client.post(f"/updates/{u.id}/translate", json={"target": "en"})
    assert r.status_code == 404


def test_translate_llm_down_503(client, db):
    u = _update(db)
    with patch("app.llm.llm_json", side_effect=ExtractorError("down")):
        r = client.post(f"/updates/{u.id}/translate", json={"target": "en"})
    assert r.status_code == 503


def test_translate_empty_result_503(client, db):
    u = _update(db)
    with patch("app.llm.llm_json", return_value={"translation": "  "}):
        r = client.post(f"/updates/{u.id}/translate", json={"target": "en"})
    assert r.status_code == 503


def test_translate_requires_auth(anon_client, db):
    u = _update(db)
    r = anon_client.post(f"/updates/{u.id}/translate", json={"target": "en"})
    assert r.status_code in (401, 403)
