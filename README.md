# TrafficPulse: Scalable Traffic Prediction & Congestion Analysis

**TrafficPulse** is an interactive big data engineering and machine learning system for traffic speed forecasting, historical simulation, and network congestion propagation analysis across the **Los Angeles County highway network** (METR-LA benchmark).

---

## 1. Project Overview

TrafficPulse bridges distributed big data processing (Apache Spark), machine learning regression (Spark ML Random Forest), and real-time geospatial visualization (FastAPI + React/TypeScript + Leaflet) into a unified traffic intelligence platform. The application offers two distinct operating modes:
* **Historical Replay Mode:** Step or animate through 5-minute historical METR-LA timesteps across 207 real highway loop detectors, showing real-time ML 15-minute forecasts, congestion classifications, and dynamic network propagation.
* **What-If Scenario Mode:** Interactively inject custom hypothetical traffic conditions (speed, lag features, date, time) for any sensor station to observe model predictions and downstream network association changes without fabricating live traffic.

---

## 2. Problem Statement

Urban highway networks experience rapid, non-linear phase transitions between free-flow and stop-and-go congestion. Traditional reactive traffic monitoring informs operators only after gridlock has already occurred. Developing scalable computational systems capable of:
1. Ingesting millions of sensor telemetry readings efficiently,
2. Forecasting upcoming speed drops 15 minutes in advance, and
3. Mapping road-network connectivity and downstream vulnerability,
is critical for intelligent transportation systems (ITS) and proactive traffic management.

---

## 3. Why Traffic Prediction Matters

Short-term traffic speed forecasting (10–30 minutes horizon) provides actionable lead time for:
* **Congestion Mitigation:** Adjusting ramp metering rates and variable speed limit (VSL) signs before highway capacity breaks down.
* **Incident Response:** Alerting emergency dispatchers to anomalous speed decelerations before secondary collisions occur.
* **Dynamic Route Guidance:** Routing logistics fleets away from developing bottleneck corridors.
* **Emissions Reduction:** Minimizing vehicle idle time, stop-and-go cycles, and urban emissions by smoothing freeway flow.

---

## 4. Dataset Overview

* **Dataset:** METR-LA Benchmark (Los Angeles County Highway Network, Caltrans PeMS District 7).
* **Collection Window:** March 1, 2012 to June 27, 2012 (~4 months).
* **Sensor Count:** Exactly 207 highway loop detectors.
* **Sampling Rate:** Uniform 5-minute intervals.
* **Total Readings:** 34,272 timesteps $\times$ 207 sensors = **7,094,304 data points**.
* **Sensor Dropouts:** 575,302 readings with speed $= 0$ representing temporary telemetry dropouts (retained and imputed during windowing, filtered during supervised model training).
* **Coordinates:** Real WGS84 GPS coordinates sourced from the USC InfoLab / DCRNN benchmark dataset covering freeways I-5, I-10, I-105, I-110, I-405, SR-60, SR-91, and US-101.
* **Road Network Topology:** $207 \times 207$ directed, weighted adjacency matrix (`adj_METR-LA.pkl`) with 1,515 physical off-diagonal road connections derived from road-network travel distances.

---

## 5. Apache Spark Data Preprocessing Pipeline

The raw data (`METR-LA.h5`) is stored in a wide matrix ($34,272 \times 207$). Processing this at scale with Apache Spark requires:
1. **Wide-to-Long Transformation:** Converting sensor columns into a long schema: `(timestamp, sensor_id, speed)`.
2. **Distributed Window Partitioning:** Partitioning by `sensor_id` and ordering by `timestamp` using PySpark Window specifications.
3. **Leakage-Free Feature Derivation:** Computing temporal lags and rolling metrics strictly from prior observations ($t-1, t-2, t-3$).
4. **Target Alignment:** Looking forward exactly 3 steps (15 minutes) for `future_speed_15min`.
5. **Columnar Parquet Storage:** Saving **6,395,849 ML-ready records** partitioned in Snappy Parquet format (`data/processed/traffic_features.parquet`).

