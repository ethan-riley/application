from __future__ import annotations

from dataclasses import dataclass

from app.schemas import ModelRecord


@dataclass(frozen=True)
class VirtualModelAlias:
    alias_id: str
    label: str
    providers: tuple[str, ...] = ()
    modes: tuple[str, ...] = ()
    require_tools: bool = False
    owned_by: str = "proxy"


ALIASES: tuple[VirtualModelAlias, ...] = (
    VirtualModelAlias(
        alias_id="proxy:auto",
        label="Smart route across all enabled providers",
    ),
    VirtualModelAlias(
        alias_id="openai:auto",
        label="Smart route across OpenAI-compatible providers",
        providers=("openai", "anthropic", "kimi"),
        owned_by="openai-compatible",
    ),
    VirtualModelAlias(
        alias_id="local:auto",
        label="Smart route across local candidates",
        providers=("ollama",),
        owned_by="local",
    ),
    VirtualModelAlias(
        alias_id="tools:auto",
        label="Smart route across tool-capable candidates",
        require_tools=True,
    ),
)


def get_alias(alias_id: str | None) -> VirtualModelAlias | None:
    if not alias_id:
        return None
    return next((alias for alias in ALIASES if alias.alias_id == alias_id), None)


def list_aliases() -> list[VirtualModelAlias]:
    return list(ALIASES)


def filter_models_for_alias(models: list[ModelRecord], alias: VirtualModelAlias) -> list[ModelRecord]:
    filtered = models
    if alias.providers:
        filtered = [model for model in filtered if model.provider in alias.providers]
    if alias.modes:
        filtered = [model for model in filtered if model.mode in alias.modes]
    if alias.require_tools:
        filtered = [model for model in filtered if model.supports_tools]
    return filtered
