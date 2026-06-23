// Real-backend views: API keys + Playground.
// Wires against /v1/admin/api-keys and /v1/chat/completions.
const { useState: useStateV, useEffect: useEffectV } = React;

// ─── API keys view ───────────────────────────────────────
const ApiKeysView = () => {
  const t = window.t;
  const [keys, setKeys] = useStateV([]);
  const [loading, setLoading] = useStateV(false);
  const [error, setError]   = useStateV('');
  const [name, setName]     = useStateV('');
  const [owner, setOwner]   = useStateV('platform');
  const [env, setEnv]       = useStateV('prod');
  const [lastCreated, setLastCreated] = useStateV(null);
  const [creating, setCreating] = useStateV(false);

  const load = async () => {
    setLoading(true); setError('');
    try {
      const r = await fetch('/v1/admin/api-keys');
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setKeys(Array.isArray(data) ? data : (data.api_keys || data.keys || []));
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffectV(() => { load(); }, []);

  const create = async () => {
    if (!name.trim()) return;
    setCreating(true); setError('');
    try {
      const r = await fetch('/v1/admin/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), labels: { owner, env } }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
      const data = await r.json();
      setLastCreated(data);
      setName('');
      await load();
    } catch (e) { setError(e.message); }
    finally { setCreating(false); }
  };

  const copy = (s) => navigator.clipboard?.writeText(s);

  return (
    <div className="section">
      <div className="two-col">
        <div className="panel">
          <div className="panel-head">
            <h3>{t('keys.proxyKeys') || 'Proxy API keys'}</h3>
            <button className="btn btn-sm" onClick={load} disabled={loading}>
              <Icon name="refresh" />{loading ? '…' : (t('keys.refresh') || 'Refresh')}
            </button>
          </div>
          <div className="panel-body" style={{padding:14, display:'flex', flexDirection:'column', gap:10}}>
            <div className="field">
              <label>{t('keys.name') || 'Name'}</label>
              <input className="input" placeholder="sdk-client" value={name} onChange={e => setName(e.target.value)} />
            </div>
            <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:8}}>
              <div className="field" style={{margin:0}}>
                <label>{t('keys.owner') || 'Owner'}</label>
                <input className="input" value={owner} onChange={e => setOwner(e.target.value)} />
              </div>
              <div className="field" style={{margin:0}}>
                <label>{t('keys.env') || 'Env'}</label>
                <input className="input" value={env} onChange={e => setEnv(e.target.value)} />
              </div>
            </div>
            <button className="btn btn-primary" onClick={create} disabled={creating || !name.trim()}>
              <Icon name="plus" />{creating ? (t('keys.creating') || 'Creating…') : (t('keys.create') || 'Create key')}
            </button>

            {lastCreated && (
              <div style={{background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:6, padding:12}}>
                <div style={{fontSize:11, color:'var(--text-3)', marginBottom:6}}>
                  {t('keys.oneTimeNote') || 'Shown once. Save it now.'}
                </div>
                <div style={{display:'flex', alignItems:'center', gap:6}}>
                  <code style={{fontFamily:'var(--mono)', fontSize:12, flex:1, wordBreak:'break-all', color:'var(--text-1)'}}>
                    {lastCreated.api_key || lastCreated.key || lastCreated.token || JSON.stringify(lastCreated)}
                  </code>
                  <button className="btn btn-sm" onClick={() => copy(lastCreated.api_key || lastCreated.key || lastCreated.token || '')}>
                    <Icon name="copy" />Copy
                  </button>
                </div>
              </div>
            )}

            {error && <div style={{color:'var(--red)', fontSize:12}}>{error}</div>}
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h3>{t('keys.existing') || 'Existing keys'}</h3>
            <span style={{fontSize:11, color:'var(--text-3)', fontFamily:'var(--mono)'}}>{keys.length}</span>
          </div>
          <div className="panel-body" style={{padding:0, maxHeight:'none'}}>
            {keys.length === 0 && (
              <div style={{padding:22, textAlign:'center', color:'var(--text-3)', fontSize:13}}>
                {loading ? (t('keys.loading') || 'Loading…') : (t('keys.empty') || 'No keys yet.')}
              </div>
            )}
            {keys.map((k, i) => (
              <div key={k.id || k.name || i} style={{padding:'10px 14px', borderBottom:'1px solid var(--border)', display:'grid', gridTemplateColumns:'1fr auto', gap:8}}>
                <div>
                  <div style={{fontWeight:500}}>{k.name || k.id}</div>
                  <div style={{fontSize:11, color:'var(--text-3)', fontFamily:'var(--mono)', marginTop:2}}>
                    {k.prefix ? k.prefix + '•••' : (k.id || '').slice(0, 12) + '…'}
                    {k.labels && ' · ' + Object.entries(k.labels).map(([x, y]) => `${x}=${y}`).join(' · ')}
                  </div>
                </div>
                <div style={{fontSize:11, color:'var(--text-3)', alignSelf:'center', fontFamily:'var(--mono)'}}>
                  {k.created_at || k.createdAt || ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

// ─── Playground view ─────────────────────────────────────
// Two-pane comparison: AI router (auto-selects model based on prompt analysis)
// vs. user-pinned model. Both run in parallel; outputs displayed side-by-side
// with full routing rationale, cost, latency, and tokens.
const PlaygroundView = () => {
  const t = window.t;
  const providers = window.LLMGateData.providers;
  const availableModels = providers
    .filter(p => p.enabled)
    .flatMap(p => p.modelList.map(m => ({ provider: p.id, model: m, full: `${p.id}:${m}` })));

  const [router, setRouter]       = useStateV('openai:auto');
  const [pinned, setPinned]       = useStateV('openai:gpt-4o-mini');
  const [system, setSystem]       = useStateV('You are a helpful assistant.');
  const [prompt, setPrompt]       = useStateV('Summarize: Quantum entanglement correlates particles non-locally.');
  const [token, setToken]         = useStateV('');
  const [temperature, setTemp]    = useStateV(0.7);
  const [running, setRunning]     = useStateV(false);
  const [routerOut, setRouterOut] = useStateV(null);
  const [pinnedOut, setPinnedOut] = useStateV(null);

  const callOne = async (modelId) => {
    const t0 = performance.now();
    const headers = { 'Content-Type': 'application/json' };
    if (token.trim()) headers['Authorization'] = 'Bearer ' + token.trim();
    try {
      const r = await fetch('/v1/chat/completions', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          model: modelId,
          messages: [
            ...(system.trim() ? [{ role: 'system', content: system.trim() }] : []),
            { role: 'user', content: prompt.trim() },
          ],
          temperature: Number(temperature),
        }),
      });
      const elapsed = Math.round(performance.now() - t0);
      const body = await r.json().catch(() => ({}));
      if (!r.ok) {
        return { ok: false, elapsed, error: body.detail || body.error?.message || `HTTP ${r.status}` };
      }
      return {
        ok: true,
        elapsed,
        content: body.choices?.[0]?.message?.content || '(empty)',
        model: body.model || modelId,
        finish: body.choices?.[0]?.finish_reason || '-',
        usage: body.usage || {},
        meta: body.control_plane || {},
      };
    } catch (e) {
      return { ok: false, elapsed: Math.round(performance.now() - t0), error: e.message };
    }
  };

  const run = async () => {
    if (!prompt.trim()) return;
    setRunning(true);
    setRouterOut({ loading: true });
    setPinnedOut({ loading: true });
    const [a, b] = await Promise.all([callOne(router), callOne(pinned)]);
    setRouterOut(a);
    setPinnedOut(b);
    setRunning(false);
  };

  return (
    <div className="section" style={{display:'flex', flexDirection:'column', gap:14}}>
      <div className="panel">
        <div className="panel-head">
          <h3>{t('play.title') || 'Playground'}</h3>
          <span style={{fontSize:11, color:'var(--text-3)', fontFamily:'var(--mono)'}}>side-by-side · POST /v1/chat/completions</span>
        </div>
        <div className="panel-body" style={{padding:16, display:'grid', gridTemplateColumns:'1fr 1fr', gap:14}}>
          <div className="field" style={{margin:0}}>
            <label style={{display:'flex', alignItems:'center', gap:6}}>
              <Icon name="bolt" /> {t('play.routerLabel') || 'AI router (auto)'}
            </label>
            <select className="input" value={router} onChange={e => setRouter(e.target.value)}>
              <option value="openai:auto">openai:auto · cost-aware</option>
              <option value="tools:auto">tools:auto · tool-calling capable</option>
              <option value="local:auto">local:auto · self-hosted only</option>
              <option value="proxy:auto">proxy:auto · any backend</option>
            </select>
          </div>
          <div className="field" style={{margin:0}}>
            <label style={{display:'flex', alignItems:'center', gap:6}}>
              <Icon name="cube" /> {t('play.pinLabel') || 'Pinned model (manual)'}
            </label>
            <select className="input" value={pinned} onChange={e => setPinned(e.target.value)}>
              {availableModels.map(m => <option key={m.full} value={m.full}>{m.full}</option>)}
            </select>
          </div>
          <div className="field" style={{margin:0}}>
            <label>{t('play.temperature') || 'Temperature'}</label>
            <input className="input" type="number" step="0.1" min="0" max="2" value={temperature} onChange={e => setTemp(e.target.value)} />
          </div>
          <div className="field" style={{margin:0}}>
            <label>{t('play.token') || 'API token (optional)'}</label>
            <input className="input" placeholder="Bearer token" value={token} onChange={e => setToken(e.target.value)} />
          </div>
          <div className="field" style={{margin:0, gridColumn:'1 / -1'}}>
            <label>{t('play.system') || 'System'}</label>
            <textarea className="input" rows={2} value={system} onChange={e => setSystem(e.target.value)} style={{fontFamily:'var(--mono)', fontSize:12}}></textarea>
          </div>
          <div className="field" style={{margin:0, gridColumn:'1 / -1'}}>
            <label>{t('play.user') || 'User prompt'}</label>
            <textarea className="input" rows={4} value={prompt} onChange={e => setPrompt(e.target.value)} style={{fontFamily:'var(--mono)', fontSize:13}}></textarea>
          </div>
          <div style={{gridColumn:'1 / -1', display:'flex', justifyContent:'flex-end'}}>
            <button className="btn btn-primary" onClick={run} disabled={running || !prompt.trim()}>
              <Icon name="play" />{running ? (t('play.running') || 'Running both…') : (t('play.runBoth') || 'Run comparison')}
            </button>
          </div>
        </div>
      </div>

      <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:14}}>
        <ResponsePane title={t('play.routerLabel') || 'AI router'} subtitle={router} icon="bolt" data={routerOut} showRouting />
        <ResponsePane title={t('play.pinLabel') || 'Pinned'} subtitle={pinned} icon="cube" data={pinnedOut} />
      </div>
    </div>
  );
};

const ResponsePane = ({ title, subtitle, icon, data, showRouting }) => {
  const t = window.t;
  return (
    <div className="panel" style={{minHeight:200}}>
      <div className="panel-head">
        <h3 style={{display:'flex', alignItems:'center', gap:8}}>
          <Icon name={icon} />{title}
        </h3>
        <span style={{fontSize:11, color:'var(--text-3)', fontFamily:'var(--mono)'}}>{subtitle}</span>
      </div>
      <div className="panel-body" style={{padding:14}}>
        {!data && <div style={{color:'var(--text-3)', fontSize:13, textAlign:'center', padding:24}}>{t('play.idle') || 'Idle. Run a comparison to populate.'}</div>}
        {data?.loading && <div style={{color:'var(--text-3)', fontSize:13, textAlign:'center', padding:24}}>{t('play.calling') || 'Calling…'}</div>}
        {data && !data.loading && !data.ok && (
          <div style={{color:'var(--red)', fontSize:13, padding:'8px 10px', background:'var(--red-dim)', border:'1px solid currentColor', borderRadius:6}}>
            {data.error}<div style={{fontSize:11, marginTop:4, color:'var(--text-3)', fontFamily:'var(--mono)'}}>{data.elapsed}ms</div>
          </div>
        )}
        {data && !data.loading && data.ok && (
          <>
            <div style={{display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:8, marginBottom:10}}>
              <Stat label={t('play.modelUsed') || 'Model used'} value={data.model} mono />
              <Stat label={t('play.latency') || 'Latency'} value={data.elapsed + 'ms'} />
              <Stat label={t('play.tokens') || 'Tokens'} value={data.usage?.total_tokens ?? '—'} />
              <Stat label={t('play.cost') || 'Cost'} value={data.meta?.cost_usd != null ? '$' + data.meta.cost_usd.toFixed(6) : '—'} />
            </div>
            {showRouting && data.meta && (
              <div style={{background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:6, padding:'10px 12px', marginBottom:10, fontSize:12}}>
                <div style={{fontSize:10, fontWeight:700, letterSpacing:'0.08em', color:'var(--text-3)', textTransform:'uppercase', marginBottom:6}}>
                  {t('play.routingDecision') || 'Routing decision'}
                </div>
                <Kv k={t('play.taskType') || 'Task type'} v={data.meta.task_type} />
                <Kv k={t('play.complexity') || 'Complexity'} v={data.meta.complexity} />
                <Kv k={t('play.tier') || 'Recommended tier'} v={data.meta.recommended_tier} />
                <Kv k={t('play.policy') || 'Policy'} v={data.meta.policy_id} />
                {data.meta.routing?.reason && <Kv k={t('play.reason') || 'Reason'} v={data.meta.routing.reason} />}
                {data.meta.routing?.fallback_chain?.length > 0 && (
                  <Kv k={t('play.fallback') || 'Fallback'} v={data.meta.routing.fallback_chain.join(' → ')} />
                )}
              </div>
            )}
            <div style={{background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:6, padding:12, maxHeight:280, overflow:'auto'}}>
              <pre style={{whiteSpace:'pre-wrap', margin:0, fontFamily:'var(--mono)', fontSize:13, color:'var(--text-1)'}}>{data.content}</pre>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

const Stat = ({ label, value, mono }) => (
  <div style={{padding:'8px 10px', background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:6}}>
    <div style={{fontSize:10, color:'var(--text-3)', textTransform:'uppercase', letterSpacing:'0.05em', fontWeight:500}}>{label}</div>
    <div style={{fontFamily: mono === false ? undefined : 'var(--mono)', fontSize:12, color:'var(--text-1)', marginTop:3, fontWeight:500, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}} title={String(value)}>{value}</div>
  </div>
);

const Kv = ({ k, v }) => v == null ? null : (
  <div style={{display:'flex', gap:8, padding:'2px 0'}}>
    <span style={{color:'var(--text-3)', minWidth:120}}>{k}</span>
    <span style={{color:'var(--text-1)', fontFamily:'var(--mono)', fontSize:11}}>{String(v)}</span>
  </div>
);

Object.assign(window, { ApiKeysView, PlaygroundView });
