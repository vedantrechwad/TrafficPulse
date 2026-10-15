import React from 'react';
import type { ModelMetadata } from '../types/traffic';
import { Layers } from 'lucide-react';

interface ModelStatsProps {
  modelInfo: ModelMetadata | null;
}

export const ModelStats: React.FC<ModelStatsProps> = ({ modelInfo }) => {
  const params = modelInfo?.model_parameters || { numTrees: 20, maxDepth: 6 };
  const metrics = modelInfo?.final_test_metrics || { mae: 3.2487, rmse: 5.8832, r2: 0.8046 };
  const splits = modelInfo?.splits;
  const totalTrained =
    (splits?.train_count || 4485388) + (splits?.val_count || 960301);

  return (
    <div className="card model-compact-card">
      <div className="card-header-bar">
        <div>
          <div className="card-title">
            <Layers size={16} color="#818cf8" />
            <span>Model Details</span>
            <span className="badge-count">PySpark MLlib</span>
          </div>
          <div className="card-subtitle">Architecture & Offline Validation Metrics</div>
        </div>
      </div>

      <div className="card-compact-body">
        {/* Model Title & Specs */}
        <div className="model-summary-box">
          <div className="model-tag">MODEL</div>
          <div className="model-name">{modelInfo?.model_type || 'Random Forest Regressor'}</div>
          <div className="model-specs">
            {params.numTrees || 20} trees &middot; depth {params.maxDepth || 6} &middot; 15-min horizon
          </div>
        </div>

        {/* Compact Metrics Row */}
        <div className="model-metrics-row">
          <div className="model-metric-pill">
            <span className="metric-pill-lbl">MAE</span>
            <span className="metric-pill-val">{metrics.mae.toFixed(2)} mph</span>
          </div>
          <div className="model-metric-pill">
            <span className="metric-pill-lbl">RMSE</span>
            <span className="metric-pill-val">{metrics.rmse.toFixed(2)} mph</span>
          </div>
          <div className="model-metric-pill">
            <span className="metric-pill-lbl">R²</span>
            <span className="metric-pill-val" style={{ color: '#10b981' }}>
              {metrics.r2.toFixed(3)}
            </span>
          </div>
        </div>

        {/* Pipeline Architecture Table */}
        <div className="prop-table-wrapper" style={{ maxHeight: '140px', marginTop: '0.65rem' }}>
          <table className="prop-table">
            <tbody>
              <tr>
                <td style={{ color: '#94a3b8' }}>Pipeline Scale</td>
                <td style={{ textAlign: 'right', fontWeight: 600, color: '#f8fafc' }}>
                  7,094,304 raw &middot; 6.40M ML records
                </td>
              </tr>
              <tr>
                <td style={{ color: '#94a3b8' }}>Network Coverage</td>
                <td style={{ textAlign: 'right', fontWeight: 600, color: '#f8fafc' }}>
                  207 METR-LA Highway Sensors
                </td>
              </tr>
              <tr>
                <td style={{ color: '#94a3b8' }}>Training Records</td>
                <td style={{ textAlign: 'right', fontWeight: 600, color: '#f8fafc' }}>
                  {totalTrained.toLocaleString()} (Train + Val)
                </td>
              </tr>
              <tr>
                <td style={{ color: '#94a3b8' }}>Feature Vector</td>
                <td style={{ textAlign: 'right', color: '#38bdf8' }}>
                  Lags (-5m, -10m, -15m), Rolling Mean, Time
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="prop-disclaimer">
          Trained with distributed Spark ML VectorAssembler & PipelineModel.
        </div>
      </div>
    </div>
  );
};

export default ModelStats;
