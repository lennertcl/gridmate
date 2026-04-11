import logging
from typing import Dict, List

from web.model.data.data_connector import DataConnector
from web.model.data.ha_connector import HAConnector
from web.model.optimization.models import (
    DeviceSchedule,
    OptimizationConfig,
    OptimizationResult,
)

logger = logging.getLogger(__name__)

GRIDMATE_PREFIX = 'gridmate_'
GRIDMATE_DEVICE_PREFIX = 'gridmate_device_'
GRIDMATE_TRIGGER_ID = 'gridmate_daily_optimization'
GRIDMATE_ALIAS_TAG = '[gridmate]'
AUTOMATION_DESCRIPTION = 'Managed by GridMate - do not modify manually'


class HAAutomationManager:
    def __init__(self, ha_connector: HAConnector, data_connector: DataConnector):
        self.ha = ha_connector
        self.data_connector = data_connector

    def ensure_trigger_automation(self, config: OptimizationConfig) -> bool:
        automation_config = self._build_trigger_automation(config)
        success = self.ha.create_or_update_automation(GRIDMATE_TRIGGER_ID, automation_config)
        if success:
            self.ha.reload_automations()
        return success

    def remove_trigger_automation(self) -> bool:
        return self.ha.delete_automation(GRIDMATE_TRIGGER_ID)

    def sync_device_automations(self, result: OptimizationResult) -> None:
        self._cleanup_device_automations()

        for device_id, schedule in result.device_schedules.items():
            active_entries = [e for e in schedule.schedule_entries if e.is_active]
            if not active_entries:
                continue

            device = self.data_connector.get_device(device_id)
            if not device:
                logger.warning(f'Device {device_id} not found, skipping automation')
                continue

            control_entity = device.custom_parameters.get('control_entity', '')
            if not control_entity:
                logger.warning(f'Device {device_id} has no control_entity, skipping automation')
                continue

            is_constant_power = device.custom_parameters.get('opt_constant_power', True)
            power_control_entity = device.custom_parameters.get('power_control_entity', '')

            automation_id = f'{GRIDMATE_DEVICE_PREFIX}{device_id}'
            automation_config = self._build_device_automation(
                device_name=device.name,
                schedule=schedule,
                control_entity=control_entity,
                is_constant_power=is_constant_power,
                power_control_entity=power_control_entity,
            )

            self.ha.create_or_update_automation(automation_id, automation_config)

        self.ha.reload_automations()

    def cleanup_all_automations(self) -> None:
        gridmate_ids = self._list_gridmate_automation_ids()
        for automation_id in gridmate_ids:
            self.ha.delete_automation(automation_id)
        if gridmate_ids:
            self.ha.reload_automations()

    def cleanup_device_automations(self) -> None:
        self._cleanup_device_automations()
        self.ha.reload_automations()

    def _cleanup_device_automations(self) -> None:
        gridmate_ids = self._list_gridmate_automation_ids()
        for automation_id in gridmate_ids:
            if automation_id.startswith(GRIDMATE_DEVICE_PREFIX):
                self.ha.delete_automation(automation_id)

    def _list_gridmate_automation_ids(self) -> List[str]:
        automations = self.ha.get_automations()
        gridmate_ids = []
        for automation in automations:
            automation_id = automation.get('attributes', {}).get('id', '')
            if isinstance(automation_id, str) and automation_id.startswith(GRIDMATE_PREFIX):
                gridmate_ids.append(automation_id)
        return gridmate_ids

    def _build_trigger_automation(self, config: OptimizationConfig) -> Dict:
        schedule_time = config.dayahead_schedule_time or '05:30'
        if len(schedule_time) == 5:
            schedule_time = f'{schedule_time}:00'

        return {
            'id': GRIDMATE_TRIGGER_ID,
            'alias': f'{GRIDMATE_ALIAS_TAG} Daily Optimization',
            'description': AUTOMATION_DESCRIPTION,
            'trigger': [
                {
                    'platform': 'time',
                    'at': schedule_time,
                }
            ],
            'condition': [],
            'action': [
                {
                    'service': 'rest_command.gridmate_run_optimization',
                    'data': {},
                }
            ],
            'mode': 'single',
        }

    def _build_device_automation(
        self,
        device_name: str,
        schedule: DeviceSchedule,
        control_entity: str,
        is_constant_power: bool,
        power_control_entity: str,
    ) -> Dict:
        active_entries = [e for e in schedule.schedule_entries if e.is_active]
        domain = control_entity.split('.')[0]
        triggers = []
        on_trigger_ids = []
        off_trigger_ids = []

        for i, entry in enumerate(active_entries):
            start_str = (
                entry.start_time.strftime('%H:%M:%S')
                if hasattr(entry.start_time, 'strftime')
                else str(entry.start_time)
            )
            end_str = (
                entry.end_time.strftime('%H:%M:%S') if hasattr(entry.end_time, 'strftime') else str(entry.end_time)
            )

            on_id = f'block_{i}_on'
            off_id = f'block_{i}_off'

            triggers.append({'platform': 'time', 'at': start_str, 'id': on_id})
            triggers.append({'platform': 'time', 'at': end_str, 'id': off_id})

            on_trigger_ids.append(on_id)
            off_trigger_ids.append(off_id)

        choose_branches = self._build_choose_branches(
            active_entries=active_entries,
            on_trigger_ids=on_trigger_ids,
            off_trigger_ids=off_trigger_ids,
            control_entity=control_entity,
            domain=domain,
            is_constant_power=is_constant_power,
            power_control_entity=power_control_entity,
        )

        return {
            'id': f'{GRIDMATE_DEVICE_PREFIX}{schedule.device_id}',
            'alias': f'{GRIDMATE_ALIAS_TAG} {device_name}',
            'description': AUTOMATION_DESCRIPTION,
            'trigger': triggers,
            'condition': [],
            'action': [{'choose': choose_branches}],
            'mode': 'single',
        }

    def _build_choose_branches(
        self,
        active_entries: list,
        on_trigger_ids: List[str],
        off_trigger_ids: List[str],
        control_entity: str,
        domain: str,
        is_constant_power: bool,
        power_control_entity: str,
    ) -> List[Dict]:
        branches = []

        if is_constant_power or not power_control_entity:
            on_sequence = [{'service': f'{domain}.turn_on', 'target': {'entity_id': control_entity}}]
            branches.append(
                {
                    'conditions': [{'condition': 'trigger', 'id': on_trigger_ids}],
                    'sequence': on_sequence,
                }
            )
        else:
            for i, entry in enumerate(active_entries):
                on_sequence = [
                    {'service': f'{domain}.turn_on', 'target': {'entity_id': control_entity}},
                    {
                        'service': 'number.set_value',
                        'target': {'entity_id': power_control_entity},
                        'data': {'value': round(entry.power_w, 1)},
                    },
                ]
                branches.append(
                    {
                        'conditions': [{'condition': 'trigger', 'id': on_trigger_ids[i]}],
                        'sequence': on_sequence,
                    }
                )

        off_sequence = [{'service': f'{domain}.turn_off', 'target': {'entity_id': control_entity}}]
        branches.append(
            {
                'conditions': [{'condition': 'trigger', 'id': off_trigger_ids}],
                'sequence': off_sequence,
            }
        )

        return branches
