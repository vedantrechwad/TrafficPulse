import { useState, useEffect, useRef, useCallback } from 'react';
import { Header } from './components/Header';
import { SummaryCards } from './components/SummaryCards';
import { TrafficMap } from './components/TrafficMap';
import { ReplayControls } from './components/ReplayControls';
import { WhatIfScenarioPanel } from './components/WhatIfScenarioPanel';
import { SelectedSensorBanner } from './components/SelectedSensorBanner';
import { PropagationPanel } from './components/PropagationPanel';
import { SpeedChart } from './components/SpeedChart';
import { ScalabilityChart } from './components/ScalabilityChart';
import { ModelStats } from './components/ModelStats';

import type {
  SensorObservation,
  PredictionResponse,
  ModelMetadata,
  HistoryPoint,
  PropagationResponse,
  DashboardMode,
  ReplayAvailableRangeResponse,
  ReplaySummaryResponse,
  ScenarioResponse,
} from './types/traffic';

import {
  fetchHealth,
  fetchModelInfo,
  fetchSensorObservations,
  fetchSensorHistory,
  predictTrafficSpeed,
  fetchSensorPropagation,
  fetchReplayAvailableRange,
  fetchReplaySnapshot,
  fetchReplaySummary,
} from './services/api';

export function App() {
  const [apiConnected, setApiConnected] = useState<boolean>(false);
  const [mode, setMode] = useState<DashboardMode>('replay');
  const [modelInfo, setModelInfo] = useState<ModelMetadata | null>(null);

  // Core Sensors & Selection State
  const [baselineSensors, setBaselineSensors] = useState<SensorObservation[]>([]);
  const [sensors, setSensors] = useState<SensorObservation[]>([]);
  const [selectedSensor, setSelectedSensor] = useState<SensorObservation | null>(null);
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [propagation, setPropagation] = useState<PropagationResponse | null>(null);

  const [loadingSensors, setLoadingSensors] = useState<boolean>(true);
  const [loadingPrediction, setLoadingPrediction] = useState<boolean>(false);
  const [predictionError, setPredictionError] = useState<string | null>(null);
  const [loadingPropagation, setLoadingPropagation] = useState<boolean>(false);
  const [propagationError, setPropagationError] = useState<string | null>(null);
  const [showNetwork, setShowNetwork] = useState<boolean>(true);

  // ----------------------------------------------------
  // Historical Replay Mode State
  // ----------------------------------------------------
  const [availableRange, setAvailableRange] = useState<ReplayAvailableRangeResponse | null>(null);
  const [currentDate, setCurrentDate] = useState<string>('2012-06-09');
  const [timestamps, setTimestamps] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [replaySummary, setReplaySummary] = useState<ReplaySummaryResponse | null>(null);
  const replayTimerRef = useRef<any>(null);

  // ----------------------------------------------------
  // What-If Scenario Mode State
  // ----------------------------------------------------
  const [scenarioResult, setScenarioResult] = useState<ScenarioResponse | null>(null);

  // Initial Load: Health, Model, Baseline Telemetry, and Replay Metadata
  useEffect(() => {
    let isMounted = true;

    async function initializeDashboard() {
      try {
        // 1. Check API Health
        const health = await fetchHealth();
        if (isMounted) setApiConnected(health.status === 'healthy');

        // 2. Fetch Model Metadata
        const meta = await fetchModelInfo();
        if (isMounted) setModelInfo(meta);

        // 3. Fetch 207 Baseline Sensor Observations
        const obs = await fetchSensorObservations();
        if (isMounted) {
          setBaselineSensors(obs);
          setSensors(obs);
          setLoadingSensors(false);

          const defaultSensor = obs.find((s) => s.sensor_id === '716955') || obs[0];
          if (defaultSensor) {
            handleSensorSelection(defaultSensor);
          }
        }

        // 4. Fetch Replay Available Range
        const range = await fetchReplayAvailableRange();
        if (isMounted) {
          setAvailableRange(range);
          const initialDate = range.available_dates.includes('2012-06-09')
            ? '2012-06-09'
            : range.available_dates[0] || '2012-06-09';
          setCurrentDate(initialDate);
          const tsList = range.timestamps_by_date[initialDate] || [];
          setTimestamps(tsList);
          if (tsList.length > 0) {
            loadReplayStep(tsList[0]);
          }
        }
      } catch (err: any) {
        console.error('Initialization error:', err);
        if (isMounted) {
          setApiConnected(false);
          setLoadingSensors(false);
        }
      }
    }

    initializeDashboard();

    const interval = setInterval(async () => {
      try {
        const h = await fetchHealth();
        if (isMounted) setApiConnected(h.status === 'healthy');
      } catch {
        if (isMounted) setApiConnected(false);
      }
    }, 30000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Sensor Selection Handler
  const handleSensorSelection = async (sensor: SensorObservation) => {
    setSelectedSensor(sensor);
    setLoadingPrediction(true);
    setPredictionError(null);
    setLoadingPropagation(true);
    setPropagationError(null);

    const activeTimestamp = mode === 'replay' && timestamps[currentIndex] ? timestamps[currentIndex] : sensor.timestamp;

    // 1. Live Spark ML 15-minute prediction
    const predPromise = predictTrafficSpeed({
      timestamp: activeTimestamp,
      sensor_id: sensor.sensor_id,
      speed: sensor.speed,
      speed_lag_1: sensor.speed_lag_1,
      speed_lag_2: sensor.speed_lag_2,
      speed_lag_3: sensor.speed_lag_3,
      rolling_mean_3: sensor.rolling_mean_3,
    })
      .then((res) => {
        setPrediction(res);
        setLoadingPrediction(false);
      })
      .catch((err) => {
        console.error('Prediction error:', err);
        setPredictionError(err.message || 'Failed to generate prediction');
        setPrediction(null);
        setLoadingPrediction(false);
      });

    // 2. Chronological speed history with active timestamp context
    const histPromise = fetchSensorHistory(sensor.sensor_id, activeTimestamp)
      .then((res) => {
        setHistory(res.history);
      })
      .catch((err) => {
        console.error('History error:', err);
        setHistory([]);
      });

    // 3. Network propagation analysis with active timestamp context
    const propPromise = fetchSensorPropagation(sensor.sensor_id, activeTimestamp)
      .then((res) => {
        setPropagation(res);
        setLoadingPropagation(false);
      })
      .catch((err) => {
        console.error('Propagation error:', err);
        setPropagationError(err.message || 'Failed to fetch network propagation');
        setPropagation(null);
        setLoadingPropagation(false);
      });

    await Promise.allSettled([predPromise, histPromise, propPromise]);
  };

  // ----------------------------------------------------
  // Replay Step Loader
  // ----------------------------------------------------
  const loadReplayStep = useCallback(
    async (timestamp: string) => {
      try {
        const [snapRes, sumRes] = await Promise.all([
          fetchReplaySnapshot(timestamp),
          fetchReplaySummary(timestamp),
        ]);

        // Map replay sensor observations to standard SensorObservation format
        const updatedSensors: SensorObservation[] = snapRes.sensors.map((s) => ({
          sensor_id: s.sensor_id,
          latitude: s.latitude,
          longitude: s.longitude,
          timestamp: snapRes.timestamp,
          speed: s.speed,
          speed_lag_1: s.speed_lag_1,
          speed_lag_2: s.speed_lag_2,
          speed_lag_3: s.speed_lag_3,
          rolling_mean_3: s.rolling_mean_3,
          congestion_level: s.congestion_level,
        }));

        setSensors(updatedSensors);
        setReplaySummary(sumRes);

        // Keep selected sensor synchronized with current replay timestep
        setSelectedSensor((prev) => {
          const targetId = prev ? prev.sensor_id : '716955';
          const match = snapRes.sensors.find((s) => s.sensor_id === targetId);
          if (match) {
            // Also update the prediction response object directly from the model output in snapshot
            setPrediction({
              sensor_id: match.sensor_id,
              timestamp: snapRes.timestamp,
              current_speed_mph: match.speed,
              predicted_speed_15min_mph: match.predicted_speed_15min,
              speed_change_mph: match.speed_change,
              congestion_level: match.predicted_congestion_level,
              prediction_horizon_minutes: 15,
            });

            return {
              sensor_id: match.sensor_id,
              latitude: match.latitude,
              longitude: match.longitude,
              timestamp: snapRes.timestamp,
              speed: match.speed,
              speed_lag_1: match.speed_lag_1,
              speed_lag_2: match.speed_lag_2,
              speed_lag_3: match.speed_lag_3,
              rolling_mean_3: match.rolling_mean_3,
              congestion_level: match.congestion_level,
            };
          }
          return prev;
        });

        // Synchronize propagation network state dynamically from active snapshot
        setPropagation((prevProp) => {
          if (!prevProp) return prevProp;
          const obsMap = new Map(updatedSensors.map((s) => [s.sensor_id, s]));
          const targetObs = obsMap.get(prevProp.sensor_id);

          let highCount = 0;
          let medCount = 0;
          let lowCount = 0;
          let totalWeightedState = 0;
          let totalWeight = 0;
          const stateWeights: Record<string, number> = { LOW: 0.0, MEDIUM: 0.5, HIGH: 1.0 };

          const updatedNeighbors = prevProp.neighbors.map((n) => {
            const curr = obsMap.get(n.sensor_id);
            const speed = curr ? curr.speed : n.speed_mph;
            const cong = curr ? curr.congestion_level : n.congestion_level;
            if (cong === 'HIGH') highCount++;
            else if (cong === 'MEDIUM') medCount++;
            else lowCount++;

            totalWeightedState += n.weight * (stateWeights[cong] ?? 0.0);
            totalWeight += n.weight;

            return {
              ...n,
              speed_mph: speed,
              congestion_level: cong,
            };
          });

          const weightedScore = totalWeight > 0 ? Number((totalWeightedState / totalWeight).toFixed(2)) : 0;

          return {
            ...prevProp,
            sensor_speed_mph: targetObs ? targetObs.speed : prevProp.sensor_speed_mph,
            sensor_congestion: targetObs ? targetObs.congestion_level : prevProp.sensor_congestion,
            high_count: highCount,
            medium_count: medCount,
            low_count: lowCount,
            weighted_congestion_score: weightedScore,
            neighbors: updatedNeighbors,
          };
        });
      } catch (err) {
        console.error('Error loading replay snapshot:', err);
      }
    },
    []
  );

  // When date changes, update timestamp list and reset index
  const handleSelectReplayDate = (newDate: string) => {
    setIsPlaying(false);
    setCurrentDate(newDate);
    if (availableRange) {
      const tsList = availableRange.timestamps_by_date[newDate] || [];
      setTimestamps(tsList);
      setCurrentIndex(0);
      if (tsList.length > 0) {
        loadReplayStep(tsList[0]);
        if (selectedSensor) {
          fetchSensorHistory(selectedSensor.sensor_id, tsList[0])
            .then((r) => setHistory(r.history))
            .catch(() => {});
        }
      }
    }
  };

  const handleSelectReplayIndex = (idx: number) => {
    if (idx >= 0 && idx < timestamps.length) {
      setCurrentIndex(idx);
      loadReplayStep(timestamps[idx]);
      if (selectedSensor) {
        fetchSensorHistory(selectedSensor.sensor_id, timestamps[idx])
          .then((r) => setHistory(r.history))
          .catch(() => {});
      }
    }
  };

  const handlePrevReplay = () => {
    if (currentIndex > 0) {
      const newIdx = currentIndex - 1;
      setCurrentIndex(newIdx);
      loadReplayStep(timestamps[newIdx]);
      if (selectedSensor) {
        fetchSensorHistory(selectedSensor.sensor_id, timestamps[newIdx])
          .then((r) => setHistory(r.history))
          .catch(() => {});
      }
    }
  };

  const handleNextReplay = () => {
    if (currentIndex < timestamps.length - 1) {
      const newIdx = currentIndex + 1;
      setCurrentIndex(newIdx);
      loadReplayStep(timestamps[newIdx]);
      if (selectedSensor) {
        fetchSensorHistory(selectedSensor.sensor_id, timestamps[newIdx])
          .then((r) => setHistory(r.history))
          .catch(() => {});
      }
    } else {
      setIsPlaying(false);
    }
  };

  const handleTogglePlay = () => {
    setIsPlaying((prev) => {
      const next = !prev;
      if (!next && selectedSensor && timestamps[currentIndex]) {
        fetchSensorHistory(selectedSensor.sensor_id, timestamps[currentIndex])
          .then((r) => setHistory(r.history))
          .catch(() => {});
      }
      return next;
    });
  };

  // Replay animation timer loop
  useEffect(() => {
    if (isPlaying) {
      const intervalMs = Math.max(200, Math.floor(2200 / playbackSpeed));
      replayTimerRef.current = setInterval(() => {
        setCurrentIndex((prevIdx) => {
          if (prevIdx < timestamps.length - 1) {
            const nextIdx = prevIdx + 1;
            loadReplayStep(timestamps[nextIdx]);
            return nextIdx;
          } else {
            setIsPlaying(false);
            return prevIdx;
          }
        });
      }, intervalMs);
    } else {
      if (replayTimerRef.current) {
        clearInterval(replayTimerRef.current);
      }
    }

    return () => {
      if (replayTimerRef.current) {
        clearInterval(replayTimerRef.current);
      }
    };
  }, [isPlaying, playbackSpeed, timestamps, loadReplayStep]);

  // Mode Switching
  const handleSelectMode = (newMode: DashboardMode) => {
    setIsPlaying(false);
    setMode(newMode);
    if (newMode === 'scenario') {
      // Restore baseline observations for scenario baseline
      setSensors(baselineSensors);
    } else {
      // Re-apply current replay snapshot
      if (timestamps.length > 0 && timestamps[currentIndex]) {
        loadReplayStep(timestamps[currentIndex]);
      }
    }
  };

  const handleSelectNeighbor = (neighborId: string) => {
    const target = sensors.find((s) => s.sensor_id === neighborId);
    if (target) {
      handleSensorSelection(target);
    }
  };

  const handleToggleNetwork = () => {
    setShowNetwork((prev) => !prev);
  };

  // What-If Scenario Result Handler
  const handleScenarioAnalyzed = (result: ScenarioResponse) => {
    setScenarioResult(result);
    // Find matching sensor coordinates to set selected sensor
    const match = sensors.find((s) => s.sensor_id === result.sensor_id);
    if (match) {
      setSelectedSensor({
        ...match,
        speed: result.current_speed_mph,
        congestion_level: result.current_congestion_level,
      });
    }
  };

  return (
    <div className="app-container">
      {/* 1. Header with Interactive Mode Switcher */}
      <Header apiConnected={apiConnected} mode={mode} onSelectMode={handleSelectMode} />

      {/* 2. Top Summary KPI Cards (Shows live Replay Snapshot metrics when in Replay mode) */}
      <SummaryCards
        totalSensors={sensors.length}
        modelInfo={modelInfo}
        replaySummary={mode === 'replay' ? replaySummary : null}
      />

      {loadingSensors && (
        <div className="loading-banner">
          <span className="spinner mini"></span>
          <span>Loading METR-LA telemetry and sensor network...</span>
        </div>
      )}

      {/* 3. Replay Mode: Playback Control Bar */}
      {mode === 'replay' && availableRange && (
        <ReplayControls
          availableDates={availableRange.available_dates}
          currentDate={currentDate}
          onSelectDate={handleSelectReplayDate}
          timestamps={timestamps}
          currentTimestamp={timestamps[currentIndex] || ''}
          currentIndex={currentIndex}
          onSelectIndex={handleSelectReplayIndex}
          isPlaying={isPlaying}
          onTogglePlay={handleTogglePlay}
          onPrev={handlePrevReplay}
          onNext={handleNextReplay}
          playbackSpeed={playbackSpeed}
          onChangeSpeed={setPlaybackSpeed}
          summary={replaySummary}
        />
      )}

      {/* 4. What-If Scenario Mode: Simulation Input Form & Scenario Results */}
      {mode === 'scenario' && (
        <WhatIfScenarioPanel
          sensors={baselineSensors.length > 0 ? baselineSensors : sensors}
          selectedSensorId={selectedSensor?.sensor_id || '716955'}
          onSelectSensorId={(id) => {
            const target = sensors.find((s) => s.sensor_id === id);
            if (target) handleSensorSelection(target);
          }}
          scenarioResult={scenarioResult}
          onScenarioAnalyzed={handleScenarioAnalyzed}
        />
      )}

      {/* 5. HERO MAP (Full width, interactive simulation canvas) */}
      <TrafficMap
        sensors={sensors}
        selectedSensor={selectedSensor}
        propagation={propagation}
        showNetwork={showNetwork}
        onToggleNetwork={handleToggleNetwork}
        onSelectSensor={handleSensorSelection}
        scenarioMode={mode === 'scenario'}
        scenarioResult={scenarioResult}
      />

      {/* 6. Selected Sensor & 15-Minute Forecast Horizontal Banner (Replay Mode) */}
      {mode === 'replay' && (
        <SelectedSensorBanner
          selectedSensor={selectedSensor}
          prediction={prediction}
          loadingPrediction={loadingPrediction}
          predictionError={predictionError}
        />
      )}

      {/* 7. Middle Grid: Network Propagation & Speed History (Replay Mode) */}
      {mode === 'replay' && (
        <div className="middle-grid">
          <PropagationPanel
            propagation={propagation}
            loading={loadingPropagation}
            error={propagationError}
            selectedSensorId={selectedSensor?.sensor_id || null}
            showNetwork={showNetwork}
            onToggleNetwork={handleToggleNetwork}
            onSelectNeighbor={handleSelectNeighbor}
          />

          <SpeedChart
            history={history}
            prediction={prediction}
            sensorId={selectedSensor?.sensor_id || ''}
          />
        </div>
      )}

      {/* 8. Bottom Grid: Spark Scalability Benchmark & Model Details */}
      <div className="bottom-grid">
        <ScalabilityChart />
        <ModelStats modelInfo={modelInfo} />
      </div>
    </div>
  );
}

export default App;
