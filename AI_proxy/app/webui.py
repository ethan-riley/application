from __future__ import annotations

from pathlib import Path

ASSETS_DIR = Path(__file__).parent / "webui_assets"


def render_webui() -> str:
    """Serve the LLM Gate dashboard (light theme, i18n from portal cookie)."""
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>LLM Gate — Overview</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/ui/assets/styles.css?v=4" />
<link rel="stylesheet" href="/ui/assets/light-theme.css?v=4" />
</head>
<body>
<div id="root"></div>

<script src="https://unpkg.com/react@18.3.1/umd/react.development.js" crossorigin="anonymous"></script>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js" crossorigin="anonymous"></script>
<script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js" crossorigin="anonymous"></script>

<script src="/ui/assets/i18n.js?v=4"></script>
<script src="/ui/assets/data.js?v=4"></script>
<script type="text/babel" src="/ui/assets/icons.jsx?v=4"></script>
<script type="text/babel" src="/ui/assets/shell.jsx?v=4"></script>
<script type="text/babel" src="/ui/assets/chart.jsx?v=4"></script>
<script type="text/babel" src="/ui/assets/provider_table.jsx?v=4"></script>
<script type="text/babel" src="/ui/assets/panels.jsx?v=4"></script>
<script type="text/babel" src="/ui/assets/views.jsx?v=4"></script>

<script type="text/babel">
const { useState, useEffect } = React;
const t = window.t;

const DEFAULTS = { accent: '#1a9bba', density: 'default', layout: 'table', hero: true, sparks: true };

function Placeholder({ tab }) {
  return (
    <div className="section">
      <div style={{background:'var(--bg-1)', border:'1px solid var(--border)', borderRadius:10, padding:'48px 32px', textAlign:'center', color:'var(--text-3)'}}>
        <h2 style={{color:'var(--text-1)', margin:'0 0 8px'}}>{tab} · {t('placeholder.soon')}</h2>
        <p style={{margin:0}}>{t('placeholder.soonBody')}</p>
      </div>
    </div>
  );
}

function Toast({ message, onClose }) {
  useEffect(() => {
    if (!message) return;
    const id = setTimeout(onClose, 2600);
    return () => clearTimeout(id);
  }, [message, onClose]);
  if (!message) return null;
  return (
    <div style={{
      position:'fixed', bottom:72, right:16, zIndex:30,
      background:'var(--bg-1)', border:'1px solid var(--border)', borderRadius:8,
      padding:'10px 14px', fontSize:13, color:'var(--text-1)',
      boxShadow:'0 10px 30px rgba(15,23,42,0.10)'
    }}>{message}</div>
  );
}

