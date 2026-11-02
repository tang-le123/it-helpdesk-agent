from app.skills.loader import match_skill


def test_match_skill_by_trigger() -> None:
    skill = match_skill("VPN 连不上，帮我报修", "faq_policy")
    assert skill is not None
    assert skill["name"] == "incident_triage"
    assert "create_ticket" in skill["tools"]


def test_match_skill_by_intent_when_no_trigger() -> None:
    skill = match_skill("转换 CSV 格式", "software_request")
    assert skill is not None
    assert skill["name"] == "software_request"


def test_no_skill_for_chitchat() -> None:
    assert match_skill("今天天气真好", "chitchat") is None
