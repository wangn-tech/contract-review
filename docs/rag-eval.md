# RAG 测评报告

> 实测环境：云电脑（Qdrant 1.19 + bge-m3 embedding + bge-reranker-v2-m3 + DeepSeek-V4-Flash judge）
> 知识库：9 篇文档（深大采购制度 5 + 法规 2 + 模板 2）共 267 chunks（institution 263 / regulations 2 / templates 2）

## 1. 检索指标（golden set 58 条，top_k=5，RRF k=60）

| 指标 | 值 |
|---|---|
| Recall@5 | **0.3966** |
| Precision@5 | 0.1138 |
| MRR | 0.1773 |
| NDCG@5 | 0.2586 |
| Hit@5 | 0.2586 |

示例命中：
- R01（签订时限）→ 深圳大学采购管理办法实施细则 / 网上竞价实施细则 ✓
- R02（备案手续）→ 采购管理办法实施细则 / 集中采购签订注意事项 ✓
- R05（验收标准）→ 政府采购需求管理办法 / 民法典合同编 ✓

## 2. RAGAS 生成质量（10 条抽样，真实检索上下文，LLM-as-judge）

| 指标 | 值 | 说明 |
|---|---|---|
| Faithfulness | **0.6375** | 答案忠于检索上下文 |
| Answer Relevancy | **0.6853** | 答案与问题相关度 |
| Context Precision（无参考） | **0.7333** | 检索上下文精炼度 |
| Context Recall | 0.4333 | 上下文覆盖参考答案程度 |

## 2.5 依赖冲突与解法（2026-09 实测，最终方案 ragas 0.4.3）

- **ragas（0.2 / 0.4）均无条件 import `langchain_community.chat_models.vertexai`**（官方 main 分支仍未修复），而 langchain-community 0.4.2 已移除该模块 → ModuleNotFoundError。
- **最终方案（官方文档 + 实测）**：eval 环境锁 `ragas>=0.4,<0.5` + `langchain-community<0.4`（0.3.31 保留 vertexai，且与 langchain-core 1.6 / langchain 1.4.2 共存）。
- **ragas 0.4 新 API**（官方推荐，deprecation 提示）：`llm_factory(model, client=OpenAI(base_url, api_key))` 构建 LLM；metric 用顶层已初始化实例并绑定 `m.llm`；AnswerRelevancy 需要 `embed_query`，ragas 0.4.3 新 embeddings（OpenAIEmbeddings）未提供，故用 `LangchainEmbeddingsWrapper(langchain OpenAIEmbeddings)`（官方仍保留该 wrapper）。
- 实测：2 条样本 × 4 指标（8 个 job）全部出值，无异常；`scripts/eval_rag.py` / `app/rag/eval/ragas_eval.py` 已迁移到 0.4 API。
- **主环境（无 --extra eval）不含 langchain-community**：langgraph 1.2 只依赖 langchain-core，项目代码不 import community。

## 3. 测评过程中修复的问题

1. **rerank 字段兼容**：SiliconFlow 返回 `relevance_score` 而非 `score`，`rerank.py` 已兼容两种字段名。
2. **golden set 匹配口径**：相关文档标注按文档标题，chunk 元数据 `doc_id` 才是标题（`source` 为 URL），`eval_rag.py` 改为按 `doc_id` 判定。
3. **RAGAS embedding 接入**：RAGAS 上下文精度需 embedding，已接入 SiliconFlow bge-m3；ragas 0.4.x 与 langchain-community 0.4 存在 import 冲突，评估需独立 venv（ragas 0.2.12 + langchain 0.3.x）。

## 4. 分析与优化方向

- **Recall 偏低（0.40）主因**：知识库仅 9 篇文档、法规/模板层仅 2 条各 2 chunks，覆盖不足；扩充语料（更多深大制度 + 完整法规 + 合同模板库）将显著提升。
- **Context Recall 0.43**：top-3 上下文常缺关键条款，可调高 `RAG_RERANK_TOP_K` 或启用 `rag_query_variants=3` 查询改写扩展召回。
- 建议上线前扩充 golden set 至 100+ 条，并在 CI 中固化测评（workflow_dispatch）。
