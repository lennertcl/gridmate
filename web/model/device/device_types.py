from web.model.device.device_type import DeviceType
from web.model.device.models import CustomParameterDefinition


class BatteryDevice(DeviceType):
    type_id = 'battery_device'
    name = 'Battery Device'
    icon = 'fas fa-battery-three-quarters'
    description = 'A device with a battery that exposes charge level'

    def _define_parameters(self):
        return {
            'battery_level_sensor': CustomParameterDefinition(
                name='battery_level_sensor',
                label='Battery Level Sensor',
                param_type='entity',
                unit='%',
                required=True,
                description='HA entity that reports the battery state of charge',
                placeholder='sensor.device_battery_level',
            ),
            'capacity_kwh': CustomParameterDefinition(
                name='capacity_kwh',
                label='Max Capacity',
                param_type='float',
                unit='kWh',
                required=True,
                description='Total usable capacity of the battery',
                placeholder='13.5',
            ),
            'power_sensor': CustomParameterDefinition(
                name='power_sensor',
                label='Power Sensor',
                param_type='entity',
                unit='kW',
                description='HA entity for charge/discharge power (positive = charging, negative = discharging)',
                placeholder='sensor.device_battery_power',
            ),
        }


class AutomatableDevice(DeviceType):
    type_id = 'automatable_device'
    name = 'Automatable Device'
    icon = 'fas fa-robot'
    description = 'A device that can be started or stopped remotely'

    def _define_parameters(self):
        return {
            'control_entity': CustomParameterDefinition(
                name='control_entity',
                label='Control Entity',
                param_type='entity',
                required=True,
                description='HA entity used to start/stop the device',
                placeholder='switch.device_control',
            ),
            'status_sensor': CustomParameterDefinition(
                name='status_sensor',
                label='Status Sensor',
                param_type='entity',
                description='HA entity that reports current device status',
                placeholder='sensor.device_status',
            ),
        }


class EnergyReportingDevice(DeviceType):
    type_id = 'energy_reporting_device'
    name = 'Energy Reporting Device'
    icon = 'fas fa-plug'
    description = 'A device that reports energy consumption data'

    def _define_parameters(self):
        return {
            'power_sensor': CustomParameterDefinition(
                name='power_sensor',
                label='Power Sensor',
                param_type='entity',
                unit='kW',
                required=True,
                description='HA entity that reports current power consumption',
                placeholder='sensor.device_power',
            ),
            'energy_sensor': CustomParameterDefinition(
                name='energy_sensor',
                label='Energy Sensor',
                param_type='entity',
                unit='kWh',
                description='HA entity that reports cumulative energy consumption',
                placeholder='sensor.device_energy',
            ),
        }


class DurationReportingDevice(DeviceType):
    type_id = 'duration_reporting_device'
    name = 'Duration Reporting Device'
    icon = 'fas fa-hourglass-half'
    description = 'A device that reports remaining time for its current operation'

    def _define_parameters(self):
        return {
            'remaining_time_sensor': CustomParameterDefinition(
                name='remaining_time_sensor',
                label='Remaining Time Sensor',
                param_type='entity',
                unit='min',
                required=True,
                description='HA entity that reports remaining operation time',
                placeholder='sensor.device_remaining_time',
            ),
        }


class WashingMachine(DeviceType):
    type_id = 'washing_machine'
    name = 'Washing Machine'
    icon = 'fas fa-shirt'
    description = 'A washing machine appliance'


class Dryer(DeviceType):
    type_id = 'dryer'
    name = 'Dryer'
    icon = 'fas fa-wind'
    description = 'A clothes dryer appliance'


class Dishwasher(DeviceType):
    type_id = 'dishwasher'
    name = 'Dishwasher'
    icon = 'fas fa-hands-bubbles'
    description = 'A dishwasher appliance'


