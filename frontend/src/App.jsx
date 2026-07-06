import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import MapView from './components/MapView';
import Inspector from './components/Inspector';
import AnalyticsPanel from './components/AnalyticsPanel';
import LayersPanel from './components/LayersPanel';
import SimulationSandbox from './components/SimulationSandbox';
import HistoryPanel from './components/HistoryPanel';
import AIChatModal from './components/AIChatModal';
import useWardData from './hooks/useWardData';
import { Thermometer, Sparkles } from 'lucide-react';

export default function App() {
  const {
    geoJsonData,
    citySummary,
    selectedWardDetail,
    loading,
    error,
    fetchWardDetail,
    runPredictiveSimulation
  } = useWardData();

  // Navigation state matching design repo tabs
  const [activeTab, setActiveTab] = useState('command');
  const [selectedCityId, setSelectedCityId] = useState('ahmedabad');
  const [selectedWardId, setSelectedWardId] = useState(null);
  const [activeLayer, setActiveLayer] = useState('thermal');
  const [showChat, setShowChat] = useState(false);

  // Scenario Simulator States (Inspector Sandbox runs)
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulationResult, setSimulationResult] = useState(null);
  const [simulationHistory, setSimulationHistory] = useState([]);

  // Meteorology Predictor States
  const [predTemp, setPredTemp] = useState(38);
  const [predHumidity, setPredHumidity] = useState(45);
  const [isPredicting, setIsPredicting] = useState(false);
  const [predictedLstMap, setPredictedLstMap] = useState(null);

  // Auto-select first ward on data load
  useEffect(() => {
    if (geoJsonData && geoJsonData.features && geoJsonData.features.length > 0 && !selectedWardId) {
      setSelectedWardId(geoJsonData.features[0].properties.ward_id);
    }
  }, [geoJsonData]);

  // Sync ward detail when selection changes
  useEffect(() => {
    if (selectedWardId) {
      fetchWardDetail(selectedWardId);
      // Clear current simulation run if we switch wards to keep sandbox fresh
      setSimulationResult(null);
    }
  }, [selectedWardId, fetchWardDetail]);

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center flex-col gap-4 bg-zinc-950 text-zinc-400">
        <div className="w-10 h-10 border-4 border-cyan-500/10 border-t-cyan-400 rounded-full animate-spin"></div>
        <p className="text-sm font-mono tracking-widest text-cyan-400 animate-pulse">BOOTING GIS SIMULATION PORTAL...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen w-screen items-center justify-center flex-col gap-4 bg-zinc-950 text-center p-6">
        <h2 className="text-red-400 text-xl font-bold font-mono tracking-wider">CONNECTION INTERFERENCE</h2>
        <p className="text-zinc-500 text-xs max-w-sm leading-relaxed">
          Could not establish connection to the FastAPI backend. Check that your local web server is running on port 8000.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 px-5 py-2 rounded-lg text-xs font-bold hover:bg-cyan-500/20 transition-all cursor-pointer"
        >
          RETRY LINK
        </button>
      </div>
    );
  }

  // Cities mock dataset
  const cities = [{ id: 'ahmedabad', name: 'Ahmedabad' }];

  // Parse all ward metrics from properties
  const wards = geoJsonData ? geoJsonData.features.map(f => f.properties) : [];

  // Compute HUD statistics
  const avgLst = wards.reduce((acc, w) => acc + (w.LST_mean || 38.0), 0) / (wards.length || 1);
  const highRiskCount = wards.filter((w) => (w.LST_mean || 38.0) >= 41.0).length;

  const selectedWardFeature = geoJsonData && geoJsonData.features.find(
    (f) => String(f.properties.ward_id) === String(selectedWardId)
  );
  const selectedWard = selectedWardFeature ? selectedWardFeature.properties : null;

  // Run Scenario What-If simulation
  const handleRunSimulation = async (addedCanopy, addedCoolRoofs, targetWardId = null) => {
    const wId = targetWardId || selectedWardId;
    const wFeature = geoJsonData.features.find(f => String(f.properties.ward_id) === String(wId));
    if (!wFeature) return;
    const wProps = wFeature.properties;

    setIsSimulating(true);
    try {
      const response = await fetch('http://localhost:8000/api/simulation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          wardId: String(wId),
          cityName: 'Ahmedabad',
          wardName: wProps.ward_name,
          baseLst: wProps.LST_mean,
          baseCanopy: Math.round((wProps.ndvi_mean || 0.1) * 100),
          baseHvi: wProps.hvi,
          popDensity: wProps.pop_density_km2,
          addedCanopy,
          addedCoolRoofs,
        }),
      });

      if (!response.ok) throw new Error('Simulation failed');
      const result = await response.json();

      setSimulationResult(result);
      // Add to history
      setSimulationHistory((prev) => [result, ...prev]);
    } catch (err) {
      console.error('Error running simulation:', err);
    } finally {
      setIsSimulating(false);
    }
  };

  const handleClearSimulation = () => {
    setSimulationResult(null);
  };

  // Run simulation from the sandbox table row click
  const handleActivateWardSimulation = async (wardProps, canopy, coolRoofs) => {
    setSelectedWardId(wardProps.ward_id);
    setActiveTab('command');
    // Run simulation
    await handleRunSimulation(canopy, coolRoofs, wardProps.ward_id);
  };

  // Restore simulated parameters from history logs
  const handleRestoreSimulation = (sim) => {
    setSimulationResult(sim);
    setSelectedWardId(sim.wardId);
    setActiveTab('command');
  };

  // Meteorology risk forecaster calculations
  const eVal = (predHumidity / 100.0) * 6.105 * Math.exp((17.27 * predTemp) / (237.7 + predTemp));
  const apparentTemp = predTemp + 0.33 * eVal - 4.0;

  const handleRunSimulationPredictive = async () => {
    setIsPredicting(true);
    const predictions = await runPredictiveSimulation(predTemp, predHumidity);
    if (predictions) {
      setPredictedLstMap(predictions);
      setActiveLayer('thermal'); // Switch map to thermal layer to see predictions
    }
    setIsPredicting(false);
  };

  const handleResetSimulationPredictive = () => {
    setPredictedLstMap(null);
  };

  const avatarUrl = 'https://lh3.googleusercontent.com/aida-public/AB6AXuDoxl5BbXa7EBYRi_sB1EzvT82n8XLnABJjsHM2m5arVANDp7Z6mfbV4sqt7oXOBwz3gBLr-rhWnqw0ornZbg0LUGlR2KJOxaRjSGCERBK_l6tL-NtgXJnenU0PpT4gsHKfyVVhsaTyFlvo_zthdNMiuvqTYqGSW1hLpPsRgUWDVRaHqSGNnDnJ7lYm4EmfdEZLjykIfnOk8qERpzEr34xvfWCrvShsq9ekynudXbUeTzb1BVFPS9W4';

  return (
    <div className="relative w-full h-screen bg-zinc-950 text-white overflow-hidden font-sans select-none antialiased">
      
      {/* 1. Header HUD */}
      <Header
        cities={cities}
        selectedCityId={selectedCityId}
        setSelectedCityId={setSelectedCityId}
        avgLst={avgLst}
        highRiskCount={highRiskCount}
        setShowChat={setShowChat}
        showChat={showChat}
      />

      {/* 2. Floating Left Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        avatarUrl={avatarUrl}
      />

      {/* 3. Central Router Viewport */}
      <main className="w-full h-full relative">
        
        {/* Command Center: Interactive Leaflet Map + Floating Inspector */}
        <div className={`w-full h-full transition-all duration-500 ${activeTab === 'command' ? 'opacity-100 z-10' : 'opacity-0 z-0 pointer-events-none'}`}>
          <div className={`absolute left-24 top-24 bottom-6 rounded-2xl border border-white/10 overflow-hidden transition-all duration-300 ${selectedWard ? 'right-[430px]' : 'right-6'}`}>
            <MapView
              geoJsonData={geoJsonData}
              activeLayer={activeLayer}
              predictedLstMap={predictedLstMap}
              selectedWardId={selectedWardId}
              onSelectWard={setSelectedWardId}
              simulationResult={simulationResult}
            />

            {/* Floating Weather Forecaster HUD Card nested inside map */}
            <div 
              style={{ 
                position: 'absolute', 
                top: '20px', 
                left: '20px', 
                zIndex: 1000, 
                width: '280px'
              }} 
              className="bg-zinc-950/80 backdrop-blur-xl border border-white/10 p-4 rounded-xl shadow-xl flex flex-col gap-3 text-left"
            >
            <div className="flex items-center gap-2 text-cyan-400 border-b border-white/5 pb-2">
              <Thermometer className="w-4 h-4" />
              <span className="text-[10px] font-sans font-bold uppercase tracking-widest text-zinc-300">
                Weather Forecast HUD
              </span>
            </div>
            
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-[10px] mb-1">
                  <span className="text-zinc-400">Air Temperature</span>
                  <span className="font-mono text-white font-bold">{predTemp}°C</span>
                </div>
                <input
                  type="range"
                  min="30"
                  max="50"
                  step="1"
                  value={predTemp}
                  onChange={(e) => setPredTemp(Number(e.target.value))}
                  className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                />
              </div>

              <div>
                <div className="flex justify-between text-[10px] mb-1">
                  <span className="text-zinc-400">Relative Humidity</span>
                  <span className="font-mono text-white font-bold">{predHumidity}%</span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="90"
                  step="5"
                  value={predHumidity}
                  onChange={(e) => setPredHumidity(Number(e.target.value))}
                  className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                />
              </div>

              <div className="flex justify-between items-center bg-white/5 p-2 rounded-lg text-[10px]">
                <span className="text-zinc-400">Apparent Heat Index:</span>
                <span className={`font-mono font-bold ${apparentTemp >= 40 ? 'text-red-400' : apparentTemp >= 35 ? 'text-orange-400' : 'text-teal-400'}`}>
                  {apparentTemp.toFixed(1)}°C
                </span>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={handleRunSimulationPredictive}
                  disabled={isPredicting}
                  className="flex-1 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white font-bold text-[10px] cursor-pointer shadow-[0_0_10px_rgba(6,182,212,0.2)] transition-all"
                >
                  {isPredicting ? 'Simulating...' : 'Run Forecast'}
                </button>
                {predictedLstMap && (
                  <button
                    onClick={handleResetSimulationPredictive}
                    className="bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white rounded-lg px-2 border border-white/10 cursor-pointer text-[10px] transition-all"
                  >
                    Reset
                  </button>
                )}
              </div>
            </div>
          </div>
          </div>

          {/* Right Floating Inspector Panel */}
          {selectedWard && (
            <Inspector
              selectedWard={selectedWard}
              onRunSimulation={handleRunSimulation}
              isSimulating={isSimulating}
              simulationResult={simulationResult}
              onClearSimulation={handleClearSimulation}
            />
          )}
        </div>

        {/* Analytics Tab */}
        {activeTab === 'analytics' && (
          <AnalyticsPanel
            wards={wards}
            cityName="Ahmedabad"
          />
        )}

        {/* Layers Tab */}
        {activeTab === 'layers' && (
          <LayersPanel
            activeLayer={activeLayer}
            setActiveLayer={setActiveLayer}
            setActiveTab={setActiveTab}
          />
        )}

        {/* Simulation Sandbox Tab */}
        {activeTab === 'simulation_list' && (
          <SimulationSandbox
            wards={wards}
            cityName="Ahmedabad"
            onActivateWardSimulation={handleActivateWardSimulation}
          />
        )}

        {/* History Log Tab */}
        {activeTab === 'history' && (
          <HistoryPanel
            simulations={simulationHistory}
            onClearHistory={() => setSimulationHistory([])}
            onSelectSimulation={handleRestoreSimulation}
          />
        )}
      </main>

      {/* 4. Floating AI Chatbot overlay */}
      {showChat && (
        <AIChatModal
          onClose={() => setShowChat(false)}
          selectedWardName={selectedWard ? selectedWard.ward_name : ''}
          selectedCityName="Ahmedabad"
        />
      )}
    </div>
  );
}
