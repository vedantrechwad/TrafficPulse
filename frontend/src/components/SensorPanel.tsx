import React from 'react';
import type {
  SensorObservation,
  PredictionResponse,
} from '../types/traffic';
import { SelectedSensorBanner } from './SelectedSensorBanner';

interface SensorPanelProps {
  selectedSensor: SensorObservation | null;
  prediction: PredictionResponse | null;
  loadingPrediction: boolean;
  predictionError: string | null;
}

export const SensorPanel: React.FC<SensorPanelProps> = ({
  selectedSensor,
  prediction,
  loadingPrediction,
  predictionError,
}) => {
  return (
    <SelectedSensorBanner
      selectedSensor={selectedSensor}
      prediction={prediction}
      loadingPrediction={loadingPrediction}
      predictionError={predictionError}
    />
  );
};

export default SensorPanel;
