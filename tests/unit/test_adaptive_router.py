from app.agents.nodes.intent import rule_based_intent
from app.core.enums import IntentLabel, RetrievalStrategy
from app.retrieval.adaptive import rule_based_complexity
from app.schemas.agent import IntentResult


def _intent(label: IntentLabel) -> IntentResult:
    return IntentResult(label=label, confidence=0.9, prompt_version="test")


def test_greeting_goes_direct() -> None:
    intent = rule_based_intent("你好")
    assert intent.label == IntentLabel.GREETING
    routed = rule_based_complexity("你好", intent)
    assert routed.strategy == RetrievalStrategy.DIRECT


def test_ticket_id_goes_agent() -> None:
    routed = rule_based_complexity("TKT10001 处理到哪了", _intent(IntentLabel.TICKET_STATUS))
    assert routed.strategy == RetrievalStrategy.AGENT


def test_ticket_status_without_id_goes_agent() -> None:
    routed = rule_based_complexity("我的工单什么时候能修好", _intent(IntentLabel.TICKET_STATUS))
    assert routed.strategy == RetrievalStrategy.AGENT


def test_policy_question_stays_single() -> None:
    routed = rule_based_complexity("VPN 证书过期怎么办", _intent(IntentLabel.FAQ_POLICY))
    assert routed.strategy == RetrievalStrategy.SINGLE


def test_multi_hop_policy_goes_multi() -> None:
    query = "离职员工账号怎么回收，外包和正式员工有区别吗"
    routed = rule_based_complexity(query, _intent(IntentLabel.FAQ_POLICY))
    assert routed.strategy == RetrievalStrategy.MULTI


def test_incident_troubleshooting_is_single() -> None:
    routed = rule_based_complexity("电脑蓝屏了", _intent(IntentLabel.INCIDENT_REPORT))
    assert routed.strategy == RetrievalStrategy.SINGLE


def test_incident_with_explicit_request_goes_agent() -> None:
    routed = rule_based_complexity("帮我报修，显示器坏了", _intent(IntentLabel.INCIDENT_REPORT))
    assert routed.strategy == RetrievalStrategy.AGENT


def test_out_of_scope_refuses() -> None:
    routed = rule_based_complexity("帮我写作业", _intent(IntentLabel.OUT_OF_SCOPE))
    assert routed.strategy == RetrievalStrategy.REFUSE
