"""RAG Core service configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class RagCoreSettings(BaseSettings):
    # Database
    database_url: str = "postgresql://aicp_user:aicp_pass@localhost:5432/aicp_db"
    database_pool_size: int = 10

    # OpenSearch
    opensearch_url: str = "http://localhost:9200"
    opensearch_index_prefix: str = "aicp"
    opensearch_username: str = "admin"
    opensearch_password: str = "admin"

    # Embeddings
    embedding_provider: str = "local_bge"
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 32

    # Vertex AI
    vertex_ai_project: str = ""
    vertex_ai_location: str = "us-central1"
    vertex_ai_embedding_model: str = "text-embedding-004"

    # GCS
    gcs_bucket_artifacts: str = ""

    # Redis cache
    redis_url: str = "redis://localhost:6379/1"

    # OTel
    otel_endpoint: str = ""
    otel_service_name: str = "aicp-rag-core"

    # Retrieval
    retrieval_top_k: int = 10
    rrf_k: int = 60
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = RagCoreSettings()
