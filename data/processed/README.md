# Processed Dataset & Sensor Locations

## 1. Sensor Geographic Coordinates (`sensor_locations.csv`)

* **File:** `data/processed/sensor_locations.csv`
* **Sensor Count:** Exactly **207** sensors (100% matched to `data/raw/METR-LA.h5` and `data/raw/adj_METR-LA.pkl`).
* **Source:** Official METR-LA sensor location dataset published by the USC Information Laboratory and authors of the DCRNN benchmark (Li et al., *Diffusion Convolutional Recurrent Neural Network: Data-Driven Traffic Forecasting*, ICLR 2018).
* **Reference Repository:** [liyaguang/DCRNN (data/sensor_graph/graph_sensor_locations.csv)](https://raw.githubusercontent.com/liyaguang/DCRNN/master/data/sensor_graph/graph_sensor_locations.csv).
* **Geographic Coverage:** Los Angeles County highway sensor network (Caltrans Performance Measurement System - PeMS District 7).
  * Latitude Range: `[33.9556, 34.3323]` °N
  * Longitude Range: `[-118.5298, -118.1256]` °W
* **Columns:**
  1. `sensor_id`: Caltrans PeMS Station ID (string).
  2. `latitude`: WGS84 decimal latitude.
  3. `longitude`: WGS84 decimal longitude.

## 2. Feature-Engineered Dataset (`traffic_features.parquet`)

* **File:** `data/processed/traffic_features.parquet`
* **Record Count:** **6,395,849** ML-ready records.
* **Schema:**
  - `timestamp`: Timestamp of observation (5-minute uniform intervals).
  - `sensor_id`: Traffic sensor ID.
  - `speed`: Current observed traffic speed in mph.
  - `speed_lag_1`: Speed 5 minutes prior (t-1).
  - `speed_lag_2`: Speed 10 minutes prior (t-2).
  - `speed_lag_3`: Speed 15 minutes prior (t-3).
  - `rolling_mean_3`: 3-step rolling average speed.
  - `hour`: Hour of day (0-23).
  - `minute`: Minute of hour (0-55).
  - `day_of_week`: Day of week (1=Sunday ... 7=Saturday).
  - `is_weekend`: Binary flag (1 if weekend, 0 otherwise).
  - `future_speed_15min`: Prediction target (speed 15 minutes ahead).

## 3. Historical Replay Dataset (`historical_replay_data.json`)

* **File:** `data/processed/historical_replay_data.json`
* **Generation Script:** `spark/generate_replay_data.py`
* **Purpose:** Powers responsive frontend Historical Replay mode without querying 6.4M Parquet rows or initiating Spark jobs per second during simulation.
* **Timestep Coverage:** 711 unique 5-minute historical timesteps across three representative dates:
  * `2012-06-09` (Full weekend day, 00:00 to 23:55)
  * `2012-06-27` (Full weekday, 00:00 to 23:55)
  * `2012-06-02` (Full weekend day, 00:00 to 23:55)
* **Total Observation Records:** **143,233** records across all 207 sensors.
* **Content Per Record:**
  * `timestamp`: ISO timestamp string.
  * `sensor_id`: Caltrans PeMS station ID.
  * `speed`: Real historical speed (mph) at time $T$.
  * `predicted_speed`: Genuine Spark ML Random Forest model prediction for $T + 15\text{ min}$.
  * `speed_change`: Difference ($\text{predicted} - \text{current}$).
  * `congestion`: Visual classification (`LOW`, `MEDIUM`, `HIGH`).
  * `latitude`, `longitude`: WGS84 coordinates.
* **Replay Timestep Summary Precomputation:** Each of the 711 timesteps includes pre-aggregated metrics: total sensors, low/medium/high counts, average network speed, and predicted slowdown count.

## 4. Latest Observations & Sensor History (`latest_sensor_observations.json`, `sensor_history.json`)

* **`latest_sensor_observations.json`:** 207 records representing the baseline operational state of each sensor station with real historical coordinates and lag features.
* **`sensor_history.json`:** Chronological historical telemetry arrays (past 2 hours at 5-minute intervals) for all 207 stations to feed interactive Recharts telemetry charts.

## 5. Scalability Benchmark (`scalability_benchmark.csv`)

* **File:** `data/processed/scalability_benchmark.csv`
* **Generation Script:** `spark/benchmark.py`
* **Contents:** Empirically recorded Spark runtimes across 10%, 25%, 50%, 75%, and 100% data fractions with records processed, median wall-clock time, and throughput.
