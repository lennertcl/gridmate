from web.forms.contract import (
    CapacityComponentForm,
    ConstantComponentForm,
    FixedComponentForm,
    PercentageComponentForm,
    VariableComponentForm,
)
from web.forms.data import DataJsonEditForm
from web.forms.device import AddDeviceForm, EditDeviceForm
from web.forms.energy import EnergyCostsForm, EnergyFeedConfigForm
from web.forms.optimization import EnergyOptimizationForm, OptimizationSettingsForm
from web.forms.solar import SolarConfigForm

__all__ = [
    'AddDeviceForm',
    'EditDeviceForm',
    'SolarConfigForm',
    'EnergyFeedConfigForm',
    'EnergyCostsForm',
    'ConstantComponentForm',
    'FixedComponentForm',
    'VariableComponentForm',
    'CapacityComponentForm',
    'PercentageComponentForm',
    'EnergyOptimizationForm',
    'OptimizationSettingsForm',
    'DataJsonEditForm',
]
