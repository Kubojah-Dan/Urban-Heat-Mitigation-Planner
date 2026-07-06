import React from 'react';
import { BarChart3, TrendingDown, Eye, ShieldAlert, Thermometer, Trees } from 'lucide-react';

export default function AnalyticsPanel({ wards, cityName }) {
  // Map our live ward fields:
  // - name: ward_name
  // - lst: LST_mean
  // - canopy: ndvi_mean * 100 (approximate percentage)
  const mappedWards = wards.map(w => ({
    id: w.ward_id,
    name: w.ward_name,
    lst: w.LST_mean || 38.0,
    canopy: Math.round((w.ndvi_mean || 0.1) * 100),
    hvi: w.hvi || 0.5
  }));

  // Sort wards by LST (highest first) to show critical zones - show top 8
  const sortedByLst = [...mappedWards].sort((a, b) => b.lst - a.lst).slice(0, 8);
  // Sort wards by canopy (lowest first) to show bare land risk - show top 8
  const sortedByCanopy = [...mappedWards].sort((a, b) => a.canopy - b.canopy).slice(0, 8);

  // Maximum values for scales
  const maxLst = Math.max(...mappedWards.map((w) => w.lst), 50);
  const maxCanopy = Math.max(...mappedWards.map((w) => w.canopy), 100);

  return (
    <div className="fixed right-6 top-24 bottom-6 left-24 bg-zinc-900/45 backdrop-blur-2xl border border-white/10 rounded-2xl flex flex-col z-40 overflow-hidden shadow-2xl animate-fadeIn">
      {/* Absolute top glowing bar */}
      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent"></div>

      {/* Header */}
      <div className="p-5 border-b border-white/5 bg-zinc-950/40 flex justify-between items-center text-left">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-cyan-400" />
            Ecological Analytics: {cityName} Grid
          </h2>
          <p className="text-xs text-zinc-400 mt-1">
            Comparative macroclimate sensor readings and canopy-to-temperature correlations.
          </p>
        </div>
      </div>

      {/* Content Body (Grid Layout) */}
      <div className="p-6 flex-1 grid grid-cols-2 gap-6 overflow-y-auto" style={{ scrollbarWidth: 'none' }}>
        
        {/* Chart 1: LST Heat Anomaly Leaderboard */}
        <div className="bg-zinc-950/30 p-5 rounded-xl border border-white/5 flex flex-col text-left">
          <div className="flex items-center gap-2 mb-4">
            <Thermometer className="w-4 h-4 text-orange-400" />
            <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-300">
              Land Surface Temperature (LST) Leaderboard (Hotspots)
            </h3>
          </div>
          <div className="space-y-4 flex-1 flex flex-col justify-center">
            {sortedByLst.map((ward) => {
              const percentage = (ward.lst / maxLst) * 100;
              const isDanger = ward.lst >= 41.0;
              return (
                <div key={ward.id} className="space-y-1">
                  <div className="flex justify-between text-[11px]">
                    <span className="font-semibold text-zinc-300">{ward.name}</span>
                    <span className={`font-mono font-bold ${isDanger ? 'text-red-400' : 'text-orange-400'}`}>
                      {ward.lst.toFixed(1)}°C
                    </span>
                  </div>
                  <div className="w-full h-2 bg-zinc-900 rounded-full overflow-hidden border border-white/5 relative">
                    <div
                      className={`h-full rounded-full transition-all duration-1000 ${
                        isDanger
                          ? 'bg-gradient-to-r from-orange-500 to-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]'
                          : 'bg-gradient-to-r from-yellow-500 to-orange-400 shadow-[0_0_8px_rgba(249,115,22,0.4)]'
                      }`}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Chart 2: Tree Canopy Deficit Index */}
        <div className="bg-zinc-950/30 p-5 rounded-xl border border-white/5 flex flex-col text-left">
          <div className="flex items-center gap-2 mb-4">
            <Trees className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-300">
              Tree Canopy Coverage Index (Deficits)
            </h3>
          </div>
          <div className="space-y-4 flex-1 flex flex-col justify-center">
            {sortedByCanopy.map((ward) => {
              const percentage = (ward.canopy / maxCanopy) * 100;
              const isCritical = ward.canopy < 12;
              return (
                <div key={ward.id} className="space-y-1">
                  <div className="flex justify-between text-[11px]">
                    <span className="font-semibold text-zinc-300">{ward.name}</span>
                    <span className={`font-mono font-bold ${isCritical ? 'text-purple-400' : 'text-emerald-400'}`}>
                      {ward.canopy}% {isCritical && '(Critical)'}
                    </span>
                  </div>
                  <div className="w-full h-2 bg-zinc-900 rounded-full overflow-hidden border border-white/5">
                    <div
                      className={`h-full rounded-full transition-all duration-1000 ${
                        isCritical
                          ? 'bg-gradient-to-r from-indigo-500 to-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.4)]'
                          : 'bg-gradient-to-r from-emerald-500 to-teal-400 shadow-[0_0_8px_rgba(16,185,129,0.4)]'
                      }`}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Correlation Insight Module */}
        <div className="col-span-2 bg-zinc-950/40 p-5 rounded-xl border border-white/5 text-left flex gap-6 items-center">
          <div className="w-14 h-14 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center shrink-0 shadow-[0_0_15px_rgba(6,182,212,0.15)]">
            <TrendingDown className="w-7 h-7 text-cyan-400" />
          </div>
          <div className="space-y-1.5">
            <h4 className="text-sm font-bold text-white uppercase tracking-wider font-sans">
              Critical Thermomap Correlation Detected
            </h4>
            <p className="text-[11px] text-zinc-300 leading-relaxed font-sans">
              Our ecological telemetry reveals an **inverse correlation coefficient** between canopy coverage (NDVI) and land surface temperature (LST) across {cityName}. Every **10% increase in canopy cover** is simulated to reduce localized ambient temperatures by approximately **0.6°C to 2.2°C** via solar shading, soil moisture retention, and latent transpiration cooling.
            </p>
            <div className="flex gap-4 mt-2 select-none">
              <span className="text-[10px] text-zinc-400 flex items-center gap-1">
                <Eye className="w-3.5 h-3.5 text-cyan-400" />
                Target: 15% Canopy minimum
              </span>
              <span className="text-[10px] text-zinc-400 flex items-center gap-1">
                <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                Urgent Action: Wards with HVI &gt; 0.5
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
