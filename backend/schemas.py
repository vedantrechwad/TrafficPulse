"""
TrafficPulse API - Pydantic Request & Response Schemas
Defines structured input validation and response contracts for prediction endpoints.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class PredictionRequest(BaseModel):
    """
    Traffic speed prediction request payload.
    Temporal features (hour, minute, day_of_week, is_weekend) are automatically
    derived by the backend from the provided timestamp.
    """
    timestamp: str = Field(
        ...,
        description="ISO timestamp of observation (e.g. '2012-06-09T02:30:00' or '2012-06-09 02:30:00')",
        examples=["2012-06-09T02:30:00"],
    )
    sensor_id: str = Field(
        ...,
        description="METR-LA traffic sensor ID string (e.g. '716955')",
        examples=["716955"],
    )
    speed: float = Field(
        ...,
        ge=0.0,
        le=150.0,
        description="Current observed traffic speed in mph",
        examples=[51.71],
    )
    speed_lag_1: float = Field(
        ...,
        ge=0.0,
        le=150.0,
        description="Traffic speed 5 minutes ago (t-1) in mph",
        examples=[49.71],
    )
    speed_lag_2: float = Field(
        ...,
        ge=0.0,
        le=150.0,
        description="Traffic speed 10 minutes ago (t-2) in mph",
        examples=[56.29],
    )
    speed_lag_3: float = Field(
        ...,
        ge=0.0,
        le=150.0,
        description="Traffic speed 15 minutes ago (t-3) in mph",
        examples=[46.86],
    )
    rolling_mean_3: float = Field(
        ...,
        ge=0.0,
        le=150.0,
        description="Rolling average speed over recent 3 observations (t-2 to t) in mph",
        examples=[52.76],
    )

    @field_validator("sensor_id")
    @classmethod
    def validate_sensor_id(cls, v: str) -> str:
        v_str = str(v).strip()
        if not v_str:
            raise ValueError("sensor_id must not be empty")
        return v_str

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        v_str = v.strip()
        try:
            if "T" in v_str:
                datetime.fromisoformat(v_str)
            else:
                datetime.strptime(v_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            raise ValueError(
                f"Invalid timestamp format '{v}'. Expected ISO format like 'YYYY-MM-DDTHH:MM:SS' or 'YYYY-MM-DD HH:MM:SS'"
            )
        return v_str


class PredictionResponse(BaseModel):
    """
    Traffic speed prediction response payload.
    """
    sensor_id: str = Field(..., description="Sensor identifier")
    timestamp: str = Field(..., description="Observation timestamp")
    current_speed_mph: float = Field(..., description="Current observed speed in mph")
    predicted_speed_15min_mph: float = Field(..., description="Predicted traffic speed 15 minutes ahead in mph")
    speed_change_mph: float = Field(..., description="Speed change (predicted - current) in mph")
    congestion_level: str = Field(..., description="Congestion classification: LOW, MEDIUM, or HIGH")
    prediction_horizon_minutes: int = Field(15, description="Prediction horizon in minutes")


class HealthResponse(BaseModel):
    """
    API health and model availability status.
    """
    status: str = Field("healthy", description="API operational status")
    model_loaded: bool = Field(..., description="True if Spark ML PipelineModel is loaded into memory")
    model_type: str = Field(..., description="Loaded ML model algorithm")
    prediction_horizon_minutes: int = Field(15, description="Model forecasting horizon in minutes")


class SensorLocation(BaseModel):
    """Sensor geographic coordinate"""
    sensor_id: str
    latitude: float
    longitude: float


class SensorsResponse(BaseModel):
    """
    List of active METR-LA traffic sensors available for prediction.
    """
    total_sensors: int = Field(..., description="Total number of active sensors")
    sensors: List[str] = Field(..., description="List of unique sensor IDs")
    locations: Optional[List[SensorLocation]] = Field(default=None, description="Geographic coordinates for each sensor")


class SensorObservation(BaseModel):
    """
    Latest observed telemetry for a sensor across the road network.
    """
    sensor_id: str
    latitude: float
    longitude: float
    timestamp: str
    speed: float
    speed_lag_1: float
    speed_lag_2: float
    speed_lag_3: float
    rolling_mean_3: float
    congestion_level: str


class HistoryPoint(BaseModel):
    timestamp: str
    speed: float
    future_speed_15min: Optional[float] = None


class SensorHistoryResponse(BaseModel):
    sensor_id: str
    history: List[HistoryPoint]


class PropagationNeighbor(BaseModel):
    """
    Connected downstream/adjacent sensor details with network connection weight.
    """
    sensor_id: str = Field(..., description="Connected neighbor sensor ID")
    weight: float = Field(..., description="Road network adjacency edge weight")
    speed_mph: float = Field(..., description="Current speed in mph")
    congestion_level: str = Field(..., description="Congestion state: LOW, MEDIUM, or HIGH")
    latitude: float = Field(..., description="Sensor latitude")
    longitude: float = Field(..., description="Sensor longitude")


class PropagationResponse(BaseModel):
    """
    Congestion propagation analysis response for a selected sensor.
    Note: Network relationship represents graph connectivity across the physical highway network;
    it does not imply causal proof.
    """
    sensor_id: str = Field(..., description="Queried sensor ID")
    sensor_speed_mph: float = Field(..., description="Current speed of selected sensor in mph")
    sensor_congestion: str = Field(..., description="Congestion classification of selected sensor")
    neighbor_count: int = Field(..., description="Number of outgoing connected neighbors")
    high_count: int = Field(..., description="Number of connected neighbors in HIGH congestion")
    medium_count: int = Field(..., description="Number of connected neighbors in MEDIUM congestion")
    low_count: int = Field(..., description="Number of connected neighbors in LOW congestion")
    weighted_congestion_score: float = Field(
        ...,
        description="Weighted network congestion score: sum(weight * state_val) / sum(weight)"
    )
    neighbors: List[PropagationNeighbor] = Field(
        ...,
        description="List of graph-connected neighbors sorted by weight descending"
    )


class BenchmarkRecord(BaseModel):
    data_fraction: str = Field(..., description="Percentage of dataset processed")
    records: int = Field(..., description="Total rows processed in Spark transformation")
    processing_time_seconds: float = Field(..., description="Measured elapsed wall-clock time in seconds")
    records_per_second: int = Field(..., description="Empirical throughput (records / second)")


class BenchmarkResponse(BaseModel):
    environment: str = Field(..., description="Execution environment specifications")
    spark_mode: str = Field(..., description="Spark runtime execution mode")
    workload: str = Field(..., description="Description of representative Spark transformations")
    results: List[BenchmarkRecord] = Field(..., description="Benchmark measurements across fractions")


# ====================================================
# Replay & Scenario Schemas (Interactive Modes)
# ====================================================

class ReplaySensorObservation(BaseModel):
    sensor_id: str
    latitude: float
    longitude: float
    speed: float
    speed_lag_1: float
    speed_lag_2: float
    speed_lag_3: float
    rolling_mean_3: float
    predicted_speed_15min: float
    speed_change: float
    congestion_level: str
    predicted_congestion_level: str


class ReplayAvailableRangeResponse(BaseModel):
    start: str
    end: str
    interval_minutes: int
    total_snapshots: int
    available_dates: List[str]
    timestamps_by_date: Dict[str, List[str]]


class ReplaySnapshotResponse(BaseModel):
    timestamp: str
    total_sensors: int
    sensors: List[ReplaySensorObservation]


class ReplaySummaryResponse(BaseModel):
    timestamp: str
    total_sensors: int
    low_count: int
    medium_count: int
    high_count: int
    average_speed: float
    predicted_slowdowns: int


class ReplayPredictRequest(BaseModel):
    timestamp: Optional[str] = None
    sensors: Optional[List[Dict[str, Any]]] = None


class ScenarioRequest(BaseModel):
    sensor_id: str = Field(..., description="Target sensor ID")
    timestamp: str = Field(..., description="Hypothetical observation timestamp")
    speed: float = Field(..., ge=0.0, le=150.0, description="Hypothetical speed in mph")
    speed_lag_1: float = Field(..., ge=0.0, le=150.0, description="Speed 5 min ago in mph")
    speed_lag_2: float = Field(..., ge=0.0, le=150.0, description="Speed 10 min ago in mph")
    speed_lag_3: float = Field(..., ge=0.0, le=150.0, description="Speed 15 min ago in mph")
    rolling_mean_3: Optional[float] = Field(None, ge=0.0, le=150.0, description="Rolling mean over 3 intervals")

    @field_validator("sensor_id")
    @classmethod
    def validate_sensor_id(cls, v: str) -> str:
        v_str = str(v).strip()
        if not v_str:
            raise ValueError("sensor_id must not be empty")
        return v_str


class ScenarioResponse(BaseModel):
    sensor_id: str
    timestamp: str
    current_speed_mph: float
    predicted_speed_15min_mph: float
    speed_change_mph: float
    current_congestion_level: str
    predicted_congestion_level: str
    connected_sensors_count: int
    high_count: int
    medium_count: int
    low_count: int
    weighted_congestion_indicator: float
    neighbors: List[PropagationNeighbor]
    disclaimer: str = (
        "Graph connectivity indicates network association, not causality. "
        "The weighted congestion indicator is an analytical indicator."
    )


