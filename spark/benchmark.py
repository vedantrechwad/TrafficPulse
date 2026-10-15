"""
TrafficPulse - Stage 6: PySpark Scalability Benchmark
Empirically measures Apache Spark processing time and throughput across increasing
dataset sizes (10%, 25%, 50%, 75%, 100%) using deterministic chronological subsets.

Methodology:
1. Deterministic Subsets: Subsets are partitioned chronologically by timestamp ranges
   (10%, 25%, 50%, 75%, 100%) from the existing METR-LA processed dataset.
2. Identical Workload: Every fraction executes the exact same Spark pipeline:
   - Reading Parquet data
   - Predicate filtering (dropouts and zero readings: speed > 0)
   - Feature engineering (speed difference, acceleration delta, speed ratio, cyclical hour encoding, congestion classification)
   - Multi-key grouping (sensor_id, hour, day_of_week)
   - Distributed statistical reduction (sample count, mean, min, max, stddev, avg delta, avg accel, avg ratio)
   - Distributed action execution (sort and collect)
3. Alive SparkSession: Single SparkSession initialized with local[*] multi-threading.
4. JIT Warm-up: Multiple untimed warm-up passes to prime the Catalyst optimizer,
   Janino code generator, and HotSpot C2 compiler before benchmark recording.
5. Statistical Stability: Each fraction is run 3 times, recording the MEDIAN runtime.
6. Empirical Output: Saves actual measurements to data/processed/scalability_benchmark.csv.
"""

import os
import sys
import time
import csv
import shutil
import psutil
import numpy as np
from typing import List, Dict, Any

