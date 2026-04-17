import logging
from typing import Dict, List, Optional, Tuple

from web.model.optimization.models import (
    BatteryOptimizationConfig,
    DeferrableLoadConfig,
    DeviceDayEntry,
    OptimizationConfig,
    OptimizationResult,
)
from web.model.optimization.result_store import OptimizationResultStore

logger = logging.getLogger(__name__)


class OptimizationManager:
    def __init__(self, data_connector):
        self.connector = data_connector
        self.result_store = OptimizationResultStore()

    def get_config(self) -> OptimizationConfig:
        return self.connector.get_optimization_config()

    def save_config(self, config: OptimizationConfig) -> None:
        self.connector.set_optimization_config(config)

    def get_deferrable_loads(self) -> List[DeferrableLoadConfig]:
        devices = self.connector.get_devices()
        loads = []
        for device in devices:
            if 'deferrable_load' not in device.get_all_type_ids():
                continue
            loads.append(DeferrableLoadConfig.from_device(device))

        loads.sort(key=lambda l: l.priority)
        return loads

    def get_enabled_deferrable_loads(self) -> List[DeferrableLoadConfig]:
        loads = self.get_deferrable_loads()
        return [l for l in loads if l.enabled]

    def get_effective_deferrable_loads(
        self, config: OptimizationConfig
    ) -> Tuple[List[DeferrableLoadConfig], Dict[int, Tuple[str, int]]]:
        base_loads = self.get_deferrable_loads()
        schedule = config.weekly_schedule
        overrides = {o.device_id: o for o in config.next_run_overrides}
        today_entries = {e.device_id: e for e in schedule.get_today()}

        expanded_loads = []
        index_mapping = {}

        for load in base_loads:
            if not load.enabled:
                continue

            override = overrides.get(load.device_id)
            day_entry = today_entries.get(load.device_id)

            if override is not None:
                effective = override
            elif day_entry is not None:
                effective = day_entry
            else:
                effective = DeviceDayEntry(device_id=load.device_id, num_cycles=1, hours_between_runs=0.0)

            if effective.num_cycles <= 0:
                continue

            effective_load = DeferrableLoadConfig(
                device_id=load.device_id,
                enabled=True,
                nominal_power_w=load.nominal_power_w,
                operating_duration_hours=load.operating_duration_hours,
                is_constant_power=load.is_constant_power,
                is_continuous_operation=load.is_continuous_operation,
                earliest_start_time=effective.earliest_start_time or load.earliest_start_time,
                latest_end_time=effective.latest_end_time or load.latest_end_time,
                startup_penalty=load.startup_penalty,
                priority=load.priority,
            )

            num_cycles = max(1, effective.num_cycles)
            gap_hours = effective.hours_between_runs

            if num_cycles == 1 or gap_hours <= 0:
                idx = len(expanded_loads)
                expanded_loads.append(effective_load)
                index_mapping[idx] = (load.device_id, 0)
                continue

            sub_loads = self._expand_multi_run(effective_load, num_cycles, gap_hours)
            for run_num, sub_load in enumerate(sub_loads):
                idx = len(expanded_loads)
                expanded_loads.append(sub_load)
                index_mapping[idx] = (load.device_id, run_num)

        return expanded_loads, index_mapping

    def _expand_multi_run(
        self, load: DeferrableLoadConfig, num_cycles: int, gap_hours: float
    ) -> List[DeferrableLoadConfig]:
        if not load.earliest_start_time or not load.latest_end_time:
            return [load]

        s_hour, s_min = map(int, load.earliest_start_time.split(':'))
        e_hour, e_min = map(int, load.latest_end_time.split(':'))
        total_start_minutes = s_hour * 60 + s_min
        total_end_minutes = e_hour * 60 + e_min

        if total_end_minutes <= total_start_minutes:
            total_end_minutes += 1440

        total_minutes = total_end_minutes - total_start_minutes
        total_hours = total_minutes / 60.0
        gap_total = (num_cycles - 1) * gap_hours
        window_size = (total_hours - gap_total) / num_cycles

        if window_size < load.operating_duration_hours:
            logger.warning(
                'Device %s: window too small for %d cycles with %.1fh gap (%.1fh per window, needs %.1fh). '
                'Falling back to 1 cycle.',
                load.device_id,
                num_cycles,
                gap_hours,
                window_size,
                load.operating_duration_hours,
            )
            return [load]

        sub_loads = []
        for i in range(num_cycles):
            start_offset_minutes = i * (window_size + gap_hours) * 60
            end_offset_minutes = start_offset_minutes + window_size * 60

            win_start = total_start_minutes + start_offset_minutes
            win_end = total_start_minutes + end_offset_minutes

            win_start_h = int(win_start // 60) % 24
            win_start_m = int(win_start % 60)
            win_end_h = int(win_end // 60) % 24
            win_end_m = int(win_end % 60)

            sub = DeferrableLoadConfig(
                device_id=load.device_id,
                enabled=True,
                nominal_power_w=load.nominal_power_w,
                operating_duration_hours=load.operating_duration_hours,
                is_constant_power=load.is_constant_power,
                is_continuous_operation=load.is_continuous_operation,
                earliest_start_time=f'{win_start_h:02d}:{win_start_m:02d}',
                latest_end_time=f'{win_end_h:02d}:{win_end_m:02d}',
                startup_penalty=load.startup_penalty,
                priority=load.priority,
            )
            sub_loads.append(sub)

        return sub_loads

    def clear_next_run_overrides(self, config: OptimizationConfig) -> None:
        config.next_run_overrides = []
        self.save_config(config)

    def get_managed_battery(self) -> Optional[BatteryOptimizationConfig]:
        devices = self.connector.get_devices()
        for device in devices:
            if 'home_battery' in device.get_all_type_ids():
                capacity = float(device.custom_parameters.get('capacity_kwh', 0))
                if capacity > 0:
                    return BatteryOptimizationConfig.from_device(device)
        return None

    def get_latest_result(self) -> Optional[OptimizationResult]:
        return self.result_store.get_latest_result()

    def _resolve_emhass_url(self, config: OptimizationConfig) -> str:
        from web.model.optimization.emhass_connector import resolve_emhass_url

        return resolve_emhass_url(config.emhass_url)

    def sync_config_to_emhass(self, config: OptimizationConfig) -> bool:
        from web.model.data.ha_connector import HAConnector
        from web.model.optimization.emhass_connector import EmhassConnector

        deferrable_loads, load_mapping = self.get_effective_deferrable_loads(config)
        config.deferrable_loads = deferrable_loads
        config.load_mapping = load_mapping

        ha_connector = HAConnector()
        connector = EmhassConnector(self._resolve_emhass_url(config), ha_connector, self.connector)
        config_dict = connector.build_emhass_config_dict(config)
        logger.debug('Syncing EMHASS config: %s', config_dict)
        return connector.set_emhass_config(config_dict)

    def get_emhass_config(self, config: OptimizationConfig) -> Optional[Dict]:
        from web.model.data.ha_connector import HAConnector
        from web.model.optimization.emhass_connector import EmhassConnector

        ha_connector = HAConnector()
        connector = EmhassConnector(self._resolve_emhass_url(config), ha_connector, self.connector)
        return connector.get_emhass_config()