class ElectricVehicle(DeviceType):
    type_id = 'electric_vehicle'
    name = 'Electric Vehicle'
    icon = 'fas fa-car'
    description = 'An electric vehicle that can be charged and monitored'

    def _define_parameters(self):
        return {
            'range_sensor': CustomParameterDefinition(
                name='range_sensor',
                label='Range Sensor',
                param_type='entity',
                unit='km',
                description='HA entity that reports estimated driving range',
                placeholder='sensor.ev_range',
            ),
            'charging_state_sensor': CustomParameterDefinition(
                name='charging_state_sensor',
                label='Charging State Sensor',
                param_type='entity',
                description='HA entity that reports if the vehicle is currently charging',
                placeholder='sensor.ev_charging_state',
            ),
        }


class HomeBattery(DeviceType):
    type_id = 'home_battery'
    name = 'Home Battery'
    icon = 'fas fa-car-battery'
    description = 'A stationary home battery system for energy storage'

    def _define_parameters(self):
        return {
            'opt_enabled': CustomParameterDefinition(
                name='opt_enabled',
                label='Optimization Enabled',
                param_type='bool',
                default_value=False,
                description='Whether this battery participates in optimization',
            ),
            'max_charge_power': CustomParameterDefinition(
                name='max_charge_power',
                label='Max Charge Power',
                param_type='float',
                unit='kW',
                description='Maximum charging power of the battery',
                placeholder='5.0',
            ),
            'max_discharge_power': CustomParameterDefinition(
                name='max_discharge_power',
                label='Max Discharge Power',
                param_type='float',
                unit='kW',
                description='Maximum discharging power of the battery',
                placeholder='5.0',
            ),
            'mode_select_entity': CustomParameterDefinition(
                name='mode_select_entity',
                label='Mode Select Entity',
                param_type='entity',
                description='HA select/input_select entity to switch the battery operating mode',
                placeholder='select.battery_mode',
            ),
            'charge_efficiency': CustomParameterDefinition(
                name='charge_efficiency',
                label='Charge Efficiency',
                param_type='float',
                default_value=0.95,
                description='Charging efficiency factor between 0 and 1',
                placeholder='0.95',
            ),
            'discharge_efficiency': CustomParameterDefinition(
                name='discharge_efficiency',
                label='Discharge Efficiency',
                param_type='float',
                default_value=0.95,
                description='Discharging efficiency factor between 0 and 1',
                placeholder='0.95',
            ),
            'min_charge_level': CustomParameterDefinition(
                name='min_charge_level',
                label='Min Charge Level',
                param_type='int',
                unit='%',
                default_value=20,
                description='Minimum battery state of charge to maintain',
                placeholder='20',
            ),
            'max_charge_level': CustomParameterDefinition(
                name='max_charge_level',
                label='Max Charge Level',
                param_type='int',
                unit='%',
                default_value=80,
                description='Maximum battery state of charge allowed',
                placeholder='80',
            ),
            'target_soc': CustomParameterDefinition(
                name='target_soc',
                label='Target SOC',
                param_type='int',
                unit='%',
                default_value=80,
                description='Target state of charge for optimization',
                placeholder='80',
            ),
        }


class WaterHeater(DeviceType):
    type_id = 'water_heater'
    name = 'Water Heater'
    icon = 'fas fa-faucet-drip'
    description = 'An electric water heater or boiler'

    def _define_parameters(self):
        return {
            'temperature_sensor': CustomParameterDefinition(
                name='temperature_sensor',
                label='Temperature Sensor',
                param_type='entity',
                unit='°C',
                description='HA entity that reports current water temperature',
                placeholder='sensor.boiler_temperature',
            ),
        }


class ElectricHeating(DeviceType):
    type_id = 'electric_heating'
    name = 'Electric Heating'
    icon = 'fas fa-fire'
    description = 'An electric heater or radiator'

    def _define_parameters(self):
        return {
            'temperature_sensor': CustomParameterDefinition(
                name='temperature_sensor',
                label='Temperature Sensor',
                param_type='entity',
                unit='°C',
                description='HA entity that reports current temperature',
                placeholder='sensor.heater_temperature',
            ),
            'thermostat_entity': CustomParameterDefinition(
                name='thermostat_entity',
                label='Thermostat Entity',
                param_type='entity',
                description='HA climate entity for thermostat control',
                placeholder='climate.heater',
            ),
        }


