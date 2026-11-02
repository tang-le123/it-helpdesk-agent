"""Asset tools: device ownership, model and warranty lookup."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import ToolRisk
from app.schemas.agent import ToolResult
from app.schemas.ticket import Asset
from app.tools.base import NoArgsInput, Tool, ToolContext
from app.tools.deps import RepositoryBackedTool


class AssetIdInput(BaseModel):
    asset_id: str = Field(
        min_length=5,
        max_length=32,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="资产编号，如 AST10001；不要填工单号 TKT10001 或序列号",
    )


def _asset_summary(asset: Asset) -> dict[str, Any]:
    return {
        "asset_id": asset.asset_id,
        "asset_type": asset.asset_type,
        "model": asset.model,
        "serial_no": asset.serial_no,
        "owner_user_id": asset.owner_user_id,
        "status": asset.status.value,
        "warranty_until": asset.warranty_until.isoformat() if asset.warranty_until else None,
        "location": asset.location,
    }


class GetAssetTool(RepositoryBackedTool, Tool):
    name = "get_asset"
    description = (
        "按资产编号查询设备型号、序列号、归属人、状态和保修到期日。只读。"
        "何时用：问「这台电脑是谁的」「我的 MacBook 保修到什么时候」「AST10001 什么型号」。"
        "何时不用：查工单进度用 get_ticket；问报修流程用 search_knowledge；不知道资产号先 list_my_assets。"
        "参数 asset_id：形如 AST10001，不是工单号 TKT10001，也不是设备序列号。"
        "返回 asset_id、asset_type、model、serial_no、owner_user_id、status、warranty_until、location；"
        "status 取值 in_use/in_stock/repairing/retired/lost。"
    )
    risk = ToolRisk.READ
    input_model = AssetIdInput

    async def execute(self, parsed: AssetIdInput, context: ToolContext) -> ToolResult:
        asset = await self.repository.get_visible_asset(parsed.asset_id, context.user_id)
        return ToolResult(name=self.name, success=True, output=_asset_summary(asset))


class ListMyAssetsTool(RepositoryBackedTool, Tool):
    name = "list_my_assets"
    description = (
        "列出当前用户名下全部 IT 资产（笔记本、显示器、外设）。只读。"
        "何时用：用户说「我名下有哪些设备」「我的资产有哪些」但没给资产号。"
        "何时不用：已知资产号用 get_asset；查工单用 list_my_tickets。"
        "无需参数；返回 assets[]，每条含 asset_id、asset_type、model、status、warranty_until。"
    )
    risk = ToolRisk.READ
    input_model = NoArgsInput

    async def execute(self, parsed: NoArgsInput, context: ToolContext) -> ToolResult:
        assets = await self.repository.list_assets_for_user(context.user_id, limit=10)
        return ToolResult(
            name=self.name,
            success=True,
            output={
                "assets": [
                    {
                        "asset_id": asset.asset_id,
                        "asset_type": asset.asset_type,
                        "model": asset.model,
                        "status": asset.status.value,
                        "warranty_until": (
                            asset.warranty_until.isoformat() if asset.warranty_until else None
                        ),
                    }
                    for asset in assets
                ]
            },
        )
