"""Planner that turns intent, skills and complexity into tool plans."""

from __future__ import annotations

import re

from app.agents.state import AgentState
from app.core.exceptions import LLMOutputError, LLMProviderError
from app.core.ids import new_id
from app.prompts.planner import PLANNER_SYSTEM, PLANNER_USER
from app.providers.base import LLMProvider
from app.providers.fake import OfflineLLMProvider
from app.providers.json_parser import parse_model
from app.schemas.agent import AgentPlan, PlanStep
from app.schemas.chat import ActionProposal
from app.skills.loader import match_skill
from app.tools.permissions import WRITE_RISKS
from app.tools.registry import ToolRegistry

_TICKET_RE = re.compile(r"TKT\d{4,}", re.IGNORECASE)
_ASSET_RE = re.compile(r"AST\d{4,}", re.IGNORECASE)
_ALWAYS_AVAILABLE = ("search_knowledge", "escalate_to_human")

_CATEGORY_CUES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("network", ("vpn", "wifi", "wi-fi", "断网", "网络", "邮箱", "代理", "连不上")),
    ("device", ("电脑", "显示器", "键盘", "鼠标", "扩展坞", "开机", "蓝屏", "设备")),
    ("software", ("软件", "安装", "figma", "matlab", "license", "许可")),
    ("security", ("钓鱼", "病毒", "泄露", "安全", "u 盘", "u盘")),
    ("account", ("密码", "账号", "权限", "mfa", "登录", "解锁")),
)


class Planner:
    def __init__(self, llm: LLMProvider, registry: ToolRegistry) -> None:
        self._llm = llm
        self._registry = registry

    def _tool_catalog(self, allowed: set[str] | None = None) -> str:
        lines = []
        for tool in self._registry.all():
            if allowed is not None and tool.name not in allowed:
                continue
            lines.append(f"- {tool.name}: {tool.description} [{tool.risk.value}]")
        return "\n".join(lines) or "- (no tools)"

    async def create_plan(self, query: str, intent_label: str, summary: str) -> AgentPlan:
        skill = match_skill(query, intent_label)
        allowed = _allowed_tools(skill, self._registry)
        if isinstance(self._llm, OfflineLLMProvider):
            return (
                skill_to_plan(skill, query, self._registry)
                if skill
                else _knowledge_fallback(query, self._registry)
            )
        try:
            response = await self._llm.generate(
                [
                    {
                        "role": "system",
                        "content": PLANNER_SYSTEM.format(
                            tools=self._tool_catalog(allowed),
                            skill_context=_format_skill(skill),
                        ),
                    },
                    {
                        "role": "user",
                        "content": PLANNER_USER.format(
                            query=query, intent=intent_label, summary=summary or "无"
                        ),
                    },
                ],
                temperature=0.0,
                max_tokens=512,
                response_format={"type": "json_object"},
            )
            plan = parse_model(response.content, AgentPlan)
            plan = _sanitize_plan(plan, self._registry, allowed)
            if plan.steps:
                if skill:
                    plan.rationale = f"skill:{skill['name']};{plan.rationale}"
                return plan
        except (LLMOutputError, LLMProviderError):
            pass
        if skill:
            return skill_to_plan(skill, query, self._registry)
        return _knowledge_fallback(query, self._registry)


def _allowed_tools(skill: dict | None, registry: ToolRegistry) -> set[str] | None:
    if skill is None:
        return None
    names = set(registry.names())
    allowed = {name for name in skill.get("tools", []) if name in names}
    allowed.update(name for name in _ALWAYS_AVAILABLE if name in names)
    return allowed or None


def _format_skill(skill: dict | None) -> str:
    if skill is None:
        return "无（通用工具集）"
    steps = "、".join(skill.get("steps") or [])
    tools = ", ".join(skill.get("tools") or [])
    return f"{skill['name']}：{skill.get('description', '')}。步骤：{steps}。工具：{tools}"


