// Provider table + drawer
const { useState: useStateP } = React;

const StatusPill = ({ status }) => {
  const map = {
    healthy: { cls: 'pill-green', label: 'healthy' },
    degraded: { cls: 'pill-amber', label: 'degraded' },
    down: { cls: 'pill-red', label: 'down' },
    unconfigured: { cls: 'pill-neutral', label: 'unconfigured' },
    disabled: { cls: 'pill-neutral', label: 'disabled' },
  };
  const m = map[status] || map.unconfigured;
  return (
    <span className={`pill ${m.cls}`}>
      <span className="pill-dot" style={{background:'currentColor'}}></span>
      {m.label}
    </span>
  );
};

const ProviderLogo = ({ p, size = 22 }) => (
  <div className="prov-logo" style={{width:size, height:size, background: p.accent ? `color-mix(in oklab, ${p.accent} 18%, var(--bg-3))` : 'var(--bg-3)', color: p.accent || 'var(--text-2)', borderColor: p.accent ? `color-mix(in oklab, ${p.accent} 30%, var(--border))` : 'var(--border)'}}>
    {p.logo}
  </div>
);

const ProviderTable = ({ onSelect, selected, filter, providers: propProviders, search = '' }) => {
  const providers = propProviders || window.LLMGateData.providers;
  const t = window.t;
  const [sort, setSort] = useStateP({ key: 'req24h', dir: 'desc' });

  let list = providers.slice();
  if (filter && filter !== 'all') {
    if (filter === 'external') list = list.filter(p => p.kind === 'external');
    if (filter === 'self-hosted') list = list.filter(p => p.kind === 'self-hosted');
    if (filter === 'issues') list = list.filter(p => p.status !== 'healthy' || p.key === 'missing');
  }
  if (search && search.trim()) {
    const q = search.trim().toLowerCase();
    list = list.filter(p =>
      p.name.toLowerCase().includes(q) ||
      p.id.toLowerCase().includes(q) ||
      (p.modelList || []).some(m => m.toLowerCase().includes(q))
    );
  }
  list.sort((a, b) => {
    const av = a[sort.key], bv = b[sort.key];
    if (typeof av === 'number') return sort.dir === 'asc' ? av - bv : bv - av;
    return sort.dir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
  });

  const headCell = (label, key, align) => (
    <th onClick={() => setSort({ key, dir: sort.key === key && sort.dir === 'desc' ? 'asc' : 'desc' })}
        style={{textAlign: align || 'left', cursor:'pointer', userSelect:'none'}}>
      {label}
      {sort.key === key && <span style={{marginLeft:4, opacity:0.6}}>{sort.dir === 'desc' ? '↓' : '↑'}</span>}
    </th>
  );

  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th style={{width: 28}}></th>
            {headCell(t('tbl.provider'), 'name')}
            <th style={{width: 90}}>{t('tbl.kind')}</th>
            <th style={{width: 110}}>{t('tbl.status')}</th>
            {headCell(t('tbl.models'), 'models', 'right')}
            {headCell(t('tbl.rpm'), 'rpm', 'right')}
            {headCell(t('tbl.tpm'), 'tpm', 'right')}
            {headCell(t('tbl.p50'), 'p50', 'right')}
            {headCell(t('tbl.p99'), 'p99', 'right')}
            {headCell(t('tbl.err'), 'err', 'right')}
            {headCell(t('tbl.cost24h'), 'cost24h', 'right')}
            <th style={{width: 80}}>{t('tbl.traffic')}</th>
            <th style={{width: 40}}></th>
          </tr>
        </thead>
        <tbody>
          {list.length === 0 && (
            <tr><td colSpan={13} style={{textAlign:'center', color:'var(--text-3)', padding:'22px 8px', fontSize:13}}>{t('tbl.noResults')}</td></tr>
          )}
          {list.map(p => (
            <tr key={p.id} className={selected?.id === p.id ? 'selected' : ''} onClick={() => onSelect(p)}>
              <td><ProviderLogo p={p} size={22} /></td>
              <td>
                <div style={{display:'flex', flexDirection:'column', gap:1}}>
                  <span className="prov-name">{p.name}</span>
                  <span className="prov-models">
                    {p.key === 'missing' ? <span style={{color:'var(--amber)'}}>{t('tbl.missingKey')}</span> :
                     p.keyMasked === '—' ? 'local' : p.keyMasked}
                  </span>
                </div>
              </td>
              <td><span className="pill pill-neutral">{p.kind}</span></td>
              <td><StatusPill status={p.enabled ? p.status : 'disabled'} /></td>
              <td className="col-num">{p.models}</td>
              <td className="col-num-strong">{p.rpm || '—'}</td>
              <td className="col-num">{p.tpm === '0' ? '—' : p.tpm}</td>
              <td className="col-num">{p.p50 ? p.p50 + 'ms' : '—'}</td>
              <td className="col-num" style={{color: p.p99 > 3000 ? 'var(--amber)' : undefined}}>{p.p99 ? p.p99 + 'ms' : '—'}</td>
              <td className="col-num" style={{color: p.err >= 1 ? 'var(--red)' : p.err > 0.2 ? 'var(--amber)' : 'var(--text-2)'}}>
                {p.rpm ? p.err.toFixed(2) : '—'}
              </td>
              <td className="col-num-strong">{p.cost24h > 0 ? '$' + p.cost24h.toFixed(2) : p.kind === 'self-hosted' ? 'free' : '$0'}</td>
              <td>
                <Sparkline values={p.spark} w={70} h={20} color={p.status === 'degraded' ? 'var(--amber)' : p.status === 'unconfigured' ? 'var(--text-4)' : 'var(--accent)'} fill />
              </td>
              <td style={{textAlign:'right'}}>
                <button className="icon-btn" style={{width:22, height:22}} onClick={(e) => { e.stopPropagation(); onSelect(p); }}>
                  <Icon name="chev" className="nav-icon" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const Drawer = ({ provider, onClose, onToggleEnabled }) => {
  const [tab, setTab] = useStateP('overview');
  if (!provider) return null;
  const p = provider;

  return (
    <>
      <div className={`drawer-backdrop ${p ? 'open' : ''}`} onClick={onClose}></div>
      <div className={`drawer ${p ? 'open' : ''}`}>
        <div className="drawer-head">
          <ProviderLogo p={p} size={32} />
          <div>
            <h2>{p.name}</h2>
            <div style={{fontSize:11, color:'var(--text-3)', fontFamily:'var(--mono)', marginTop:2}}>
              {p.kind} · {p.region} · added {p.added}
            </div>
          </div>
          <button className="drawer-close" onClick={onClose}><Icon name="close" /></button>
        </div>
        <div className="drawer-tabs">
          {['overview', 'models', 'logs', 'settings'].map(t => (
            <button key={t} className={`drawer-tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
              {t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        <div className="drawer-body">
          {tab === 'overview' && (
            <>
              <div style={{display:'flex', gap:8, marginBottom:14, alignItems:'center'}}>
                <StatusPill status={p.enabled ? p.status : 'disabled'} />
                <div style={{marginLeft:'auto', display:'flex', alignItems:'center', gap:8, fontSize:12, color:'var(--text-2)'}}>
                  <span>Enabled</span>
                  <span className={`toggle ${p.enabled ? 'on' : ''}`} onClick={() => onToggleEnabled(p.id)}></span>
                </div>
              </div>

              <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginBottom:16}}>
                {[
                  ['Requests 24h', p.req24h.toLocaleString()],
                  ['Cost 24h', p.cost24h > 0 ? '$' + p.cost24h.toFixed(2) : 'free'],
                  ['p50 latency', p.p50 ? p.p50 + 'ms' : '—'],
                  ['p99 latency', p.p99 ? p.p99 + 'ms' : '—'],
                  ['Error rate', p.rpm ? p.err.toFixed(2) + '%' : '—'],
                  ['Models', p.models],
                ].map(([k, v]) => (
                  <div key={k} style={{padding:'10px 12px', background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:6}}>
                    <div style={{fontSize:10, color:'var(--text-3)', textTransform:'uppercase', letterSpacing:'0.05em', fontWeight:500}}>{k}</div>
                    <div style={{fontFamily:'var(--mono)', fontSize:15, color:'var(--text-1)', marginTop:3, fontWeight:500}}>{v}</div>
                  </div>
                ))}
              </div>

              <h4 style={{fontSize:11, color:'var(--text-3)', textTransform:'uppercase', letterSpacing:'0.06em', margin:'0 0 6px'}}>Connection</h4>
              <dl className="kv">
                <dt>Endpoint</dt><dd>{p.kind === 'self-hosted' ? 'http://ollama.svc.cluster/v1' : 'https://api.' + p.name + '.com/v1'}</dd>
                <dt>Auth</dt><dd>{p.keyMasked}</dd>
                <dt>Region</dt><dd>{p.region}</dd>
                <dt>Timeout</dt><dd>30s</dd>
                <dt>Retries</dt><dd>3 · exponential</dd>
              </dl>

              <h4 style={{fontSize:11, color:'var(--text-3)', textTransform:'uppercase', letterSpacing:'0.06em', margin:'16px 0 6px'}}>Traffic · last 60 min</h4>
              <div style={{background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:6, padding:12}}>
                <Sparkline values={p.spark.length ? p.spark : [0,0,0]} w={432} h={72} color={p.status === 'degraded' ? 'var(--amber)' : 'var(--accent)'} fill />
              </div>
            </>
          )}
          {tab === 'models' && (
            <div>
              <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:10}}>
                <span style={{fontSize:12, color:'var(--text-3)'}}>{p.modelList.length} model{p.modelList.length !== 1 && 's'} registered</span>
                <button className="btn btn-sm"><Icon name="plus" />Register model</button>
              </div>
              <table className="mini-tbl">
                <thead>
                  <tr><th>Model</th><th>Context</th><th>Req 24h</th><th>Enabled</th></tr>
                </thead>
                <tbody>
                  {p.modelList.length === 0 && (
                    <tr><td colSpan={4} style={{color:'var(--text-3)', textAlign:'center', padding:20}}>
                      No models registered. Add a key first to sync the catalog.
                    </td></tr>
                  )}
                  {p.modelList.map((m, i) => (
                    <tr key={m}>
                      <td className="name">{m}</td>
                      <td>{[200000, 128000, 64000, 32000, 8192][i % 5].toLocaleString()}</td>
                      <td>{Math.floor(p.req24h / Math.max(1, p.modelList.length) * (0.5 + Math.random())).toLocaleString()}</td>
                      <td><span className="toggle on"></span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {tab === 'logs' && (
            <div style={{fontFamily:'var(--mono)', fontSize:11, color:'var(--text-2)'}}>
              {window.LLMGateData.activity.filter(a => a.prov === p.id).slice(0, 8).map((a, i) => (
                <div key={i} style={{padding:'6px 8px', borderBottom:'1px solid var(--border)', display:'flex', gap:8}}>
                  <span style={{color:'var(--text-3)'}}>{a.t}</span>
                  <span style={{color: a.code === 200 ? 'var(--green)' : 'var(--red)'}}>{a.status}</span>
                  <span dangerouslySetInnerHTML={{__html: a.msg}}></span>
                </div>
              ))}
              {window.LLMGateData.activity.filter(a => a.prov === p.id).length === 0 && (
                <div style={{color:'var(--text-3)', textAlign:'center', padding:20}}>No recent activity.</div>
              )}
            </div>
          )}
          {tab === 'settings' && (
            <>
              <div className="field">
                <label>API key</label>
                <input className="input" defaultValue={p.keyMasked} readOnly />
              </div>
              <div className="field">
                <label>Base URL</label>
                <input className="input" defaultValue={p.kind === 'self-hosted' ? 'http://ollama.svc.cluster/v1' : 'https://api.' + p.name + '.com/v1'} />
              </div>
              <div className="field">
                <label>Rate limit override</label>
                <input className="input" defaultValue="200 req/min" />
              </div>
              <div style={{display:'flex', gap:6, marginTop:12}}>
                <button className="btn">Test connection</button>
                <button className="btn" style={{color:'var(--red)', borderColor:'color-mix(in oklab, var(--red) 30%, var(--border))'}}>Remove provider</button>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
};

Object.assign(window, { ProviderTable, Drawer, StatusPill, ProviderLogo });
