"""
TrafficPulse - Generate Historical Replay Dataset using Apache Spark
Extracts real METR-LA sensor observations from data/processed/traffic_features.parquet,
runs batch inference through the trained Spark ML PipelineModel, enriches with coordinates
and congestion levels, and saves a fast-access historical replay dataset.
"""

import os
import sys
import csv
import json
import logging
from typing import Dict, Any, List

# Configure Hadoop and PySpark paths for Windows
hadoop_home = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "hadoop"))
if os.path.exists(hadoop_home):
    os.environ["HADOOP_HOME"] = hadoop_home
    os.environ["PATH"] = os.path.join(hadoop_home, "bin") + ";" + os.environ.get("PATH", "")

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.ml import PipelineModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("generate_replay_data")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARQUET_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "traffic_features.parquet")
MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "traffic_speed_model")
LOCATIONS_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "sensor_locations.csv")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "congestion_config.json")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "historical_replay_data.json")

# Target dates to index for Replay simulation
# 1. 2012-06-09: Specified in user specification (Saturday, day-long highway sequence)
# 2. 2012-06-27: Peak weekday evening rush hour (featured in sensor history)
# 3. 2012-06-02: Complete 24-hour sequence (including early morning 01:45 to midnight)
REPLAY_DATES = ["2012-06-09", "2012-06-27", "2012-06-02"]


def get_congestion_level(speed: float) -> str:
    if speed >= 50.0:
        return "LOW"
    elif speed >= 30.0:
        return "MEDIUM"
    else:
        return "HIGH"


def main():
    logger.info("Starting PySpark session for Historical Replay generation...")
    spark = (
        SparkSession.builder.appName("TrafficPulse_Replay_Generation")
        .master("local[*]")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    # 1. Load sensor locations
    locations_map: Dict[str, Dict[str, float]] = {}
    with open(LOCATIONS_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            s_id = str(row["sensor_id"]).strip()
            locations_map[s_id] = {
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
            }
    logger.info(f"Loaded {len(locations_map)} sensor locations.")

    # 2. Load traffic features parquet
    logger.info(f"Loading features from: {PARQUET_PATH}")
    df_raw = spark.read.parquet(PARQUET_PATH)

    # 3. Filter for target replay dates
    date_conditions = [F.col("timestamp").cast("string").startswith(d) for d in REPLAY_DATES]
    combined_filter = date_conditions[0]
    for cond in date_conditions[1:]:
        combined_filter = combined_filter | cond

    df_filtered = df_raw.filter(combined_filter)
    count = df_filtered.count()
    logger.info(f"Filtered {count} records across target replay dates: {REPLAY_DATES}")

    # 4. Load trained PipelineModel and execute batch inference
    logger.info(f"Loading trained Spark ML PipelineModel from: {MODEL_PATH}")
    model = PipelineModel.load(MODEL_PATH)
    logger.info("Executing Spark ML batch predictions for all replay timesteps...")
    predictions_df = model.transform(df_filtered)

    # 5. Collect predictions and assemble fast-lookup replay structure
    selected_cols = [
        "timestamp",
        "sensor_id",
        "speed",
        "speed_lag_1",
        "speed_lag_2",
        "speed_lag_3",
        "rolling_mean_3",
        "prediction",
    ]
    records = predictions_df.select(selected_cols).collect()
    logger.info(f"Collected {len(records)} prediction records into driver memory.")

    snapshots_by_ts: Dict[str, List[Dict[str, Any]]] = {}
    timestamps_by_date: Dict[str, List[str]] = {d: [] for d in REPLAY_DATES}

    for r in records:
        ts_str = str(r["timestamp"])[:19]
        d_str = ts_str[:10]
        s_id = str(r["sensor_id"])
        coords = locations_map.get(s_id, {"latitude": 34.0522, "longitude": -118.2437})

        speed = round(float(r["speed"]), 2)
        pred_speed = round(float(r["prediction"]), 2)
        change = round(pred_speed - speed, 2)

        cong = get_congestion_level(speed)
        pred_cong = get_congestion_level(pred_speed)

        sensor_entry = {
            "sensor_id": s_id,
            "latitude": coords["latitude"],
            "longitude": coords["longitude"],
            "speed": speed,
            "speed_lag_1": round(float(r["speed_lag_1"]), 2),
            "speed_lag_2": round(float(r["speed_lag_2"]), 2),
            "speed_lag_3": round(float(r["speed_lag_3"]), 2),
            "rolling_mean_3": round(float(r["rolling_mean_3"]), 2),
            "predicted_speed_15min": pred_speed,
            "speed_change": change,
            "congestion_level": cong,
            "predicted_congestion_level": pred_cong,
        }

        if ts_str not in snapshots_by_ts:
            snapshots_by_ts[ts_str] = []
            if d_str in timestamps_by_date:
                timestamps_by_date[d_str].append(ts_str)

        snapshots_by_ts[ts_str].append(sensor_entry)

    # Sort timestamps chronologically for each date
    for d in REPLAY_DATES:
        timestamps_by_date[d] = sorted(list(set(timestamps_by_date[d])))
        logger.info(f"Date {d}: {len(timestamps_by_date[d])} timestamps.")

    # 6. Precompute summary metrics for each timestamp
    summaries_by_ts: Dict[str, Dict[str, Any]] = {}
    for ts, sensors in snapshots_by_ts.items():
        total = len(sensors)
        low_count = sum(1 for s in sensors if s["congestion_level"] == "LOW")
        med_count = sum(1 for s in sensors if s["congestion_level"] == "MEDIUM")
        high_count = sum(1 for s in sensors if s["congestion_level"] == "HIGH")
        avg_spd = round(sum(s["speed"] for s in sensors) / total, 2) if total > 0 else 0.0
        slowdowns = sum(1 for s in sensors if s["speed_change"] < -1.0)

        summaries_by_ts[ts] = {
            "timestamp": ts,
            "total_sensors": total,
            "low_count": low_count,
            "medium_count": med_count,
            "high_count": high_count,
            "average_speed": avg_spd,
            "predicted_slowdowns": slowdowns,
        }

    # 7. Assemble final dataset payload
    replay_payload = {
        "metadata": {
            "dataset": "METR-LA Historical Traffic",
            "interval_minutes": 5,
            "prediction_horizon_minutes": 15,
            "model_type": "Spark ML Random Forest Regressor",
            "total_indexed_timestamps": len(snapshots_by_ts),
        },
        "available_dates": REPLAY_DATES,
        "timestamps_by_date": timestamps_by_date,
        "snapshots": snapshots_by_ts,
        "summaries": summaries_by_ts,
    }

    logger.info(f"Saving replay payload to: {OUTPUT_PATH}")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(replay_payload, f)

    file_size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    logger.info(f"Successfully generated historical replay dataset ({file_size_mb:.2f} MB).")
    spark.stop()


if __name__ == "__main__":
    main()
