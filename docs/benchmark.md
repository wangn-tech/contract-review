# 压测报告（模板）

> 本文档为压测执行模板，M6 在 Docker 环境跑完 locust 后回填真实数据。

## 环境

| 项 | 值 |
| --- | --- |
| 时间 | 待回填 |
| 部署 | docker compose（backend 2 worker） |
| 压测机 | 待回填（CPU/内存/网络） |
| 并发 | 20 用户，5/s ramp |
| 时长 | 5 分钟 |
| LLM | DeepSeek-V3.2 / V4-Flash（SiliconFlow） |
| 可观测 | Langfuse 自托管 trace 关联 |

## 场景与指标

| 场景 | 指标 | P50 | P95 | 成功率 |
| --- | --- | --- | --- | --- |
| POST /api/auth/login | 延迟 | | | |
| GET /api/contracts | 延迟 | | | |
| POST /api/reviews/start (SSE) | TTFT / 完整时长 | | | |
| POST /api/chats (SSE) | 首 token / 完整时长 | | | |
| 整体吞吐 | req/s | | | |

## Langfuse 观测

- 每个审阅任务 = 1 个 trace（span: intent → router → specialists → gate → arbitration）；
- 检索链路单独 span（dense/sparse/RRF/rerank 各阶段耗时）；
- 关注：LLM 调用耗时占比、RAG 检索 P95、专家并行度收益（对比串行基线）。

## 结论与优化

- 待回填（例如：SSE 长连接 + 慢 LLM 是吞吐瓶颈；建议上 K8s 水平扩展 + 结果缓存）。
