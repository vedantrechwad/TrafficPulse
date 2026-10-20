"""
TrafficPulse - Stage 6: Congestion Propagation Analysis Module
Analyzes traffic network relationships and associated downstream congestion
using the METR-LA road sensor adjacency matrix (adj_METR-LA.pkl).

Note on Scientific Interpretation:
  This module analyzes graph connectivity and associated congestion states
  across physical highway loop detector locations. Network association does
  not assert causal or physical causality.
"""

import os
import csv
import pickle
from typing import Dict, Any, List, Optional, Tuple
import numpy as np


def load_adjacency_graph(
    pkl_path: Optional[str] = None,
) -> Tuple[List[str], Dict[str, int], np.ndarray]:
    """
    Loads and unpacks the METR-LA sensor network adjacency graph.
    Returns:
      - sensor_ids: list of 207 sensor ID strings
      - sensor_to_ind: dict mapping sensor_id to matrix row/col index
      - adj_mx: 207x207 numpy.ndarray of directed Gaussian distance weights
    """
    if pkl_path is None:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        pkl_path = os.path.join(project_root, "data", "raw", "adj_METR-LA.pkl")

    if not os.path.exists(pkl_path):
        raise FileNotFoundError(f"Adjacency graph file not found: {pkl_path}")

    with open(pkl_path, "rb") as f:
        sensor_ids, sensor_to_ind, adj_mx = pickle.load(f, encoding="latin1")

    # Ensure IDs are strings
    sensor_ids = [str(s) for s in sensor_ids]
    sensor_to_ind = {str(k): int(v) for k, v in sensor_to_ind.items()}
    return sensor_ids, sensor_to_ind, adj_mx