def _sanitize_plan(
    plan: AgentPlan,
    registry: ToolRegistry,
    allowed: set[str] | None,
) -> AgentPlan:
    names = set(registry.names())
    if allowed is not None:
        names = names & allowed
    steps = [step for step in plan.steps if not step.tool_name or step.tool_name in names]
    return AgentPlan(steps=steps[:6], rationale=plan.rationale)


def skill_to_plan(skill: dict, query: str, registry: ToolRegistry) -> AgentPlan:
    steps: list[PlanStep] = []
    for index, tool_name in enumerate(skill.get("tools", []), start=1):
        if tool_name not in registry.names():
            continue
        arguments = _tool_arguments(tool_name, query)
        # Without an explicit id, get_ticket/get_asset cannot run; the paired
        # list_* tool is the right fallback and is already in the skill.
        if tool_name in {"get_ticket", "get_asset"} and not arguments:
            continue
        steps.append(
            PlanStep(
                step_id=index,
                goal=skill["name"],
                tool_name=tool_name,
                arguments=arguments,
                needs_retrieval=tool_name == "search_knowledge",
            )
        )
    if steps:
        return AgentPlan(steps=steps, rationale=f"skill:{skill['name']}")
    return _knowledge_fallback(query, registry)


def _tool_arguments(tool_name: str, query: str) -> dict:
    if tool_name == "search_knowledge":
        return {"query": query[:200]}
    if tool_name == "get_ticket":
        match = _TICKET_RE.search(query)
        return {"ticket_id": match.group(0).upper()} if match else {}
    if tool_name == "get_asset":
        match = _ASSET_RE.search(query)
        return {"asset_id": match.group(0).upper()} if match else {}
    if tool_name in {"list_my_tickets", "list_my_assets"}:
        return {}
    if tool_name == "create_ticket":
        return {
            "category": _guess_category(query),
            "priority": _guess_priority(query),
            "title": query[:80],
            "description": query[:200],
        }
    if tool_name == "request_access":
        return {
            "system": _guess_system(query),
            "scope": _guess_scope(query),
            "reason": query[:200],
        }
    if tool_name == "reset_password":
        return {"reason": query[:200]}
    if tool_name == "request_software":
        return {"software": query[:64], "reason": query[:200]}
    if tool_name == "escalate_to_human":
        return {"reason": query[:200]}
    return {}


def _guess_category(query: str) -> str:
    lowered = query.lower()
    for category, cues in _CATEGORY_CUES:
        if any(cue in lowered for cue in cues):
            return category
    return "other"


def _guess_priority(query: str) -> str:
    if any(cue in query for cue in ("全员", "整个部门", "全公司", "业务中断", "无法办公")):
        return "p1"
    if any(cue in query for cue in ("无法", "打不开", "坏了", "紧急", "蓝屏")):
        return "p2"
    return "p3"


def _guess_system(query: str) -> str:
    lowered = query.lower()
    for system in ("CRM", "ERP", "GitLab", "飞书", "VPN"):
        if system.lower() in lowered:
            return system
    return "其他系统"


