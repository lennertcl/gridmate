from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from web.model.device.device_type import DeviceType

PARAM_TYPE_STRING = 'string'
PARAM_TYPE_FLOAT = 'float'
PARAM_TYPE_INT = 'int'
PARAM_TYPE_BOOL = 'bool'
PARAM_TYPE_ENTITY = 'entity'
PARAM_TYPE_TIME = 'time'

VALID_PARAM_TYPES = [
    PARAM_TYPE_STRING,
    PARAM_TYPE_FLOAT,
    PARAM_TYPE_INT,
    PARAM_TYPE_BOOL,
    PARAM_TYPE_ENTITY,
    PARAM_TYPE_TIME,
]


@dataclass
class CustomParameterDefinition:
    name: str
    label: str
    param_type: str = PARAM_TYPE_STRING
    unit: str = ''
    required: bool = False
    description: str = ''
    default_value: Any = None
    placeholder: str = ''

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'label': self.label,
            'param_type': self.param_type,
            'unit': self.unit,
            'required': self.required,
            'description': self.description,
            'default_value': self.default_value,
            'placeholder': self.placeholder,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'CustomParameterDefinition':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Device:
    device_id: str
    name: str
    primary_type: str
    secondary_types: List[str] = field(default_factory=list)
    custom_parameters: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    def get_all_type_ids(self) -> List[str]:
        return [self.primary_type] + self.secondary_types

    def get_all_parameters(self, type_registry: Dict[str, DeviceType]) -> Dict[str, CustomParameterDefinition]:
        params = {}
        for type_id in self.get_all_type_ids():
            dt = type_registry.get(type_id)
            if dt:
                params.update(dt.custom_parameters)
        return params

    def to_dict(self) -> Dict:
        return {
            'device_id': self.device_id,
            'name': self.name,
            'primary_type': self.primary_type,
            'secondary_types': self.secondary_types,
            'custom_parameters': self.custom_parameters,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'last_updated': self.last_updated.isoformat()
            if isinstance(self.last_updated, datetime)
            else self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Device':
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        last_updated = data.get('last_updated')
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)
        elif last_updated is None:
            last_updated = datetime.now()

        return cls(
            device_id=data.get('device_id', ''),
            name=data.get('name', ''),
            primary_type=data.get('primary_type', ''),
            secondary_types=data.get('secondary_types', []),
            custom_parameters=data.get('custom_parameters', {}),
            created_at=created_at,
            last_updated=last_updated,
        )

    def get_param(self, key: str, default: Any = None) -> Any:
        return self.custom_parameters.get(key, default)

    def set_param(self, key: str, value: Any) -> None:
        self.custom_parameters[key] = value
