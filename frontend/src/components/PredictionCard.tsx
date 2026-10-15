import React from 'react';
import { ArrowUpRight, ArrowDownRight, ArrowRight, Zap } from 'lucide-react';
import type { PredictionResponse } from '../types/traffic';

interface PredictionCardProps {
  prediction: PredictionResponse | null;
  loading: boolean;
}

export const PredictionCard: React.FC<PredictionCardProps> = ({ prediction, loading }) => {
  if (loading) {
    return (
      <div className="prediction-box">
        <div className="forecast-header">
          <span>Spark ML Inference Engine</span>
          <span className="spinner"></span>
        </div>
        <div style={{ padding: '1rem 0', color: '#94a3b8', fontSize: '0.85rem' }}>
          Generating 15-minute speed forecast via Spark PipelineModel...
        </div>
      </div>
    );
  }

  if (!prediction) {
    return (
      <div className="prediction-box">
        <div className="forecast-header">
          <span>Spark ML Inference</span>
          <Zap size={14} />
        </div>
        <div style={{ color: '#94a3b8', fontSize: '0.82rem', padding: '0.5rem 0' }}>
          Select a sensor on the map to trigger real-time Spark ML 15-minute speed prediction.
        </div>
      </div>
    );
  }

  const change = prediction.speed_change_mph;
  const isPositive = change > 0.3;
  const isNegative = change < -0.3;

  let changeClass = 'change-neutral';
  let ArrowIcon = ArrowRight;
  let sign = '';

  if (isPositive) {
    changeClass = 'change-up';
    ArrowIcon = ArrowUpRight;
    sign = '+';
  } else if (isNegative) {
    changeClass = 'change-down';
    ArrowIcon = ArrowDownRight;
  }

  const badgeClass =
    prediction.congestion_level === 'LOW'
      ? 'badge-low'
      : prediction.congestion_level === 'MEDIUM'
      ? 'badge-med'
      : 'badge-high';

  return (
    <div className="prediction-box">
      <div className="forecast-header">
        <span>15-Minute Forecast (+15m)</span>
        <span className={`badge-congestion ${badgeClass}`}>{prediction.congestion_level}</span>
      </div>

      <div className="forecast-values">
        <div className="forecast-speed">
          {prediction.predicted_speed_15min_mph.toFixed(2)}
          <small>mph</small>
        </div>

        <div className={`forecast-change ${changeClass}`}>
          <ArrowIcon size={16} />
          <span>
            {sign}
            {change.toFixed(2)} mph
          </span>
        </div>
      </div>

      <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '0.5rem' }}>
        Forecasted by trained Random Forest pipeline based on sensor lags and cyclical temporal patterns.
      </div>
    </div>
  );
};
