"""
TrafficPulse - Stage 1: Dataset Inspection Script
Inspects raw METR-LA traffic speed dataset (METR-LA.h5) and
sensor network adjacency graph (adj_METR-LA.pkl).
"""

import os
import pickle
import numpy as np
import pandas as pd
import h5py


def inspect_metr_la_h5(filepath: str) -> dict:
    """Inspects METR-LA.h5 traffic speed data."""
    print("=" * 70)
    print("1. INSPECTING TRAFFIC SPEED DATASET: METR-LA.h5")
    print("=" * 70)

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    # Inspect internal HDF5 structure
    print(f"\n[HDF5 File Structure]")
    with h5py.File(filepath, "r") as h5_file:
        keys = list(h5_file.keys())
        print(f"  Root Keys: {keys}")
        for k in keys:
            print(f"  - Key '{k}': type={type(h5_file[k])}")

    # Load with pandas HDFStore
    df = pd.read_hdf(filepath)

    n_timestamps, n_sensors = df.shape
    total_cells = df.size
    time_index = df.index

    # Timestamps analysis
    start_time = time_index.min()
    end_time = time_index.max()
    freq = time_index[1] - time_index[0] if len(time_index) > 1 else None
    is_monotonic = time_index.is_monotonic_increasing

    # Missing values analysis
    nan_count = int(df.isna().sum().sum())
    nan_pct = (nan_count / total_cells) * 100
    zero_count = int((df == 0.0).sum().sum())
    zero_pct = (zero_count / total_cells) * 100

    # Traffic speed statistics (Overall)
    overall_min = float(df.min().min())
    overall_max = float(df.max().max())
    overall_mean = float(df.mean().mean())
    overall_median = float(df.median().median())
    overall_std = float(df.values.std())

    # Traffic speed statistics (Non-Zero: active traffic speeds)
    non_zero_speeds = df.values[df.values > 0]
    nz_min = float(non_zero_speeds.min()) if len(non_zero_speeds) > 0 else 0.0
    nz_max = float(non_zero_speeds.max()) if len(non_zero_speeds) > 0 else 0.0
    nz_mean = float(non_zero_speeds.mean()) if len(non_zero_speeds) > 0 else 0.0
    nz_median = float(np.median(non_zero_speeds)) if len(non_zero_speeds) > 0 else 0.0
    nz_std = float(non_zero_speeds.std()) if len(non_zero_speeds) > 0 else 0.0
    nz_q25 = float(np.percentile(non_zero_speeds, 25)) if len(non_zero_speeds) > 0 else 0.0
    nz_q75 = float(np.percentile(non_zero_speeds, 75)) if len(non_zero_speeds) > 0 else 0.0

    # Sensor IDs
    sensor_ids = list(df.columns)

    print(f"\n[Dimensions & Temporal Scope]")
    print(f"  Shape (Timestamps x Sensors): {n_timestamps:,} x {n_sensors}")
    print(f"  Total Data Points: {total_cells:,}")
    print(f"  Start Timestamp: {start_time}")
    print(f"  End Timestamp:   {end_time}")
    print(f"  Temporal Sampling Interval: {freq}")
    print(f"  Total Duration: {(end_time - start_time).days} days, {(end_time - start_time).components.hours} hours")
    print(f"  Is Chronologically Monotonic: {is_monotonic}")

    print(f"\n[Sensors]")
    print(f"  Number of Sensors: {n_sensors}")
    print(f"  Sensor ID Data Type: {type(sensor_ids[0]).__name__}")
    print(f"  First 5 Sensor IDs: {sensor_ids[:5]}")
    print(f"  Last 5 Sensor IDs:  {sensor_ids[-5:]}")

    print(f"\n[Missing Values & Sensor Outages]")
    print(f"  Explicit NaN / Null Count: {nan_count:,} ({nan_pct:.2f}%)")
    print(f"  Zero Readings (0.0 mph / sensor dropouts): {zero_count:,} ({zero_pct:.2f}%)")
    print(f"  Valid Active Readings (> 0.0 mph): {len(non_zero_speeds):,} ({100 - zero_pct:.2f}%)")

    print(f"\n[Speed Statistics - Overall (Including 0s)]")
    print(f"  Min:    {overall_min:.2f} mph")
    print(f"  Max:    {overall_max:.2f} mph")
    print(f"  Mean:   {overall_mean:.2f} mph")
    print(f"  Median: {overall_median:.2f} mph")
    print(f"  Std:    {overall_std:.2f} mph")

    print(f"\n[Speed Statistics - Active Traffic Only (> 0 mph)]")
    print(f"  Min:    {nz_min:.2f} mph")
    print(f"  25th%:  {nz_q25:.2f} mph")
    print(f"  Median: {nz_median:.2f} mph")
    print(f"  Mean:   {nz_mean:.2f} mph")
    print(f"  75th%:  {nz_q75:.2f} mph")
    print(f"  Max:    {nz_max:.2f} mph")
    print(f"  Std:    {nz_std:.2f} mph")

    return {
        "n_timestamps": n_timestamps,
        "n_sensors": n_sensors,
        "start_time": str(start_time),
        "end_time": str(end_time),
        "freq": str(freq),
        "sensor_ids": sensor_ids,
        "nan_count": nan_count,
        "zero_count": zero_count,
        "zero_pct": zero_pct,
        "overall_mean": overall_mean,
        "overall_std": overall_std,
        "nz_mean": nz_mean,
        "nz_std": nz_std,
    }


