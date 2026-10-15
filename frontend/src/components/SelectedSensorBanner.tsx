import React from 'react';
import type { SensorObservation, PredictionResponse } from '../types/traffic';
import { ArrowUpRight, ArrowDownRight, ArrowRight, Activity, MapPin } from 'lucide-react';

interface SelectedSensorBannerProps {
  selectedSensor: SensorObservation | null;
  prediction: PredictionResponse | null;
  loadingPrediction: boolean;
  predictionError: string | null;
}

export const SelectedSensorBanner: React.FC<SelectedSensorBannerProps> = ({
  selectedSensor,
  prediction,
  loadingPrediction,
  predictionError,
}) => {
  if (!selectedSensor) {
    return (
      <div className="sensor-banner-card empty">
        <MapPin size={18} color="#64748b" />
        <span>Select any sensor marker on the METR-LA map to view real-time telemetry and 15-minute speed predictions.</span>
      </div>
    );
  }

  const change = prediction ? prediction.speed_change_mph : 0;
  const isPositive = change > 0.2;
  const isNegative = change < -0.2;
  const sign = isPositive ? '+' : '';
  const ArrowIcon = isPositive ? ArrowUpRight : isNegative ? ArrowDownRight : ArrowRight;
  const changeClass = isPositive ? 'change-up' : isNegative ? 'change-down' : 'change-neutral';

  const status = prediction ? prediction.congestion_level : selectedSensor.congestion_level;
  const badgeClass =
    status === 'LOW' ? 'badge-low' : status === 'MEDIUM' ? 'badge-med' : 'badge-high';

  return (
    <div className="sensor-banner-card">
      <div className="sensor-banner-inner">
        {/* 1. Sensor Identity & GPS */}
        <div className="sensor-col-id">
          <div className="sensor-label">Selected Station</div>
          <div className="sensor-title">
            <span className="sensor-dot"></span>
            Sensor {selectedSensor.sensor_id}
          </div>
          <div className="sensor-sub">
            {selectedSensor.latitude.toFixed(4)}°, {selectedSensor.longitude.toFixed(4)}°
          </div>
        </div>

        {/* 2. Current Speed */}
        <div className="sensor-col-metric">
          <div className="sensor-label">Current</div>
          <div className="metric-val">
            {selectedSensor.speed.toFixed(2)} <span className="metric-unit">mph</span>
          </div>
          <div className="sensor-sub">Lag -5m: {selectedSensor.speed_lag_1.toFixed(1)} mph</div>
        </div>

        {/* 3. 15-Min Forecast */}
        <div className="sensor-col-metric highlight">
          <div className="sensor-label" style={{ color: '#38bdf8' }}>
            15-Min Forecast
          </div>
          {loadingPrediction ? (
            <div className="metric-loading">
              <span className="spinner mini"></span>
              <span>Predicting...</span>
            </div>
          ) : prediction ? (
            <div className="metric-val" style={{ color: '#38bdf8' }}>
              {prediction.predicted_speed_15min_mph.toFixed(2)} <span className="metric-unit">mph</span>
            </div>
          ) : (
            <div className="metric-val text-muted">--</div>
          )}
          <div className="sensor-sub">Spark Random Forest</div>
        </div>

        {/* 4. Speed Change */}
        <div className="sensor-col-metric">
          <div className="sensor-label">Change</div>
          {loadingPrediction ? (
            <div className="metric-val text-muted">...</div>
          ) : prediction ? (
            <div className={`metric-change-pill ${changeClass}`}>
              <ArrowIcon size={14} />
              <span>
                {sign}{change.toFixed(2)} mph
              </span>
            </div>
          ) : (
            <div className="metric-val text-muted">--</div>
          )}
          <div className="sensor-sub">Expected Delta</div>
        </div>

        {/* 5. Congestion Status */}
        <div className="sensor-col-metric">
          <div className="sensor-label">Status</div>
          <div style={{ marginTop: '2px' }}>
            <span className={`badge-congestion ${badgeClass}`}>{status}</span>
          </div>
          <div className="sensor-sub">
            {status === 'LOW' ? '≥ 50 mph' : status === 'MEDIUM' ? '30–50 mph' : '< 30 mph'}
          </div>
        </div>
      </div>

      {predictionError && (
        <div className="sensor-banner-error">
          <Activity size={14} />
          <span>Prediction alert: {predictionError}</span>
        </div>
      )}
    </div>
  );
};
