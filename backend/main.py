"""
TrafficPulse - FastAPI Prediction Service
Exposes the trained Apache Spark ML model for real-time traffic speed forecasting
and congestion level classification.
"""

import os
import sys
import csv
import json
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional

# Configure Hadoop and PySpark paths for Windows execution
if os.name == "nt":
    hadoop_home = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "hadoop"))
    if os.path.exists(hadoop_home):
        os.environ["HADOOP_HOME"] = hadoop_home
        os.environ["PATH"] = os.path.join(hadoop_home, "bin") + ";" + os.environ.get("PATH", "")

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pyspark.sql import SparkSession
from pyspark.ml import PipelineModel

from backend.schemas import (
    PredictionRequest,
    PredictionResponse,
    HealthResponse,
    SensorsResponse,
    SensorLocation,
    SensorObservation,
    SensorHistoryResponse,
    HistoryPoint,
    PropagationNeighbor,
    PropagationResponse,
    BenchmarkRecord,
    BenchmarkResponse,
    ReplayAvailableRangeResponse,
    ReplaySensorObservation,
    ReplaySnapshotResponse,
    ReplaySummaryResponse,
    ReplayPredictRequest,
    ScenarioRequest,
    ScenarioResponse,
)
from spark.propagation import load_adjacency_graph, analyze_congestion_neighbors

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("trafficpulse_api")

# Global paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "traffic_speed_model")
METADATA_PATH = os.path.join(PROJECT_ROOT, "models", "model_metadata.json")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "congestion_config.json")
LOCATIONS_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "sensor_locations.csv")
OBSERVATIONS_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "latest_sensor_observations.json")
HISTORY_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "sensor_history.json")
GRAPH_PATH = os.path.join(PROJECT_ROOT, "data", "raw", "adj_METR-LA.pkl")
BENCHMARK_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "scalability_benchmark.csv")
REPLAY_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "historical_replay_data.json")