def inspect_adj_metr_la_pkl(filepath: str, expected_sensors: list = None) -> dict:
    """Inspects adj_METR-LA.pkl sensor network adjacency matrix."""
    print("\n" + "=" * 70)
    print("2. INSPECTING SENSOR ADJACENCY MATRIX: adj_METR-LA.pkl")
    print("=" * 70)

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(filepath, "rb") as f:
        # Note: 'latin1' encoding is required to unpack pickle files serialized in Python 2
        adj_data = pickle.load(f, encoding="latin1")

    print(f"\n[Pickle Container Structure]")
    print(f"  Type: {type(adj_data)}")
    print(f"  Elements Count: {len(adj_data)}")

    sensor_ids_adj = adj_data[0]
    sensor_to_ind = adj_data[1]
    adj_mx = adj_data[2]

    print(f"  - Element 0 (Sensor IDs): list of length {len(sensor_ids_adj)}")
    print(f"  - Element 1 (Sensor-to-Index Map): dict with {len(sensor_to_ind)} entries")
    print(f"  - Element 2 (Adjacency Matrix): numpy.ndarray with shape {adj_mx.shape}, dtype={adj_mx.dtype}")

    # Consistency check with HDF5 sensor list
    if expected_sensors is not None:
        ids_match = sensor_ids_adj == expected_sensors
        print(f"\n[Sensor ID Alignment Check]")
        print(f"  Matches METR-LA.h5 sensor IDs order exactly: {ids_match}")

    # Adjacency matrix properties
    n_rows, n_cols = adj_mx.shape
    total_pairs = n_rows * n_cols
    diagonal_elements = np.diag(adj_mx)
    self_loops = int(np.count_nonzero(diagonal_elements))

    # Exclude self-loops to compute actual inter-sensor network edges
    off_diag_mask = ~np.eye(n_rows, dtype=bool)
    inter_sensor_edges = int(np.count_nonzero(adj_mx[off_diag_mask]))
    total_edges = int(np.count_nonzero(adj_mx))

    zero_entries = int((adj_mx == 0.0).sum())
    sparsity_pct = (zero_entries / total_pairs) * 100

    min_weight = float(np.min(adj_mx))
    max_weight = float(np.max(adj_mx))
    mean_weight = float(np.mean(adj_mx))
    non_zero_weights = adj_mx[adj_mx > 0]
    nz_min_weight = float(np.min(non_zero_weights)) if len(non_zero_weights) > 0 else 0.0

    # Directed vs Symmetric check
    is_symmetric = np.allclose(adj_mx, adj_mx.T, atol=1e-5)

    # Degree statistics (out-degree: row sum of non-zero connections excluding self-loop)
    adj_no_diag = adj_mx.copy()
    np.fill_diagonal(adj_no_diag, 0)
    out_degrees = (adj_no_diag > 0).sum(axis=1)
    in_degrees = (adj_no_diag > 0).sum(axis=0)

    print(f"\n[Graph & Connectivity Analysis]")
    print(f"  Matrix Dimensions: {n_rows} x {n_cols}")
    print(f"  Total Sensor Pairs: {total_pairs:,}")
    print(f"  Zero Entries: {zero_entries:,} ({sparsity_pct:.2f}% sparsity)")
    print(f"  Total Non-Zero Elements (including self-loops): {total_edges:,}")
    print(f"  Self-Loop Entries (diagonal): {self_loops} (Value: {diagonal_elements[0]:.1f})")
    print(f"  Inter-Sensor Directed Edges (> 0 weight, excluding self): {inter_sensor_edges:,}")
    print(f"  Graph Is Symmetric (Undirected): {is_symmetric}")
    print(f"  Edge Weight Range (Non-zero): [{nz_min_weight:.6f}, {max_weight:.1f}]")
    print(f"  Average Out-Degree per Sensor: {out_degrees.mean():.2f} connected neighbors")
    print(f"  Min Out-Degree: {out_degrees.min()} neighbors")
    print(f"  Max Out-Degree: {out_degrees.max()} neighbors")
    print(f"  Average In-Degree per Sensor: {in_degrees.mean():.2f} incoming connections")

    print("\n" + "=" * 70)
    print("STAGE 1 INSPECTION COMPLETE.")
    print("=" * 70)

    return {
        "adj_shape": adj_mx.shape,
        "total_edges": total_edges,
        "inter_sensor_edges": inter_sensor_edges,
        "is_symmetric": is_symmetric,
        "sparsity_pct": sparsity_pct,
        "avg_out_degree": float(out_degrees.mean()),
        "max_out_degree": int(out_degrees.max()),
        "min_out_degree": int(out_degrees.min()),
    }


def main():
    raw_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    h5_path = os.path.join(raw_dir, "METR-LA.h5")
    pkl_path = os.path.join(raw_dir, "adj_METR-LA.pkl")

    h5_results = inspect_metr_la_h5(h5_path)
    inspect_adj_metr_la_pkl(pkl_path, expected_sensors=h5_results["sensor_ids"])


if __name__ == "__main__":
    main()
