# 高校合同智能审阅系统（Contract Review Agent）

基于 **LangGraph Multi-Agent + 混合检索 RAG** 的高校合同智能审阅系统：上传合同 → Agent 并行审阅 6 个风险维度 → SSE 实时推送风险点 → 比对 / 问答 / 看板，配套 Docker Compose 一键部署、GitHub Actions CI、Langfuse 可观测与 Locust 压测。

## 架构

```mermaid
flowchart TB
    subgraph FE["展示层 · 前端 (Vue3 + TypeScript)"]
        UI["Nginx :80<br/>静态资源 + /api 反向代理"]
        PAGES["页面：登录 / 看板 / 合同 / 审阅 / 比对 / 问答 / 配置"]
    end

    subgraph BE["应用层 · FastAPI 后端 (:8080)"]
        API["REST API 路由<br/>auth · contracts · sessions · reviews · chats · admin"]
        SSE["SSE 流式<br/>审阅风险点 · 聊天回复"]
        AUTH["JWT 鉴权<br/>PBKDF2 · CAS 预留"]
        DOC["文档解析<br/>pdf/docx → 文本"]
    end

    subgraph AGENT["Agent 编排层 · LangGraph"]
        INTENT["意图识别<br/>LLM + 规则降级"]
        ROUTER["条款分发 Router"]
        S1["专家1 主体合规"]
        S2["专家2 财务付款"]
        S3["专家3 知产保密"]
        S4["专家4 违约解除"]
        S5["专家5 验收质保"]
        S6["专家6 争议管辖"]
        GATE["Gate 质检"]
        ARB["Arbitration 仲裁"]
    end

    subgraph RAG["RAG 检索层"]
        DENSE["Dense<br/>bge-m3 · Qdrant"]
        SPARSE["Sparse<br/>BM25 · jieba"]
        RRF["RRF 融合 k=60"]
        RERANK["Rerank<br/>bge-reranker-v2-m3"]
    end

    subgraph INFRA["基础设施层"]
        MYSQL[(MySQL 8)]
        REDIS[(Redis 7)]
        QD[(Qdrant 向量库)]
        LF["Langfuse 可观测"]
    end

    SILICON["SiliconFlow<br/>DeepSeek · bge 系列"]

    UI -->|"HTTP + SSE"| API
    PAGES --> UI
    API --> AUTH
    API --> DOC
    API --> SSE
    SSE -->|"审阅任务"| INTENT
    INTENT --> ROUTER
    ROUTER --> S1 & S2 & S3 & S4 & S5 & S6
    S1 & S2 & S3 & S4 & S5 & S6 -->|"ReAct 循环调用检索"| RAG
    S1 & S2 & S3 & S4 & S5 & S6 --> GATE
    GATE --> ARB
    ARB -->|"风险点结果"| SSE
    DENSE --> RRF
    SPARSE --> RRF
    RRF --> RERANK
    RERANK -->|"Top-5 证据"| S1 & S2 & S3 & S4 & S5 & S6
    DENSE --> QD
    API --> MYSQL & REDIS
    RERANK -.->|"embedding/rerank API"| SILICON
    AGENT -.->|"LLM 调用"| SILICON
    API -.->|"trace"| LF
```

- **Agent 编排（LangGraph）**：意图识别（LLM + 规则降级）→ 条款分发 → 6 个风险维度专家并行审阅（ReAct + RAG 工具）→ Gate 质检 → 仲裁汇总；提示词模板独立管理。
- **RAG 工程**：bge-m3 稠密（Qdrant）+ BM25 稀疏双路召回 → RRF 融合 → bge-reranker-v2-m3 精排；知识分层（制度/法规/模板），证据可追溯；内置检索指标与 RAGAS 测评。
- **后端工程**：FastAPI + SQLAlchemy 2 + Pydantic v2 + JWT + SSE 流式；统一响应与异常；PBKDF2 密码；CI（ruff + pytest + 前端构建 + 镜像）。
- **可观测与压测**：Langfuse 自托管 trace 关联；Locust 全链路压测（SSE TTFT/完整时长/成功率）。

## 快速开始

> 完整启动/测试指南见 [`docs/QUICKSTART.md`](docs/QUICKSTART.md)。

```bash
# 1. 配置密钥（SiliconFlow key 必填）
cp backend/.env.example .env
# 编辑 .env: SILICONFLOW_API_KEY=sk-xxx

# 2. 一键起全套（mysql/redis/qdrant/langfuse/backend/frontend）
docker compose -f deploy/docker-compose.yml up -d --build

# 3. 构建知识库（深大制度 + 法规 + 模板 → Qdrant + BM25）
docker compose -f deploy/docker-compose.yml exec backend python scripts/ingest_kb.py

# 4. 打开前端 http://localhost（注册账号后上传合同并审阅）
```

## 本地开发

```bash
# 后端（Python 3.12 + uv）
cd backend && uv sync && uv run pytest tests/ -q && uv run ruff check app/ tests/
uv run uvicorn app.main:app --reload --port 8080

# 前端（Node 22）
cd frontend && npm install && npm run dev   # http://localhost:5173，/api 代理到 8080
```

## 目录结构

```
backend/
  app/agent/       LangGraph 状态机、节点（意图/分发/专家/质检/仲裁）、提示词模板
  app/rag/         ingest（chunker/crawler/loader）、retrievers（hybrid/BM25）、rerank、eval
  app/api/         FastAPI 路由（auth/contracts/sessions/reviews/comparisons/chats/admin/dashboard）
  app/services/    审阅编排（SSE）、聊天（SSE）、文档解析
  scripts/         ingest_kb.py（知识库构建）、eval_rag.py（RAG 测评）、bench_locust.py（压测）
frontend/          Vue3 + TS + Vite + Element Plus + Pinia + ECharts
deploy/            docker-compose（六服务）
.github/workflows/ CI（lint → test → 前端构建 → 镜像 → 部署占位）
docs/              设计文档、压测/测评报告模板
```

## 测试与验证

| 层 | 命令 | 覆盖 |
| --- | --- | --- |
| 单测/集成 | `uv run pytest tests/ -q` | 鉴权/会话/合同/审阅 SSE/聊天 SSE/Agent 纯逻辑/RAG 纯函数 |
| Lint | `uv run ruff check app/ tests/ scripts/` | E/F/I/W/UP/B/SIM |
| 前端 | `cd frontend && npm run build` | vue-tsc 类型检查 + Vite 构建 |
| 端到端 | docker compose 一键起 | 六服务健康检查 + 依赖等待 |

## 简历亮点（Agent 项目）

1. **Multi-Agent 编排**：LangGraph 状态机（意图识别 → 分发 → 6 专家并行 → 质检 → 仲裁），提示词模板化 + JSON Schema 约束 + 规则降级兜底，专家并行（信号量限流 20）。
2. **RAG 全链路**：混合检索（dense+sparse → RRF → cross-encoder 重排）、知识分层、证据可追溯、检索指标（Recall@K/MRR/NDCG）+ RAGAS 四指标测评。
3. **工程化**：FastAPI 分层、SSE 流式、统一异常、CI 五阶段、Docker Compose 六服务、Langfuse 可观测、Locust 压测指标。