def load_congestion_helper(config_data: dict, speed: float) -> str:
    """Helper to classify congestion based on config dictionary."""
    categories = config_data.get("categories", {})
    low_thresh = categories.get("LOW", {}).get("min_speed", 50.0)
    med_thresh = categories.get("MEDIUM", {}).get("min_speed", 30.0)

    if speed >= low_thresh:
        return "LOW"
    elif speed >= med_thresh:
        return "MEDIUM"
    else:
        return "HIGH"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan Context Manager.
    Initializes SparkSession and loads the Spark ML model, coordinates, and telemetry once on startup.
    Shuts down Spark cleanly on application exit.
    """
    logger.info("Initializing SparkSession for TrafficPulse API...")
    spark_driver_memory = os.environ.get("SPARK_DRIVER_MEMORY", "2g")
    spark = (
        SparkSession.builder.appName("TrafficPulse_API")
        .master("local[*]")
        .config("spark.driver.memory", spark_driver_memory)
        .config("spark.sql.shuffle.partitions", "16")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    app.state.spark = spark

    # 1. Load trained PipelineModel
    if not os.path.exists(MODEL_PATH):
        logger.error(f"Trained model not found at: {MODEL_PATH}")
        raise RuntimeError(f"Trained model directory not found at: {MODEL_PATH}")

    logger.info(f"Loading Spark ML PipelineModel from: {MODEL_PATH}")
    app.state.model = PipelineModel.load(MODEL_PATH)
    logger.info("Spark ML model loaded successfully into memory.")

    # 2. Load model metadata
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, "r") as f:
            app.state.metadata = json.load(f)
    else:
        logger.warning(f"Metadata file not found at: {METADATA_PATH}")
        app.state.metadata = {"model_type": "Random Forest"}

    # 3. Load configurable congestion thresholds
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            app.state.congestion_config = json.load(f)
        logger.info("Loaded configurable congestion classification thresholds.")
    else:
        app.state.congestion_config = {
            "categories": {
                "LOW": {"min_speed": 50.0, "max_speed": None},
                "MEDIUM": {"min_speed": 30.0, "max_speed": 50.0},
                "HIGH": {"min_speed": 0.0, "max_speed": 30.0},
            }
        }

    # 4. Load real geographic sensor coordinates
    locations_map: Dict[str, Dict[str, float]] = {}
    if os.path.exists(LOCATIONS_PATH):
        with open(LOCATIONS_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                s_id = str(row["sensor_id"]).strip()
                locations_map[s_id] = {
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                }
        logger.info(f"Loaded real geographic coordinates for {len(locations_map)} sensors.")
    else:
        logger.warning(f"Sensor locations file not found at: {LOCATIONS_PATH}")
    app.state.locations_map = locations_map

    # 5. Load latest sensor observations
    observations_list: List[Dict[str, Any]] = []
    if os.path.exists(OBSERVATIONS_PATH):
        with open(OBSERVATIONS_PATH, "r", encoding="utf-8") as f:
            raw_obs = json.load(f)
            for item in raw_obs:
                s_id = str(item["sensor_id"])
                coords = locations_map.get(s_id, {"latitude": 34.0522, "longitude": -118.2437})
                speed_val = float(item["speed"])
                congestion = load_congestion_helper(app.state.congestion_config, speed_val)
                observations_list.append({
                    "sensor_id": s_id,
                    "latitude": coords["latitude"],
                    "longitude": coords["longitude"],
                    "timestamp": str(item["timestamp"]),
                    "speed": round(speed_val, 2),
                    "speed_lag_1": round(float(item["speed_lag_1"]), 2),
                    "speed_lag_2": round(float(item["speed_lag_2"]), 2),
                    "speed_lag_3": round(float(item["speed_lag_3"]), 2),
                    "rolling_mean_3": round(float(item["rolling_mean_3"]), 2),
                    "congestion_level": congestion,
                })
        logger.info(f"Loaded {len(observations_list)} latest sensor observations for map rendering.")
    app.state.observations = observations_list
    app.state.sensors_list = [obs["sensor_id"] for obs in observations_list]
    app.state.sensors_set = set(app.state.sensors_list)

    # 6. Load sensor historical time series
    history_map: Dict[str, List[Dict[str, Any]]] = {}
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            history_map = json.load(f)
        logger.info(f"Loaded historical time series for {len(history_map)} sensors.")
    app.state.history_map = history_map

    # 7. Precompute fast observation lookup map
    app.state.observations_map = {obs["sensor_id"]: obs for obs in observations_list}

    # 8. Load METR-LA sensor adjacency graph
    logger.info(f"Loading METR-LA sensor adjacency graph from: {GRAPH_PATH}")
    try:
        g_ids, g_s2i, g_adj = load_adjacency_graph(GRAPH_PATH)
        app.state.graph_sensor_ids = g_ids
        app.state.graph_sensor_to_ind = g_s2i
        app.state.adj_mx = g_adj
        logger.info(f"Loaded graph with {len(g_ids)} sensors and adjacency matrix shape {g_adj.shape}.")
    except Exception as e:
        logger.error(f"Error loading adjacency graph: {e}", exc_info=True)
        app.state.graph_sensor_ids = []
        app.state.graph_sensor_to_ind = {}
        app.state.adj_mx = None

    # 9. Warm up Spark ML execution engine
    logger.info("Warming up Spark ML pipeline for low-latency inference...")
    try:
        sample_sensor = app.state.sensors_list[0] if app.state.sensors_list else "716955"
        dummy_df = spark.createDataFrame([{
            "sensor_id": sample_sensor,
            "speed": 50.0,
            "speed_lag_1": 50.0,
            "speed_lag_2": 50.0,
            "speed_lag_3": 50.0,
            "rolling_mean_3": 50.0,
            "hour": 12,
            "minute": 0,
            "day_of_week": 4,
            "is_weekend": 0,
        }])
        app.state.model.transform(dummy_df).select("prediction").first()
        logger.info("Spark ML pipeline warmed up successfully. Ready for real-time requests.")
    except Exception as e:
        logger.warning(f"Spark model warmup encountered an issue: {e}")

    # 10. Load historical replay dataset for instant interactive simulation
    replay_data: Dict[str, Any] = {
        "available_dates": [],
        "timestamps_by_date": {},
        "snapshots": {},
        "summaries": {},
    }
    if os.path.exists(REPLAY_DATA_PATH):
        try:
            logger.info(f"Loading historical replay dataset from: {REPLAY_DATA_PATH}")
            with open(REPLAY_DATA_PATH, "r", encoding="utf-8") as f:
                replay_data = json.load(f)
            total_snaps = len(replay_data.get("snapshots", {}))
            dates = replay_data.get("available_dates", [])
            logger.info(f"Loaded {total_snaps} historical replay snapshots across dates: {dates}")
        except Exception as e:
            logger.error(f"Error loading historical replay dataset: {e}", exc_info=True)
    else:
        logger.warning(f"Historical replay dataset not found at: {REPLAY_DATA_PATH}")
    app.state.replay_data = replay_data

    yield

    # Clean shutdown
    logger.info("Stopping SparkSession...")
    try:
        app.state.spark.stop()
    except Exception:
        pass
    logger.info("TrafficPulse API shutdown complete.")


# Initialize FastAPI application
app = FastAPI(
    title="TrafficPulse Prediction API",
    description=(
        "Scalable Traffic Speed Prediction & Congestion Analysis API powered by Apache Spark ML. "
        "Forecasts traffic speeds 15 minutes ahead across the METR-LA sensor network."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for frontend applications (Vite / Next.js / Create-React-App)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "*",  # Permissive for local college project demo
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_congestion_level(speed: float) -> str:
    """Classifies speed into LOW, MEDIUM, or HIGH congestion levels."""
    return load_congestion_helper(app.state.congestion_config, speed)


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error processing {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred while processing the prediction request."},
    )


@app.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    tags=["Health"],
)
def health_check():
    """Verifies that the API service is active and the Spark ML PipelineModel is loaded."""
    model_loaded = hasattr(app.state, "model") and app.state.model is not None
    model_type = app.state.metadata.get("model_type", "Random Forest")
    return HealthResponse(
        status="healthy",
        model_loaded=model_loaded,
        model_type=model_type,
        prediction_horizon_minutes=15,
    )


@app.get(
    "/api/model-info",
    summary="Model Architecture & Evaluation Metadata",
    tags=["Metadata"],
)
def get_model_info():
    """Returns training metadata, validation comparisons, test metrics, and feature configurations."""
    return app.state.metadata


@app.get(
    "/api/sensors",
    response_model=SensorsResponse,
    summary="Get Active Network Sensors",
    tags=["Sensors"],
)
def get_sensors():
    """Returns the list of 207 verified traffic sensors with their geographic coordinates."""
    sensors = app.state.sensors_list
    loc_map = app.state.locations_map
    locations = [
        SensorLocation(
            sensor_id=s_id,
            latitude=loc_map.get(s_id, {}).get("latitude", 34.0522),
            longitude=loc_map.get(s_id, {}).get("longitude", -118.2437),
        )
        for s_id in sensors
    ]
    return SensorsResponse(
        total_sensors=len(sensors),
        sensors=sensors,
        locations=locations,
    )


@app.get(
    "/api/sensor-observations",
    response_model=List[SensorObservation],
    summary="Latest Observed Sensor Telemetry",
    tags=["Telemetry"],
)
def get_sensor_observations():
    """
    Returns the latest available observed speed, lag features, coordinates,
    and congestion status for all 207 sensors for immediate dashboard rendering.
    Cached in memory to eliminate repeated disk reads.
    """
    return [SensorObservation(**item) for item in app.state.observations]


@app.get(
    "/api/sensors/{sensor_id}/history",
    response_model=SensorHistoryResponse,
    summary="Get Recent Historical Speed Profile",
    tags=["Telemetry"],
)
def get_sensor_history(sensor_id: str, timestamp: Optional[str] = None):
    """
    Returns recent chronological traffic speed observations for the specified sensor
    to render the actual vs future speed trend line chart.
    """
    s_id = str(sensor_id).strip()
    if s_id not in app.state.sensors_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor ID '{s_id}' not found in METR-LA network.",
        )

    history_points = []
    if timestamp:
        ts_clean = str(timestamp).strip()
        replay_data = getattr(app.state, "replay_data", {})
        snapshots = replay_data.get("snapshots", {})
        alt_ts = ts_clean.replace("T", " ") if "T" in ts_clean else ts_clean.replace(" ", "T")
        match_ts = ts_clean if ts_clean in snapshots else (alt_ts if alt_ts in snapshots else None)
        if match_ts:
            d_str = match_ts[:10]
            day_ts_list = replay_data.get("timestamps_by_date", {}).get(d_str, [])
            if match_ts in day_ts_list:
                idx = day_ts_list.index(match_ts)
                start_idx = max(0, idx - 18)
                window_ts = day_ts_list[start_idx : idx + 1]
                for t in window_ts:
                    s_obs = next((s for s in snapshots.get(t, []) if s.get("sensor_id") == s_id), None)
                    if s_obs:
                        history_points.append(
                            HistoryPoint(
                                timestamp=t,
                                speed=round(float(s_obs["speed"]), 2),
                                future_speed_15min=round(float(s_obs["predicted_speed_15min"]), 2)
                                if s_obs.get("predicted_speed_15min") is not None
                                else None,
                            )
                        )

    if not history_points:
        history_records = app.state.history_map.get(s_id, [])
        history_points = [
            HistoryPoint(
                timestamp=r["timestamp"],
                speed=round(float(r["speed"]), 2),
                future_speed_15min=round(float(r["future_speed_15min"]), 2)
                if r.get("future_speed_15min") is not None
                else None,
            )
            for r in history_records
        ]

    return SensorHistoryResponse(
        sensor_id=s_id,
        history=history_points,
    )


@app.post(
    "/api/predict",
    response_model=PredictionResponse,
    summary="Predict Traffic Speed 15 Minutes Ahead",
    tags=["Prediction"],
)
def predict_traffic_speed(payload: PredictionRequest):
    """
    Accepts observation details for a given sensor and returns the forecasted speed
    and congestion level 15 minutes into the future using the trained Spark ML pipeline.

    Derived temporal features (hour, minute, day_of_week, is_weekend) are computed automatically.
    """
    sensor_id = payload.sensor_id
    if app.state.sensors_set and sensor_id not in app.state.sensors_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Sensor ID '{sensor_id}' is not recognized in the METR-LA network. "
                f"Please select a valid sensor ID from /api/sensors."
            ),
        )

    ts_str = payload.timestamp.strip()
    try:
        if "T" in ts_str:
            dt = datetime.fromisoformat(ts_str)
        else:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to parse timestamp '{ts_str}'. Please use ISO 8601 format (e.g. '2012-06-09T02:30:00').",
        )

    hour = dt.hour
    minute = dt.minute
    day_of_week = (dt.weekday() + 1) % 7 + 1
    is_weekend = 1 if day_of_week in [1, 7] else 0

    row_dict = {
        "sensor_id": sensor_id,
        "speed": float(payload.speed),
        "speed_lag_1": float(payload.speed_lag_1),
        "speed_lag_2": float(payload.speed_lag_2),
        "speed_lag_3": float(payload.speed_lag_3),
        "rolling_mean_3": float(payload.rolling_mean_3),
        "hour": int(hour),
        "minute": int(minute),
        "day_of_week": int(day_of_week),
        "is_weekend": int(is_weekend),
    }

    try:
        input_df = app.state.spark.createDataFrame([row_dict])
        predictions = app.state.model.transform(input_df)
        pred_raw = predictions.select("prediction").first()[0]
    except Exception as e:
        logger.error(f"Spark ML transform failed for sensor {sensor_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Spark ML inference pipeline encountered an error during transformation.",
        )

    current_speed = round(float(payload.speed), 2)
    predicted_speed = round(float(pred_raw), 2)
    speed_change = round(predicted_speed - current_speed, 2)
    congestion_level = get_congestion_level(predicted_speed)

    return PredictionResponse(
        sensor_id=sensor_id,
        timestamp=payload.timestamp,
        current_speed_mph=current_speed,
        predicted_speed_15min_mph=predicted_speed,
        speed_change_mph=speed_change,
        congestion_level=congestion_level,
        prediction_horizon_minutes=15,
    )


@app.get(
    "/api/sensors/{sensor_id}/propagation",
    response_model=PropagationResponse,
    summary="Congestion Propagation & Network Relationship Analysis",
    tags=["Propagation"],
)
def get_sensor_propagation(sensor_id: str, timestamp: Optional[str] = None):
    """
    Analyzes graph-connected downstream sensors and network congestion indicators
    for a selected sensor based on the physical METR-LA road sensor adjacency matrix.

    Note on Interpretation:
      This endpoint evaluates physical road-network relationships and associated
      congestion levels. Network association does not assert causal proof.
    """
    s_id = str(sensor_id).strip()
    if not hasattr(app.state, "graph_sensor_to_ind") or s_id not in app.state.graph_sensor_to_ind:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor ID '{s_id}' not found in METR-LA road network graph.",
        )

    obs_map = app.state.observations_map
    if timestamp:
        ts_clean = str(timestamp).strip()
        replay_data = getattr(app.state, "replay_data", {})
        snapshots = replay_data.get("snapshots", {})
        alt_ts = ts_clean.replace("T", " ") if "T" in ts_clean else ts_clean.replace(" ", "T")
        match_ts = ts_clean if ts_clean in snapshots else (alt_ts if alt_ts in snapshots else None)
        if match_ts:
            obs_map = {s["sensor_id"]: s for s in snapshots[match_ts]}

    try:
        analysis = analyze_congestion_neighbors(
            sensor_id=s_id,
            observations_map=obs_map,
            sensor_ids=app.state.graph_sensor_ids,
            sensor_to_ind=app.state.graph_sensor_to_ind,
            adj_mx=app.state.adj_mx,
            locations_map=app.state.locations_map,
            config_categories=app.state.congestion_config.get("categories"),
        )
        return PropagationResponse(**analysis)
    except Exception as e:
        logger.error(f"Error computing propagation analysis for sensor {s_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute congestion propagation analysis.",
        )


@app.get(
    "/api/benchmark",
    response_model=BenchmarkResponse,
    summary="PySpark Scalability Benchmark Results",
    tags=["Scalability"],
)
def get_scalability_benchmark():
    """
    Returns empirical Spark scalability benchmark measurements evaluating wall-clock
    processing times and throughput across 10%, 25%, 50%, 75%, and 100% of the dataset.
    """
    if not os.path.exists(BENCHMARK_PATH):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scalability benchmark CSV not found. Please execute spark/benchmark.py first.",
        )

    records = []
    try:
        with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(BenchmarkRecord(
                    data_fraction=row["data_fraction"],
                    records=int(row["records"]),
                    processing_time_seconds=float(row["processing_time_seconds"]),
                    records_per_second=int(row["records_per_second"]),
                ))
    except Exception as e:
        logger.error(f"Error reading benchmark results CSV: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse scalability benchmark dataset.",
        )

    return BenchmarkResponse(
        environment="Windows Local Workstation (16 Cores, 15.7 GB RAM)",
        spark_mode="Spark Local Mode (master='local[*]')",
        workload=(
            "Distributed Parquet loading, zero-reading filtering, speed deviation derivation, "
            "multi-key aggregation (sensor_id, hour), and statistical reduction"
        ),
        results=records,
    )


# ====================================================
# Interactive Replay & Scenario Endpoints
# ====================================================

@app.get(
    "/api/replay/available-range",
    response_model=ReplayAvailableRangeResponse,
    summary="Get Available Historical Replay Time Range",
    tags=["Replay"],
)
def get_replay_available_range():
    """
    Returns available historical replay dates, continuous 5-minute timestamps,
    and total available simulation snapshots.
    """
    replay_data = getattr(app.state, "replay_data", {})
    timestamps_by_date = replay_data.get("timestamps_by_date", {})
    available_dates = replay_data.get("available_dates", [])

    all_ts = list(replay_data.get("snapshots", {}).keys())
    start_ts = min(all_ts) if all_ts else "N/A"
    end_ts = max(all_ts) if all_ts else "N/A"

    return ReplayAvailableRangeResponse(
        start=start_ts,
        end=end_ts,
        interval_minutes=5,
        total_snapshots=len(all_ts),
        available_dates=available_dates,
        timestamps_by_date=timestamps_by_date,
    )


@app.get(
    "/api/replay/snapshot",
    response_model=ReplaySnapshotResponse,
    summary="Get Replay Snapshot for Specific Timestamp",
    tags=["Replay"],
)
def get_replay_snapshot(timestamp: str):
    """
    Returns the real METR-LA sensor observations and precomputed Spark ML 15-minute
    predictions for all 207 sensors at the specified timestamp.
    """
    ts_clean = str(timestamp).strip()
    replay_data = getattr(app.state, "replay_data", {})
    snapshots = replay_data.get("snapshots", {})

    if ts_clean not in snapshots:
        alt_ts = ts_clean.replace("T", " ") if "T" in ts_clean else ts_clean.replace(" ", "T")
        if alt_ts in snapshots:
            ts_clean = alt_ts
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Replay snapshot for timestamp '{timestamp}' not found. Please query /api/replay/available-range.",
            )

    sensor_records = snapshots[ts_clean]
    return ReplaySnapshotResponse(
        timestamp=ts_clean,
        total_sensors=len(sensor_records),
        sensors=[ReplaySensorObservation(**s) for s in sensor_records],
    )


@app.get(
    "/api/replay/summary",
    response_model=ReplaySummaryResponse,
    summary="Get Replay Network Summary for Timestamp",
    tags=["Replay"],
)
def get_replay_summary(timestamp: str):
    """
    Returns aggregate network metrics (LOW/MED/HIGH counts, average speed,
    predicted slowdown count) for a specific historical timestamp.
    """
    ts_clean = str(timestamp).strip()
    replay_data = getattr(app.state, "replay_data", {})
    summaries = replay_data.get("summaries", {})

    if ts_clean not in summaries:
        alt_ts = ts_clean.replace("T", " ") if "T" in ts_clean else ts_clean.replace(" ", "T")
        if alt_ts in summaries:
            ts_clean = alt_ts
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Replay summary for timestamp '{timestamp}' not found.",
            )

    return ReplaySummaryResponse(**summaries[ts_clean])


@app.post(
    "/api/replay/predict",
    summary="Batch Predict for Replay Timestep or Observations",
    tags=["Replay"],
)
def post_replay_predict(payload: ReplayPredictRequest):
    """
    Returns 15-minute future speed predictions for replay observations.
    Uses precomputed model predictions if timestamp is provided, or transforms
    custom sensor rows on-the-fly using the Spark ML PipelineModel.
    """
    replay_data = getattr(app.state, "replay_data", {})
    snapshots = replay_data.get("snapshots", {})

    if payload.timestamp and payload.timestamp.strip() in snapshots:
        ts = payload.timestamp.strip()
        sensors = snapshots[ts]
        return {
            "timestamp": ts,
            "predictions": [
                {
                    "sensor_id": s["sensor_id"],
                    "current_speed_mph": s["speed"],
                    "predicted_speed_15min_mph": s["predicted_speed_15min"],
                    "speed_change_mph": s["speed_change"],
                    "congestion_level": s["predicted_congestion_level"],
                }
                for s in sensors
            ],
        }

    # If custom sensor records passed, run through Spark ML model
    if payload.sensors and len(payload.sensors) > 0:
        rows = []
        for s in payload.sensors:
            dt = datetime.fromisoformat(s.get("timestamp", "2012-06-09T12:00:00").replace(" ", "T"))
            dow = (dt.weekday() + 1) % 7 + 1
            rows.append({
                "sensor_id": str(s.get("sensor_id", "716955")),
                "speed": float(s.get("speed", 50.0)),
                "speed_lag_1": float(s.get("speed_lag_1", s.get("speed", 50.0))),
                "speed_lag_2": float(s.get("speed_lag_2", s.get("speed", 50.0))),
                "speed_lag_3": float(s.get("speed_lag_3", s.get("speed", 50.0))),
                "rolling_mean_3": float(s.get("rolling_mean_3", s.get("speed", 50.0))),
                "hour": int(dt.hour),
                "minute": int(dt.minute),
                "day_of_week": int(dow),
                "is_weekend": 1 if dow in [1, 7] else 0,
            })
        try:
            df = app.state.spark.createDataFrame(rows)
            preds = app.state.model.transform(df).select("sensor_id", "speed", "prediction").collect()
            return {
                "timestamp": payload.timestamp or "custom",
                "predictions": [
                    {
                        "sensor_id": str(r["sensor_id"]),
                        "current_speed_mph": round(float(r["speed"]), 2),
                        "predicted_speed_15min_mph": round(float(r["prediction"]), 2),
                        "speed_change_mph": round(float(r["prediction"]) - float(r["speed"]), 2),
                        "congestion_level": get_congestion_level(float(r["prediction"])),
                    }
                    for r in preds
                ],
            }
        except Exception as e:
            logger.error(f"Error executing batch replay predict: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Spark ML batch prediction failed.")

    raise HTTPException(status_code=400, detail="Must provide either valid timestamp or sensors array.")


@app.post(
    "/api/scenario/analyze",
    response_model=ScenarioResponse,
    summary="Analyze What-If Traffic Scenario",
    tags=["Scenario"],
)
def analyze_scenario(payload: ScenarioRequest):
    """
    Executes live Spark ML inference for a user-specified hypothetical sensor condition
    and evaluates downstream graph-network propagation and congestion indicators.
    """
    sensor_id = payload.sensor_id
    if sensor_id not in app.state.sensors_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor ID '{sensor_id}' not found in METR-LA network.",
        )

    ts_str = payload.timestamp.strip()
    try:
        if "T" in ts_str:
            dt = datetime.fromisoformat(ts_str)
        else:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid timestamp format '{ts_str}'. Please use ISO or 'YYYY-MM-DD HH:MM:SS'.",
        )

    hour = dt.hour
    minute = dt.minute
    day_of_week = (dt.weekday() + 1) % 7 + 1
    is_weekend = 1 if day_of_week in [1, 7] else 0

    speed = float(payload.speed)
    lag1 = float(payload.speed_lag_1)
    lag2 = float(payload.speed_lag_2)
    lag3 = float(payload.speed_lag_3)
    rolling3 = float(payload.rolling_mean_3) if payload.rolling_mean_3 is not None else round((speed + lag1 + lag2) / 3.0, 2)

    row_dict = {
        "sensor_id": sensor_id,
        "speed": speed,
        "speed_lag_1": lag1,
        "speed_lag_2": lag2,
        "speed_lag_3": lag3,
        "rolling_mean_3": rolling3,
        "hour": int(hour),
        "minute": int(minute),
        "day_of_week": int(day_of_week),
        "is_weekend": int(is_weekend),
    }

    try:
        input_df = app.state.spark.createDataFrame([row_dict])
        predictions = app.state.model.transform(input_df)
        pred_raw = predictions.select("prediction").first()[0]
    except Exception as e:
        logger.error(f"Spark ML transform failed in scenario analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Spark ML inference pipeline encountered an error during scenario transformation.",
        )

    current_speed = round(speed, 2)
    predicted_speed = round(float(pred_raw), 2)
    speed_change = round(predicted_speed - current_speed, 2)
    current_congestion = get_congestion_level(current_speed)
    predicted_congestion = get_congestion_level(predicted_speed)

    # 1. Base observations map: contextualize with snapshot if timestamp available, else default observations
    base_obs_map = dict(app.state.observations_map)
    ts_clean = payload.timestamp.strip()
    replay_data = getattr(app.state, "replay_data", {})
    snapshots = replay_data.get("snapshots", {})
    alt_ts = ts_clean.replace("T", " ") if "T" in ts_clean else ts_clean.replace(" ", "T")
    snap_key = ts_clean if ts_clean in snapshots else (alt_ts if alt_ts in snapshots else None)
    if snap_key:
        for s in snapshots[snap_key]:
            base_obs_map[s["sensor_id"]] = s

    # 2. Determine target sensor baseline speed and scenario perturbation
    sensor_baseline_speed = float(base_obs_map.get(sensor_id, {}).get("speed", 55.0))
    speed_delta = current_speed - sensor_baseline_speed

    # 3. Propagate perturbation across physical road graph connections
    prop_analysis = analyze_congestion_neighbors(
        sensor_id=sensor_id,
        observations_map=base_obs_map,
        sensor_ids=app.state.graph_sensor_ids,
        sensor_to_ind=app.state.graph_sensor_to_ind,
        adj_mx=app.state.adj_mx,
        locations_map=app.state.locations_map,
        speed_delta=speed_delta,
        config_categories=app.state.congestion_config.get("categories"),
    )

    return ScenarioResponse(
        sensor_id=sensor_id,
        timestamp=payload.timestamp,
        current_speed_mph=current_speed,
        predicted_speed_15min_mph=predicted_speed,
        speed_change_mph=speed_change,
        current_congestion_level=current_congestion,
        predicted_congestion_level=predicted_congestion,
        connected_sensors_count=prop_analysis["neighbor_count"],
        high_count=prop_analysis["high_count"],
        medium_count=prop_analysis["medium_count"],
        low_count=prop_analysis["low_count"],
        weighted_congestion_indicator=prop_analysis["weighted_congestion_score"],
        neighbors=prop_analysis["neighbors"],
        disclaimer=(
            "Graph connectivity indicates network association, not causality. "
            "The weighted congestion indicator is an analytical indicator."
        ),
    )


# Serve built frontend Single Page App if present
frontend_dist = os.path.join(PROJECT_ROOT, "frontend", "dist")
if os.path.exists(frontend_dist):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")



