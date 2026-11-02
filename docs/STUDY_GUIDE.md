# IT Helpdesk Agent 学习手册

> 一份可以对照源码阅读的工程手册。目标不是“知道它用了什么”，而是“能从一次员工提问，追到每一层代码，并说清为什么这样设计”。
>
> 适用版本：`afebfeb`（2026-11）· Python 3.12 · FastAPI · LangGraph · React

---

## 怎么读

这份手册按依赖顺序组织，建议从第 1 章顺着读：

1. **先建立地图**：第 1–3 章讲清项目是什么、怎么跑、代码怎么分层。
2. **再跟一条请求**：第 4–5 章从 HTTP 进入，逐节点走到回答落库。
3. **然后拆子系统**：第 6–8 章是“想清楚再检索”，第 9–12 章是“查数据、改数据、说人话”。
4. **最后看工程化**：第 13–17 章是安全、可靠性、评测、前端、部署。
5. **动手与复盘**：第 18 章是二次开发配方，第 19 章是排错与面试。

阅读约定：

- `文件路径` 都相对仓库根目录；函数名用反引号标注。
- 多数章节末尾有 **“调用关系”** 和 **“设计取舍”**，专门回答“这块和别的块怎么连”。
- 代码块只截关键分支，完整实现以源文件为准。

---

## 目录

