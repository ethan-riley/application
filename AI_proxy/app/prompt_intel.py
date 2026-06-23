from __future__ import annotations

from app.schemas import ChatCompletionRequest, PromptAnalysis


class PromptIntelligence:
    def analyze(self, request: ChatCompletionRequest) -> PromptAnalysis:
        text = " ".join(message.content or "" for message in request.messages).lower()
        prompt_tokens = max(1, len(text.split()) * 2)

        if any(term in text for term in ("python", "typescript", "code", "function", "bug")):
            task_type = "code_generation"
        elif any(term in text for term in ("summarize", "summary", "tl;dr")):
            task_type = "summarization"
        elif any(term in text for term in ("classify", "label", "sentiment")):
            task_type = "classification"
        else:
            task_type = "general_chat"

        if request.tools:
            task_type = "code_generation" if task_type == "general_chat" else task_type
            prompt_tokens += 80 * len(request.tools)

        if prompt_tokens > 1_500:
            complexity = "high"
        elif prompt_tokens > 400:
            complexity = "medium"
        else:
            complexity = "low"

        if request.tools:
            recommended_tier = "premium" if complexity == "high" else "balanced"
        elif task_type == "code_generation" or complexity == "high":
            recommended_tier = "premium"
        elif task_type == "classification":
            recommended_tier = "economy"
        else:
            recommended_tier = "balanced"

        return PromptAnalysis(
            task_type=task_type,
            complexity=complexity,
            estimated_prompt_tokens=prompt_tokens,
            recommended_tier=recommended_tier,
        )
