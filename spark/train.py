"""
TrafficPulse - Stage 3: Machine Learning Training and Evaluation Pipeline
Trains, compares, evaluates, and persists Spark ML regression models for 15-minute
traffic speed forecasting on the METR-LA dataset.

Pipeline:
  1. Load processed Parquet dataset (data/processed/traffic_features.parquet).
  2. Perform chronological (non-shuffled) train (70%) / validation (15%) / test (15%) split.
  3. Feature Engineering via Spark ML Pipeline:
     - StringIndexer + OneHotEncoder for categorical sensor_id
     - VectorAssembler combining lags, rolling mean, temporal features, and sensor vectors.
  4. Train Baseline Model (LinearRegression) on Train, evaluate on Validation.
  5. Train Non-Linear Model (RandomForestRegressor) on Train, evaluate on Validation.
  6. Compare models (MAE, RMSE, R²) and select top-performing model.
  7. Retrain selected model on combined Train + Validation data.
  8. Final evaluation on the unseen Test set.
  9. Persist fitted PipelineModel to models/traffic_speed_model.
 10. Persist metadata and configurable congestion thresholds to JSON.
"""

import os
import sys
import time
import json
from datetime import datetime

# Windows Hadoop & PySpark configuration
hadoop_home = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "hadoop"))
if os.path.exists(hadoop_home):
    os.environ["HADOOP_HOME"] = hadoop_home
    os.environ["PATH"] = os.path.join(hadoop_home, "bin") + ";" + os.environ.get("PATH", "")

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.ml import Pipeline
from pyspark.ml.feature import StringIndexer, OneHotEncoder, VectorAssembler
from pyspark.ml.regression import LinearRegression, RandomForestRegressor
from pyspark.ml.evaluation import RegressionEvaluator


def get_spark_session(app_name: str = "TrafficPulse_Training") -> SparkSession:
    """Initializes SparkSession optimized for ML model training."""
    spark = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", "6g")
        .config("spark.sql.shuffle.partitions", "16")
        .config("spark.driver.host", "localhost")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def load_dataset(parquet_path: str, spark: SparkSession):
    """Loads processed Parquet features and prints basic info."""
    print(f"\n[Step 3.1] Loading processed features from: {parquet_path}")
    df = spark.read.parquet(parquet_path)
    total_records = df.count()
    print(f"  Total ML-Ready Records: {total_records:,}")
    return df, total_records


def split_data_chronologically(df):
    """
    Step 3.5: Chronological Train (70%) / Validation (15%) / Test (15%) split.
    Guarantees strict time ordering with zero temporal overlap.
    """
    print("\n[Step 3.5] Performing Chronological Time-Series Split (70% Train / 15% Val / 15% Test)...")
    t0 = time.time()
    
    # Extract distinct timestamps in sorted chronological order
    timestamps = [
        r[0]
        for r in df.select("timestamp").distinct().orderBy("timestamp").collect()
    ]
    n_times = len(timestamps)

    train_idx = int(n_times * 0.70)
    val_idx = int(n_times * 0.85)

    train_start = timestamps[0]
    train_end = timestamps[train_idx - 1]
    val_start = timestamps[train_idx]
    val_end = timestamps[val_idx - 1]
    test_start = timestamps[val_idx]
    test_end = timestamps[-1]

    train_df = df.filter(F.col("timestamp") <= train_end)
    val_df = df.filter(
        (F.col("timestamp") >= val_start) & (F.col("timestamp") <= val_end)
    )
    test_df = df.filter(F.col("timestamp") >= test_start)

    train_count = train_df.count()
    val_count = val_df.count()
    test_count = test_df.count()

    print(f"  TRAIN SET:      {train_start}  -->  {train_end} | {train_count:,} records ({(train_count / (train_count + val_count + test_count))*100:.1f}%)")
    print(f"  VALIDATION SET: {val_start}  -->  {val_end} | {val_count:,} records ({(val_count / (train_count + val_count + test_count))*100:.1f}%)")
    print(f"  TEST SET:       {test_start}  -->  {test_end} | {test_count:,} records ({(test_count / (train_count + val_count + test_count))*100:.1f}%)")
    print(f"  Split computed in {time.time() - t0:.2f}s (Verified: 0 temporal overlap)")

    split_info = {
        "train_period": f"{train_start} to {train_end}",
        "val_period": f"{val_start} to {val_end}",
        "test_period": f"{test_start} to {test_end}",
        "train_count": train_count,
        "val_count": val_count,
        "test_count": test_count,
    }

    return train_df, val_df, test_df, split_info


