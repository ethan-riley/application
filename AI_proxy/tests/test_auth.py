from app.auth import authenticate_proxy_key, create_api_client
from app.config import Settings
from app.runtime_config import RuntimeConfigStore
from app.schemas import ApiClientCreateRequest
import json


def test_create_api_client_returns_token_and_persists_hash(tmp_path):
    store = RuntimeConfigStore(Settings(runtime_config_path=str(tmp_path / "runtime.json")))
    created = create_api_client(store, ApiClientCreateRequest(name="sdk-client"))
    assert created.api_key.startswith("tsp_live_")
    clients = store.list_api_clients()
    assert len(clients) == 1
    assert clients[0].key_hash
    assert clients[0].key_hash != created.api_key


def test_authenticate_proxy_key_accepts_valid_bearer(tmp_path):
    store = RuntimeConfigStore(Settings(runtime_config_path=str(tmp_path / "runtime.json")))
    created = create_api_client(store, ApiClientCreateRequest(name="sdk-client"))
    client = authenticate_proxy_key(store, f"Bearer {created.api_key}")
    assert client.name == "sdk-client"


def test_runtime_store_backfills_missing_default_providers(tmp_path):
    runtime_path = tmp_path / "runtime.json"
    runtime_path.write_text(json.dumps({"providers": [], "models": [], "policies": [], "api_clients": []}))
    store = RuntimeConfigStore(Settings(runtime_config_path=str(runtime_path)))
    providers = {provider.provider_id for provider in store.list_providers()}
    assert {"openai", "anthropic", "ollama", "kimi"}.issubset(providers)
