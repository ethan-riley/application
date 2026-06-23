// Shell: topbar + navbar + sidebar + page header.
// Translations via window.t() (see i18n.js).
const { useState, useEffect, useRef, useMemo } = React;

const Topbar = ({ theme, setTheme, searchValue, onSearchChange, userBadge }) => {
  const t = window.t;
  return (
    <div className="topbar">
      <div className="brand">
        <div className="brand-mark"></div>
        <div className="brand-text"><span>LLM Gate</span></div>
      </div>
      <div className="env-switcher">
        <span className="env-dot"></span>
        <span>acme-prod</span>
        <Icon name="chev" className="chev" />
      </div>
      <div className="topbar-search" style={{display:'flex', alignItems:'center'}}>
        <Icon name="search" />
        <input
          className="search-input"
          placeholder={t('topbar.search.placeholder')}
          value={searchValue}
          onChange={(e) => onSearchChange(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Escape') onSearchChange(''); }}
          style={{background:'transparent', border:0, color:'var(--text-1)', outline:'none', flex:1, minWidth:0, fontSize:12, padding:0, marginLeft:2}}
        />
        {searchValue ? (
          <button className="icon-btn" style={{width:18, height:18}} onClick={() => onSearchChange('')} title="Clear">
            <Icon name="close" />
          </button>
        ) : <kbd>⌘K</kbd>}
      </div>
      <div className="topbar-right">
        <div className="theme-switch" role="tablist" aria-label="Theme">
          <button className={`theme-btn ${theme === 'light' ? 'active' : ''}`} onClick={() => setTheme('light')} title="Light"><Icon name="sun" /></button>
          <button className={`theme-btn ${theme === 'dark' ? 'active' : ''}`} onClick={() => setTheme('dark')} title="Dark"><Icon name="moon" /></button>
          <button className={`theme-btn ${theme === 'auto' ? 'active' : ''}`} onClick={() => setTheme('auto')} title="Auto"><Icon name="auto" /></button>
        </div>
        <div className="topbar-divider"></div>
        <button className="icon-btn" title={t('topbar.docs')} onClick={() => window.open('https://docs.tech-sphere.pro/llm-gate', '_blank')}><Icon name="external" /></button>
        <button className="icon-btn" title={t('topbar.alerts')}>
          <Icon name="bell" />
          <span className="badge-dot"></span>
        </button>
        <button className="icon-btn" title={t('topbar.settings')}><Icon name="settings" /></button>
        <div className="avatar" title={userBadge || 'User'}>{(userBadge || 'NR').slice(0, 2).toUpperCase()}</div>
      </div>
    </div>
  );
};

const Navbar = ({ activeTab, setActiveTab }) => {
  const t = window.t;
  const tabs = [
    { id: 'Overview',   label: t('nav.overview') },
    { id: 'Providers',  label: t('nav.providers') },
    { id: 'Models',     label: t('nav.models') },
    { id: 'Policies',   label: t('nav.policies') },
    { id: 'API keys',   label: t('nav.apiKeys') },
    { id: 'Playground', label: t('nav.playground') },
    { id: 'Analytics',  label: t('nav.analytics') },
    { id: 'Logs',       label: t('nav.logs') },
  ];
  return (
    <div className="navbar">
      <div className="top-nav">
        {tabs.map(tab => (
          <button key={tab.id} className={`tab ${tab.id === activeTab ? 'active' : ''}`} onClick={() => setActiveTab(tab.id)}>
            {tab.label}
          </button>
        ))}
      </div>
      <div className="navbar-right">
        <span className="mono">openai-compat</span>
        <span style={{color:'var(--text-4)'}}>·</span>
        <span>v2.3.1</span>
      </div>
    </div>
  );
};

const Sidebar = ({ activeTab, setActiveTab, providers }) => {
  const t = window.t;
  const modelsCount = providers.reduce((a, p) => a + (p.models || 0), 0);
  const enabled = providers.filter(p => p.enabled).length;
  const groups = [
    { group: t('side.workspace'), items: [
      { id: 'Overview',   icon: 'overview',  label: t('nav.overview') },
      { id: 'Providers',  icon: 'providers', label: t('nav.providers'), count: enabled },
      { id: 'Models',     icon: 'models',    label: t('nav.models'),    count: modelsCount },
      { id: '__deploy',   icon: 'cube',      label: t('side.deployments'), count: 4 },
    ]},
    { group: t('side.routing'), items: [
      { id: 'Policies',   icon: 'policies',  label: t('nav.policies'), count: 5 },
      { id: '__rate',     icon: 'filter',    label: t('side.rateLimits') },
      { id: '__exp',      icon: 'flask',     label: t('side.experiments'), count: 2 },
    ]},
    { group: t('side.developer'), items: [
      { id: 'API keys',   icon: 'keys',       label: t('nav.apiKeys'), count: 12 },
      { id: 'Playground', icon: 'playground', label: t('nav.playground') },
      { id: 'Logs',       icon: 'logs',       label: t('nav.logs') },
    ]},
    { group: t('side.observability'), items: [
      { id: 'Analytics',  icon: 'analytics', label: t('nav.analytics') },
      { id: '__spend',    icon: 'dollar',    label: t('side.spend') },
      { id: '__alerts',   icon: 'bell',      label: t('topbar.alerts'), count: 2 },
    ]},
  ];
  return (
    <aside className="sidebar">
      {groups.map((g, i) => (
        <div className="nav-group" key={i}>
          <div className="nav-group-label">{g.group}</div>
          {g.items.map(it => (
            <div
              key={it.id}
              className={`nav-item ${activeTab === it.id ? 'active' : ''}`}
              onClick={() => setActiveTab(it.id)}
              role="button"
            >
              <Icon name={it.icon} className="nav-icon" />
              {it.label}
              {it.count !== undefined && <span className="count">{it.count}</span>}
            </div>
          ))}
        </div>
      ))}
      <div className="sidebar-footer">
        <div className="quota-row"><span>{t('side.budget')}</span><strong>62%</strong></div>
        <div className="quota-bar"><div className="quota-bar-fill" style={{width:'62%'}}></div></div>
        <div className="quota-row"><span>6,210 / 10,000</span><span className="dim">{t('side.freeTier')}</span></div>
        <div style={{height:6}}></div>
        <div className="quota-row"><span>{t('side.gpuHours')}</span><strong>38%</strong></div>
        <div className="quota-bar"><div className="quota-bar-fill" style={{width:'38%', background:'var(--blue)'}}></div></div>
        <div className="quota-row"><span>278 / 730 hrs</span><span className="dim">{t('side.selfHosted')}</span></div>
      </div>
    </aside>
  );
};

const PageHeader = ({ title, timeRange, setTimeRange, onAddProvider, onDeploy, onExport }) => {
  const t = window.t;
  const ranges = ['1h', '24h', '7d', '30d'];
  return (
    <div className="page-header">
      <div>
        <h1>{title || t('page.overview')}</h1>
        <div className="page-header-sub">
          <span className="flex ai-c" style={{gap:6}}><span className="live-dot"></span>{t('page.liveSync')}</span>
          <span className="sep">·</span>
          <span>acme-prod / <span className="mono">openai-compat</span></span>
          <span className="sep">·</span>
          <span>{t('page.region')}: <span className="mono">us-east-1</span></span>
        </div>
      </div>
      <div className="page-actions">
        <div className="segmented">
          {ranges.map(r => (
            <button key={r} className={timeRange === r ? 'on' : ''} onClick={() => setTimeRange(r)}>{r}</button>
          ))}
        </div>
        <button className="btn" onClick={onExport}><Icon name="download" />{t('page.export')}</button>
        <button className="btn" onClick={onDeploy}><Icon name="cube" />{t('page.deploy')}</button>
        <button className="btn btn-primary" onClick={onAddProvider}><Icon name="plus" />{t('page.addProvider')}</button>
      </div>
    </div>
  );
};

Object.assign(window, { Topbar, Navbar, Sidebar, PageHeader });
