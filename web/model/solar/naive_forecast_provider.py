import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from web.model.solar.forecast_provider import SolarForecastProvider

logger = logging.getLogger(__name__)


class NaiveSolarForecastProvider(SolarForecastProvider):
    """Solar forecast provider that uses yesterday's actual production as the forecast.

    Fetches historical production data from 24 hours ago and shifts it forward
    to produce a naive forecast. Requires no external service — just the actual
    production sensor from the solar inverter.
    """

    def __init__(self, ha_connector, production_sensor: str):
        self.ha = ha_connector
        self.production_sensor = production_sensor

    def get_power_forecast_at(self, timestamp: datetime) -> Optional[float]:
        yesterday = timestamp - timedelta(hours=24)
        window_start = yesterday - timedelta(minutes=5)
        window_end = yesterday + timedelta(minutes=5)

        history = self.ha.get_history(
            [self.production_sensor],
            window_start,
            window_end,
            minimal_response=False,
            significant_changes_only=False,
        )
        if not history or not history[0]:
            return None

        best_val = None
        best_diff = float('inf')
        for entry in history[0]:
            try:
                ts = self._parse_timestamp(entry.get('last_changed', ''))
                val = float(entry.get('state', 0))
                diff = abs((ts - yesterday).total_seconds())
                if diff < best_diff:
                    best_diff = diff
                    best_val = max(0.0, val * 1000.0)
            except (ValueError, TypeError):
                continue

        return best_val

    def get_power_forecast_between(self, start: datetime, end: datetime) -> List[Tuple[datetime, float]]:
        history_start = start - timedelta(hours=24)
        history_end = end - timedelta(hours=24)

        now = datetime.now()
        if history_end > now:
            history_end = now

        history = self.ha.get_history(
            [self.production_sensor],
            history_start,
            history_end,
            minimal_response=False,
            significant_changes_only=False,
        )
        if not history or not history[0]:
            return []

        result = []
        for entry in history[0]:
            try:
                ts = self._parse_timestamp(entry.get('last_changed', ''))
                val = float(entry.get('state', 0))
                forecast_ts = ts + timedelta(hours=24)
                if start <= forecast_ts <= end:
                    result.append((forecast_ts, max(0.0, val * 1000.0)))
            except (ValueError, TypeError):
                continue

        result.sort(key=lambda p: p[0])
        return result

    @staticmethod
    def _parse_timestamp(ts_str: str) -> datetime:
        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        if ts.tzinfo is not None:
            ts = ts.astimezone(tz=None).replace(tzinfo=None)
        return ts
