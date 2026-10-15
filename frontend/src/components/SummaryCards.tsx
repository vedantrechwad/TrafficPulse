import React from 'react';
import type { ModelMetadata, ReplaySummaryResponse } from '../types/traffic';
import { Radio, Clock, Target, TrendingUp, Gauge, AlertTriangle, CheckCircle, ShieldAlert } from 'lucide-react';

interface SummaryCardsProps {
  totalSensors: number;
  modelInfo: ModelMetadata | null;
  replaySummary?: ReplaySummaryResponse | null;
}

export const SummaryCards: React.FC<SummaryCardsProps> = ({
  totalSensors,
  modelInfo,
  replaySummary,
}) => {
  if (replaySummary) {
    return (
      <div className="kpi-compact-bar replay-mode-kpi">
        <div className="kpi-compact-item">
          <div className="kpi-icon-pill">
            <Radio size={15} color="#38bdf8" />
          </div>
          <div>
            <div className="kpi-compact-val">{replaySummary.total_sensors || totalSensors}</div>
            <div className="kpi-compact-lbl">Sensors</div>
          </div>
        </div>

        <div className="kpi-compact-item">
          <div className="kpi-icon-pill">
            <Gauge size={15} color="#38bdf8" />
          </div>
          <div>
            <div className="kpi-compact-val">{replaySummary.average_speed.toFixed(1)} <small style={{ fontSize: '0.75rem', fontWeight: 500 }}>mph</small></div>
            <div className="kpi-compact-lbl">Avg Speed</div>
          </div>
        </div>

        <div className="kpi-compact-item">
          <div className="kpi-icon-pill" style={{ background: 'rgba(239, 68, 68, 0.12)' }}>
            <ShieldAlert size={15} color="#ef4444" />
          </div>
          <div>
            <div className="kpi-compact-val text-high">{replaySummary.high_count}</div>
            <div className="kpi-compact-lbl text-high">HIGH (&lt;30m)</div>
          </div>
        </div>

        <div className="kpi-compact-item">
          <div className="kpi-icon-pill" style={{ background: 'rgba(245, 158, 11, 0.12)' }}>
            <AlertTriangle size={15} color="#f59e0b" />
          </div>
          <div>
            <div className="kpi-compact-val text-med">{replaySummary.medium_count}</div>
            <div className="kpi-compact-lbl text-med">MEDIUM (30-50m)</div>
          </div>
        </div>

        <div className="kpi-compact-item">
          <div className="kpi-icon-pill" style={{ background: 'rgba(16, 185, 129, 0.12)' }}>
            <CheckCircle size={15} color="#10b981" />
          </div>
          <div>
            <div className="kpi-compact-val text-low">{replaySummary.low_count}</div>
            <div className="kpi-compact-lbl text-low">LOW (&ge;50m)</div>
          </div>
        </div>
      </div>
    );
  }

  const testMAE = modelInfo?.final_test_metrics?.mae
    ? `${modelInfo.final_test_metrics.mae.toFixed(2)} mph`
    : '3.25 mph';
  const testR2 = modelInfo?.final_test_metrics?.r2
    ? modelInfo.final_test_metrics.r2.toFixed(3)
    : '0.805';

  return (
    <div className="kpi-compact-bar">
      <div className="kpi-compact-item">
        <div className="kpi-icon-pill">
          <Radio size={15} color="#38bdf8" />
        </div>
        <div>
          <div className="kpi-compact-val">{totalSensors || 207}</div>
          <div className="kpi-compact-lbl">Sensors</div>
        </div>
      </div>

      <div className="kpi-compact-item">
        <div className="kpi-icon-pill">
          <Clock size={15} color="#818cf8" />
        </div>
        <div>
          <div className="kpi-compact-val">15 min</div>
          <div className="kpi-compact-lbl">Forecast</div>
        </div>
      </div>

      <div className="kpi-compact-item">
        <div className="kpi-icon-pill">
          <Target size={15} color="#34d399" />
        </div>
        <div>
          <div className="kpi-compact-val">{testMAE}</div>
          <div className="kpi-compact-lbl">MAE</div>
        </div>
      </div>

      <div className="kpi-compact-item">
        <div className="kpi-icon-pill">
          <TrendingUp size={15} color="#fbbf24" />
        </div>
        <div>
          <div className="kpi-compact-val">{testR2}</div>
          <div className="kpi-compact-lbl">R²</div>
        </div>
      </div>
    </div>
  );
};

export default SummaryCards;
