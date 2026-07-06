import React from 'react';
import { ShieldAlert, Sun, Activity, ArrowRight, RotateCcw } from 'lucide-react';

export default function Dashboard({
  summary,
  predTemp,
  predHumidity,
  isPredicting,
  predictedLstMap,
  onTempChange,
  onHumidityChange,
  onRunSimulation,
  onResetSimulation
}) {
  if (!summary) {
    return (
      <div style={{ padding: '20px', color: 'var(--text-secondary)' }}>
        Loading municipal data aggregates...
      </div>
    );
  }

  // Calculate apparent temp locally for real-time display
  const e = (predHumidity / 100.0) * 6.105 * Math.exp((17.27 * predTemp) / (237.7 + predTemp));
  const apparentTemp = predTemp + 0.33 * e - 4.0;

  const vCounts = summary.vulnerability_counts || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%', overflowY: 'auto', paddingRight: '4px' }}>
      
      {/* ── Section: Header ── */}
      <div style={{ marginBottom: '4px' }}>
        <h2 style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '2px' }}>Ahmedabad, India</h2>
        <p style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Pilot City Baseline</p>
      </div>

      {/* ── Section: Key Cards (Control Center side-by-side widgets) ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <div className="cc-widget" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '90px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--primary)' }}>
            <Sun size={15} />
            <span style={{ fontSize: '10px', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.05em' }}>Avg LST</span>
          </div>
          <div style={{ fontSize: '22px', fontWeight: 800, color: '#fff' }}>{summary.avg_lst_mean}°C</div>
        </div>

        <div className="cc-widget" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '90px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--accent)' }}>
            <ShieldAlert size={15} />
            <span style={{ fontSize: '10px', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.05em' }}>Avg HVI</span>
          </div>
          <div style={{ fontSize: '22px', fontWeight: 800, color: '#fff' }}>{summary.avg_hvi}</div>
        </div>
      </div>

      {/* ── Section: Stats Breakdown ── */}
      <div className="cc-widget">
        <h3 style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '14px', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
          Physical Cover Indexes
        </h3>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '6px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Built Surface Ratio</span>
              <span style={{ fontWeight: 600, color: '#fff' }}>{(summary.city_built_ratio * 100).toFixed(2)}%</span>
            </div>
            <div style={{ height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ height: '100%', background: 'linear-gradient(90deg, var(--primary), #60a5fa)', width: `${summary.city_built_ratio * 100}%` }}></div>
            </div>
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '6px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Vegetative (Canopy) Ratio</span>
              <span style={{ fontWeight: 600, color: '#fff' }}>{(summary.city_green_ratio * 100).toFixed(2)}%</span>
            </div>
            <div style={{ height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ height: '100%', background: 'linear-gradient(90deg, var(--secondary), #34d399)', width: `${summary.city_green_ratio * 100}%` }}></div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Section: Vulnerability Distribution Chart ── */}
      <div className="cc-widget">
        <h3 style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '14px', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
          Vulnerability Distribution
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {['Extreme', 'High', 'Moderate', 'Low'].map((vclass) => {
            const count = vCounts[vclass] || 0;
            const widthPct = (count / 12) * 100;

            let barColor = 'var(--text-muted)';
            if (vclass === 'Extreme') barColor = 'linear-gradient(90deg, #a855f7, #c084fc)';
            if (vclass === 'High') barColor = 'linear-gradient(90deg, #ec4899, #f472b6)';
            if (vclass === 'Moderate') barColor = 'linear-gradient(90deg, #f43f5e, #fb7185)';
            if (vclass === 'Low') barColor = 'linear-gradient(90deg, #3b82f6, #60a5fa)';

            return (
              <div key={vclass} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ width: '70px', fontSize: '11px', fontWeight: 500, color: 'var(--text-secondary)' }}>{vclass}</span>
                <div style={{ flex: 1, height: '12px', background: 'rgba(0,0,0,0.25)', borderRadius: '6px', overflow: 'hidden' }}>
                  <div style={{ height: '100%', background: barColor, width: `${widthPct}%`, transition: 'width 0.5s ease-out', borderRadius: '6px' }}></div>
                </div>
                <span style={{ width: '50px', fontSize: '11px', textAlign: 'right', fontWeight: 600, color: '#fff' }}>{count} wards</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Section: Risk Forecaster (ML simulation) ── */}
      <div className="cc-widget" style={{ border: '1px solid rgba(59, 130, 246, 0.2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary)', marginBottom: '10px' }}>
          <Activity size={16} />
          <h3 style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
            Risk Predictor (XGBoost)
          </h3>
        </div>

        <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '14px', lineHeight: 1.4 }}>
          Project municipal surface temperatures under local atmospheric constraints.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginBottom: '16px' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '6px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Air Temperature</span>
              <span style={{ color: '#fff', fontWeight: 600 }}>{predTemp}°C</span>
            </div>
            <input
              type="range"
              min="30"
              max="50"
              step="1"
              value={predTemp}
              onChange={(e) => onTempChange(parseInt(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '6px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Relative Humidity</span>
              <span style={{ color: '#fff', fontWeight: 600 }}>{predHumidity}%</span>
            </div>
            <input
              type="range"
              min="10"
              max="90"
              step="5"
              value={predHumidity}
              onChange={(e) => onHumidityChange(parseInt(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>
        </div>

        {/* Calculated Info */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.2)', padding: '10px 14px', borderRadius: 'var(--radius-widget)', marginBottom: '14px', fontSize: '11px' }}>
          <span style={{ color: 'var(--text-secondary)' }}>Apparent Heat Index</span>
          <span style={{ color: apparentTemp >= 40 ? 'var(--danger)' : apparentTemp >= 35 ? 'var(--warning)' : 'var(--secondary)', fontWeight: 700 }}>{apparentTemp.toFixed(1)}°C</span>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={onRunSimulation}
            disabled={isPredicting}
            style={{
              flex: 1,
              background: 'var(--primary)',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--radius-widget)',
              padding: '10px',
              fontWeight: 700,
              fontSize: '12px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              boxShadow: '0 4px 12px rgba(47, 128, 237, 0.25)',
              transition: 'all 0.2s'
            }}
            onMouseOver={(e) => e.target.style.background = '#2563eb'}
            onMouseOut={(e) => e.target.style.background = 'var(--primary)'}
          >
            {isPredicting ? 'Simulating...' : 'Run Simulation'}
            <ArrowRight size={14} />
          </button>

          {predictedLstMap && (
            <button
              onClick={onResetSimulation}
              title="Reset to baseline"
              style={{
                background: 'rgba(255,255,255,0.04)',
                color: 'var(--text-secondary)',
                border: '1px solid var(--border-light)',
                borderRadius: 'var(--radius-widget)',
                width: '40px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
              onMouseOver={(e) => e.target.style.background = 'rgba(255,255,255,0.08)'}
              onMouseOut={(e) => e.target.style.background = 'rgba(255,255,255,0.04)'}
            >
              <RotateCcw size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
