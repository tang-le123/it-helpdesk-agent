# 02 · 工具与人工确认

## 工具清单

| 工具 | 风险 | 说明 |
|:---|:---:|:---|
| `get_ticket` | READ | 按工单号查状态、优先级、处理组、SLA、最近进展 |
| `list_my_tickets` | READ | 本人最近 5 张工单 |
| `get_asset` | READ | 设备型号、序列号、归属、保修 |
| `list_my_assets` | READ | 本人名下资产 |
| `search_knowledge` | READ | 检索 31 篇 SOP |
| `create_ticket` | WRITE | 建单，按分类派组、按优先级算 SLA |
| `request_access` | WRITE | 权限申请审批单；高危加签信息安全组 |
| `reset_password` | WRITE | 密码重置审批单 |
| `request_software` | WRITE | 软件安装 / License 审批单 |
| `escalate_to_human` | EXTERNAL | 转二线并登记原因 |

MCP 侧另有 `mcp_service_hours`（值班时间）与 `mcp_change_calendar`（变更窗口）。

## 写操作生命周期

```text
员工: "帮我申请 CRM 客户导出权限"
  → planner 找到 request_access（WRITE）
  → executor 因未确认拒绝执行
  → 返回 pending_action{action_id, tool_name, arguments, summary}
员工: "确认执行" + action_id
  → ChatService 校验 session / user / 过期时间
  → planner 直接产出单步计划
  → executor 带 confirmed_action_id 执行
  → 写 approval 表 + idempotency 表 + audit 表
```

- **权限**：`app/tools/permissions.py`，WRITE / DESTRUCTIVE 未确认直接抛 `ToolPermissionError`。
- **确认绑定**：`action_id` 与 session、user 绑定，换人换会话都失效；进程内保留 15 分钟。
- **幂等**：同一 action 重放时读 `idempotency_keys`，不重复建单。
- **审计**：每次写操作写 `audit_logs`，带 `trace_id`。

## 可见性

`get_visible_ticket` / `get_visible_asset` / `get_visible_approval` 对他人数据一律返回“不存在”，不暴露“你没有权限”，避免枚举。

## 审批链

| 操作 | 审批人 | 有效期 |
|:---|:---|:---:|
| 普通权限 | 直属主管 | 72h |
| 高危权限（导出/付款/生产库） | 信息安全组 | 48h |
| 密码重置 | IT 管理员 | 24h |
| 软件安装 | IT 管理员 | 72h |

审批单只是“已提交”，**不代表已开通**；真实系统接入点在 `app/repositories/ticket_repository.py` 的 `mark_approval_executed`。
