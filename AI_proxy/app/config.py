from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "llm-control-plane"
    environment: str = "development"
    default_org_id: str = "techsphere"
    default_timeout_ms: int = 2_000
    default_fallback_model: str = "gpt-4o-mini"
    runtime_config_path: str = "data/runtime_config.json"
    runtime_config_backend: str = "auto"

    openai_enabled: bool = True
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_organization: str | None = None
    openai_project: str | None = None
    openai_timeout_seconds: float = 30.0

    anthropic_enabled: bool = True
    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    anthropic_timeout_seconds: float = 30.0
    anthropic_version: str = "2023-06-01"

    kimi_enabled: bool = True
    kimi_api_key: str | None = None
    kimi_base_url: str = "https://api.moonshot.ai/v1"
    kimi_timeout_seconds: float = 30.0

    ollama_enabled: bool = True
    ollama_base_url: str = "http://ollama-external.default.svc.cluster.local:11434"
    ollama_timeout_seconds: float = 60.0

    doppler_enabled: bool = True
    doppler_project: str = "coding"
    doppler_config: str | None = None
    doppler_openai_secret_name: str = "OPENAI_API_KEY_AI_PROJECTS"
    doppler_anthropic_secret_name: str = "ANTHROPIC_API_KEY_AI_PROJECTS"
    doppler_kimi_secret_name: str = "MOONSHOT_API_KEY"

    cohere_enabled: bool = True
    cohere_api_key: str | None = None
    cohere_base_url: str = "https://api.cohere.ai"
    cohere_timeout_seconds: float = 30.0

    groq_enabled: bool = True
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: float = 30.0

    mistral_enabled: bool = True
    mistral_api_key: str | None = None
    mistral_base_url: str = "https://api.mistral.ai/v1"
    mistral_timeout_seconds: float = 30.0

    gemini_enabled: bool = True
    gemini_api_key: str | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_timeout_seconds: float = 30.0

    azure_openai_enabled: bool = True
    azure_openai_api_key: str | None = None
    azure_openai_base_url: str | None = None
    azure_openai_api_version: str = "2024-02-01"
    azure_openai_timeout_seconds: float = 30.0

    doppler_groq_secret_name: str = "GROQ_API_KEY"
    doppler_mistral_secret_name: str = "MISTRAL_API_KEY"
    doppler_gemini_secret_name: str = "GEMINI_API_KEY"
    doppler_azure_openai_secret_name: str = "AZURE_OPENAI_API_KEY"

    search_provider: str = "tavily"
    search_tavily_api_key: str | None = None
    search_tavily_endpoint: str = "https://api.tavily.com/search"
    search_exa_api_key: str | None = None
    search_exa_endpoint: str = "https://api.exa.ai/search"
    search_timeout_seconds: float = 30.0

    allow_mock_fallback: bool = True

    clickhouse_enabled: bool = False
    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 8123
    clickhouse_username: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "aiproject"
    clickhouse_secure: bool = False
    clickhouse_request_log_table: str = "llm_request_logs"
    clickhouse_runtime_config_table: str = "llm_runtime_config"
    clickhouse_runtime_config_key: str = "default"

    redis_enabled: bool = False
    redis_url: str = "redis://redis.default.svc.cluster.local:6379/0"
    redis_quota_prefix: str = "llmcp:quota"
    redis_circuit_prefix: str = "llmcp:circuit"
    redis_circuit_failure_threshold: int = 3
    redis_circuit_open_seconds: int = 60
    default_team_daily_cost_limit_usd: float | None = None

    model_config = SettingsConfigDict(env_prefix="LLM_CP_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
