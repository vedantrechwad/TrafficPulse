"""
TrafficPulse - Stage 2: Optimized PySpark Preprocessing and Feature Engineering
Converts raw METR-LA HDF5 traffic speeds into an ML-ready Parquet dataset.

Optimizations:
  - Repartitions once by sensor_id to avoid repeated cross-node shuffles.
  - Combines window operations (lags, rolling mean, lead target) into a single unified window.
  - Avoids expensive global forward/backward fills; drops invalid/dropout rows naturally via filtering.
  - Defers expensive network aggregations to the downstream propagation stage.
  - Executes a single end-to-end Spark write job without intermediate action bottlenecks.
"""

import os
import sys
import time
import pandas as pd

# Configure environment for local Windows execution
hadoop_home = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "hadoop"))
if os.path.exists(hadoop_home):
    os.environ["HADOOP_HOME"] = hadoop_home
    os.environ["PATH"] = os.path.join(hadoop_home, "bin") + ";" + os.environ.get("PATH", "")

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F


def get_spark_session(app_name: str = "TrafficPulse_Preprocessing") -> SparkSession:
    """Initializes a fast, lean local SparkSession."""
    spark = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.shuffle.partitions", "16")
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .config("spark.driver.host", "localhost")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def load_raw_data(h5_path: str):
    """
    Step 1: Ingests raw METR-LA HDF5 using pandas/PyTables.
    Returns:
      df_raw: wide DataFrame (34,272 timestamps x 207 sensors)
      n_timestamps: int
      n_sensors: int
    """
    print(f"[1/7] Ingesting raw HDF5 dataset: {h5_path}")
    t0 = time.time()
    df_raw = pd.read_hdf(h5_path)
    n_timestamps, n_sensors = df_raw.shape
    print(f"      Loaded raw matrix: {n_timestamps:,} timestamps x {n_sensors} sensors in {time.time() - t0:.2f}s")
    return df_raw, n_timestamps, n_sensors


def convert_to_long_format(df_raw, spark: SparkSession):
    """
    Step 1 (cont.): Melts wide sensor matrix into scalable long format:
      (timestamp, sensor_id, speed)
    and converts to a Spark DataFrame.
    """
    print("[2/7] Converting wide matrix to long format (timestamp | sensor_id | speed)...")
    t0 = time.time()
    df_melted = df_raw.reset_index().melt(
        id_vars="index", var_name="sensor_id", value_name="speed"
    )
    df_melted.rename(columns={"index": "timestamp"}, inplace=True)
    df_melted["sensor_id"] = df_melted["sensor_id"].astype(str)
    df_melted["speed"] = df_melted["speed"].astype(float)

    # Ingest into PySpark DataFrame
    spark_df = spark.createDataFrame(df_melted)
    print(f"      Created Spark DataFrame ({len(df_melted):,} rows) in {time.time() - t0:.2f}s")
    return spark_df


def clean_sensor_values(df):
    """
    Step 2: Converts 0.0 mph dropouts to null.
    Avoids expensive global iterative fills; rows with unavailable historical
    or current data will be cleanly pruned during feature filtering.
    """
    print("[3/7] Converting sensor dropouts (0.0 mph) to NULL...")
    return df.withColumn(
        "speed",
        F.when(F.col("speed") == 0.0, None).otherwise(F.col("speed")),
    )


def create_time_features(df):
    """
    Step 3: Creates core calendar features:
      - hour (0-23)
      - minute (0-55)
      - day_of_week (1=Sunday, 2=Monday, ..., 7=Saturday)
      - is_weekend (1 if weekend, else 0)
    """
    print("[4/7] Generating temporal features (hour, minute, day_of_week, is_weekend)...")
    return (
        df.withColumn("hour", F.hour(F.col("timestamp")))
        .withColumn("minute", F.minute(F.col("timestamp")))
        .withColumn("day_of_week", F.dayofweek(F.col("timestamp")))
        .withColumn(
            "is_weekend",
            F.when(F.col("day_of_week").isin([1, 7]), 1).otherwise(0),
        )
    )


