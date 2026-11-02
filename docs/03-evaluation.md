# 03 · 评测

## 数据集

| 文件 | 条数 | 说明 |
|:---|:---:|:---|
| `eval/dataset/intent_100.jsonl` | 100 | 11 个意图标签，含易混对 |
| `eval/dataset/rag_eval.jsonl` | 60 | 31 篇 SOP，带 `relevant_doc_ids` |
| `eval/dataset/e2e_eval.jsonl` | 20 | 政策 / 工单 / 资产 / 写操作 / 越权 / 转人工 |

## 命令

```bash
# 只测意图（规则 + 覆盖层）
python -m eval.runner --task intent

# 检索（BM25 / 稠密 / RRF / 精排）
HF_HUB_OFFLINE=1 python -m eval.runner --task retrieval

# 端到端（无 API Key 时自动走离线 provider）
python -m eval.runner --task e2e

# 全部 + LLM 判官
python -m eval.runner --task all --llm
```

报告写入 `eval/reports/*.json`（已被 `.gitignore` 忽略），同时更新 `latest.json`。

## 当前数字

见 [`eval/MEASURED.md`](../eval/MEASURED.md)。摘要（2026-11-01，bge-small，未加载 Cross-Encoder）：

| 系统 | P@1 | R@3 | MRR |
|:---|:---:|:---:|:---:|
| BM25（标题+小节） | 68.3% | 94.2% | 0.804 |
| bge-small 稠密 | 61.7% | 95.0% | 0.776 |
| BM25+bge+RRF | 71.7% | 91.7% | 0.826 |
| +词法重排 | 70.0% | 88.3% | 0.807 |

端到端：拒答 100%、路由 100%、确认流 100%、关键词 87.5%。

## 口径与限制

- 意图 100% 是「规则 + FAQ 兜底」，集合由同一词表构造，存在过拟合；纯覆盖层是 90%。
- 稠密模型是 `bge-small-zh-v1.5`；Cross-Encoder 未加载，词法重排**不是**精排。
- E2E 用离线 provider，40ms 只说明链路耗时，不代表线上 LLM 延迟。
- 数据集是自建的，规模小，不适合与公开 benchmark 横向比较。
