"""Unit tests for view_interpreter: matchers, guards, and _coerce. No LLM involved;
_coerce takes the raw dict the model would have produced."""
from app import view_interpreter as vi

WORLD = {
    "projects": [{"name": "Website Redesign", "name_ja": "ウェブサイト刷新", "tasks": []},
                 {"name": "Mobile App v2", "name_ja": None, "tasks": []}],
    "people": ["Alex", "Sam", "Casey", "Yamada-san"],
    "teams": [{"name": "Platform", "members": ["Alex", "Sam"]},
              {"name": "Mobile", "members": ["Casey"]}],
}


# ---------- matchers ----------
def test_match_project_abbreviation():
    assert vi._match_project("Website", WORLD) == "Website Redesign"
    assert vi._match_project("website", WORLD) == "Website Redesign"
    assert vi._match_project("Unknown Thing", WORLD) is None
    assert vi._match_project(None, WORLD) is None


def test_match_team_partial():
    assert vi._match_team("plat", WORLD) == "Platform"
    assert vi._match_team("Mobile", WORLD) == "Mobile"
    assert vi._match_team("Ghost", WORLD) is None


def test_match_person_honorific_base_token():
    assert vi._match_person("yamada", WORLD) == "Yamada-san"
    assert vi._match_person("Sam", WORLD) == "Sam"
    assert vi._match_person("nobody", WORLD) is None


# ---------- severity guard ----------
def test_severity_sort_phrase_drops_filter():
    raw = {"severity": "high", "sort": "severity"}
    out = vi._coerce(raw, WORLD, request="top 3 blockers by severity")
    assert out["severity"] is None and out["sort"] == "severity"


def test_severity_explicit_word_keeps_filter():
    out = vi._coerce({"severity": "high"}, WORLD, request="show high severity blockers")
    assert out["severity"] == "high"


# ---------- section guard ----------
def test_sections_dropped_without_literal_words():
    raw = {"sections": ["delivery", "per_person", "activity"]}
    out = vi._coerce(raw, WORLD, request="how are things")
    assert out["sections"] == []


def test_sections_kept_with_english_words():
    raw = {"sections": ["blockers", "per_person"]}
    out = vi._coerce(raw, WORLD, request="show blockers and workload")
    assert out["sections"] == ["blockers", "per_person"]


def test_sections_kept_with_japanese_words():
    out = vi._coerce({"sections": ["blockers"], "days": 7}, WORLD, request="今週のブロッカー")
    assert out["sections"] == ["blockers"]
    assert out["days"] == 7  # 今週 is a time word


def test_invalid_section_names_dropped():
    out = vi._coerce({"sections": ["blockers", "nonsense"], "hide": ["nope", "risks"]},
                     WORLD, request="show blockers, hide risks")
    assert out["sections"] == ["blockers"]
    assert out["hide"] == ["risks"]


# ---------- team / person guards ----------
def test_team_kept_when_request_names_it():
    out = vi._coerce({"team": "Mobile"}, WORLD,
                     request="focus on the Mobile team")
    assert out["team"] == "Mobile"


def test_team_dropped_when_invented():
    out = vi._coerce({"team": "Platform"}, WORLD, request="how are things")
    assert out["team"] is None


def test_person_possessive_kept():
    out = vi._coerce({"person": "Sam"}, WORLD, request="Sam's tasks")
    assert out["person"] == "Sam"


def test_person_base_token_matches_honorific():
    out = vi._coerce({"person": "yamada"}, WORLD, request="what is yamada working on")
    assert out["person"] == "Yamada-san"


def test_person_dropped_when_invented():
    out = vi._coerce({"person": "Casey"}, WORLD, request="overall status please")
    assert out["person"] is None


# ---------- time guard ----------
def test_dates_dropped_without_time_words():
    raw = {"days": 7, "date_from": "2026-06-01", "date_to": "2026-06-08"}
    out = vi._coerce(raw, WORLD, request="how are things")
    assert out["days"] is None and out["date_from"] is None and out["date_to"] is None


def test_days_beats_dates_with_time_word():
    raw = {"days": 14, "date_from": "2026-06-01"}
    out = vi._coerce(raw, WORLD, request="show the last 2 weeks")
    assert out["days"] == 14 and out["date_from"] is None


def test_iso_or_none():
    assert vi._iso_or_none("2026-06-01") == "2026-06-01"
    assert vi._iso_or_none("2026-06-01T10:00:00") == "2026-06-01"
    assert vi._iso_or_none("June first") is None
    assert vi._iso_or_none(None) is None


# ---------- enum and number coercion ----------
def test_invalid_enums_dropped():
    raw = {"status": "stuck", "severity": "catastrophic", "sort": "alphabetical"}
    out = vi._coerce(raw, WORLD, request="anything high")
    assert out["status"] is None and out["severity"] is None and out["sort"] is None


def test_limit_coercion():
    assert vi._coerce({"limit": 3}, WORLD)["limit"] == 3
    assert vi._coerce({"limit": 3.0}, WORLD)["limit"] == 3
    assert vi._coerce({"limit": 0}, WORLD)["limit"] is None
    assert vi._coerce({"limit": "three"}, WORLD)["limit"] is None


def test_empty_request_short_circuits_without_llm():
    # interpret_view must not call Ollama for a blank request.
    assert vi.interpret_view("", WORLD) == vi.EMPTY_CONFIG
    assert vi.interpret_view("   ", WORLD) == vi.EMPTY_CONFIG
