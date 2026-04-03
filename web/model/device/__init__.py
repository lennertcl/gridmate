import web.model.device.device_types  # noqa: F401 — triggers __init_subclass__ registration
from web.model.device.device_type import DeviceType, get_device_type_registry
from web.model.device.models import (
    PARAM_TYPE_BOOL,
    PARAM_TYPE_ENTITY,
    PARAM_TYPE_FLOAT,
    PARAM_TYPE_INT,
    PARAM_TYPE_STRING,
    VALID_PARAM_TYPES,
    CustomParameterDefinition,
    Device,
)

__all__ = [
    'Device',
    'DeviceType',
    'CustomParameterDefinition',
    'PARAM_TYPE_STRING',
    'PARAM_TYPE_FLOAT',
    'PARAM_TYPE_INT',
    'PARAM_TYPE_BOOL',
    'PARAM_TYPE_ENTITY',
    'VALID_PARAM_TYPES',
    'get_device_type_registry',
]