def build_feature_pipeline(regressor):
    """
    Steps 3.3 & 3.4: Builds a reusable Spark ML Pipeline:
      1. StringIndexer: maps categorical sensor_id strings to integer indices.
      2. OneHotEncoder: converts sensor indices to binary sparse indicator vectors.
      3. VectorAssembler: merges numerical features + sensor one-hot vector into 'features'.
      4. regressor: the specified estimator (LinearRegression or RandomForestRegressor).
    """
    indexer = StringIndexer(
        inputCol="sensor_id", outputCol="sensor_idx", handleInvalid="keep"
    )
    encoder = OneHotEncoder(inputCol="sensor_idx", outputCol="sensor_vec")

    feature_cols = [
        "speed",
        "speed_lag_1",
        "speed_lag_2",
        "speed_lag_3",
        "rolling_mean_3",
        "hour",
        "minute",
        "day_of_week",
        "is_weekend",
        "sensor_vec",
    ]

    assembler = VectorAssembler(inputCols=feature_cols, outputCol="features")
    pipeline = Pipeline(stages=[indexer, encoder, assembler, regressor])
    return pipeline


def evaluate_predictions(predictions, label_col="future_speed_15min", pred_col="prediction"):
    """Calculates MAE, RMSE, and R2 on predictions."""
    evaluator_mae = RegressionEvaluator(
        labelCol=label_col, predictionCol=pred_col, metricName="mae"
    )
    evaluator_rmse = RegressionEvaluator(
        labelCol=label_col, predictionCol=pred_col, metricName="rmse"
    )
    evaluator_r2 = RegressionEvaluator(
        labelCol=label_col, predictionCol=pred_col, metricName="r2"
    )

    mae = float(evaluator_mae.evaluate(predictions))
    rmse = float(evaluator_rmse.evaluate(predictions))
    r2 = float(evaluator_r2.evaluate(predictions))

    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "r2": round(r2, 4)}


def train_baseline_linear_regression(train_df, val_df):
    """
    Step 3.6: Trains baseline LinearRegression model.
    """
    print("\n[Step 3.6] Training Baseline Model: Linear Regression...")
    t0 = time.time()
    lr = LinearRegression(
        featuresCol="features",
        labelCol="future_speed_15min",
        maxIter=25,
        regParam=0.01,
    )
    lr_pipeline = build_feature_pipeline(lr)
    lr_model = lr_pipeline.fit(train_df)
    train_time = time.time() - t0
    print(f"  Linear Regression trained in {train_time:.2f}s")

    preds = lr_model.transform(val_df)
    metrics = evaluate_predictions(preds)
    print(f"  Validation Metrics -> MAE: {metrics['mae']} mph | RMSE: {metrics['rmse']} mph | R2: {metrics['r2']}")

    return lr_model, metrics, train_time


def train_random_forest(train_df, val_df):
    """
    Step 3.7: Trains non-linear RandomForestRegressor model.
    Configured for practical, robust local performance.
    """
    print("\n[Step 3.7] Training Non-Linear Model: Random Forest Regressor...")
    t0 = time.time()
    rf = RandomForestRegressor(
        featuresCol="features",
        labelCol="future_speed_15min",
        numTrees=20,
        maxDepth=6,
        seed=42,
    )
    rf_pipeline = build_feature_pipeline(rf)
    rf_model = rf_pipeline.fit(train_df)
    train_time = time.time() - t0
    print(f"  Random Forest trained in {train_time:.2f}s")

    preds = rf_model.transform(val_df)
    metrics = evaluate_predictions(preds)
    print(f"  Validation Metrics -> MAE: {metrics['mae']} mph | RMSE: {metrics['rmse']} mph | R2: {metrics['r2']}")

    return rf_model, metrics, train_time


def compare_and_select(lr_metrics, rf_metrics):
    """
    Step 3.8: Compares validation results and selects the best model.
    """
    print("\n" + "=" * 60)
    print("[Step 3.8] MODEL COMPARISON (VALIDATION SET)")
    print("=" * 60)
    print(f"{'Model':<22} | {'MAE (mph)':<10} | {'RMSE (mph)':<10} | {'R2':<8}")
    print("-" * 60)
    print(f"{'Linear Regression':<22} | {lr_metrics['mae']:<10.4f} | {lr_metrics['rmse']:<10.4f} | {lr_metrics['r2']:<8.4f}")
    print(f"{'Random Forest':<22} | {rf_metrics['mae']:<10.4f} | {rf_metrics['rmse']:<10.4f} | {rf_metrics['r2']:<8.4f}")
    print("-" * 60)

    # Select based on lowest MAE on validation set
    if rf_metrics["mae"] < lr_metrics["mae"]:
        selected = "Random Forest"
        print("  Selected Model: Random Forest (lower validation error)")
    else:
        selected = "Linear Regression"
        print("  Selected Model: Linear Regression (lower validation error / higher R2)")

    return selected


