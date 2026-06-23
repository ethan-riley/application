# AI Proxy

OpenAI-compatible LLM routing proxy with a built-in admin WebUI, multi-provider execution, policy enforcement, request logging, and cost-aware model selection.

## What This Project Does

This service exposes an OpenAI-shaped public API while deciding the actual backend provider and model behind the scenes.

Current public namespace:

- `POST /openai/v1/chat/completions`
- `POST /openai/v1/responses`
- `GET /openai/v1/models`

Current admin/UI surface:

- `GET /ui`
- `GET /v1/admin/providers`
- `GET /v1/admin/models`
- `GET /v1/admin/policies`
- `GET /v1/admin/api-keys`
- `GET /v1/admin/requests`

## Current Providers

Implemented provider integrations:

- `openai`
- `anthropic`
- `kimi`
- `ollama`

Provider routing is internal. Clients still talk to the proxy using OpenAI-compatible endpoints.

Virtual aliases:

- `proxy:auto`
- `openai:auto`
- `local:auto`
- `tools:auto`

## Key Features

- OpenAI-compatible request and response shapes
- Tool-calling support on chat and responses endpoints
- Cost-aware routing with fallbacks
- Policy enforcement for tenant scope and allowed models
- Reliability layer with timeout and fallback execution
- Provider catalog sync for SaaS backends
- Persistent runtime config using ClickHouse
- Proxy-issued API keys for client access
- Admin WebUI with:
  - overview
  - external providers
  - model management
  - policies
  - API keys
  - playground
  - analytics

## Repository Structure

Core application:

- [app/main.py](/home/felipe/pegas/techsphere/AI_proxy/app/main.py)
- [app/control_plane.py](/home/felipe/pegas/techsphere/AI_proxy/app/control_plane.py)
- [app/routing.py](/home/felipe/pegas/techsphere/AI_proxy/app/routing.py)
- [app/reliability.py](/home/felipe/pegas/techsphere/AI_proxy/app/reliability.py)
- [app/policy_engine.py](/home/felipe/pegas/techsphere/AI_proxy/app/policy_engine.py)
- [app/runtime_config.py](/home/felipe/pegas/techsphere/AI_proxy/app/runtime_config.py)
- [app/webui.py](/home/felipe/pegas/techsphere/AI_proxy/app/webui.py)

Providers:

- [app/providers/openai.py](/home/felipe/pegas/techsphere/AI_proxy/app/providers/openai.py)
- [app/providers/anthropic.py](/home/felipe/pegas/techsphere/AI_proxy/app/providers/anthropic.py)
- [app/providers/ollama.py](/home/felipe/pegas/techsphere/AI_proxy/app/providers/ollama.py)
- [app/providers/router.py](/home/felipe/pegas/techsphere/AI_proxy/app/providers/router.py)

Persistence:

- [app/storage/clickhouse.py](/home/felipe/pegas/techsphere/AI_proxy/app/storage/clickhouse.py)
- [app/storage/clickhouse_runtime_config.py](/home/felipe/pegas/techsphere/AI_proxy/app/storage/clickhouse_runtime_config.py)
- [app/storage/redis_store.py](/home/felipe/pegas/techsphere/AI_proxy/app/storage/redis_store.py)

Deployment:

- [Dockerfile](/home/felipe/pegas/techsphere/AI_proxy/Dockerfile)
- [k8s/llm-control-plane-deployment.yaml](/home/felipe/pegas/techsphere/AI_proxy/k8s/llm-control-plane-deployment.yaml)
- [k8s/llm-control-plane-ingress.yaml](/home/felipe/pegas/techsphere/AI_proxy/k8s/llm-control-plane-ingress.yaml)
- [k8s/llm-control-plane-secret.yaml](/home/felipe/pegas/techsphere/AI_proxy/k8s/llm-control-plane-secret.yaml)

## Runtime Configuration

The proxy stores persistent runtime configuration in ClickHouse when enabled.

Config domains:

- providers
- models
- policies
- proxy API clients

Fallback backend:

- local JSON file at [data/runtime_config.json](/home/felipe/pegas/techsphere/AI_proxy/data/runtime_config.json)

## Secrets

The app resolves provider secrets from:

1. explicit provider config values
2. environment variables
3. Doppler

Default Doppler project:

- `coding`

Expected Doppler secrets:

- `OPENAI_API_KEY_AI_PROJECTS`
- `ANTHROPIC_API_KEY_AI_PROJECTS`
- `MOONSHOT_API_KEY`

Secret resolution code:

- [app/secrets.py](/home/felipe/pegas/techsphere/AI_proxy/app/secrets.py)

## Local Development

Install:

```bash
pip install -e '.[dev,storage]'
```

Run:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run tests:

```bash
pytest -q
```

## Kubernetes Deployment

The current deployment model used in this repo is:

1. build a local image tag
2. save to tar
3. import into k3s containerd
4. apply manifests
5. restart rollout

Typical flow:

```bash
docker build -t llm-control-plane:fix20 .
docker save llm-control-plane:fix20 -o llm-control-plane_fix20.tar
sudo k3s ctr images import /home/felipe/pegas/techsphere/AI_proxy/llm-control-plane_fix20.tar
kubectl apply -f k8s/llm-control-plane-deployment.yaml
kubectl rollout restart deployment/llm-control-plane -n default
kubectl rollout status deployment/llm-control-plane -n default
```

## Live Environment Notes

Known live hostname:

- `ai.tech-sphere.pro`

Public API style:

- clients should use `/openai/v1/...`

The `/ui` surface and all `/v1/admin/*` endpoints are currently unauthenticated. Deploy behind a trusted ingress (intranet, VPN, or network policy). The only auth layer that remains is the proxy API key check on the `/openai/v1/*` namespace.

## Known Operational Notes

- imported model catalogs often start with `0.0` cost placeholders until pricing metadata is enriched
- proxy API keys are only shown once at creation time
- the playground can reuse a manually pasted token or a token created in the UI and remembered in browser storage
- Kimi uses the OpenAI-compatible `/v1/models` and `/chat/completions` surface, but must not receive OpenAI-specific org/project headers

## Status

As of the current repo state:

- the WebUI follows the Tech Sphere design system (light/teal, Inter, Tailwind CDN)
- the playground executes real chats
- the decision process panel uses real routing output from the last playground run
- Kimi catalog sync is working
- runtime config is persisted

