from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatToolFunction(BaseModel):
    name: str
    arguments: str


class ChatToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ChatToolFunction
    index: int | None = None


class ChatToolDefinitionFunction(BaseModel):
    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None


class ChatToolDefinition(BaseModel):
    type: Literal["function"] = "function"
    function: ChatToolDefinitionFunction


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ChatToolCall] = Field(default_factory=list)


class RequestMetadata(BaseModel):
    org_id: str = "techsphere"
    team_id: str = "platform"
    user_id: str = "anonymous"
    service: str = "unknown"
    latency_slo_ms: int | None = None
    max_cost_usd: float | None = None
    preferred_models: list[str] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    temperature: float | None = 0.2
    max_tokens: int | None = 512
    tools: list[ChatToolDefinition] = Field(default_factory=list)
    tool_choice: str | dict[str, Any] | None = None
    parallel_tool_calls: bool | None = None
    stream: bool | None = False
    tags: list[str] = Field(default_factory=list)
    metadata: RequestMetadata = Field(default_factory=RequestMetadata)


class PromptAnalysis(BaseModel):
    task_type: str
    complexity: str
    estimated_prompt_tokens: int
    recommended_tier: str


class PolicyRuleSet(BaseModel):
    max_cost_per_request: float | None = None
    allowed_models: list[str] = Field(default_factory=list)
    blocked_terms: list[str] = Field(default_factory=list)
    fallback_model: str | None = None


class Policy(BaseModel):
    policy_id: str
    scope: Literal["org", "team"]
    scope_id: str
    rules: PolicyRuleSet


class ModelRecord(BaseModel):
    model: str
    provider: str
    mode: Literal["economy", "balanced", "premium"]
    cost_per_1k_input_tokens: float
    cost_per_1k_output_tokens: float
    avg_latency_ms: int
    quality_score: float
    error_rate: float
    supports_tools: bool = False
    supports_streaming: bool = False
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)


class RoutingDecision(BaseModel):
    selected_model: str
    fallback_chain: list[str]
    reason: str
    candidate_scores: dict[str, float]


class ProviderResponse(BaseModel):
    model: str
    content: str | None = None
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    finish_reason: str = "stop"
    tool_calls: list[ChatToolCall] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class RequestLog(BaseModel):
    request_id: str
    org_id: str
    team_id: str
    user_id: str
    service: str
    task_type: str
    prompt_tokens: int
    completion_tokens: int
    model_used: str
    latency_ms: int
    cost_usd: float
    status: Literal["success", "blocked", "error"]
    policy_id: str | None = None
    route_reason: str | None = None
    attempted_models: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: str | None = None


class QuotaDecision(BaseModel):
    allowed: bool
    scope_key: str
    limit_usd: float | None = None
    current_usage_usd: float | None = None
    retry_after_seconds: int | None = None
    reason: str | None = None


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage
    control_plane: dict[str, Any]


class ProviderConfig(BaseModel):
    provider_id: str
    provider_type: str
    enabled: bool = True
    base_url: str | None = None
    api_key: str | None = None
    organization: str | None = None
    project: str | None = None
    timeout_seconds: float | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class ProviderConfigResponse(BaseModel):
    provider_id: str
    provider_type: str
    enabled: bool = True
    base_url: str | None = None
    organization: str | None = None
    project: str | None = None
    timeout_seconds: float | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    api_key_configured: bool = False


class RuntimeConfig(BaseModel):
    providers: list[ProviderConfig] = Field(default_factory=list)
    models: list[ModelRecord] = Field(default_factory=list)
    policies: list[Policy] = Field(default_factory=list)
    api_clients: list["ApiClientRecord"] = Field(default_factory=list)


class ResponsesRequest(BaseModel):
    model: str | None = None
    input: str | list[Any]
    temperature: float | None = 0.2
    max_output_tokens: int | None = 512
    tools: list[ChatToolDefinition] = Field(default_factory=list)
    tool_choice: str | dict[str, Any] | None = None
    parallel_tool_calls: bool | None = None
    metadata: RequestMetadata = Field(default_factory=RequestMetadata)


