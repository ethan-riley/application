from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Header, HTTPException, status

from app.runtime_config import RuntimeConfigStore
from app.schemas import (
    ApiClientCreateRequest,
    ApiClientCreateResponse,
    ApiClientRecord,
    ApiClientUpdateRequest,
)


def create_api_client(store: RuntimeConfigStore, request: ApiClientCreateRequest) -> ApiClientCreateResponse:
    secret = secrets.token_urlsafe(24)
    key_id = uuid4().hex[:12]
    api_key = f"tsp_live_{key_id}_{secret}"
    created_at = _utc_now()
    record = ApiClientRecord(
        key_id=key_id,
        name=request.name,
        enabled=True,
        key_prefix=api_key[:18],
        key_hash=_hash_key(api_key),
        created_at=created_at,
        labels=request.labels,
    )
    store.upsert_api_client(record)
    return ApiClientCreateResponse(
        key_id=record.key_id,
        name=record.name,
        api_key=api_key,
        key_prefix=record.key_prefix,
        created_at=record.created_at,
        labels=record.labels,
    )


def update_api_client(store: RuntimeConfigStore, key_id: str, request: ApiClientUpdateRequest) -> ApiClientRecord:
    current = store.get_api_client(key_id)
    if not current:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API client not found")
    updated = current.model_copy(update={"enabled": request.enabled, "labels": request.labels})
    return store.upsert_api_client(updated)


def authenticate_proxy_key(
    store: RuntimeConfigStore,
    authorization: str | None,
) -> ApiClientRecord:
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    hashed = _hash_key(token)
    for client in store.list_api_clients():
        if client.enabled and secrets.compare_digest(client.key_hash, hashed):
            used_at = _utc_now()
            if client.last_used_at != used_at:
                store.upsert_api_client(client.model_copy(update={"last_used_at": used_at}))
            return client

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_proxy_api_key(runtime_config: RuntimeConfigStore, authorization: str | None = Header(default=None)) -> ApiClientRecord:
    return authenticate_proxy_key(runtime_config, authorization)


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
