// Icons — thin line, 1.5px stroke
const Icon = ({ name, className = "" }) => {
  const paths = {
    overview: 'M3 3h7v7H3zM14 3h7v4h-7zM14 10h7v11h-7zM3 14h7v7H3zM14 10',
    providers: 'M3 7l9-4 9 4M3 12l9 4 9-4M3 17l9 4 9-4',
    models: 'M3 5h18M3 12h18M3 19h18M7 5v14M17 5v14',
    policies: 'M12 2l8 4v6c0 5-3.5 9-8 10-4.5-1-8-5-8-10V6z',
    keys: 'M15 7a4 4 0 110 8H9l-2 2v-2l-2-2h4a4 4 0 014-6zm0 4v.01',
    playground: 'M5 3l14 9-14 9z',
    analytics: 'M3 20h18M7 16V9M12 16V4M17 16v-7',
    logs: 'M9 5h10M9 12h10M9 19h10M4 5h1M4 12h1M4 19h1',
    settings: 'M12 8a4 4 0 100 8 4 4 0 000-8zM19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 9 1.65 1.65 0 004.27 7.18l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z',
    plus: 'M12 5v14M5 12h14',
    search: 'M11 19a8 8 0 100-16 8 8 0 000 16zM21 21l-4.3-4.3',
    arrow: 'M5 12h14M13 5l7 7-7 7',
    chev: 'M6 9l6 6 6-6',
    close: 'M6 6l12 12M6 18L18 6',
    shield: 'M12 2l8 4v6c0 5-3.5 9-8 10-4.5-1-8-5-8-10V6z',
    ruler: 'M3 17l4-4 4 4 4-4 4 4M3 7h18',
    lock: 'M6 11h12v10H6zM8 11V7a4 4 0 118 0v4',
    refresh: 'M3 12a9 9 0 019-9 9 9 0 016.8 3.1M21 12a9 9 0 01-9 9 9 9 0 01-6.8-3.1M21 4v5h-5M3 20v-5h5',
    globe: 'M12 2a10 10 0 100 20 10 10 0 000-20zM2 12h20M12 2a15 15 0 010 20M12 2a15 15 0 000 20',
    bolt: 'M13 2L3 14h7v8l10-12h-7z',
    trending: 'M3 17l6-6 4 4 8-8M14 7h7v7',
    check: 'M5 13l4 4L19 7',
    dollar: 'M12 2v20M17 7H9a3 3 0 000 6h6a3 3 0 010 6H6',
    cube: 'M12 2L3 7v10l9 5 9-5V7z M3 7l9 5 9-5 M12 12v10',
    filter: 'M4 4h16l-6 8v6l-4 2v-8z',
    download: 'M12 3v12M7 10l5 5 5-5M4 21h16',
    copy: 'M9 9h12v12H9zM5 15H3V3h12v2',
    bell: 'M15 17h5l-1.4-1.4A2 2 0 0118 14V9a6 6 0 00-12 0v5a2 2 0 01-.6 1.4L4 17h5M9 17a3 3 0 006 0',
    external: 'M15 3h6v6M10 14L21 3M21 14v6H3V6h6',
    play: 'M5 3l14 9-14 9z',
    pause: 'M6 4h4v16H6zM14 4h4v16h-4z',
    flask: 'M10 2v7l-6 10a2 2 0 001.7 3h12.6a2 2 0 001.7-3l-6-10V2M8 2h8',
    sliders: 'M4 6h10M4 12h16M4 18h6M18 4v4M14 10v4M12 16v4',
    chart: 'M3 3v18h18',
    sun: 'M12 3v2M12 19v2M5 12H3M21 12h-2M6 6l1.5 1.5M16.5 16.5L18 18M6 18l1.5-1.5M16.5 7.5L18 6M12 7a5 5 0 100 10 5 5 0 000-10z',
    moon: 'M20 14.5A8 8 0 019.5 4a8 8 0 1010.5 10.5z',
    auto: 'M12 3a9 9 0 100 18 9 9 0 000-18zM12 3v18M12 3a9 9 0 010 18',
  };
  return (
    <svg className={`icon ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d={paths[name] || ''} />
    </svg>
  );
};

// Sparkline
const Sparkline = ({ values, w = 70, h = 20, color = 'var(--text-2)', fill = false }) => {
  if (!values || values.length === 0) {
    return <svg width={w} height={h}><line x1="0" y1={h/2} x2={w} y2={h/2} stroke="var(--border-2)" strokeDasharray="2,2"/></svg>;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = w / (values.length - 1);
  const pts = values.map((v, i) => [i * step, h - ((v - min) / range) * (h - 2) - 1]);
  const d = pts.map((p, i) => (i === 0 ? 'M' : 'L') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  const area = d + ` L${w},${h} L0,${h} Z`;
  return (
    <svg width={w} height={h} style={{display:'inline-block', verticalAlign:'middle'}}>
      {fill && <path d={area} fill={color} opacity="0.15" />}
      <path d={d} fill="none" stroke={color} strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};

Object.assign(window, { Icon, Sparkline });
