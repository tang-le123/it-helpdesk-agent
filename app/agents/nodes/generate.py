"""Answer generation and refusal nodes."""

from __future__ import annotations

import json
import time

from pydantic import BaseModel, Field

from app.agents.state import AgentState
from app.core.enums import RetrievalStrategy
from app.core.exceptions import LLMOutputError, LLMProviderError
from app.prompts.answer import ANSWER_SYSTEM, ANSWER_USER
from app.providers.base import LLMProvider
from app.providers.fake import OfflineLLMProvider
from app.providers.json_parser import parse_model
from app.schemas.common import LatencyBreakdown, TokenUsage
from app.schemas.retrieval import Citation


class AnswerPayload(BaseModel):
    answer: str
    citation_chunk_ids: list[str] = Field(default_factory=list)
    refused: bool = False


async def generate_node(state: AgentState, llm: LLMProvider) -> dict:
    started = time.perf_counter()
    chunks = state.get("retrieved_chunks") or []
    tools = state.get("tool_results") or []
    if tools and all(not tool.success for tool in tools):
        return {
            "final_answer": "暂时无法查到相关记录，请核对工单号或资产号，或稍后重试。",
            "citations": [],
        }
    pending = state.get("pending_action")
    if (state.get("extra") or {}).get("missing_slot"):
        return {
            "final_answer": "请补充必要信息（如工单号、系统或权限点），确认后我才能继续。",
            "citations": [],
        }
    if pending:
        answer = pending.summary
        latency = state.get("latency") or LatencyBreakdown()
        latency.llm_ms = (time.perf_counter() - started) * 1000
        return {
            "final_answer": answer,
            "citations": [],
            "refused": False,
            "latency": latency,
        }
    evidence = (
        "\n\n".join(f"[{c.chunk_id}] {c.title}\n{c.content}" for c in chunks[:6]) or "(无检索结果)"
    )
    tool_text = json.dumps([t.model_dump() for t in tools], ensure_ascii=False) if tools else "(无)"
    intent = state.get("intent")
    strategy = state.get("strategy") or RetrievalStrategy.DIRECT
    if isinstance(llm, OfflineLLMProvider):
        answer, citation_ids = _offline_answer(state)
        citations = [
            Citation(
                document_id=chunk.document_id,
                title=chunk.title,
                chunk_id=chunk.chunk_id,
                section=chunk.section,
            )
            for chunk in chunks
            if chunk.chunk_id in citation_ids
        ]
        return {"final_answer": answer, "citations": citations, "refused": False}
    messages = [
        {"role": "system", "content": ANSWER_SYSTEM},
        {
            "role": "user",
            "content": ANSWER_USER.format(
                query=state["user_query"],
                intent=intent.label.value if intent else "unknown",
                strategy=strategy.value,
                evidence=evidence,
                tool_results=tool_text,
            ),
        },
    ]
    try:
        response = await llm.generate(
            messages,
            temperature=0.2,
            max_tokens=700,
            response_format={"type": "json_object"},
        )
        payload = parse_model(response.content, AnswerPayload)
        usage = response.usage
    except (LLMProviderError, LLMOutputError):
        payload = AnswerPayload(
            answer=_extractive_fallback(state["user_query"], evidence, tool_text),
            citation_chunk_ids=[chunks[0].chunk_id] if chunks else [],
        )
        usage = TokenUsage()
    citations = [
        Citation(
            document_id=chunk.document_id,
            title=chunk.title,
            chunk_id=chunk.chunk_id,
            section=chunk.section,
        )
        for chunk in chunks
        if chunk.chunk_id in set(payload.citation_chunk_ids)
    ]
    latency = state.get("latency") or LatencyBreakdown()
    latency.llm_ms = (time.perf_counter() - started) * 1000
    prev_usage = state.get("token_usage") or TokenUsage()
    merged = TokenUsage(
        prompt_tokens=prev_usage.prompt_tokens + usage.prompt_tokens,
        completion_tokens=prev_usage.completion_tokens + usage.completion_tokens,
        total_tokens=prev_usage.total_tokens + usage.total_tokens,
    )
    return {
        "final_answer": payload.answer,
        "citations": citations,
        "refused": payload.refused,
        "latency": latency,
        "token_usage": merged,
    }


