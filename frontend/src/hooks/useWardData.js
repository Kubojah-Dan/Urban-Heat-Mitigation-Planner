import { useState, useEffect, useCallback } from 'react';

const API_BASE_URL = 'http://localhost:8000/api';

export default function useWardData() {
  const [geoJsonData, setGeoJsonData] = useState(null);
  const [citySummary, setCitySummary] = useState(null);
  const [selectedWardDetail, setSelectedWardDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch initial baseline assets (boundary maps and city aggregates)
  const fetchBaselineData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch city summary aggregates
      const summaryRes = await fetch(`${API_BASE_URL}/city-summary`);
      if (!summaryRes.ok) throw new Error('Failed to fetch city summary data.');
      const summaryData = await summaryRes.json();
      setCitySummary(summaryData);

      // Fetch ward geometries
      const wardsRes = await fetch(`${API_BASE_URL}/wards`);
      if (!wardsRes.ok) throw new Error('Failed to fetch ward boundary coordinates.');
      const wardsData = await wardsRes.json();
      setGeoJsonData(wardsData);

    } catch (err) {
      console.error(err);
      setError(err.message || 'An error occurred fetching baseline data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBaselineData();
  }, [fetchBaselineData]);

  // Fetch metrics and top interventions for a specific ward
  const fetchWardDetail = useCallback(async (wardId) => {
    if (!wardId) {
      setSelectedWardDetail(null);
      return null;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/wards/${wardId}`);
      if (!res.ok) throw new Error(`Failed to fetch details for ward ID ${wardId}`);
      const data = await res.json();
      setSelectedWardDetail(data);
      return data;
    } catch (err) {
      console.error(err);
      return null;
    }
  }, []);

  // Call the dynamic ML risk simulator
  const runPredictiveSimulation = useCallback(async (temp, humidity) => {
    try {
      const res = await fetch(`${API_BASE_URL}/predict?temp=${temp}&humidity=${humidity}`);
      if (!res.ok) throw new Error('Simulation endpoint failed.');
      const data = await res.json();
      return data.predictions; // returns map of ward_id -> predicted LST
    } catch (err) {
      console.error(err);
      alert('Error running simulation. Ensure backend API is online.');
      return null;
    }
  }, []);

  return {
    geoJsonData,
    citySummary,
    selectedWardDetail,
    loading,
    error,
    fetchWardDetail,
    runPredictiveSimulation,
    refetch: fetchBaselineData
  };
}
