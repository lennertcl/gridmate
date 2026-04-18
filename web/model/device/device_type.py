from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from web.model.device.models import CustomParameterDefinition

if TYPE_CHECKING:
    from web.model.device.models import Device

_DEVICE_TYPE_REGISTRY: Dict[str, DeviceType] = {}

DEVICE_TYPE_SECTION_PRIORITY = [
    'energy_reporting_device',
    'deferrable_load',
    'battery_device',
    'duration_reporting_device',
    'home_battery',
    'electric_vehicle',
    'charging_station',
    'heat_pump',
    'electric_heating',
    'water_heater',
    'washing_machine',
    'dryer',
    'dishwasher',
]

MAX_DEVICE_CARD_SECTIONS = 3


class DeviceType:
    type_id: str = ''
    name: str = ''
    icon: str = 'fas fa-plug'
    description: str = ''

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.type_id:
            _DEVICE_TYPE_REGISTRY[cls.type_id] = cls()

    def __init__(self):
        self.custom_parameters: Dict[str, CustomParameterDefinition] = self._define_parameters()

    def _define_parameters(self) -> Dict[str, CustomParameterDefinition]:
        return {}

    def get_mandatory_parameters(self) -> Dict[str, CustomParameterDefinition]:
        return {k: v for k, v in self.custom_parameters.items() if v.required}

    def get_optional_parameters(self) -> Dict[str, CustomParameterDefinition]:
        return {k: v for k, v in self.custom_parameters.items() if not v.required}

    def to_dict(self) -> Dict:
        return {
            'type_id': self.type_id,
            'name': self.name,
            'icon': self.icon,
            'custom_parameters': {k: v.to_dict() for k, v in self.custom_parameters.items()},
            'description': self.description,
        }


def get_device_type_registry() -> Dict[str, DeviceType]:
    return _DEVICE_TYPE_REGISTRY


def get_device_sections(
    device: Device, type_registry: Dict[str, DeviceType], max_sections: Optional[int] = MAX_DEVICE_CARD_SECTIONS
) -> List[Tuple[str, DeviceType]]:
    sections = []
    seen = set()

    if device.primary_type != 'automatable_device':
        pt = type_registry.get(device.primary_type)
        if pt:
            sections.append((device.primary_type, pt))
            seen.add(device.primary_type)

    all_type_ids = set(device.get_all_type_ids())
    for type_id in DEVICE_TYPE_SECTION_PRIORITY:
        if max_sections is not None and len(sections) >= max_sections:
            break
        if type_id in all_type_ids and type_id not in seen and type_id != 'automatable_device':
            dt = type_registry.get(type_id)
            if dt:
                sections.append((type_id, dt))
                seen.add(type_id)

    for type_id in device.get_all_type_ids():
        if max_sections is not None and len(sections) >= max_sections:
            break
        if type_id not in seen and type_id != 'automatable_device':
            dt = type_registry.get(type_id)
            if dt:
                sections.append((type_id, dt))
                seen.add(type_id)

    return sections
