from app.services.prompt_service import parse_llm_json


def test_parse_strips_fences() -> None:
    raw = "```json\n{\"process\": {\"id\": \"demo\", \"name\": \"Demo\"}, \"nodes\": [], \"flows\": []}\n```"
    data = parse_llm_json(raw)
    assert data["process"]["id"] == "demo"


def test_parse_rejects_plain_text() -> None:
    try:
        parse_llm_json("not json at all")
    except ValueError:
        return
    raise AssertionError("expected ValueError")