Pipeline script: `spark/preprocess.py`

---

## 6. Feature Engineering

Each training observation incorporates 10 features capturing temporal trends and station specificity:

| Feature Name | Type | Description |
| :--- | :--- | :--- |
| `speed` | Double | Current observed traffic speed (mph) at time $T$ |
| `speed_lag_1` | Double | Speed 5 minutes prior ($T - 5\text{ min}$) |
| `speed_lag_2` | Double | Speed 10 minutes prior ($T - 10\text{ min}$) |
| `speed_lag_3` | Double | Speed 15 minutes prior ($T - 15\text{ min}$) |
| `rolling_mean_3` | Double | Mean speed over past 15 minutes: $\frac{1}{3} \sum_{i=1}^3 \text{speed}_{t-i}$ |
| `hour` | Integer | Hour of the day ($0 - 23$) |
| `minute` | Integer | Minute of the hour ($0 - 55$) |
| `day_of_week` | Integer | Day of week ($1 = \text{Sunday}, \dots, 7 = \text{Saturday}$) |
| `is_weekend` | Integer | Binary indicator ($1$ if Saturday/Sunday, $0$ otherwise) |
| `sensor_id` | String / Categorical | Caltrans station identifier indexed via `StringIndexer` |

Prediction target: `future_speed_15min` (continuous speed in mph at $T + 15\text{ min}$).

---

## 7. Machine Learning Model

* **Architecture:** `org.apache.spark.ml.regression.RandomForestRegressor`
* **Pipeline:** `StringIndexer` (sensor_id) $\to$ `VectorAssembler` (10 feature columns) $\to$ `RandomForestRegressor`.
* **Hyperparameters:**
  * `numTrees`: 20
  * `maxDepth`: 6
  * `maxBins`: 256 (supports all 207 categorical sensor IDs)
  * `seed`: 42
* **Split Strategy:** Deterministic chronological 80/20 train/test split (no future data leakage into training).
* **Evaluation Metrics:**
  * **Test $R^2$:** **0.8046** (model explains >80% of speed variance 15 minutes ahead)
  * **Test MAE:** **3.250 mph**
  * **Test RMSE:** **5.459 mph**
* **Model Artifacts:** Serialized Spark ML `PipelineModel` stored at `models/traffic_speed_model/`.

Training script: `spark/train.py`

---

## 8. 15-Minute Speed Prediction

Predictions represent the expected average traffic velocity (mph) 15 minutes into the future for a specific highway segment. The 15-minute horizon is chosen because:
1. It matches 3 consecutive 5-minute sampling intervals.
2. It provides sufficient lead time for traffic management interventions.
3. It retains high predictive fidelity ($R^2 \approx 0.805$) compared to longer horizons where stochastic incident variance increases.

---

## 9. Congestion Classification Thresholds

Project visualization and operational alerting use three standardized levels configured in `config/congestion_config.json`:

| Level | Speed Threshold | UI Color | Classification |
| :--- | :--- | :--- | :--- |
| **`LOW`** | $\ge 50.0\text{ mph}$ | `#10B981` (Emerald) | Free-flow conditions, normal speeds |
| **`MEDIUM`** | $30.0 \le \text{speed} < 50.0\text{ mph}$ | `#F59E0B` (Amber) | Moderate slowdown, developing congestion |
| **`HIGH`** | $< 30.0\text{ mph}$ | `#EF4444` (Rose) | Severe congestion, stop-and-go traffic |

---

## 10. Road Network Adjacency & Propagation Analysis

TrafficPulse models the physical interconnectivity of Los Angeles freeways using the METR-LA adjacency graph (`adj_METR-LA.pkl`):
* **Nodes:** 207 highway sensors with real WGS84 GPS coordinates.
* **Edges:** 1,515 directed off-diagonal freeway connections.
* **Weights:** Gaussian radial basis distance function along physical road network corridors ($W_{ij} \in (0, 1]$).
* **Self-Loops:** Excluded during propagation computation ($j \ne i$).

