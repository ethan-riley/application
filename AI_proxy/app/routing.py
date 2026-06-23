from __future__ import annotations

from app.schemas import ModelRecord, PromptAnalysis, RequestMetadata, RoutingDecision


class IntelligentRouter:
    def choose_model(
        self,
        models: list[ModelRecord],
        analysis: PromptAnalysis,
        metadata: RequestMetadata,
        requested_model: str | None = None,
        fallback_model: str | None = None,
    ) -> RoutingDecision:
        if requested_model:
            scores = {model.model: 0.0 for model in models}
            fallback_chain = self._fallback_chain(models, requested_model, fallback_model)
            return RoutingDecision(
                selected_model=requested_model,
                fallback_chain=fallback_chain,
                reason="explicit model requested by client",
                candidate_scores=scores,
            )

        scores = {model.model: round(self._score_model(model, analysis, metadata), 4) for model in models}
        ranked_models = self._rank_models(models, analysis, metadata)
        selected = ranked_models[0]
        fallback_chain = self._fallback_chain(ranked_models, selected.model, fallback_model)

        return RoutingDecision(
            selected_model=selected.model,
            fallback_chain=fallback_chain,
            reason="lowest estimated cost among models suitable for the task and SLO",
            candidate_scores=scores,
        )

    def _rank_models(
        self,
        models: list[ModelRecord],
        analysis: PromptAnalysis,
        metadata: RequestMetadata,
    ) -> list[ModelRecord]:
        suitable_models = [
            model
            for model in models
            if self._meets_quality_floor(model, analysis) and self._meets_latency_budget(model, metadata)
        ]
        if not suitable_models:
            suitable_models = [model for model in models if self._meets_quality_floor(model, analysis)]
        if not suitable_models:
            suitable_models = models

        return sorted(
            suitable_models,
            key=lambda model: (
                self._estimated_request_cost(model, analysis),
                self._tier_distance(model, analysis),
                model.avg_latency_ms,
                model.error_rate,
                -model.quality_score,
            ),
        )

    def _score_model(self, model: ModelRecord, analysis: PromptAnalysis, metadata: RequestMetadata) -> float:
        estimated_cost = self._estimated_request_cost(model, analysis)
        cost_score = 1 / (1 + estimated_cost * 1000)
        latency_budget = max(metadata.latency_slo_ms or 2000, 1)
        latency_score = max(0.0, 1 - (model.avg_latency_ms / latency_budget))
        quality_score = model.quality_score
        reliability_score = 1 - model.error_rate
        suitability_bonus = 0.2 if self._meets_quality_floor(model, analysis) else 0.0
        suitability_bonus += 0.1 if self._meets_latency_budget(model, metadata) else 0.0
        tier_bonus = 0.05 if model.mode == analysis.recommended_tier else 0.0
        return cost_score + latency_score + quality_score + reliability_score + suitability_bonus + tier_bonus

    def _estimated_request_cost(self, model: ModelRecord, analysis: PromptAnalysis) -> float:
        prompt_tokens = analysis.estimated_prompt_tokens
        completion_tokens = self._estimated_completion_tokens(analysis)
        return (
            prompt_tokens / 1000 * model.cost_per_1k_input_tokens
            + completion_tokens / 1000 * model.cost_per_1k_output_tokens
        )

    def _estimated_completion_tokens(self, analysis: PromptAnalysis) -> int:
        base = {
            "classification": 48,
            "summarization": 220,
            "code_generation": 420,
            "general_chat": 160,
        }.get(analysis.task_type, 160)
        multiplier = {"low": 1.0, "medium": 1.5, "high": 2.2}.get(analysis.complexity, 1.0)
        return int(base * multiplier)

    def _meets_quality_floor(self, model: ModelRecord, analysis: PromptAnalysis) -> bool:
        floor = {
            "classification": {"low": 0.55, "medium": 0.62, "high": 0.7},
            "summarization": {"low": 0.68, "medium": 0.75, "high": 0.82},
            "code_generation": {"low": 0.8, "medium": 0.86, "high": 0.9},
            "general_chat": {"low": 0.65, "medium": 0.72, "high": 0.8},
        }.get(analysis.task_type, {"low": 0.65, "medium": 0.72, "high": 0.8})
        return model.quality_score >= floor.get(analysis.complexity, 0.72)

    def _meets_latency_budget(self, model: ModelRecord, metadata: RequestMetadata) -> bool:
        if not metadata.latency_slo_ms:
            return True
        return model.avg_latency_ms <= int(metadata.latency_slo_ms * 1.15)

    def _tier_distance(self, model: ModelRecord, analysis: PromptAnalysis) -> int:
        order = {"economy": 0, "balanced": 1, "premium": 2}
        return abs(order[model.mode] - order[analysis.recommended_tier])

    def _fallback_chain(
        self,
        models: list[ModelRecord],
        selected_model: str,
        fallback_model: str | None,
    ) -> list[str]:
        ordered = [model.model for model in models if model.model != selected_model]
        if fallback_model and fallback_model != selected_model:
            ordered = [fallback_model] + [model for model in ordered if model != fallback_model]
        return ordered[:3]