class HeatPump(DeviceType):
    type_id = 'heat_pump'
    name = 'Heat Pump'
    icon = 'fas fa-temperature-arrow-up'
    description = 'A heat pump for heating and cooling'

    def _define_parameters(self):
        return {
            'temperature_sensor': CustomParameterDefinition(
                name='temperature_sensor',
                label='Temperature Sensor',
                param_type='entity',
                unit='°C',
                description='HA entity that reports current temperature',
                placeholder='sensor.heat_pump_temperature',
            ),
            'cop_sensor': CustomParameterDefinition(
                name='cop_sensor',
                label='COP Sensor',
                param_type='entity',
                description='HA entity that reports coefficient of performance',
                placeholder='sensor.heat_pump_cop',
            ),
        }


class ChargingStation(DeviceType):
    type_id = 'charging_station'
    name = 'Charging Station'
    icon = 'fas fa-charging-station'
    description = 'An EV charging station or wallbox'

    def _define_parameters(self):
        return {
            'max_charge_rate': CustomParameterDefinition(
                name='max_charge_rate',
                label='Max Charge Rate',
                param_type='float',
                unit='kW',
                description='Maximum charging rate of the station',
                placeholder='22',
            ),
            'session_energy_sensor': CustomParameterDefinition(
                name='session_energy_sensor',
                label='Session Energy Sensor',
                param_type='entity',
                unit='kWh',
                description='HA entity that reports energy used in current session',
                placeholder='sensor.charger_session_energy',
            ),
        }


class DeferrableLoad(DeviceType):
    type_id = 'deferrable_load'
    name = 'Deferrable Load'
    icon = 'fas fa-clock'
    description = 'A device whose operation can be scheduled by the optimizer'

    def _define_parameters(self):
        return {
            'opt_enabled': CustomParameterDefinition(
                name='opt_enabled',
                label='Optimization Enabled',
                param_type='bool',
                default_value=True,
                description='Whether this device participates in optimization',
            ),
            'opt_nominal_power': CustomParameterDefinition(
                name='opt_nominal_power',
                label='Nominal Power',
                param_type='float',
                unit='W',
                required=True,
                description='Nominal power consumption when operating',
                placeholder='2000',
            ),
            'opt_duration_hours': CustomParameterDefinition(
                name='opt_duration_hours',
                label='Operating Duration',
                param_type='float',
                unit='hours',
                required=True,
                description='Required operating duration per cycle',
                placeholder='3',
            ),
            'opt_constant_power': CustomParameterDefinition(
                name='opt_constant_power',
                label='Constant Power',
                param_type='bool',
                default_value=True,
                description='When enabled, the device always runs at its full nominal power when active (on/off only). When disabled, the optimizer can vary the power between 0 and the nominal power to better match available solar or cheaper time slots.',
            ),
            'opt_continuous_operation': CustomParameterDefinition(
                name='opt_continuous_operation',
                label='Continuous Operation',
                param_type='bool',
                default_value=False,
                description='When enabled, the device must complete its full run in one uninterrupted block. When disabled, the optimizer may split the operation into separate time segments to find cheaper energy prices.',
            ),
            'opt_earliest_start': CustomParameterDefinition(
                name='opt_earliest_start',
                label='Earliest Start Time',
                param_type='time',
                description='Earliest time of day the device is allowed to start operating',
                placeholder='08:00',
            ),
            'opt_latest_end': CustomParameterDefinition(
                name='opt_latest_end',
                label='Latest End Time',
                param_type='time',
                description='Latest time of day the device must finish its operation',
                placeholder='22:00',
            ),
            'opt_startup_penalty': CustomParameterDefinition(
                name='opt_startup_penalty',
                label='Startup Penalty',
                param_type='float',
                unit='€',
                default_value=0.0,
                description='Cost penalty applied each time the device starts, discouraging frequent on/off cycling',
                placeholder='0.50',
            ),
            'opt_priority': CustomParameterDefinition(
                name='opt_priority',
                label='Priority',
                param_type='int',
                default_value=5,
                description='Determines scheduling order when multiple devices compete for the same cheap time slots. Lower values (1) are scheduled first, higher values (10) last.',
                placeholder='5',
            ),
        }
