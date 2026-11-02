"""Complexity routing.

Mapping:
- simple      -> DIRECT (no retrieval) or REFUSE
- single_hop  -> SINGLE (one-shot hybrid retrieval)
- multi_hop   -> MULTI  (Self-RAG iterative retrieval)
- tool needs  -> AGENT  (planner + tools, optional retrieval)

The LLM classifier is preferred. The rule fallback keeps the system testable
and available when the model is down.
"""

from __future__ import annotations

import re

from app.core.constants import PROMPT_VERSION_COMPLEXITY
from app.core.enums import IntentLabel, QueryComplexity, RetrievalStrategy
from app.core.exceptions import LLMOutputError, LLMProviderError
from app.prompts.complexity import COMPLEXITY_SYSTEM, COMPLEXITY_USER
from app.providers.base import LLMProvider
from app.providers.fake import OfflineLLMProvider
from app.providers.json_parser import parse_model
from app.schemas.agent import ComplexityResult, IntentResult

_TICKET_ID = re.compile(r"\bTKT\d{4,}\b", re.IGNORECASE)
_ASSET_ID = re.compile(r"\bAST\d{4,}\b", re.IGNORECASE)

_MULTI_HOP_CUES = (
    "同时",
    "并且",
    "还是",
    "如果",
    "但是",
    "以及",
    "另外",
    "区别",
    "分别",
    "既",
    "又",
)
# An incident report only needs a ticket when the employee asks to file one;
# "电脑蓝屏怎么办" is a troubleshooting question for the SOP.
_WRITE_CUES = ("报修", "建单", "提工单", "提交工单", "帮我建", "申请", "开通", "重置")


def rule_based_complexity(query: str, intent: IntentResult) -> ComplexityResult:
    text = query.strip()
    label = intent.label

    if label == IntentLabel.OUT_OF_SCOPE:
        return ComplexityResult(
            complexity=QueryComplexity.OUT_OF_SCOPE,
            strategy=RetrievalStrategy.REFUSE,
            confidence=0.95,
            rationale="intent_out_of_scope",
        )
    if label in {IntentLabel.GREETING, IntentLabel.CHITCHAT}:
        return ComplexityResult(
            complexity=QueryComplexity.SIMPLE,
            strategy=RetrievalStrategy.DIRECT,
            confidence=0.9,
            rationale="social_or_greeting",
        )
    if _TICKET_ID.search(text) or _ASSET_ID.search(text):
        return ComplexityResult(
            complexity=QueryComplexity.TOOL_REQUIRED,
            strategy=RetrievalStrategy.AGENT,
            confidence=0.92,
            rationale="explicit_entity_id",
        )
    if label in {
        IntentLabel.TICKET_STATUS,
        IntentLabel.ASSET_QUERY,
        IntentLabel.ACCESS_REQUEST,
        IntentLabel.SOFTWARE_REQUEST,
        IntentLabel.HUMAN_HANDOFF,
        IntentLabel.COMPLAINT,
    }:
        return ComplexityResult(
            complexity=QueryComplexity.TOOL_REQUIRED,
            strategy=RetrievalStrategy.AGENT,
            confidence=0.85,
            rationale="account_or_action_intent",
        )
    if label == IntentLabel.INCIDENT_REPORT:
        if any(cue in text for cue in _WRITE_CUES):
            return ComplexityResult(
                complexity=QueryComplexity.TOOL_REQUIRED,
                strategy=RetrievalStrategy.AGENT,
                confidence=0.85,
                rationale="incident_needs_ticket",
            )
        return ComplexityResult(
            complexity=QueryComplexity.SINGLE_HOP,
            strategy=RetrievalStrategy.SINGLE,
            confidence=0.8,
            rationale="incident_troubleshooting",
        )

    hops = sum(1 for cue in _MULTI_HOP_CUES if cue in text)
    if hops >= 2 or (hops >= 1 and len(text) > 18):
        return ComplexityResult(
            complexity=QueryComplexity.MULTI_HOP,
            strategy=RetrievalStrategy.MULTI,
            confidence=0.75,
            rationale="multi_constraint_query",
        )
    return ComplexityResult(
        complexity=QueryComplexity.SINGLE_HOP,
        strategy=RetrievalStrategy.SINGLE,
        confidence=0.75,
        rationale="single_policy_or_faq",
    )


class AdaptiveRouter:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def route(self, query: str, intent: IntentResult) -> ComplexityResult:
        fallback = rule_based_complexity(query, intent)
        if isinstance(self._llm, OfflineLLMProvider):
            return fallback
        try:
            response = await self._llm.generate(
                [
                    {"role": "system", "content": COMPLEXITY_SYSTEM},
                    {
                        "role": "user",
                        "content": COMPLEXITY_USER.format(
                            query=query,
                            intent=intent.label.value,
                            prompt_version=PROMPT_VERSION_COMPLEXITY,
                        ),
                    },
                ],
                temperature=0.0,
                max_tokens=256,
                response_format={"type": "json_object"},
            )
            parsed = parse_model(response.content, ComplexityResult)
            # Explicit ids must always reach the tools, even if the model
            # classifies the sentence as a policy question.
            if _TICKET_ID.search(query) or _ASSET_ID.search(query):
                return fallback
            return parsed
        except (LLMProviderError, LLMOutputError):
            return fallback
