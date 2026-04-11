import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from web.model.device import Device, DeviceType
from web.model.device.device_type import get_device_type_registry
from web.model.energy import EnergyContract, EnergyFeed, EnergyPeriodData
from web.model.energy.models import (
    ENERGY_SENSOR_CONSUMPTION_HIGH_TARIFF,
    ENERGY_SENSOR_CONSUMPTION_LOW_TARIFF,
    ENERGY_SENSOR_INJECTION_HIGH_TARIFF,
    ENERGY_SENSOR_INJECTION_LOW_TARIFF,
    ENERGY_SENSOR_TOTAL_CONSUMPTION,
    ENERGY_SENSOR_TOTAL_INJECTION,
    ENERGY_SENSOR_TOTAL_USAGE,
    ENERGY_SENSOR_USAGE_HIGH_TARIFF,
    ENERGY_SENSOR_USAGE_LOW_TARIFF,
    PRESELECTABLE_ENERGY_SENSORS,
)
from web.model.optimization.models import OptimizationConfig
from web.model.persistence import JsonRepository
from web.model.solar import Solar

logger = logging.getLogger(__name__)


class DataConnector:
    """
    Manages persistent storage and retrieval of all configuration data
    Uses domain models and swappable persistence layer
    """

    def __init__(self, repository_or_path: any = None):
        """
        Initialize DataConnector

        Args:
            repository_or_path: Either a Repository instance or a file path string (defaults to JsonRepository with default path)
        """
        # Handle both Repository instances and file path strings for backward compatibility
        if isinstance(repository_or_path, str):
            self.repository = JsonRepository(repository_or_path)
        elif repository_or_path is None:
            is_local_dev = os.environ.get('LOCAL_DEV', '').lower() == 'true'
            if is_local_dev:
                self.repository = JsonRepository('data/settings.json')
            else:
                self.repository = JsonRepository('/data/settings.json')
        else:
            self.repository = repository_or_path

    def _load_from_storage(self) -> Dict:
        """Load fresh data from repository, always reading from disk"""
        data = self.repository.load()
        if not data:
            data = {
                'version': '1.0',
                'devices': {},
                'energy_feed': {},
                'energy_contract': {},
                'solar': {},
                'optimization': {},
            }
        if 'device_types' in data:
            del data['device_types']
            self._save_to_storage(data)
        return data

    def _save_to_storage(self, data: Dict) -> None:
        """Save data to repository"""
        self.repository.save(data)

    def export(self) -> Dict:
        """Export all data as dictionary"""
        return self._load_from_storage().copy()

    def export_json(self) -> str:
        """Export all data as JSON string"""
        import json

        return json.dumps(self._load_from_storage(), indent=2)

    # ============================================
    # Device Operations
    # ============================================

    def get_devices(self) -> List[Device]:
        """Get all devices as domain models"""
        data = self._load_from_storage()
        devices = []
        for device_id, device_data in data.get('devices', {}).items():
            device_data['device_id'] = device_id
            devices.append(Device.from_dict(device_data))
        return devices

    def get_device(self, device_id: str) -> Optional[Device]:
        """Get a specific device by ID as domain model"""
        data = self._load_from_storage()
        device_data = data.get('devices', {}).get(device_id)
        if device_data:
            device_data['device_id'] = device_id
            return Device.from_dict(device_data)
        return None

    def add_device(self, device_id: str, device: Device) -> bool:
        """
        Add a new device

        Args:
            device_id: Unique device identifier
            device: Device domain model

        Returns:
            True if successful, False if device already exists
        """
        data = self._load_from_storage()
        if device_id in data.get('devices', {}):
            return False

        device.last_updated = datetime.now()
        if device.created_at == datetime.now():
            device.created_at = datetime.now()

        device_dict = device.to_dict()
        data['devices'][device_id] = device_dict
        self._save_to_storage(data)
        return True

    def update_device(self, device_id: str, device: Device) -> bool:
        """
        Update an existing device

        Args:
            device_id: Unique device identifier
            device: Updated Device domain model

        Returns:
            True if successful, False if device not found
        """
        data = self._load_from_storage()
        if device_id not in data.get('devices', {}):
            return False

        device.last_updated = datetime.now()
        device_dict = device.to_dict()
        del device_dict['device_id']
        data['devices'][device_id] = device_dict
        self._save_to_storage(data)
        return True

    def remove_device(self, device_id: str) -> bool:
        """
        Remove a device

        Args:
            device_id: Unique device identifier

        Returns:
            True if successful, False if device not found
        """
        data = self._load_from_storage()
        if device_id not in data.get('devices', {}):
            return False

        del data['devices'][device_id]
        self._save_to_storage(data)
        return True

    def device_exists(self, device_id: str) -> bool:
        """Check if a device exists"""
        return device_id in self._load_from_storage().get('devices', {})

    # ============================================
    # Energy Feed Operations
    # ============================================

    def get_energy_feed(self) -> EnergyFeed:
        """Get energy feed configuration as domain model"""
        data = self._load_from_storage()
        feed_data = data.get('energy_feed', {})
        return EnergyFeed.from_dict(feed_data)

    def set_energy_feed(self, feed: EnergyFeed) -> None:
        """
        Set energy feed configuration

        Args:
            feed: EnergyFeed domain model
        """
        data = self._load_from_storage()
        feed.last_updated = datetime.now()
        data['energy_feed'] = feed.to_dict()
        self._save_to_storage(data)

    def update_energy_feed(self, updates: Dict) -> None:
        """
        Update energy feed configuration (partial update)

        Args:
            updates: Dictionary of fields to update
        """
        feed = self.get_energy_feed()
        for key, value in updates.items():
            if hasattr(feed, key):
                setattr(feed, key, value)
        feed.last_updated = datetime.now()
        self.set_energy_feed(feed)

    # ============================================
    # Energy Contract Operations
    # ============================================

    def get_energy_contract(self) -> EnergyContract:
        """Get energy contract configuration as domain model"""
        data = self._load_from_storage()
        contract_data = data.get('energy_contract', {})
        return EnergyContract.from_dict(contract_data)

    def set_energy_contract(self, contract: EnergyContract) -> None:
        """
        Set energy contract configuration

        Args:
            contract: EnergyContract domain model
        """
        data = self._load_from_storage()
        contract.last_updated = datetime.now()
        data['energy_contract'] = contract.to_dict()
        self._save_to_storage(data)

    def update_energy_contract(self, updates: Dict) -> None:
        """
        Update energy contract configuration (partial update)

        Args:
            updates: Dictionary of fields to update
        """
        contract = self.get_energy_contract()
        for key, value in updates.items():
            if hasattr(contract, key):
                setattr(contract, key, value)
        contract.last_updated = datetime.now()
        self.set_energy_contract(contract)

    # ============================================
    # Solar Operations
    # ============================================

    def get_solar(self) -> Solar:
        """Get solar panels configuration as domain model"""
        data = self._load_from_storage()
        solar_data = data.get('solar', {})
        return Solar.from_dict(solar_data)

    def set_solar(self, solar: Solar) -> None:
        """
        Set solar panels configuration

        Args:
            solar: Solar domain model
        """
        data = self._load_from_storage()
        solar.last_updated = datetime.now()
        data['solar'] = solar.to_dict()
        self._save_to_storage(data)

    def update_solar(self, updates: Dict) -> None:
        """
        Update solar configuration (partial update)

        Args:
            updates: Dictionary of fields to update
        """
        solar = self.get_solar()
        for key, value in updates.items():
            if hasattr(solar, key):
                setattr(solar, key, value)
        solar.last_updated = datetime.now()
        self.set_solar(solar)

    def has_solar(self) -> bool:
        """Check if solar is configured"""
        solar = self.get_solar()
        return solar.is_configured

    def get_optimization_config(self) -> OptimizationConfig:
        data = self._load_from_storage()
        opt_data = data.get('optimization', {})
        return OptimizationConfig.from_dict(opt_data)

    def set_optimization_config(self, config: OptimizationConfig) -> None:
        data = self._load_from_storage()
        config.last_updated = datetime.now()
        data['optimization'] = config.to_dict()
        self._save_to_storage(data)

    def update_optimization_config(self, updates: Dict) -> None:
        config = self.get_optimization_config()
        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)
        config.last_updated = datetime.now()
        self.set_optimization_config(config)

    # ============================================
    # Bulk Operations
    # ============================================

    def clear_all(self) -> None:
        """Clear all data and reset to defaults"""
        data = {
            'version': '1.0',
            'devices': {},
            'device_types': {},
            'energy_feed': {},
            'energy_contract': {},
            'solar': {},
            'optimization': {},
            'forecaster': {},
        }
        self._save_to_storage(data)

    def get_summary(self) -> Dict:
        """Get a summary of all configuration"""
        data = self._load_from_storage()
        return {
            'version': data.get('version'),
            'devices_count': len(data.get('devices', {})),
            'has_energy_feed': bool(data.get('energy_feed')),
            'has_energy_contract': bool(data.get('energy_contract')),
            'has_solar': self.has_solar(),
            'has_optimization': bool(data.get('optimization')),
            'has_forecaster': bool(data.get('forecaster')),
            'devices': list(data.get('devices', {}).keys()),
        }


