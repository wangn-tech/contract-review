"""Golden set for RAG evaluation: question + expected answer + relevant doc keys.

规模目标 50 条（当前内置 18 条核心 + 结构可扩展）；每条标注 risk_dim 与
期望召回的文档标题，用于 Recall@K / MRR / NDCG 判定。
"""
from dataclasses import dataclass, field


@dataclass
class EvalCase:
    id: str
    question: str
    expected_answer: str
    relevant_docs: list[str] = field(default_factory=list)  # 相关文档标题关键词
    risk_dim: str = ""


GOLDEN_SET: list[EvalCase] = [
    # ---- 主体资格与合规 ----
    EvalCase(
        id="R01",
        question="中标通知书发出后，采购人应当在多长时间内与供应商签订采购合同？",
        expected_answer="中标通知书发出之日起 30 日内，按照采购文件确定的事项签订采购合同。",
        relevant_docs=["深圳大学采购管理办法实施细则", "民法典合同编"],
        risk_dim="主体资格与合规",
    ),
    EvalCase(
        id="R02",
        question="政府采购合同签订后，学校需要办理什么备案手续？",
        expected_answer="政府采购项目合同报送政府集中采购机构备案；学校集中采购项目合同报送招投标管理中心归档。",
        relevant_docs=["深圳大学采购管理办法实施细则", "自行采购项目合同备案"],
        risk_dim="主体资格与合规",
    ),
    # ---- 财务与付款 ----
    EvalCase(
        id="R03",
        question="采购合同价款应当与什么保持一致？",
        expected_answer="合同价款应与成交金额一致，且应填写签署落款日期。",
        relevant_docs=["自行采购项目合同备案", "集中采购合同签订注意事项"],
        risk_dim="财务与付款",
    ),
    EvalCase(
        id="R04",
        question="采购合同应包含哪些与价款支付有关的必备内容？",
        expected_answer="价款及付款方式（包括付款进度要求）、供应商收款账户名称、账号、开户行名称、履行期限与方式等。",
        relevant_docs=["集中采购合同签订注意事项"],
        risk_dim="财务与付款",
    ),
    # ---- 验收交付与质保 ----
    EvalCase(
        id="R05",
        question="采购合同中应当如何约定验收标准？",
        expected_answer="应明确验收标准及方法，合同验收小组按合同组织项目验收。",
        relevant_docs=["集中采购合同签订注意事项", "科研仪器设备类采购指南"],
        risk_dim="验收交付与质保",
    ),
    EvalCase(
        id="R06",
        question="合同标的条款应包含哪些内容？",
        expected_answer="标的（包括数量、品牌规格型号、质量等要求）。",
        relevant_docs=["集中采购合同签订注意事项"],
        risk_dim="验收交付与质保",
    ),
    # ---- 违约责任 ----
    EvalCase(
        id="R07",
        question="采购合同违约责任条款应包含什么？",
        expected_answer="违约责任（包括违约金或者赔偿金的计算方法等）。",
        relevant_docs=["集中采购合同签订注意事项", "民法典合同编"],
        risk_dim="违约责任与解除",
    ),
    EvalCase(
        id="R08",
        question="中标后拒绝签订采购合同有什么法律后果？",
        expected_answer="中标通知书发出后，采购人或供应商拒绝签订或延期签订采购合同的，应当依法承担法律责任。",
        relevant_docs=["深圳大学采购管理办法实施细则"],
        risk_dim="违约责任与解除",
    ),
    # ---- 知识产权与保密 ----
    EvalCase(
        id="R09",
        question="定制开发的信息化产品合同应当如何处理知识产权归属？",
        expected_answer="采购项目涉及知识产权归属处理的，应当在合同中明确知识产权归属。",
        relevant_docs=["政府采购需求管理办法"],
        risk_dim="知识产权与保密",
    ),
    # ---- 争议解决 ----
    EvalCase(
        id="R10",
        question="采购合同解决争议的方法应在哪里约定？",
        expected_answer="应在合同文本中约定违约责任与解决争议的方法等法定必备条款。",
        relevant_docs=["政府采购需求管理办法", "集中采购合同签订注意事项"],
        risk_dim="争议解决与管辖",
    ),
    EvalCase(
        id="R11",
        question="网上竞价采购合同签订应当依据什么文件？",
        expected_answer="采购人依据中标通知书与供应商签订合同，中标通知书作为合同的附件。",
        relevant_docs=["深圳大学网上竞价采购管理办法实施细则", "深圳大学网上竞价采购管理办法"],
        risk_dim="主体资格与合规",
    ),
    EvalCase(
        id="R12",
        question="补充协议或者解除合同后应在多长时间内办理备案变更？",
        expected_answer="签订补充协议或者解除合同的，应当在签订补充协议或者解除合同之日起十日内办理备案变更手续。",
        relevant_docs=["深圳大学采购管理办法实施细则"],
        risk_dim="争议解决与管辖",
    ),
]
