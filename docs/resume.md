# 简历项目：高校采购合同智能审阅 Agent

> 面向 Agent 应用开发方向的秋招简历素材，按"项目名 / 技术栈 / 项目亮点"组织，所有指标均来自项目实测。

## 项目名

高校采购合同智能审阅 Agent（Multi-Agent + RAG 的合同风险审查系统）

## 技术栈

Python / FastAPI / LangGraph 1.x / OpenAI SDK / Qdrant / Redis / MySQL / Docker / GitHub Actions / RAGAS（前端 Vue3+TS，不作为简历重点）

## 项目亮点

**1. LangGraph Multi-Agent 编排（核心亮点）**
- 构建「意图识别 → 六路专家并行审阅 → 门控 Gate → 仲裁 Arbitration」多 Agent 编排图；意图识别失败时按规则降级兜底，专家节点按风险维度（主体资格/财务付款/知识产权保密/违约责任/验收质保/争议管辖）并行抽取风险点，仲裁合并去重后输出结构化审阅报告
- 全链路 SSE 真流式输出，首 Token 延迟（TTFT）从 172.9s 优化至 37.1s（性能优化 4.7 倍）
- 基于 MCP 2.x 暴露检索/解析工具、注入规则 Skills，Agent 具备工具调用与规则约束能力

**2. RAG 检索与评测工程（核心亮点）**
- 混合检索全链路：bge-m3 稠密向量 + BM25 稀疏召回 → RRF 融合 → bge-reranker-v2-m3 精排；跨法规 / 校内制度 / 合同模板三层知识库分层多路召回，Qdrant 向量库 + 持久化 BM25 索引
- 多引擎文档解析（MinerU / Docling / DeepSeek-OCR / PyMuPDF / pdfplumber / LibreOffice 等 10 种），支持 PDF / DOCX / 扫描件多格式
- 自建 golden set（100 条）与 RAGAS 0.4.3 评测体系，修复 rerank 索引错位、单库过滤等检索链路 bug 后：Recall@5 0.40→0.68、MRR 0.18→0.65、NDCG@5 0.26→0.63、RAGAS ContextRecall 0.43→0.70

**3. 后端工程化**
- FastAPI + JWT 认证（预留 CAS 对接接口）+ Redis 缓存 / 分布式锁 + 全局鉴权 / 限流中间件 + 统一响应结构，Swagger / ReDoc 自动文档
- 基于 OpenAI SDK 统一接入大模型，供应商（SiliconFlow / OpenAI 等）通过环境变量一键切换
- Docker Compose 一键部署 + GitHub Actions CI 全绿（lint / 测试 / 前端构建 / 镜像构建）+ Langfuse 可观测 + Locust 压测（SSE 平均 120ms，6 并发 0 失败）

## 使用建议（秋招版）

- 简历正文 3-4 行即可：取亮点 1 与 2 各压缩为一句，亮点 3 选「FastAPI + JWT + Redis + CI」一句带过，量化数字保留。
- 面试可展开：意图识别与规则降级的设计取舍、RRF 融合为什么优于分数归一化、rerank 索引 bug 的排查过程（体现 debug 与评测驱动优化）。
