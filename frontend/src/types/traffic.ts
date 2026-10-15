export type CongestionLevel = 'LOW' | 'MEDIUM' | 'HIGH';

export interface SensorLocation {
  sensor_id: string;
  latitude: number;
  longitude: number;
}

export interface SensorObservation {
  sensor_id: string;
  latitude: number;
  longitude: number;
  timestamp: string;
  speed: number;
  speed_lag_1: number;
  speed_lag_2: number;
  speed_lag_3: number;
  rolling_mean_3: number;
  congestion_level: CongestionLevel;
}

export interface PredictionRequest {
  timestamp: string;
  sensor_id: string;
  speed: number;
  speed_lag_1: number;
  speed_lag_2: number;
  speed_lag_3: number;
  rolling_mean_3: number;
}

export interface PredictionResponse {
  sensor_id: string;
  timestamp: string;
  current_speed_mph: number;
  predicted_speed_15min_mph: number;
  speed_change_mph: number;
  congestion_level: CongestionLevel;
  prediction_horizon_minutes: number;
}

export interface HealthResponse {
  status: string;
  model_loaded: boolean;
  model_type: string;
  prediction_horizon_minutes: number;
}

export interface ModelMetadata {
  project: string;
  model_type: string;
  prediction_horizon: string;
  features: string[];
  target: string;
  model_parameters: {
    numTrees?: number;
    maxDepth?: number;
    seed?: number;
    maxIter?: number;
    regParam?: number;
  };
  training_timestamp: string;
  splits: {
    train_period: string;
    val_period: string;
    test_period: string;
    train_count: number;
    val_count: number;
    test_count: number;
  };
  validation_comparison: {
    linear_regression: { mae: number; rmse: number; r2: number };
    random_forest: { mae: number; rmse: number; r2: number };
  };
  final_test_metrics: {
    mae: number;
    rmse: number;
    r2: number;
  };
}

export interface HistoryPoint {
  timestamp: string;
  speed: number;
  future_speed_15min?: number | null;
}

export interface SensorHistoryResponse {
  sensor_id: string;
  history: HistoryPoint[];
}

export interface PropagationNeighbor {
  sensor_id: string;
  weight: number;
  speed_mph: number;
  congestion_level: CongestionLevel;
  latitude: number;
  longitude: number;
}

export interface PropagationResponse {
  sensor_id: string;
  sensor_speed_mph: number;
  sensor_congestion: CongestionLevel;
  neighbor_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  weighted_congestion_score: number;
  neighbors: PropagationNeighbor[];
}

export interface BenchmarkRecord {
  data_fraction: string;
  records: number;
  processing_time_seconds: number;
  records_per_second: number;
}

export interface BenchmarkResponse {
  environment: string;
  spark_mode: string;
  workload: string;
  results: BenchmarkRecord[];
}

export type DashboardMode = 'replay' | 'scenario';

export interface ReplaySensorObservation {
  sensor_id: string;
  latitude: number;
  longitude: number;
  speed: number;
  speed_lag_1: number;
  speed_lag_2: number;
  speed_lag_3: number;
  rolling_mean_3: number;
  predicted_speed_15min: number;
  speed_change: number;
  congestion_level: CongestionLevel;
  predicted_congestion_level: CongestionLevel;
}

export interface ReplayAvailableRangeResponse {
  start: string;
  end: string;
  interval_minutes: number;
  total_snapshots: number;
  available_dates: string[];
  timestamps_by_date: Record<string, string[]>;
}

export interface ReplaySnapshotResponse {
  timestamp: string;
  total_sensors: number;
  sensors: ReplaySensorObservation[];
}

export interface ReplaySummaryResponse {
  timestamp: string;
  total_sensors: number;
  low_count: number;
  medium_count: number;
  high_count: number;
  average_speed: number;
  predicted_slowdowns: number;
}

export interface ScenarioRequest {
  sensor_id: string;
  timestamp: string;
  speed: number;
  speed_lag_1: number;
  speed_lag_2: number;
  speed_lag_3: number;
  rolling_mean_3?: number;
}

export interface ScenarioResponse {
  sensor_id: string;
  timestamp: string;
  current_speed_mph: number;
  predicted_speed_15min_mph: number;
  speed_change_mph: number;
  current_congestion_level: CongestionLevel;
  predicted_congestion_level: CongestionLevel;
  connected_sensors_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  weighted_congestion_indicator: number;
  neighbors: PropagationNeighbor[];
  disclaimer: string;
}


