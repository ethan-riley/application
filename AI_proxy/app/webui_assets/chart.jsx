// KPI strip + traffic chart
const { useState: useStateK, useRef: useRefK } = React;

const KPIStrip = () => {
  const kpis = [
    { label: 'Requests / min', value: '448', unit: '', delta: '+12%', kind: 'up', spark: window.LLMGateData.trafficSeries.map(p => p.external + p.selfhosted + p.cached), color: 'var(--accent)' },
    { label: 'Tokens / min', value: '314', unit: 'K', delta: '+8.1%', kind: 'up', spark: [40,42,38,50,54,60,62,58,66,72,68,74,80,76,82,78,86,90,88,94,92,96,102,100], color: 'var(--blue)' },
    { label: 'Spend today', value: '$82.96', unit: '', delta: '-4.2%', kind: 'down-good', spark: [20,24,22,28,30,34,36,40,42,46,48,52,56,58,62,66,68,72,74,76,78,80,82,82], color: 'var(--green)' },
    { label: 'Error rate', value: '0.38', unit: '%', delta: '+0.06', kind: 'up-bad', spark: [0.2,0.3,0.25,0.22,0.28,0.35,0.40,0.38,0.42,0.48,0.32,0.30,0.28,0.33,0.38,0.41,0.36,0.34,0.38,0.42,0.39,0.36,0.40,0.38], color: 'var(--amber)' },
    { label: 'p99 latency', value: '1.82', unit: 's', delta: '-120ms', kind: 'down-good', spark: [2.1,2.0,1.9,2.1,2.2,2.0,1.8,1.9,2.0,1.85,1.82,1.78,1.90,1.88,1.86,1.84,1.82,1.80,1.88,1.85,1.83,1.82,1.80,1.82], color: 'var(--purple)' },
  ];
  const deltaClass = (kind) => {
    if (kind === 'up' || kind === 'down-good') return '';
    if (kind === 'up-bad') return 'down';
    if (kind === 'down') return 'down';
    return 'neutral';
  };
  return (
    <div className="kpi-strip">
      {kpis.map((k, i) => (
        <div className="kpi" key={i}>
          <div className="kpi-label">{k.label}</div>
          <div className="kpi-value">
            {k.value}{k.unit && <span className="unit">{k.unit}</span>}
          </div>
          <div className={`kpi-delta ${deltaClass(k.kind)}`}>
            <span>{k.delta}</span>
            <span className="dim" style={{color:'var(--text-4)'}}>vs yesterday</span>
          </div>
          <div className="kpi-spark">
            <Sparkline values={k.spark} w={70} h={28} color={k.color} fill />
          </div>
        </div>
      ))}
    </div>
  );
};