def load_sensor_locations(locations_path: Optional[str] = None) -> Dict[str, Dict[str, float]]:
    """
    Loads verified GPS coordinates for all 207 METR-LA sensors.
    """
    if locations_path is None:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        locations_path = os.path.join(project_root, "data", "processed", "sensor_locations.csv")

    locations: Dict[str, Dict[str, float]] = {}
    if os.path.exists(locations_path):
        with open(locations_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                s_id = str(row["sensor_id"]).strip()
                locations[s_id] = {
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                }
    return locations


def get_neighbors(
    sensor_id: str,
    sensor_ids: List[str],
    sensor_to_ind: Dict[str, int],
    adj_mx: np.ndarray,
    locations_map: Optional[Dict[str, Dict[str, float]]] = None,
) -> List[Dict[str, Any]]:
    """
    Extracts outgoing connected neighbors for sensor_id (excluding self-loop),
    sorted by adjacency connection weight descending.
    """
    s_id = str(sensor_id).strip()
    if s_id not in sensor_to_ind:
        raise KeyError(f"Sensor ID '{s_id}' not found in adjacency graph.")

    idx = sensor_to_ind[s_id]
    row = adj_mx[idx]

    neighbors = []
    for j, weight in enumerate(row):
        if j != idx and weight > 0:
            neighbor_id = sensor_ids[j]
            coords = locations_map.get(neighbor_id, {"latitude": 34.0522, "longitude": -118.2437}) if locations_map else {"latitude": 34.0522, "longitude": -118.2437}
            neighbors.append({
                "sensor_id": neighbor_id,
                "weight": round(float(weight), 4),
                "latitude": coords["latitude"],
                "longitude": coords["longitude"],
            })

    # Sort by connection weight descending
    neighbors.sort(key=lambda x: x["weight"], reverse=True)
    return neighbors


def get_top_neighbors(
    sensor_id: str,
    sensor_ids: List[str],
    sensor_to_ind: Dict[str, int],
    adj_mx: np.ndarray,
    k: int = 5,
    locations_map: Optional[Dict[str, Dict[str, float]]] = None,
) -> List[Dict[str, Any]]:
    """Returns top-k connected neighbors by edge weight."""
    all_neighbors = get_neighbors(sensor_id, sensor_ids, sensor_to_ind, adj_mx, locations_map)
    return all_neighbors[:k]


def analyze_congestion_neighbors(
    sensor_id: str,
    observations_map: Dict[str, Dict[str, Any]],
    sensor_ids: List[str],
    sensor_to_ind: Dict[str, int],
    adj_mx: np.ndarray,
    locations_map: Optional[Dict[str, Dict[str, float]]] = None,
    speed_delta: float = 0.0,
    config_categories: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Computes network congestion propagation metrics for a selected sensor:
      - Outgoing connected sensors and their live speeds/congestion.
      - If speed_delta != 0, propagates the hypothetical perturbation along physical graph edges:
          propagated_speed = clamp(base_speed + weight * speed_delta, 5.0, 80.0)
      - Counts of connected sensors in HIGH, MEDIUM, and LOW states.
      - Weighted network congestion score:
          score = sum(weight * state_val) / sum(weight)
          where LOW=0.0, MEDIUM=0.5, HIGH=1.0.
    """
    s_id = str(sensor_id).strip()
    sensor_obs = observations_map.get(s_id, {})
    sensor_speed = sensor_obs.get("speed", 50.0)
    sensor_congestion = sensor_obs.get("congestion_level", "LOW")

    raw_neighbors = get_neighbors(s_id, sensor_ids, sensor_to_ind, adj_mx, locations_map)

    enriched_neighbors = []
    high_count = 0
    medium_count = 0
    low_count = 0

    total_weighted_state = 0.0
    total_weight = 0.0

    state_weights = {"LOW": 0.0, "MEDIUM": 0.5, "HIGH": 1.0}

    low_thresh = 50.0
    med_thresh = 30.0
    if config_categories:
        low_thresh = config_categories.get("LOW", {}).get("min_speed", 50.0)
        med_thresh = config_categories.get("MEDIUM", {}).get("min_speed", 30.0)

    for n in raw_neighbors:
        n_id = n["sensor_id"]
        n_obs = observations_map.get(n_id, {})
        n_speed_base = float(n_obs.get("speed", 50.0))

        if speed_delta != 0.0:
            propagated_change = n["weight"] * speed_delta
            n_speed = round(max(5.0, min(80.0, n_speed_base + propagated_change)), 2)
            if n_speed >= low_thresh:
                n_congestion = "LOW"
            elif n_speed >= med_thresh:
                n_congestion = "MEDIUM"
            else:
                n_congestion = "HIGH"
        else:
            n_speed = round(n_speed_base, 2)
            n_congestion = n_obs.get("congestion_level")
            if not n_congestion:
                if n_speed >= low_thresh:
                    n_congestion = "LOW"
                elif n_speed >= med_thresh:
                    n_congestion = "MEDIUM"
                else:
                    n_congestion = "HIGH"

        if n_congestion == "HIGH":
            high_count += 1
        elif n_congestion == "MEDIUM":
            medium_count += 1
        else:
            low_count += 1

        w = n["weight"]
        total_weighted_state += w * state_weights.get(n_congestion, 0.0)
        total_weight += w

        enriched_neighbors.append({
            "sensor_id": n_id,
            "weight": n["weight"],
            "speed_mph": n_speed,
            "congestion_level": n_congestion,
            "latitude": n["latitude"],
            "longitude": n["longitude"],
        })

    weighted_score = (
        round(total_weighted_state / total_weight, 2) if total_weight > 0 else 0.0
    )

    return {
        "sensor_id": s_id,
        "sensor_speed_mph": round(float(sensor_speed), 2),
        "sensor_congestion": sensor_congestion,
        "neighbor_count": len(enriched_neighbors),
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "weighted_congestion_score": weighted_score,
        "neighbors": enriched_neighbors,
    }


def main():
    print("=" * 60)
    print("TRAFFICPULSE PROPAGATION MODULE VERIFICATION")
    print("=" * 60)

    sensor_ids, sensor_to_ind, adj_mx = load_adjacency_graph()
    locations = load_sensor_locations()

    sample_sensor = "716955"
    neighbors = get_neighbors(sample_sensor, sensor_ids, sensor_to_ind, adj_mx, locations)
    print(f"\nSample Sensor: {sample_sensor}")
    print(f"Connected Outgoing Neighbors: {len(neighbors)}")
    for n in neighbors:
        print(f"  -> Station {n['sensor_id']} | Weight: {n['weight']} | Coordinates: ({n['latitude']}, {n['longitude']})")

    # Mock observation check
    mock_obs = {
        "716955": {"speed": 42.5, "congestion_level": "MEDIUM"},
        "716949": {"speed": 28.0, "congestion_level": "HIGH"},
        "718371": {"speed": 41.2, "congestion_level": "MEDIUM"},
        "760650": {"speed": 55.4, "congestion_level": "LOW"},
        "773013": {"speed": 34.0, "congestion_level": "MEDIUM"},
        "716953": {"speed": 25.1, "congestion_level": "HIGH"},
    }

    analysis = analyze_congestion_neighbors(sample_sensor, mock_obs, sensor_ids, sensor_to_ind, adj_mx, locations)
    print("\nPropagation Analysis Metric Output:")
    print(f"  Neighbor Count:           {analysis['neighbor_count']}")
    print(f"  High Congestion Neighbors: {analysis['high_count']}")
    print(f"  Medium Congestion Neighbors: {analysis['medium_count']}")
    print(f"  Low Congestion Neighbors:  {analysis['low_count']}")
    print(f"  Weighted Congestion Score: {analysis['weighted_congestion_score']}")


if __name__ == "__main__":
    main()
