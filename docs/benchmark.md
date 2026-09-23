# 性能压测报告（Locust）

> 实测环境：云电脑（无 Docker，本地 SQLite + fakeredis + Qdrant 1.19 + SiliconFlow 真实 LLM）
> 后端端口 8090；数据：6 账号 × 独立合同/会话；压测时间 2026-09-23

## 1. 场景与配置

| 项 | 值 |
|---|---|
| 工具 | Locust 2.46.6（headless） |
| 常规场景 | 6 并发用户 × 6 分钟（登录/列表/聊天 SSE 混合，权重 2:2:1） |
| 审阅专项 | 2 并发用户 × 8 分钟（仅审阅 SSE） |
| LLM 链路 | 真实 SiliconFlow（DeepSeek-V3.2 审阅 / V4-Flash 聊天） |

## 2. 常规场景指标（6 用户 / 6 分钟）

| 接口 | 请求数 | 成功率 | Avg | P50 | P95 | P99 | Max |
|---|---|---|---|---|---|---|---|
| POST /api/auth/login | 6 | 100% | 305ms | 330ms | 420ms | 420ms | 420ms |
| GET /api/contracts（列表） | 123 | 100% | 41ms | 33ms | 57ms | 230ms | 300ms |
| POST /api/chats（SSE） | 118 | 100% | 120ms | 120ms | 140ms | 220ms | 230ms |

## 3. 审阅 SSE 专项（2 用户 / 8 分钟）

| 指标 | 值 |
|---|---|
| 完成审阅次数 | 4（0 失败） |
| 完整审阅时长 | Avg 205s · Min 158s · Max 251s · Med 250s |
| SSE 首包（TTFT） | **37.1s**（流式改造后；改造前 172.9s） |

## 4. 压测暴露并已修复的问题

1. **SSE 非真流式**：原实现 graph 跑完才一次性输出（TTFT≈173s）。已改造为 LangGraph custom stream 模式：每个专家任务完成即推送 SSE，TTFT 降至 **37.1s**（后续可进一步细粒度化到条款级）。
2. **多账号并发 401**：login 将 access_token 单值写入 Redis，多用户共用账号导致 token 互踢。压测脚本改为每用户独立账号。
3. **Locust SSE API 兼容**：`client.stream()` 在 locust 2.46 已移除，改为 `client.request(..., stream=True)`；`iter_lines()` 返回 bytes 需解码。
4. **审阅并发安全**：`start_review` 会清理同 session 旧任务，压测按用户隔离 session，避免互删。

## 5. 说明与局限

- 本环境用 SQLite+fakeredis 替代 MySQL/Redis，读写并发低于生产 Docker（mysql/redis）配置，P99 尾部延迟会略低于真实部署。
- 审阅耗时由 LLM 推理主导（6 专家并行 ReAct），与并发无关；真实部署建议接入缓存与模型蒸馏。