- [第 1 章 项目全景](#第-1-章-项目全景)
- [第 2 章 十分钟跑起来](#第-2-章-十分钟跑起来)
- [第 3 章 目录、分层与依赖方向](#第-3-章-目录分层与依赖方向)
- [第 4 章 一次请求的完整生命周期](#第-4-章-一次请求的完整生命周期)
- [第 5 章 状态机与 LangGraph](#第-5-章-状态机与-langgraph)
- [第 6 章 意图识别与自适应路由](#第-6-章-意图识别与自适应路由)
- [第 7 章 检索链路](#第-7-章-检索链路)
- [第 8 章 Self-RAG 多跳](#第-8-章-self-rag-多跳)
- [第 9 章 领域模型与工具层](#第-9-章-领域模型与工具层)
- [第 10 章 写操作与人工确认](#第-10-章-写操作与人工确认)
- [第 11 章 生成、引用与忠实度](#第-11-章-生成引用与忠实度)
- [第 12 章 上下文预算与记忆压缩](#第-12-章-上下文预算与记忆压缩)
- [第 13 章 护栏与安全边界](#第-13-章-护栏与安全边界)
- [第 14 章 可靠性与可观测性](#第-14-章-可靠性与可观测性)
- [第 15 章 评测体系](#第-15-章-评测体系)
- [第 16 章 前端工作台](#第-16-章-前端工作台)
- [第 17 章 部署与配置](#第-17-章-部署与配置)
- [第 18 章 二次开发配方](#第-18-章-二次开发配方)
- [第 19 章 排错与面试复盘](#第-19-章-排错与面试复盘)

---

# 第 1 章 项目全景

## 1.1 它到底是什么

一句话：**企业内部 IT 服务台的智能体**。员工用自然语言问 IT，系统判断这个问题该“直接答、查一份 SOP、跨文档拼证据、调业务工具，还是拒绝”，并且把权限 / 软件 / 密码这类写操作变成**可审批、可审计**的动作。

它不是一个“把文档塞进向量库然后问答”的 demo。真正的差异在第二个问题之后：

- 问“你好”不该检索；
- 问“TKT10001 到哪了”必须查数据库，不能靠文档编；
- 问“帮我开权限”不能模型说了算，必须先出审批单；
- 查不到证据要拒答，而不是硬编。

## 1.2 五条处理路径

| 策略 | 典型输入 | 系统行为 | 对应节点 |
|:---|:---|:---|:---|
| `DIRECT` | “你好”“你是谁” | 不检索，直接答 | `generate_answer` |
| `SINGLE` | “VPN 证书过期怎么办” | 一轮混合检索 + 精排 | `retrieve_docs` |
| `MULTI` | “离职账号怎么回收，外包和正式有区别吗” | 多跳检索 + 自纠错 | `retrieve_docs`（Self-RAG） |
| `AGENT` | “TKT10001 处理到哪了”“帮我申请权限” | 规划 + 调工具 + 人工确认 | `plan_tasks` → `execute_tools` |
| `REFUSE` | “帮我写作业”“今天股市怎么样” | 越界拒答 | `refuse_answer` |

这套分流的思路是：**不是所有问题都值得走向量检索**，简单问题直接答，多跳问题才迭代检索。

## 1.3 能力清单

| 能力 | 落点 |
|:---|:---|
| 11 类意图识别 | `prompts/intent.py` + `nodes/intent.py` + `intent_overlay.py` |
| 混合检索（BM25 + bge + RRF） | `retrieval/` |
| 多跳与查询改写 | `retrieval/self_rag.py`、`query_rewrite.py` |
| 10 个业务工具 | `tools/` |
| 写操作审批 / 幂等 / 审计 | `nodes/planner.py`、`executor.py`、`repositories/` |
| 引用绑定与忠实度检查 | `nodes/generate.py`、`guardrails/hallucination.py` |
| 三级上下文压缩 | `memory/` |
| 分层降级与能力探测 | `services/container.py`、`api/routes/health.py` |
| 离线评测 | `eval/` |
| React 工作台 | `frontend/` |

## 1.4 技术栈与选型

| 层 | 选择 | 为什么 |
|:---|:---|:---|
| Web | FastAPI + SSE | 异步、原生 Pydantic、流式简单 |
| 编排 | LangGraph | 状态机显式，条件边比 if/else 链可读 |
| 模型 | DeepSeek `deepseek-chat` | OpenAI 兼容，中文与 JSON 输出稳定 |
| 向量 | `bge-small-zh-v1.5` | 512 维、~95MB，CPU 可跑 |
| 精排 | `bge-reranker-base`（可选） | Cross-Encoder，缺权重时词法回退 |
| 存储 | SQLite / PostgreSQL | 演示零依赖，生产可切 |
| 缓存 | 内存 / Redis | 检索结果短 TTL 缓存 |
| 向量库 | 内存 / Qdrant | 同上，按配置切换 |

**关键取舍**：所有外部依赖都可以缺失。没有 API Key 就离线回答；没有 Qdrant 就内存；没有 Cross-Encoder 就词法重排。降级不是异常，是设计的一部分。

## 1.5 和“玩具 RAG”的差别

| 维度 | 玩具版 | 本项目 |
|:---|:---|:---|
| 路由 | 全部走向量 | 五路分流，显式 ID 强制走工具 |
| 召回 | 单路 top-k | BM25（含标题/小节）+ 向量 + RRF |
| 多跳 | 一次检索 | 改写 → 补检 → 评估，最多 3 跳 |
| 写操作 | 模型直接调 | 权限 → 确认 → 幂等 → 审计 |
| 幻觉 | 直接返回 | 引用绑定 + 忠实度 + 自纠错 + 拒答 |
| 故障 | 直接失败 | 分层降级 + `/capabilities` 可见 |
| 评测 | 手测 | 100 意图 + 60 检索 + 20 端到端 |

## 1.6 学习路线

```text
第 1-3 章  建立地图：能跑、知道每个目录干什么
   ↓
第 4-5 章  跟一条请求：HTTP → ChatService → Graph → 落库
   ↓
第 6-8 章  想清楚：意图 → 路由 → 检索 → 多跳
   ↓
第 9-12 章 做事情：工具 → 审批 → 生成 → 记忆
   ↓
第 13-17 章 工程化：安全 → 可靠性 → 评测 → 前端 → 部署
   ↓
第 18-19 章 动手：改一个功能、排一次错、答一轮面试
```

---

# 第 2 章 十分钟跑起来

## 2.1 前置条件

- Python 3.11–3.12
- Node.js 20.19+ / 22.12+（只跑后端可不要）
- 可选：Docker Desktop（三档部署）、DeepSeek API Key（生成式回答）

## 2.2 三种启动方式

### 方式 A：一键脚本（Windows）

```bat
start.bat
```

脚本做四件事：用 `.venv` 起 API（8002）→ 起 Vite（5173）→ 轮询 `/health` → 打开浏览器。停止用 `stop.bat`。

需要真实 bge 权重：

```bat
start.bat -WithModels
```

### 方式 B：PyCharm

运行配置已内置：

| 配置 | 作用 |
|:---|:---|
| `API (uvicorn)` | 只起后端 8002 |
| `Web (vite)` | 只起前端 5173 |
| `Full stack` | 前后端一起 |

解释器选 `.venv\Scripts\python.exe`。也可以直接右键 `scripts/api.py` / `scripts/web.py` → Run。

### 方式 C：手动

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m uvicorn app.asgi:app --port 8002
```

前端另开一个终端：

```bash
cd frontend
npm ci
npm run dev
```

## 2.3 演示数据

`python scripts/seed_demo.py` 会写入 `u_demo` 名下：

| 类型 | 数据 |
|:---|:---|
| 工单 | `TKT10001` VPN 故障（处理中）、`TKT10002` Figma（已解决）、`TKT10003` CRM 权限（待审批） |
| 资产 | `AST10001` MacBook Pro 14、`AST10002` Dell U2723QE |
| 审批 | `APR10001` CRM 客户导出（pending） |

种子逻辑在 `app/services/seed.py`：先 `session.get` 判断存在再插入，所以可以重复执行。

## 2.4 四个验证请求

```bash
# 1) 健康
curl http://127.0.0.1:8002/api/v1/health

# 2) 政策问答（single + 引用）
curl -s http://127.0.0.1:8002/api/v1/chat \
  -H "content-type: application/json; charset=utf-8" \
  -d '{"message":"VPN 证书过期怎么办","user_id":"u_demo"}'

# 3) 工单查询（agent + 工具）
curl -s http://127.0.0.1:8002/api/v1/chat \
  -H "content-type: application/json; charset=utf-8" \
  -d '{"message":"TKT10001 处理到哪了","user_id":"u_demo"}'

# 4) 写操作（返回 pending_action，不执行）
curl -s http://127.0.0.1:8002/api/v1/chat \
  -H "content-type: application/json; charset=utf-8" \
  -d '{"message":"帮我申请 CRM 客户导出权限","user_id":"u_demo"}'
```

确认执行：

```bash
curl -s http://127.0.0.1:8002/api/v1/chat \
  -H "content-type: application/json; charset=utf-8" \
  -d '{"message":"确认执行","user_id":"u_demo","session_id":"<上一步的 session_id>","confirm_action_id":"<pending_action.action_id>"}'
```

## 2.5 五分钟内最容易踩的坑

| 现象 | 原因 | 处理 |
|:---|:---|:---|
| 中文请求体变成 `???` | 客户端未用 UTF-8 编码 | 显式 `charset=utf-8`；PowerShell 用 UTF-8 字节 |
| `llm: offline` | `.env` 没有 `DEEPSEEK_API_KEY` | 填 key 后重启 |
| 401 | key 不是 `sk-` 开头或已失效 | 到 DeepSeek 控制台重建 |
| 首次启动很慢 | 下载 bge / Cross-Encoder 权重 | 设 `LOCAL_EMBEDDING_ENABLED=false` 或 `HF_ENDPOINT=https://hf-mirror.com` |
| 端口占用 | 上次进程没退 | `stop.bat` |
| `ModuleNotFoundError` | 用了系统 Python | 用 `.venv` 或 `python -m pip install -e .` |

---

# 第 3 章 目录、分层与依赖方向

## 3.1 一句话请求路径

```text
HTTP / SSE → ChatService → LangGraph → 检索 或 工具 → Provider / DB
```

这四段对应四层：接口层 → 编排层 → 决策层 → 能力层。

## 3.2 分层职责

| 层 | 目录 | 职责 | 不该做什么 |
|:---|:---|:---|:---|
| 接口层 | `app/api/` | 参数校验、SSE、错误映射 | 不写业务判断 |
| 编排层 | `app/services/` | 会话、限流、确认、持久化、容器装配 | 不写检索算法 |
| 决策层 | `app/agents/` | 状态机、节点、路由、规划 | 不直接连数据库 |
| 能力层 | `app/retrieval/`、`app/tools/`、`app/providers/`、`app/repositories/` | 检索、工具、模型、存储 | 不感知 HTTP |
| 横切层 | `app/core/`、`app/guardrails/`、`app/memory/`、`app/observability/` | 异常、重试、安全、压缩、指标 | 不依赖上层 |

## 3.3 依赖方向

```text
api ──▶ services ──▶ agents ──▶ retrieval / tools / providers / repositories
                          │
                          └──▶ guardrails / memory
core / observability 被所有人依赖，但不依赖任何人
```

规则只有一条：**箭头不能反向**。`retrieval` 不认识 `ChatService`，`tools` 不认识 FastAPI；所以它们可以被单测、被 eval、被别的入口复用。

## 3.4 文件地图（先记 12 个）

| 文件 | 作用 |
|:---|:---|
| `app/asgi.py` | ASGI 入口，创建 app |
| `app/main.py` | FastAPI 装配、中间件、路由挂载 |
| `app/services/chat_service.py` | 一次对话的总导演 |
| `app/services/container.py` | 依赖注入与降级装配 |
| `app/agents/graph.py` | LangGraph 状态机 |
| `app/agents/state.py` | `AgentState` 字段契约 |
| `app/retrieval/hybrid.py` | BM25 + 向量 + RRF |
| `app/retrieval/self_rag.py` | 多跳循环 |
| `app/tools/factory.py` | 10 个工具的注册表 |
| `app/agents/nodes/executor.py` | 工具执行、权限、幂等 |
| `app/guardrails/hallucination.py` | 忠实度检查 |
| `app/repositories/ticket_repository.py` | 工单/资产/审批的读写 |

---

# 第 4 章 一次请求的完整生命周期

## 4.1 入口：FastAPI 与中间件

`app/asgi.py` 只做一件事：把 `app.main.create_app()` 暴露成 ASGI 应用。

`app/main.py` 在 lifespan 里构建容器：

```python
container = await build_container(settings)
app.state.container = container
```

同时注册两个中间件：

- **请求上下文**：从 `x-trace-id` / `x-request-id` 读取，没有就生成，写进 `contextvars`，供日志和指标使用。
- **异常映射**：`AppError` 统一转成 `{code, message}` JSON，避免把堆栈暴露给前端。

路由挂载：

```python
app.include_router(health.router, prefix=prefix)
app.include_router(chat.router, prefix=prefix)
app.include_router(admin.router, prefix=prefix)
```

## 4.2 JSON 与 SSE 两个入口

`app/api/routes/chat.py` 只有 36 行：

```python
@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request, container=Depends(get_container)):
    return await container.chat_service.chat(payload, trace_id=request.state.trace_id)
```

流式入口把 `ChatService.stream()` 的每个字典包成 `JSONServerSentEvent`。**接口层不判断策略，也不拼答案**，只做转发。

`ChatRequest` 的字段决定了这一层的边界：

| 字段 | 含义 |
|:---|:---|
| `message` | 1–4000 字 |
| `session_id` | 为空则新建会话 |
| `user_id` | 数据可见性依据（当前未做认证） |
| `confirm_action_id` | 确认写操作时携带 |
| `idempotency_key` | 客户端重试去重 |

## 4.3 `ChatService.chat()` 逐段读

`app/services/chat_service.py` 的 `chat()` 是同步路径的总导演：

```python
await self._enforce_rate_limit(request.user_id)
session_id = request.session_id or new_id("sess_")
async with request_session(self._session_factory) as db:
    state = await self._initial_state(db, request, session_id, trace_id)
    result = await self._invoke(state)
    response = self._to_response(result, session_id=session_id, trace_id=trace_id)
    await self._persist(db, request, response, summary=result.get("summary") or "")
    await db.commit()
self._remember_pending(request, response)
self._observe(response, started)
```

逐段含义：

1. **限流**：`RateLimiter.allow(f"user:{user_id}")`，内存或 Redis。
2. **会话 ID**：没有就生成 `sess_...`。
3. **`request_session`**：把 `AsyncSession` 放进 `contextvars`，工具层用 `get_db_session()` 惰性取，不需要一路传参数。
4. **`_initial_state`**：解析确认、读最近 20 条消息、组装 `AgentState`。
5. **`_invoke`**：跑 Graph；`GuardrailError` 转成拒答状态，其它 `AppError` 继续抛。
6. **`_to_response`**：把状态映射成 `ChatResponse`。
7. **`_persist`**：写 user/assistant 两条消息，必要时更新摘要。
8. **`_remember_pending`**：把 `pending_action` 存进进程内字典，15 分钟过期。
9. **`_observe`**：打点、日志、延迟。

## 4.4 确认是怎么被“接住”的

```python
def _resolve_confirmation(self, request, session_id):
    if not request.confirm_action_id:
        return None
    pending = self._pending_actions.get(request.confirm_action_id)
    if (pending is None
        or pending.expires_at < time.monotonic()
        or pending.session_id != session_id
        or pending.user_id != request.user_id):
        raise InvalidRequestError("待确认操作不存在或已过期，请重新发起。")
    return pending.action
```

四个校验缺一不可：**存在、未过期、同会话、同用户**。少任何一个，都可能被他人重放。

## 4.5 SSE 流式路径

`stream()` 比 `chat()` 多了一个队列：

```python
async def _run_graph():
    async for update in self._graph.astream(state, stream_mode="updates"):
        for node, payload in update.items():
            holder["merged"].update(payload)
            await queue.put({"event": "node", "node": node, ...})
    await queue.put(None)
```

事件顺序：

```text
started → node* →（可选 token*）→ answer → done
```

SSE 帧本身只有 `data: <JSON>`，事件名在 JSON 的 `event` 字段里（`JSONServerSentEvent` 只接受 `data`）。前端 `SseDecoder` 解析的也是这个形状。

关键设计：**只在忠实度检查之后才发 token**。代码里 `answer` 事件包含完整 `ChatResponse`；`token` 是把最终答案按 48 字符切片补发。这样前端不会先看到一段“可能被自纠错改掉”的文字。

## 4.6 持久化与观测

`_persist()` 调用 `SessionRepository`：

- `append_message(session_id, "user", message)`
- `append_message(session_id, "assistant", answer)`
- `save_summary(session_id, summary)`

`_observe()` 做五件事：

```python
REQUESTS.labels(strategy=..., intent=..., status=...).inc()
ROUTING.labels(strategy=...).inc()
REQUEST_LATENCY.observe(total_ms / 1000)
STAGE_LATENCY.labels(stage="intent").observe(...)
logger.info("chat_completed", extra={"trace_id": ...})
```

## 4.7 异常在哪一层被吃掉

| 异常 | 捕获位置 | 结果 |
|:---|:---|:---|
| `GuardrailError` | `ChatService._invoke` / `stream` | 拒答 + `error_code` |
| `RateLimitError` | 路由/全局异常处理 | 429 |
| `InvalidRequestError` | 全局异常处理 | 400 |
| `ToolPermissionError` | `executor_node` | 该工具失败，继续后面的步骤 |
| 单工具失败 | `execute_with_fallback` | 读工具降级到 `search_knowledge` |
| LLM 超时 | 各节点 `except` | 规则/抽取式回退 |
| 其它 | 全局异常处理 | 500 + 脱敏 message |

## 4.8 时序图

```text
Client          API            ChatService        Graph              Tools/DB
  │  POST /chat   │                  │                │                   │
  │──────────────▶│  validate        │                │                   │
  │               │─────────────────▶│ rate limit     │                   │
  │               │                  │ init state ────│                   │
  │               │                  │                │ guardrail         │
  │               │                  │                │ intent            │
  │               │                  │                │ route             │
  │               │                  │                │ retrieve/plan     │
  │               │                  │                │──────────────────▶│
  │               │                  │                │◀──────────────────│
  │               │                  │                │ generate          │
  │               │                  │                │ faithfulness      │
  │               │                  │                │ memory            │
  │               │                  │◀───────────────│                   │
  │               │                  │ persist ───────────────────────────▶│
  │               │◀─────────────────│ response       │                   │
  │◀──────────────│                  │                │                   │
```

## 4.9 调用关系小结

- `chat.py` 只依赖 `AppContainer`，不依赖任何节点。
- `ChatService` 依赖 Graph、仓储、限流、指标。
- Graph 的节点只依赖“能力对象”（retriever、registry、llm），这些对象由 `container.py` 注入。
- 工具通过 `contextvars` 拿数据库会话，避免把 `AsyncSession` 穿进 Graph 状态。

## 4.10 设计取舍

**为什么不让路由直接调 Graph？** 因为确认、持久化、限流、指标这四件事每个入口都要做，放在 Service 里只写一遍。

**为什么 pending_action 不落库？** 当前实现是进程内字典 + 15 分钟 TTL，简单但不支持多副本。这是已知边界，路线图里明确写了“迁移到持久化存储”。


# 第 5 章 状态机与 LangGraph

## 5.1 为什么用 Graph 而不是一条 if/else

一次对话要走的分支不是线性的：

- 护栏可能直接拒答；
- 不同意图要去检索或去调工具；
- 调完工具还要回来生成；
- 生成后可能被忠实度检查打回重写；
- 最后统一压缩记忆。

`app/agents/graph.py` 用 `StateGraph` 把这些分支画出来，条件边只回答“下一个节点是谁”，节点本身不关心全局流程。

## 5.2 `AgentState`：节点之间的契约

`app/agents/state.py` 是一个 `TypedDict(total=False)`：

| 字段 | 类型 | 谁写 | 谁读 |
|:---|:---|:---|:---|
| `trace_id` / `session_id` / `user_id` | str | Service | 所有节点 |
| `user_query` | str | Service | 意图、检索、规划、生成 |
| `messages` / `summary` | list / str | Service、memory | memory、生成 |
| `intent` | `IntentResult` | intent | router、planner |
| `complexity` / `strategy` | `ComplexityResult` / `RetrievalStrategy` | router | 条件边、检索、生成 |
| `rewritten_queries` | list[str] | retrieval | 调试、生成 |
| `retrieved_chunks` | list[`RetrievedChunk`] | retrieval | 生成、忠实度 |
| `plan` | `AgentPlan` | planner | executor |
| `tool_results` | list[`ToolResult`] | executor | 生成、忠实度 |
| `pending_action` | `ActionProposal` | planner | 生成、Service |
| `confirmed_action` / `confirm_action_id` | `ActionProposal` / str | Service | planner、executor |
| `idempotency_key` | str | 请求 | executor |
| `final_answer` / `citations` / `refused` | str / list / bool | generate、faithfulness | Service |
| `step_count` | int | executor | 循环保护 |
| `token_usage` / `latency` | 结构体 | 各节点累加 | 观测 |

**关键设计**：没有 `Annotated[list, add]` 这种 reducer。LangGraph 默认“后写覆盖”，消息列表只在 memory 节点显式压缩，避免某个节点悄悄把 128k 预算撑爆。

## 5.3 节点与边

```python
graph.add_edge(START, "apply_guardrail")
graph.add_conditional_edges("apply_guardrail", _after_guardrail, {...})
graph.add_edge("classify_intent", "route_complexity")
graph.add_conditional_edges("route_complexity", _route_after_complexity, {...})
graph.add_edge("retrieve_docs", "generate_answer")
graph.add_edge("plan_tasks", "execute_tools")
graph.add_edge("execute_tools", "generate_answer")
graph.add_edge("generate_answer", "check_faithfulness")
graph.add_edge("refuse_answer", "compact_memory")
graph.add_edge("check_faithfulness", "compact_memory")
graph.add_edge("compact_memory", END)
```

两条条件边：

```python
def _after_guardrail(state):
    return "refuse_answer" if state.get("refused") else "classify_intent"

def _route_after_complexity(state):
    return {
        DIRECT: "generate_answer",
        REFUSE: "refuse_answer",
        SINGLE: "retrieve_docs",
        MULTI: "retrieve_docs",
        AGENT: "plan_tasks",
    }[state.get("strategy") or SINGLE]
```

注意 `SINGLE` 和 `MULTI` 都去 `retrieve_docs`，真正的差别在 `retrieval_node` 里：MULTI 走 Self-RAG，SINGLE 走“改写 + 单轮”。

## 5.4 节点契约

每个节点都是 `async def node(state, **deps) -> dict`，返回**只包含自己改动的字段**。依赖通过 `functools.partial` 在 `build_graph` 里绑定：

```python
graph.add_node("retrieve_docs", partial(retrieval_node, retriever=..., reranker=...))
```

这样节点本身不依赖容器，单测时可以注入假对象。

## 5.5 拒绝路径

护栏在 `apply_guardrail` 直接返回 `refused=True`，条件边跳到 `refuse_answer`。`refuse_node` 写一段固定的 IT 边界话术，然后进 `compact_memory` 收尾。

拒答不会经过检索和生成，省一次 LLM 调用。

## 5.6 确认路径

确认请求在 Service 层就被识别：`_resolve_confirmation` 产出 `confirmed_action`。`planner_node` 看到它就不再做意图规划，直接生成单步计划：

```python
if confirmed is not None:
    return {"plan": AgentPlan(steps=[PlanStep(...tool_name=confirmed.tool_name,
                                                arguments=confirmed.arguments)]),
            "pending_action": None}
```

这样“确认执行”不会重新分类、不会重新规划，避免模型在确认轮改参数。

## 5.7 记忆是最后一个节点

`compact_memory` 在生成和拒答之后统一执行：把本轮 user/assistant 消息追加进去，按预算压缩，必要时摘要。放在末尾的好处是：**生成时看到的是完整上下文，压缩只影响下一轮**。

---

# 第 6 章 意图识别与自适应路由

## 6.1 11 个标签

`app/core/enums.py`：

| 标签 | 含义 |
|:---|:---|
| `greeting` | 打招呼 |
| `chitchat` | 闲聊 |
| `faq_policy` | 流程、制度、时效类问题 |
| `ticket_status` | 工单进度 |
| `asset_query` | 设备归属、保修 |
| `incident_report` | 报障 |
| `access_request` | 权限、账号、密码 |
| `software_request` | 软件安装、License |
| `complaint` | 投诉 |
| `human_handoff` | 转人工 |
| `out_of_scope` | 越界 |

标签不是越多越好。11 个标签刚好覆盖“问制度、问自己的东西、让 IT 改东西”三类，再多会让分类边界变模糊。

## 6.2 LLM 分类器

`app/prompts/intent.py` 的 prompt 有三层：

1. 标签清单；
2. 11 条优先级规则（越界 > 转人工 > 问候 > 闲聊 > 投诉 > 工单 > 资产 > 权限 > 软件 > 报障 > 制度）；
3. 17 条易混样例（“报修流程是什么 → faq_policy”“帮我报修 → incident_report”）。

输出是固定 JSON：

```json
{"label":"incident_report","confidence":0.9,"rationale":"...","prompt_version":"intent_v4"}
```

`IntentClassifier.classify()` 的流程：

```python
fallback = rule_based_intent(query)
if isinstance(llm, OfflineLLMProvider):
    return self._maybe_overlay(query, fallback)
try:
    response = await llm.generate(...)
    parsed = parse_model(response.content, IntentResult)
    return self._maybe_overlay(query, parsed)
except (LLMProviderError, LLMOutputError):
    return self._maybe_overlay(query, fallback)
```

**模型永远不是唯一路径**：超时、401、JSON 不合法都会退到规则。

## 6.3 规则兜底与高精度覆盖层

`app/agents/nodes/intent_overlay.py` 是一张词表 + 一组优先级判断，输出 `IntentLabel | None`。返回 `None` 表示“我不确定，交给模型”。

几个关键规则：

```python
_TICKET_ID = re.compile(r"\bTKT\d{4,}\b", re.I)
_ASSET_ID = re.compile(r"\bAST\d{4,}\b", re.I)
_TICKET_STRONG = ("我的工单", "工单进度", "工单状态", "处理到哪", "什么时候修好")
_POLICY_HINTS = ("规则", "政策", "流程", "条件", "标准", "时效", "多久", "有效期", ...)
_ACTION_HINTS = ("帮我", "开通", "重置", "解锁", "提交", "给我开", "建单", "加权限")
```

两个容易踩的坑，代码里专门处理了：

1. **“哪些”是政策词，但也出现在“我的工单有哪些”里**。所以 `_TICKET_STRONG` 在政策判断**之前**匹配。
2. **“申请”既可能是动作，也可能是流程问题**。`_ACTION_HINTS` 里没有放“申请”，而是靠“帮我/开通/重置”这些强动作词；因此“权限申请流程”会落到 `faq_policy`。

还有一条特例：

```python
if ("离职" in text or "外包" in text) and _has(text, ("怎么", "如何", "区别", "流程", "多久")):
    return IntentLabel.FAQ_POLICY
```

“离职账号怎么回收”是流程问题，不是“申请账号”。

## 6.4 自适应路由

`app/retrieval/adaptive.py` 的 `rule_based_complexity()` 是规则版分流：

| 条件 | 策略 |
|:---|:---|
| `out_of_scope` | `REFUSE` |
| `greeting` / `chitchat` | `DIRECT` |
| 出现 `TKT` / `AST` 编号 | `AGENT` |
| `ticket_status` / `asset_query` / `access_request` / `software_request` / `human_handoff` / `complaint` | `AGENT` |
| `incident_report` 且含“报修/建单/申请/开通/重置” | `AGENT` |
| `incident_report` 其它情况 | `SINGLE`（排障 SOP） |
| 多跳线索 ≥ 2，或 ≥ 1 且长度 > 18 | `MULTI` |
| 其余 | `SINGLE` |

**故障报障不一定建单**：问“电脑蓝屏怎么办”是排障，问“帮我报修”才建单。这条区分避免用户只想问怎么修，却被强行开一张工单。

LLM 也可以做复杂度分类，但有一条硬规则：

```python
if _TICKET_ID.search(query) or _ASSET_ID.search(query):
    return fallback
```

只要用户给了显式编号，就信规则，不信模型。

## 6.5 调用关系

```text
intent_node → IntentClassifier.classify
                ├─ rule_based_intent (offline / 失败)
                ├─ LLM (deepseek)
                └─ apply_intent_overlay (纠偏)
        ↓
router_node → AdaptiveRouter.route
                ├─ rule_based_complexity
                └─ LLM + 显式 ID 兜底
        ↓
graph 条件边
```

## 6.6 设计取舍

- **规则 + 模型双轨**：规则保证可测、可离线；模型保证长尾覆盖。
- **覆盖层只做高精度纠偏**：返回 `None` 就不干预，避免规则把模型带偏。
- **显式 ID 优先级最高**：这是确定性最强、最不该让模型猜的信号。

---

# 第 7 章 检索链路

## 7.1 全流程

```text
knowledge/*.md
   │ list_knowledge_files
   ▼
parse_path（Unstructured 或 Markdown 回退）
   │ cleaning / normalize
   ▼
chunk_markdown（H1–H3 分节，500 字窗口，60 重叠）
   │ stable_chunk_id
   ▼
embed（bge-small 或 hash）
   ├─▶ BM25Retriever（jieba）
   └─▶ VectorStore（内存 / Qdrant）
        │
query ─▶ HybridRetriever（各 top_k → RRF）─▶ DocumentReranker（top_n）
```

入口在 `app/services/container.py::build_retrieval()`，启动时执行一次 `ingest_knowledge()`。

## 7.2 切块：为什么是 500 / 60

`app/retrieval/chunking.py`：

```python
MAX_CHUNK_CHARS = 500
OVERLAP_CHARS = 60
_HEADING = re.compile(r"^#{1,3}\s+(.*)$")
```

- 按 H1–H3 切小节；第一个标题前的内容归到 `body` 节。
- 每个小节超过 500 字再按字符窗口切，窗口之间重叠 60 字，防止一句话被切断后两边都检索不到。
- 500 字大约是中文 300–400 token，既能装下一段完整制度，又不会让精排输入过长。

**chunk_id 是稳定的**：

```python
document_id = f"{stem}_{sha1(relative_path)[:8]}"
chunk_id = f"{document_id}_{index:02d}"
```

同样的文件在 Windows、Linux、Docker 里会得到同一个 ID，引用不会因为换机器而失效。

## 7.3 BM25：为什么把标题和小节也建索引

`app/retrieval/bm25.py`：

```python
tokenized = [tokenize(f"{chunk.title} {chunk.section} {chunk.content}")
             for chunk in self._chunks]
self._bm25 = BM25Okapi(tokenized)
```

只索引正文时，“VPN 怎么申请”这类短问句容易输给正文里碰巧出现“VPN”的长文档。把 `title`（文件名）和 `section`（小节标题，如“申请资格”）一起索引后，小节标题能直接命中。

实测这一改动把 BM25 的 P@1 从 58.3% 提到 **68.3%**。

`tokenize()` 优先用 jieba；没有 jieba 时退化成“中文二元组 + 英文单词”，保证 BM25 仍可用。

## 7.4 向量检索

`app/retrieval/vector.py` 支持两种存储：

| 实现 | 场景 |
|:---|:---|
| `InMemoryVectorStore` | 测试、无 Qdrant |
| `QdrantVectorStore` | 生产，COSINE 距离 |

要点：

- 向量先 L2 归一化，余弦相似度退化成点积。
- Qdrant 的 point id 必须是 UUID/int，所以用 `md5(chunk_id)` 转 UUID，保证重复 ingest 不产生重复点。
- Qdrant 客户端是同步的，检索放在 `asyncio.to_thread` 里，避免阻塞事件循环。

## 7.5 RRF 融合

`app/retrieval/fusion.py`：

```python
RRF(d) = Σ_i 1 / (k + rank_i(d))
```

为什么用排名而不是分数：BM25 分数和余弦相似度量纲不同，直接加权需要调参；RRF 只看排名，天然可比。`k=60` 是论文默认值。

重复 chunk 会合并，分数相加，第一次见到的元数据保留。

## 7.6 精排

`DocumentReranker.rerank()` 把候选文档交给 `RerankProvider`，拿回 `(original_index, score)` 列表，再按新顺序复制 chunk、改 `rank` 和 `source="rerank"`。

两种 provider：

- `CrossEncoderRerankProvider`：加载 `bge-reranker-base`，效果最好；权重缺失时 `available=False`。
- `LexicalRerankProvider`：按词重叠打分，CI/离线用，**不是** Cross-Encoder。

`eval/MEASURED.md` 里明确写了：词法重排那行不能当精排收益。

## 7.7 缓存

`app/retrieval/cache.py` 只缓存“静态制度检索”：

```python
def _looks_like_personal_query(query):
    compact = query.upper().replace(" ", "")
    if any(token in compact for token in ("TKT", "AST", "APR")):
        return True
    return any(token in query for token in ("工单", "资产", "审批", "我的"))
```

命中的查询直接跳过缓存。为什么？因为“我的工单”这类结果依赖用户，缓存会串数据。

## 7.8 HybridRetriever 的容错

```python
try:
    lexical = self._bm25.search(query, top_k=top_k)
except Exception:
    lexical_error = exc
try:
    dense = await self._vector.search(query, top_k=top_k)
except Exception:
    dense_error = exc
if not lexical and not dense:
    raise RetrievalError(...)
fused = reciprocal_rank_fusion([lexical, dense], k=self._rrf_k)
```

两路各自独立失败：BM25 挂了还能用向量，向量挂了还能用 BM25；两路都空才抛错。这是“分层降级”的最小单元。

## 7.9 配置与实测

| 参数 | 默认 | 作用 |
|:---|:---:|:---|
| `retrieval_top_k_simple` | 3 | SINGLE 每路召回 |
| `retrieval_top_k_complex` | 8 | MULTI 每路召回 |
| `rrf_k` | 60 | RRF 常数 |
| `rerank_top_n` | 5 | 精排后保留 |

60 条检索集的实测（bge-small，未加载 CE）：

| 系统 | P@1 | R@3 | MRR |
|:---|:---:|:---:|:---:|
| BM25 | 68.3% | 94.2% | 0.804 |
| bge-small | 61.7% | 95.0% | 0.776 |
| BM25+bge+RRF | 71.7% | 91.7% | 0.826 |

## 7.10 调用关系

```text
container.build_retrieval
  ├─ ingest_knowledge → BM25Retriever + VectorStore
  └─ HybridRetriever(bm25, VectorRetriever(store, embedder), rrf_k)
        ↓
retrieval_node
  ├─ SINGLE: QueryRewriter → HybridRetriever × 2 → Reranker
  └─ MULTI : SelfRAGLoop（内部同样用 HybridRetriever + Reranker）
```

---

# 第 8 章 Self-RAG 多跳

## 8.1 它解决什么问题

“离职员工账号怎么回收，外包和正式员工有区别吗”这类问题，答案分散在 `account_lifecycle` 和 `account_shared` 两篇文档里。单轮 top-k 只能命中一篇，模型就容易只答一半。

Self-RAG 的思路：**检索 → 评分 → 不够就改写再检 → 直到够或到上限**。

## 8.2 循环

`app/retrieval/self_rag.py`：

```python
for _hop in range(self._settings.max_retrieval_hops):   # 默认 3
    rewritten = await self._rewriter.rewrite(current_query, missing_aspect=missing)
    queries = list(dict.fromkeys([query, *rewritten]))[:2]
    candidates = {}
    for search_query in queries:
        for candidate in await self._retriever.retrieve(search_query, top_k=top_k):
            candidates.setdefault(candidate.chunk_id, candidate)
    reranked = await self._reranker.rerank(query, list(candidates.values()), top_n=...)
    accumulated.update({c.chunk_id: c for c in reranked})
    grade = await self._grade(query, list(accumulated.values()))
    if grade.sufficient:
        break
    missing = grade.missing_aspect or "more specific policy conditions"
```

四个关键点：

1. **最多 3 跳**：`max_retrieval_hops` 限制成本，防止死循环。
2. **跨跳累积**：`accumulated` 按 chunk_id 去重，后面几跳补的是“上一跳缺的那部分”。
3. **评分驱动**：`_grade()` 用 LLM 输出 `relevant / sufficient / missing_aspect`；模型失败时退化为“有结果就算够”。
4. **最终截断**：返回 `rerank_top_n * 2` 条，给生成留冗余但不过量。

## 8.3 评分失败怎么办

```python
except (LLMProviderError, LLMOutputError):
    return GradeResult(relevant=bool(chunks), sufficient=bool(chunks), rationale="fallback")
```

没有模型时不做多跳判断，直接把已检索到的内容当“够用”。这是一个有意识的降级：宁可少跳，不要因为评分器挂了导致整轮失败。

## 8.4 与单轮的差别

`app/agents/nodes/retrieval.py`：

```python
if strategy == RetrievalStrategy.MULTI:
    chunks = await self_rag.retrieve(query, top_k=top_k)
    rewritten = [query]
else:
    suggestions = await rewriter.rewrite(query)
    rewritten = list(dict.fromkeys([query, *suggestions]))[:2]
    by_id = {}
    for search_query in rewritten:
        for candidate in await retriever.retrieve(search_query, top_k=top_k):
            by_id.setdefault(candidate.chunk_id, candidate)
    chunks = await reranker.rerank(query, list(by_id.values()), top_n=...)
```

- SINGLE：改写 1–3 条查询，合并去重，精排一次。
- MULTI：进入 Self-RAG，循环内部同样会改写、检索、精排。

两者都用了“多查询合并”——**改写不是为了换说法，而是为了补召回**。

## 8.5 成本与观测

- 每次多跳 = 1 次改写 + N 次检索 + 1 次精排 + 1 次评分。
- `retrieval_node` 把耗时写进 `latency.retrieval_ms`。
- 如果模型不可用，改写直接返回原句，评分退化为“有结果即够”，多跳退化成单轮。

## 8.6 设计取舍

**为什么不用“固定检索 3 次再合并”**？因为不同问题的信息缺口不同，固定次数会要么浪费、要么不够。评分器给出 `missing_aspect`，下一跳才能有针对性地改写。

**为什么评分用结构化 JSON 而不是特殊 token**？JSON 可以被 Pydantic 校验，失败可回退；特殊 token 依赖模型微调，DeepSeek 通用模型不提供。


# 第 9 章 领域模型与工具层

## 9.1 四张业务表

`app/repositories/models.py` 定义了 8 张表，其中 4 张是业务表：

### tickets

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `ticket_id` | String(32) PK | `TKT` + 9 位，创建时生成 |
| `user_id` | String(64) index | 提单人 |
| `category` | String(32) index | account / device / network / software / security / other |
| `priority` | String(8) index | p1 / p2 / p3，默认 p3 |
| `status` | String(32) index | open / in_progress / pending_approval / resolved / closed / cancelled |
| `title` / `description` | String(128) / Text | 标题与现象 |
| `assignee_group` | String(64) nullable | 按分类自动派组 |
| `source` | String(16) | 默认 `chat` |
| `created_at` / `updated_at` | DateTime | 应用侧 `utcnow` |
| `resolved_at` | DateTime nullable | 解决/关闭时写 |
| `sla_due_at` | DateTime nullable | 创建时按优先级算 |

SLA 规则在 `ticket_repository.py`：

```python
SLA_HOURS = {"p1": 0.5, "p2": 4.0, "p3": 8.0}
```

### ticket_events

追加式时间线：`ticket_id`、`event_type`（created / assigned / comment / resolved / approval_requested）、`actor_id`、`content`、`created_at`。只增不改，用来还原“这张单经历了什么”。

### assets

`asset_id`（`AST` + 5 位）、`asset_type`、`model`、`serial_no`、`owner_user_id`、`status`（in_use / in_stock / repairing / retired / lost）、`purchased_at`、`warranty_until`、`location`。

### approvals

| 字段 | 说明 |
|:---|:---|
| `approval_id` | `APR` + 9 位 |
| `ticket_id` | 可空，关联工单 |
| `requester_id` | 申请人 |
| `kind` | access / password_reset / vpn / software_install / asset_issue |
| `target` | 权限点、账号或软件名 |
| `payload` | JSON 文本，存明细 |
| `status` | pending / approved / rejected / executed / expired |
| `approver_role` | manager / it_admin / security |
| `approver_id` / `decided_at` | 审批人、决策时间 |
| `expires_at` / `executed_at` | 过期与执行时间 |

另外 4 张支撑表：`sessions`、`messages`、`audit_logs`、`idempotency_keys`。

## 9.2 仓储层

`app/repositories/ticket_repository.py` 是唯一的领域读写入口：

| 方法 | 行为 |
|:---|:---|
| `get_ticket` / `get_visible_ticket` | 后者校验 `user_id`，他人数据当作“不存在” |
| `list_tickets_for_user` | 最近 N 条，`selectinload(events)` |
| `get_asset` / `get_visible_asset` / `list_assets_for_user` | 同上 |
| `get_approval` / `get_visible_approval` / `list_approvals_for_user` | 审批单可见性 |
| `create_ticket` | 生成 ID、算 SLA、写一条 `created` 事件、写审计、`flush` |
| `create_approval` | 生成审批单、写审计、返回 `approval_id/status/expires_at` |
| `mark_approval` / `mark_approval_executed` | 状态推进（当前无调用方） |
| `update_ticket_status` | 解决/关闭时写 `resolved_at` |
| `add_event` | 追加时间线 |
| `write_audit` | 写 `audit_logs`，payload 可 str 或 dict |

**安全设计**：越权统一抛 `InvalidRequestError("ticket not found: ...")`，而不是 403。攻击者无法通过错误信息枚举“哪些工单存在”。

## 9.3 工具基类

`app/tools/base.py`：

```python
class Tool:
    name: str
    description: str
    risk: ToolRisk = ToolRisk.READ
    input_model: type[BaseModel]

    async def run(self, arguments, context):
        parsed = self.parse(arguments)      # Pydantic 校验
        try:
            return await self.execute(parsed, context)
        except InvalidRequestError:
            raise
        except Exception as exc:
            raise ToolExecutionError(f"{self.name} failed") from exc
```

三个要点：

1. **参数校验前置**：`input_model` 是 Pydantic 模型，类型不对直接 `InvalidRequestError`。
2. **异常包装**：业务上可预期的错误透传，未知异常统一成 `ToolExecutionError`，Graph 不会因为一个工具崩掉。
3. **`openai_schema()`**：把 `input_model` 转成 Function Calling schema，模型看到的就是这些字段说明。

`NoArgsInput` 是给无参数工具用的空模型。**不要写 `input_model = BaseModel`**——基类不能实例化，会在参数校验时崩。

## 9.4 十个工具

| 工具 | 风险 | 参数模型 | 关键行为 |
|:---|:---:|:---|:---|
| `get_ticket` | READ | `ticket_id` 5–32 | 查可见工单，返回状态、优先级、处理组、SLA、最近事件 |
| `list_my_tickets` | READ | 无 | 本人最近 5 条 |
| `get_asset` | READ | `asset_id` 5–32 | 查可见资产，返回型号、序列号、归属、保修 |
| `list_my_assets` | READ | 无 | 本人至多 10 条 |
| `search_knowledge` | READ | `query` 1–200 | 检索 top 4，chunk 截断 400 字 |
| `create_ticket` | **WRITE** | category / priority / title / description | 建单 + SLA + 首条事件 |
| `request_access` | **WRITE** | system / scope / duration_days / reason | 生成审批单；高危加签 security |
| `reset_password` | **WRITE** | account / reason | 生成审批单，24h 有效 |
| `request_software` | **WRITE** | software / version / reason | 生成审批单，72h 有效 |
| `escalate_to_human` | EXTERNAL | reason | 返回 `esc_...` 伪 ID，不落库 |

`WRITE_RISKS = {WRITE, DESTRUCTIVE}`。EXTERNAL 不要求确认，这是当前设计的缺口：转人工不落库、不审计。

高危权限判断在 `request_access`：

```python
_HIGH_RISK_SCOPES = ("导出", "付款", "生产", "管理员", "密钥", "root")
high_risk = any(token in parsed.scope for token in _HIGH_RISK_SCOPES)
approver_role = "security" if high_risk else "manager"
ttl_hours = 48 if high_risk else 72
```

## 9.5 工具如何拿到数据库

工具不接收 `AsyncSession` 参数，而是通过 `contextvars`：

```python
class RepositoryBackedTool:
    @property
    def repository(self) -> TicketRepository:
        if self._repository is not None:
            return self._repository
        return TicketRepository(get_db_session())
```

`ChatService` 用 `request_session(...)` 把 session 放进 contextvar，工具惰性取。好处是 Graph 状态里不必塞数据库句柄；测试时可以直接 `Tool(repository=fake_repo)` 注入。

## 9.6 Skill 与 MCP

`app/skills/definitions/*.json` 是“工具编排模板”：

```json
{
  "name": "incident_triage",
  "triggers": ["报修", "报障", "坏了", "连不上", "蓝屏", "打不开", "开不了机"],
  "steps": ["确认影响范围与优先级", "检索相关排障 SOP", "必要时创建工单并告知 SLA"],
  "tools": ["search_knowledge", "create_ticket"]
}
```

`Planner` 用 `match_skill()` 先按触发词、再按意图映射找模板，模板里的 `tools` 同时成为**规划白名单**（`_allowed_tools`），减少模型乱选工具。

`app/mcp/` 把本地工具与远程 HTTP 工具统一成 `Tool`。默认目录只有两个：`mcp_service_hours`、`mcp_change_calendar`。

## 9.7 调用关系

```text
planner_node → Planner.create_plan
    ├─ match_skill → skill["tools"]
    ├─ LLM 产出 AgentPlan（或 skill_to_plan 规则计划）
    └─ _sanitize_plan 过滤不存在的工具
executor_node → ToolRegistry.get(name)
    ├─ WRITE: assert_permitted → 幂等检查 → tool.run → 写幂等表
    └─ READ : execute_with_fallback → 失败降级 search_knowledge
```

---

# 第 10 章 写操作与人工确认

## 10.1 两条“确认”不要混

项目里有两层确认，职责不同：

| 层 | 存储 | 生命周期 | 作用 |
|:---|:---|:---|:---|
| `pending_action` | `ChatService._pending_actions` 内存字典 | 15 分钟，进程重启即丢 | 防止模型未经用户同意就执行写操作 |
| `ApprovalRow` | `approvals` 表 | 24–72 小时 | 业务审批单，记录“谁申请、谁审批、是否执行” |

第一层是**对话级确认**，第二层是**业务级审批**。两者不是一回事；`models.py` 注释里“HITL 可跨进程重启”只对 `ApprovalRow` 成立。

## 10.2 从一句话到一张审批单

以“帮我申请 ERP 采购审批权限”为例：

```text
intent: access_request
  ↓
adaptive: AGENT
  ↓
planner: 匹配 access_request skill → request_access(WRITE)
  ↓ 未确认
executor: assert_permitted 抛 ToolPermissionError
  ↓
planner_node 生成 pending_action
  ↓
ChatService._remember_pending（15 分钟）
  ↓ 用户点“确认执行”
_initial_state → _resolve_confirmation → confirmed_action
  ↓
planner_node 直接单步计划（不再规划）
  ↓
executor: 带 confirm_action_id → 执行 request_access
  ↓
create_approval → approvals 表（pending）
```

## 10.3 Planner 的写操作判断

`app/agents/nodes/planner.py`：

```python
write_steps = [step for step in plan.steps
               if step.tool_name and planner._registry.get(step.tool_name).risk in WRITE_RISKS]
if any(_explicit_write_request(query, step.tool_name) for step in write_steps):
    if any(_missing_required_args(step) for step in write_steps):
        return {"plan": plan.model_copy(update={"steps": []}), "extra": {"missing_slot": True}}
```

三个判断：

1. **是否明确要求写**：`_explicit_write_request()` 看“帮我报修 / 申请权限 / 重置密码”等强动作词。如果句子里有“流程/规则/怎么/能不能”，一律不算写请求。
2. **参数是否齐**：`create_ticket` 要 title、`request_access` 要 system+scope、`request_software` 要 software；缺了返回 `missing_slot`，生成节点会提示补充。
3. **只保留写步骤**：不是明确写请求的写工具，从计划里删掉，避免“咨询类问题被强行建单”。

## 10.4 确认绑定

`ChatService._resolve_confirmation()` 校验四件事：存在、未过期、同会话、同用户。

```python
if (pending is None
    or pending.expires_at < time.monotonic()
    or pending.session_id != session_id
    or pending.user_id != request.user_id):
    raise InvalidRequestError("待确认操作不存在或已过期，请重新发起。")
```

这四条是防重放的核心。少一条，别人拿到 `action_id` 就能替你执行。

## 10.5 幂等

`executor_node` 对 WRITE 工具做两层保护：

```python
idem_key = context.confirmed_action_id or context.idempotency_key
if idem_key:
    fp = sha256({"tool": name, "arguments": args})
    existing = await idempotency.get_if_matches(idem_key, fp)
    if existing: return cached_result
    result = await tool.run(...)
    await idempotency.put(idem_key, fp, result.output)
```

- 同一个 key + 同 payload → 直接返回上次结果，不重复建单。
- 同一个 key + 不同 payload → `IDEMPOTENCY_CONFLICT`（409）。
- 只有 WRITE 分支走幂等；READ 和 EXTERNAL 不进表。

## 10.6 审计

`ticket_repository.write_audit()` 每次写操作都落一条 `audit_logs`，带 `trace_id`、`action`、`payload`。`create_ticket` / `create_approval` 内部都会调用。

## 10.7 审批单状态机（当前实现边界）

设计上的状态机：

```text
pending ──approve──▶ approved ──execute──▶ executed
   │
   ├──reject──▶ rejected
   └──timeout─▶ expired
```

但核对全仓调用方后可以确认：**`mark_approval` 和 `mark_approval_executed` 目前没有调用方**，也没有审批 API 和过期清扫任务。也就是说：

- 创建审批单是通的（`create_approval`）；
- “谁批准、何时执行、过期作废”还停留在方法层面，没有接进任何入口；
- `ApprovalStatus` 的 `approved/rejected/expired` 目前只是定义。

这是**设计好了但未接通**的部分，不是 bug。写进手册是为了避免读者误以为审批流已经闭环；真实系统里应该由 ITSM 或审批服务来推进。

## 10.8 设计取舍

- **为什么不让模型直接执行**：删权限、改密码这类动作不可逆，模型输出不可信。
- **为什么确认放内存**：Demo 简单；生产必须持久化，否则多副本/重启会丢确认。
- **为什么审批单和确认分离**：对话确认解决“你现在同不同意”，审批单解决“公司流程允不允许”。

---

# 第 11 章 生成、引用与忠实度

## 11.1 生成 prompt

`app/prompts/answer.py` 的角色是“企业内部 IT 服务台助手”，规则包括：

- 只根据证据、工具结果和制度回答；
- 证据不足就说不确定，并给出下一步；
- 不编造工单号、资产编号、审批结果、时效；
- 引用时用 `chunk_id`；
- 申请类操作只说“已生成审批单、需要谁审批”，不说“已开通”；
- 不泄露他人的工单/资产/账号。

输出是 JSON：

```json
{"answer":"...","citation_chunk_ids":["..."],"refused":false}
```

## 11.2 生成节点的三条分支

`app/agents/nodes/generate.py`：

1. **工具全失败** → 固定话术“暂时无法查到相关记录”。
2. **有 `pending_action`** → 直接返回 `pending.summary`，不调模型，保证“确认卡片文案”不被模型改写。
3. **正常** → 拼证据（最多 6 条）与工具结果，调 LLM；离线时走 `_offline_answer()`。

`_offline_answer()` 按工具名逐条渲染：

```python
if result.name == "create_ticket":
    return f"已创建工单 {data.get('ticket_id')}，优先级 {data.get('priority')} ..."
if result.name == "get_ticket":
    return f"工单 ... 当前状态：{status}。最近进展：..."
```

这段是“没有模型也能用”的关键：结构化数据直接变人话。

## 11.3 引用绑定

模型返回 `citation_chunk_ids`，节点只保留**实际检索到**的 chunk：

```python
citations = [Citation(...) for chunk in chunks
             if chunk.chunk_id in set(payload.citation_chunk_ids)]
```

模型编一个不存在的 `chunk_id` 会被静默丢弃。前端 `CitationList` 再按 `chunk_id` 去重展示。

## 11.4 忠实度检查

`app/guardrails/hallucination.py` 把问题、回答、证据、工具结果一起交给 LLM，输出：

```json
{"supported": true, "hallucinated_spans": [], "rationale": "..."}
```

`faithfulness_node` 的处理：

- `supported=true` → 原样通过，`extra.faithfulness` 记录结果。
- `supported=false` → `HALLUCINATION_FLAGS.inc()`，调用 `self_correct_answer()` 重写。
- 重写后仍不支持 → 用抽取式回退（直接引用证据原文）。

## 11.5 自纠错

`self_correct_answer()` 把“原回答 + 裁判说明 + 证据”再交给模型，要求删除或改写不被支持的句子。最多一轮，避免无限循环。

## 11.6 拒答

两类拒答：

- **入口拒答**：`guardrail_node` 检测到注入，直接 `refused=True`。
- **证据不足拒答**：`faithfulness_node` 在 SINGLE/MULTI 且没有 chunk 时，返回“现有资料不足”，`refused=True`。

`refuse_node` 的话术固定为 IT 边界，不再调用模型。

## 11.7 调用关系

```text
generate_answer
  ├─ tool_results → pending_action? → summary
  ├─ OfflineLLMProvider → _offline_answer
  └─ LLM → AnswerPayload → citations 过滤
        ↓
check_faithfulness
  ├─ supported → 通过
  └─ unsupported → self_correct_answer → 仍失败 → 抽取式回退
        ↓
compact_memory
```

## 11.8 设计取舍

- **引用只认检索结果**：不做“模型说引用了就信”。
- **pending 文案不走模型**：确认卡片必须和计划参数一致。
- **忠实度用同模型裁判**：便宜，但偏乐观；评测文档里明确写了这一点。

---

# 第 12 章 上下文预算与记忆压缩

## 12.1 为什么要自己算 token

DeepSeek 没有公开 tokenizer，项目用启发式：

```python
def estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 1.5))   # 中文约 1 token / 1.5 字
```

不是精确值，但足够做“是否接近预算”的判断。

## 12.2 三级阈值

`app/memory/budget.py`：

```python
if ratio >= 0.85: AUTO_COMPACT
elif ratio >= 0.70: HARD_COMPRESS
elif ratio >= 0.50: SOFT_TRUNCATE
else: NONE
```

对应配置 `token_budget=128000`、`compress_soft_ratio=0.50`、`compress_hard_ratio=0.70`、`auto_compact_ratio=0.85`。

## 12.3 压缩动作

`app/memory/compression.py`：

| 级别 | 工具结果 | 消息 |
|:---|:---|:---|
| NONE | 不截断（上限 10000 字符） | 原样 |
| SOFT_TRUNCATE | 截到 400 字符 | 原样 |
| HARD_COMPRESS | 截到 160 字符 | 滑动窗口保留末 8 条，摘要前置 |
| AUTO_COMPACT | 截到 160 字符 | 同 HARD，并触发 LLM 摘要 |

```python
KEEP_RECENT_TURNS = 4
TOOL_SOFT_CHARS = 400
TOOL_HARD_CHARS = 160
```

注意：`compression.py` 的 docstring 说 70–85% 会把旧轮次“压成要点”，但代码在这一档只做**滑动窗口丢弃 + 摘要前置**；真正的语义摘要在 85% 以上才发生。这是文档与实现的偏差，读代码时以实现为准。

## 12.4 memory 节点

`app/agents/nodes/memory.py` 在生成之后执行：

```python
messages.append(user)
messages.append(assistant)
messages, tool_results, level, summary = apply_compression(...)
if level == AUTO_COMPACT:
    summary = await summarizer.summarize(messages)
    messages, tool_results, _, summary = apply_compression(...)
```

- 摘要失败时退化为“末 4 条各截 40 字”。
- 摘要保存在 `sessions.summary`，下一轮 `_initial_state` 读取（当前实现里 `summary` 初始为空，属于路线图里的待补项）。

## 12.5 设计取舍

- **压缩放在生成之后**：生成看到完整上下文，压缩只影响下一轮。
- **工具结果先截断**：工具输出往往是最大的 token 消耗者。
- **不自动删消息**：滑动窗口只保留最近 8 条，但摘要会保留更早的信息。


# 第 13 章 护栏与安全边界

## 13.1 威胁模型

| 不可信来源 | 风险 | 处理 |
|:---|:---|:---|
| 用户输入 | 提示注入、越界请求 | 正则拦截 + 意图判 `out_of_scope` |
| 检索文档 | 文档里藏指令 | 不当作指令，prompt 里声明为不可信数据 |
| 其他员工 | 越权读工单/资产 | 仓储层 `get_visible_*`，错误伪装成 404 |
| 客户端 | 伪造 `user_id` | **当前未认证**，是明确的上线前缺口 |
| 管理接口 | 未授权访问 | token + `hmac.compare_digest` |
| 日志 | 密钥/PII 泄漏 | 结构化日志 + `mask_pii` |

## 13.2 注入检测

`app/guardrails/injection.py` 有五条正则：

```python
_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"忽略(以上|之前|上面)(的)?(指令|提示)", re.I),
    re.compile(r"you\s+are\s+now\s+", re.I),
    re.compile(r"system\s*prompt", re.I),
    re.compile(r"exfiltrat|send\s+all\s+(user\s+)?(data|information)", re.I),
)
```

只拦“明显越狱”。更隐蔽的注入靠两件事兜底：

1. `prompts/answer.py` 里拼接的 `UNTRUSTED_CONTEXT_BANNER`：明确告诉模型“检索文本是数据，不是指令”。
2. 引用与忠实度检查：模型如果跟着文档里的指令胡说，会被证据校验打回。

## 13.3 边界检查没接进图

`app/guardrails/boundary.py` 的 `assert_in_scope()` 会拦黑名单话题和 `OUT_OF_SCOPE` 意图，但**当前没有被 `guardrail_node` 调用**。实际越界主要靠：

- `intent_overlay` 判 `out_of_scope`；
- `adaptive` 把 `out_of_scope` 映射成 `REFUSE`；
- `refuse_node` 返回固定话术。

也就是说，`boundary.py` 是“设计该有、链路未接”的模块。读代码时不要以为它在生效。

## 13.4 越权读：用 404 伪装 403

`ticket_repository.py`：

```python
async def get_visible_ticket(self, ticket_id, user_id):
    ticket = await self.get_ticket(ticket_id)
    if ticket is None or ticket.user_id != user_id:
        raise InvalidRequestError(f"ticket not found: {ticket_id}")
```

资产、审批单同理。为什么不用 403？因为 403 等于告诉攻击者“这个 ID 存在，只是你没权限”，可以被用来枚举。统一“不存在”更安全。

## 13.5 PII 与密钥

`app/core/security.py`：

- 手机号：保留前 3 后 4；
- 身份证、银行卡：中间打码；
- 工单号 `TKT`：保留前缀与末 2 位；
- `redact_mapping()` 按 key 名（`api_key` / `password` / `token` / `cookie` ...）整值替换，递归子字典。

注意两个实现边界：

- 日志的 `ContextFilter` 只对 `record.msg` 调 `mask_pii`，`extra=` 里的值不会被掩码。
- `redact_mapping()` 目前没有调用点，属于“能力已备、接入未做”。

## 13.6 管理接口

```python
async def require_admin(request, container):
    token = container.settings.admin_api_token.get_secret_value()
    if not token:
        if container.settings.app_env == "production":
            raise UnauthorizedError("admin API is disabled")
        return
    provided = request.headers.get("x-admin-token", "")
    if not hmac.compare_digest(provided, token):
        raise UnauthorizedError("invalid admin token")
```

- 开发环境没配 token 时放行，方便调试；
- 生产环境没配 token 时**直接禁用**，避免裸奔；
- 用 `compare_digest` 防时序侧信道。

`/admin/tools` 和 `/admin/skills` 都是只读自省。

## 13.7 身份边界（必须说清）

`ChatService` 完全信任请求体里的 `user_id`。这意味着：

- 任何人都能伪造 `user_id` 读别人的工单——只要知道工单号；
- 前端默认 `u_demo` 只是演示。

这是项目 README 和路线图里明确写的第一条 P0：**部署前必须由可信服务端认证并绑定身份**。

## 13.8 设计取舍

- **护栏不做“全能过滤”**：正则只能拦明显攻击，真正的防线是“检索文本不可信 + 引用校验”。
- **越权伪装 404**：牺牲错误可读性，换不可枚举。
- **管理接口默认关闭**：生产环境宁可不可用，也不要裸奔。

---

# 第 14 章 可靠性与可观测性

## 14.1 降级矩阵

| 依赖 | 缺失时 | 影响 |
|:---|:---|:---|
| `DEEPSEEK_API_KEY` | `OfflineLLMProvider` | 规则分类、抽取式回答；无生成 |
| 本地 embedding | `HashEmbeddingProvider` | 稠密检索退化为词法哈希；效果下降 |
| Cross-Encoder | `LexicalRerankProvider` | 精排退化为字符重叠 |
| Redis | 内存限流 + 内存缓存 | 多副本不共享 |
| Qdrant | `InMemoryVectorStore` | 重启后向量丢失，BM25 重建 |
| PostgreSQL | SQLite | 功能可用，并发弱 |
| 数据库整体不可用 | 启动失败 | `/ready` 报 not ready |

**降级是否可见**：`/capabilities` 会报告实际后端，`degraded` 为 true 表示至少一项退化。这是排查“系统正常但效果不对”的第一入口。

## 14.2 重试

`app/core/retry.py` 是全抖动指数退避：

```python
delay = random.uniform(0.0, min(cap, base * 2**attempt))
```

- 默认 3 次，`base=0.5s`，`cap=8s`。
- 只重试 `exc.retryable` 的 `AppError`；超时/连接错误单独处理。
- 400/401/403/404/422 不重试；408/429/500/502/503/504 可重试。

为什么用全抖动？多个实例同时失败时，固定退避会让它们同时重试，形成二次洪峰；随机化把重试摊开。

## 14.3 限流

`app/infra/rate_limit.py`：

- `InMemoryRateLimiter`：单进程滑动窗口。
- `RedisRateLimiter`：多副本共享。

`ChatService._enforce_rate_limit()` 按 `user:{user_id}` 计数，超限抛 `RateLimitError`（429）。

**一个实现细节**：`stream()` 是异步生成器，限流在第一次迭代时才执行；此时响应头已经发出，**429 无法变成 HTTP 状态**，客户端只能看到流中断。这是 SSE 场景的已知坑。

## 14.4 结构化日志

`app/observability/logging.py`：

```python
formatter = JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s %(request_id)s")
handler.addFilter(ContextFilter())
```

`ContextFilter` 从 `contextvars` 取 `trace_id` / `request_id`，并给 `msg` 打 PII 掩码。

调用链：

```text
main 中间件 bind_request_context(trace_id, request_id)
   ↓ contextvars
ChatService._observe → logger.info("chat_completed", extra={...})
   ↓
JSON 日志（带 trace_id）
```

`finally` 必须 `reset`，否则 contextvar 会泄漏到后续请求。

## 14.5 指标

`app/observability/metrics.py` 定义了 7 个 Prometheus 指标：

| 指标 | 类型 | 标签 |
|:---|:---|:---|
| `cs_requests_total` | Counter | strategy / intent / status |
| `cs_request_latency_seconds` | Histogram | 0.05–16s |
| `cs_stage_latency_seconds` | Histogram | stage（intent/retrieval/llm） |
| `cs_tool_calls_total` | Counter | tool / status（ok/fallback/denied/error/idempotent/conflict） |
| `cs_tokens_total` | Counter | kind |
| `cs_hallucination_flags_total` | Counter | 无 |
| `cs_routing_total` | Counter | strategy |

`/metrics` 由 `main.py` 暴露，**没有鉴权**；生产应放在内网或加网关。

## 14.6 健康检查的三种语义

| 接口 | 回答的问题 | 关键实现 |
|:---|:---|:---|
| `/health` | 进程活着吗 | 固定 `{"status":"ok"}` |
| `/ready` | 能接流量吗 | 只把 database 当硬依赖；Redis 未配置算 ready |
| `/capabilities` | 实际用了什么后端 | 反射容器里的 provider |

`/ready` 里 LLM 的 `ping()` 只判断 key 是否存在，**不发网络请求**——readiness 必须便宜。代价是：key 配了但失效时，`/ready` 仍然绿。

## 14.7 异常映射

| 异常 | HTTP | 错误码 |
|:---|:---:|:---|
| `InvalidRequestError` | 400 | INVALID_REQUEST |
| `UnauthorizedError` | 401 | UNAUTHORIZED |
| `ToolPermissionError` | 403 | TOOL_PERMISSION_DENIED |
| `RateLimitError` | 429 | RATE_LIMITED |
| `RetrievalError` | 503 | VECTOR_DB_UNAVAILABLE / RETRIEVAL_TIMEOUT |
| `LLMProviderError` | 503 | LLM_PROVIDER_UNAVAILABLE / LLM_TIMEOUT |
| `LLMOutputError` | 502 | LLM_OUTPUT_INVALID |
| `GuardrailError` | 400 | QUERY_OUT_OF_SCOPE / PROMPT_INJECTION_BLOCKED |

`app/main.py` 统一转成 `{error_code, message, trace_id}`，生产环境不暴露细节。

## 14.8 设计取舍

- **健康检查分层**：liveness 便宜、readiness 只认硬依赖，避免“模型慢导致整个 Pod 被重启”。
- **指标进程内**：不引入 Pushgateway，多副本由 Prometheus 聚合。
- **降级不隐藏**：`capabilities` 是唯一的“效果体检入口”。

---

# 第 15 章 评测体系

## 15.1 三套数据集

| 文件 | 条数 | 字段 | 用途 |
|:---|:---:|:---|:---|
| `eval/dataset/intent_100.jsonl` | 100 | `id/query/intent` | 意图准确率 |
| `eval/dataset/rag_eval.jsonl` | 60 | `id/query/relevant_doc_ids/gold_answer_contains` | 检索 P@1/R@3/MRR |
| `eval/dataset/e2e_eval.jsonl` | 20 | `id/query/user_id/expect_refused/expect_keywords/expect_strategy/expect_pending` | 端到端行为 |

`intent_100` 覆盖 11 个标签；`rag_eval` 覆盖 31 篇 SOP；`e2e_eval` 覆盖政策、工单、资产、写操作、越权、转人工。

## 15.2 指标定义

`eval/metrics.py`：

```python
precision_at_k(relevant, retrieved, k)
recall_at_k(relevant, retrieved, k)
hit_at_k(relevant, retrieved, k)
mrr(relevant, retrieved)
percentile(values, p)
classification_report(pairs)
```

检索评测会先把 chunk 归并到文档：`document_id.rsplit("_", 1)[0]` 去掉哈希后缀，再去重保序。这样 P@1 衡量的是“第一篇文章对不对”，而不是“第一个 chunk 对不对”。

## 15.3 runner 的四个 task

`eval/runner.py`：

| task | 需要 LLM | 做什么 |
|:---|:---:|:---|
| `intent` | 否 | 规则/覆盖层准确率；`--llm` 时加 LLM 版本 |
| `retrieval` | 否 | BM25 / 向量 / RRF / 精排四套系统对比 |
| `generation` | 是 | 无检索 / RAG / RAG+自纠错三档，LLM 判忠实度 |
| `e2e` | 否 | 跑 20 条端到端，统计拒答/路由/确认/关键词/延迟 |
| `all` | 可选 | 前四者组合；无 key 时 e2e 走离线 provider |

跑完写 `eval/reports/{task}_{timestamp}.json` 和 `latest.json`，并打印 `resume_bullets`。

## 15.4 当前数字（2026-11-01）

检索（bge-small，未加载 CE）：

| 系统 | P@1 | R@3 | MRR |
|:---|:---:|:---:|:---:|
| BM25（标题+小节） | 68.3% | 94.2% | 0.804 |
| bge-small | 61.7% | 95.0% | 0.776 |
| BM25+bge+RRF | **71.7%** | 91.7% | **0.826** |
| +词法重排 | 70.0% | 88.3% | 0.807 |

意图：

| 方式 | 准确率 |
|:---|:---:|
| 规则 + FAQ 兜底 | 100.0% |
| 纯覆盖层 | 90.0%（10 条未覆盖） |

端到端（20 条，离线）：

| 指标 | 结果 |
|:---|:---:|
| 拒答 / 路由 / 确认流 | 100% / 100% / 100% |
| 关键词命中 | 87.5% |
| P50 / P95 | 40.0ms / 57.7ms |

## 15.5 口径陷阱

- 意图 100% 是“规则 + FAQ 兜底”，而且集合由同一词表构造，**存在过拟合**；纯覆盖层只有 90%。
- 词法重排不是 Cross-Encoder，不能当精排收益。
- E2E 用离线 provider，40ms 只说明链路耗时，不代表线上 LLM 延迟。
- 数据集是自建的、规模小，不能和公开 benchmark 横向比较。

这些在 `eval/MEASURED.md` 的“不要写”一节里逐条列了。

## 15.6 怎么加一条评测

1. 在对应 `.jsonl` 追加一行，字段与现有保持一致；
2. `rag_eval` 的 `relevant_doc_ids` 用文件名（不含 `.md` 和哈希）；
3. `e2e` 的 `expect_strategy` 写 `direct/single/multi/agent/refuse`；
4. 跑 `python -m eval.runner --task e2e`，看 `cases` 里哪条不符合预期。

## 15.7 设计取舍

- **离线评测不依赖线上流量**：可复现、可回归。
- **偏好“能解释的指标”**：P@1 比“感觉准”有用。
- **明确写限制**：自建集、同模型裁判、离线延迟，都写进口径文件。

---

# 第 16 章 前端工作台

## 16.1 组件树

```text
App
├─ Sidebar（会话列表、搜索、主题、新建）
├─ main
│  ├─ topbar（连接状态、API 文档）
│  ├─ MessageView
│  │  ├─ user bubble
│  │  ├─ assistant markdown + CitationList + ActionCard
│  │  └─ copy / stopped 状态
│  └─ Composer（输入、发送、停止）
└─ SearchDialog（本地会话搜索）
```

状态集中在 `useChat`，组件只负责展示与回调。

## 16.2 `useChat` 的 reducer

`frontend/src/hooks/useChat.ts` 用 `useReducer` 管理：

| action | 行为 |
|:---|:---|
| `select` / `delete` | 切换、删除会话 |
| `start` | 插入 user 消息 + 空的 streaming assistant |
| `token` | 追加流式文本 |
| `complete` | 用最终 `ChatResponse` 覆盖内容、引用、pending、策略、延迟 |
| `fail` | 标记 error / stopped |
| `dismiss` | 清掉某条消息的 pendingAction |

发送流程：

```ts
dispatch({type:"start", ...})
await streamChat(payload, onEvent, signal)
  onEvent token → dispatch token
  onEvent answer → dispatch complete
```

`busyRef` 防重复发送；`AbortController` 支持“停止生成”。

## 16.3 SSE 解析

`frontend/src/lib/sse.ts` 的 `SseDecoder` 处理“UTF-8 字符跨 chunk、帧边界跨 read”：

```ts
this.buffer += this.decoder.decode(bytes, {stream: true})
const boundary = /\r?\n\r?\n/.exec(this.buffer)
```

每帧只取 `data:` 行，拼成 JSON，要求含 `event` 字段。后端用 `JSONServerSentEvent`，所以 **SSE 帧本身没有 `event:` 行，事件名在 JSON 的 `event` 字段里**。

## 16.4 消息渲染

`MessageView.tsx`：

- assistant 用 `ReactMarkdown + remarkGfm` 渲染；
- `CitationList` 按 `chunk_id` 去重，显示 `title · section`；
- `ActionCard` 展示 `pending_action.summary`，两个按钮：确认执行 / 取消；
- `disabled={busy}` 防止请求进行中重复确认；
- 复制按钮用 `navigator.clipboard`，失败静默。

## 16.5 本地存储

`frontend/src/lib/storage.ts`：

- key：`it-helpdesk-web:v1`
- 最多 50 个会话、每个 100 条消息；
- `pagehide` 时强制落盘；
- `state === "streaming"` 的消息在加载时改成 `stopped`，避免刷新后永远转圈。

**边界**：会话只存在浏览器，换设备/清缓存就没了；后端没有历史列表接口。

## 16.6 API 地址与确认

`lib/api.ts`：

```ts
const API_BASE = import.meta.env.VITE_API_BASE ?? "";
```

开发时 Vite 代理 `/api` 到 8002；生产可指向独立 API。

**注意一个真实的坑**：后端没有 CORS 中间件。如果把 `VITE_API_BASE` 设成绝对地址（如 `http://127.0.0.1:8002`），浏览器会从 5173 跨域请求 8002，直接被拦截。本地开发应**留空**，让 Vite 代理转发；`start.ps1` 已移除这个变量。

确认执行时，前端把 `confirm_action_id` 放进请求体：

```ts
chat.send("确认执行", action.action_id)
```

`App.tsx` 的 `confirm()` 成功后才 `dismissAction`，避免确认失败但卡片消失。

## 16.7 设计取舍

- **乐观 UI**：先插入 streaming 消息，再逐步补文本。
- **最终答案覆盖流式文本**：`complete` 用后端 `answer` 覆盖，保证与引用一致。
- **本地会话**：零后端成本，但不可跨设备。


# 第 17 章 部署与配置

## 17.1 配置从哪来

`app/config/settings.py` 用 `pydantic-settings`：

```python
model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
```

优先级：**环境变量 > `.env` > 默认值**。`get_settings()` 带 `lru_cache`，测试里用 `clear_settings_cache()` 清缓存。

关键配置：

| 配置 | 默认 | 说明 |
|:---|:---|:---|
| `app_env` | development | testing 会跳过本地模型 |
| `deepseek_api_key` | 空 | 空则离线 |
| `deepseek_model` | deepseek-chat | 可换模型名 |
| `local_embedding_enabled` | true | 本地 bge |
| `cross_encoder_enabled` | true | 本地精排 |
| `database_url` | sqlite+aiosqlite | 生产换 PG |
| `redis_url` / `qdrant_url` | 空 | 空则内存 |
| `retrieval_top_k_simple` / `complex` | 3 / 8 | 召回数 |
| `rrf_k` | 60 | RRF 常数 |
| `rerank_top_n` | 5 | 精排保留 |
| `max_retrieval_hops` | 3 | 多跳上限 |
| `token_budget` | 128000 | 上下文预算 |
| `max_agent_steps` / `max_tool_calls` | 8 / 6 | 循环保护 |
| `rate_limit_per_minute` | 60 | 每用户 |
| `admin_api_token` | 空 | 生产为空则禁用管理接口 |

## 17.2 本地启动的三条路径

| 方式 | 命令 | 适用 |
|:---|:---|:---|
| 一键脚本 | `start.bat` | Windows 演示 |
| PyCharm | `Full stack` 运行配置 | 日常开发 |
| 手动 | `uvicorn app.asgi:app --port 8002` + `npm run dev` | 其他系统 |

前端构建后，FastAPI 会在 `/` 托管 `frontend/dist`。

## 17.3 Docker 三档

| 文件 | 组件 | 适用 |
|:---|:---|:---|
| `docker-compose.yml` | API + SQLite + 内存检索 | 演示、CI |
| `docker-compose.single.yml` | API + PostgreSQL + Redis | 单机生产 |
| `docker-compose.multi.yml` | 2×API + PostgreSQL + Redis + Qdrant + Nginx | 多实例 |

演示档显式关闭本地模型：

```yaml
LOCAL_EMBEDDING_ENABLED: "false"
CROSS_ENCODER_ENABLED: "false"
UNSTRUCTURED_ENABLED: "false"
```

这样镜像小、启动快，代价是检索效果下降——`/capabilities` 会显示 `retriever: bm25`、`reranker: lexical`。

## 17.4 启动顺序

`build_container()`：

```text
Settings
  → build_infrastructure：engine → init_schema → session_factory → 可选 Redis
  → build_retrieval：embedding → cache → ingest_knowledge → HybridRetriever → Reranker
  → 选 LLM（DeepSeek / Offline）
  → 选限流（Redis / 内存）
  → build_tool_registry → 合并 MCP
  → ChatService（内部 build_graph）
```

`init_schema` 用 `Base.metadata.create_all`，**不是 Alembic**。这是演示便利，生产应改为部署时迁移。

## 17.5 上线前检查清单

- [ ] 服务端认证 `user_id`，不能信任请求体。
- [ ] `pending_action` 从进程内字典迁到 Redis/数据库。
- [ ] 审批单状态机接通（`mark_approval` + 审批 API + 过期清扫）。
- [ ] 数据库迁移改用 Alembic，不在启动时 `create_all`。
- [ ] `/metrics`、`/admin` 放到内网或加网关鉴权。
- [ ] 关闭 CORS 通配，限制前端来源。
- [ ] 配置 `ADMIN_API_TOKEN`，生产环境不能为空。
- [ ] 知识库增量更新与删除同步。
- [ ] 日志接入集中采集，确认 `trace_id` 能串起来。

---

# 第 18 章 二次开发配方

## 18.1 加一篇 SOP

1. 在 `knowledge/` 新建 `.md`，文件名前缀决定分类（`account_`、`vpn_`、`device_`、`software_`、`security_`、`meeting_`...）。
2. 结构建议：

```markdown
# 标题

> 适用范围 · 责任人 · 版本

## 一句话
## 申请条件
## 流程
## 常见问题
## SLA
## 例外与红线
```

3. 重启服务触发全量 ingest。
4. 在 `eval/dataset/rag_eval.jsonl` 加一条检索题，跑 `--task retrieval` 看是否命中。

注意：切块按 H1–H3，**每个小节尽量不超过 500 字**，否则会被字符窗口硬切。

## 18.2 加一个工具

以“查询会议室空闲”为例：

```python
class RoomInput(BaseModel):
    room: str = Field(min_length=1, max_length=32)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

class GetRoomTool(RepositoryBackedTool, Tool):
    name = "get_room_availability"
    description = "查询会议室某天的空闲时段。只读。参数 room 会议室名，date 日期。"
    risk = ToolRisk.READ
    input_model = RoomInput

    async def execute(self, parsed, context):
        ...
        return ToolResult(name=self.name, success=True, output={...})
```

然后：

1. 在 `app/tools/factory.py` 注册；
2. 在 `app/skills/definitions/` 加一个 skill（可选）；
3. 在 `app/agents/nodes/executor.py` 的 `READ_FALLBACKS` 加降级目标（可选）；
4. 加单测：参数校验、可见性、失败降级；
5. 加一条 e2e 用例。

**写工具**额外要：`risk=WRITE`、在 `_explicit_write_request` 加触发词、在 `_missing_required_args` 加必填槽位、确认走 `create_approval` 而不是直接改数据。

## 18.3 加一个意图

1. `app/core/enums.py` 加 `IntentLabel`；
2. `app/prompts/intent.py` 加标签与样例；
3. `app/agents/nodes/intent_overlay.py` 加高精度词（可选）；
4. `app/retrieval/adaptive.py` 决定它走 DIRECT/SINGLE/MULTI/AGENT；
5. `app/skills/loader.py` 加意图→技能映射；
6. `eval/dataset/intent_100.jsonl` 加样本，重跑准确率。

漏掉第 4 步，新意图会默认走 `SINGLE`；漏掉第 5 步，规划器不会选对应工具。

## 18.4 换模型

只改 `.env`：

```ini
DEEPSEEK_MODEL=deepseek-reasoner
```

前提是模型兼容 OpenAI chat completions 且支持 `response_format=json_object`。项目所有结构化输出都依赖 JSON 模式；不支持的模型会让 `parse_model` 频繁失败，然后退回规则。

## 18.5 开启真实向量与精排

```ini
LOCAL_EMBEDDING_ENABLED=true
CROSS_ENCODER_ENABLED=true
HF_ENDPOINT=https://hf-mirror.com
```

首次会下载 bge-small（~95MB）和 bge-reranker-base（~1.1GB）。如果只想开向量、不想下精排，保持 `CROSS_ENCODER_ENABLED=false`。

## 18.6 把确认表迁到 Redis

当前 `ChatService._pending_actions` 是进程内字典。改造点：

1. 定义 `PendingStore` 协议：`put(action_id, payload, ttl)` / `get(action_id)` / `delete`；
2. 内存实现保持不变，Redis 实现用 `SETEX`；
3. `_remember_pending` / `_resolve_confirmation` 改为调用 store；
4. 多副本共享同一 Redis 即可。

注意：Redis 里存的是 `ActionProposal` 的 JSON，取出后要重新校验 `session_id` / `user_id`。

## 18.7 接通审批推进

当前只有 `create_approval`，没有审批接口。补法：

1. 新增 `POST /api/v1/approvals/{id}/approve`，校验审批人角色；
2. 调 `repository.mark_approval(id, status=APPROVED, approver_id=...)`；
3. 审批通过后调 `mark_approval_executed`，并触发真实系统开通；
4. 加定时任务扫描 `expires_at < now` 的 pending 单，置为 `expired`；
5. 写审计。

---

# 第 19 章 排错与面试复盘

## 19.1 排错表

| 现象 | 可能原因 | 排查 |
|:---|:---|:---|
| 所有问题都 `single` | 意图分类全落 `faq_policy` | 看 `/capabilities` 的 `llm`；检查 key；看日志 `intent` |
| 中文请求变 `???` | 客户端编码 | 显式 UTF-8；用 Python/httpx 复测 |
| 回答是“资料节选” | 模型不可用 | `llm=offline` 或 401；看 API 日志 |
| 检索命中错文档 | 向量/精排降级 | `/capabilities` 看 `retriever/reranker`；开 bge 重试 |
| 写操作没有 pending | 触发词没命中 | 看 `_explicit_write_request`；换“帮我申请...”说法 |
| 确认报“不存在或已过期” | 跨会话/超 15 分钟/服务重启 | 重新发起；多副本需持久化 |
| 重复建单 | 幂等键没带 | 确认轮带 `confirm_action_id`；客户端重试带 `idempotency_key` |
| 前端一直转圈 | SSE 中断 | 看 Network 的 stream；看后端是否 500 |
| 5173 空白 | 前端依赖/接口地址 | `npm ci`；`VITE_API_BASE` 留空用代理 |
| 浏览器报 CORS | `VITE_API_BASE` 设了绝对地址 | 留空，让 Vite 代理；或给后端加 CORS |
| Docker 里没有演示数据 | 镜像不含 `scripts/`，启动不 seed | 进容器执行 seed，或挂载脚本 |
| 多副本确认报“已过期” | 轮询到另一副本，pending 在内存 | 会话粘滞，或把 pending 迁 Redis |
| SSE 60 秒断流/攒批 | Nginx 未关 buffering | `proxy_buffering off`、调大 `proxy_read_timeout` |

## 19.2 已知问题清单

这些是读代码和实测确认的边界，不是猜测。写在这里是为了避免“以为它已经做了”：

| # | 问题 | 影响 | 建议 |
|:---:|:---|:---|:---|
| 1 | `user_id` 未认证 | 可伪造身份读他人工单 | 服务端认证并绑定 |
| 2 | `pending_action` 在进程内 | 多副本/重启丢失 | 迁 Redis，TTL key |
| 3 | 审批状态机无推进器 | `approved/executed` 不会发生 | 补审批 API + 过期清扫 |
| 4 | `escalate_to_human` 是 EXTERNAL | 不落库、不审计 | 改成 WRITE 或补审计 |
| 5 | 后端无 CORS | 绝对 base 即跨域 | 代理或加中间件 |
| 6 | Docker 不 seed | 默认无 TKT/AST 数据 | 启动参数或挂载脚本 |
| 7 | 多副本 SSE 被 Nginx 攒批 | 流式变“一次性” | 关 buffering |
| 8 | 前端只查 liveness | DB 挂了仍显示已连接 | 改查 `/ready` 并轮询 |
| 9 | “取消”只关本地卡片 | 服务端 pending 留到过期 | 增加 cancel 接口 |
| 10 | 压缩 docstring 与实现不一致 | 70–85% 档并不做语义摘要 | 以代码为准 |

## 19.3 二十个高频问题

**Q1：为什么不做成“所有问题都检索”？**
简单问题和越界问题不该走向量检索：问候浪费一次 embedding，越权还容易被检索结果带偏。五路分流让每条路径的成本和风险可控。

**Q2：意图 100% 可信吗？**
不可信。100% 是“规则 + FAQ 兜底”在自建 100 条上的结果，存在过拟合；纯覆盖层只有 90%。真实场景要看混淆矩阵和长尾样本。

**Q3：RRF 为什么不用分数加权？**
BM25 和余弦的量纲不同，加权需要调参；RRF 只看排名，天然可比，k=60 是论文默认值。

**Q4：为什么 BM25 要把标题和小节一起索引？**
短问句（“VPN 怎么申请”）在正文里可能匹配不到，但小节标题“申请资格”能直接命中。实测 P@1 从 58.3% 提到 68.3%。

**Q5：Self-RAG 怎么停？**
两个条件：评分器说 `sufficient=true`，或达到 `max_retrieval_hops=3`。评分器失败时退化为“有结果就算够”。

**Q6：写操作怎么防重复？**
四层：planner 出 `pending_action`、executor 无确认不执行、`assert_permitted` 权限断言、幂等表按 `action_id + 参数指纹` 去重。

**Q7：确认为什么绑定 session 和 user？**
否则拿到 `action_id` 的人可以替你执行。四个校验：存在、未过期、同会话、同用户。

**Q8：忠实度检查失败怎么办？**
先让模型自纠错一次；仍不支持就用检索原文做抽取式回答；再不行拒答。检查器本身不可用时会 fail-closed，走抽取式。

**Q9：有哪些降级？**
LLM→离线规则、向量→哈希、精排→词法、Redis→内存、Qdrant→内存、PG→SQLite。`/capabilities` 会报告实际后端。

**Q10：为什么要有 `/capabilities`？**
因为降级是静默的。没有它，系统“能跑”和“效果正常”无法区分。

**Q11：token 怎么估算？**
DeepSeek tokenizer 不公开，用 `len(text)/1.5` 的启发式；不精确，但足够判断是否接近预算。

**Q12：为什么压缩放在生成之后？**
生成需要完整上下文；压缩只影响下一轮。先压缩会让本轮回答缺证据。

**Q13：越权为什么返回 404 而不是 403？**
403 等于告诉攻击者“ID 存在但你没权限”，可以被枚举；统一“不存在”更安全。

**Q14：SSE 为什么最后才发 token？**
答案可能被忠实度检查改掉。先流式输出会让用户看到一段随后被替换的文字；项目选择“校验完再切片发”。

**Q15：`pending_action` 存内存有什么问题？**
多副本不共享、进程重启即丢、无法审计。生产应迁 Redis 或数据库。

**Q16：评测最容易骗自己的地方是什么？**
自建集过拟合、同模型裁判偏乐观、离线延迟当线上、词法重排当 Cross-Encoder。

**Q17：加一个工具要改哪些文件？**
工具类、`factory.py`、可选的 skill、`READ_FALLBACKS`、测试、e2e 用例。写工具还要加触发词与必填槽位。

**Q18：怎么支持多副本？**
把 `pending_action`、限流、检索缓存迁到 Redis；数据库换 PG；Qdrant 独立部署；确认表用 TTL key。

**Q19：为什么用 LangGraph 而不是自己写状态机？**
条件边、状态合并、`astream(updates)` 都是现成的；自己写要处理节点顺序、增量合并和流式事件，容易和业务耦合。

**Q20：这个项目最大的不足？**
身份未认证、确认表在内存、审批流只写了入口、知识库全量 ingest、合成数据。README 的“使用边界”一节没有美化这些。

## 19.4 学习检查清单

读完这份手册，应该能独立回答：

- [ ] 画出 HTTP → ChatService → Graph → Tool/Retriever 的完整链路
- [ ] 说出 5 条策略各自的触发条件与节点
- [ ] 解释 `TKT`/`AST` 为什么必须优先于 LLM 路由
- [ ] 说清 chunk 的 500/60 与稳定 ID 的生成方式
- [ ] 解释 RRF 公式与 k=60 的含义
- [ ] 说清写操作的四层保护
- [ ] 解释 `pending_action` 与 `ApprovalRow` 的区别
- [ ] 说出忠实度检查失败后的三条路径
- [ ] 解释三级压缩阈值
- [ ] 说出至少 5 种降级
- [ ] 解释评测的三个数据集与指标口径
- [ ] 能独立加一篇 SOP、一个工具、一个意图

---

# 附录 A 命令速查

```bash
# 启动 / 停止
start.bat
start.bat -WithModels
stop.bat

# 后端
.venv\Scripts\python -m uvicorn app.asgi:app --port 8002
.venv\Scripts\python -m app.cli

# 前端
cd frontend && npm run dev
cd frontend && npm test
cd frontend && npm run build

# 质量
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m ruff check app eval tests
.venv\Scripts\python -m ruff format --check app eval tests
.venv\Scripts\python -m mypy

# 评测
.venv\Scripts\python -m eval.runner --task intent
.venv\Scripts\python -m eval.runner --task retrieval
.venv\Scripts\python -m eval.runner --task e2e
.venv\Scripts\python -m eval.runner --task all --llm

# 数据
.venv\Scripts\python scripts\seed_demo.py
```

# 附录 B 文件索引

| 文件 | 一句话 |
|:---|:---|
| `app/asgi.py` | ASGI 入口 |
| `app/main.py` | FastAPI 工厂、中间件、错误信封 |
| `app/services/chat_service.py` | 对话总导演 |
| `app/services/container.py` | 依赖装配与降级 |
| `app/agents/graph.py` | 10 节点状态机 |
| `app/agents/state.py` | `AgentState` 契约 |
| `app/agents/nodes/guardrail.py` | 注入拦截 |
| `app/agents/nodes/intent.py` | 规则 + LLM 分类 |
| `app/agents/nodes/intent_overlay.py` | 高精度词表 |
| `app/agents/nodes/router.py` | 意图/复杂度路由节点 |
| `app/agents/nodes/retrieval.py` | 单轮/多跳检索 |
| `app/agents/nodes/planner.py` | 计划与 pending |
| `app/agents/nodes/executor.py` | 权限、幂等、降级 |
| `app/agents/nodes/generate.py` | 生成与离线回答 |
| `app/agents/nodes/faithfulness.py` | 忠实度与自纠错 |
| `app/agents/nodes/memory.py` | 压缩收尾 |
| `app/retrieval/adaptive.py` | 五路规则 |
| `app/retrieval/hybrid.py` | BM25+向量+RRF |
| `app/retrieval/self_rag.py` | 多跳循环 |
| `app/retrieval/query_rewrite.py` | 查询改写 |
| `app/retrieval/chunking.py` | 切块与稳定 ID |
| `app/retrieval/ingest.py` | 知识入库 |
| `app/retrieval/vector.py` | 向量库 |
| `app/retrieval/fusion.py` | RRF |
| `app/retrieval/reranker.py` | 精排封装 |
| `app/retrieval/cache.py` | 检索缓存 |
| `app/tools/base.py` | 工具基类 |
| `app/tools/factory.py` | 10 工具注册 |
| `app/tools/ticket_tools.py` | 工单工具 |
| `app/tools/asset_tools.py` | 资产工具 |
| `app/tools/access_tools.py` | 权限/密码工具 |
| `app/tools/software_tools.py` | 软件工具 |
| `app/tools/knowledge_tools.py` | 检索与转人工 |
| `app/repositories/models.py` | 8 张表 |
| `app/repositories/ticket_repository.py` | 工单/资产/审批 |
| `app/repositories/idempotency.py` | 幂等表 |
| `app/guardrails/injection.py` | 注入正则 |
| `app/guardrails/hallucination.py` | 忠实度 |
| `app/memory/budget.py` | token 估算与阈值 |
| `app/memory/compression.py` | 三级压缩 |
| `app/memory/summarizer.py` | 摘要 |
| `app/providers/deepseek.py` | DeepSeek 客户端 |
| `app/providers/embeddings.py` | 三种 embedding |
| `app/providers/reranker.py` | CE + 词法回退 |
| `app/providers/json_parser.py` | JSON 修复 |
| `app/observability/metrics.py` | 7 个指标 |
| `app/observability/logging.py` | JSON 日志 |
| `app/config/settings.py` | 全部配置 |
| `frontend/src/hooks/useChat.ts` | 会话状态机 |
| `frontend/src/lib/api.ts` | 流式请求 |
| `frontend/src/lib/sse.ts` | SSE 解码 |
| `frontend/src/components/MessageView.tsx` | 消息与确认卡片 |
| `eval/runner.py` | 四个评测任务 |
| `eval/metrics.py` | 指标实现 |

# 附录 C 术语表

| 术语 | 含义 |
|:---|:---|
| RAG | Retrieval-Augmented Generation，检索增强生成 |
| RRF | Reciprocal Rank Fusion，按排名融合多路检索 |
| Self-RAG | 检索后自评，不够再改写补检 |
| HITL | Human-in-the-loop，人工确认/审批 |
| Embedding | 文本向量化 |
| Rerank | 对召回结果二次排序，通常用 Cross-Encoder |
| Chunk | 切块后的检索单元 |
| SSE | Server-Sent Events，服务器推送流 |
| SLA | Service Level Agreement，响应/解决时效 |
| Idempotency | 同一请求重复执行结果一致 |
| Trace ID | 贯穿一次请求的关联 ID |

---

> 手册基于 `afebfeb` 版本代码整理。代码继续演进时，以源文件与 `eval/MEASURED.md` 为准。