function App() {
  const [activeTab, setActiveTab]   = useState('Overview');
  const [selectedProv, setSelectedProv] = useState(null);
  const [modalOpen, setModalOpen]   = useState(false);
  const [providers, setProviders]   = useState(window.LLMGateData.providers);
  const [filter, setFilter]         = useState('all');
  const [search, setSearch]         = useState('');
  const [timeRange, setTimeRange]   = useState('24h');
  const [metric, setMetric]         = useState('Requests');
  const [tweaksOpen, setTweaksOpen] = useState(false);
  const [state, setState]           = useState(DEFAULTS);
  const [theme, setTheme]           = useState('light');
  const [toast, setToast]           = useState('');

  // Accent cascade to CSS vars
  useEffect(() => {
    document.body.className = `density-${state.density}`;
    document.documentElement.style.setProperty('--accent', state.accent);
    const hex = state.accent.replace('#', '');
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    document.documentElement.style.setProperty('--accent-dim', `rgba(${r},${g},${b},0.12)`);
    document.documentElement.style.setProperty('--accent-line', `rgba(${r},${g},${b},0.35)`);
  }, [state]);

  // Global ⌘K / Ctrl+K focuses search — native browser focus isn't accessible, emit event
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const el = document.querySelector('.topbar .search-input');
        if (el) el.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (selectedProv) {
      const fresh = providers.find(p => p.id === selectedProv.id);
      if (fresh && fresh !== selectedProv) setSelectedProv(fresh);
    }
  }, [providers]);

  const onToggleEnabled = (id) => setProviders(providers.map(p => p.id === id ? {...p, enabled: !p.enabled} : p));
  const showToast = (msg) => setToast(msg);

  const filters = [
    { id: 'all',         label: t('sec.filterAll'),        count: providers.length },
    { id: 'external',    label: t('sec.filterExternal'),   count: providers.filter(p => p.kind === 'external').length },
    { id: 'self-hosted', label: t('sec.filterSelfHosted'), count: providers.filter(p => p.kind === 'self-hosted').length },
    { id: 'issues',      label: t('sec.filterIssues'),     count: providers.filter(p => p.status !== 'healthy' || p.key === 'missing').length },
  ];

  const sectionProviders = (
    <div className="section">
      <div className="section-head">
        <h2><Icon name="providers" />{t('sec.providers')}<span className="section-sub">{t('sec.providersSub', {n: providers.length, e: providers.filter(p => p.enabled).length})}</span></h2>
        <div className="section-actions">
          <div className="segmented">
            {filters.map(f => (
              <button key={f.id} className={filter === f.id ? 'on' : ''} onClick={() => setFilter(f.id)}>
                {f.label}<span style={{marginLeft:5, color:'var(--text-4)', fontFamily:'var(--mono)', fontSize:10}}>{f.count}</span>
              </button>
            ))}
          </div>
          <button className="btn btn-sm" onClick={() => showToast(t('toast.notImplemented'))}><Icon name="filter" />{t('sec.filter')}</button>
          <button className="btn btn-sm btn-primary" onClick={() => setModalOpen(true)}><Icon name="plus" />{t('sec.add')}</button>
        </div>
      </div>
      <ProviderTable onSelect={setSelectedProv} selected={selectedProv} filter={filter} providers={providers} search={search} />
    </div>
  );

  const sectionTraffic = (
    <div className="section">
      <div className="section-head">
        <h2><Icon name="chart" />{t('sec.requestVolume')}<span className="section-sub">{t('sec.requestVolumeSub')}</span></h2>
        <div className="section-actions">
          <div className="segmented">
            {['Requests','Tokens','Cost','Latency'].map(m => {
              const label = { Requests: t('sec.requests'), Tokens: t('sec.tokens'), Cost: t('sec.cost'), Latency: t('sec.latency') }[m];
              return <button key={m} className={metric === m ? 'on' : ''} onClick={() => setMetric(m)}>{label}</button>;
            })}
          </div>
        </div>
      </div>
      <TrafficChart />
    </div>
  );

  const renderView = () => {
    if (activeTab === 'Overview') {
      return (
        <>
          <KPIStrip />
          {state.hero && <Hero onDeploy={() => showToast(t('toast.notImplemented'))} onAddProvider={() => setModalOpen(true)} />}
          {sectionTraffic}
          {sectionProviders}
          <div className="section">
            <div className="two-col">
              <PoliciesPanel />
              <ActivityFeed />
            </div>
          </div>
        </>
      );
    }
    if (activeTab === 'Providers') return sectionProviders;
    if (activeTab === 'Policies') {
      return (
        <div className="section">
          <div className="two-col">
            <PoliciesPanel />
            <ActivityFeed />
          </div>
        </div>
      );
    }
    if (activeTab === 'Logs') return <div className="section"><ActivityFeed /></div>;
    if (activeTab === 'Analytics') {
      return <><KPIStrip />{sectionTraffic}</>;
    }
    if (activeTab === 'API keys') return <ApiKeysView />;
    if (activeTab === 'Playground') return <PlaygroundView />;
    return <Placeholder tab={activeTab} />;
  };

  return (
    <div className="app">
      <Topbar theme={theme} setTheme={setTheme} searchValue={search} onSearchChange={setSearch} userBadge="NR" />
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} providers={providers} />
      <main className="main">
        <PageHeader
          title={t('nav.' + (activeTab === 'Overview' ? 'overview' : activeTab === 'Providers' ? 'providers' : activeTab === 'Models' ? 'models' : activeTab === 'Policies' ? 'policies' : activeTab === 'API keys' ? 'apiKeys' : activeTab === 'Playground' ? 'playground' : activeTab === 'Analytics' ? 'analytics' : activeTab === 'Logs' ? 'logs' : 'overview'))}
          timeRange={timeRange} setTimeRange={setTimeRange}
          onAddProvider={() => setModalOpen(true)}
          onDeploy={() => showToast(t('toast.notImplemented'))}
          onExport={() => {
            const blob = new Blob([JSON.stringify(providers, null, 2)], { type: 'application/json' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'llm-gate-providers.json';
            a.click();
            URL.revokeObjectURL(a.href);
          }}
        />
        {renderView()}
      </main>

      <Drawer provider={selectedProv} onClose={() => setSelectedProv(null)} onToggleEnabled={onToggleEnabled} />
      <AddProviderModal open={modalOpen} onClose={() => setModalOpen(false)} onAdd={() => { showToast(t('toast.notImplemented')); }} />
      <TweaksPanel open={tweaksOpen} onClose={() => setTweaksOpen(false)} state={state} setState={setState} />

      {!tweaksOpen && (
        <button className="btn" style={{position:'fixed', right:16, bottom:16, zIndex:20, boxShadow:'0 6px 20px rgba(15,23,42,0.10)'}} onClick={() => setTweaksOpen(true)}>
          <Icon name="sliders" />Tweaks
        </button>
      )}

      <Toast message={toast} onClose={() => setToast('')} />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
</script>
</body>
</html>"""