class DeviceManager:
    def __init__(self, connector: DataConnector):
        self.connector = connector

    def add_device(
        self,
        device_id: str,
        name: str,
        primary_type: str,
        secondary_types: List[str] = None,
        custom_parameters: Dict = None,
    ) -> bool:
        device = Device(
            device_id=device_id,
            name=name,
            primary_type=primary_type,
            secondary_types=secondary_types or [],
            custom_parameters=custom_parameters or {},
        )
        return self.connector.add_device(device_id, device)

    def get_devices_by_type(self, type_id: str) -> List[Device]:
        return [d for d in self.connector.get_devices() if type_id in d.get_all_type_ids()]

    def list_all_devices(self) -> List[Device]:
        return self.connector.get_devices()

    def get_device(self, device_id: str) -> Optional[Device]:
        return self.connector.get_device(device_id)

    def update_device(
        self,
        device_id: str,
        name: str,
        primary_type: str,
        secondary_types: List[str] = None,
        custom_parameters: Dict = None,
    ) -> bool:
        device = self.connector.get_device(device_id)
        if not device:
            return False
        device.name = name
        device.primary_type = primary_type
        device.secondary_types = secondary_types or []
        if custom_parameters is not None:
            device.custom_parameters = custom_parameters
        return self.connector.update_device(device_id, device)

    def remove_device(self, device_id: str) -> bool:
        return self.connector.remove_device(device_id)


