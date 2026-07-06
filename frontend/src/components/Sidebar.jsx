import React from 'react';
import { LayoutDashboard, BarChart3, Layers, FlaskConical, History } from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab, avatarUrl }) {
  const menuItems = [
    { id: 'command', label: 'Command', icon: LayoutDashboard },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'layers', label: 'Layers', icon: Layers },
    { id: 'simulation_list', label: 'Simulation', icon: FlaskConical },
    { id: 'history', label: 'History', icon: History },
  ];

  return (
    <nav className="fixed left-0 top-1/2 -translate-y-1/2 z-[9999] flex flex-col items-center py-4 w-16 bg-zinc-950/80 backdrop-blur-2xl rounded-full ml-6 border border-white/10 shadow-2xl">
      <div className="flex flex-col gap-6 my-4">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`p-3 rounded-xl transition-all duration-300 flex flex-col items-center gap-1 group relative cursor-pointer ${
                isActive
                  ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                  : 'text-zinc-400 hover:bg-white/5 hover:text-cyan-400'
              }`}
            >
              <Icon className="w-6 h-6" />
              <span className="font-sans text-[10px] uppercase font-bold tracking-widest absolute left-14 opacity-0 group-hover:opacity-100 bg-zinc-900 text-white px-2.5 py-1 rounded border border-white/10 pointer-events-none transition-all duration-300 whitespace-nowrap z-50 shadow-xl">
                {item.label}
              </span>
            </button>
          );
        })}
      </div>
      <div className="mt-auto mb-4 flex flex-col items-center group relative">
        <div className="w-10 h-10 rounded-full border border-white/20 overflow-hidden ring-1 ring-white/10 shadow-lg">
          <img
            className="w-full h-full object-cover"
            src={avatarUrl}
            alt="Operator"
            referrerPolicy="no-referrer"
          />
        </div>
        <span className="font-sans text-[10px] uppercase font-bold tracking-widest absolute left-14 opacity-0 group-hover:opacity-100 bg-zinc-900 text-cyan-400 px-2.5 py-1 rounded border border-cyan-500/30 pointer-events-none transition-all duration-300 whitespace-nowrap z-50 shadow-xl">
          System: Active
        </span>
      </div>
    </nav>
  );
}