### Weighted Network Congestion Indicator
To evaluate the congestion state of physically connected downstream segments, TrafficPulse calculates an analytical index:

$$\text{Weighted Congestion Indicator} = \frac{\sum_{i=1}^{K} (W_i \times S_i)}{\sum_{i=1}^{K} W_i}$$

Where:
* $W_i$ is the physical road network adjacency weight of neighbor $i$.
* $S_i$ is the discrete congestion score for neighbor $i$:
  * **`LOW`** $= 0.0$
  * **`MEDIUM`** $= 0.5$
  * **`HIGH`** $= 1.0$

> [!IMPORTANT]
> **Academic Integrity Notice:** The adjacency graph represents physical road-network connectivity and downstream sensor association. It does **NOT** prove causality. The Weighted Congestion Indicator is an analytical metric, **NOT** a probability, risk percentage, or proof of causal propagation.

---

## 11. Historical Replay Mode

The **Historical Replay** mode enables continuous or stepped temporal navigation through real METR-LA historical traffic conditions:
* **Real Data:** Built on 711 genuine 5-minute timesteps (143,233 observations) across three representative dates (`2012-06-09`, `2012-06-27`, `2012-06-02`).
* **Playback Controls:** Date selector, Prev Step, Play / Pause, Next Step, and Playback Speeds (`1x`, `2x`, `5x`, `10x`).
* **Timeline Slider:** Draggable scrubber displaying current timestamp and total duration.
* **Dynamic Updates:** On each tick, all 207 map markers, congestion categories, KPI summary counts (Low, Medium, High, Avg Speed, Slowdown Count), station panels, and connected neighbors update in sync.
* **Zero Fabrication:** Speeds and predictions are derived strictly from genuine historical readings and the Spark ML model.

---

## 12. What-If Scenario Mode

The **What-If Scenario** mode enables operators to test hypothetical traffic conditions on any sensor station:
* **Interactive Inputs:** Choose any of the 207 sensors, set current speed, lags ($t-1, t-2, t-3$), date, and time.
* **Scenario Presets:** Quick-fill presets for realistic experiments (*Developing Slowdown*, *Bottleneck Congestion*, *Free Flow*).
* **Live Model Inference:** Dispatches parameters to `POST /api/scenario/analyze`, executing real-time Spark ML feature assembly and regression.
* **Scenario Map Visuals:** Selected sensor is prominently highlighted on the Leaflet map with gold pulse effects; connected neighbors are highlighted with cyan circles and connection polylines whose stroke widths reflect road network adjacency weights.
* **Before / After Comparison:** Card directly contrasting current vs. predicted speeds, delta, and congestion transitions.

---

