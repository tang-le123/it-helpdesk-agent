# 04 · 部署

## 本地（推荐）

Python 3.11–3.12。示例使用 conda：

```bash
conda create -n it-helpdesk python=3.12 -y
conda activate it-helpdesk
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.asgi:app --reload --port 8002
```

首次使用本地 embedding 会下载 `BAAI/bge-small-zh-v1.5`（约 95MB）。国内建议：

```bash
set HF_ENDPOINT=https://hf-mirror.com
```

不想下载模型时，关闭两路本地模型，走哈希向量 + 词法重排：

```bash
set LOCAL_EMBEDDING_ENABLED=false
set CROSS_ENCODER_ENABLED=false
```

## 前端

```bash
cd frontend
npm ci
npm run dev
```

访问 `http://127.0.0.1:5173`。`npm run build` 后，FastAPI 会在 `/` 提供 `frontend/dist`。

## Docker

```bash
docker compose up --build -d                 # SQLite + 内存检索
docker compose -f docker-compose.single.yml up -d   # PostgreSQL + Redis
docker compose -f docker-compose.multi.yml up -d    # 多实例 + Qdrant + Nginx
```

## 关键环境变量

| 变量 | 默认 | 说明 |
|:---|:---|:---|
| `DEEPSEEK_API_KEY` | 空 | 为空时进入离线模式，只返回检索原文或工具结果 |
| `KNOWLEDGE_DIR` | `knowledge` | 启动时全量 ingest |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/local/app.db` | 生产换 PostgreSQL |
| `REDIS_URL` | 空 | 为空用内存限流与缓存 |
| `QDRANT_URL` | 空 | 为空用内存向量库 |
| `QDRANT_COLLECTION` | `it_knowledge` | Qdrant 集合名 |
| `LOCAL_EMBEDDING_ENABLED` | `true` | 本地 bge-small |
| `CROSS_ENCODER_ENABLED` | `true` | 本地 bge-reranker |
| `RATE_LIMIT_PER_MINUTE` | `60` | 每用户每分钟请求数 |
| `ADMIN_API_TOKEN` | 空 | 管理接口令牌 |

完整列表见 `.env.example` 与 `app/config/settings.py`。

## 健康检查

```bash
curl http://127.0.0.1:8002/api/v1/health
curl http://127.0.0.1:8002/api/v1/capabilities
```

`capabilities` 会报告实际生效的数据库、缓存、向量库、检索、精排与 LLM 后端；降级时以它为准。

## 上线前必须补

- 服务端认证 `user_id`，不能信任请求体。
- 待确认操作从进程内字典迁到持久化存储，支持多副本。
- 知识库增量入库与删除同步。
- 数据库迁移改为部署时执行 Alembic，而不是启动时 `create_all`。
