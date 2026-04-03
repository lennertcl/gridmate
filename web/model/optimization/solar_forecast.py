import logging
from datetime import datetime, timedelta
from typing import List

logger = logging.getLogger(__name__)


class SolarForecastService:
    def build_pv_power_forecast(self, ha_connector, solar, time_step: int, horizon_hours: int) -> List[float]:
        sensor_id = solar.estimation_sensors.estimated_actual_production_offset_day
        if not sensor_id:
            logger.info('No PV forecast sensor configured, EMHASS will use its internal weather-based method')
            return []

        forecast = self._build_forecast_from_history(ha_connector, sensor_id, time_step, horizon_hours)
        if forecast:
            logger.info(
                'PV forecast from %s: %d values, max=%.0f W',
                sensor_id,
                len(forecast),
                max(forecast),
            )
            return forecast

        logger.info('No PV forecast from sensors, EMHASS will use its internal weather-based method')
        return []

    def _build_forecast_from_history(
        self, ha_connector, sensor_id: str, time_step: int, horizon_hours: int
    ) -> List[float]:
        now = datetime.now()
        start = now - timedelta(hours=24)

        history = ha_connector.get_history(
            [sensor_id], start, now, minimal_response=False, significant_changes_only=False
        )
        if not history or not history[0]:
            return []

        history_points = []
        for entry in history[0]:
            try:
                ts = datetime.fromisoformat(entry.get('last_changed', '').replace('Z', '+00:00'))
                if ts.tzinfo is not None:
                    ts = ts.astimezone(tz=None).replace(tzinfo=None)
                val = float(entry.get('state', 0))
                history_points.append((ts, max(0.0, val * 1000.0)))
            except (ValueError, TypeError):
                continue

        if not history_points:
            return []

        history_points.sort(key=lambda p: p[0])

        num_steps = int((horizon_hours * 60) // time_step)
        result = []
        for i in range(num_steps):
            target = now + timedelta(minutes=i * time_step)
            lookback = target - timedelta(hours=24)
            best_val = 0.0
            best_diff = float('inf')
            for ts, val in history_points:
                diff = abs((ts - lookback).total_seconds())
                if diff < best_diff:
                    best_diff = diff
                    best_val = val
            result.append(best_val)

        if all(v == 0.0 for v in result):
            return []
        return result
