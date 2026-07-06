import React, { useState, useEffect } from 'react';
import { Thermometer, Trees, Users, AlertTriangle, ShieldCheck, RefreshCw } from 'lucide-react';

export default function Inspector({
  selectedWard,
  onRunSimulation,
  isSimulating,
  simulationResult,
  onClearSimulation,
}) {
  const [addedCanopy, setAddedCanopy] = useState(5);
  const [addedCoolRoofs, setAddedCoolRoofs] = useState(15);
  const [activeChip, setActiveChip] = useState(null);

  // Sync sliders back when active ward changes
  useEffect(() => {
    setAddedCanopy(5);
    setAddedCoolRoofs(15);
    setActiveChip(null);
  }, [selectedWard]);

  // Adjust sliders if user clicks a recommended intervention chip
  const handleChipClick = (chip) => {
    setActiveChip(chip === activeChip ? null : chip);
    if (chip.toLowerCase().includes('cool roof')) {
      setAddedCoolRoofs(30);
    } else if (chip.toLowerCase().includes('forest') || chip.toLowerCase().includes('canopy')) {
      setAddedCanopy(15);
    } else if (chip.toLowerCase().includes('pave') || chip.toLowerCase().includes('reflect')) {
      setAddedCanopy(8);
      setAddedCoolRoofs(10);
    }
  };

  // Map fields for selected ward
  const name = selectedWard.ward_name;
  const coords = [
    selectedWard.latitude ? parseFloat(selectedWard.latitude).toFixed(3) : '23.023',
    selectedWard.longitude ? parseFloat(selectedWard.longitude).toFixed(3) : '72.571'
  ];
  
  // Map index from 0-1 scale to 1-10 scale
  const baseHvi = (selectedWard.hvi || 0.5) * 10.0;
  const baseLst = selectedWard.LST_mean || 38.0;
  const baseCanopy = Math.round((selectedWard.ndvi_mean || 0.1) * 100);
  const basePopDensity = Math.round((selectedWard.pop_density_km2 || 10000) / 1000.0);

  const currentHvi = simulationResult ? (simulationResult.newHvi * 10.0) : baseHvi;
  const currentLst = simulationResult ? simulationResult.newLst : baseLst;
  const currentCanopy = simulationResult ? simulationResult.newCanopy : baseCanopy;

  // Percentage calculations for SVG Circle
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const hviPercent = (currentHvi / 10) * 100;
  const strokeDashoffset = circumference - (hviPercent / 100) * circumference;

  // Recommended strategies (pre-loaded or from recommendations)
  const chips = [
    'Cool Roofs Coating',
    'Urban Canopy Forest',
    'Reflective Paving'
  ];

  return (
    <aside className="fixed right-6 top-24 bottom-6 w-[400px] bg-zinc-900/70 backdrop-blur-2xl border border-white/10 rounded-2xl flex flex-col z-40 overflow-hidden shadow-2xl">
      {/* Absolute top glowing bar */}
      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent"></div>

      {/* Header Info */}
      <div className="p-5 border-b border-white/5 bg-zinc-950/30">
        <h2 className="text-lg font-bold text-white flex items-center justify-between">
          <span className="truncate">Ward: {name}</span>
          <span className="font-mono text-xs text-zinc-400 bg-white/5 px-2 py-0.5 rounded border border-white/5 whitespace-nowrap">
            [{coords.join(', ')}]
          </span>
        </h2>
      </div>

      {/* Main Body */}
      <div className="p-5 flex-1 flex flex-col gap-5 overflow-y-auto" style={{ scrollbarWidth: 'none' }}>
        
        {/* Scenario Status Banner */}
        {simulationResult && (
          <div className="bg-cyan-500/10 border border-cyan-500/30 rounded-xl p-3 flex items-center gap-2.5 animate-pulse">
            <ShieldCheck className="w-5 h-5 text-cyan-400 shrink-0" />
            <div className="text-left">
              <div className="text-[11px] font-bold text-cyan-400 uppercase tracking-widest font-sans">
                Active Simulation Layer
              </div>
              <div className="text-[10px] text-zinc-300">
                LST dropped by <span className="text-cyan-400 font-bold">-{simulationResult.temperatureDrop}°C</span>
              </div>
            </div>
            <button
              onClick={onClearSimulation}
              className="ml-auto bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 p-1.5 rounded-lg border border-cyan-500/20 transition-all cursor-pointer"
              title="Reset Simulation"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Vulnerability Index Circle Gauge */}
        <div className="flex flex-col items-center justify-center p-4 bg-zinc-950/40 rounded-xl border border-white/5 relative">
          <span className="font-sans text-[10px] font-bold uppercase tracking-widest text-zinc-400 mb-3 select-none">
            Vulnerability Index
          </span>
          <div className="relative w-32 h-32 flex items-center justify-center">
            {/* SVG Ring Gauge */}
            <svg className="w-full h-full transform -rotate-90 absolute" viewBox="0 0 100 100">
              <circle
                cx="50"
                cy="50"
                fill="none"
                r={radius}
                stroke="rgba(255,255,255,0.06)"
                strokeWidth="8"
              ></circle>
              <circle
                className="transition-all duration-1000 ease-out"
                cx="50"
                cy="50"
                fill="none"
                r={radius}
                stroke={currentHvi >= 8.0 ? '#f43f5e' : currentHvi >= 6.0 ? '#fb923c' : '#2dd4bf'}
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeWidth="8"
                strokeLinecap="round"
                style={{
                  filter: `drop-shadow(0 0 6px ${currentHvi >= 8.0 ? 'rgba(244, 63, 94, 0.6)' : currentHvi >= 6.0 ? 'rgba(251, 146, 60, 0.6)' : 'rgba(45, 212, 191, 0.6)'})`,
                }}
              ></circle>
            </svg>
            <div className="text-center z-10 flex flex-col items-center">
              <span
                className={`font-mono font-black text-3.5xl transition-colors duration-500 tracking-tighter ${
                  currentHvi >= 8.0 ? 'text-rose-400' : currentHvi >= 6.0 ? 'text-orange-400' : 'text-teal-400'
                }`}
              >
                {currentHvi.toFixed(1)}
              </span>
              <span className="font-mono text-[9px] uppercase tracking-widest text-zinc-500 mt-0.5">
                /10 HVI
              </span>
            </div>
          </div>
        </div>

        {/* Telemetry Stats Grid */}
        <div className="grid grid-cols-3 gap-2">
          {/* LST Card */}
          <div className="bg-zinc-950/30 p-3 rounded-xl border border-white/5 flex flex-col items-center justify-center transition-all duration-300">
            <Thermometer className="w-4 h-4 text-orange-400 mb-1" />
            <span className="font-sans text-[9px] font-bold uppercase tracking-wider text-zinc-500">
              LST
            </span>
            <span className="font-mono text-xs font-bold text-white mt-1">
              {currentLst.toFixed(1)}°C
            </span>
          </div>

          {/* Canopy Card */}
          <div className="bg-zinc-950/30 p-3 rounded-xl border border-white/5 flex flex-col items-center justify-center transition-all duration-300">
            <Trees className="w-4 h-4 text-emerald-400 mb-1" />
            <span className="font-sans text-[9px] font-bold uppercase tracking-wider text-zinc-500">
              Canopy
            </span>
            <span className="font-mono text-xs font-bold text-white mt-1">
              {currentCanopy}%
            </span>
          </div>

          {/* Density Card */}
          <div className="bg-zinc-950/30 p-3 rounded-xl border border-white/5 flex flex-col items-center justify-center transition-all duration-300">
            <Users className="w-4 h-4 text-cyan-400 mb-1" />
            <span className="font-sans text-[9px] font-bold uppercase tracking-wider text-zinc-500">
              Density
            </span>
            <span className="font-mono text-xs font-bold text-white mt-1">
              {basePopDensity}k/km²
            </span>
          </div>
        </div>

        {/* What-If Planning Simulator Form */}
        <div className="bg-zinc-950/40 p-4 rounded-xl border border-white/5 space-y-4 text-left">
          <div className="flex items-center gap-1.5 border-b border-white/5 pb-2">
            <AlertTriangle className="w-4 h-4 text-cyan-400" />
            <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-200">
              What-If Scenario Sandbox
            </h3>
          </div>

          <div className="space-y-3.5">
            {/* Added Canopy slider */}
            <div>
              <div className="flex justify-between mb-1">
                <label className="text-[10px] text-zinc-400">Add Tree Canopy Cover</label>
                <span className="font-mono text-xs font-bold text-cyan-400">+{addedCanopy}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="20"
                step="1"
                value={addedCanopy}
                onChange={(e) => setAddedCanopy(Number(e.target.value))}
                className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
              />
            </div>

            {/* Added Cool Roofs slider */}
            <div>
              <div className="flex justify-between mb-1">
                <label className="text-[10px] text-zinc-400">Add Cool Roof Coatings</label>
                <span className="font-mono text-xs font-bold text-orange-400">+{addedCoolRoofs}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="50"
                step="1"
                value={addedCoolRoofs}
                onChange={(e) => setAddedCoolRoofs(Number(e.target.value))}
                className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-orange-400"
              />
            </div>

            {/* Run Button */}
            <button
              onClick={() => onRunSimulation(addedCanopy, addedCoolRoofs)}
              disabled={isSimulating}
              className="w-full py-2.5 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white font-bold text-xs cursor-pointer shadow-[0_0_15px_rgba(6,182,212,0.3)] transition-all flex items-center justify-center gap-1.5"
            >
              {isSimulating ? 'Processing...' : 'Run Simulation'}
            </button>
          </div>
        </div>

        {/* Targeted Interventions Section */}
        <div className="space-y-2.5 text-left">
          <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
            Recommended Mitigations
          </span>
          <div className="flex flex-wrap gap-2">
            {chips.map((chip) => {
              const isSelected = activeChip === chip;
              return (
                <button
                  key={chip}
                  onClick={() => handleChipClick(chip)}
                  className={`text-[10px] font-semibold px-2.5 py-1.5 rounded-full border transition-all duration-300 cursor-pointer ${
                    isSelected
                      ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50 shadow-[0_0_8px_rgba(6,182,212,0.25)]'
                      : 'bg-white/5 text-zinc-400 border-white/5 hover:border-white/10 hover:text-zinc-200'
                  }`}
                >
                  {chip}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </aside>
  );
}
