import React, { useState } from 'react';
import type { ScenarioRequest, ScenarioResponse, SensorObservation } from '../types/traffic';
import { analyzeScenario } from '../services/api';
import { Sliders, Sparkles, ArrowRight, Network, AlertCircle } from 'lucide-react';

interface WhatIfScenarioPanelProps {
  sensors: SensorObservation[];
  selectedSensorId: string;
  onSelectSensorId: (sensorId: string) => void;
  scenarioResult: ScenarioResponse | null;
  onScenarioAnalyzed: (result: ScenarioResponse) => void;
}

export const WhatIfScenarioPanel: React.FC<WhatIfScenarioPanelProps> = ({
  sensors,
  selectedSensorId,
  onSelectSensorId,
  scenarioResult,
  onScenarioAnalyzed,
}) => {
  const [speed, setSpeed] = useState<number>(32.0);
  const [speedLag1, setSpeedLag1] = useState<number>(35.0);
  const [speedLag2, setSpeedLag2] = useState<number>(38.0);
  const [speedLag3, setSpeedLag3] = useState<number>(41.0);
  const [scenarioDate, setScenarioDate] = useState<string>('2012-06-09');
  const [scenarioTime, setScenarioTime] = useState<string>('17:30');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Sync inputs with the target sensor when selected
  React.useEffect(() => {
    const match = sensors.find((s) => s.sensor_id === selectedSensorId);
    if (match) {
      setSpeed(match.speed);
      setSpeedLag1(match.speed_lag_1);
      setSpeedLag2(match.speed_lag_2);
      setSpeedLag3(match.speed_lag_3);
      if (match.timestamp) {
        const parts = match.timestamp.split(' ');
        if (parts.length === 2) {
          setScenarioDate(parts[0]);
          setScenarioTime(parts[1].substring(0, 5));
        }
      }
    }
  }, [selectedSensorId, sensors]);

  // Quick preset helper
  const applyPreset = (type: 'slowdown' | 'heavy' | 'freeflow') => {
    if (type === 'slowdown') {
      setSpeed(32.0);
      setSpeedLag1(35.0);
      setSpeedLag2(38.0);
      setSpeedLag3(41.0);
    } else if (type === 'heavy') {
      setSpeed(22.0);
      setSpeedLag1(26.0);
      setSpeedLag2(30.0);
      setSpeedLag3(35.0);
    } else {
      setSpeed(65.0);
      setSpeedLag1(64.0);
      setSpeedLag2(62.0);
      setSpeedLag3(60.0);
    }
  };

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const fullTimestamp = `${scenarioDate} ${scenarioTime}:00`;
    const payload: ScenarioRequest = {
      sensor_id: selectedSensorId || '716955',
      timestamp: fullTimestamp,
      speed: Number(speed),
      speed_lag_1: Number(speedLag1),
      speed_lag_2: Number(speedLag2),
      speed_lag_3: Number(speedLag3),
      rolling_mean_3: Number(((Number(speed) + Number(speedLag1) + Number(speedLag2)) / 3.0).toFixed(2)),
    };

    try {
      const res = await analyzeScenario(payload);
      onScenarioAnalyzed(res);
      setLoading(false);
    } catch (err: any) {
      console.error('Scenario analysis error:', err);
      setError(err.message || 'Failed to analyze scenario');
      setLoading(false);
    }
  };

  const getBadgeClass = (level: string) => {
    if (level === 'LOW') return 'badge-low';
    if (level === 'MEDIUM') return 'badge-med';
    return 'badge-high';
  };

  return (
    <div className="scenario-container">
      {/* Input Parameters Card */}
      <div className="card scenario-form-card">
        <div className="card-header-bar">
          <div className="card-title">
            <Sliders size={16} color="#38bdf8" />
            <span>WHAT-IF SCENARIO CONFIGURATION</span>
          </div>
          <div className="scenario-preset-group">
            <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Presets:</span>
            <button
              type="button"
              className="btn-preset"
              onClick={() => applyPreset('slowdown')}
              title="Gradual congestion developing"
            >
              Developing Slowdown
            </button>
            <button
              type="button"
              className="btn-preset"
              onClick={() => applyPreset('heavy')}
              title="Heavy traffic bottleneck"
            >
              Bottleneck Congestion
            </button>
            <button
              type="button"
              className="btn-preset"
              onClick={() => applyPreset('freeflow')}
              title="Normal free flow highway speed"
            >
              Free Flow
            </button>
          </div>
        </div>

        <form onSubmit={handleAnalyze} className="scenario-form">
          <div className="scenario-grid-inputs">
            {/* Sensor Selection */}
            <div className="form-field">
              <label htmlFor="scenario-sensor-select">Target Sensor:</label>
              <select
                id="scenario-sensor-select"
                className="form-input select"
                value={selectedSensorId}
                onChange={(e) => onSelectSensorId(e.target.value)}
              >
                {sensors.map((s) => (
                  <option key={s.sensor_id} value={s.sensor_id}>
                    Station #{s.sensor_id} ({s.latitude.toFixed(2)}°, {s.longitude.toFixed(2)}°)
                  </option>
                ))}
              </select>
            </div>

            {/* Current Speed */}
            <div className="form-field">
              <label htmlFor="scenario-speed">Current Speed (mph):</label>
              <input
                id="scenario-speed"
                type="number"
                step="0.1"
                min="0"
                max="120"
                className="form-input"
                value={speed}
                onChange={(e) => setSpeed(Number(e.target.value))}
                required
              />
            </div>

            {/* Lag -5m */}
            <div className="form-field">
              <label htmlFor="scenario-lag1">Speed 5 min ago (t-1):</label>
              <input
                id="scenario-lag1"
                type="number"
                step="0.1"
                min="0"
                max="120"
                className="form-input"
                value={speedLag1}
                onChange={(e) => setSpeedLag1(Number(e.target.value))}
                required
              />
            </div>

            {/* Lag -10m */}
            <div className="form-field">
              <label htmlFor="scenario-lag2">Speed 10 min ago (t-2):</label>
              <input
                id="scenario-lag2"
                type="number"
                step="0.1"
                min="0"
                max="120"
                className="form-input"
                value={speedLag2}
                onChange={(e) => setSpeedLag2(Number(e.target.value))}
                required
              />
            </div>

            {/* Lag -15m */}
            <div className="form-field">
              <label htmlFor="scenario-lag3">Speed 15 min ago (t-3):</label>
              <input
                id="scenario-lag3"
                type="number"
                step="0.1"
                min="0"
                max="120"
                className="form-input"
                value={speedLag3}
                onChange={(e) => setSpeedLag3(Number(e.target.value))}
                required
              />
            </div>

            {/* Date */}
            <div className="form-field">
              <label htmlFor="scenario-date">Date:</label>
              <input
                id="scenario-date"
                type="date"
                className="form-input"
                value={scenarioDate}
                onChange={(e) => setScenarioDate(e.target.value)}
                required
              />
            </div>

            {/* Time */}
            <div className="form-field">
              <label htmlFor="scenario-time">Time:</label>
              <input
                id="scenario-time"
                type="time"
                className="form-input"
                value={scenarioTime}
                onChange={(e) => setScenarioTime(e.target.value)}
                required
              />
            </div>

            {/* Submit Action */}
            <div className="form-field submit-field">
              <button type="submit" className="btn-analyze" disabled={loading}>
                {loading ? (
                  <>
                    <span className="spinner mini"></span>
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={15} />
                    <span>ANALYZE SCENARIO</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>

        {error && (
          <div className="scenario-error-banner">
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Scenario Analysis Results */}
      {scenarioResult && (
        <div className="scenario-results-grid">
          {/* 1. TRAFFIC FORECAST CARD */}
          <div className="card scenario-card">
            <div className="card-header-bar">
              <div className="card-title">TRAFFIC FORECAST (+15 MIN)</div>
              <span className={`badge-congestion ${getBadgeClass(scenarioResult.predicted_congestion_level)}`}>
                {scenarioResult.predicted_congestion_level}
              </span>
            </div>
            <div className="card-compact-body">
              <div className="scenario-metric-box">
                <div className="metric-row">
                  <span className="lbl">Current Speed:</span>
                  <span className="val">{scenarioResult.current_speed_mph.toFixed(1)} mph</span>
                </div>
                <div className="metric-row highlight">
                  <span className="lbl">Predicted in 15 min:</span>
                  <span className="val" style={{ color: '#38bdf8', fontSize: '1.2rem', fontWeight: 800 }}>
                    {scenarioResult.predicted_speed_15min_mph.toFixed(2)} mph
                  </span>
                </div>
                <div className="metric-row">
                  <span className="lbl">Expected Change:</span>
                  <span
                    className={`val ${
                      scenarioResult.speed_change_mph < -0.3
                        ? 'text-high'
                        : scenarioResult.speed_change_mph > 0.3
                        ? 'text-low'
                        : ''
                    }`}
                  >
                    {scenarioResult.speed_change_mph > 0 ? '+' : ''}
                    {scenarioResult.speed_change_mph.toFixed(2)} mph
                  </span>
                </div>
                <div className="metric-row">
                  <span className="lbl">Predicted Congestion:</span>
                  <span className="val font-semibold">{scenarioResult.predicted_congestion_level}</span>
                </div>
              </div>

              {/* BEFORE / AFTER SCENARIO COMPARISON */}
              <div className="scenario-comparison-card">
                <div className="comp-title">BEFORE / AFTER SCENARIO</div>
                <div className="comp-row">
                  <div className="comp-col">
                    <span className="comp-tag">Input Condition</span>
                    <span className="comp-val">{scenarioResult.current_speed_mph.toFixed(1)} mph</span>
                    <span className={`badge-congestion ${getBadgeClass(scenarioResult.current_congestion_level)}`}>
                      {scenarioResult.current_congestion_level}
                    </span>
                  </div>
                  <div className="comp-arrow">
                    <ArrowRight size={20} color="#94a3b8" />
                  </div>
                  <div className="comp-col">
                    <span className="comp-tag">Spark ML Forecast</span>
                    <span className="comp-val">{scenarioResult.predicted_speed_15min_mph.toFixed(1)} mph</span>
                    <span className={`badge-congestion ${getBadgeClass(scenarioResult.predicted_congestion_level)}`}>
                      {scenarioResult.predicted_congestion_level}
                    </span>
                  </div>
                </div>
                <div className="comp-delta-bar">
                  Expected Delta: {scenarioResult.speed_change_mph > 0 ? '+' : ''}
                  {scenarioResult.speed_change_mph.toFixed(2)} mph &middot; Congestion Shift:{' '}
                  {scenarioResult.current_congestion_level} &rarr; {scenarioResult.predicted_congestion_level}
                </div>
              </div>
            </div>
          </div>

          {/* 2. NETWORK ANALYSIS CARD */}
          <div className="card scenario-card">
            <div className="card-header-bar">
              <div className="card-title">
                <Network size={16} color="#818cf8" />
                <span>NETWORK ANALYSIS</span>
                <span className="badge-count">{scenarioResult.connected_sensors_count} Connected</span>
              </div>
            </div>
            <div className="card-compact-body">
              <div className="propagation-summary-row">
                <div className="prop-summary-pill">
                  <span className="prop-summary-lbl">Connected</span>
                  <span className="prop-summary-val">{scenarioResult.connected_sensors_count}</span>
                </div>
                <div className="prop-summary-pill">
                  <span className="prop-summary-lbl text-high">HIGH</span>
                  <span className="prop-summary-val text-high">{scenarioResult.high_count}</span>
                </div>
                <div className="prop-summary-pill">
                  <span className="prop-summary-lbl text-med">MEDIUM</span>
                  <span className="prop-summary-val text-med">{scenarioResult.medium_count}</span>
                </div>
                <div className="prop-summary-pill">
                  <span className="prop-summary-lbl text-low">LOW</span>
                  <span className="prop-summary-val text-low">{scenarioResult.low_count}</span>
                </div>
                <div className="prop-summary-pill">
                  <span className="prop-summary-lbl">Indicator</span>
                  <span className="prop-summary-val" style={{ color: '#818cf8' }}>
                    {scenarioResult.weighted_congestion_indicator.toFixed(2)}
                  </span>
                </div>
              </div>

              {/* Connected Neighbor Table */}
              <div className="prop-table-wrapper" style={{ maxHeight: '150px' }}>
                <table className="prop-table">
                  <thead>
                    <tr>
                      <th>Connected Sensor</th>
                      <th>Adjacency Weight</th>
                      <th>Speed</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scenarioResult.neighbors.map((n) => (
                      <tr key={n.sensor_id}>
                        <td style={{ fontWeight: 600, color: '#f8fafc' }}>Station #{n.sensor_id}</td>
                        <td style={{ fontFamily: 'monospace', color: '#94a3b8' }}>{n.weight.toFixed(4)}</td>
                        <td style={{ color: '#f8fafc' }}>{n.speed_mph.toFixed(1)} mph</td>
                        <td>
                          <span className={`badge-congestion ${getBadgeClass(n.congestion_level)}`}>
                            {n.congestion_level}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Explicit Academic Disclaimer */}
              <div className="prop-disclaimer">
                {scenarioResult.disclaimer}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default WhatIfScenarioPanel;