async def refuse_node(state: AgentState) -> dict:
    return {
        "final_answer": "这个问题超出 IT 服务台范围，我无法协助。可以问我账号、设备、网络、软件或流程相关的问题。",
        "refused": True,
        "citations": [],
    }


def _extractive_fallback(query: str, evidence: str, tool_text: str) -> str:
    if evidence and evidence != "(无检索结果)":
        snippet = evidence.split("\n", 1)[-1][:240].strip()
        return f"暂时无法生成完整答复。相关资料节选：\n\n> {snippet}\n\n请以原文为准。"
    if tool_text and tool_text != "(无)":
        return "已查询到系统数据，但暂时无法可靠地整理答复。请稍后重试或转人工。"
    return "暂时无法基于现有信息给出可靠答复，请补充相关信息或转人工。"


def _offline_answer(state: AgentState) -> tuple[str, set[str]]:
    """Use only retrieved text or whitelisted tool fields when no LLM is configured."""
    strategy = state.get("strategy")
    if strategy == RetrievalStrategy.DIRECT:
        return "你好，我可以帮你查工单、查设备、查流程，也能提交权限、软件和密码申请。", set()

    for result in state.get("tool_results") or []:
        if not result.success:
            continue
        data = result.output
        if result.name == "create_ticket":
            return (
                f"已创建工单 {data.get('ticket_id', '')}，优先级 "
                f"{str(data.get('priority', '')).upper()}，"
                f"处理组：{data.get('assignee_group') or '待分派'}。",
                set(),
            )
        if result.name == "request_access":
            return (
                f"已提交权限申请 {data.get('approval_id', '')}（{data.get('target', '')}），"
                f"需 {data.get('approver_role', '主管')} 审批后生效。",
                set(),
            )
        if result.name == "reset_password":
            return (
                f"已提交密码重置申请 {data.get('approval_id', '')}，"
                "审批通过后临时密码将通过飞书发送。",
                set(),
            )
        if result.name == "request_software":
            return (
                f"已提交 {data.get('target', '该软件')} 的安装申请 "
                f"{data.get('approval_id', '')}，审批通过后由 IT 推送安装。",
                set(),
            )
        if result.name == "get_ticket":
            status = {
                "open": "待处理",
                "in_progress": "处理中",
                "pending_approval": "待审批",
                "resolved": "已解决",
                "closed": "已关闭",
                "cancelled": "已取消",
            }.get(str(data.get("status")), "未知")
            latest = data.get("latest_event") or {}
            note = f"最近进展：{latest.get('content')}" if latest.get("content") else ""
            return f"工单 {data.get('ticket_id', '')} 当前状态：{status}。{note}", set()
        if result.name == "get_asset":
            owner = data.get("owner_user_id") or "未分配"
            return (
                f"资产 {data.get('asset_id', '')} 是 {data.get('model', '')}，"
                f"归属：{owner}，状态：{data.get('status', '未知')}。",
                set(),
            )
        if result.name in {"list_my_tickets", "list_my_assets"}:
            items = data.get("tickets") or data.get("assets") or []
            ids = [
                str(item.get("ticket_id") or item.get("asset_id"))
                for item in items
                if isinstance(item, dict)
            ][:3]
            suffix = ("：" + "、".join(ids)) if ids else ""
            return f"共查询到 {len(items)} 条记录{suffix}。", set()
        if result.name == "escalate_to_human":
            return "已为你转接人工 IT 工程师，正在排队。", set()
        if result.name == "search_knowledge":
            found = data.get("chunks") or []
            if found and isinstance(found[0], dict):
                item = found[0]
                title = str(item.get("title") or "相关制度")
                excerpt = str(item.get("content") or "").strip()[:260]
                return (
                    f"暂时无法生成完整回答。找到《{title}》中的资料节选，请核对原文：\n\n> {excerpt}",
                    set(),
                )

    chunks = state.get("retrieved_chunks") or []
    if chunks:
        chunk = chunks[0]
        excerpt = chunk.content.strip()[:260]
        return (
            f"暂时无法生成完整回答，以下是《{chunk.title}》的资料节选，请核对原文：\n\n> {excerpt}",
            {chunk.chunk_id},
        )
    return (
        "当前无法可靠回答这个问题。请补充相关信息，或转人工 IT 工程师。",
        set(),
    )
