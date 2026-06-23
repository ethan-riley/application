// Mock data for LLM Gate dashboard
window.LLMGateData = (() => {
  // Deterministic pseudo-random for sparklines
  function seeded(seed) {
    let s = seed;
    return () => {
      s = (s * 9301 + 49297) % 233280;
      return s / 233280;
    };
  }

  function spark(seed, n = 24, base = 50, vol = 30) {
    const r = seeded(seed);
    const out = [];
    let v = base;
    for (let i = 0; i < n; i++) {
      v += (r() - 0.5) * vol;
      v = Math.max(5, Math.min(100, v));
      out.push(v);
    }
    return out;
  }

  const providers = [
    {
      id: 'anthropic',
      name: 'anthropic',
      kind: 'external',
      logo: 'A',
      accent: '#c48a5a',
      status: 'healthy',
      enabled: true,
      key: 'set',
      keyMasked: 'sk-ant-•••••••••••••3kH2',
      models: 4,
      modelList: ['claude-sonnet-4-5', 'claude-opus-4-1', 'claude-haiku-4-5', 'claude-3-5-sonnet'],
      rpm: 184,
      tpm: '142k',
      p50: 412,
      p99: 1820,
      err: 0.12,
      cost24h: 42.18,
      req24h: 12840,
      spark: spark(11, 24, 60, 25),
      region: 'us-east-1',
      added: '2026-02-14'
    },
    {
      id: 'openai',
      name: 'openai',
      kind: 'external',
      logo: 'O',
      accent: '#10a37f',
      status: 'healthy',
      enabled: true,
      key: 'set',
      keyMasked: 'sk-proj-•••••••••••pQ4n',
      models: 6,
      modelList: ['gpt-4.1', 'gpt-4o', 'gpt-4o-mini', 'o1', 'o1-mini', 'text-embedding-3-large'],
      rpm: 92,
      tpm: '68k',
      p50: 384,
      p99: 2140,
      err: 0.31,
      cost24h: 28.44,
      req24h: 6210,
      spark: spark(22, 24, 40, 20),
      region: 'us-west-2',
      added: '2026-02-10'
    },
    {
      id: 'google',
      name: 'google',
      kind: 'external',
      logo: 'G',
      accent: '#4285f4',
      status: 'degraded',
      enabled: true,
      key: 'set',
      keyMasked: 'AIz•••••••••••••9Qw',
      models: 5,
      modelList: ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.0-pro', 'gemini-2.0-flash', 'text-embedding-005'],
      rpm: 48,
      tpm: '34k',
      p50: 612,
      p99: 4200,
      err: 2.4,
      cost24h: 8.12,
      req24h: 3110,
      spark: spark(33, 24, 30, 18),
      region: 'us-central1',
      added: '2026-03-02'
    },
    {
      id: 'ollama',
      name: 'ollama',
      kind: 'self-hosted',
      logo: 'ol',
      accent: '#6b7280',
      status: 'healthy',
      enabled: true,
      key: 'local',
      keyMasked: '—',
      models: 7,
      modelList: ['qwen3.5:4b', 'qwen3.5:latest', 'deepseek-r1:1.5b', 'llama3.3:70b', 'mistral:7b', 'phi4:14b', 'nomic-embed:latest'],
      rpm: 24,
      tpm: '18k',
      p50: 208,
      p99: 940,
      err: 0.0,
      cost24h: 0.00,
      req24h: 1602,
      spark: spark(44, 24, 25, 12),
      region: 'k8s/prod',
      added: '2026-01-28'
    },
    {
      id: 'groq',
      name: 'groq',
      kind: 'external',
      logo: 'gq',
      accent: '#f97316',
      status: 'healthy',
      enabled: true,
      key: 'set',
      keyMasked: 'gsk_•••••••••••ttv8',
      models: 4,
      modelList: ['llama-3.3-70b', 'llama-3.1-8b-instant', 'mixtral-8x7b', 'whisper-large-v3'],
      rpm: 62,
      tpm: '92k',
      p50: 144,
      p99: 510,
      err: 0.08,
      cost24h: 4.22,
      req24h: 4240,
      spark: spark(55, 24, 45, 22),
      region: 'us-east',
      added: '2026-03-14'
    },
    {
      id: 'mistral',
      name: 'mistral',
      kind: 'external',
      logo: 'm',
      accent: '#ff7000',
      status: 'healthy',
      enabled: false,
      key: 'set',
      keyMasked: 'Nk•••••••••••xRt',
      models: 3,
      modelList: ['mistral-large-2', 'codestral', 'mistral-embed'],
      rpm: 0,
      tpm: '0',
      p50: 0,
      p99: 0,
      err: 0,
      cost24h: 0,
      req24h: 0,
      spark: spark(66, 24, 5, 3),
      region: 'eu-west-1',
      added: '2026-03-21'
    },
    {
      id: 'kimi',
      name: 'kimi',
      kind: 'external',
      logo: 'K',
      accent: '#a855f7',
      status: 'unconfigured',
      enabled: false,
      key: 'missing',
      keyMasked: '—',
      models: 0,
      modelList: [],
      rpm: 0,
      tpm: '0',
      p50: 0,
      p99: 0,
      err: 0,
      cost24h: 0,
      req24h: 0,
      spark: [],
      region: '—',
      added: '2026-04-02'
    },
    {
      id: 'vllm',
      name: 'vllm-prod',
      kind: 'self-hosted',
      logo: 'vL',
      accent: '#14b8a6',
      status: 'healthy',
      enabled: true,
      key: 'local',
      keyMasked: '—',
      models: 2,
      modelList: ['llama-3.3-70b-instruct', 'qwen2.5-coder-32b'],
      rpm: 38,
      tpm: '58k',
      p50: 166,
      p99: 620,
      err: 0.02,
      cost24h: 0,
      req24h: 2480,
      spark: spark(77, 24, 35, 16),
      region: 'k8s/prod',
      added: '2026-02-05'
    },
  ];

  // Traffic time series (last 60 minutes)
  function trafficSeries() {
    const r = seeded(101);
    const pts = [];
    for (let i = 0; i < 60; i++) {
      const base = 200 + Math.sin(i / 9) * 60 + Math.cos(i / 4) * 30;
      pts.push({
        t: i,
        external: Math.max(40, base + (r() - 0.5) * 80),
        selfhosted: Math.max(20, 80 + Math.sin(i / 11) * 40 + (r() - 0.5) * 40),
        cached: Math.max(10, 50 + Math.cos(i / 7) * 25 + (r() - 0.5) * 20),
      });
    }
    return pts;
  }

  const policies = [
    { id: 'cost-ceiling', icon: 'shield', title: 'Cost ceiling — production', rule: 'limit $/request > 0.02 → route to groq/llama-3.1-8b', active: true, hits: 142 },
    { id: 'prompt-length', icon: 'ruler', title: 'Long context spillover', rule: 'when tokens > 128k → gemini-2.5-pro, else claude-sonnet-4-5', active: true, hits: 38 },
    { id: 'pii', icon: 'lock', title: 'PII redaction', rule: 'if detect(pii) → mask + force self-hosted', active: true, hits: 22 },
    { id: 'fallback', icon: 'refresh', title: 'Failover chain', rule: 'openai → anthropic → groq (on 5xx or p99 > 5s)', active: true, hits: 6 },
    { id: 'region', icon: 'globe', title: 'EU residency', rule: 'if request.region = "eu" → mistral, vllm-eu', active: false, hits: 0 },
  ];

  const activity = [
    { t: '14:02:11', kind: 'route', prov: 'anthropic', msg: 'POST /v1/chat → <code>claude-sonnet-4-5</code>', status: '200', code: 200 },
    { t: '14:02:09', kind: 'route', prov: 'ollama', msg: 'POST /v1/chat → <code>qwen3.5:4b</code> (policy: PII)', status: '200', code: 200 },
    { t: '14:02:07', kind: 'route', prov: 'groq', msg: 'POST /v1/chat → <code>llama-3.1-8b-instant</code>', status: '200', code: 200 },
    { t: '14:02:04', kind: 'fail', prov: 'google', msg: 'Timeout on <code>gemini-2.5-pro</code>, failing over', status: '504', code: 504 },
    { t: '14:02:04', kind: 'route', prov: 'anthropic', msg: 'Retry → <code>claude-sonnet-4-5</code>', status: '200', code: 200 },
    { t: '14:02:01', kind: 'route', prov: 'openai', msg: 'POST /v1/embeddings → <code>text-embedding-3-large</code>', status: '200', code: 200 },
    { t: '14:01:58', kind: 'route', prov: 'vllm', msg: 'POST /v1/chat → <code>qwen2.5-coder-32b</code>', status: '200', code: 200 },
    { t: '14:01:55', kind: 'policy', prov: 'groq', msg: 'Cost ceiling triggered · <code>llama-3.1-8b-instant</code>', status: '200', code: 200 },
    { t: '14:01:52', kind: 'route', prov: 'anthropic', msg: 'POST /v1/messages · streaming', status: '200', code: 200 },
    { t: '14:01:48', kind: 'auth', prov: 'kimi', msg: 'Auth failed · <code>api key missing</code>', status: '401', code: 401 },
    { t: '14:01:45', kind: 'route', prov: 'ollama', msg: 'POST /v1/chat → <code>llama3.3:70b</code>', status: '200', code: 200 },
    { t: '14:01:41', kind: 'route', prov: 'groq', msg: 'POST /v1/chat → <code>mixtral-8x7b</code>', status: '200', code: 200 },
  ];

  const catalog = [
    { id: 'anthropic', name: 'Anthropic', logo: 'A', auth: 'API key' },
    { id: 'openai', name: 'OpenAI', logo: 'O', auth: 'API key' },
    { id: 'google', name: 'Google AI', logo: 'G', auth: 'API key' },
    { id: 'azure', name: 'Azure OpenAI', logo: 'Az', auth: 'API key + endpoint' },
    { id: 'bedrock', name: 'AWS Bedrock', logo: 'Be', auth: 'IAM' },
    { id: 'groq', name: 'Groq', logo: 'gq', auth: 'API key' },
    { id: 'mistral', name: 'Mistral', logo: 'm', auth: 'API key' },
    { id: 'together', name: 'Together AI', logo: 'tg', auth: 'API key' },
    { id: 'fireworks', name: 'Fireworks', logo: 'fw', auth: 'API key' },
    { id: 'cohere', name: 'Cohere', logo: 'co', auth: 'API key' },
    { id: 'ollama', name: 'Ollama', logo: 'ol', auth: 'local URL' },
    { id: 'vllm', name: 'vLLM', logo: 'vL', auth: 'local URL' },
  ];

  return { providers, trafficSeries: trafficSeries(), policies, activity, catalog };
})();
