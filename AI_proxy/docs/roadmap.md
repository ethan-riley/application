# Product Roadmap

## Positioning

This is not an LLM proxy. It is a control plane for LLM traffic:

- API gateway for a stable client surface
- FinOps layer for spend visibility and optimization
- SRE layer for reliability and SLO enforcement
- Policy engine for safety, compliance, and governance

## MVP build sequence

### Phase 1: harden the request path

- OpenAI-compatible request handling
- model registry
- request logging
- basic routing
- latency, cost, token accounting

### Phase 2: make it sellable

- org/team policy inheritance
- timeouts, retries, fallback chains
- quotas and scoped API keys
- admin APIs

### Phase 3: add intelligence

- prompt classification
- dynamic routing weights
- evaluation runner
- A/B routing

### Phase 4: enterprise controls

- persistent observability store
- audit logs
- SSO
- multi-region execution
- compliance integrations

## Current design choices

- FastAPI for a quick OpenAI-compatible edge
- in-memory catalogs for easy iteration
- provider abstraction so OpenAI, Anthropic, Mistral, and local models can be added without changing the public API
- explicit routing and policy objects so future storage can replace current fixtures cleanly

## Recommended next production steps

1. Replace in-memory request logs with ClickHouse.
2. Add Redis-backed quota and circuit-breaker state.
3. Add real provider adapters with streaming support.
4. Add RBAC and tenant-authenticated admin APIs.
5. Add benchmarking workers and scheduled evaluations.
