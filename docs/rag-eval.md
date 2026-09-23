# RAG 测评报告（模板）

> 本文档为 RAG 测评执行模板，M6 在 Docker 环境（Qdrant 就绪 + 知识库构建后）回填真实数据。

## 方法

- **检索指标**：golden set（目标 50 条，当前 18 条）→ Recall@K / Precision@K / MRR / NDCG@K / Hit@K；
- **生成质量（RAGAS）**：Faithfulness / Answer Relevancy / Context Precision / Context Recall（LLM-as-judge，DeepSeek 作裁判模型）。

## 知识库

| 层 | 内容 | 来源 |
| --- | --- | --- |
| kb_institution | 深圳大学采购/合同管理制度 | 官网公开页面（可追溯） |
| kb_regulations | 民法典合同编、政府采购需求管理办法 | 公开法规原文 |
| kb_templates | 样例合同条款模板 | 自建演示语料 |

## 检索指标结果

| K | Recall@K | Precision@K | MRR | NDCG@K | Hit@K |
| --- | --- | --- | --- | --- | --- |
| 5 | | | | | |

## RAGAS 结果

| 指标 | 得分 | 说明 |
| --- | --- | --- |
| Faithfulness | | 生成内容忠于检索证据 |
| Answer Relevancy | | 回答与问题相关度 |
| Context Precision | | 检索上下文精确度 |
| Context Recall | | 检索上下文覆盖率 |

## 基线对比（可扩展）

- dense-only vs hybrid（dense+BM25+RRF）vs hybrid+rerank：验证多路召回+重排的收益。

## 失败案例分析

- 待回填（例如：法律术语改写导致召回失败 → 增加同义词查询改写）。
