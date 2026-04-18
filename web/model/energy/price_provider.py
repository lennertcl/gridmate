import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROVIDER_TYPE_STATIC = 'static'
PROVIDER_TYPE_SENSOR = 'sensor'
PROVIDER_TYPE_NORDPOOL = 'nordpool'
PROVIDER_TYPE_ACTION = 'action'

PROVIDER_TYPES = {
    PROVIDER_TYPE_STATIC: 'Static Price',
    PROVIDER_TYPE_SENSOR: 'Sensor Price',
    PROVIDER_TYPE_NORDPOOL: 'Nord Pool',
    PROVIDER_TYPE_ACTION: 'Action Price',
}


def _align_to_15min(dt: datetime) -> datetime:
    return dt.replace(minute=(dt.minute // 15) * 15, second=0, microsecond=0)


def _generate_15min_windows(start: datetime, end: datetime) -> List[datetime]:
    windows = []
    current = _align_to_15min(start)
    aligned_end = _align_to_15min(end)
    while current <= aligned_end:
        windows.append(current)
        current += timedelta(minutes=15)
    return windows


def _dt_to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0)


@dataclass
class EnergyPriceProvider(ABC):
    name: str = ''
    provider_type: str = ''

    def get_kwh_price(self, timestamp: datetime, ha_connector: Any) -> Optional[float]:
        aligned = _align_to_15min(timestamp)
        now = _align_to_15min(datetime.now())
        if aligned <= now:
            return self._get_past_kwh_price(aligned, ha_connector)
        return self._get_future_kwh_price(aligned, ha_connector)

    def get_kwh_prices(self, start: datetime, end: datetime, ha_connector: Any) -> Dict[int, Optional[float]]:
        windows = _generate_15min_windows(start, end)
        result = {}
        for window in windows:
            price = self.get_kwh_price(window, ha_connector)
            result[_dt_to_ms(window)] = price
        return result

    @abstractmethod
    def _get_past_kwh_price(self, timestamp: datetime, ha_connector: Any) -> Optional[float]:
        raise NotImplementedError

    @abstractmethod
    def _get_future_kwh_price(self, timestamp: datetime, ha_connector: Any) -> Optional[float]:
        raise NotImplementedError

    def to_dict(self) -> Dict:
        return {
            'type': self.__class__.__name__,
            'name': self.name,
            'provider_type': self.provider_type,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'EnergyPriceProvider':
        by_class_name = {
            'StaticPriceProvider': StaticPriceProvider,
            'SensorPriceProvider': SensorPriceProvider,
            'NordpoolPriceProvider': NordpoolPriceProvider,
            'ActionPriceProvider': ActionPriceProvider,
        }
        by_provider_type = {
            PROVIDER_TYPE_STATIC: StaticPriceProvider,
            PROVIDER_TYPE_SENSOR: SensorPriceProvider,
            PROVIDER_TYPE_NORDPOOL: NordpoolPriceProvider,
            PROVIDER_TYPE_ACTION: ActionPriceProvider,
        }
        provider_cls = by_class_name.get(data.get('type', '')) or by_provider_type.get(data.get('provider_type', ''))
        if provider_cls is None:
            raise ValueError(f'Unknown price provider type: {data}')
        return provider_cls.from_dict(data)

    def __str__(self) -> str:
        label = PROVIDER_TYPES.get(self.provider_type, self.provider_type)
        return f'{self.name} ({label})'


@dataclass
class StaticPriceProvider(EnergyPriceProvider):
    price_per_kwh: float = 0.0

    def __post_init__(self) -> None:
        self.provider_type = PROVIDER_TYPE_STATIC

    def _get_past_kwh_price(self, timestamp: datetime, ha_connector: Any) -> Optional[float]:
        return self.price_per_kwh

    def _get_future_kwh_price(self, timestamp: datetime, ha_connector: Any) -> Optional[float]:
        return self.price_per_kwh

    def get_kwh_prices(self, start: datetime, end: datetime, ha_connector: Any) -> Dict[int, Optional[float]]:
        windows = _generate_15min_windows(start, end)
        return {_dt_to_ms(w): self.price_per_kwh for w in windows}

    def to_dict(self) -> Dict:
        base = super().to_dict()
        base['price_per_kwh'] = self.price_per_kwh
        return base

    @classmethod
    def from_dict(cls, data: Dict) -> 'StaticPriceProvider':
        return cls(
            name=data.get('name', ''),
            price_per_kwh=data.get('price_per_kwh', 0.0),
        )


@dataclass
class SensorPriceProvider(EnergyPriceProvider):
    price_sensor: str = ''

    def __post_init__(self) -> None:
        self.provider_type = PROVIDER_TYPE_SENSOR

    def _get_past_kwh_price(self, timestamp: datetime, ha_connector: Any) -> Optional[float]:
        end = timestamp + timedelta(minutes=15)
        stats = ha_connector.get_statistics([self.price_sensor], timestamp, end, period='5minute', types=['mean'])
        if not stats or self.price_sensor not in stats:
            return None
        entries = stats[self.price_sensor]
        if not entries:
            return None
        values = [e.get('mean') for e in entries if e.get('mean') is not None]
        if not values:
            return None
        return sum(values) / len(values)

    def _get_future_kwh_price(self, timestamp: datetime, ha_connector: Any) -> Optional[float]:
        forecast_prices = self._get_forecast_prices(ha_connector)
        hour_key = timestamp.replace(minute=0, second=0, microsecond=0)
        if hour_key in forecast_prices:
            return forecast_prices[hour_key]

        state_data = ha_connector.get_state(self.price_sensor, silent=True)
        if state_data:
            try:
                return float(state_data.get('state', 0))
            except (ValueError, TypeError):
                pass
        return None

    def get_kwh_prices(self, start: datetime, end: datetime, ha_connector: Any) -> Dict[int, Optional[float]]:
        now = _align_to_15min(datetime.now())
        windows = _generate_15min_windows(start, end)
        result: Dict[int, Optional[float]] = {}

        past_windows = [w for w in windows if w <= now]
        future_windows = [w for w in windows if w > now]

        if past_windows:
            stats = ha_connector.get_statistics(
                [self.price_sensor],
                past_windows[0],
                past_windows[-1] + timedelta(minutes=15),
                period='5minute',
                types=['mean'],
            )
            price_map = self._stats_to_15min_prices(stats)
            for w in past_windows:
                result[_dt_to_ms(w)] = price_map.get(_dt_to_ms(w))

        if future_windows:
            forecast_prices = self._get_forecast_prices(ha_connector)
            current_price = self._get_current_price(ha_connector)
            for w in future_windows:
                hour_key = w.replace(minute=0, second=0, microsecond=0)
                result[_dt_to_ms(w)] = forecast_prices.get(hour_key, current_price)

        return result

    def _get_forecast_prices(self, ha_connector: Any) -> Dict[datetime, float]:
        state_data = ha_connector.get_state(self.price_sensor, silent=True)
        if not state_data:
            return {}

        attributes = state_data.get('attributes', {})
        forecast_data = attributes.get('forecast', []) or attributes.get('forecasts', [])
        if not forecast_data:
            return {}

        prices: Dict[datetime, float] = {}
        for entry in forecast_data:
            if not isinstance(entry, dict):
                continue
            ts_str = entry.get('start_time') or entry.get('start') or entry.get('datetime')
            value = entry.get('native_value') or entry.get('value') or entry.get('price')
            if ts_str and value is not None:
                try:
                    ts = datetime.fromisoformat(str(ts_str).replace('Z', '+00:00'))
                    if ts.tzinfo is not None:
                        ts = ts.astimezone(tz=None)
                    prices[ts.replace(minute=0, second=0, microsecond=0, tzinfo=None)] = float(value)
                except (ValueError, TypeError):
                    continue
        return prices

    def _get_current_price(self, ha_connector: Any) -> Optional[float]:
        state_data = ha_connector.get_state(self.price_sensor, silent=True)
        if state_data:
            try:
                return float(state_data.get('state', 0))
            except (ValueError, TypeError):
                pass
        return None

    def _stats_to_15min_prices(self, stats: Optional[Dict]) -> Dict[int, float]:
        if not stats or self.price_sensor not in stats:
            return {}

        entries = stats[self.price_sensor]
        if not entries:
            return {}

        price_map: Dict[int, float] = {}
        bucket: List[Dict] = []
        current_quarter_key = None

        for entry in entries:
            start_ms = entry.get('start', 0)
            start_dt = _ms_to_dt(start_ms)
            quarter_key = (start_dt.year, start_dt.month, start_dt.day, start_dt.hour, start_dt.minute // 15)

            if current_quarter_key is None:
                current_quarter_key = quarter_key

            if quarter_key != current_quarter_key:
                if bucket:
                    aligned_ts = bucket[0]['start']
                    values = [e.get('mean') for e in bucket if e.get('mean') is not None]
                    if values:
                        price_map[aligned_ts] = sum(values) / len(values)
                bucket = [entry]
                current_quarter_key = quarter_key
            else:
                bucket.append(entry)

        if bucket:
            aligned_ts = bucket[0]['start']
            values = [e.get('mean') for e in bucket if e.get('mean') is not None]
            if values:
                price_map[aligned_ts] = sum(values) / len(values)

        return price_map

    def to_dict(self) -> Dict:
        base = super().to_dict()
        base['price_sensor'] = self.price_sensor
        return base

    @classmethod
    def from_dict(cls, data: Dict) -> 'SensorPriceProvider':
        return cls(
            name=data.get('name', ''),
            price_sensor=data.get('price_sensor', ''),
        )


@dataclass
class NordpoolPriceProvider(EnergyPriceProvider):
    area: str = ''
    _config_entry_id: str = field(default='', init=False, repr=False)

    def __post_init__(self) -> None:
        self.provider_type = PROVIDER_TYPE_NORDPOOL

    @property
    def current_price_sensor(self) -> str:
        return f'sensor.nord_pool_{self.area.lower()}_current_price'

    @property
    def next_price_sensor(self) -> str:
        return f'sensor.nord_pool_{self.area.lower()}_next_price'

    def _get_past_kwh_price(self, timestamp: datetime, ha_connector: Any) -> Optional[float]:
        return self._get_date_prices(timestamp.date(), ha_connector).get(timestamp)

    def _get_future_kwh_price(self, timestamp: datetime, ha_connector: Any) -> Optional[float]:
        return self._get_date_prices(timestamp.date(), ha_connector).get(timestamp)

    def get_kwh_prices(self, start: datetime, end: datetime, ha_connector: Any) -> Dict[int, Optional[float]]:
        windows = _generate_15min_windows(start, end)
        prices_by_timestamp: Dict[datetime, float] = {}
        for target_date in sorted({window.date() for window in windows}):
            prices_by_timestamp.update(self._get_date_prices(target_date, ha_connector))

        return {_dt_to_ms(window): prices_by_timestamp.get(window) for window in windows}

    def _get_date_prices(self, target_date: Any, ha_connector: Any) -> Dict[datetime, float]:
        config_entry_id = self._get_config_entry_id(ha_connector)
        if not config_entry_id:
            return self._get_current_and_next_prices(ha_connector)

        command = {
            'id': 1,
            'type': 'call_service',
            'domain': 'nordpool',
            'service': 'get_prices_for_date',
            'service_data': {
                'config_entry': config_entry_id,
                'date': str(target_date),
                'areas': self.area.upper(),
            },
            'return_response': True,
        }
        response = ha_connector.websocket_command(command)
        if not response:
            return self._get_current_and_next_prices(ha_connector) if target_date == datetime.now().date() else {}

        return self._parse_date_prices_response(response)

    def _get_config_entry_id(self, ha_connector: Any) -> str:
        if self._config_entry_id:
            return self._config_entry_id

        try:
            response = ha_connector.request('GET', '/api/config/config_entries/entry', timeout=10)
        except Exception as exc:
            logger.warning(f'Failed to resolve Nord Pool config entry: {exc}')
            return ''

        if response.status_code != 200:
            logger.warning(f'Failed to resolve Nord Pool config entry: {response.status_code}')
            return ''

        try:
            entries = response.json()
        except ValueError:
            return ''

        for entry in entries:
            if entry.get('domain') == 'nordpool':
                self._config_entry_id = entry.get('entry_id', '')
                break

        return self._config_entry_id

    def _parse_date_prices_response(self, response: Dict) -> Dict[datetime, float]:
        response_data = response.get('response', response)
        area_prices = response_data.get(self.area.upper()) or response_data.get(self.area)
        if not isinstance(area_prices, list):
            return {}

        prices: Dict[datetime, float] = {}
        for entry in area_prices:
            if not isinstance(entry, dict):
                continue
            ts_str = entry.get('start') or entry.get('start_time') or entry.get('datetime')
            value = entry.get('price')
            if ts_str is None or value is None:
                continue
            try:
                ts = datetime.fromisoformat(str(ts_str).replace('Z', '+00:00'))
                if ts.tzinfo is not None:
                    ts = ts.astimezone(tz=None)
                prices[ts.replace(second=0, microsecond=0, tzinfo=None)] = float(value) / 1000.0
            except (ValueError, TypeError):
                continue

        return prices

    def _get_current_and_next_prices(self, ha_connector: Any) -> Dict[datetime, float]:
        now = _align_to_15min(datetime.now())
        prices: Dict[datetime, float] = {}

        current_state = ha_connector.get_state(self.current_price_sensor, silent=True)
        if current_state:
            try:
                prices[now] = float(current_state.get('state', 0))
            except (ValueError, TypeError):
                pass

        next_state = ha_connector.get_state(self.next_price_sensor, silent=True)
        if next_state:
            try:
                prices[now + timedelta(minutes=15)] = float(next_state.get('state', 0))
            except (ValueError, TypeError):
                pass

        return prices

    def _stats_to_15min_prices(self, stats: Optional[Dict]) -> Dict[int, float]:
        if not stats or self.current_price_sensor not in stats:
            return {}

        entries = stats[self.current_price_sensor]
        if not entries:
            return {}

        price_map: Dict[int, float] = {}
        bucket: List[Dict] = []
        current_quarter_key = None

        for entry in entries:
            start_ms = entry.get('start', 0)
            start_dt = _ms_to_dt(start_ms)
            quarter_key = (start_dt.year, start_dt.month, start_dt.day, start_dt.hour, start_dt.minute // 15)

            if current_quarter_key is None:
                current_quarter_key = quarter_key

            if quarter_key != current_quarter_key:
                if bucket:
                    aligned_ts = bucket[0]['start']
                    values = [e.get('mean') for e in bucket if e.get('mean') is not None]
                    if values:
                        price_map[aligned_ts] = sum(values) / len(values)
                bucket = [entry]
                current_quarter_key = quarter_key
            else:
                bucket.append(entry)

        if bucket:
            aligned_ts = bucket[0]['start']
            values = [e.get('mean') for e in bucket if e.get('mean') is not None]
            if values:
                price_map[aligned_ts] = sum(values) / len(values)

        return price_map

    def to_dict(self) -> Dict:
        base = super().to_dict()
        base['area'] = self.area
        return base

    @classmethod
    def from_dict(cls, data: Dict) -> 'NordpoolPriceProvider':
        return cls(
            name=data.get('name', ''),
            area=data.get('area', ''),
        )


@dataclass
class ActionPriceProvider(EnergyPriceProvider):
    action_domain: str = ''
    action_service: str = ''
    action_data: Dict = field(default_factory=dict)
    response_price_key: str = 'prices'

    def __post_init__(self) -> None:
        self.provider_type = PROVIDER_TYPE_ACTION

    def _get_past_kwh_price(self, timestamp: datetime, ha_connector: Any) -> Optional[float]:
        prices = self._call_action_for_date(timestamp.date(), ha_connector)
        hour_key = timestamp.replace(minute=0, second=0, microsecond=0)
        return prices.get(hour_key)

    def _get_future_kwh_price(self, timestamp: datetime, ha_connector: Any) -> Optional[float]:
        prices = self._call_action_for_date(timestamp.date(), ha_connector)
        hour_key = timestamp.replace(minute=0, second=0, microsecond=0)
        return prices.get(hour_key)

    def get_kwh_prices(self, start: datetime, end: datetime, ha_connector: Any) -> Dict[int, Optional[float]]:
        windows = _generate_15min_windows(start, end)
        dates_needed = sorted({w.date() for w in windows})

        all_prices: Dict[datetime, float] = {}
        for date in dates_needed:
            day_prices = self._call_action_for_date(date, ha_connector)
            all_prices.update(day_prices)

        result: Dict[int, Optional[float]] = {}
        for w in windows:
            hour_key = w.replace(minute=0, second=0, microsecond=0)
            result[_dt_to_ms(w)] = all_prices.get(hour_key)
        return result

    def _call_action_for_date(self, target_date: Any, ha_connector: Any) -> Dict[datetime, float]:
        service_data = dict(self.action_data)
        service_data['date'] = str(target_date)

        command = {
            'id': 1,
            'type': 'call_service',
            'domain': self.action_domain,
            'service': self.action_service,
            'service_data': service_data,
            'return_response': True,
        }
        response = ha_connector.websocket_command(command)
        if not response:
            logger.warning(f'Action {self.action_domain}.{self.action_service} returned no data for {target_date}')
            return {}

        return self._parse_action_response(response)

    def _parse_action_response(self, response: Dict) -> Dict[datetime, float]:
        prices: Dict[datetime, float] = {}

        response_data = response.get('response', response)
        price_list = response_data.get(self.response_price_key, [])

        if not isinstance(price_list, list):
            return prices

        for entry in price_list:
            if not isinstance(entry, dict):
                continue
            ts_str = entry.get('start') or entry.get('start_time') or entry.get('datetime')
            value = entry.get('price') or entry.get('value') or entry.get('native_value')
            if ts_str and value is not None:
                try:
                    ts = datetime.fromisoformat(str(ts_str).replace('Z', '+00:00'))
                    if ts.tzinfo is not None:
                        ts = ts.astimezone(tz=None)
                    prices[ts.replace(minute=0, second=0, microsecond=0, tzinfo=None)] = float(value)
                except (ValueError, TypeError):
                    continue

        return prices

    def to_dict(self) -> Dict:
        base = super().to_dict()
        base.update(
            {
                'action_domain': self.action_domain,
                'action_service': self.action_service,
                'action_data': self.action_data,
                'response_price_key': self.response_price_key,
            }
        )
        return base

    @classmethod
    def from_dict(cls, data: Dict) -> 'ActionPriceProvider':
        return cls(
            name=data.get('name', ''),
            action_domain=data.get('action_domain', ''),
            action_service=data.get('action_service', ''),
            action_data=data.get('action_data', {}),
            response_price_key=data.get('response_price_key', 'prices'),
        )
