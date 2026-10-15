import React from 'react';
import { Database } from 'lucide-react';
import { ScalabilityChart } from './ScalabilityChart';

export const PipelineScale: React.FC = () => {
  return (
    <div className="pipeline-scale-wrapper">
      <div className="info-card">
        <h3>
          <Database size={18} color="#38bdf8" />
          <span>Pipeline Scale & Big Data Architecture</span>
        </h3>

        <table className="stats-table">
          <tbody>
            <tr>
              <td>Raw Records</td>
              <td className="stat-val">7,094,304</td>
            </tr>
            <tr>
              <td>ML-Ready Records</td>
              <td className="stat-val">6,395,849</td>
            </tr>
            <tr>
              <td>Sensors</td>
              <td className="stat-val">207</td>
            </tr>
            <tr>
              <td>Sampling Interval</td>
              <td className="stat-val">5 minutes</td>
            </tr>
            <tr>
              <td>Prediction Horizon</td>
              <td className="stat-val">15 minutes</td>
            </tr>
          </tbody>
        </table>

        <div
          style={{
            marginTop: '0.85rem',
            padding: '0.55rem 0.75rem',
            backgroundColor: 'rgba(15, 23, 42, 0.6)',
            border: '1px solid #1f2d44',
            borderRadius: '6px',
            fontSize: '0.72rem',
            color: '#94a3b8',
            lineHeight: '1.4',
          }}
        >
          Apache Spark provides the distributed processing architecture used by the pipeline. Scalability is demonstrated empirically by measuring processing behavior at increasing data volumes in Spark local mode.
        </div>
      </div>

      {/* Embedded Scalability Benchmark Chart */}
      <ScalabilityChart />
    </div>
  );
};