const TrafficChart = () => {
  const data = window.LLMGateData.trafficSeries;
  const wrapRef = useRefK(null);
  const [tooltip, setTooltip] = useStateK(null);

  const W = 1000, H = 180, pad = { l: 36, r: 12, t: 12, b: 22 };
  const chartW = W - pad.l - pad.r;
  const chartH = H - pad.t - pad.b;
  const maxY = Math.ceil(Math.max(...data.map(p => p.external + p.selfhosted + p.cached)) / 100) * 100;

  const xFor = (i) => pad.l + (i / (data.length - 1)) * chartW;
  const yFor = (v) => pad.t + chartH - (v / maxY) * chartH;

  // Stacked areas: cached (bottom), self-hosted (mid), external (top)
  const stacks = data.map(p => ({
    t: p.t,
    cached: p.cached,
    selfhostedTop: p.cached + p.selfhosted,
    externalTop: p.cached + p.selfhosted + p.external,
  }));

  const areaPath = (key, prevKey) => {
    const top = stacks.map((p, i) => `${i === 0 ? 'M' : 'L'}${xFor(i).toFixed(1)},${yFor(p[key]).toFixed(1)}`).join(' ');
    const bot = stacks.slice().reverse().map((p, ri) => {
      const i = stacks.length - 1 - ri;
      const v = prevKey ? p[prevKey] : 0;
      return `L${xFor(i).toFixed(1)},${yFor(v).toFixed(1)}`;
    }).join(' ');
    return `${top} ${bot} Z`;
  };

  const handleMove = (e) => {
    const rect = wrapRef.current.getBoundingClientRect();
    const ratio = W / rect.width;
    const x = (e.clientX - rect.left) * ratio;
    const idx = Math.round(((x - pad.l) / chartW) * (data.length - 1));
    if (idx < 0 || idx >= data.length) { setTooltip(null); return; }
    const p = data[idx];
    setTooltip({
      x: xFor(idx) / ratio,
      y: yFor(p.external + p.selfhosted + p.cached) / ratio,
      idx, p,
    });
  };

  // grid lines
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map(r => Math.round(maxY * r));

  return (
    <div className="chart-card">
      <div className="chart-head">
        <div>
          <div style={{fontSize:12, color:'var(--text-2)', fontWeight:500}}>Request volume — last 60 min</div>
          <div style={{fontSize:11, color:'var(--text-3)', marginTop:2}} className="mono">
            avg <span style={{color:'var(--text-1)'}}>448/min</span> · peak <span style={{color:'var(--text-1)'}}>612/min</span>
          </div>
        </div>
        <div className="chart-legend">
          <div className="legend-item"><span className="legend-swatch" style={{background:'var(--accent)'}}></span>external</div>
          <div className="legend-item"><span className="legend-swatch" style={{background:'var(--blue)'}}></span>self-hosted</div>
          <div className="legend-item"><span className="legend-swatch" style={{background:'var(--text-3)'}}></span>cached</div>
        </div>
      </div>
      <div className="chart-wrap" ref={wrapRef} onMouseMove={handleMove} onMouseLeave={() => setTooltip(null)}>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
          <defs>
            <linearGradient id="grad-ext" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="oklch(72% 0.16 165)" stopOpacity="0.35" />
              <stop offset="100%" stopColor="oklch(72% 0.16 165)" stopOpacity="0.05" />
            </linearGradient>
            <linearGradient id="grad-sh" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#60a5fa" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#60a5fa" stopOpacity="0.05" />
            </linearGradient>
            <linearGradient id="grad-cache" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#71717a" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#71717a" stopOpacity="0.05" />
            </linearGradient>
          </defs>

          {/* horizontal gridlines */}
          {yTicks.map((t, i) => (
            <g key={i}>
              <line x1={pad.l} x2={W - pad.r} y1={yFor(t)} y2={yFor(t)} stroke="var(--border)" strokeDasharray={i === 0 ? '' : '2,3'} />
              <text x={pad.l - 6} y={yFor(t) + 3} fontSize="10" textAnchor="end" fill="var(--text-3)" fontFamily="var(--mono)">{t}</text>
            </g>
          ))}

          {/* x labels */}
          {[0, 15, 30, 45, 59].map(i => (
            <text key={i} x={xFor(i)} y={H - 6} fontSize="10" textAnchor="middle" fill="var(--text-3)" fontFamily="var(--mono)">
              {i === 59 ? 'now' : `-${59 - i}m`}
            </text>
          ))}

          {/* stacks */}
          <path d={areaPath('cached')} fill="url(#grad-cache)" />
          <path d={areaPath('selfhostedTop', 'cached')} fill="url(#grad-sh)" />
          <path d={areaPath('externalTop', 'selfhostedTop')} fill="url(#grad-ext)" />

          {/* top line (total) */}
          <path
            d={stacks.map((p, i) => `${i === 0 ? 'M' : 'L'}${xFor(i).toFixed(1)},${yFor(p.externalTop).toFixed(1)}`).join(' ')}
            fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
          />

          {/* tooltip crosshair */}
          {tooltip && (
            <g>
              <line x1={xFor(tooltip.idx)} x2={xFor(tooltip.idx)} y1={pad.t} y2={H - pad.b} stroke="var(--border-3)" strokeDasharray="2,2" />
              <circle cx={xFor(tooltip.idx)} cy={yFor(tooltip.p.external + tooltip.p.selfhosted + tooltip.p.cached)} r="3" fill="var(--accent)" stroke="var(--bg-1)" strokeWidth="2" />
            </g>
          )}
        </svg>
        {tooltip && (
          <div className="chart-tooltip show" style={{left: tooltip.x, top: tooltip.y}}>
            <div className="tt-row"><span className="tt-label">t</span><span>-{59 - tooltip.idx}m</span></div>
            <div className="tt-row"><span className="tt-label">external</span><span style={{color:'var(--accent)'}}>{Math.round(tooltip.p.external)}</span></div>
            <div className="tt-row"><span className="tt-label">self-hosted</span><span style={{color:'var(--blue)'}}>{Math.round(tooltip.p.selfhosted)}</span></div>
            <div className="tt-row"><span className="tt-label">cached</span><span style={{color:'var(--text-2)'}}>{Math.round(tooltip.p.cached)}</span></div>
            <div className="tt-row" style={{borderTop:'1px solid var(--border)', marginTop:4, paddingTop:4}}>
              <span className="tt-label">total</span><span style={{color:'var(--text-1)'}}>{Math.round(tooltip.p.external + tooltip.p.selfhosted + tooltip.p.cached)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

Object.assign(window, { KPIStrip, TrafficChart });
