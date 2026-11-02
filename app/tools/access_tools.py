"""Access and credential tools: permission requests and password resets.

Both tools only *stage* an approval. Nothing is granted or changed until a human
approves it, which is the whole point of the HITL flow in this project.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.enums import ApprovalKind, ToolRisk
from app.schemas.agent import ToolResult
from app.tools.base import Tool, ToolContext
from app.tools.deps import RepositoryBackedTool

_HIGH_RISK_SCOPES = ("导出", "付款", "生产", "管理员", "密钥", "root")


class AccessRequestInput(BaseModel):
    system: str = Field(
        min_length=2,
        max_length=32,
        description="目标系统：CRM、ERP、GitLab、飞书、VPN 或其他系统名",
    )
    scope: str = Field(
        min_length=2,
        max_length=60,
        description="权限点，如「客户导出」「采购审批」「代码库写权限」；不要填账号或密码",
    )
    duration_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="申请有效期（天），默认 30，最长 365",
    )
    reason: str = Field(
        default="",
        max_length=200,
        description="业务用途，如「季度客户回访需要导出客户列表」；不要填工单号",
    )


class PasswordResetInput(BaseModel):
    account: str = Field(
        default="",
        max_length=64,
        description="要重置的账号（工号或邮箱），留空表示本人账号",
    )
    reason: str = Field(
        default="",
        max_length=200,
        description="原因，如「忘记密码」「账号被锁定」「更换手机后 MFA 丢失」",
    )


class RequestAccessTool(RepositoryBackedTool, Tool):
    name = "request_access"
    description = (
        "提交业务系统权限申请（write，须用户确认；确认后只生成审批单，不是立即开通）。"
        "何时用：用户要申请 CRM/ERP/GitLab/飞书/VPN 的权限，如客户导出、采购审批、代码库写权限。"
        "何时不用：只是问权限规则用 search_knowledge；查已有工单用 get_ticket；改密码用 reset_password。"
        "参数 system：系统名；scope：权限点；duration_days：1–365，默认 30；reason：业务用途。"
        "返回 approval_id、approver_role、expires_at；告知需主管或信息安全组审批，不要说权限已开通。"
    )
    risk = ToolRisk.WRITE
    input_model = AccessRequestInput

    async def execute(self, parsed: AccessRequestInput, context: ToolContext) -> ToolResult:
        high_risk = any(token in parsed.scope for token in _HIGH_RISK_SCOPES)
        output = await self.repository.create_approval(
            requester_id=context.user_id,
            kind=ApprovalKind.ACCESS,
            target=f"{parsed.system}·{parsed.scope}",
            payload={
                "system": parsed.system,
                "scope": parsed.scope,
                "duration_days": parsed.duration_days,
                "reason": parsed.reason,
            },
            approver_role="security" if high_risk else "manager",
            ttl_hours=48 if high_risk else 72,
            trace_id=context.trace_id,
        )
        output["high_risk"] = high_risk
        return ToolResult(name=self.name, success=True, output=output, risk=self.risk)


class ResetPasswordTool(RepositoryBackedTool, Tool):
    name = "reset_password"
    description = (
        "提交密码重置或账号解锁申请（write，须用户确认；生成审批单，不直接改密）。"
        "何时用：用户忘记密码、账号被锁、换手机后 MFA 丢失，且自助重置失败。"
        "何时不用：只是问密码规则用 search_knowledge；用户能自助重置时引导到飞书自助入口。"
        "参数 account：要重置的账号，留空表示本人；reason：原因。"
        "返回 approval_id、approver_role、expires_at；临时密码审批通过后经飞书发送，不要声称已经重置。"
    )
    risk = ToolRisk.WRITE
    input_model = PasswordResetInput

    async def execute(self, parsed: PasswordResetInput, context: ToolContext) -> ToolResult:
        target = parsed.account.strip() or "本人账号"
        output = await self.repository.create_approval(
            requester_id=context.user_id,
            kind=ApprovalKind.PASSWORD_RESET,
            target=target,
            payload={"account": target, "reason": parsed.reason},
            approver_role="it_admin",
            ttl_hours=24,
            trace_id=context.trace_id,
        )
        output["delivery"] = "临时密码将在审批通过后通过飞书发送"
        return ToolResult(name=self.name, success=True, output=output, risk=self.risk)