# Windows Hadoop Environment Setup
hadoop_home = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "hadoop"))
if os.path.exists(hadoop_home):
    os.environ["HADOOP_HOME"] = hadoop_home
    os.environ["PATH"] = os.path.join(hadoop_home, "bin") + ";" + os.environ.get("PATH", "")

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def get_spark_session(app_name: str = "TrafficPulse-Scalability-Benchmark") -> SparkSession:
    """Initializes Spark in local mode with tuned driver settings."""
    spark = (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.shuffle.partitions", "16")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def execute_spark_workload(spark: SparkSession, dataset_path: str) -> List[Any]:
    """
    Executes a representative, distributed Spark transformation pipeline:
    1. Loads dataset from Parquet
    2. Filters dropout/zero readings
    3. Derives speed delta, acceleration rate, ratio, and cyclical temporal encodings
    4. Performs multi-column aggregation across sensor, hour, and day of week
    5. Calculates descriptive statistics and forces execution via sort() and collect()
    """
    df = spark.read.parquet(dataset_path)
    transformed = (
        df
        .filter((F.col("speed") > 0.0) & F.col("speed").isNotNull())
        .withColumn("speed_diff", F.col("future_speed_15min") - F.col("speed"))
        .withColumn("speed_accel", F.col("speed") - F.col("speed_lag_1"))
        .withColumn("speed_ratio", F.col("speed") / (F.col("rolling_mean_3") + 0.1))
        .withColumn("hour_sin", F.sin(2 * 3.14159 * F.col("hour") / 24))
        .withColumn("hour_cos", F.cos(2 * 3.14159 * F.col("hour") / 24))
        .withColumn(
            "congestion_tier",
            F.when(F.col("speed") >= 50.0, "LOW")
            .when(F.col("speed") >= 30.0, "MEDIUM")
            .otherwise("HIGH")
        )
        .groupBy("sensor_id", "hour", "day_of_week")
        .agg(
            F.count("speed").alias("sample_count"),
            F.avg("speed").alias("mean_speed"),
            F.min("speed").alias("min_speed"),
            F.max("speed").alias("max_speed"),
            F.stddev("speed").alias("std_speed"),
            F.avg("speed_diff").alias("avg_diff"),
            F.avg("speed_accel").alias("avg_accel"),
            F.avg("speed_ratio").alias("avg_ratio")
        )
        .sort("sensor_id", "hour", "day_of_week")
    )
    return transformed.collect()


def run_benchmark() -> List[Dict[str, Any]]:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    base_parquet = os.path.join(project_root, "data", "processed", "traffic_features.parquet")
    output_csv = os.path.join(project_root, "data", "processed", "scalability_benchmark.csv")
    scratch_dir = os.path.join(project_root, "data", "processed", "_bench_scratch")

    if not os.path.exists(base_parquet):
        raise FileNotFoundError(f"Parquet dataset not found at: {base_parquet}")

    print("=" * 80)
    print("TRAFFICPULSE: PYSPARK SCALABILITY BENCHMARK (EMPIRICAL MEDIAN RUNS)")
    print("=" * 80)
    cpu_cores = psutil.cpu_count(logical=True)
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    print(f"Environment:       Windows Local Workstation ({cpu_cores} Cores, {ram_gb} GB RAM)")
    print(f"Execution Mode:    Spark Local Mode (master='local[*]')")
    print(f"Dataset Source:    {base_parquet}")

    spark = get_spark_session()

    # 1. Inspect base dataset and determine deterministic chronological cutoff points
    base_df = spark.read.parquet(base_parquet)
    total_records = base_df.count()
    print(f"Total Available Dataset Records: {total_records:,}")

    print("\nDetermining deterministic chronological timestamp boundaries...")
    distinct_timestamps = [
        r[0] for r in base_df.select("timestamp").distinct().sort("timestamp").collect()
    ]
    total_ts = len(distinct_timestamps)
    print(f"Total Unique Timestamps: {total_ts:,}")

    fractions = [0.10, 0.25, 0.50, 0.75, 1.00]
    fraction_labels = ["10%", "25%", "50%", "75%", "100%"]
    num_partitions = {"10%": 2, "25%": 4, "50%": 8, "75%": 12, "100%": 16}

    # 2. Materialize deterministic chronological subsets
    os.makedirs(scratch_dir, exist_ok=True)
    slice_paths: Dict[str, str] = {}

    print("\nPreparing deterministic chronological subsets for benchmark:")
    for frac, label in zip(fractions, fraction_labels):
        slice_path = os.path.join(scratch_dir, f"subset_{int(frac * 100)}")
        slice_paths[label] = slice_path

        if frac < 1.0:
            idx = min(int(total_ts * frac) - 1, total_ts - 1)
            cutoff_ts = distinct_timestamps[idx]
            sub_df = base_df.filter(F.col("timestamp") <= cutoff_ts)
        else:
            sub_df = base_df

        parts = num_partitions[label]
        sub_df.repartition(parts).write.mode("overwrite").parquet(slice_path)
        rec_cnt = spark.read.parquet(slice_path).count()

        print(f"  [{label}] -> {rec_cnt:,} records, {parts} partitions ({slice_path})")

    # 3. Comprehensive JIT Warm-Up: Prime Catalyst, Janino compiler, and thread pools
    print("\nExecuting untimed JIT warm-up passes on base workload...")
    for w in range(3):
        execute_spark_workload(spark, slice_paths["100%"])
    print("Warm-up complete. All HotSpot C2 compiler methods primed.")

    # 4. Execute Benchmark: 3 runs per fraction, take MEDIAN
    benchmark_results: List[Dict[str, Any]] = []

    print("\n" + "-" * 82)
    print(f"{'Fraction':<10} | {'Records':<12} | {'Runs (s)':<22} | {'Median (s)':<12} | {'Throughput (rec/s)'}")
    print("-" * 82)

    for label in fraction_labels:
        path = slice_paths[label]
        rec_count = spark.read.parquet(path).count()

        times = []
        for r in range(3):
            t0 = time.perf_counter()
            execute_spark_workload(spark, path)
            elapsed = time.perf_counter() - t0
            times.append(round(elapsed, 3))

        median_time = round(float(np.median(times)), 3)
        throughput = int(rec_count / median_time) if median_time > 0 else 0

        runs_str = f"[{times[0]:.3f}, {times[1]:.3f}, {times[2]:.3f}]"
        print(f"{label:<10} | {rec_count:<12,} | {runs_str:<22} | {median_time:<12.3f} | {throughput:<20,}")

        benchmark_results.append({
            "data_fraction": label,
            "records": rec_count,
            "processing_time_seconds": median_time,
            "records_per_second": throughput,
        })

    print("-" * 82)

    # 5. Clean up temporary scratch benchmark slices
    if os.path.exists(scratch_dir):
        shutil.rmtree(scratch_dir)
        print("Cleaned temporary scratch benchmark slices.")

    # 6. Save actual median results to CSV
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["data_fraction", "records", "processing_time_seconds", "records_per_second"]
        )
        writer.writeheader()
        for row in benchmark_results:
            writer.writerow(row)

    print(f"\n[OK] Scalability benchmark results successfully saved to:\n     {output_csv}")
    spark.stop()
    return benchmark_results


if __name__ == "__main__":
    run_benchmark()
