import React from 'react';
import { Activity, History, SlidersHorizontal } from 'lucide-react';
import type { DashboardMode } from '../types/traffic';

interface HeaderProps {
  apiConnected: boolean;
  mode: DashboardMode;
  onSelectMode: (mode: DashboardMode) => void;
}

export const Header: React.FC<HeaderProps> = ({ apiConnected, mode, onSelectMode }) => {
  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="brand-icon">
          <Activity size={22} color="#fff" />
        </div>
        <div className="brand-text">
          <h1>
            Traffic<span>Pulse</span>
          </h1>
          <p>Scalable Traffic Prediction & Congestion Propagation Analysis Using Apache Spark</p>
        </div>
      </div>

      {/* Mode Switcher Tabs */}
      <div className="mode-switcher-container">
        <button
          type="button"
          className={`mode-tab-btn ${mode === 'replay' ? 'active' : ''}`}
          onClick={() => onSelectMode('replay')}
        >
          <History size={14} />
          <span>Historical Replay</span>
        </button>

        <button
          type="button"
          className={`mode-tab-btn ${mode === 'scenario' ? 'active' : ''}`}
          onClick={() => onSelectMode('scenario')}
        >
          <SlidersHorizontal size={14} />
          <span>What-If Scenario</span>
        </button>
      </div>

      <div className="header-status">
        <div className={`status-badge ${apiConnected ? 'connected' : 'offline'}`}>
          <span className="status-dot"></span>
          <span>{apiConnected ? 'API Connected' : 'API Offline'}</span>
        </div>
      </div>
    </header>
  );
};

export default Header;
