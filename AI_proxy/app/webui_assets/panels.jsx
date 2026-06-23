// Policies panel + Activity feed + Add Provider modal + Tweaks
const { useState: useStateM } = React;

const PoliciesPanel = () => {
  const { policies } = window.LLMGateData;
  const t = window.t;
  const [list, setList] = useStateM(policies);
  const toggle = (id) => setList(list.map(p => p.id === id ? {...p, active: !p.active} : p));
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>{t('pol.title')}</h3>
        <div className="flex ai-c gap-2">
          <span style={{fontSize:11, color:'var(--text-3)', fontFamily:'var(--mono)'}}>
            {list.filter(p => p.active).length}/{list.length} {t('pol.active')}
          </span>
          <button className="btn btn-sm"><Icon name="plus" />{t('pol.new')}</button>
        </div>
      </div>
      <div className="panel-body" style={{padding:0}}>
        {list.map((p, i) => (
          <div className="policy" key={p.id} style={{opacity: p.active ? 1 : 0.55}}>
            <div className="policy-icon"><Icon name={p.icon} /></div>
            <div className="policy-main">
              <div style={{display:'flex', alignItems:'center', gap:8}}>
                <span className="policy-title">{p.title}</span>
                <span style={{fontSize:10, color:'var(--text-4)', fontFamily:'var(--mono)'}}>#{i+1}</span>
                {p.active && p.hits > 0 && (
                  <span className="pill pill-blue" style={{marginLeft:'auto'}}>{p.hits} hits · 24h</span>
                )}
              </div>
              <div className="policy-rule" dangerouslySetInnerHTML={{__html: p.rule.replace(/`([^`]+)`/g, '<code>$1</code>').replace(/(\b[a-z0-9-\/.:]+\b)/g, (m) => ['limit','route','when','else','mask','force','on','or','if','detect'].includes(m) ? `<span style="color:var(--text-2)">${m}</span>` : m)}}></div>
            </div>
            <span className={`toggle ${p.active ? 'on' : ''}`} onClick={() => toggle(p.id)}></span>
          </div>
        ))}
      </div>
    </div>
  );
};

const ActivityFeed = () => {
  const { activity } = window.LLMGateData;
  const providers = window.LLMGateData.providers;
  const findProv = (id) => providers.find(p => p.id === id) || { logo: '?', accent: '#71717a' };
  const t = window.t;
  const [mode, setModeA] = useStateM('all');
  const [paused, setPaused] = useStateM(false);
  const feed = activity.filter(a => {
    if (mode === 'errors') return a.code >= 400;
    if (mode === 'policy') return a.kind === 'policy';
    return true;
  });
  return (
    <div className="panel">
      <div className="panel-head">
        <h3 className="flex ai-c gap-2"><span className="live-dot"></span>{t('act.title')}</h3>
        <div className="flex ai-c gap-2">
          <div className="segmented">
            <button className={mode === 'all' ? 'on' : ''} onClick={() => setModeA('all')}>{t('act.all')}</button>
            <button className={mode === 'errors' ? 'on' : ''} onClick={() => setModeA('errors')}>{t('act.errors')}</button>
            <button className={mode === 'policy' ? 'on' : ''} onClick={() => setModeA('policy')}>{t('act.policy')}</button>
          </div>
          <button className="btn btn-sm btn-ghost" onClick={() => setPaused(!paused)} title={paused ? 'Resume' : 'Pause'}>
            <Icon name={paused ? 'play' : 'pause'} />
          </button>
        </div>
      </div>
      <div className="panel-body" style={{padding:0, maxHeight:'none', opacity: paused ? 0.55 : 1}}>
        {feed.map((a, i) => {
          const prov = findProv(a.prov);
          const isErr = a.code >= 400;
          return (
            <div className="activity-row" key={i}>
              <span className="activity-time">{a.t}</span>
              <div className="activity-main">
                <ProviderLogo p={prov} size={18} />
                <span className="event" dangerouslySetInnerHTML={{__html: a.msg}}></span>
              </div>
              <span className="status" style={{color: isErr ? 'var(--red)' : 'var(--green)'}}>
                {a.status}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const Hero = ({ onDeploy, onAddProvider }) => {
  const t = window.t;
  return (
    <div className="hero">
      <div>
        <div style={{display:'flex', alignItems:'center', gap:8, marginBottom:8}}>
          <span className="pill pill-blue"><Icon name="bolt" className="nav-icon" style={{width:10, height:10}} />{t('hero.badge')}</span>
          <span style={{fontSize:11, color:'var(--text-3)'}}>{t('hero.sub')}</span>
        </div>
        <h3>{t('hero.title')}</h3>
        <p dangerouslySetInnerHTML={{__html: t('hero.body')}}></p>
      </div>
      <div className="hero-actions">
        <button className="btn" onClick={onDeploy}><Icon name="cube" />{t('page.deploy')}</button>
        <button className="btn btn-primary" onClick={() => window.open('https://docs.tech-sphere.pro/llm-gate', '_blank')}>{t('hero.docs')}<Icon name="external" /></button>
      </div>
    </div>
  );
};

const AddProviderModal = ({ open, onClose, onAdd }) => {
  const [sel, setSel] = useStateM(null);
  const [key, setKey] = useStateM('');
  const [step, setStep] = useStateM(1);
  const [testing, setTesting] = useStateM(false);
  const [tested, setTested] = useStateM(false);

  React.useEffect(() => {
    if (!open) { setSel(null); setKey(''); setStep(1); setTesting(false); setTested(false); }
  }, [open]);

  const doTest = () => {
    setTesting(true);
    setTimeout(() => { setTesting(false); setTested(true); }, 1100);
  };

  return (
    <div className={`modal-backdrop ${open ? 'open' : ''}`} onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-head">
          <h2>Add provider</h2>
          <p>Connect a SaaS or self-hosted inference backend. Step {step} of 2.</p>
        </div>
        <div className="modal-body">
          {step === 1 && (
            <>
              <div className="field">
                <label>Choose a provider</label>
              </div>
              <div className="provider-grid">
                {window.LLMGateData.catalog.map(c => (
                  <button key={c.id} className={`provider-option ${sel?.id === c.id ? 'selected' : ''}`} onClick={() => setSel(c)}>
                    <div className="prov-logo" style={{width:20, height:20, fontSize:9, borderRadius:4}}>{c.logo}</div>
                    <span className="provider-option-name">{c.name}</span>
                    <span className="provider-option-hint">{c.auth}</span>
                  </button>
                ))}
              </div>
            </>
          )}
          {step === 2 && sel && (
            <>
              <div style={{padding:'10px 12px', background:'var(--bg-2)', border:'1px solid var(--border)', borderRadius:6, marginBottom:14, display:'flex', alignItems:'center', gap:10}}>
                <div className="prov-logo" style={{width:26, height:26, fontSize:11}}>{sel.logo}</div>
                <div>
                  <div style={{fontWeight:500}}>{sel.name}</div>
                  <div style={{fontSize:11, color:'var(--text-3)', fontFamily:'var(--mono)'}}>{sel.auth}</div>
                </div>
                <button className="btn btn-sm btn-ghost" style={{marginLeft:'auto'}} onClick={() => setStep(1)}>Change</button>
              </div>
              <div className="field">
                <label>API key</label>
                <input className="input" placeholder={`${sel.id === 'anthropic' ? 'sk-ant-' : sel.id === 'openai' ? 'sk-proj-' : ''}•••••••••`} value={key} onChange={e => setKey(e.target.value)} />
              </div>
              <div className="field">
                <label>Namespace (optional)</label>
                <input className="input" placeholder="prod · staging · team-growth" />
              </div>
              <div className="field">
                <label>Default models</label>
                <div style={{fontSize:12, color:'var(--text-2)', padding:'8px 0'}}>
                  <span style={{color:'var(--text-3)'}}>Catalog will be synced on connect ·</span> <a style={{color:'var(--accent)'}}>customize after</a>
                </div>
              </div>
              <div style={{display:'flex', alignItems:'center', gap:8, marginTop:8, fontSize:12}}>
                <button className="btn btn-sm" onClick={doTest} disabled={!key || testing}>
                  {testing ? 'Testing…' : tested ? <><Icon name="check" />Connected</> : 'Test connection'}
                </button>
                {tested && <span style={{color:'var(--green)', fontFamily:'var(--mono)', fontSize:11}}>✓ 4 models available · 142ms</span>}
              </div>
            </>
          )}
        </div>
        <div className="modal-foot">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          {step === 1 && (
            <button className="btn btn-primary" disabled={!sel} onClick={() => setStep(2)} style={{opacity: sel ? 1 : 0.5}}>
              Continue<Icon name="arrow" />
            </button>
          )}
          {step === 2 && (
            <>
              <button className="btn" onClick={() => setStep(1)}>Back</button>
              <button className="btn btn-primary" disabled={!tested} style={{opacity: tested ? 1 : 0.5}} onClick={() => { onAdd(sel); onClose(); }}>
                Add provider<Icon name="arrow" />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const TweaksPanel = ({ open, onClose, state, setState }) => {
  const accents = [
    { name: 'Teal',    val: 'oklch(72% 0.16 165)' },
    { name: 'Cyan',    val: 'oklch(72% 0.16 220)' },
    { name: 'Violet',  val: 'oklch(68% 0.18 300)' },
    { name: 'Pink',    val: 'oklch(72% 0.18 350)' },
    { name: 'Amber',   val: 'oklch(78% 0.16 75)' },
    { name: 'Green',   val: 'oklch(72% 0.16 140)' },
  ];
  return (
    <div className={`tweaks-panel ${open ? 'open' : ''}`}>
      <div className="tweaks-head">
        <h3><Icon name="sliders" />Tweaks</h3>
        <button className="icon-btn" onClick={onClose} style={{width:22, height:22}}><Icon name="close" /></button>
      </div>
      <div className="tweaks-body">
        <div className="tweak-row">
          <div className="tweak-label">Accent</div>
          <div className="tweak-swatches">
            {accents.map(a => (
              <button key={a.name} className={`swatch ${state.accent === a.val ? 'active' : ''}`} style={{background: a.val}} onClick={() => setState({...state, accent: a.val})} title={a.name}></button>
            ))}
          </div>
        </div>
        <div className="tweak-row">
          <div className="tweak-label">Density</div>
          <div className="segmented" style={{width:'100%'}}>
            {['compact','default','comfortable','spacious'].map(d => (
              <button key={d} className={state.density === d ? 'on' : ''} style={{flex:1}} onClick={() => setState({...state, density: d})}>{d}</button>
            ))}
          </div>
        </div>
        <div className="tweak-row">
          <div className="tweak-label">Layout</div>
          <div className="segmented" style={{width:'100%'}}>
            {[['table','Table'],['grid','Cards']].map(([v, l]) => (
              <button key={v} className={state.layout === v ? 'on' : ''} style={{flex:1}} onClick={() => setState({...state, layout: v})}>{l}</button>
            ))}
          </div>
        </div>
        <div className="tweak-row">
          <div className="tweak-label">Show hero</div>
          <div style={{display:'flex', alignItems:'center', gap:8}}>
            <span className={`toggle ${state.hero ? 'on' : ''}`} onClick={() => setState({...state, hero: !state.hero})}></span>
            <span style={{fontSize:12, color:'var(--text-3)'}}>{state.hero ? 'Visible' : 'Hidden'}</span>
          </div>
        </div>
        <div className="tweak-row">
          <div className="tweak-label">Sparklines</div>
          <div style={{display:'flex', alignItems:'center', gap:8}}>
            <span className={`toggle ${state.sparks ? 'on' : ''}`} onClick={() => setState({...state, sparks: !state.sparks})}></span>
            <span style={{fontSize:12, color:'var(--text-3)'}}>In table rows</span>
          </div>
        </div>
      </div>
    </div>
  );
};

Object.assign(window, { PoliciesPanel, ActivityFeed, Hero, AddProviderModal, TweaksPanel });