## 13. System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   React + TypeScript Frontend                          │
│   ┌───────────────────────────┬────────────────────────────────────┐   │
│   │   Historical Replay Mode  │       What-If Scenario Mode        │   │
│   │   • Playback Timeline     │       • Interactive Parameter Form │   │
│   │   • Step / Speed Controls │       • Live Scenario Execution    │   │
│   │   • Replay KPI Counters   │       • Before/After Comparison    │   │
│   └─────────────┬─────────────┴──────────────────┬─────────────────┘   │
│                 │                                │                     │
│                 ▼                                ▼                     │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │          Interactive Leaflet Highway Map (207 Sensors)         │   │
│   │          • Real LA Coordinates • Adjacency Graph Polylines     │   │
│   └─────────────────────────────┬──────────────────────────────────┘   │
└─────────────────────────────────┼──────────────────────────────────────┘
                                  │ HTTP REST (JSON)
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend Service                          │
│   • Lifespan Replay Data & Adjacency Graph Cache                       │
│   • Endpoints: /api/replay/*, /api/scenario/analyze, /api/predict      │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │ PySpark VectorAssembler & PipelineModel
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    Spark ML Random Forest Regressor                    │
│   • 20 Trees, Depth 6, MaxBins 256                                     │
│   • 15-Minute Future Speed Prediction (R² = 0.805, MAE = 3.25 mph)     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 14. API Reference

The backend runs on FastAPI with automatic interactive documentation at `http://127.0.0.1:8000/docs`.

### Existing Core Endpoints
* `GET /api/health`: Health status, model load status, sensor count.
* `GET /api/model-info`: Random Forest hyperparameters, features, and test metrics.
* `GET /api/sensors`: List of all 207 sensors with coordinates and status.
* `GET /api/sensor-observations`: Latest observations across all sensors with congestion classifications.
* `GET /api/sensors/{id}/history`: Chronological 2-hour speed history for telemetry charts.
* `GET /api/sensors/{id}/propagation`: Adjacency network neighbors and weighted congestion score.
* `POST /api/predict`: Single-station 15-minute speed prediction.
* `GET /api/benchmark`: Scalability benchmark results across 5 data fractions.

### New Replay Endpoints
* `GET /api/replay/available-range`: Returns available dates, timestamps, total steps, and interval (5 min).
* `GET /api/replay/snapshot?timestamp=...`: Full 207-sensor snapshot with current speeds, predictions, and classifications.
* `GET /api/replay/summary?timestamp=...`: High/Medium/Low counts, average speed, and predicted slowdown count.
* `POST /api/replay/predict`: Model predictions for a provided timestamp or observation array.

### New Scenario Endpoint
* `POST /api/scenario/analyze`: Evaluates user-specified speed, lags, and timestamp for a sensor; returns live Spark ML prediction, delta, congestion transition, connected neighbors, and weighted congestion indicator.

---

## 15. Frontend Dashboard Components

Built with Vite, React 19, TypeScript, Leaflet, and Recharts:
* **`Header.tsx`:** Mode switching tabs (`Historical Replay` vs `What-If Scenario`) and live API connectivity indicator.
* **`ReplayControls.tsx`:** Comprehensive playback toolbar with date picker, Prev/Play/Pause/Next buttons, speed multipliers (`1x`, `2x`, `5x`, `10x`), timeline slider, and live snapshot counters.
* **`WhatIfScenarioPanel.tsx`:** Interactive scenario configuration form, quick presets, Traffic Forecast card, Before/After comparison card, and Network Analysis summary.
* **`TrafficMap.tsx`:** Hero component with Leaflet tile layer, 207 colored sensor markers, popup details, selection handlers, and scenario network polylines scaled by adjacency weight.
* **`SummaryCards.tsx`:** Real-time KPI banner syncing with active replay snapshot or global dataset stats.
* **`SensorPanel.tsx`:** Detailed telemetry inspection for selected highway stations.
* **`PredictionCard.tsx`:** Dedicated 15-minute forecast display with trend indicators.
* **`SpeedChart.tsx`:** Historical speed telemetry series with 15-minute prediction horizon.
* **`ScalabilityChart.tsx`:** Interactive dual-axis chart visualizing Spark empirical runtime vs. records processed.
* **`ModelStats.tsx` & `PipelineScale.tsx`:** System specification and big data pipeline metrics.

---

## 16. PySpark Big Data Scalability Benchmark

Empirical benchmark executed on 6,395,849 processed records (`spark/benchmark.py`) in Spark local mode using deterministic chronological subsets and median runtime across 3 runs:

| Data Fraction | Records Processed | Measured Median Time | Empirical Throughput |
| :---: | :---: | :---: | :---: |
| **10%** | 635,138 | **0.719 s** | 883,363 rec/s |
| **25%** | 1,602,058 | **0.736 s** | 2,176,709 rec/s |
| **50%** | 3,211,344 | **0.826 s** | 3,887,825 rec/s |
| **75%** | 4,805,979 | **0.889 s** | 5,406,050 rec/s |
| **100%** | 6,395,849 | **0.940 s** | 6,804,094 rec/s |

### Key Benchmark Insights
1. **Monotonic Scalability:** Execution time scales gracefully as data volume increases by an order of magnitude.
2. **Sub-linear Scaling:** Throughput increases from 883k to 6.80M records/sec as fixed JVM and scheduling overheads are amortized over larger datasets.
3. **Statistical Validity:** Warm-up runs eliminate JIT skew, and deterministic chronological slicing guarantees reproducible subsets.

---

## 17. Project Limitations & Academic Disclaimers

1. **Historical METR-LA Data:** All observations originate from the 2012 Caltrans PeMS METR-LA archive. The system performs historical simulation and replay, **not** live traffic surveillance.
2. **Associative, Not Causal:** Network connections and propagation scores reflect physical road-network connectivity and downstream sensor association. They do **not** establish causal proof or directional traffic wave mechanics.
3. **Local Benchmark Disclosure:** Scalability tests were performed in Spark local mode (`local[*]`) on a single multi-core workstation. Distributed cluster deployment on YARN or Kubernetes would incur additional network shuffling and executor serialization overheads.
4. **Research Prototype:** TrafficPulse is an academic engineering demonstration and research prototype, not a production municipal traffic-control or safety-critical dispatch system.

---

## 18. Setup Instructions

### Prerequisites
* **Python:** 3.10+ (tested on Python 3.13)
* **Node.js:** v18+ and npm
* **Java:** OpenJDK 17 or 21 (required for PySpark / Apache Spark)
* **Hadoop Winutils:** Configured in `hadoop/bin/` (included for Windows execution)

### Installation
```bash
# 1. Clone the repository
git clone <repo-url>
cd TrafficPulse

# 2. Set up Python virtual environment
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install Frontend dependencies
cd frontend
npm install
cd ..
```

---

## 18.1 Quick 1-Click Run (Windows)

To start the entire application (Backend + Frontend + Browser) at once without typing multiple terminal commands:
```bat
run.bat
```
This launcher:
1. Configures `HADOOP_HOME` and system paths for PySpark on Windows.
2. Starts the **FastAPI Backend** (`http://127.0.0.1:8000`) in its own console.
3. Starts the **Vite React Frontend** (`http://127.0.0.1:5173`) in its own console.
4. Automatically opens the dashboard in your default browser.

To stop both servers at once:
```bat
stop.bat
```

---

## 18.2 Running with Docker (Recommended)

TrafficPulse is fully containerized. You can run it either via **Docker Compose** (recommended multi-container setup) or as a **Single All-in-One Container**.

### Option A: Docker Compose (Frontend + Backend)

Spins up the FastAPI PySpark backend on port 8000 and the Nginx frontend on port 5173 with automatic health checks:

```bash
# Build and start services in the background
docker compose up -d --build

# View container logs
docker compose logs -f

# Stop all services
docker compose down
```

* **Frontend Dashboard:** [http://localhost:5173](http://localhost:5173)
* **Backend API & Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Health Check:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

### Option B: Single All-in-One Docker Container

Builds the entire application (React SPA + FastAPI + Spark ML) into a single self-contained image:

```bash
# Build the image (don't forget the trailing dot!)
docker build -t trafficpulse .

# Run the container
docker run -d -p 8000:8000 --name trafficpulse-app trafficpulse

# Stop the container
docker stop trafficpulse-app && docker rm trafficpulse-app
```

* **Full Application Dashboard:** [http://localhost:8000](http://localhost:8000)
* **API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 19. How to Run Backend Manually

From the project root:
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
* **API Root:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 20. How to Run Frontend

In a separate terminal, navigate to `frontend/`:
```bash
cd frontend
npm run dev
```
* **Dashboard:** [http://127.0.0.1:5173](http://127.0.0.1:5173)

To test the production build:
```bash
cd frontend
npm run build
npm run preview
```

To run the automated backend test suite (18 comprehensive tests):
```bash
pytest backend/test_api.py -v
```