class DeviceTypeManager:
    def __init__(self, connector: DataConnector):
        self.connector = connector

    def get_registry(self) -> Dict[str, DeviceType]:
        return get_device_type_registry()

    def get_type(self, type_id: str) -> Optional[DeviceType]:
        return get_device_type_registry().get(type_id)

    def get_type_choices(self) -> List[tuple]:
        registry = self.get_registry()
        return [(tid, t.name) for tid, t in sorted(registry.items(), key=lambda x: x[1].name)]

    def get_devices_using_type(self, type_id: str) -> List[Device]:
        return [d for d in self.connector.get_devices() if type_id in d.get_all_type_ids()]


class EnergyFeedManager:
    """Helper class for managing energy feed configuration"""

    def __init__(self, connector: DataConnector):
        self.connector = connector

    def get_config(self) -> EnergyFeed:
        """Get current energy feed configuration"""
        return self.connector.get_energy_feed()


class EnergyContractManager:
    """Helper class for managing energy contract configuration"""

    def __init__(self, connector: DataConnector):
        self.connector = connector

    def get_config(self) -> EnergyContract:
        """Get current energy contract configuration"""
        return self.connector.get_energy_contract()


class SolarManager:
    def __init__(self, connector: DataConnector):
        self.connector = connector

    def get_config(self) -> Solar:
        return self.connector.get_solar()

    def set_sensors(self, sensors_dict: Dict) -> None:
        from web.model.solar.models import SolarSensors

        solar = self.get_config()
        solar.sensors = SolarSensors.from_dict(sensors_dict)
        self.connector.set_solar(solar)

    def set_estimation_sensors(self, estimation_dict: Dict) -> None:
        from web.model.solar.models import SolarEstimationSensors

        solar = self.get_config()
        solar.estimation_sensors = SolarEstimationSensors.from_dict(estimation_dict)
        self.connector.set_solar(solar)

    def get_all_sensor_ids(self) -> list:
        solar = self.get_config()
        sensor_ids = []
        for val in [
            solar.sensors.actual_production,
            solar.sensors.energy_production_today,
            solar.sensors.energy_production_lifetime,
            solar.estimation_sensors.estimated_actual_production,
            solar.estimation_sensors.estimated_energy_production_remaining_today,
            solar.estimation_sensors.estimated_energy_production_today,
            solar.estimation_sensors.estimated_energy_production_hour,
            solar.estimation_sensors.estimated_actual_production_offset_day,
            solar.estimation_sensors.estimated_energy_production_offset_day,
            solar.estimation_sensors.estimated_energy_production_offset_hour,
        ]:
            if val:
                sensor_ids.append(val)
        return sensor_ids


