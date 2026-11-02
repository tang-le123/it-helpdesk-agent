"""Software tools: installation and licence requests."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.enums import ApprovalKind, ToolRisk
from app.schemas.agent import ToolResult
from app.tools.base import Tool, ToolContext
from app.tools.deps import RepositoryBackedTool


class SoftwareRequestInput(BaseModel):
    software: str = Field(
        min_length=2,
        max_length=64,
        description="软件名称，如 Figma、MATLAB、Docker Desktop；不要填版本号代替名称",
    )
    version: str = Field(
        default="",
        max_length=32,
        description="需要的版本，留空表示由 IT 决定稳定版",
    )
    reason: str = Field(
        default="",
        max_length=200,
        description="业务用途，如「原型评审需要」；不要填工单号",
    )


class RequestSoftwareTool(RepositoryBackedTool, Tool):
    name = "request_software"
    description = (
        "提交软件安装或 License 申请（write，须用户确认；生成审批单，不直接安装）。"
        "何时用：用户要装白名单外的软件，或申请付费 License（Figma、MATLAB、JetBrains 等）。"
        "何时不用：白名单软件引导用户走公司门户自助安装；问安装规则用 search_knowledge。"
        "参数 software：软件名；version：可选；reason：业务用途。"
        "返回 approval_id、approver_role、expires_at；告知审批通过后由 IT 推送安装。"
    )
    risk = ToolRisk.WRITE
    input_model = SoftwareRequestInput

    async def execute(self, parsed: SoftwareRequestInput, context: ToolContext) -> ToolResult:
        output = await self.repository.create_approval(
            requester_id=context.user_id,
            kind=ApprovalKind.SOFTWARE_INSTALL,
            target=parsed.software,
            payload={
                "software": parsed.software,
                "version": parsed.version,
                "reason": parsed.reason,
            },
            approver_role="it_admin",
            ttl_hours=72,
            trace_id=context.trace_id,
        )
        return ToolResult(name=self.name, success=True, output=output, risk=self.risk)
