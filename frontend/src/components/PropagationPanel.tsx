import React from 'react';
import type { PropagationResponse, CongestionLevel } from '../types/traffic';
import { Network, EyeOff } from 'lucide-react';

interface PropagationPanelProps {
  propagation: PropagationResponse | null;
  loading: boolean;
  error: string | null;
  selectedSensorId: string | null;
  showNetwork: boolean;
  onToggleNetwork: () => void;
  onSelectNeighbor: (sensorId: string) => void;
}

export const PropagationPanel: React.FC<PropagationPanelProps> = ({
  propagation,
  loading,
  error,
  selectedSensorId,
  showNetwork,
  onToggleNetwork,
  onSelectNeighbor,
}) => {
  const getCongestionBadge = (level: CongestionLevel | string) => {
    switch (level) {
      case 'HIGH':
        return <span className="badge-congestion badge-high">HIGH</span>;
      case 'MEDIUM':
        return <span className="badge-congestion badge-med">MED</span>;
      case 'LOW':
      default:
        return <span className="badge-congestion badge-low">LOW</span>;
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 0.66) return '#ef4444';
    if (score >= 0.33) return '#f59e0b';
    return '#10b981';
  };

  return (
    <div className="card propagation-compact-card">
      <div className="card-header-bar">
        <div className="card-title">
          <Network size={16} color="#38bdf8" />
          <span>Network Propagation</span>
          {selectedSensorId && <span className="badge-count">Station #{selectedSensorId}</span>}
        </div>
        <button
          type="button"
          onClick={onToggleNetwork}
          className={`network-toggle-btn ${showNetwork ? 'active' : ''}`}
          title="Toggle network propagation overlay on map"
        >
          {showNetwork ? <EyeOff size={12} /> : <Network size={12} />}
          <span>{showNetwork ? 'Hide Network' : 'Show Network'}</span>
        </button>
      </div>

      <div className="card-compact-body">
        {loading && (
          <div className="panel-loading-state">
            <span className="spinner mini"></span>
            <span>Querying adjacency graph for #{selectedSensorId}...</span>
          </div>
        )}

        {error && !loading && (
          <div className="panel-error-alert">{error}</div>
        )}

        {!loading && !error && !propagation && (
          <div className="panel-empty-state">
            Select a station on the map to evaluate downstream graph propagation.
          </div>
        )}

        {!loading && !error && propagation && (
          <>
            {/* Compact Summary Row */}
            <div className="propagation-summary-row">
              <div className="prop-summary-pill">
                <span className="prop-summary-lbl">Connected</span>
                <span className="prop-summary-val">{propagation.neighbor_count}</span>
              </div>
              <div className="prop-summary-pill">
                <span className="prop-summary-lbl text-high">HIGH</span>
                <span className="prop-summary-val text-high">{propagation.high_count}</span>
              </div>
              <div className="prop-summary-pill">
                <span className="prop-summary-lbl text-med">MEDIUM</span>
                <span className="prop-summary-val text-med">{propagation.medium_count}</span>
              </div>
              <div className="prop-summary-pill">
                <span className="prop-summary-lbl text-low">LOW</span>
                <span className="prop-summary-val text-low">{propagation.low_count}</span>
              </div>
              <div className="prop-summary-pill">
                <span className="prop-summary-lbl">Score</span>
                <span
                  className="prop-summary-val"
                  style={{ color: getScoreColor(propagation.weighted_congestion_score) }}
                >
                  {propagation.weighted_congestion_score.toFixed(2)}
                </span>
              </div>
            </div>

            {/* Connected Neighbors Table */}
            {propagation.neighbors.length > 0 ? (
              <div className="prop-table-wrapper">
                <table className="prop-table">
                  <thead>
                    <tr>
                      <th>Neighbor</th>
                      <th>Graph Weight</th>
                      <th>Speed</th>
                      <th>Status</th>
                      <th style={{ textAlign: 'right' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {propagation.neighbors.map((n) => (
                      <tr
                        key={n.sensor_id}
                        className="prop-table-row"
                        onClick={() => onSelectNeighbor(n.sensor_id)}
                      >
                        <td style={{ fontWeight: 600, color: '#f8fafc' }}>#{n.sensor_id}</td>
                        <td style={{ fontFamily: 'monospace', color: '#94a3b8' }}>
                          {n.weight.toFixed(4)}
                        </td>
                        <td style={{ color: '#f8fafc' }}>{n.speed_mph.toFixed(1)} mph</td>
                        <td>{getCongestionBadge(n.congestion_level)}</td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            type="button"
                            className="inspect-btn"
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectNeighbor(n.sensor_id);
                            }}
                          >
                            Inspect
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="prop-no-neighbors">
                No outgoing connections in adjacency graph (terminal/sink station).
              </div>
            )}

            {/* Single-line scientific disclaimer */}
            <div className="prop-disclaimer">
              Graph connectivity indicates network association, not causality.
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default PropagationPanel;
