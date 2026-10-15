"""
TrafficPulse - API Test Suite
Tests all FastAPI endpoints against the live Spark ML model using FastAPI TestClient.
"""

import sys
import os
import json

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from backend.main import app


def run_tests():
    print("=" * 60)
    print("RUNNING TRAFFICPULSE API TEST SUITE")
    print("=" * 60)

    # TestClient invokes the lifespan (startup/shutdown) automatically
    with TestClient(app) as client:
        print("\n--- Test 1: GET /api/health ---")
        res = client.get("/api/health")
        print(f"Status Code: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert res.json()["status"] == "healthy"
        assert res.json()["model_loaded"] is True
        print("[PASS] Health check PASSED")

        print("\n--- Test 2: GET /api/model-info ---")
        res = client.get("/api/model-info")
        print(f"Status Code: {res.status_code}")
        info = res.json()
        print(f"Model Type: {info.get('model_type')}")
        print(f"Test MAE: {info.get('final_test_metrics', {}).get('mae')} mph")
        print(f"Test RMSE: {info.get('final_test_metrics', {}).get('rmse')} mph")
        print(f"Test R2: {info.get('final_test_metrics', {}).get('r2')}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert "model_type" in info
        print("[PASS] Model info check PASSED")

        print("\n--- Test 3: GET /api/sensors ---")
        res = client.get("/api/sensors")
        print(f"Status Code: {res.status_code}")
        sensors_data = res.json()
        print(f"Total Sensors: {sensors_data.get('total_sensors')}")
        print(f"First 5 Sensors: {sensors_data.get('sensors')[:5]}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert sensors_data.get("total_sensors") == 207
        assert "716955" in sensors_data.get("sensors")
        print("[PASS] Sensors check PASSED")

        print("\n--- Test 3b: GET /api/sensor-observations ---")
        res = client.get("/api/sensor-observations")
        print(f"Status Code: {res.status_code}")
        obs_data = res.json()
        print(f"Total Observations: {len(obs_data)}")
        print(f"Sample Observation: {obs_data[0]}")
        assert res.status_code == 200
        assert len(obs_data) == 207
        assert "latitude" in obs_data[0]
        assert "longitude" in obs_data[0]
        assert "congestion_level" in obs_data[0]
        print("[PASS] Sensor observations check PASSED")

        print("\n--- Test 3c: GET /api/sensors/716955/history ---")
        res = client.get("/api/sensors/716955/history")
        print(f"Status Code: {res.status_code}")
        hist_data = res.json()
        print(f"History points for 716955: {len(hist_data.get('history', []))}")
        assert res.status_code == 200
        assert len(hist_data.get("history", [])) > 0
        print("[PASS] Sensor history check PASSED")

        print("\n--- Test 4: POST /api/predict (Valid Request) ---")
        valid_payload = {
            "timestamp": "2012-06-09T02:30:00",
            "sensor_id": "716955",
            "speed": 51.71,
            "speed_lag_1": 49.71,
            "speed_lag_2": 56.29,
            "speed_lag_3": 46.86,
            "rolling_mean_3": 52.76,
        }
        res = client.post("/api/predict", json=valid_payload)
        print(f"Status Code: {res.status_code}")
        pred_data = res.json()
        print(f"Prediction Response: {json.dumps(pred_data, indent=2)}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert pred_data["sensor_id"] == "716955"
        assert "predicted_speed_15min_mph" in pred_data
        assert pred_data["congestion_level"] in ["LOW", "MEDIUM", "HIGH"]
        assert pred_data["prediction_horizon_minutes"] == 15
        print("[PASS] Valid prediction check PASSED")

        print("\n--- Test 5: POST /api/predict (Invalid Sensor ID) ---")
        invalid_sensor_payload = {
            "timestamp": "2012-06-09T02:30:00",
            "sensor_id": "NON_EXISTENT_SENSOR_999999",
            "speed": 51.71,
            "speed_lag_1": 49.71,
            "speed_lag_2": 56.29,
            "speed_lag_3": 46.86,
            "rolling_mean_3": 52.76,
        }
        res = client.post("/api/predict", json=invalid_sensor_payload)
        print(f"Status Code: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        assert "not recognized" in res.json()["detail"]
        print("[PASS] Invalid sensor ID handled cleanly (404 Not Found) PASSED")

        print("\n--- Test 6: POST /api/predict (Missing Required Fields) ---")
        invalid_fields_payload = {
            "timestamp": "2012-06-09T02:30:00",
            "sensor_id": "716955",
            # missing speed, speed_lag_1, etc.
        }
        res = client.post("/api/predict", json=invalid_fields_payload)
        print(f"Status Code: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 422, f"Expected 422, got {res.status_code}"
        print("[PASS] Missing fields validation handled cleanly (422 Unprocessable Entity) PASSED")

        print("\n--- Test 7: POST /api/predict (Invalid Timestamp Format) ---")
        invalid_ts_payload = {
            "timestamp": "not-a-timestamp",
            "sensor_id": "716955",
            "speed": 51.71,
            "speed_lag_1": 49.71,
            "speed_lag_2": 56.29,
            "speed_lag_3": 46.86,
            "rolling_mean_3": 52.76,
        }
        res = client.post("/api/predict", json=invalid_ts_payload)
        print(f"Status Code: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 422, f"Expected 422, got {res.status_code}"
        print("[PASS] Invalid timestamp format handled cleanly (422) PASSED")

        print("\n--- Test 8: GET /api/sensors/716955/propagation (Valid Sensor) ---")
        res = client.get("/api/sensors/716955/propagation")
        print(f"Status Code: {res.status_code}")
        prop_data = res.json()
        print(f"Propagation Response for 716955:")
        print(f"  Sensor Speed: {prop_data.get('sensor_speed_mph')} mph ({prop_data.get('sensor_congestion')})")
        print(f"  Neighbor Count: {prop_data.get('neighbor_count')}")
        print(f"  High: {prop_data.get('high_count')}, Med: {prop_data.get('medium_count')}, Low: {prop_data.get('low_count')}")
        print(f"  Weighted Score: {prop_data.get('weighted_congestion_score')}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert prop_data["sensor_id"] == "716955"
        assert prop_data["neighbor_count"] > 0
        assert len(prop_data["neighbors"]) == prop_data["neighbor_count"]
        # Verify neighbor schema
        first_n = prop_data["neighbors"][0]
        assert "sensor_id" in first_n
        assert "weight" in first_n
        assert "speed_mph" in first_n
        assert "congestion_level" in first_n
        assert "latitude" in first_n
        assert "longitude" in first_n
        assert 0.0 <= prop_data["weighted_congestion_score"] <= 1.0
        print("[PASS] Valid sensor propagation check PASSED")

        print("\n--- Test 9: GET /api/sensors/INVALID_SENSOR_9999/propagation (Invalid Sensor) ---")
        res = client.get("/api/sensors/INVALID_SENSOR_9999/propagation")
        print(f"Status Code: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        assert "not found" in res.json()["detail"].lower()
        print("[PASS] Invalid sensor propagation handled cleanly (404 Not Found) PASSED")

        print("\n--- Test 10: GET /api/sensors/717804/propagation (Zero Outgoing Neighbors) ---")
        res = client.get("/api/sensors/717804/propagation")
        print(f"Status Code: {res.status_code}")
        zero_prop_data = res.json()
        print(f"Zero-Neighbor Response: {zero_prop_data}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert zero_prop_data["sensor_id"] == "717804"
        assert zero_prop_data["neighbor_count"] == 0
        assert len(zero_prop_data["neighbors"]) == 0
        assert zero_prop_data["weighted_congestion_score"] == 0.0
        print("[PASS] Zero outgoing neighbors handled correctly PASSED")

        print("\n--- Test 11: GET /api/benchmark ---")
        res = client.get("/api/benchmark")
        print(f"Status Code: {res.status_code}")
        bench_data = res.json()
        print(f"Benchmark Environment: {bench_data.get('environment')}")
        print(f"Results Count: {len(bench_data.get('results', []))}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert len(bench_data["results"]) == 5
        fractions = [r["data_fraction"] for r in bench_data["results"]]
        assert fractions == ["10%", "25%", "50%", "75%", "100%"]
        print("[PASS] Scalability benchmark endpoint check PASSED")

        print("\n--- Test 12: GET /api/replay/available-range ---")
        res = client.get("/api/replay/available-range")
        print(f"Status Code: {res.status_code}")
        range_data = res.json()
        print(f"Total Snapshots: {range_data.get('total_snapshots')}")
        print(f"Available Dates: {range_data.get('available_dates')}")
        assert res.status_code == 200
        assert range_data["total_snapshots"] > 0
        assert len(range_data["available_dates"]) > 0
        test_date = range_data["available_dates"][0]
        test_timestamps = range_data["timestamps_by_date"][test_date]
        assert len(test_timestamps) > 0
        sample_ts = test_timestamps[0]
        print(f"Sample test timestamp: {sample_ts}")
        print("[PASS] Replay available range check PASSED")

        print("\n--- Test 13: GET /api/replay/snapshot (Valid Timestamp) ---")
        res = client.get(f"/api/replay/snapshot?timestamp={sample_ts}")
        print(f"Status Code: {res.status_code}")
        snap_data = res.json()
        print(f"Total Sensors in Snapshot: {snap_data.get('total_sensors')}")
        assert res.status_code == 200
        assert snap_data["total_sensors"] >= 200
        first_sensor = snap_data["sensors"][0]
        assert "speed" in first_sensor
        assert "predicted_speed_15min" in first_sensor
        assert "congestion_level" in first_sensor
        print("[PASS] Replay snapshot check PASSED")

        print("\n--- Test 14: GET /api/replay/snapshot (Invalid Timestamp) ---")
        res = client.get("/api/replay/snapshot?timestamp=1999-01-01 00:00:00")
        print(f"Status Code: {res.status_code}")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()
        print("[PASS] Invalid replay snapshot handled cleanly (404) PASSED")

        print("\n--- Test 15: GET /api/replay/summary ---")
        res = client.get(f"/api/replay/summary?timestamp={sample_ts}")
        print(f"Status Code: {res.status_code}")
        sum_data = res.json()
        print(f"Summary: {sum_data}")
        assert res.status_code == 200
        assert "average_speed" in sum_data
        assert "low_count" in sum_data
        assert "medium_count" in sum_data
        assert "high_count" in sum_data
        print("[PASS] Replay summary check PASSED")

        print("\n--- Test 16: POST /api/replay/predict ---")
        res = client.post("/api/replay/predict", json={"timestamp": sample_ts})
        print(f"Status Code: {res.status_code}")
        replay_pred_data = res.json()
        assert res.status_code == 200
        assert len(replay_pred_data["predictions"]) >= 200
        print(f"Sample prediction: {replay_pred_data['predictions'][0]}")
        print("[PASS] Replay predict check PASSED")

        print("\n--- Test 17: POST /api/scenario/analyze (Valid Request) ---")
        scenario_payload = {
            "sensor_id": "716955",
            "timestamp": "2012-06-09 17:30:00",
            "speed": 32.0,
            "speed_lag_1": 35.0,
            "speed_lag_2": 38.0,
            "speed_lag_3": 41.0,
            "rolling_mean_3": 35.0,
        }
        res = client.post("/api/scenario/analyze", json=scenario_payload)
        print(f"Status Code: {res.status_code}")
        scen_data = res.json()
        print(f"Scenario Result: {json.dumps(scen_data, indent=2)}")
        assert res.status_code == 200
        assert scen_data["sensor_id"] == "716955"
        assert scen_data["current_speed_mph"] == 32.0
        assert "predicted_speed_15min_mph" in scen_data
        assert scen_data["current_congestion_level"] in ["LOW", "MEDIUM", "HIGH"]
        assert scen_data["predicted_congestion_level"] in ["LOW", "MEDIUM", "HIGH"]
        assert scen_data["connected_sensors_count"] > 0
        assert "weighted_congestion_indicator" in scen_data
        assert "disclaimer" in scen_data
        print("[PASS] Valid scenario analyze check PASSED")

        print("\n--- Test 18: POST /api/scenario/analyze (Error Handling) ---")
        # 18a: Invalid sensor ID -> 404
        bad_sensor = dict(scenario_payload, sensor_id="INVALID_999999")
        res = client.post("/api/scenario/analyze", json=bad_sensor)
        assert res.status_code == 404
        # 18b: Invalid timestamp -> 400
        bad_ts = dict(scenario_payload, timestamp="invalid-time")
        res = client.post("/api/scenario/analyze", json=bad_ts)
        assert res.status_code == 400
        # 18c: Missing required fields -> 422
        res = client.post("/api/scenario/analyze", json={"sensor_id": "716955"})
        assert res.status_code == 422
        print("[PASS] Scenario error handling checks PASSED")

    print("\n" + "=" * 60)
    print("ALL API TESTS (18/18) PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()