def retrain_final_model(selected_name, train_df, val_df):
    """
    Step 3.9: Retrains selected model architecture on combined TRAIN + VALIDATION set.
    The test set remains completely unseen until final evaluation.
    """
    print(f"\n[Step 3.9] Retraining {selected_name} on Combined Train + Validation Data...")
    t0 = time.time()
    train_val_df = train_df.unionByName(val_df)

    if selected_name == "Random Forest":
        regressor = RandomForestRegressor(
            featuresCol="features",
            labelCol="future_speed_15min",
            numTrees=20,
            maxDepth=6,
            seed=42,
        )
        params = {"numTrees": 20, "maxDepth": 6, "seed": 42}
    else:
        regressor = LinearRegression(
            featuresCol="features",
            labelCol="future_speed_15min",
            maxIter=25,
            regParam=0.01,
        )
        params = {"maxIter": 25, "regParam": 0.01}

    pipeline = build_feature_pipeline(regressor)
    final_model = pipeline.fit(train_val_df)
    print(f"  Final Model retrained in {time.time() - t0:.2f}s")
    return final_model, params


def evaluate_final_test(final_model, test_df):
    """
    Step 3.10: Evaluates final retrained model on the untouched Test set.
    Prints actual vs predicted sample.
    """
    print("\n[Step 3.10] Evaluating Final Model on Unseen Test Set...")
    t0 = time.time()
    test_preds = final_model.transform(test_df)
    test_metrics = evaluate_predictions(test_preds)

    print(f"  Final Test Metrics:")
    print(f"    - Test MAE:  {test_metrics['mae']} mph")
    print(f"    - Test RMSE: {test_metrics['rmse']} mph")
    print(f"    - Test R2:   {test_metrics['r2']}")
    print(f"  Evaluation completed in {time.time() - t0:.2f}s")

    # Sample 10 actual-vs-predicted records
    print("\n  Sample Actual vs Predicted Speeds (First 10 Unseen Test Records):")
    sample_df = (
        test_preds.select(
            "timestamp",
            "sensor_id",
            "speed",
            F.col("future_speed_15min").alias("actual_speed"),
            F.col("prediction").alias("predicted_speed"),
            F.abs(F.col("future_speed_15min") - F.col("prediction")).alias("error"),
        )
        .limit(10)
        .collect()
    )

    print(f"  {'Timestamp':<20} | {'Sensor':<8} | {'Current':<8} | {'Actual(+15m)':<12} | {'Predicted(+15m)':<15} | {'Error (mph)':<10}")
    print("  " + "-" * 85)
    for r in sample_df:
        print(
            f"  {str(r['timestamp']):<20} | {r['sensor_id']:<8} | {r['speed']:<8.2f} | {r['actual_speed']:<12.2f} | {r['predicted_speed']:<15.2f} | {r['error']:<10.2f}"
        )

    return test_metrics