class ResponsesMessageContent(BaseModel):
    type: str = "output_text"
    text: str
    annotations: list[Any] = Field(default_factory=list)
    logprobs: list[Any] = Field(default_factory=list)


class ResponsesOutputMessage(BaseModel):
    id: str
    type: str = "message"
    status: str = "completed"
    role: str = "assistant"
    content: list[ResponsesMessageContent] = Field(default_factory=list)


class ResponsesFunctionCallOutput(BaseModel):
    id: str
    type: str = "function_call"
    call_id: str
    name: str
    arguments: str
    status: str = "completed"


class ResponsesResponse(BaseModel):
    id: str
    object: str = "response"
    status: str = "completed"
    model: str
    output: list[dict[str, Any]]
    usage: dict[str, int]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApiClientRecord(BaseModel):
    key_id: str
    name: str
    enabled: bool = True
    key_prefix: str
    key_hash: str
    created_at: str
    last_used_at: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class ApiClientResponse(BaseModel):
    key_id: str
    name: str
    enabled: bool = True
    key_prefix: str
    created_at: str
    last_used_at: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class ApiClientCreateRequest(BaseModel):
    name: str
    labels: dict[str, str] = Field(default_factory=dict)


class ApiClientCreateResponse(BaseModel):
    key_id: str
    name: str
    api_key: str
    key_prefix: str
    created_at: str
    labels: dict[str, str] = Field(default_factory=dict)


class ApiClientUpdateRequest(BaseModel):
    enabled: bool = True
    labels: dict[str, str] = Field(default_factory=dict)


class ModelBulkToggleRequest(BaseModel):
    models: list[str] = Field(default_factory=list)
    enabled: bool = True


RuntimeConfig.model_rebuild()


class EmbeddingsRequest(BaseModel):
    model: str
    input: Any
    user: str | None = None
    encoding_format: str | None = None
    dimensions: int | None = None
    metadata: RequestMetadata = Field(default_factory=RequestMetadata)


class RerankRequest(BaseModel):
    model: str
    query: str
    documents: list[str]
    top_n: int | None = None
    return_documents: bool | None = None
    metadata: RequestMetadata = Field(default_factory=RequestMetadata)


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=8, ge=1, le=100)
    recency: Literal["day", "week", "month", "year"] | None = None
    search_depth: Literal["basic", "deep"] = "basic"
    max_content_chars: int = Field(default=2000, ge=1)


class SearchSource(BaseModel):
    title: str
    url: str
    snippet: str | None = None


class SearchResponse(BaseModel):
    sources: list[SearchSource]


class AnthropicMessagesPassthroughRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    messages: list[Any]
    max_tokens: int


class ModelMetadata(BaseModel):
    id: str
    provider: str
    mode: Literal["economy", "balanced", "premium"]
    cost_per_1k_input_tokens: float
    cost_per_1k_output_tokens: float
    avg_latency_ms: int
    quality_score: float
    supports_tools: bool
    supports_streaming: bool
    enabled: bool
    tags: list[str]
    include_in_cli: bool = False


class FileObject(BaseModel):
    id: str
    object: str = "file"
    bytes: int
    created_at: int
    filename: str
    purpose: str


class BatchRequestCounts(BaseModel):
    total: int = 0
    completed: int = 0
    failed: int = 0


class BatchObject(BaseModel):
    id: str
    object: str = "batch"
    endpoint: str
    errors: dict[str, Any] | None = None
    input_file_id: str
    completion_window: str = "24h"
    status: str = "validating"
    output_file_id: str | None = None
    error_file_id: str | None = None
    created_at: int
    in_progress_at: int | None = None
    expires_at: int | None = None
    finalizing_at: int | None = None
    completed_at: int | None = None
    failed_at: int | None = None
    expired_at: int | None = None
    cancelling_at: int | None = None
    cancelled_at: int | None = None
    request_counts: BatchRequestCounts = Field(default_factory=BatchRequestCounts)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BatchCreateRequest(BaseModel):
    input_file_id: str
    endpoint: str
    completion_window: str = "24h"
    metadata: dict[str, Any] = Field(default_factory=dict)