def _guess_scope(query: str) -> str:
    """Turn "帮我申请 CRM 客户导出权限" into "客户导出"."""
    text = query.strip()
    for prefix in ("帮我申请", "我要开通", "帮我开通", "给我开个", "申请", "开通", "加"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.replace("权限", "").strip("，,。 ")
    system = _guess_system(query)
    if system != "其他系统" and text.lower().startswith(system.lower()):
        text = text[len(system) :].strip("，,。 ")
    return text[:60] or query[:60]


def _knowledge_fallback(query: str, registry: ToolRegistry) -> AgentPlan:
    if "search_knowledge" in registry.names():
        return AgentPlan(
            steps=[
                PlanStep(
                    step_id=1,
                    goal="policy lookup",
                    tool_name="search_knowledge",
                    arguments={"query": query},
                    needs_retrieval=True,
                )
            ],
            rationale="fallback_knowledge",
        )
    return AgentPlan(steps=[], rationale="empty")


async def planner_node(state: AgentState, planner: Planner) -> dict:
    confirmed = state.get("confirmed_action")
    if confirmed is not None:
        return {
            "plan": AgentPlan(
                steps=[
                    PlanStep(
                        step_id=1,
                        goal="confirmed action",
                        tool_name=confirmed.tool_name,
                        arguments=confirmed.arguments,
                    )
                ],
                rationale="confirmed_action",
            ),
            "pending_action": None,
        }
    intent = state.get("intent")
    plan = await planner.create_plan(
        state["user_query"],
        intent.label.value if intent else "faq_policy",
        state.get("summary") or "",
    )
    write_steps = [
        step
        for step in plan.steps
        if step.tool_name and planner._registry.get(step.tool_name).risk in WRITE_RISKS
    ]
    if any(
        _explicit_write_request(state["user_query"], step.tool_name or "") for step in write_steps
    ):
        if any(_missing_required_args(step) for step in write_steps):
            return {
                "plan": plan.model_copy(update={"steps": []}),
                "extra": {"missing_slot": True},
            }
    plan = plan.model_copy(
        update={
            "steps": [
                step
                for step in plan.steps
                if step not in write_steps
                or _explicit_write_request(state["user_query"], step.tool_name or "")
            ]
        }
    )
    pending = None
    for step in plan.steps:
        if not step.tool_name:
            continue
        tool = planner._registry.get(step.tool_name)
        if tool.risk in WRITE_RISKS and not state.get("confirm_action_id"):
            pending = ActionProposal(
                action_id=new_id("act_"),
                tool_name=tool.name,
                arguments=step.arguments,
                risk=tool.risk,
                summary=_action_summary(tool.name, step.arguments),
            )
            break
    return {"plan": plan, "pending_action": pending}


def _missing_required_args(step: PlanStep) -> bool:
    args = step.arguments
    if step.tool_name == "create_ticket":
        return not args.get("title")
    if step.tool_name == "request_access":
        return not (args.get("system") and args.get("scope"))
    if step.tool_name == "request_software":
        return not args.get("software")
    return False


def _explicit_write_request(query: str, tool_name: str) -> bool:
    if any(
        cue in query
        for cue in (
            "规则",
            "政策",
            "条件",
            "怎么",
            "能不能",
            "是否",
            "可以吗",
            "流程",
            "多久",
            "哪些",
        )
    ):
        return False
    lowered = query.lower()
    if tool_name == "create_ticket":
        return any(cue in query for cue in ("报修", "建单", "提工单", "提交工单", "帮我建", "报障"))
    if tool_name == "request_access":
        return "权限" in query and any(
            cue in query for cue in ("申请", "开通", "开", "要", "加", "给我")
        )
    if tool_name == "reset_password":
        return any(cue in query for cue in ("重置密码", "忘记密码", "密码忘了", "账号被锁", "解锁"))
    if tool_name == "request_software":
        if any(cue in query for cue in ("申请安装", "帮我装", "安装申请", "申请许可")):
            return True
        return any(cue in query for cue in ("装", "安装", "申请")) and any(
            cue in lowered for cue in ("软件", "license", "许可", "figma", "matlab", "docker")
        )
    return False


def _action_summary(tool_name: str, arguments: dict) -> str:
    if tool_name == "create_ticket":
        title = arguments.get("title") or "该问题"
        priority = str(arguments.get("priority") or "p3").upper()
        return f"确认后将创建 {priority} 工单「{title}」。请核对问题描述。"
    if tool_name == "request_access":
        return (
            f"确认后将提交 {arguments.get('system', '该系统')} 的权限申请"
            f"（{arguments.get('scope', '权限点')}），需审批通过后生效。"
        )
    if tool_name == "reset_password":
        return f"确认后将提交 {arguments.get('account') or '本人账号'} 的密码重置申请。"
    if tool_name == "request_software":
        return f"确认后将提交 {arguments.get('software', '该软件')} 的安装申请。"
    return "确认后将提交该操作。"