def save_model_and_metadata(
    final_model,
    selected_name,
    params,
    lr_metrics,
    rf_metrics,
    test_metrics,
    split_info,
    models_dir: str,
):
    """
    Step 3.11: Persists the complete Spark ML PipelineModel and comprehensive metadata.
    """
    model_path = os.path.join(models_dir, "traffic_speed_model")
    metadata_path = os.path.join(models_dir, "model_metadata.json")
    os.makedirs(models_dir, exist_ok=True)

    print(f"\n[Step 3.11] Saving Spark ML PipelineModel to: {model_path}")
    t0 = time.time()
    final_model.write().overwrite().save(model_path)
    print(f"  Model saved successfully in {time.time() - t0:.2f}s")

    feature_names = [
        "speed",
        "speed_lag_1",
        "speed_lag_2",
        "speed_lag_3",
        "rolling_mean_3",
        "hour",
        "minute",
        "day_of_week",
        "is_weekend",
        "sensor_id_one_hot",
    ]

    metadata = {
        "project": "TrafficPulse",
        "model_type": selected_name,
        "prediction_horizon": "15 minutes ahead (future_speed_15min)",
        "features": feature_names,
        "target": "future_speed_15min",
        "model_parameters": params,
        "training_timestamp": datetime.now().isoformat(),
        "splits": split_info,
        "validation_comparison": {
            "linear_regression": lr_metrics,
            "random_forest": rf_metrics,
        },
        "final_test_metrics": test_metrics,
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  Metadata saved to: {metadata_path}")


def save_congestion_config(config_dir: str):
    """
    Step 3.12: Persists configurable congestion thresholds to JSON.
    """
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, "congestion_config.json")

    congestion_config = {
        "description": "TrafficPulse Congestion Classification Thresholds (Visualization & Analysis)",
        "unit": "mph",
        "categories": {
            "LOW": {
                "min_speed": 50.0,
                "max_speed": None,
                "label": "Low Congestion (Free Flow)",
                "color": "#10B981",  # Green
            },
            "MEDIUM": {
                "min_speed": 30.0,
                "max_speed": 50.0,
                "label": "Medium Congestion (Moderate Delay)",
                "color": "#F59E0B",  # Amber/Yellow
            },
            "HIGH": {
                "min_speed": 0.0,
                "max_speed": 30.0,
                "label": "High Congestion (Severe Delay / Stop & Go)",
                "color": "#EF4444",  # Red
            },
        },
    }

    with open(config_path, "w") as f:
        json.dump(congestion_config, f, indent=2)
    print(f"[Step 3.12] Saved configurable congestion thresholds to: {config_path}")


def main():
    t_start = time.time()
    spark = get_spark_session()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    parquet_path = os.path.join(project_root, "data", "processed", "traffic_features.parquet")
    models_dir = os.path.join(project_root, "models")
    config_dir = os.path.join(project_root, "config")

    try:
        # 1. Load data
        df, total_records = load_dataset(parquet_path, spark)

        # 2. Chronological Split
        train_df, val_df, test_df, split_info = split_data_chronologically(df)

        # 3. Train Baseline (Linear Regression)
        lr_model, lr_metrics, lr_time = train_baseline_linear_regression(train_df, val_df)

        # 4. Train Non-Linear (Random Forest)
        rf_model, rf_metrics, rf_time = train_random_forest(train_df, val_df)

        # 5. Model Comparison & Selection
        selected_name = compare_and_select(lr_metrics, rf_metrics)

        # 6. Retrain Selected Model on Train + Val
        final_model, params = retrain_final_model(selected_name, train_df, val_df)

        # 7. Final Test Evaluation
        test_metrics = evaluate_final_test(final_model, test_df)

        # 8. Save Model & Metadata
        save_model_and_metadata(
            final_model,
            selected_name,
            params,
            lr_metrics,
            rf_metrics,
            test_metrics,
            split_info,
            models_dir,
        )

        # 9. Save Congestion Configuration
        save_congestion_config(config_dir)

        # Final Summary
        print("\n" + "=" * 60)
        print("TRAFFICPULSE MODEL TRAINING COMPLETE")
        print("=" * 60)
        print(f"Dataset:              {parquet_path}")
        print(f"Total records:        {total_records:,}")
        print(f"Training records:     {split_info['train_count']:,}")
        print(f"Validation records:   {split_info['val_count']:,}")
        print(f"Test records:         {split_info['test_count']:,}")
        print("-" * 60)
        print("MODEL COMPARISON (VALIDATION):")
        print(f"  Linear Regression -> MAE: {lr_metrics['mae']} | RMSE: {lr_metrics['rmse']} | R2: {lr_metrics['r2']}")
        print(f"  Random Forest     -> MAE: {rf_metrics['mae']} | RMSE: {rf_metrics['rmse']} | R2: {rf_metrics['r2']}")
        print("-" * 60)
        print("FINAL MODEL:")
        print(f"  Selected Model:     {selected_name}")
        print(f"  Test MAE:           {test_metrics['mae']} mph")
        print(f"  Test RMSE:          {test_metrics['rmse']} mph")
        print(f"  Test R2:            {test_metrics['r2']}")
        print(f"  Model Saved:        {os.path.join(models_dir, 'traffic_speed_model')}")
        print(f"  Metadata Saved:     {os.path.join(models_dir, 'model_metadata.json')}")
        print(f"  Total Duration:     {time.time() - t_start:.2f}s")
        print("=" * 60)

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
