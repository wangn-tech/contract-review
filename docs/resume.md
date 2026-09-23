# 简历项目：AI 智能合同审阅平台

> 秋招简历正文优化版（按用户原稿结构重写），所有指标均来自项目实测。

**AI 智能合同审阅平台**
2026.03 - 2026.06 | 个人学习实践项目

**项目描述**：面向高校及企事业单位的合同审查场景，支持合同解析、风险审阅、合同比对和合同问答。围绕长合同处理和专业规则审查，引入多智能体工作流和 RAG 检索，将法规制度、审阅规则与合同内容结合，输出风险点及修改建议。

**技术栈**：Python · FastAPI · SQLAlchemy · MySQL · Redis · LangChain · LangGraph · Qdrant · Langfuse · Docker · GitHub Actions

**项目亮点**：

1. **多智能体审阅**：使用 LangGraph 编排 Router / Specialist / Gate / Arbitration 审阅流程，Router 拆分并路由审阅任务，多个 Specialist 并行分析不同风险维度，经 Gate 校验和 Arbitration 仲裁合并审阅结果；意图识别失败按规则降级兜底，保证流程可用性。

2. **RAG 法规检索**：使用 Qdrant 存储法规、制度、合同模板等知识数据，构建 bge-m3 Embedding 召回 + BM25 多路检索 + RRF 融合 + Rerank 精排的完整检索链路，跨三层知识库召回相关规则并作为上下文交给模型判断；自建 100 条 golden set + 分层配额与文档级去重终排优化，修复 rerank 索引错位、指标超 1 假口径等链路 bug 后：Recall@5 0.40→0.86、MRR 0.18→0.70、Hit@5 0.71→0.89。

3. **长文档并发审阅**：集成 MinerU、Docling、OCR 等 10 种解析引擎解析 PDF、Word 及扫描件，对解析结果分块并并发执行审阅任务，按原始条款顺序合并风险项和修改建议；全链路 SSE 流式输出，首 Token 延迟由 172.9s 优化至 37.1s（4.7 倍）。

4. **审阅规则配置**：将 Prompt 拆分为系统级、机构级和个性化配置，支持按合同类型和审阅场景组合不同规则；基于 OpenAI SDK 统一接入大模型，LLM 供应商可通过环境变量一键切换，减少新增审阅场景时的代码改动。

5. **工程化与链路追踪**：JWT 认证 + Redis 缓存与分布式锁 + 限流中间件；Docker Compose 一键部署，GitHub Actions CI 全绿；接入 Langfuse 记录 Agent 执行、RAG 检索和模型调用过程，便于定位检索、Prompt 或模型调用问题。

---

## 面试可展开（不写入简历）

- **设计取舍**：为什么 Router 拆分 + Specialist 并行 + Gate/Arbitration，而不是单一 LLM 一次审阅；意图识别降级策略的设计。
- **RAG 细节**：RRF 融合为什么优于分数归一化直接相加；bge-m3（dense）与 BM25（sparse）互补点；三库分层召回解决什么问题；分层配额（每文档限 N chunk 进 rerank）为什么提升文档级召回。
- **排查案例**：rerank 索引错位导致排序退化的定位过程；recall>1 假指标的识别与修复（每相关条目限一次命中），体现评测驱动优化与口径严谨性。
