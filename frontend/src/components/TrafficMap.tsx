import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, Polyline, useMap } from 'react-leaflet';
import type { SensorObservation, PropagationResponse, ScenarioResponse } from '../types/traffic';
import { Legend } from './Legend';
import { MapPin, Network, EyeOff } from 'lucide-react';

interface TrafficMapProps {
  sensors: SensorObservation[];
  selectedSensor: SensorObservation | null;
  propagation: PropagationResponse | null;
  showNetwork: boolean;
  onToggleNetwork: () => void;
  onSelectSensor: (sensor: SensorObservation) => void;
  scenarioMode?: boolean;
  scenarioResult?: ScenarioResponse | null;
}

const getMarkerColor = (congestion: string) => {
  switch (congestion) {
    case 'LOW':
      return '#10b981'; // Green
    case 'MEDIUM':
      return '#f59e0b'; // Amber
    case 'HIGH':
      return '#ef4444'; // Red
    default:
      return '#38bdf8';
  }
};

/**
 * MapController automatically fits the Leaflet view to the bounding box of the
 * 207 real METR-LA sensor coordinates and handles layout invalidation on resize.
 */
function MapController({
  bounds,
  selectedSensorId,
  showNetwork,
}: {
  bounds: [[number, number], [number, number]] | null;
  selectedSensorId?: string;
  showNetwork?: boolean;
}) {
  const map = useMap();

  useEffect(() => {
    if (bounds) {
      map.fitBounds(bounds, { padding: [30, 30], maxZoom: 13 });
    }
    // Invalidate size to ensure clean rendering on initial load
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 150);

    return () => clearTimeout(timer);
  }, [map, bounds]);

  // Invalidate size on sensor selection or network toggling
  useEffect(() => {
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 100);
    return () => clearTimeout(timer);
  }, [map, selectedSensorId, showNetwork]);

  useEffect(() => {
    const handleResize = () => {
      map.invalidateSize();
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [map]);

  return null;
}

export const TrafficMap: React.FC<TrafficMapProps> = ({
  sensors,
  selectedSensor,
  propagation,
  showNetwork,
  onToggleNetwork,
  onSelectSensor,
  scenarioMode = false,
  scenarioResult = null,
}) => {
  // Center of Los Angeles Highway Sensor Network (fallback)
  const defaultCenter: [number, number] = [34.12, -118.30];

  // Calculate bounding box from the real 207 sensor coordinates
  const bounds = useMemo(() => {
    if (!sensors || sensors.length === 0) return null;
    const lats = sensors.map((s) => s.latitude).filter((lat) => !isNaN(lat) && lat !== 0);
    const lngs = sensors.map((s) => s.longitude).filter((lng) => !isNaN(lng) && lng !== 0);
    if (lats.length === 0 || lngs.length === 0) return null;

    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);

    return [
      [minLat - 0.015, minLng - 0.015],
      [maxLat + 0.015, maxLng + 0.015],
    ] as [[number, number], [number, number]];
  }, [sensors]);

  // Effective selected ID (prioritizes scenario result in scenario mode)
  const effectiveSelectedId = scenarioMode && scenarioResult ? scenarioResult.sensor_id : selectedSensor?.sensor_id;

  // Set of connected neighbor IDs for quick lookup
  const neighborIds = useMemo(() => {
    if (scenarioMode && scenarioResult && scenarioResult.neighbors) {
      return new Set(scenarioResult.neighbors.map((n) => n.sensor_id));
    }
    if (!showNetwork || !propagation || !propagation.neighbors) return new Set<string>();
    return new Set(propagation.neighbors.map((n) => n.sensor_id));
  }, [scenarioMode, scenarioResult, showNetwork, propagation]);

  // Active edges to render
  const activeEdges = useMemo(() => {
    if (scenarioMode && scenarioResult && scenarioResult.neighbors) {
      const originSensor = sensors.find((s) => s.sensor_id === scenarioResult.sensor_id) || selectedSensor;
      if (!originSensor) return [];
      return scenarioResult.neighbors.map((n) => ({
        key: `scen-edge-${scenarioResult.sensor_id}-${n.sensor_id}`,
        from: [originSensor.latitude, originSensor.longitude] as [number, number],
        to: [n.latitude, n.longitude] as [number, number],
        fromId: scenarioResult.sensor_id,
        toId: n.sensor_id,
        weight: n.weight,
        speed: n.speed_mph,
        congestion: n.congestion_level,
      }));
    }

    if (showNetwork && selectedSensor && propagation && propagation.neighbors) {
      return propagation.neighbors.map((n) => {
        const currentNeighbor = sensors.find((s) => s.sensor_id === n.sensor_id);
        const currentSpeed = currentNeighbor ? currentNeighbor.speed : n.speed_mph;
        const currentCongestion = currentNeighbor ? currentNeighbor.congestion_level : n.congestion_level;
        return {
          key: `prop-edge-${selectedSensor.sensor_id}-${n.sensor_id}`,
          from: [selectedSensor.latitude, selectedSensor.longitude] as [number, number],
          to: [n.latitude, n.longitude] as [number, number],
          fromId: selectedSensor.sensor_id,
          toId: n.sensor_id,
          weight: n.weight,
          speed: currentSpeed,
          congestion: currentCongestion,
        };
      });
    }

    return [];
  }, [scenarioMode, scenarioResult, showNetwork, selectedSensor, propagation, sensors]);

  return (
    <div className="map-container-card">
      <div className="card-header-bar">
        <div className="card-title">
          <MapPin size={17} color="#38bdf8" />
          <span>METR-LA Highway Sensor Network</span>
          <span className="badge-count">{sensors.length} Stations</span>
          {scenarioMode && <span className="badge-count" style={{ borderColor: '#818cf8', color: '#818cf8' }}>What-If Simulation</span>}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {!scenarioMode && selectedSensor && (
            <button
              type="button"
              onClick={onToggleNetwork}
              className={`network-toggle-btn ${showNetwork ? 'active' : ''}`}
              title="Toggle graph network connections on map"
            >
              {showNetwork ? <EyeOff size={13} /> : <Network size={13} />}
              <span>{showNetwork ? 'Clear Network' : 'Show Network'}</span>
            </button>
          )}
          <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
            Click station to inspect
          </span>
        </div>
      </div>

      <div className="map-wrapper">
        <MapContainer
          center={defaultCenter}
          zoom={11}
          minZoom={9}
          maxZoom={17}
          scrollWheelZoom={true}
          style={{ height: '100%', width: '100%', minHeight: '480px' }}
        >
          {/* Fit bounds dynamically to the 207 real sensor GPS locations */}
          <MapController
            bounds={bounds}
            selectedSensorId={effectiveSelectedId}
            showNetwork={showNetwork || (scenarioMode && scenarioResult !== null)}
          />

          {/* Standard OpenStreetMap Tile Layer */}
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={19}
          />

          {/* Draw propagation network connection polylines when active */}
          {activeEdges.map((edge) => {
            const weight = edge.weight || 0.1;
            const strokeWidth = Math.max(1.8, Math.min(4.5, weight * 4.2));

            return (
              <Polyline
                key={edge.key}
                positions={[edge.from, edge.to]}
                pathOptions={{
                  color: scenarioMode ? '#818cf8' : '#0284c7',
                  weight: strokeWidth,
                  opacity: 0.85,
                  dashArray: '5, 5',
                }}
              >
                <Popup>
                  <div className="map-popup-card">
                    <div className="map-popup-header">Network Edge</div>
                    <div>
                      <strong>Connection:</strong> #{edge.fromId} &rarr; #{edge.toId}
                    </div>
                    <div>
                      <strong>Adjacency Weight:</strong> {edge.weight.toFixed(4)}
                    </div>
                    <div>
                      <strong>Neighbor Speed:</strong> {edge.speed.toFixed(1)} mph
                    </div>
                    <div>
                      <strong>State:</strong> {edge.congestion}
                    </div>
                  </div>
                </Popup>
              </Polyline>
            );
          })}

          {/* Render All 207 Sensor Markers */}
          {sensors.map((sensor) => {
            let effectiveSpeed = sensor.speed;
            let effectiveCongestion = sensor.congestion_level;

            if (scenarioMode && scenarioResult) {
              if (sensor.sensor_id === scenarioResult.sensor_id) {
                effectiveSpeed = scenarioResult.current_speed_mph;
                effectiveCongestion = scenarioResult.current_congestion_level;
              } else {
                const matchNeighbor = scenarioResult.neighbors?.find((n) => n.sensor_id === sensor.sensor_id);
                if (matchNeighbor) {
                  effectiveSpeed = matchNeighbor.speed_mph;
                  effectiveCongestion = matchNeighbor.congestion_level;
                }
              }
            }

            const isSelected = effectiveSelectedId === sensor.sensor_id;
            const isNeighbor = neighborIds.has(sensor.sensor_id);
            const markerColor = getMarkerColor(effectiveCongestion);

            // Responsive marker styling
            let radius = 5.5;
            let fillOpacity = 0.85;
            let strokeColor = '#0f172a';
            let strokeWidth = 1.2;

            if (isSelected) {
              radius = 10.0;
              fillOpacity = 1.0;
              strokeColor = '#ffffff';
              strokeWidth = 3;
            } else if (isNeighbor) {
              radius = 7.5;
              fillOpacity = 0.95;
              strokeColor = scenarioMode ? '#818cf8' : '#0284c7';
              strokeWidth = 2.5;
            } else if ((showNetwork && selectedSensor) || (scenarioMode && scenarioResult)) {
              // Subdue unrelated sensors when network propagation mode is active
              radius = 4.5;
              fillOpacity = 0.35;
              strokeWidth = 0.8;
              strokeColor = 'rgba(15, 23, 42, 0.4)';
            }

            return (
              <CircleMarker
                key={sensor.sensor_id}
                center={[sensor.latitude, sensor.longitude]}
                radius={radius}
                pathOptions={{
                  fillColor: markerColor,
                  fillOpacity: fillOpacity,
                  color: strokeColor,
                  weight: strokeWidth,
                }}
                eventHandlers={{
                  click: () => onSelectSensor(sensor),
                }}
              >
                <Popup>
                  <div className="map-popup-card">
                    <div className="map-popup-header">
                      Station #{sensor.sensor_id}
                      {isSelected && ' (Active Target)'}
                      {isNeighbor && ' (Connected Neighbor)'}
                    </div>
                    <div style={{ margin: '4px 0' }}>
                      <strong>Speed:</strong> {effectiveSpeed.toFixed(1)} mph
                    </div>
                    <div>
                      <strong>Congestion:</strong>{' '}
                      <span style={{ color: markerColor, fontWeight: 700 }}>
                        {effectiveCongestion}
                      </span>
                    </div>
                    {isNeighbor && (
                      <div style={{ marginTop: '4px', fontSize: '0.75rem', color: '#0284c7' }}>
                        Graph Adjacent Loop
                      </div>
                    )}
                    <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '6px' }}>
                      Click to select for prediction
                    </div>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>

        <Legend />
      </div>
    </div>
  );
};

export default TrafficMap;
