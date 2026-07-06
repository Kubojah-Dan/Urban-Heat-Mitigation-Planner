import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';

// ── Color Ramp Helpers ────────────────────────────────────────────────────────

// Thermal Layer: High LST = Crimson/Orange, Cool = Teal/Blue
const getLstColor = (val) => {
  if (val === undefined || val === null) return '#475569';
  if (val >= 44.0) return '#ef4444'; // Crimson
  if (val >= 41.0) return '#f97316'; // Orange
  if (val >= 39.0) return '#eab308'; // Yellow-Orange
  return '#06b6d2'; // Teal
};

// Canopy Layer (NDVI): High = Emerald Green, Deficit = Purple
const getCanopyColor = (val) => {
  if (val === undefined || val === null) return '#475569';
  // Canopy percent = ndvi * 100
  if (val >= 20.0) return '#10b981'; // Emerald
  if (val >= 12.0) return '#22c55e'; // Green
  return '#a855f7'; // Purple (Deficit)
};

// Population Density Layer: High = Cyan, Low = Blue/Indigo
const getPopulationColor = (val) => {
  if (val === undefined || val === null) return '#475569';
  // Density in k/km2 (e.g. w.pop_density_km2 / 1000)
  if (val >= 25.0) return '#06b6d4'; // Glowing Cyan
  if (val >= 14.0) return '#0ea5e9'; // Blue
  return '#6366f1'; // Indigo
};

// HVI Layer: High = Rose/Coral, Low = Teal
const getHviColor = (val) => {
  if (val === undefined || val === null) return '#475569';
  // HVI index (0 to 1 scale)
  if (val >= 0.65) return '#f43f5e'; // Rose Pink
  if (val >= 0.50) return '#fb923c'; // Orange
  return '#2dd4bf'; // Teal
};

// Component to dynamically fit map boundaries to the loaded GeoJSON
function MapAutoBounds({ data }) {
  const map = useMap();
  useEffect(() => {
    if (data && data.features && data.features.length > 0) {
      try {
        const geoJsonLayer = L.geoJSON(data);
        map.fitBounds(geoJsonLayer.getBounds(), { padding: [20, 20] });
      } catch (err) {
        console.error("Error setting bounds:", err);
      }
    }
  }, [data, map]);
  return null;
}

