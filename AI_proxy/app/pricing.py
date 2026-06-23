from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    input_per_1k: float
    output_per_1k: float


def pricing_for_model(provider_id: str, model_name: str) -> ModelPricing | None:
    lowered = model_name.lower()
    if provider_id == "openai":
        return _openai_pricing(lowered)
    if provider_id == "anthropic":
        return _anthropic_pricing(lowered)
    if provider_id == "kimi":
        return _kimi_pricing(lowered)
    return None


def _openai_pricing(model_name: str) -> ModelPricing | None:
    rules: list[tuple[str, ModelPricing]] = [
        ("gpt-4.1-nano", ModelPricing(0.0001, 0.0004)),
        ("gpt-4.1-mini", ModelPricing(0.0004, 0.0016)),
        ("gpt-4.1", ModelPricing(0.002, 0.008)),
        ("gpt-4o-mini", ModelPricing(0.00015, 0.0006)),
        ("gpt-4o", ModelPricing(0.0025, 0.01)),
        ("gpt-3.5-turbo", ModelPricing(0.0005, 0.0015)),
        ("gpt-4-0613", ModelPricing(0.03, 0.06)),
        ("gpt-4-", ModelPricing(0.03, 0.06)),
    ]
    for prefix, pricing in rules:
        if model_name.startswith(prefix):
            return pricing
    return None


def _anthropic_pricing(model_name: str) -> ModelPricing | None:
    if "opus" in model_name:
        return ModelPricing(0.0075, 0.0375)
    if "sonnet" in model_name:
        return ModelPricing(0.0015, 0.0075)
    if "haiku-3.5" in model_name or "haiku-35" in model_name or "claude-3-5-haiku" in model_name:
        return ModelPricing(0.0004, 0.002)
    if "haiku" in model_name:
        return ModelPricing(0.000125, 0.000625)
    return None


def _kimi_pricing(model_name: str) -> ModelPricing | None:
    if model_name.startswith("kimi-k2.5"):
        return ModelPricing(0.0006, 0.003)
    if model_name.startswith("kimi-k2-thinking"):
        return ModelPricing(0.0006, 0.0025)
    if model_name.startswith("kimi-k2"):
        return ModelPricing(0.0006, 0.0025)
    return None
