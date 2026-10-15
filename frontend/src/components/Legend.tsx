import React from 'react';

export const Legend: React.FC = () => {
  return (
    <div className="map-legend">
      <div className="legend-title">Congestion Thresholds</div>
      <div className="legend-items">
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#10b981' }}></span>
          <span>LOW (&ge;50 mph)</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#f59e0b' }}></span>
          <span>MEDIUM (30-50 mph)</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#ef4444' }}></span>
          <span>HIGH (&lt;30 mph)</span>
        </div>
      </div>
    </div>
  );
};
