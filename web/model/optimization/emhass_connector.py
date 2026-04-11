import logging
import math
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

from web.model.data.ha_connector import HAConnector
from web.model.optimization.connector import OptimizerConnector
from web.model.optimization.models import (
    DeferrableLoadConfig,
    DeviceSchedule,
    OptimizationConfig,
    OptimizationResult,
    ScheduleEntry,
    TimeseriesPoint,
)

logger = logging.getLogger(__name__)

LOCAL_DEV_EMHASS_URL = 'http://homeassistant.local:5000'
_DEFAULT_URLS = {'', 'http://localhost:5000', LOCAL_DEV_EMHASS_URL}


def detect_emhass_addon_url() -> str:
    supervisor_token = os.environ.get('SUPERVISOR_TOKEN')
    if not supervisor_token:
        return LOCAL_DEV_EMHASS_URL

    try:
        headers = {'Authorization': f'Bearer {supervisor_token}'}
        resp = requests.get(
            'http://supervisor/addons',
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        for addon in resp.json().get('data', {}).get('addons', []):
            slug = addon.get('slug', '')
            if 'emhass' in slug.lower():
                hostname = _resolve_addon_hostname(slug, headers)
                resolved = f'http://{hostname}:5000'
                logger.info('Auto-detected EMHASS addon URL: %s', resolved)
                return resolved
    except Exception as e:
        logger.warning('Could not auto-detect EMHASS addon: %s', e)

    return LOCAL_DEV_EMHASS_URL


def _resolve_addon_hostname(slug: str, headers: dict) -> str:
    try:
        resp = requests.get(
            f'http://supervisor/addons/{slug}/info',
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        hostname = resp.json().get('data', {}).get('hostname', '')
        if hostname:
            return hostname
    except Exception as e:
        logger.debug('Could not fetch addon info for %s: %s', slug, e)
    return slug.replace('_', '-')


def resolve_emhass_url(configured_url: str) -> str:
    is_local_dev = os.environ.get('LOCAL_DEV', '').lower() == 'true'
    if configured_url not in _DEFAULT_URLS:
        return configured_url
    if is_local_dev:
        return LOCAL_DEV_EMHASS_URL
    return detect_emhass_addon_url()


class EmhassConnector(OptimizerConnector):
    def __init__(self, emhass_url: str, ha_connector: HAConnector, data_connector=None):
        self.emhass_url = emhass_url.rstrip('/')
        self.ha = ha_connector
        self.data_connector = data_connector

    def _kw_to_w(self, kw: float) -> float:
        return kw * 1000.0

    def _w_to_kw(self, w: float) -> float:
        return w / 1000.0

    def is_available(self) -> bool:
        try:
            response = requests.get(f'{self.emhass_url}/get-config', timeout=5)
            return response.ok
        except requests.RequestException:
            return False

    def get_emhass_config(self) -> Optional[Dict]:
        try:
            response = requests.get(f'{self.emhass_url}/get-config', timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f'Failed to fetch EMHASS config: {e}')
            return None

    def set_emhass_config(self, config_dict: Dict) -> bool:
        logger.debug('Setting EMHASS config: %s', config_dict)
        try:
            response = requests.post(
                f'{self.emhass_url}/set-config',
                json=config_dict,
                timeout=30,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.error(f'Failed to set EMHASS config: {e}')
            return False

    def run_dayahead_optimization(self, config: OptimizationConfig) -> OptimizationResult:
        emhass_config = self.get_emhass_config() or {}
        time_step = emhass_config.get('optimization_time_step', 30)
        horizon_hours = 24

        runtime_params = self._build_runtime_params(config, 'dayahead', time_step, horizon_hours)
        logger.debug('Day-ahead runtime params: %s', runtime_params)
        try:
            response = requests.post(
                f'{self.emhass_url}/action/dayahead-optim',
                json=runtime_params,
                timeout=120,
            )
            logger.debug('Day-ahead raw response [%s]: %s', response.status_code, response.text)
            response.raise_for_status()
            self._publish_results()
            return self._read_result_entities(emhass_config, config, 'dayahead')
        except requests.RequestException as e:
            logger.error(f'Day-ahead optimization failed: {e}')
            raise

    def run_mpc_optimization(self, config: OptimizationConfig) -> OptimizationResult:
        emhass_config = self.get_emhass_config() or {}
        time_step = emhass_config.get('optimization_time_step', 30)
        prediction_horizon = emhass_config.get('mpc_prediction_horizon', 10)
        horizon_hours = (prediction_horizon * time_step) / 60

        runtime_params = self._build_runtime_params(config, 'mpc', time_step, horizon_hours)
        logger.debug('MPC runtime params: %s', runtime_params)
        try:
            response = requests.post(
                f'{self.emhass_url}/action/naive-mpc-optim',
                json=runtime_params,
                timeout=120,
            )
            logger.debug('MPC raw response [%s]: %s', response.status_code, response.text)
            response.raise_for_status()
            self._publish_results()
            return self._read_result_entities(emhass_config, config, 'mpc')
        except requests.RequestException as e:
            logger.error(f'MPC optimization failed: {e}')
            raise

    def get_latest_result(self) -> Optional[OptimizationResult]:
        return None

    def _get_data_connector(self):
        if self.data_connector:
            return self.data_connector
        from web.model.data.data_connector import DataConnector

        return DataConnector()

    def _build_runtime_params(
        self, config: OptimizationConfig, optimization_type: str, time_step: int, horizon_hours: float
    ) -> Dict:
        from web.model.optimization.cost_forecast import CostForecastService
        from web.model.optimization.solar_forecast import SolarForecastService

        cost_service = CostForecastService()
        solar_service = SolarForecastService()
        data_connector = self._get_data_connector()

        params = {}

        deferrable_loads = config.deferrable_loads if hasattr(config, 'deferrable_loads') else []
        num_loads = len(deferrable_loads)

        if num_loads > 0:
            num_steps = int((horizon_hours * 60) // time_step)
            params['number_of_deferrable_loads'] = num_loads
            params['nominal_power_of_deferrable_loads'] = [load.nominal_power_w for load in deferrable_loads]
            params['operating_hours_of_each_deferrable_load'] = [
                load.operating_duration_hours for load in deferrable_loads
            ]
            params['treat_deferrable_load_as_semi_cont'] = [load.is_constant_power for load in deferrable_loads]
            params['set_deferrable_load_single_constant'] = [load.is_continuous_operation for load in deferrable_loads]
            params['set_deferrable_startup_penalty'] = [load.startup_penalty for load in deferrable_loads]
            params['minimum_power_of_deferrable_loads'] = [0.0] * num_loads

            now = datetime.now()
            start_indices = []
            end_indices = []
            for load in deferrable_loads:
                s, e = self._compute_load_time_window(load, now, time_step, num_steps)
                if e > 0:
                    needed_steps = math.ceil(load.operating_duration_hours * 60 / time_step)
                    available_steps = e - s
                    if available_steps < needed_steps:
                        logger.warning(
                            'Load %s: window too small (%d steps available, %d needed). Relaxing to unconstrained.',
                            load.device_id,
                            available_steps,
                            needed_steps,
                        )
                        s, e = 0, 0
                start_indices.append(s)
                end_indices.append(e)
            params['start_timesteps_of_each_deferrable_load'] = start_indices
            params['end_timesteps_of_each_deferrable_load'] = end_indices

            if optimization_type == 'mpc':
                params['def_current_state'] = [False] * num_loads

            logger.debug(
                'Deferrable loads (%d): names=%s, nominal_power=%s, '
                'duration=%s, semi_cont=%s, single_constant=%s, '
                'start_steps=%s, end_steps=%s',
                num_loads,
                [load.device_id for load in deferrable_loads],
                params['nominal_power_of_deferrable_loads'],
                params['operating_hours_of_each_deferrable_load'],
                params['treat_deferrable_load_as_semi_cont'],
                params['set_deferrable_load_single_constant'],
                params['start_timesteps_of_each_deferrable_load'],
                params['end_timesteps_of_each_deferrable_load'],
            )

        load_cost = cost_service.build_load_cost_forecast(self.ha, time_step, int(horizon_hours))
        if load_cost:
            params['load_cost_forecast'] = load_cost
            logger.debug('Load cost forecast: %d values', len(load_cost))

        prod_price = cost_service.build_prod_price_forecast(self.ha, time_step, int(horizon_hours))
        if prod_price:
            params['prod_price_forecast'] = prod_price
            logger.debug('Prod price forecast: %d values', len(prod_price))

        load_power_forecast = config.load_power_config.build_forecast(time_step, int(horizon_hours))
        if load_power_forecast:
            params['load_power_forecast'] = load_power_forecast
            logger.debug('Load power forecast: %d values', len(load_power_forecast))

        solar = data_connector.get_solar()
        if solar.is_configured:
            pv_forecast = solar_service.build_pv_power_forecast(self.ha, solar, time_step, int(horizon_hours))
            if pv_forecast:
                params['pv_power_forecast'] = pv_forecast
                logger.info(
                    'PV power forecast: %d values, first=%.1f W, max=%.1f W',
                    len(pv_forecast),
                    pv_forecast[0] if pv_forecast else 0,
                    max(pv_forecast) if pv_forecast else 0,
                )
            else:
                logger.info('No PV forecast from sensors, EMHASS will use its internal weather-based method')
        else:
            logger.debug('Solar not configured, skipping PV forecast')

        battery_device = self._find_home_battery_device(data_connector)

        if battery_device:
            bp = battery_device.custom_parameters
            capacity_kwh = float(bp.get('capacity_kwh', 0))
            max_charge_kw = float(bp.get('max_charge_power', 0))
            max_discharge_kw = float(bp.get('max_discharge_power', 0))

            if capacity_kwh > 0:
                params['battery_nominal_energy_capacity'] = self._kw_to_w(capacity_kwh)
            if max_charge_kw > 0:
                params['battery_charge_power_max'] = self._kw_to_w(max_charge_kw)
            if max_discharge_kw > 0:
                params['battery_discharge_power_max'] = self._kw_to_w(max_discharge_kw)

            params['battery_charge_efficiency'] = float(bp.get('charge_efficiency', 0.95))
            params['battery_discharge_efficiency'] = float(bp.get('discharge_efficiency', 0.95))
            params['battery_minimum_state_of_charge'] = int(bp.get('min_charge_level', 20)) / 100.0
            params['battery_maximum_state_of_charge'] = int(bp.get('max_charge_level', 80)) / 100.0
            params['battery_target_state_of_charge'] = int(bp.get('target_soc', 80)) / 100.0

            current_soc = self._get_current_battery_soc(battery_device)
            if current_soc is not None:
                params['soc_init'] = current_soc

            logger.debug(
                'Battery params: capacity=%sWh, charge_max=%sW, discharge_max=%sW, soc_init=%s, soc_min=%s, soc_max=%s',
                params.get('battery_nominal_energy_capacity'),
                params.get('battery_charge_power_max'),
                params.get('battery_discharge_power_max'),
                params.get('soc_init'),
                params.get('battery_minimum_state_of_charge'),
                params.get('battery_maximum_state_of_charge'),
            )

        params['maximum_power_from_grid'] = config.max_grid_import_w
        params['maximum_power_to_grid'] = config.max_grid_export_w

        return params

    def _find_home_battery_device(self, data_connector):
        devices = data_connector.get_devices()
        for device in devices:
            if 'home_battery' in device.get_all_type_ids():
                capacity = float(device.custom_parameters.get('capacity_kwh', 0))
                opt_enabled = device.custom_parameters.get('opt_enabled', False)
                if capacity > 0 and opt_enabled:
                    return device
        return None

    def _get_current_battery_soc(self, battery_device) -> Optional[float]:
        soc_sensor = battery_device.custom_parameters.get('battery_level_sensor', '')
        if not soc_sensor:
            return None
        state = self.ha.get_state(soc_sensor)
        if state:
            try:
                return float(state.get('state', 0)) / 100.0
            except (ValueError, TypeError):
                pass
        return None

    def _publish_results(self):
        try:
            response = requests.post(
                f'{self.emhass_url}/action/publish-data',
                json={},
                timeout=60,
            )
            if response.ok:
                logger.debug('EMHASS results published to HA')
            else:
                logger.debug('EMHASS publish-data returned %s: %s', response.status_code, response.text[:200])
        except requests.RequestException as e:
            logger.debug('Could not publish EMHASS results: %s', e)

    def _compute_load_time_window(self, load, opt_start: datetime, time_step_min: int, horizon_steps: int):
        if load.earliest_start_time and load.latest_end_time:
            s_hour, s_min = map(int, load.earliest_start_time.split(':'))
            e_hour, e_min = map(int, load.latest_end_time.split(':'))
            start_total = s_hour * 60 + s_min
            end_total = e_hour * 60 + e_min
            span = (end_total - start_total) % 1440
            if span >= 1380:
                return 0, 0

        start_index = self._time_to_timestep_index(load.earliest_start_time, opt_start, time_step_min, horizon_steps)
        end_index = self._time_to_timestep_index(
            load.latest_end_time, opt_start, time_step_min, horizon_steps, is_end=True
        )

        if end_index > 0 and end_index <= start_index and load.latest_end_time:
            hour, minute = map(int, load.latest_end_time.split(':'))
            target = opt_start.replace(hour=hour, minute=minute, second=0, microsecond=0)
            target += timedelta(days=1)
            delta_minutes = (target - opt_start).total_seconds() / 60
            end_index = int(delta_minutes / time_step_min)
            if end_index >= horizon_steps:
                end_index = 0
            end_index = max(0, end_index)

        return start_index, end_index

    def _time_to_timestep_index(
        self, time_str: str, opt_start: datetime, time_step_min: int, horizon_steps: int, is_end: bool = False
    ) -> int:
        if not time_str:
            return horizon_steps if is_end else 0

        hour, minute = map(int, time_str.split(':'))
        target = opt_start.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if target < opt_start:
            if is_end:
                target += timedelta(days=1)
            else:
                return 0

        delta_minutes = (target - opt_start).total_seconds() / 60
        index = int(delta_minutes / time_step_min)

        return max(0, min(index, horizon_steps))

    def _read_result_entities(
        self, emhass_config: Dict, config: OptimizationConfig, optimization_type: str
    ) -> OptimizationResult:
        prefix = emhass_config.get('entity_prefix', '')
        time_step = emhass_config.get('optimization_time_step', 30)
        data_connector = self._get_data_connector()
        battery_device = self._find_home_battery_device(data_connector)

        entity_map = {
            'pv': f'sensor.{prefix}p_pv_forecast' if prefix else 'sensor.p_pv_forecast',
            'load': f'sensor.{prefix}p_load_forecast' if prefix else 'sensor.p_load_forecast',
            'grid': f'sensor.{prefix}p_grid_forecast' if prefix else 'sensor.p_grid_forecast',
            'total_cost': f'sensor.{prefix}total_cost_profit_value' if prefix else 'sensor.total_cost_profit_value',
        }

        if battery_device:
            entity_map['battery_power'] = f'sensor.{prefix}p_batt_forecast' if prefix else 'sensor.p_batt_forecast'
            entity_map['battery_soc'] = f'sensor.{prefix}soc_batt_forecast' if prefix else 'sensor.soc_batt_forecast'

        deferrable_loads = config.deferrable_loads if hasattr(config, 'deferrable_loads') else []
        for i in range(len(deferrable_loads)):
            entity_name = f'sensor.{prefix}p_deferrable{i}' if prefix else f'sensor.p_deferrable{i}'
            entity_map[f'deferrable_{i}'] = entity_name

        all_entity_ids = list(entity_map.values())
        states = self.ha.get_states(all_entity_ids, silent=True)

        result = OptimizationResult(
            timestamp=datetime.now(),
            optimization_type=optimization_type,
            time_step_minutes=time_step,
        )

        result.pv_forecast = self._parse_forecast_entity(states.get(entity_map['pv']), to_kw=True)
        result.load_forecast = self._parse_forecast_entity(states.get(entity_map['load']), to_kw=True)
        result.grid_forecast = self._parse_forecast_entity(states.get(entity_map['grid']), to_kw=True)

        if battery_device:
            result.battery_power_forecast = self._parse_forecast_entity(
                states.get(entity_map['battery_power']),
                to_kw=True,
                fallback_attr='battery_scheduled_power',
            )
            result.battery_soc_forecast = self._parse_forecast_entity(
                states.get(entity_map['battery_soc']),
                to_kw=False,
                fallback_attr='battery_scheduled_soc',
            )

        total_cost_state = states.get(entity_map['total_cost'])
        if total_cost_state and total_cost_state.get('state'):
            try:
                result.total_cost_eur = float(total_cost_state['state'])
            except (ValueError, TypeError):
                pass

        for i, load_config in enumerate(deferrable_loads):
            entity_key = f'deferrable_{i}'
            entity_id = entity_map.get(entity_key)
            if not entity_id:
                continue

            forecast_points = self._parse_forecast_entity(states.get(entity_id), to_kw=False)
            schedule = self._build_device_schedule(load_config, forecast_points, time_step)
            result.device_schedules[load_config.device_id] = schedule

            forecast_points_kw = self._parse_forecast_entity(states.get(entity_id), to_kw=True)
            result.device_power_forecasts[load_config.device_id] = forecast_points_kw

        self._compute_summary(result)
        return result

    def _parse_forecast_entity(
        self, state_data: Optional[Dict], to_kw: bool = False, fallback_attr: str = None
    ) -> List[TimeseriesPoint]:
        if not state_data:
            return []

        attributes = state_data.get('attributes', {})

        forecast_keys = ['forecasts', 'deferrables_schedule']
        if fallback_attr:
            forecast_keys.append(fallback_attr)

        for key in forecast_keys:
            data = attributes.get(key)
            if not data:
                continue
            if isinstance(data, list):
                result = self._parse_forecast_list_of_dicts(data, to_kw)
                if result:
                    return result
            elif isinstance(data, dict):
                result = self._parse_forecast_dict(data, to_kw)
                if result:
                    return result

        return []

    def _parse_forecast_list_of_dicts(self, forecasts: List[Dict], to_kw: bool) -> List[TimeseriesPoint]:
        points = []
        for entry in forecasts:
            ts_str = entry.get('date')
            if not ts_str:
                continue
            value_key = [k for k in entry if k != 'date']
            if not value_key:
                continue
            try:
                ts = datetime.fromisoformat(str(ts_str))
                ts = ts.replace(tzinfo=None)
                val = float(entry[value_key[0]])
                if to_kw:
                    val = self._w_to_kw(val)
                points.append(TimeseriesPoint(timestamp=ts, value=val))
            except (ValueError, TypeError):
                continue
        return points

    def _parse_forecast_dict(self, forecasts: Dict, to_kw: bool) -> List[TimeseriesPoint]:
        points = []
        for ts_str, value in sorted(forecasts.items()):
            try:
                ts = datetime.fromisoformat(str(ts_str))
                ts = ts.replace(tzinfo=None)
                val = float(value)
                if to_kw:
                    val = self._w_to_kw(val)
                points.append(TimeseriesPoint(timestamp=ts, value=val))
            except (ValueError, TypeError):
                continue
        return points

    def _build_device_schedule(
        self, load_config: DeferrableLoadConfig, forecast_points: List[TimeseriesPoint], time_step_minutes: int
    ) -> DeviceSchedule:
        schedule = DeviceSchedule(
            device_id=load_config.device_id,
            device_name=load_config.device_id,
        )

        if not forecast_points:
            return schedule

        entries = []
        current_start = None
        block_values = []

        for i, point in enumerate(forecast_points):
            is_active = point.value > 0
            if is_active and current_start is None:
                current_start = point.timestamp
                block_values = [point.value]
            elif is_active and current_start is not None:
                block_values.append(point.value)
            elif not is_active and current_start is not None:
                avg_power = sum(block_values) / len(block_values)
                entries.append(
                    ScheduleEntry(
                        start_time=current_start,
                        end_time=point.timestamp,
                        power_w=avg_power,
                        is_active=True,
                    )
                )
                current_start = None
                block_values = []

        if current_start is not None and forecast_points:
            last_point = forecast_points[-1]
            avg_power = sum(block_values) / len(block_values)
            entries.append(
                ScheduleEntry(
                    start_time=current_start,
                    end_time=last_point.timestamp,
                    power_w=avg_power,
                    is_active=True,
                )
            )

        schedule.schedule_entries = entries

        time_step_hours = time_step_minutes / 60.0
        total_energy = 0.0
        for point in forecast_points:
            if point.value > 0:
                total_energy += self._w_to_kw(point.value) * time_step_hours
        schedule.total_energy_kwh = total_energy

        return schedule

    def _compute_summary(self, result: OptimizationResult) -> None:
        time_step_hours = result.time_step_minutes / 60.0

        total_import = 0.0
        total_export = 0.0
        for point in result.grid_forecast:
            if point.value > 0:
                total_import += point.value * time_step_hours
            else:
                total_export += abs(point.value) * time_step_hours

        result.total_grid_import_kwh = total_import
        result.total_grid_export_kwh = total_export

        total_pv = sum(p.value * time_step_hours for p in result.pv_forecast if p.value > 0)
        result.total_pv_production_kwh = total_pv

        result.total_self_consumption_kwh = max(0, total_pv - total_export)

    def build_emhass_config_dict(self, config: OptimizationConfig) -> Dict:
        data_connector = self._get_data_connector()

        emhass_config = {}

        battery_device = self._find_home_battery_device(data_connector)
        has_battery = battery_device is not None
        emhass_config['set_use_battery'] = has_battery

        solar = data_connector.get_solar()
        has_solar = solar.is_configured
        emhass_config['set_use_pv'] = has_solar
        if has_solar and solar.sensors.actual_production:
            emhass_config['sensor_power_photovoltaics'] = solar.sensors.actual_production

        emhass_config['weather_forecast_method'] = 'open-meteo'

        emhass_config['load_cost_forecast_method'] = 'csv'
        emhass_config['production_price_forecast_method'] = 'csv'
        emhass_config['load_forecast_method'] = 'csv'

        if config.load_power_config.source_type == 'sensor' and config.load_power_config.sensor_entity:
            emhass_config['sensor_power_load_no_var_loads'] = config.load_power_config.sensor_entity

        deferrable_loads = config.deferrable_loads if hasattr(config, 'deferrable_loads') else []
        if deferrable_loads:
            emhass_config['number_of_deferrable_loads'] = len(deferrable_loads)
            emhass_config['nominal_power_of_deferrable_loads'] = [load.nominal_power_w for load in deferrable_loads]
            emhass_config['operating_hours_of_each_deferrable_load'] = [
                load.operating_duration_hours for load in deferrable_loads
            ]
            emhass_config['treat_deferrable_load_as_semi_cont'] = [load.is_constant_power for load in deferrable_loads]
            emhass_config['set_deferrable_load_single_constant'] = [
                load.is_continuous_operation for load in deferrable_loads
            ]
            emhass_config['start_timesteps_of_each_deferrable_load'] = [0 for _ in deferrable_loads]
            emhass_config['end_timesteps_of_each_deferrable_load'] = [0 for _ in deferrable_loads]
            emhass_config['set_deferrable_startup_penalty'] = [load.startup_penalty for load in deferrable_loads]
            emhass_config['set_deferrable_max_startups'] = [0 for _ in deferrable_loads]
            emhass_config['minimum_power_of_deferrable_loads'] = [0.0] * len(deferrable_loads)

        if has_battery:
            bp = battery_device.custom_parameters
            capacity_kwh = float(bp.get('capacity_kwh', 0))
            max_charge_kw = float(bp.get('max_charge_power', 0))
            max_discharge_kw = float(bp.get('max_discharge_power', 0))

            if capacity_kwh > 0:
                emhass_config['battery_nominal_energy_capacity'] = self._kw_to_w(capacity_kwh)
            if max_charge_kw > 0:
                emhass_config['battery_charge_power_max'] = self._kw_to_w(max_charge_kw)
            if max_discharge_kw > 0:
                emhass_config['battery_discharge_power_max'] = self._kw_to_w(max_discharge_kw)

            emhass_config['battery_charge_efficiency'] = float(bp.get('charge_efficiency', 0.95))
            emhass_config['battery_discharge_efficiency'] = float(bp.get('discharge_efficiency', 0.95))
            emhass_config['battery_minimum_state_of_charge'] = int(bp.get('min_charge_level', 20)) / 100.0
            emhass_config['battery_maximum_state_of_charge'] = int(bp.get('max_charge_level', 80)) / 100.0
            emhass_config['battery_target_state_of_charge'] = int(bp.get('target_soc', 80)) / 100.0

        emhass_config['maximum_power_from_grid'] = config.max_grid_import_w
        emhass_config['maximum_power_to_grid'] = config.max_grid_export_w

        return emhass_config
