import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class SolarForecastProvider(ABC):
    @abstractmethod
    def get_power_forecast_at(self, timestamp: datetime) -> Optional[float]:
        """Return forecasted power in Watts at the given timestamp, or None if outside forecast window."""

    @abstractmethod
    def get_power_forecast_between(self, start: datetime, end: datetime) -> List[Tuple[datetime, float]]:
        """Return list of (timestamp, power_w) data points at native resolution, sorted by time."""

    def get_emhass_power_forecast(self, time_step: int, horizon_hours: int) -> List[float]:
        """Produce regularly-spaced power values (W) for EMHASS pv_power_forecast.

        One value per time_step-minute interval, starting from now,
        for horizon_hours * 60 / time_step total values.
        """
        now = datetime.now()
        end = now + timedelta(hours=horizon_hours)
        num_steps = int((horizon_hours * 60) // time_step)

        data_points = self.get_power_forecast_between(now, end)
        if not data_points:
            return []

        result = []
        for i in range(num_steps):
            step_start = now + timedelta(minutes=i * time_step)
            step_end = step_start + timedelta(minutes=time_step)

            points_in_interval = [val for ts, val in data_points if step_start <= ts < step_end]

            if points_in_interval:
                result.append(sum(points_in_interval) / len(points_in_interval))
            else:
                target = step_start + timedelta(minutes=time_step / 2)
                best_val = 0.0
                best_diff = float('inf')
                for ts, val in data_points:
                    diff = abs((ts - target).total_seconds())
                    if diff < best_diff:
                        best_diff = diff
                        best_val = val
                result.append(best_val)

        if all(v == 0.0 for v in result):
            return []
        return result

    def get_energy_forecast_between(self, start: datetime, end: datetime) -> Optional[float]:
        """Return total forecasted energy in Wh over the period using trapezoidal integration."""
        data_points = self.get_power_forecast_between(start, end)
        if not data_points:
            return None

        total_wh = 0.0
        for i in range(1, len(data_points)):
            t0, p0 = data_points[i - 1]
            t1, p1 = data_points[i]
            dt_hours = (t1 - t0).total_seconds() / 3600.0
            total_wh += ((p0 + p1) / 2.0) * dt_hours

        return total_wh if total_wh > 0 else None

    @staticmethod
    def from_dict(data: dict, ha_connector) -> Optional['SolarForecastProvider']:
        """Create a provider from a config dict.

        Args:
            data: dict with 'type' and 'config' keys
            ha_connector: HA REST API connector

        Returns:
            A SolarForecastProvider instance, or None if type is empty/unknown
        """
        if not data:
            return None

        provider_type = data.get('type', '')
        config = data.get('config', {})

        if provider_type == 'forecast_solar':
            from web.model.solar.forecast_solar_provider import ForecastDotSolarProvider

            sensor_entity = config.get('sensor_entity', '')
            if not sensor_entity:
                return None
            return ForecastDotSolarProvider(ha_connector, sensor_entity)

        if provider_type == 'solcast':
            from web.model.solar.solcast_provider import SolcastProvider

            forecast_entity = config.get('forecast_entity', '')
            if not forecast_entity:
                return None
            return SolcastProvider(ha_connector, forecast_entity)

        if provider_type == 'naive':
            from web.model.solar.naive_forecast_provider import NaiveSolarForecastProvider

            production_sensor = config.get('production_sensor', '')
            if not production_sensor:
                return None
            return NaiveSolarForecastProvider(ha_connector, production_sensor)

        return None
