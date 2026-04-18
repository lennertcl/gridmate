import logging
import time
from datetime import datetime
from typing import List, Optional, Tuple

from web.model.solar.forecast_provider import SolarForecastProvider

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300


class SolcastProvider(SolarForecastProvider):
    """Solar forecast provider using the Solcast HA integration (HACS).

    Reads the detailedForecast attribute from the Solcast forecast_today and
    forecast_tomorrow sensors. Each entry has period_start (ISO8601) and
    pv_estimate (kW) at 30-minute intervals.
    """

    def __init__(self, ha_connector, forecast_entity: str):
        self.ha = ha_connector
        self.forecast_entity = forecast_entity
        self._cache = None
        self._cache_time = 0

    def _get_tomorrow_entity(self) -> str:
        return self.forecast_entity.replace('forecast_today', 'forecast_tomorrow')

    def _load_forecast_data(self) -> List[Tuple[datetime, float]]:
        now = time.time()
        if self._cache is not None and (now - self._cache_time) < CACHE_TTL_SECONDS:
            return self._cache

        result = []

        for entity_id in [self.forecast_entity, self._get_tomorrow_entity()]:
            try:
                state = self.ha.get_state(entity_id)
                if not state:
                    continue

                detailed = state.get('attributes', {}).get('detailedForecast', [])
                if not detailed:
                    detailed = state.get('attributes', {}).get('detailed_forecast', [])

                for entry in detailed:
                    try:
                        period_start = entry.get('period_start', '')
                        ts = datetime.fromisoformat(period_start.replace('Z', '+00:00'))
                        if ts.tzinfo is not None:
                            ts = ts.astimezone(tz=None).replace(tzinfo=None)
                        pv_kw = float(entry.get('pv_estimate', 0))
                        result.append((ts, max(0.0, pv_kw * 1000.0)))
                    except (ValueError, TypeError):
                        continue
            except Exception as e:
                logger.warning('Failed to load Solcast data from %s: %s', entity_id, e)

        result.sort(key=lambda p: p[0])
        self._cache = result
        self._cache_time = now
        return result

    def get_power_forecast_at(self, timestamp: datetime) -> Optional[float]:
        data_points = self._load_forecast_data()
        if not data_points:
            return None

        first_ts = data_points[0][0]
        last_ts = data_points[-1][0]
        if timestamp < first_ts or timestamp > last_ts:
            return None

        for i in range(len(data_points) - 1):
            t0, p0 = data_points[i]
            t1, p1 = data_points[i + 1]
            if t0 <= timestamp <= t1:
                if t0 == t1:
                    return p0
                fraction = (timestamp - t0).total_seconds() / (t1 - t0).total_seconds()
                return p0 + fraction * (p1 - p0)

        return data_points[-1][1]

    def get_power_forecast_between(self, start: datetime, end: datetime) -> List[Tuple[datetime, float]]:
        data_points = self._load_forecast_data()
        return [(ts, val) for ts, val in data_points if start <= ts <= end]
