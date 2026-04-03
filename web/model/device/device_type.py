from typing import Dict

from web.model.device.models import CustomParameterDefinition

_DEVICE_TYPE_REGISTRY: Dict[str, 'DeviceType'] = {}


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
