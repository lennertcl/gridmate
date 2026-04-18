from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict


@dataclass
class SolarSensors:
    actual_production: str = ''
    energy_production_today: str = ''
    energy_production_lifetime: str = ''

    def to_dict(self) -> Dict:
        return {
            'actual_production': self.actual_production,
            'energy_production_today': self.energy_production_today,
            'energy_production_lifetime': self.energy_production_lifetime,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'SolarSensors':
        return cls(
            actual_production=data.get('actual_production', ''),
            energy_production_today=data.get('energy_production_today', ''),
            energy_production_lifetime=data.get('energy_production_lifetime', ''),
        )

    @property
    def has_any(self) -> bool:
        return bool(self.actual_production or self.energy_production_today or self.energy_production_lifetime)


@dataclass
class Solar:
    sensors: SolarSensors = field(default_factory=SolarSensors)
    forecast_provider_config: dict = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def is_configured(self) -> bool:
        return self.sensors.has_any

    def to_dict(self) -> Dict:
        return {
            'sensors': self.sensors.to_dict(),
            'forecast_provider': self.forecast_provider_config,
            'last_updated': self.last_updated.isoformat()
            if isinstance(self.last_updated, datetime)
            else self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Solar':
        last_updated = data.get('last_updated')
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)
        elif last_updated is None:
            last_updated = datetime.now()

        sensors_data = data.get('sensors', {})
        if not sensors_data:
            sensors_data = {
                'actual_production': data.get('production_entity', ''),
            }

        forecast_provider_config = data.get('forecast_provider', {})

        # Migration: convert old estimation_sensors to forecast_provider_config
        if not forecast_provider_config:
            estimation_data = data.get('estimation_sensors', {})
            offset_sensor = estimation_data.get('estimated_actual_production_offset_day', '')
            if offset_sensor:
                forecast_provider_config = {
                    'type': 'forecast_solar',
                    'config': {'sensor_entity': offset_sensor},
                }

        return cls(
            sensors=SolarSensors.from_dict(sensors_data),
            forecast_provider_config=forecast_provider_config,
            last_updated=last_updated,
        )