export default function MapView({ 
  geoJsonData, 
  activeLayer, 
  predictedLstMap, 
  selectedWardId, 
  onSelectWard,
  simulationResult
}) {
  const geojsonRef = useRef(null);

  // Redraw features when data, layer mode, predictions, or simulation results change
  useEffect(() => {
    if (geojsonRef.current) {
      geojsonRef.current.clearLayers().addData(geoJsonData);
    }
  }, [geoJsonData, activeLayer, predictedLstMap, simulationResult]);

  // Style each polygon dynamically
  const styleFeature = (feature) => {
    const props = feature.properties;
    const wardId = props.ward_id;
    const isSelected = String(selectedWardId) === String(wardId);
    let color = '#64748b';

    // Check if there is an active sandbox simulation result for this ward
    const hasActiveSim = isSelected && simulationResult && String(simulationResult.wardId) === String(wardId);

    if (activeLayer === 'thermal') {
      let tempVal = props.LST_mean;
      if (hasActiveSim) {
        tempVal = simulationResult.newLst;
      } else if (predictedLstMap && predictedLstMap[wardId] !== undefined) {
        tempVal = predictedLstMap[wardId];
      }
      color = getLstColor(tempVal);
    } else if (activeLayer === 'canopy') {
      const canopyVal = hasActiveSim ? simulationResult.newCanopy : Math.round((props.ndvi_mean || 0.1) * 100);
      color = getCanopyColor(canopyVal);
    } else if (activeLayer === 'population') {
      const popVal = (props.pop_density_km2 || 10000) / 1000.0;
      color = getPopulationColor(popVal);
    } else if (activeLayer === 'hvi') {
      const hviVal = hasActiveSim ? simulationResult.newHvi : props.hvi;
      color = getHviColor(hviVal);
    }

    return {
      fillColor: color,
      fillOpacity: isSelected ? 0.85 : 0.6,
      color: isSelected ? '#22d3ee' : 'rgba(255,255,255,0.15)',
      weight: isSelected ? 2.5 : 1,
      dashArray: isSelected ? 'none' : '2,1',
      className: 'transition-all duration-300'
    };
  };

  // Interactions for each polygon
  const onEachFeature = (feature, layer) => {
    const props = feature.properties;
    const wardName = props.ward_name || `Ward ${props.ward_id}`;
    
    // Bind detailed HUD tooltip
    const lstVal = props.LST_mean ? props.LST_mean.toFixed(1) : 'N/A';
    const canopyVal = props.ndvi_mean ? Math.round(props.ndvi_mean * 100) : 'N/A';
    const popVal = props.pop_density_km2 ? (props.pop_density_km2 / 1000.0).toFixed(1) : 'N/A';
    const hviVal = props.hvi ? (props.hvi * 10.0).toFixed(1) : 'N/A';

    layer.bindTooltip(
      `<div className="text-left font-sans space-y-1">` +
      `<strong className="text-white text-xs block border-b border-white/5 pb-1">${wardName}</strong>` +
      `<div className="text-[10px] text-zinc-400 font-mono space-y-0.5">` +
      `<div>LST Temp: <span className="text-orange-400 font-bold">${lstVal}°C</span></div>` +
      `<div>Tree Canopy: <span className="text-emerald-400 font-bold">${canopyVal}%</span></div>` +
      `<div>Pop Density: <span className="text-cyan-400 font-bold">${popVal}k/km²</span></div>` +
      `<div>Vulnerability: <span className="text-rose-400 font-bold">${hviVal}/10 HVI</span></div>` +
      `</div>` +
      `</div>`,
      { direction: 'top', sticky: true, className: 'map-tooltip' }
    );

    layer.on({
      mouseover: (e) => {
        const l = e.target;
        l.setStyle({
          weight: 2,
          color: '#ffffff',
          fillOpacity: 0.8
        });
      },
      mouseout: (e) => {
        const l = e.target;
        if (geojsonRef.current) {
          geojsonRef.current.resetStyle(l);
        }
      },
      click: () => {
        onSelectWard(props.ward_id);
      }
    });
  };

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <MapContainer
        center={[23.0225, 72.5714]} // Ahmedabad Center
        zoom={12}
        zoomControl={true}
        style={{ width: '100%', height: '100%' }}
      >
        {/* Dark Mode Map Tiles */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          className="dark-tiles"
        />

        {geoJsonData && (
          <>
            <GeoJSON
              ref={geojsonRef}
              data={geoJsonData}
              style={styleFeature}
              onEachFeature={onEachFeature}
            />
            <MapAutoBounds data={geoJsonData} />
          </>
        )}
      </MapContainer>

      {/* Map Legend */}
      <div 
        style={{ 
          position: 'absolute', 
          bottom: '24px', 
          left: '24px', 
          zIndex: 1000, 
        }} 
        className="bg-zinc-950/80 backdrop-blur-xl border border-white/10 p-4 rounded-xl shadow-xl flex flex-col gap-2 max-w-[240px] text-left"
      >
        <span className="text-[10px] font-sans font-bold uppercase tracking-widest text-zinc-400">
          Map Legend: <span className="text-cyan-400 font-bold">{activeLayer.toUpperCase()}</span>
        </span>
        
        {activeLayer === 'thermal' && (
          <div className="flex flex-col gap-1.5 mt-1 text-[10px] text-zinc-400 font-mono">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1.5 rounded bg-red-500 shadow-[0_0_4px_#ef4444]"></span>
              <span>&gt;= 44°C (Critical)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1.5 rounded bg-orange-500 shadow-[0_0_4px_#f97316]"></span>
              <span>41°C - 44°C</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1.5 rounded bg-yellow-500 shadow-[0_0_4px_#eab308]"></span>
              <span>39°C - 41°C</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1.5 rounded bg-cyan-500 shadow-[0_0_4px_#06b6d2]"></span>
              <span>&lt; 39°C (Moderate)</span>
            </div>
          </div>
        )}

        {activeLayer === 'canopy' && (
          <div className="flex flex-col gap-1.5 mt-1 text-[10px] text-zinc-400 font-mono">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1.5 rounded bg-emerald-500 shadow-[0_0_4px_#10b981]"></span>
              <span>&gt;= 20% (Optimal)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1.5 rounded bg-green-500 shadow-[0_0_4px_#22c55e]"></span>
              <span>12% - 20%</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1.5 rounded bg-purple-500 shadow-[0_0_4px_#a855f7]"></span>
              <span>&lt; 12% (Deficit)</span>
            </div>
          </div>
        )}

        {activeLayer === 'population' && (
          <div className="flex flex-col gap-1.5 mt-1 text-[10px] text-zinc-400 font-mono">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1.5 rounded bg-cyan-400 shadow-[0_0_4px_#06b6d4]"></span>
              <span>&gt;= 25k/km² (Dense)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1.5 rounded bg-sky-500 shadow-[0_0_4px_#0ea5e9]"></span>
              <span>14k - 25k/km²</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1.5 rounded bg-indigo-500 shadow-[0_0_4px_#6366f1]"></span>
              <span>&lt; 14k/km² (Sparse)</span>
            </div>
          </div>
        )}

        {activeLayer === 'hvi' && (
          <div className="flex flex-col gap-1.5 mt-1 text-[10px] text-zinc-400 font-mono">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1.5 rounded bg-rose-500 shadow-[0_0_4px_#f43f5e]"></span>
              <span>&gt;= 6.5/10 HVI (Severe)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1.5 rounded bg-orange-400 shadow-[0_0_4px_#fb923c]"></span>
              <span>5.0 - 6.5 HVI</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-1.5 rounded bg-teal-400 shadow-[0_0_4px_#2dd4bf]"></span>
              <span>&lt; 5.0 HVI (Low)</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
