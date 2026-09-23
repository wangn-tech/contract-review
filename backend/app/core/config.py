"""Application configuration driven by environment variables (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # 统一约定：.env 放项目根目录（compose/本地均可用）。
        # 本地开发在 backend/ 下运行时会回退读取上级目录的 .env。
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # runtime
    app_name: str = "contract-review"
    app_env: str = "dev"
    debug: bool = True
    server_host: str = "0.0.0.0"
    server_port: int = 8080

    # mysql
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "contract"
    mysql_password: str = "change-me"
    mysql_db: str = "contract_review"

    # redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # jwt
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # LLM 供应商（OpenAI SDK 接入；换供应商只需改 LLM_BASE_URL / LLM_API_KEY）
    llm_base_url: str = "https://api.siliconflow.cn/v1"
    llm_api_key: str = ""
    # siliconflow（兼容旧变量名，LLM 变量为空时回退）
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    llm_review_model: str = "deepseek-ai/DeepSeek-V3.2"
    llm_chat_model: str = "deepseek-ai/DeepSeek-V4-Flash"
    llm_intent_model: str = "deepseek-ai/DeepSeek-V4-Flash"
    embedding_model: str = "BAAI/bge-m3"
    rerank_model: str = "BAAI/bge-reranker-v2-m3"

    # qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_regulations: str = "kb_regulations"
    qdrant_collection_institution: str = "kb_institution"
    qdrant_collection_templates: str = "kb_templates"

    # rag
    rag_hybrid_top_k: int = 60
    kb_bm25_path: str = ""  # 空则自动推导为 OSS_BUCKET_DIR 上级的 kb_bm25.pkl
    rag_rerank_top_k: int = 5
    rag_query_variants: int = 3
    rag_per_doc_quota: int = 3  # 分层配额：每个文档最多 N 个 chunk 进入 rerank

    # langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"

    # storage
    upload_dir: str = "/data/uploads"
    oss_bucket_dir: str = "/data/parsed"

    # frontend / cas
    frontend_url: str = "http://localhost:5173"
    cas_server_url: str = ""

    # 文档解析引擎（有序回退链）
    doc_parser_engines: str = "pdfplumber,pymupdf,pypdf,docx,libreoffice,ocr"
    ocr_lang: str = "chi_sim"
    deepseek_ocr_api_key: str = ""
    deepseek_ocr_model: str = "deepseek-ocr"

    # 中间件 / 缓存 / 限流
    auth_middleware_enabled: bool = True
    request_log_enabled: bool = True
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 120
    chat_cache_ttl: int = 1800

    # MCP
    mcp_enabled: bool = False
    mcp_server_urls: str = ""

    @property
    def mysql_dsn(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
