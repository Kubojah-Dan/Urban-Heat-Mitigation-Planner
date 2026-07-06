import React from 'react';
import { History, Trash2, ArrowRight, Thermometer, Trees, ShieldAlert } from 'lucide-react';

export default function HistoryPanel({ simulations, onClearHistory, onSelectSimulation }) {
  return (
    <div className="fixed right-6 top-24 bottom-6 left-24 bg-zinc-900/45 backdrop-blur-2xl border border-white/10 rounded-2xl flex flex-col z-40 overflow-hidden shadow-2xl animate-fadeIn">
      {/* Absolute top glowing bar */}
      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent"></div>

      {/* Header */}
      <div className="p-5 border-b border-white/5 bg-zinc-950/40 flex justify-between items-center text-left">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <History className="w-5 h-5 text-cyan-400" />
            Simulation Run Log
          </h2>
          <p className="text-xs text-zinc-400 mt-1">
            Historical audit logs of parameter testing runs and thermodynamic impacts.
          </p>
        </div>
        {simulations.length > 0 && (
          <button
            onClick={onClearHistory}
            className="flex items-center gap-1.5 text-xs text-rose-400 hover:text-rose-300 bg-rose-500/10 hover:bg-rose-500/20 px-3 py-1.5 rounded-lg border border-rose-500/25 cursor-pointer transition-all"
          >
            <Trash2 className="w-3.5 h-3.5" /> Clear Logs
          </button>
        )}
      </div>

      {/* Body List */}
      <div className="p-6 flex-1 overflow-y-auto space-y-4" style={{ scrollbarWidth: 'none' }}>
        {simulations.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center gap-2 text-zinc-500">
            <History className="w-12 h-12 text-zinc-600 stroke-[1.5]" />
            <p className="text-sm font-medium">No simulation runs recorded yet.</p>
            <p className="text-xs">Select a ward in the sandbox or map view and click 'Run Simulation' to log results.</p>
          </div>
        ) : (
          simulations.map((sim, index) => (
            <div
              key={index}
              className="bg-zinc-950/20 border border-white/5 hover:border-white/10 rounded-xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-6 transition-all group"
            >
              {/* Left Details */}
              <div className="space-y-2 text-left">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20">
                    {sim.timestamp}
                  </span>
                  <h3 className="text-sm font-bold text-white tracking-wide">
                    {sim.cityName} • {sim.wardName}
                  </h3>
                </div>
                <p className="text-xs text-zinc-400 max-w-2xl leading-relaxed">
                  {sim.aiExplanation}
                </p>
              </div>

              {/* Right Metrics Grid */}
              <div className="flex items-center gap-6 shrink-0">
                <div className="grid grid-cols-3 gap-4 text-center">
                  {/* LST Compare */}
                  <div className="space-y-1">
                    <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-widest block">LST</span>
                    <span className="text-xs font-mono font-bold text-orange-400 flex items-center justify-center gap-1">
                      {sim.originalLst.toFixed(1)}°C <ArrowRight className="w-3 h-3 text-zinc-600" /> {sim.newLst.toFixed(1)}°C
                    </span>
                  </div>

                  {/* Canopy Compare */}
                  <div className="space-y-1">
                    <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-widest block">Canopy</span>
                    <span className="text-xs font-mono font-bold text-emerald-400 flex items-center justify-center gap-1">
                      {sim.originalCanopy.toFixed(0)}% <ArrowRight className="w-3 h-3 text-zinc-600" /> {sim.newCanopy.toFixed(0)}%
                    </span>
                  </div>

                  {/* HVI Compare */}
                  <div className="space-y-1">
                    <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-widest block">HVI Score</span>
                    <span className="text-xs font-mono font-bold text-rose-400 flex items-center justify-center gap-1">
                      {sim.originalHvi.toFixed(2)} <ArrowRight className="w-3 h-3 text-zinc-600" /> {sim.newHvi.toFixed(2)}
                    </span>
                  </div>
                </div>

                {/* Inspect Button */}
                <button
                  onClick={() => onSelectSimulation(sim)}
                  className="text-xs font-bold text-zinc-300 hover:text-white bg-white/5 hover:bg-white/10 px-3.5 py-2 rounded-lg border border-white/5 cursor-pointer transition-all duration-200"
                >
                  Load State
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
