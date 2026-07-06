import React, { useState } from 'react';
import { FlaskConical, Thermometer, Play, Trees } from 'lucide-react';

export default function SimulationSandbox({ wards, cityName, onActivateWardSimulation }) {
  const [globalCanopy, setGlobalCanopy] = useState(10);
  const [globalCoolRoofs, setGlobalCoolRoofs] = useState(25);

  // Map our live ward fields
  const mappedWards = wards.map(w => ({
    id: String(w.ward_id),
    name: w.ward_name,
    lst: w.LST_mean || 38.0,
    popDensity: (w.pop_density_km2 || 10000) / 1000.0, // scale to matches mock ROI calculation
    canopy: Math.round((w.ndvi_mean || 0.1) * 100),
    hvi: w.hvi || 0.5,
    raw_ward: w
  }));

  // Calculate cooling potential based on global inputs
  // 1% canopy = 0.22°C drop. 1% cool roofs = 0.12°C drop (matching UI sandbox formulas)
  const tempDrop = (globalCanopy * 0.22) + (globalCoolRoofs * 0.12);

  // Calculate ROI and sort
  const simulatedWards = mappedWards.map((ward) => {
    const originalLst = ward.lst;
    const newLst = Math.max(25, originalLst - tempDrop);
    const originalHvi = ward.hvi;
    
    // Scale HVI reduction based on index format (our index is 0 to 1, mock was 1 to 10)
    // Scale HVI drop appropriately
    const hviReduction = ((globalCanopy * 0.15) + (globalCoolRoofs * 0.05)) / 10.0;
    const newHvi = Math.max(0.1, originalHvi - hviReduction);
    
    // Impact Score = temp drop * population density
    const roiScore = tempDrop * ward.popDensity;

    return {
      ...ward,
      newLst,
      newHvi,
      roiScore,
    };
  }).sort((a, b) => b.roiScore - a.roiScore);

  return (
    <div className="fixed right-6 top-24 bottom-6 left-24 bg-zinc-900/45 backdrop-blur-2xl border border-white/10 rounded-2xl flex flex-col z-40 overflow-hidden shadow-2xl animate-fadeIn">
      {/* Absolute top glowing bar */}
      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent"></div>

      {/* Header */}
      <div className="p-5 border-b border-white/5 bg-zinc-950/40 flex justify-between items-center text-left">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <FlaskConical className="w-5 h-5 text-cyan-400 animate-pulse" />
            Ecological Simulation Sandbox: {cityName} Grid
          </h2>
          <p className="text-xs text-zinc-400 mt-1">
            Compare thermodynamic response rates and calculate overall social-ecological Return on Investment (ROI) across wards.
          </p>
        </div>
      </div>

      <div className="p-6 flex-1 grid grid-cols-3 gap-6 overflow-hidden">
        {/* Left Panel: Global Input Sliders */}
        <div className="bg-zinc-950/20 p-5 rounded-xl border border-white/5 flex flex-col justify-between text-left h-full">
          <div className="space-y-6">
            <div className="flex items-center gap-1.5 border-b border-white/5 pb-2">
              <FlaskConical className="w-4.5 h-4.5 text-cyan-400" />
              <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-200">
                Sandbox Parameters
              </h3>
            </div>

            <div className="space-y-4">
              {/* Canopy slider */}
              <div>
                <div className="flex justify-between mb-1.5">
                  <label className="text-[11px] text-zinc-400 font-sans">Global Canopy Increase</label>
                  <span className="font-mono text-xs font-bold text-cyan-400">
                    +{globalCanopy}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="20"
                  step="1"
                  value={globalCanopy}
                  onChange={(e) => setGlobalCanopy(Number(e.target.value))}
                  className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                />
              </div>

              {/* Cool Roofs slider */}
              <div>
                <div className="flex justify-between mb-1.5">
                  <label className="text-[11px] text-zinc-400 font-sans">Global Cool Roof Cover</label>
                  <span className="font-mono text-xs font-bold text-orange-400">
                    +{globalCoolRoofs}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="50"
                  step="1"
                  value={globalCoolRoofs}
                  onChange={(e) => setGlobalCoolRoofs(Number(e.target.value))}
                  className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-orange-400"
                />
              </div>
            </div>

            {/* Simulated cooling yield badge */}
            <div className="bg-white/5 border border-white/5 rounded-xl p-4 space-y-2">
              <div className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider">
                Simulated Cool Air Delta
              </div>
              <div className="flex items-center gap-2">
                <Thermometer className="w-6 h-6 text-cyan-400" />
                <span className="text-2xl font-black text-cyan-400 glow-text-cyan font-mono">
                  -{tempDrop.toFixed(2)}°C
                </span>
              </div>
              <p className="text-[10px] text-zinc-500 leading-relaxed">
                Calculated air cooling yield across Ahmedabad due to evapotranspiration and increased surface albedo reflectance.
              </p>
            </div>
          </div>

          <div className="text-[10px] text-zinc-500 italic">
            *Table on the right lists wards sorted by social-ecological ROI.
          </div>
        </div>

        {/* Right Panel: Scrollable Results Table */}
        <div className="col-span-2 bg-zinc-950/30 rounded-xl border border-white/5 overflow-hidden flex flex-col h-full">
          {/* Table Header */}
          <div className="grid grid-cols-6 gap-4 bg-zinc-950/40 p-4 border-b border-white/5 text-[10px] font-bold uppercase tracking-wider text-zinc-400 text-left font-mono">
            <span className="col-span-2">Ward Name</span>
            <span>Base LST</span>
            <span>Sim LST</span>
            <span>Sim ROI</span>
            <span className="text-right">Action</span>
          </div>

          {/* Table Rows */}
          <div className="flex-1 overflow-y-auto divide-y divide-white/5" style={{ scrollbarWidth: 'none' }}>
            {simulatedWards.map((ward) => (
              <div
                key={ward.id}
                className="grid grid-cols-6 gap-4 p-4 items-center text-xs text-left text-zinc-300 hover:bg-white/2 transition-colors"
              >
                <div className="col-span-2 flex flex-col">
                  <span className="font-bold text-white truncate">{ward.name}</span>
                  <span className="text-[9px] text-zinc-500 font-mono">ID: {ward.id}</span>
                </div>
                <span className="font-mono text-zinc-400">{ward.lst.toFixed(1)}°C</span>
                <span className="font-mono text-cyan-400 font-bold">
                  {ward.newLst.toFixed(1)}°C
                </span>
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_4px_#22d3ee]"></span>
                  <span className="font-mono font-bold text-zinc-200">
                    {ward.roiScore.toFixed(0)} pts
                  </span>
                </div>
                <div className="text-right">
                  <button
                    onClick={() => onActivateWardSimulation(ward.raw_ward, globalCanopy, globalCoolRoofs)}
                    className="inline-flex items-center justify-center p-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/25 border border-cyan-500/20 hover:border-cyan-500/40 text-cyan-400 transition-all cursor-pointer"
                    title="Load simulation parameters to Command center"
                  >
                    <Play className="w-3.5 h-3.5 fill-cyan-400/20" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
