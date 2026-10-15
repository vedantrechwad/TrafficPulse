import type {
  HealthResponse,
  ModelMetadata,
  PredictionRequest,
  PredictionResponse,
  SensorObservation,
  SensorHistoryResponse,
  PropagationResponse,
  BenchmarkResponse,
} from '../types/traffic';

const API_BASE_URL = import.meta.env.VITE_API_URL !== undefined
  ? import.meta.env.VITE_API_URL
  : (import.meta.env.PROD ? '' : 'http://127.0.0.1:8000');

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/api/health`);
  if (!res.ok) {
    throw new Error(`Health check failed with status ${res.status}`);
  }
  return res.json();
}

export async function fetchModelInfo(): Promise<ModelMetadata> {
  const res = await fetch(`${API_BASE_URL}/api/model-info`);
  if (!res.ok) {
    throw new Error(`Failed to load model metadata (${res.status})`);
  }
  return res.json();
}

export async function fetchSensorObservations(): Promise<SensorObservation[]> {
  const res = await fetch(`${API_BASE_URL}/api/sensor-observations`);
  if (!res.ok) {
    throw new Error(`Failed to fetch sensor observations (${res.status})`);
  }
  return res.json();
}

export async function fetchSensorHistory(sensorId: string): Promise<SensorHistoryResponse> {
  const res = await fetch(`${API_BASE_URL}/api/sensors/${sensorId}/history`);
  if (!res.ok) {
    throw new Error(`Failed to fetch history for sensor ${sensorId} (${res.status})`);
  }
  return res.json();
}

export async function predictTrafficSpeed(payload: PredictionRequest): Promise<PredictionResponse> {
  const res = await fetch(`${API_BASE_URL}/api/predict`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Prediction request failed (${res.status})`);
  }

  return res.json();
}

export async function fetchSensorPropagation(sensorId: string): Promise<PropagationResponse> {
  const res = await fetch(`${API_BASE_URL}/api/sensors/${sensorId}/propagation`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch propagation analysis for sensor ${sensorId} (${res.status})`);
  }
  return res.json();
}

export async function fetchScalabilityBenchmark(): Promise<BenchmarkResponse> {
  const res = await fetch(`${API_BASE_URL}/api/benchmark`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch scalability benchmark data (${res.status})`);
  }
  return res.json();
}

// ----------------------------------------------------
// Replay & Scenario Endpoints
// ----------------------------------------------------

export async function fetchReplayAvailableRange(): Promise<import('../types/traffic').ReplayAvailableRangeResponse> {
  const res = await fetch(`${API_BASE_URL}/api/replay/available-range`);
  if (!res.ok) {
    throw new Error(`Failed to load replay available range (${res.status})`);
  }
  return res.json();
}

export async function fetchReplaySnapshot(timestamp: string): Promise<import('../types/traffic').ReplaySnapshotResponse> {
  const res = await fetch(`${API_BASE_URL}/api/replay/snapshot?timestamp=${encodeURIComponent(timestamp)}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to load replay snapshot (${res.status})`);
  }
  return res.json();
}

export async function fetchReplaySummary(timestamp: string): Promise<import('../types/traffic').ReplaySummaryResponse> {
  const res = await fetch(`${API_BASE_URL}/api/replay/summary?timestamp=${encodeURIComponent(timestamp)}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to load replay summary (${res.status})`);
  }
  return res.json();
}

export async function analyzeScenario(payload: import('../types/traffic').ScenarioRequest): Promise<import('../types/traffic').ScenarioResponse> {
  const res = await fetch(`${API_BASE_URL}/api/scenario/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to analyze scenario (${res.status})`);
  }

  return res.json();
}


