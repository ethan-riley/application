from __future__ import annotations

import os
import subprocess
from functools import lru_cache

from app.config import Settings


def resolve_provider_api_key(provider_type: str, explicit_value: str | None, settings: Settings) -> str | None:
    if explicit_value:
        return explicit_value

    setting_value = {
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "kimi": settings.kimi_api_key,
        "groq": settings.groq_api_key,
        "mistral": settings.mistral_api_key,
        "gemini": settings.gemini_api_key,
        "azure_openai": settings.azure_openai_api_key,
    }.get(provider_type)
    if setting_value:
        return setting_value

    secret_name = {
        "openai": settings.doppler_openai_secret_name,
        "anthropic": settings.doppler_anthropic_secret_name,
        "kimi": settings.doppler_kimi_secret_name,
        "groq": settings.doppler_groq_secret_name,
        "mistral": settings.doppler_mistral_secret_name,
        "gemini": settings.doppler_gemini_secret_name,
        "azure_openai": settings.doppler_azure_openai_secret_name,
    }.get(provider_type)
    if not secret_name:
        return None

    return resolve_secret(secret_name, settings)


def resolve_secret(name: str, settings: Settings) -> str | None:
    env_value = os.getenv(name)
    if env_value:
        return env_value

    if not settings.doppler_enabled:
        return None

    return _get_doppler_secret(name, settings.doppler_project, settings.doppler_config)


@lru_cache(maxsize=64)
def _get_doppler_secret(name: str, project: str, config: str | None) -> str | None:
    command = ["doppler", "secrets", "get", name, "--project", project, "--plain"]
    if config:
        command.extend(["--config", config])

    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None

    value = completed.stdout.strip()
    return value or None