def create_lag_and_target_features(df):
    """
    Steps 4-8:
      - Repartitions once by sensor_id to co-locate all timestamps for each sensor.
      - Uses a unified Window partitioned by sensor_id and ordered by timestamp.
      - Generates:
          * speed_lag_1 (5 mins ago, t-1)
          * speed_lag_2 (10 mins ago, t-2)
          * speed_lag_3 (15 mins ago, t-3)
          * rolling_mean_3 (average of t, t-1, t-2)
          * future_speed_15min (target: 15 mins ahead, t+3 lead)
      - Prunes boundary rows and dropout rows where any required feature or target is null.
      - Selects the final clean feature column set.
    """
    print("[5/7] Partitioning by sensor_id and creating lag, rolling, and target features...")

    # Step 4: Repartition by sensor_id once so window operations run without additional shuffles
    df_partitioned = df.repartition(16, "sensor_id")

    # Unified Window specification for all lag, rolling, and target operations
    w = Window.partitionBy("sensor_id").orderBy("timestamp")
    w_roll3 = Window.partitionBy("sensor_id").orderBy("timestamp").rowsBetween(-2, 0)

    # Step 5: Lags
    # Step 6: Target (lead 3 steps = 15 minutes)
    # Step 7: Rolling mean over recent 3 measurements (t-2 to t)
    df_features = (
        df_partitioned.withColumn("speed_lag_1", F.lag(F.col("speed"), 1).over(w))
        .withColumn("speed_lag_2", F.lag(F.col("speed"), 2).over(w))
        .withColumn("speed_lag_3", F.lag(F.col("speed"), 3).over(w))
        .withColumn("future_speed_15min", F.lead(F.col("speed"), 3).over(w))
        .withColumn("rolling_mean_3", F.avg(F.col("speed")).over(w_roll3))
    )

    # Step 8: Remove invalid training rows where any required feature or target is null
    df_clean = df_features.filter(
        F.col("speed").isNotNull()
        & F.col("speed_lag_1").isNotNull()
        & F.col("speed_lag_2").isNotNull()
        & F.col("speed_lag_3").isNotNull()
        & F.col("future_speed_15min").isNotNull()
        & F.col("rolling_mean_3").isNotNull()
    )

    # Step 9: Select final feature schema
    final_cols = [
        "timestamp",
        "sensor_id",
        "speed",
        "speed_lag_1",
        "speed_lag_2",
        "speed_lag_3",
        "rolling_mean_3",
        "hour",
        "minute",
        "day_of_week",
        "is_weekend",
        "future_speed_15min",
    ]

    return df_clean.select(*final_cols)


def save_processed_data(df, output_path: str):
    """
    Step 9: Saves the processed dataset to Parquet in a single write job.
    Coalesces to 8 partitions for optimal storage and high read throughput.
    """
    print(f"[6/7] Writing processed Parquet dataset to: {output_path}")
    t0 = time.time()
    os.makedirs(output_path, exist_ok=True)
    df.coalesce(8).write.mode("overwrite").parquet(output_path)
    print(f"      Parquet dataset successfully written in {time.time() - t0:.2f}s")


def validate_output(output_path: str, spark: SparkSession, raw_count: int, n_sensors: int):
    """
    Step 11: Validates the written Parquet dataset with targeted, efficient checks.
    """
    print("\n" + "=" * 60)
    print("[7/7] VALIDATION & SUMMARY")
    print("=" * 60)

    val_df = spark.read.parquet(output_path)
    processed_count = val_df.count()
    validated_sensors = val_df.select("sensor_id").distinct().count()

    print(f"\n* Input Dimensions:    {raw_count:,} records ({n_sensors} sensors)")
    print(f"* Output Row Count:    {processed_count:,} ML-ready records")
    print(f"* Retention Rate:      {(processed_count / raw_count) * 100:.2f}%")
    print(f"* Validated Sensors:   {validated_sensors}")
    print(f"* Output File Path:    {output_path}")

    # Check for any remaining nulls across key columns
    null_count = val_df.filter(
        F.col("speed").isNull()
        | F.col("speed_lag_1").isNull()
        | F.col("speed_lag_3").isNull()
        | F.col("future_speed_15min").isNull()
    ).count()
    print(f"* Remaining Nulls:     {null_count} (0 expected)")

    print("\n* Output Schema:")
    val_df.printSchema()

    print("\n* First 10 Processed Rows:")
    val_df.show(10, truncate=False)

    print("=" * 60)
    print("TRAFFICPULSE STAGE 2 PREPROCESSING COMPLETE")
    print("=" * 60)


def main():
    t_start = time.time()

    raw_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    processed_dir = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
    h5_path = os.path.join(raw_dir, "METR-LA.h5")
    output_parquet = os.path.join(processed_dir, "traffic_features.parquet")

    spark = get_spark_session()

    try:
        # Step 1: Load raw HDF5 data
        df_raw, n_timestamps, n_sensors = load_raw_data(h5_path)
        raw_count = n_timestamps * n_sensors

        # Step 1 (cont.): Convert to long format
        spark_df = convert_to_long_format(df_raw, spark)

        # Step 2: Handle sensor dropouts (convert 0.0 to null)
        clean_df = clean_sensor_values(spark_df)

        # Step 3: Calendar features
        time_df = create_time_features(clean_df)

        # Steps 4-8: Repartition, Lags, Target, Rolling, and Prune
        final_df = create_lag_and_target_features(time_df)

        # Step 9: Save as Parquet
        save_processed_data(final_df, output_parquet)

        # Step 11: Validate output
        validate_output(output_parquet, spark, raw_count, n_sensors)

        print(f"\nTotal Pipeline Elapsed Time: {time.time() - t_start:.2f}s")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
