import pytest

from app.agents.nodes.generate import generate_node
from app.agents.nodes.intent import IntentClassifier, rule_based_intent
from app.core.enums import IntentLabel, RetrievalStrategy
from app.providers.fake import OfflineLLMProvider
from app.schemas.retrieval import RetrievedChunk


def test_greeting_prefix_does_not_hide_incident_intent() -> None:
    intent = rule_based_intent("你好，我想报修，显示器坏了")
    assert intent.label != IntentLabel.GREETING


@pytest.mark.asyncio
async def test_offline_classifier_uses_rules_not_fake_json() -> None:
    intent = await IntentClassifier(OfflineLLMProvider()).classify("报修流程是什么？")
    assert intent.label == IntentLabel.FAQ_POLICY


@pytest.mark.asyncio
async def test_offline_answer_quotes_evidence_instead_of_test_json() -> None:
    chunk = RetrievedChunk(
        chunk_id="chunk-1",
        document_id="vpn_troubleshoot",
        title="VPN 常见故障排查",
        content="提示证书过期时，请升级 GlobalProtect 到 6.1；仍失败提 P3 工单。",
        score=1.0,
    )
    result = await generate_node(
        {
            "user_query": "VPN 证书过期怎么办？",
            "strategy": RetrievalStrategy.SINGLE,
            "retrieved_chunks": [chunk],
        },
        OfflineLLMProvider(),
    )
    assert "证书" in result["final_answer"]
    assert "label" not in result["final_answer"]
    assert result["citations"][0].chunk_id == "chunk-1"
