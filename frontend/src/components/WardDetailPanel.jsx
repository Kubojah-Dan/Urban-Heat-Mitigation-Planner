import React from 'react';
import { X, TreePine, Paintbrush, TrendingDown, Users, CheckCircle } from 'lucide-react';

export default function WardDetailPanel({
  wardId,
  detail,
  onClose,
  canopyValue,
  coolRoofValue,
  onCanopyChange,
  onCoolRoofChange
}) {
  if (!detail || !detail.ward_metrics) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '10px' }}>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)', padding: '20px', textAlign: 'center' }}>
          Loading details for Ward #{wardId}...
        </div>
      </div>
    );
  }

  const metrics = detail.ward_metrics;
  const recommendations = detail.recommendations || [];

  // ── WHAT-IF SIMULATION LOGIC ──
  const tempDrop = (canopyValue * 0.06) + (coolRoofValue * 0.04);
  const simulatedLst = metrics.LST_mean - tempDrop;
  const hviDrop = tempDrop * 0.045;
  const simulatedHvi = Math.max(0.0, metrics.hvi - hviDrop);

  // Classify HVI
  let simulatedClass = "Low";
  if (simulatedHvi >= 0.58) simulatedClass = "Extreme";
  else if (simulatedHvi >= 0.44) simulatedClass = "High";
  else if (simulatedHvi >= 0.28) simulatedClass = "Moderate";

  const isClassReduced = simulatedClass !== metrics.vulnerability_class;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%', overflowY: 'auto', paddingRight: '4px' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
        <div>
          <h2 style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text-primary)' }}>{metrics.ward_name}</h2>
          <p style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Ward #{metrics.ward_id} • {metrics.area_km2.toFixed(1)} km²</p>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'rgba(255, 255, 255, 0.06)',
            border: 'none',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            padding: '6px',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background 0.2s'
          }}
          onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)'}
          onMouseOut={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)'}
        >
          <X size={16} />
        </button>
      </div>

      {/* ── Section: What-If Simulator Widget ── */}
      <div className="cc-widget" style={{ border: '1px solid rgba(16, 185, 129, 0.2)', background: 'rgba(16, 185, 129, 0.02)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--secondary)', marginBottom: '14px' }}>
          <TrendingDown size={15} />
          <h3 style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
            What-If Simulator
          </h3>
        </div>

        {/* Sliders */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginBottom: '16px' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '6px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--text-secondary)' }}>
                <TreePine size={13} /> Tree Canopy Increase
              </span>
              <span style={{ color: '#fff', fontWeight: 600 }}>+{canopyValue}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="30"
              step="5"
              value={canopyValue}
              onChange={(e) => onCanopyChange(parseInt(e.target.value))}
            />
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '6px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--text-secondary)' }}>
                <Paintbrush size={13} /> Cool Roof Cover
              </span>
              <span style={{ color: '#fff', fontWeight: 600 }}>+{coolRoofValue}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="50"
              step="5"
              value={coolRoofValue}
              onChange={(e) => onCoolRoofChange(parseInt(e.target.value))}
            />
          </div>
        </div>

        {/* Simulated Results */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', background: 'rgba(0,0,0,0.25)', padding: '12px', borderRadius: '12px' }}>
          <div>
            <div style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '2px' }}>Projected LST</div>
            <div style={{ fontSize: '13px', fontWeight: 800, color: tempDrop > 0 ? 'var(--secondary)' : '#fff' }}>
              {metrics.LST_mean.toFixed(1)}°C {tempDrop > 0 && `→ ${simulatedLst.toFixed(1)}°C`}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '2px' }}>Risk Category</div>
            <div style={{ fontSize: '13px', fontWeight: 800, color: isClassReduced ? '#34d399' : '#fff' }}>
              {metrics.vulnerability_class} {isClassReduced && `→ ${simulatedClass}`}
            </div>
          </div>
        </div>

        {isClassReduced && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '12px', padding: '8px 12px', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '8px', border: '1px solid rgba(16, 185, 129, 0.15)' }}>
            <CheckCircle size={14} color="#10b981" />
            <span style={{ fontSize: '11px', color: '#86efac', fontWeight: 600 }}>Planning Targets Achieved!</span>
          </div>
        )}
      </div>

      {/* ── Section: Recommendations ── */}
      <div>
        <h3 style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
          Targeted Interventions
        </h3>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {recommendations.map((rec, index) => {
            let badgeBg = 'rgba(59, 130, 246, 0.08)';
            let badgeColor = '#60a5fa';
            if (rec.priority_score >= 60) {
              badgeBg = 'rgba(239, 68, 68, 0.08)';
              badgeColor = '#f87171';
            } else if (rec.priority_score >= 45) {
              badgeBg = 'rgba(245, 158, 11, 0.08)';
              badgeColor = '#fbbf24';
            }

            return (
              <div key={rec.key} className="cc-widget" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: 'var(--text-muted)' }}>RANK {index + 1}</div>
                  <span style={{ fontSize: '10px', fontWeight: 700, padding: '2px 8px', borderRadius: '9999px', background: badgeBg, color: badgeColor }}>
                    Score: {rec.priority_score}%
                  </span>
                </div>

                <h4 style={{ fontSize: '14px', color: '#fff', fontWeight: 700 }}>{rec.title}</h4>
                <p style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{rec.rationale}</p>
                
                <div style={{ display: 'flex', gap: '16px', fontSize: '10px', color: 'var(--text-muted)', borderTop: '1px solid var(--border-light)', paddingTop: '8px', marginTop: '6px' }}>
                  <div>Cost: <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{rec.cost_tier}</span></div>
                  <div>Impact: <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{rec.impact_potential}</span></div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Section: Ward Profile Metrics ── */}
      <div className="cc-widget">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary)', marginBottom: '14px' }}>
          <Users size={15} />
          <h3 style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
            Demographic & Built Profile
          </h3>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Population Density</span>
            <span style={{ fontWeight: 600, color: '#fff' }}>{metrics.pop_density_km2 ? metrics.pop_density_km2.toFixed(0) : 'N/A'} / km²</span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Literacy Rate</span>
            <span style={{ fontWeight: 600, color: '#fff' }}>{metrics.literacy_rate ? (metrics.literacy_rate * 100).toFixed(1) : 'N/A'}%</span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Child Ratio (Age 0-6)</span>
            <span style={{ fontWeight: 600, color: '#fff' }}>{metrics.child_ratio ? (metrics.child_ratio * 100).toFixed(1) : 'N/A'}%</span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Road Cover Ratio</span>
            <span style={{ fontWeight: 600, color: '#fff' }}>{metrics.road_coverage_ratio ? (metrics.road_coverage_ratio * 100).toFixed(2) : 'N/A'}%</span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Building Coverage</span>
            <span style={{ fontWeight: 600, color: '#fff' }}>{metrics.built_area_ratio ? (metrics.built_area_ratio * 100).toFixed(2) : 'N/A'}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
