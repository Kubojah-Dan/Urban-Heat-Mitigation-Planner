import React from 'react';
import { Bell, Settings, User, Sparkles } from 'lucide-react';

export default function Header({
  cities,
  selectedCityId,
  setSelectedCityId,
  avgLst,
  highRiskCount,
  setShowChat,
  showChat,
}) {
  return (
    <header className="fixed top-0 left-0 right-0 z-[9999] flex justify-between items-center px-6 h-16 bg-zinc-950/70 backdrop-blur-xl border border-white/10 shadow-2xl rounded-full mt-4 mx-6">
      {/* Brand & Global Stats */}
      <div className="flex items-center gap-4">
        <span className="text-xl font-bold text-cyan-400 tracking-tighter glow-text-cyan flex items-center gap-2 select-none">
          UrbanCool AI
        </span>
        <div className="h-5 w-px bg-white/15 mx-2"></div>
        <div className="flex gap-5">
          {/* Avg LST HUD */}
          <div className="flex items-center gap-2 bg-white/5 px-3 py-1 rounded-full border border-white/5">
            <div className="w-2.5 h-2.5 rounded-full bg-orange-500 shadow-[0_0_8px_#ec6a06]"></div>
            <span className="font-mono text-xs text-zinc-300">
              Avg LST: <span className="text-orange-400 font-bold">{avgLst ? avgLst.toFixed(1) : '39.0'}°C</span>
            </span>
          </div>

          {/* High Risk HUD */}
          <div className="flex items-center gap-2 bg-white/5 px-3 py-1 rounded-full border border-white/5">
            <div className="w-2.5 h-2.5 rounded-full bg-red-400 shadow-[0_0_8px_rgba(239,68,68,0.8)]"></div>
            <span className="font-mono text-xs text-zinc-300">
              High Risk Wards: <span className="text-red-400 font-bold">{highRiskCount}</span>
            </span>
          </div>
        </div>
      </div>

      {/* City Toggle Nav */}
      <nav className="flex gap-1 bg-white/5 p-1 rounded-full border border-white/5">
        {cities.map((city) => {
          const isActive = selectedCityId === city.id;
          return (
            <button
              key={city.id}
              onClick={() => setSelectedCityId(city.id)}
              className={`px-4 py-1.5 rounded-full text-xs font-semibold tracking-wider transition-all duration-300 uppercase cursor-pointer ${
                isActive
                  ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 font-bold'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/5'
              }`}
            >
              {city.name}
            </button>
          );
        })}
      </nav>

      {/* Quick Action Utilities */}
      <div className="flex gap-3">
        <button
          onClick={() => setShowChat(!showChat)}
          className={`w-9 h-9 rounded-full transition-all duration-300 flex items-center justify-center cursor-pointer relative ${
            showChat
              ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 shadow-[0_0_8px_rgba(6,182,212,0.4)]'
              : 'text-zinc-400 hover:bg-white/5 hover:text-cyan-400 border border-transparent'
          }`}
          title="AI Assistant Chat"
        >
          <User className="w-4.5 h-4.5" />
          {!showChat && (
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-cyan-400 rounded-full animate-pulse shadow-[0_0_4px_#22d3ee]"></span>
          )}
        </button>

        <button className="w-9 h-9 rounded-full text-zinc-400 hover:bg-white/5 hover:text-cyan-400 transition-all duration-300 flex items-center justify-center cursor-pointer border border-transparent">
          <Bell className="w-4.5 h-4.5" />
        </button>

        <button className="w-9 h-9 rounded-full text-zinc-400 hover:bg-white/5 hover:text-cyan-400 transition-all duration-300 flex items-center justify-center cursor-pointer border border-transparent">
          <Settings className="w-4.5 h-4.5" />
        </button>
      </div>
    </header>
  );
}
