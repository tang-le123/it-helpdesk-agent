# 技术文档

本项目是「企业内部 IT 服务台 Agent」：员工用自然语言查工单、查设备、查制度，或提交权限、软件、密码申请。文档只写仓库里真实存在的行为。

| 文档 | 内容 |
|:---|:---|
| [学习手册](STUDY_GUIDE.md) | 19 章、2.2k 行：从请求链路到二次开发的完整教材 |
| [01 · 架构](01-architecture.md) | 请求链路、LangGraph 节点、五路分流、降级 |
| [02 · 工具与人工确认](02-tools-and-hitl.md) | 10 个工具、风险分级、审批与幂等 |
| [03 · 评测](03-evaluation.md) | 数据集、指标口径、已知限制 |
| [04 · 部署](04-deployment.md) | 本地运行、Docker、环境变量 |

代码入口：`app/asgi.py` → `app/services/chat_service.py` → `app/agents/graph.py`。