class EnergyDataService:
    """Service for fetching energy period data from Home Assistant.

    Uses the HA WebSocket statistics API (recorder/statistics_during_period)
    with 5-minute pre-aggregated statistics, then merges into 15-minute intervals
    (hh:00, hh:15, hh:30, hh:45). This is much faster than fetching raw history
    because HA's recorder pre-computes these statistics.
    """

    def __init__(self, connector: DataConnector, ha_connector=None):
        """
        Initialize the energy data service.

        Args:
            connector: DataConnector instance for accessing energy feed config
            ha_connector: Optional HAConnector instance (creates one if not provided)
        """
        self.connector = connector
        if ha_connector is None:
            from web.model.data.ha_connector import HAConnector

            ha_connector = HAConnector()
        self.ha_connector = ha_connector

    def get_energy_feed(self) -> EnergyFeed:
        """Get the configured energy feed sensors."""
        return self.connector.get_energy_feed()

    def get_period_data(
        self, year: int, month: Optional[int] = None, contract: Optional['EnergyContract'] = None
    ) -> EnergyPeriodData:
        """
        Fetch energy period data from Home Assistant using 15-minute interval statistics.

        For a month: fetches data from the 1st of the month to the 1st of next month
        For a year: fetches data from Jan 1 to Jan 1 of next year

        Args:
            year: The year to fetch data for
            month: The month (1-12) or None for yearly data
            contract: Optional EnergyContract to include variable price sensors

        Returns:
            EnergyPeriodData populated with real values from Home Assistant
        """
        if month:
            start_time = datetime(year, month, 1)
            if month == 12:
                end_time = datetime(year + 1, 1, 1)
            else:
                end_time = datetime(year, month + 1, 1)
        else:
            start_time = datetime(year, 1, 1)
            end_time = datetime(year + 1, 1, 1)

        return self.get_period_data_for_range(start_time, end_time, contract)

    def get_period_data_for_range(
        self, start_time: datetime, end_time: datetime, contract: Optional['EnergyContract'] = None
    ) -> EnergyPeriodData:
        """
        Fetch energy period data from Home Assistant for a specific date range.

        Uses HA's 5-minute statistics and aggregates to 15-minute intervals.

        Args:
            start_time: Start of the period
            end_time: End of the period
            contract: Optional EnergyContract to include variable price sensors

        Returns:
            EnergyPeriodData populated with real values from Home Assistant
        """
        energy_feed = self.get_energy_feed()

        # Collect all sensor IDs we need statistics for
        all_sensor_ids = self._collect_sensor_ids(energy_feed, contract)

        if not all_sensor_ids:
            logger.warning('No sensors configured, returning empty data')
            return EnergyPeriodData()

        # Fetch 5-minute statistics via WebSocket and aggregate to 15-min
        sensor_stats_15min = self._fetch_15min_statistics(all_sensor_ids, start_time, end_time)
        self._extend_preselectable_sensor_history(sensor_stats_15min, energy_feed)

        # Get start and end states for meter readings
        cons_high_start, cons_high_end = self._get_start_end_state(
            sensor_stats_15min.get(energy_feed.total_consumption_high_tariff, [])
        )
        cons_low_start, cons_low_end = self._get_start_end_state(
            sensor_stats_15min.get(energy_feed.total_consumption_low_tariff, [])
        )
        inj_high_start, inj_high_end = self._get_start_end_state(
            sensor_stats_15min.get(energy_feed.total_injection_high_tariff, [])
        )
        inj_low_start, inj_low_end = self._get_start_end_state(
            sensor_stats_15min.get(energy_feed.total_injection_low_tariff, [])
        )

        # Calculate consumption/injection as difference between end and start
        # This represents the actual energy consumed/injected during the period
        consumption_high = cons_high_end - cons_high_start
        consumption_low = cons_low_end - cons_low_start
        injection_high = inj_high_end - inj_high_start
        injection_low = inj_low_end - inj_low_start

        # Warn if differences are negative (potential meter reset or data quality issue)
        if consumption_high < 0:
            logger.warning(
                f'Negative consumption_high difference: {consumption_high:.2f} kWh (start={cons_high_start:.2f}, end={cons_high_end:.2f})'
            )
            consumption_high = 0.0
        if consumption_low < 0:
            logger.warning(
                f'Negative consumption_low difference: {consumption_low:.2f} kWh (start={cons_low_start:.2f}, end={cons_low_end:.2f})'
            )
            consumption_low = 0.0
        if injection_high < 0:
            logger.warning(
                f'Negative injection_high difference: {injection_high:.2f} kWh (start={inj_high_start:.2f}, end={inj_high_end:.2f})'
            )
            injection_high = 0.0
        if injection_low < 0:
            logger.warning(
                f'Negative injection_low difference: {injection_low:.2f} kWh (start={inj_low_start:.2f}, end={inj_low_end:.2f})'
            )
            injection_low = 0.0

        max_power, max_power_timestamp = self._max_mean_with_timestamp(
            sensor_stats_15min.get(energy_feed.actual_consumption, [])
        )

        # Compute monthly peak powers for capacity tariff (TTM average)
        monthly_peak_powers = self._compute_monthly_peak_powers(
            sensor_stats_15min.get(energy_feed.actual_consumption, [])
        )

        period_data = EnergyPeriodData(
            consumption_high_tariff=consumption_high,
            consumption_low_tariff=consumption_low,
            injection_high_tariff=injection_high,
            injection_low_tariff=injection_low,
            total_consumption=consumption_high + consumption_low,
            total_injection=injection_high + injection_low,
            consumption_high_start=cons_high_start,
            consumption_high_end=cons_high_end,
            consumption_low_start=cons_low_start,
            consumption_low_end=cons_low_end,
            injection_high_start=inj_high_start,
            injection_high_end=inj_high_end,
            injection_low_start=inj_low_start,
            injection_low_end=inj_low_end,
            max_power_kw=max_power,
            max_power_timestamp=max_power_timestamp,
            monthly_peak_powers=monthly_peak_powers,
            sensor_history=sensor_stats_15min,
        )

        self._extend_custom_contract_sensor_history(period_data, contract, start_time, end_time)

        logger.info(
            f'Fetched 15-min statistics for {start_time.date()} to {end_time.date()}: '
            f'consumption={period_data.get_total_consumption():.2f} kWh, '
            f'injection={period_data.get_total_injection():.2f} kWh, '
            f'max_power={period_data.max_power_kw:.2f} kW'
        )

        return period_data

    def _collect_sensor_ids(self, energy_feed: EnergyFeed, contract: Optional['EnergyContract'] = None) -> List[str]:
        from web.model.energy.models import FixedComponent, VariableComponent

        sensors = set()

        for sensor_id in [
            energy_feed.total_consumption_high_tariff,
            energy_feed.total_consumption_low_tariff,
            energy_feed.total_injection_high_tariff,
            energy_feed.total_injection_low_tariff,
            energy_feed.actual_consumption,
            energy_feed.actual_injection,
            energy_feed.actual_usage,
            energy_feed.total_usage_high_tariff,
            energy_feed.total_usage_low_tariff,
        ]:
            if sensor_id:
                sensors.add(sensor_id)

        if contract and contract.components:
            for component in contract.components:
                if isinstance(component, VariableComponent):
                    if component.variable_price_sensor:
                        sensors.add(component.variable_price_sensor)
                    energy_sensor = component.energy_sensor or ENERGY_SENSOR_TOTAL_CONSUMPTION
                    if energy_sensor and energy_sensor not in PRESELECTABLE_ENERGY_SENSORS:
                        sensors.add(energy_sensor)
                if isinstance(component, FixedComponent):
                    energy_sensor = component.energy_sensor or ENERGY_SENSOR_TOTAL_CONSUMPTION
                    if energy_sensor and energy_sensor not in PRESELECTABLE_ENERGY_SENSORS:
                        sensors.add(energy_sensor)

        return list(sensors)

    SHORT_TERM_RETENTION_DAYS = 10

    def _fetch_15min_statistics(
        self, sensor_ids: List[str], start_time: datetime, end_time: datetime
    ) -> Dict[str, List[Dict]]:
        """
        Fetch statistics from HA and aggregate into 15-minute intervals.

        Uses a hybrid strategy to handle HA's short-term statistics retention
        (default 10 days): 5-minute statistics for recent data, hourly long-term
        statistics for older data. This ensures complete coverage for any date range.

        Returns data at exactly hh:00, hh:15, hh:30, hh:45 boundaries for the
        5-minute portion. Hourly entries pass through as single-entry buckets.
        """
        stat_types = ['mean', 'change', 'max', 'state']
        now = datetime.now()
        retention_boundary = (now - timedelta(days=self.SHORT_TERM_RETENTION_DAYS)).replace(
            minute=0, second=0, microsecond=0
        )

        raw_stats = self._fetch_hybrid_statistics(sensor_ids, start_time, end_time, retention_boundary, stat_types)

        if not raw_stats:
            logger.warning('No statistics returned from Home Assistant')
            return {}

        result = {}
        for sensor_id, entries in raw_stats.items():
            result[sensor_id] = self._aggregate_to_15min(entries)

        return result

    def _fetch_hybrid_statistics(
        self,
        sensor_ids: List[str],
        start_time: datetime,
        end_time: datetime,
        retention_boundary: datetime,
        stat_types: List[str],
    ) -> Dict[str, List[Dict]]:
        """
        Fetch statistics using hourly long-term data for the portion before
        the retention boundary and 5-minute short-term data for the portion after.
        """
        if start_time >= retention_boundary:
            return (
                self.ha_connector.get_statistics(
                    statistic_ids=sensor_ids,
                    start_time=start_time,
                    end_time=end_time,
                    period='5minute',
                    types=stat_types,
                )
                or {}
            )

        if end_time <= retention_boundary:
            return (
                self.ha_connector.get_statistics(
                    statistic_ids=sensor_ids,
                    start_time=start_time,
                    end_time=end_time,
                    period='hour',
                    types=stat_types,
                )
                or {}
            )

        hourly_stats = (
            self.ha_connector.get_statistics(
                statistic_ids=sensor_ids,
                start_time=start_time,
                end_time=retention_boundary,
                period='hour',
                types=stat_types,
            )
            or {}
        )

        fivemin_stats = (
            self.ha_connector.get_statistics(
                statistic_ids=sensor_ids,
                start_time=retention_boundary,
                end_time=end_time,
                period='5minute',
                types=stat_types,
            )
            or {}
        )

        all_sensor_ids = set(list(hourly_stats.keys()) + list(fivemin_stats.keys()))
        merged: Dict[str, List[Dict]] = {}
        for sensor_id in all_sensor_ids:
            merged[sensor_id] = hourly_stats.get(sensor_id, []) + fivemin_stats.get(sensor_id, [])
        return merged

    def _extend_preselectable_sensor_history(
        self,
        sensor_stats_15min: Dict[str, List[Dict]],
        energy_feed: EnergyFeed,
    ) -> None:
        preselected_sensor_map = {
            ENERGY_SENSOR_CONSUMPTION_HIGH_TARIFF: energy_feed.total_consumption_high_tariff,
            ENERGY_SENSOR_CONSUMPTION_LOW_TARIFF: energy_feed.total_consumption_low_tariff,
            ENERGY_SENSOR_INJECTION_HIGH_TARIFF: energy_feed.total_injection_high_tariff,
            ENERGY_SENSOR_INJECTION_LOW_TARIFF: energy_feed.total_injection_low_tariff,
        }

        for preset_key, sensor_id in preselected_sensor_map.items():
            if sensor_id:
                sensor_stats_15min[preset_key] = sensor_stats_15min.get(sensor_id, [])
            elif preset_key not in sensor_stats_15min:
                sensor_stats_15min[preset_key] = []

        if ENERGY_SENSOR_TOTAL_CONSUMPTION not in sensor_stats_15min:
            sensor_stats_15min[ENERGY_SENSOR_TOTAL_CONSUMPTION] = self._combine_sensor_histories(
                sensor_stats_15min.get(ENERGY_SENSOR_CONSUMPTION_HIGH_TARIFF, []),
                sensor_stats_15min.get(ENERGY_SENSOR_CONSUMPTION_LOW_TARIFF, []),
            )

        if ENERGY_SENSOR_TOTAL_INJECTION not in sensor_stats_15min:
            sensor_stats_15min[ENERGY_SENSOR_TOTAL_INJECTION] = self._combine_sensor_histories(
                sensor_stats_15min.get(ENERGY_SENSOR_INJECTION_HIGH_TARIFF, []),
                sensor_stats_15min.get(ENERGY_SENSOR_INJECTION_LOW_TARIFF, []),
            )

        if energy_feed.usage_mode == 'manual' and energy_feed.total_usage_high_tariff:
            usage_map = {
                ENERGY_SENSOR_USAGE_HIGH_TARIFF: energy_feed.total_usage_high_tariff,
                ENERGY_SENSOR_USAGE_LOW_TARIFF: energy_feed.total_usage_low_tariff,
            }
            for preset_key, sensor_id in usage_map.items():
                if sensor_id:
                    sensor_stats_15min[preset_key] = sensor_stats_15min.get(sensor_id, [])
                elif preset_key not in sensor_stats_15min:
                    sensor_stats_15min[preset_key] = []
            if ENERGY_SENSOR_TOTAL_USAGE not in sensor_stats_15min:
                sensor_stats_15min[ENERGY_SENSOR_TOTAL_USAGE] = self._combine_sensor_histories(
                    sensor_stats_15min.get(ENERGY_SENSOR_USAGE_HIGH_TARIFF, []),
                    sensor_stats_15min.get(ENERGY_SENSOR_USAGE_LOW_TARIFF, []),
                )
        elif energy_feed.usage_mode == 'auto':
            consumption_history = sensor_stats_15min.get(ENERGY_SENSOR_TOTAL_CONSUMPTION, [])
            injection_history = sensor_stats_15min.get(ENERGY_SENSOR_TOTAL_INJECTION, [])
            solar = self.connector.get_solar()
            production_sensor = solar.sensors.actual_production if solar.sensors.has_any else ''
            production_history = sensor_stats_15min.get(production_sensor, []) if production_sensor else []
            sensor_stats_15min[ENERGY_SENSOR_TOTAL_USAGE] = self._calculate_usage_history(
                consumption_history, production_history, injection_history
            )

    def _extend_custom_contract_sensor_history(
        self,
        period_data: EnergyPeriodData,
        contract: Optional['EnergyContract'],
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        if not contract or not contract.components:
            return

        from web.model.energy.models import FixedComponent, VariableComponent

        missing_custom_sensors = set()
        for component in contract.components:
            if not isinstance(component, (VariableComponent, FixedComponent)):
                continue

            energy_sensor = component.energy_sensor or ENERGY_SENSOR_TOTAL_CONSUMPTION
            if not energy_sensor or energy_sensor in PRESELECTABLE_ENERGY_SENSORS:
                continue

            if energy_sensor not in period_data.sensor_history:
                missing_custom_sensors.add(energy_sensor)

        if not missing_custom_sensors:
            return

        custom_stats = self._fetch_15min_statistics(list(missing_custom_sensors), start_time, end_time)
        for sensor_id, entries in custom_stats.items():
            period_data.sensor_history[sensor_id] = entries

    @staticmethod
    def _combine_sensor_histories(first_history: List[Dict], second_history: List[Dict]) -> List[Dict]:
        if not first_history or not second_history:
            return []

        first_by_start = {entry.get('start'): entry for entry in first_history if entry.get('start') is not None}
        second_by_start = {entry.get('start'): entry for entry in second_history if entry.get('start') is not None}

        result = []
        for start in sorted(set(first_by_start.keys()) & set(second_by_start.keys())):
            first_entry = first_by_start[start]
            second_entry = second_by_start[start]
            result.append(
                {
                    'start': start,
                    'end': first_entry.get('end', second_entry.get('end', start)),
                    'state': (first_entry.get('state') or 0.0) + (second_entry.get('state') or 0.0),
                    'mean': (first_entry.get('mean') or 0.0) + (second_entry.get('mean') or 0.0),
                    'max': (first_entry.get('max') or 0.0) + (second_entry.get('max') or 0.0),
                    'change': (first_entry.get('change') or 0.0) + (second_entry.get('change') or 0.0),
                }
            )

        return result

    @staticmethod
    def _calculate_usage_history(
        consumption_history: List[Dict],
        production_history: List[Dict],
        injection_history: List[Dict],
    ) -> List[Dict]:
        cons_by_start = {e.get('start'): e for e in consumption_history if e.get('start') is not None}
        prod_by_start = {e.get('start'): e for e in production_history if e.get('start') is not None}
        inj_by_start = {e.get('start'): e for e in injection_history if e.get('start') is not None}

        all_starts = sorted(set(cons_by_start.keys()) | set(prod_by_start.keys()) | set(inj_by_start.keys()))
        result = []
        for start in all_starts:
            cons = cons_by_start.get(start, {})
            prod = prod_by_start.get(start, {})
            inj = inj_by_start.get(start, {})
            usage_mean = (cons.get('mean') or 0.0) + (prod.get('mean') or 0.0) - (inj.get('mean') or 0.0)
            usage_change = (cons.get('change') or 0.0) + (prod.get('change') or 0.0) - (inj.get('change') or 0.0)
            result.append(
                {
                    'start': start,
                    'end': cons.get('end', prod.get('end', inj.get('end', start))),
                    'mean': max(usage_mean, 0.0),
                    'change': max(usage_change, 0.0),
                    'max': max(usage_mean, 0.0),
                    'state': None,
                }
            )
        return result

    @staticmethod
    def _aggregate_to_15min(entries_5min: List[Dict]) -> List[Dict]:
        if not entries_5min:
            return []

        result = []
        bucket = []
        current_quarter_key = None

        for entry in entries_5min:
            start_ms = entry.get('start', 0)
            start_dt = datetime.fromtimestamp(start_ms / 1000.0)
            # Determine which 15-min quarter this belongs to
            quarter_key = (start_dt.year, start_dt.month, start_dt.day, start_dt.hour, start_dt.minute // 15)

            if current_quarter_key is None:
                current_quarter_key = quarter_key

            if quarter_key != current_quarter_key:
                # Flush the previous bucket
                if bucket:
                    result.append(EnergyDataService._merge_bucket(bucket))
                bucket = [entry]
                current_quarter_key = quarter_key
            else:
                bucket.append(entry)

        # Flush the last bucket
        if bucket:
            result.append(EnergyDataService._merge_bucket(bucket))

        return result

    @staticmethod
    def _merge_bucket(entries: List[Dict]) -> Dict:
        """Merge up to 3 consecutive 5-minute entries into one 15-minute entry."""
        n = len(entries)
        return {
            'start': entries[0]['start'],
            'end': entries[-1].get('end', entries[-1]['start']),
            'mean': sum(e.get('mean') or 0.0 for e in entries) / n,
            'change': sum(e.get('change') or 0.0 for e in entries),
            'max': max((e.get('max') or 0.0 for e in entries), default=0.0),
            'state': entries[0].get('state'),
        }

    @staticmethod
    def _sum_changes(entries: List[Dict]) -> float:
        """Sum the 'change' field across all 15-min entries for a total delta."""
        return sum(e.get('change') or 0.0 for e in entries)

    @staticmethod
    def _get_start_end_state(entries: List[Dict]) -> tuple:
        """Get start and end state values from entries.

        If the start state is 0, uses the first nonzero state value as start.
        This handles cases where data collection starts after the beginning of the period.

        Note: The 'state' field from HA statistics should always have a value, but we use
        'or 0.0' as defensive programming to handle None/missing values.

        Args:
            entries: List of 15-minute stat dicts with 'state' field

        Returns:
            Tuple of (start_state, end_state)
        """
        if not entries:
            return 0.0, 0.0

        # Get the end state (last entry)
        end = entries[-1].get('state') or 0.0

        # Get the start state - if first entry is 0, find first nonzero value
        start = entries[0].get('state') or 0.0
        if start == 0.0:
            # Find the first nonzero state value (skip index 0 as it's already checked)
            # Use index iteration to avoid creating a slice copy
            for i in range(1, len(entries)):
                state = entries[i].get('state') or 0.0
                if state != 0.0:  # Use != to handle both positive and negative values
                    start = state
                    break

        return float(start), float(end)

    @staticmethod
    def _max_mean_with_timestamp(entries: List[Dict]) -> tuple:
        if not entries:
            return 0.0, ''
        max_entry = max(entries, key=lambda e: e.get('mean') or 0.0)
        max_mean = max_entry.get('mean') or 0.0
        start_ms = max_entry.get('start', 0)
        if start_ms:
            ts = datetime.fromtimestamp(start_ms / 1000.0)
            timestamp_str = ts.strftime('%d %b %H:%M')
        else:
            timestamp_str = ''
        return max_mean, timestamp_str

    @staticmethod
    def _compute_monthly_peak_powers(entries: List[Dict]) -> Dict[int, float]:
        """Compute peak power (max mean) per calendar month from 15-min statistics.

        Returns a dict mapping month number (1-12) to the peak power in kW
        for that month. Months with no data are omitted.
        """
        if not entries:
            return {}

        monthly_peaks: Dict[int, float] = {}
        for entry in entries:
            start_ms = entry.get('start', 0)
            if not start_ms:
                continue
            mean_val = entry.get('mean') or 0.0
            month = datetime.fromtimestamp(start_ms / 1000.0).month
            if month not in monthly_peaks or mean_val > monthly_peaks[month]:
                monthly_peaks[month] = mean_val

        return monthly_peaks

    def is_ha_available(self) -> bool:
        """Check if Home Assistant is available."""
        return self.ha_connector.is_connected()
