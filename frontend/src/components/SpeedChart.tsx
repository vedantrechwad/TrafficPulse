import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceDot,
} from 'recharts';
import type { HistoryPoint, PredictionResponse } from '../types/traffic';
import { LineChart as ChartIcon } from 'lucide-react';

interface SpeedChartProps {
  history: HistoryPoint[];
  prediction: PredictionResponse | null;
  sensorId: string;
}

export const SpeedChart: React.FC<SpeedChartProps> = ({ history, prediction, sensorId }) => {
  if (!history || history.length === 0) {
    return (
      <div className="card speed-chart-card">
        <div className="card-header-bar">
          <div>
            <div className="card-title">
              <ChartIcon size={16} color="#38bdf8" />
              <span>Speed History</span>
              {sensorId && <span className="badge-count">Station #{sensorId}</span>}
            </div>
            <div className="card-subtitle">5-minute observations • 15-minute forecast</div>
          </div>
        </div>
        <div className="panel-empty-state" style={{ height: '220px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          Select a sensor to render actual speed history and forecast point.
        </div>
      </div>
    );
  }

  // Format data for chart
  const formattedData = history.map((pt) => {
    const timeParts = pt.timestamp.split(' ');
    const timeLabel = timeParts.length > 1 ? timeParts[1].substring(0, 5) : pt.timestamp;
    return {
      time: timeLabel,
      fullTime: pt.timestamp,
      observedSpeed: pt.speed,
      targetSpeed: pt.future_speed_15min,
    };
  });

  // Calculate prediction horizon point if available
  const lastPoint = formattedData[formattedData.length - 1];
  const predictedValue = prediction ? prediction.predicted_speed_15min_mph : null;

  return (
    <div className="card speed-chart-card">
      <div className="card-header-bar">
        <div>
          <div className="card-title">
            <ChartIcon size={16} color="#38bdf8" />
            <span>Speed History</span>
            {sensorId && <span className="badge-count">Station #{sensorId}</span>}
          </div>
          <div className="card-subtitle">5-minute observations • 15-minute forecast</div>
        </div>
      </div>

      <div className="speed-chart-wrapper">
        <ResponsiveContainer width="100%" height={230}>
          <LineChart data={formattedData} margin={{ top: 10, right: 15, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2d44" vertical={false} />
            <XAxis
              dataKey="time"
              stroke="#64748b"
              fontSize={10}
              tickLine={false}
              axisLine={{ stroke: '#1f2d44' }}
            />
            <YAxis
              stroke="#64748b"
              fontSize={10}
              tickLine={false}
              domain={[20, 80]}
              axisLine={{ stroke: '#1f2d44' }}
              tickFormatter={(v) => `${v}m`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1e293b',
                borderColor: '#334155',
                borderRadius: '8px',
                fontSize: '11px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
              }}
              formatter={(value: any, name: any) => [
                `${Number(value).toFixed(2)} mph`,
                name === 'observedSpeed' ? 'Observed Speed' : 'Actual Target (+15m)',
              ]}
              labelFormatter={(label, items) => {
                const item = items && items[0] ? (items[0].payload as any) : null;
                return item ? item.fullTime : label;
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px', paddingTop: '2px' }}
              formatter={(val) => (val === 'observedSpeed' ? 'Observed Speed' : 'Actual (+15m)')}
            />
            <Line
              type="monotone"
              dataKey="observedSpeed"
              stroke="#38bdf8"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, stroke: '#38bdf8', strokeWidth: 2, fill: '#fff' }}
            />
            <Line
              type="monotone"
              dataKey="targetSpeed"
              stroke="#818cf8"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
            />

            {/* Visual marker for ML prediction at horizon */}
            {predictedValue !== null && lastPoint && (
              <ReferenceDot
                x={lastPoint.time}
                y={predictedValue}
                r={5.5}
                fill="#10b981"
                stroke="#ffffff"
                strokeWidth={2}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default SpeedChart;
