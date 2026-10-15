import React from 'react';
import { Play, Pause, SkipBack, SkipForward, Clock, Calendar, Gauge } from 'lucide-react';
import type { ReplaySummaryResponse } from '../types/traffic';

interface ReplayControlsProps {
  availableDates: string[];
  currentDate: string;
  onSelectDate: (date: string) => void;
  timestamps: string[];
  currentTimestamp: string;
  currentIndex: number;
  onSelectIndex: (index: number) => void;
  isPlaying: boolean;
  onTogglePlay: () => void;
  onPrev: () => void;
  onNext: () => void;
  playbackSpeed: number;
  onChangeSpeed: (speed: number) => void;
  summary: ReplaySummaryResponse | null;
}

export const ReplayControls: React.FC<ReplayControlsProps> = ({
  availableDates,
  currentDate,
  onSelectDate,
  timestamps,
  currentTimestamp,
  currentIndex,
  onSelectIndex,
  isPlaying,
  onTogglePlay,
  onPrev,
  onNext,
  playbackSpeed,
  onChangeSpeed,
  summary,
}) => {
  const startTime = timestamps.length > 0 ? timestamps[0].substring(11, 16) : '--:--';
  const endTime = timestamps.length > 0 ? timestamps[timestamps.length - 1].substring(11, 16) : '--:--';
  const curTime = currentTimestamp ? currentTimestamp.substring(11, 16) : '--:--';

  const dateLabels: Record<string, string> = {
    '2012-06-09': '2012-06-09 (Weekend Loop)',
    '2012-06-27': '2012-06-27 (Peak Rush Hour)',
    '2012-06-02': '2012-06-02 (24-Hour Cycle)',
  };

  return (
    <div className="card replay-controls-card">
      <div className="replay-top-bar">
        {/* Date Selector */}
        <div className="control-group">
          <Calendar size={15} color="#38bdf8" />
          <label htmlFor="replay-date-select">Date:</label>
          <select
            id="replay-date-select"
            className="control-select"
            value={currentDate}
            onChange={(e) => onSelectDate(e.target.value)}
          >
            {availableDates.map((d) => (
              <option key={d} value={d}>
                {dateLabels[d] || d}
              </option>
            ))}
          </select>
        </div>

        {/* Playback Step & Toggle Controls */}
        <div className="playback-btn-group">
          <button
            type="button"
            className="btn-playback"
            onClick={onPrev}
            disabled={currentIndex <= 0}
            title="Step backward 5 minutes"
          >
            <SkipBack size={14} />
            <span>Prev</span>
          </button>

          <button
            type="button"
            className={`btn-playback play-toggle ${isPlaying ? 'active' : ''}`}
            onClick={onTogglePlay}
            title={isPlaying ? 'Pause replay simulation' : 'Start replay simulation'}
          >
            {isPlaying ? <Pause size={15} /> : <Play size={15} />}
            <span>{isPlaying ? 'Pause' : 'Play'}</span>
          </button>

          <button
            type="button"
            className="btn-playback"
            onClick={onNext}
            disabled={currentIndex >= timestamps.length - 1}
            title="Step forward 5 minutes"
          >
            <span>Next</span>
            <SkipForward size={14} />
          </button>
        </div>

        {/* Speed Selector */}
        <div className="control-group">
          <Gauge size={15} color="#818cf8" />
          <label htmlFor="replay-speed-select">Speed:</label>
          <select
            id="replay-speed-select"
            className="control-select speed-select"
            value={playbackSpeed}
            onChange={(e) => onChangeSpeed(Number(e.target.value))}
          >
            <option value={1}>1x (Real-time pace)</option>
            <option value={2}>2x</option>
            <option value={5}>5x</option>
            <option value={10}>10x</option>
          </select>
        </div>

        {/* Current Replay Timestamp Indicator */}
        <div className="replay-timestamp-pill">
          <Clock size={13} color="#38bdf8" />
          <span className="replay-ts-val">{currentTimestamp || 'Loading...'}</span>
          <span className="replay-step-tag">
            Step {currentIndex + 1} / {timestamps.length}
          </span>
        </div>
      </div>

      {/* Timeline Range Slider */}
      <div className="replay-timeline-bar">
        <span className="timeline-bound-lbl">{startTime}</span>
        <input
          type="range"
          min={0}
          max={Math.max(0, timestamps.length - 1)}
          value={currentIndex}
          onChange={(e) => onSelectIndex(Number(e.target.value))}
          className="timeline-slider"
          aria-label="Replay timeline slider"
        />
        <span className="timeline-bound-lbl">{endTime}</span>
        <div className="timeline-current-bubble">{curTime}</div>
      </div>

      {/* Snapshot Summary Metrics Bar */}
      {summary && (
        <div className="replay-summary-strip">
          <div className="summary-strip-title">LIVE REPLAY SNAPSHOT</div>
          <div className="summary-pills-row">
            <span className="sum-pill">
              <strong>Sensors:</strong> {summary.total_sensors}
            </span>
            <span className="sum-pill">
              <strong>Avg Speed:</strong> {summary.average_speed.toFixed(1)} mph
            </span>
            <span className="sum-pill text-low">
              <strong>LOW:</strong> {summary.low_count}
            </span>
            <span className="sum-pill text-med">
              <strong>MEDIUM:</strong> {summary.medium_count}
            </span>
            <span className="sum-pill text-high">
              <strong>HIGH:</strong> {summary.high_count}
            </span>
            <span className="sum-pill highlight">
              <strong>Predicted Slowdowns:</strong> {summary.predicted_slowdowns}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReplayControls;
