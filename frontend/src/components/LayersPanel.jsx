import React from 'react';
import { Layers, Thermometer, Trees, Users, AlertTriangle, CheckCircle2 } from 'lucide-react';

export default function LayersPanel({ activeLayer, setActiveLayer, setActiveTab }) {
  const layers = [
    {
      id: 'thermal',
      name: 'LST Thermal Plume Heatmap',
      icon: Thermometer,
      color: 'from-orange-500 to-red-500 text-orange-400 border-orange-500/30 bg-orange-500/5',
      glow: 'shadow-[0_0_15px_rgba(249,115,22,0.15)]',
      description: 'Visualizes high-resolution Land Surface Temperatures (LST). Hot anomalies and concrete heat-sinks are flagged in vibrant crimson.',
      metric: 'Range: 30°C to 50°C LST'
    },
    {
      id: 'canopy',
      name: 'Eco-Canopy Vegetation Density',
      icon: Trees,
      color: 'from-emerald-500 to-teal-500 text-emerald-400 border-emerald-500/30 bg-emerald-500/5',
      glow: 'shadow-[0_0_15px_rgba(16,185,129,0.15)]',
      description: 'Maps the vegetative tree canopy density (NDVI). Crucial for identifying severe concrete corridors and open soil drying.',
      metric: 'Range: 0% to 30% vegetation'
    },
    {
      id: 'population',
      name: 'Population Demographics Density',
      icon: Users,
      color: 'from-cyan-500 to-blue-500 text-cyan-400 border-cyan-500/30 bg-cyan-500/5',
      glow: 'shadow-[0_0_15px_rgba(6,182,212,0.15)]',
      description: 'Identifies residential and commercial core sectors, showing human density hotspots vulnerable to extreme heat waves.',
      metric: 'Range: 0 to 50k residents/km²'
    },
    {
      id: 'hvi',
      name: 'Heat Vulnerability Index (HVI) hotspots',
      icon: AlertTriangle,
      color: 'from-rose-500 to-pink-500 text-rose-400 border-rose-500/30 bg-rose-500/5',
      glow: 'shadow-[0_0_15px_rgba(244,63,94,0.15)]',
      description: 'Synthesizes LST, density, and canopy cover to calculate overall health and thermal stress risk. Severe risk regions flash red.',
      metric: 'Range: 0.1 to 1.0 HVI Index'
    }
  ];

  const handleActivateLayer = (layerId) => {
    setActiveLayer(layerId);
    setActiveTab('command'); // Auto transition back to map to see it instantly!
  };

  return (
    <div className="fixed right-6 top-24 bottom-6 left-24 bg-zinc-900/45 backdrop-blur-2xl border border-white/10 rounded-2xl flex flex-col z-40 overflow-hidden shadow-2xl animate-fadeIn">
      {/* Absolute top glowing bar */}
      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent"></div>

      {/* Header */}
      <div className="p-5 border-b border-white/5 bg-zinc-950/40 flex justify-between items-center text-left">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Layers className="w-5 h-5 text-cyan-400" />
            GIS Data Layer Selector
          </h2>
          <p className="text-xs text-zinc-400 mt-1">
            Toggle global map overlays to audit municipal heat islands and cooling targets.
          </p>
        </div>
      </div>

      {/* Grid List */}
      <div className="p-6 flex-1 grid grid-cols-2 gap-4 overflow-y-auto" style={{ scrollbarWidth: 'none' }}>
        {layers.map((layer) => {
          const Icon = layer.icon;
          const isActive = activeLayer === layer.id;
          return (
            <div
              key={layer.id}
              className={`p-5 rounded-xl border flex flex-col justify-between transition-all duration-300 relative text-left group ${layer.glow} ${
                isActive
                  ? 'border-cyan-500/50 bg-cyan-500/5'
                  : 'border-white/5 bg-zinc-950/20 hover:border-white/15 hover:bg-zinc-950/40'
              }`}
            >
              {/* Active Badge */}
              {isActive && (
                <div className="absolute top-4 right-4 flex items-center gap-1 text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20 text-[9px] font-bold font-mono tracking-widest uppercase select-none">
                  <CheckCircle2 className="w-3.5 h-3.5" /> ACTIVE
                </div>
              )}

              {/* Icon & Name */}
              <div className="space-y-3">
                <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${layer.color} border flex items-center justify-center shrink-0`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-sm font-bold text-white tracking-wide">
                    {layer.name}
                  </h3>
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    {layer.description}
                  </p>
                </div>
              </div>

              {/* Action Button & Range HUD */}
              <div className="mt-6 pt-4 border-t border-white/5 flex justify-between items-center">
                <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">
                  {layer.metric}
                </span>
                {!isActive && (
                  <button
                    onClick={() => handleActivateLayer(layer.id)}
                    className="text-xs font-bold text-cyan-400 hover:text-cyan-300 bg-cyan-500/10 hover:bg-cyan-500/20 px-3 py-1.5 rounded-lg border border-cyan-500/25 cursor-pointer transition-all duration-200"
                  >
                    Load Layer
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
