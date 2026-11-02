import pytest

from app.agents.nodes.intent_overlay import high_precision_intent
from app.core.enums import IntentLabel

CASES: list[tuple[str, IntentLabel]] = [
    ("你好", IntentLabel.GREETING),
    ("今天天气真好", IntentLabel.CHITCHAT),
    ("帮我转人工", IntentLabel.HUMAN_HANDOFF),
    ("你们 IT 什么态度，我要投诉", IntentLabel.COMPLAINT),
    ("TKT10001 处理到哪了", IntentLabel.TICKET_STATUS),
    ("我的工单什么时候能修好", IntentLabel.TICKET_STATUS),
    ("AST10001 是谁的电脑", IntentLabel.ASSET_QUERY),
    ("我的 MacBook 保修到什么时候", IntentLabel.ASSET_QUERY),
    ("帮我申请 CRM 客户导出权限", IntentLabel.ACCESS_REQUEST),
    ("账号被锁了怎么解锁", IntentLabel.ACCESS_REQUEST),
    ("帮我装 Figma", IntentLabel.SOFTWARE_REQUEST),
    ("VPN 连不上怎么办", IntentLabel.INCIDENT_REPORT),
    ("电脑蓝屏了", IntentLabel.INCIDENT_REPORT),
    ("报修流程是什么", IntentLabel.FAQ_POLICY),
    ("离职流程是什么", IntentLabel.FAQ_POLICY),
    ("外包账号有效期多久", IntentLabel.FAQ_POLICY),
    ("密码要多少位", IntentLabel.FAQ_POLICY),
    ("帮我写作业", IntentLabel.OUT_OF_SCOPE),
    ("今天股市怎么样", IntentLabel.OUT_OF_SCOPE),
]


@pytest.mark.parametrize(("query", "expected"), CASES)
def test_overlay_matches_high_precision_cases(query: str, expected: IntentLabel) -> None:
    assert high_precision_intent(query) == expected


def test_overlay_returns_none_when_unsure() -> None:
    assert high_precision_intent("这个怎么弄") is None
    assert high_precision_intent("") is None
