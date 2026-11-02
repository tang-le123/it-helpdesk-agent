"""High-precision lexical overlay applied after the LLM intent classifier.

The LLM remains the primary classifier. Overlay only fires on phrases that are
stable in Chinese IT service desks and that historically confuse nearby labels
(ticket status vs policy, access request vs policy, incident vs complaint).
"""

from __future__ import annotations

import re

from app.core.enums import IntentLabel

_GREETING_ONLY = re.compile(
    r"^(你好|您好|hi|hello|嗨|哈喽|早上好|下午好)(，?(在吗|有人吗))?[!！。.~]*$",
    re.IGNORECASE,
)

_JAILBREAK = (
    "ignore previous",
    "ignore all previous",
    "jailbreak",
    "系统提示词",
    "你的提示词",
    "开发者模式",
)
_OOS = (
    "股市",
    "炒股",
    "写作业",
    "医疗诊断",
    "看病",
    "法律咨询",
    "选总统",
    "造炸弹",
    "工资条",
    "报销",
    "招聘",
    "离职补偿",
    "翻译合同",
)
_HANDOFF = (
    "转人工",
    "人工客服",
    "找人工",
    "接人工",
    "找工程师",
    "叫工程师",
    "值班经理",
    "升级处理",
    "转二线",
)
_CHITCHAT = (
    "今天天气",
    "讲个笑话",
    "你是谁",
    "你叫什么",
    "是不是机器人",
    "吃什么",
    "在忙什么",
    "周末去哪",
)
_COMPLAINT = ("投诉", "差评", "态度太差", "推诿", "没人管", "敷衍", "骂人")
_TICKET_ID = re.compile(r"\bTKT\d{4,}\b", re.IGNORECASE)
_ASSET_ID = re.compile(r"\bAST\d{4,}\b", re.IGNORECASE)
_TICKET_STRONG = ("我的工单", "工单进度", "工单状态", "处理到哪", "什么时候修好")
_ASSET_QUERY = (
    "资产编号",
    "设备归属",
    "序列号",
    "谁的电脑",
    "这台电脑",
    "保修到",
    "我的资产",
    "我的设备",
)
_ACCESS = ("权限", "开通", "加权限", "账号被锁", "申请账号", "解锁", "密码重置", "重置")
_SOFTWARE = (
    "安装软件",
    "装软件",
    "软件安装",
    "license",
    "许可",
    "figma",
    "matlab",
    "docker",
    "jetbrains",
)
_INCIDENT = (
    "报修",
    "报障",
    "坏了",
    "连不上",
    "打不开",
    "蓝屏",
    "黑屏",
    "开不了机",
    "死机",
    "断网",
    "中毒",
    "卡死",
)
_FAQ = (
    "流程",
    "规则",
    "政策",
    "条件",
    "时效",
    "多久",
    "有效期",
    "多少位",
    "几位",
    "哪些材料",
    "标准",
    "sla",
)
_POLICY_HINTS = (
    "规则",
    "政策",
    "流程",
    "条件",
    "标准",
    "时效",
    "多久",
    "有效期",
    "多少位",
    "几位",
    "哪些",
    "是否",
    "可以吗",
    "能不能",
)
# Only strong action verbs suppress the policy check; "报修流程" is still FAQ.
_ACTION_HINTS = ("帮我", "开通", "重置", "解锁", "提交", "给我开", "建单", "加权限")


def _has(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def high_precision_intent(query: str) -> IntentLabel | None:
    """Return a label only when the rule is confident; otherwise None."""
    text = query.strip()
    if not text:
        return None
    lowered = text.lower()

    if _has(lowered, _JAILBREAK) or _has(text, _OOS):
        return IntentLabel.OUT_OF_SCOPE
    if _has(text, _HANDOFF):
        return IntentLabel.HUMAN_HANDOFF
    if _GREETING_ONLY.match(text) or _GREETING_ONLY.match(lowered):
        return IntentLabel.GREETING
    if _has(text, _CHITCHAT):
        return IntentLabel.CHITCHAT
    if _has(text, _COMPLAINT):
        return IntentLabel.COMPLAINT
    if _TICKET_ID.search(text):
        return IntentLabel.TICKET_STATUS
    if _ASSET_ID.search(text):
        return IntentLabel.ASSET_QUERY
    # Strong ownership phrases beat the policy check: "我的工单有哪些" is a
    # status query even though "哪些" also appears in policy questions.
    if _has(text, _TICKET_STRONG):
        return IntentLabel.TICKET_STATUS
    if _has(text, _ASSET_QUERY):
        return IntentLabel.ASSET_QUERY
    # "离职账号怎么回收 / 外包和正式有什么区别" is a process question, not a request.
    if ("离职" in text or "外包" in text) and _has(text, ("怎么", "如何", "区别", "流程", "多久")):
        return IntentLabel.FAQ_POLICY
    # A pure "how long / what rule" question stays FAQ even when it mentions
    # accounts or passwords, unless it also asks to change something.
    if _has(text, _POLICY_HINTS) and not _has(text, _ACTION_HINTS):
        return IntentLabel.FAQ_POLICY
    if _has(text, _ACCESS):
        return IntentLabel.ACCESS_REQUEST
    if _has(
        lowered, ("figma", "matlab", "docker", "jetbrains", "license", "postman", "zoom", "vscode")
    ) or _has(text, _SOFTWARE):
        return IntentLabel.SOFTWARE_REQUEST
    if _has(text, _INCIDENT):
        return IntentLabel.INCIDENT_REPORT
    if _has(text, _FAQ):
        return IntentLabel.FAQ_POLICY
    return None


def apply_intent_overlay(query: str, label: IntentLabel) -> tuple[IntentLabel, str | None]:
    forced = high_precision_intent(query)
    if forced is None or forced == label:
        return label, None
    return forced, f"overlay:{forced.value}"
