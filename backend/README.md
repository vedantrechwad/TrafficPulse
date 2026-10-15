# TrafficPulse Prediction API

Lightweight FastAPI service serving real-time traffic speed forecasting (15 minutes ahead) and congestion classification across the METR-LA sensor network using a pre-trained **Apache Spark ML PipelineModel**.

---

## 1. Quickstart

### Start the Service
From the project root directory, run:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

* **Interactive Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 2. API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health status and loaded model confirmation. |
| `GET` | `/api/model-info` | Complete training history, metrics (MAE, RMSE, $R^2$), and hyperparameters. |
| `GET` | `/api/sensors` | List of all 207 active METR-LA sensor IDs (cached in memory). |
| `POST` | `/api/predict` | Forecasts traffic speed and congestion level 15 minutes ahead. |

---

## 3. Prediction Endpoint Specification

### `POST /api/predict`

#### Request Payload
```json
{
  "timestamp": "2012-06-09T02:30:00",
  "sensor_id": "716955",
  "speed": 51.71,
  "speed_lag_1": 49.71,
  "speed_lag_2": 56.29,
  "speed_lag_3": 46.86,
  "rolling_mean_3": 52.76
}
```

> **Note:** The backend automatically derives calendar and cyclical features (`hour`, `minute`, `day_of_week`, `is_weekend`) directly from the `timestamp` field.

#### Example Response
```json
{
  "sensor_id": "716955",
  "timestamp": "2012-06-09T02:30:00",
  "current_speed_mph": 51.71,
  "predicted_speed_15min_mph": 52.3,
  "speed_change_mph": 0.59,
  "congestion_level": "LOW",
  "prediction_horizon_minutes": 15
}
```

---

## 4. Congestion Thresholds

Congestion classifications are driven by `config/congestion_config.json`:

* **`LOW` (Free Flow):** Predicted Speed $\ge 50.0\text{ mph}$
* **`MEDIUM` (Moderate Delay):** $30.0 \le \text{Predicted Speed} < 50.0\text{ mph}$
* **`HIGH` (Severe Congestion / Stop & Go):** Predicted Speed $< 30.0\text{ mph}$

---

## 5. Architectural & Performance Notes

* **Single SparkSession:** A local SparkSession is initialized once during FastAPI startup (`lifespan`) and shared across requests.
* **In-Memory Model:** The `PipelineModel` (StringIndexer, OneHotEncoder, VectorAssembler, RandomForestRegressor) remains resident in memory for low-latency transformation.
* **Zero Disk Scans for Sensor Validation:** The list of 207 sensor IDs is scanned once on startup and stored in an in-memory set for $O(1)$ validation.
* **CORS Enabled:** Cross-Origin Resource Sharing is enabled for standard local frontend dev ports (`http://localhost:3000` and `http://localhost:5173`).
