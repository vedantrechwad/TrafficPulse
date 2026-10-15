import React, { useState, useEffect } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import type { BenchmarkResponse } from '../types/traffic';
import { fetchScalabilityBenchmark } from '../services/api';
import { Cpu } from 'lucide-react';

export const ScalabilityChart: React.FC = () => {
  const [data, setData] = useState<BenchmarkResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchScalabilityBenchmark()
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load scalability benchmark data:', err);
        setError(err.message || 'Could not load benchmark metrics');
        setLoading(false);
      });
  }, []);

  const formatRecords = (val: number) => {
    if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
    if (val >= 1_000) return `${(val / 1_000).toFixed(0)}k`;
    return `${val}`;
  };

  return (
    <div className="card scalability-compact-card">
      <div className="card-header-bar">
        <div>
          <div className="card-title">
            <Cpu size={16} color="#10b981" />
            <span>Spark Scalability</span>
            {data && <span className="badge-count">{data.spark_mode}</span>}
          </div>
          <div className="card-subtitle">Empirical runtime vs dataset volume</div>
        </div>
      </div>

      <div className="card-compact-body">
        {loading && (
          <div className="panel-loading-state">
            <span className="spinner mini"></span>
            <span>Loading empirical Spark benchmark measurements...</span>
          </div>
        )}

        {error && <div className="panel-error-alert">{error}</div>}

        {!loading && !error && data && (
          <>
            {/* Chart: Height ~180px */}
            <div style={{ height: '175px', width: '100%', marginBottom: '0.75rem' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.results} margin={{ top: 8, right: 20, left: -10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2d44" vertical={false} />
                  <XAxis
                    dataKey="records"
                    stroke="#64748b"
                    fontSize={10}
                    tickFormatter={formatRecords}
                    axisLine={{ stroke: '#1f2d44' }}
                    tickLine={false}
                  />
                  <YAxis
                    stroke="#64748b"
                    fontSize={10}
                    unit="s"
                    domain={[0, 'auto']}
                    axisLine={{ stroke: '#1f2d44' }}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      borderColor: '#334155',
                      borderRadius: '8px',
                      color: '#f8fafc',
                      fontSize: '11px',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                    }}
                    formatter={(value: any, name: any) => {
                      if (name === 'processing_time_seconds') return [`${value} s`, 'Runtime'];
                      return [value, name];
                    }}
                    labelFormatter={(label: any) => {
                      const item = data.results.find((r) => r.records === label);
                      return item ? `${item.data_fraction} (${Number(label).toLocaleString()} records)` : `${label} records`;
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="processing_time_seconds"
                    stroke="#38bdf8"
                    strokeWidth={2}
                    dot={{ fill: '#38bdf8', r: 3.5 }}
                    activeDot={{ r: 5, fill: '#60a5fa' }}
                    name="processing_time_seconds"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Compact Benchmark Table */}
            <div className="prop-table-wrapper" style={{ maxHeight: '140px' }}>
              <table className="prop-table">
                <thead>
                  <tr>
                    <th>Fraction</th>
                    <th>Records</th>
                    <th>Time</th>
                    <th style={{ textAlign: 'right' }}>Throughput</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((r) => (
                    <tr key={r.data_fraction}>
                      <td style={{ fontWeight: 600, color: '#38bdf8' }}>{r.data_fraction}</td>
                      <td style={{ color: '#f8fafc' }}>{r.records.toLocaleString()}</td>
                      <td style={{ fontFamily: 'monospace', color: '#f8fafc' }}>
                        {r.processing_time_seconds.toFixed(3)}s
                      </td>
                      <td
                        style={{
                          textAlign: 'right',
                          color: '#10b981',
                          fontFamily: 'monospace',
                          fontWeight: 600,
                        }}
                      >
                        {r.records_per_second.toLocaleString()} rec/s
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="prop-disclaimer">
              Distributed PySpark pipeline tested on {data.environment}.
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default ScalabilityChart;
