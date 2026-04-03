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
class SolarEstimationSensors:
    estimated_actual_production: str = ''
    estimated_energy_production_remaining_today: str = ''
    estimated_energy_production_today: str = ''
    estimated_energy_production_hour: str = ''
    estimated_actual_production_offset_day: str = ''
    estimated_energy_production_offset_day: str = ''
    estimated_energy_production_offset_hour: str = ''

    def to_dict(self) -> Dict:
        return {
            'estimated_actual_production': self.estimated_actual_production,
            'estimated_energy_production_remaining_today': self.estimated_energy_production_remaining_today,
            'estimated_energy_production_today': self.estimated_energy_production_today,
            'estimated_energy_production_hour': self.estimated_energy_production_hour,
            'estimated_actual_production_offset_day': self.estimated_actual_production_offset_day,
            'estimated_energy_production_offset_day': self.estimated_energy_production_offset_day,
            'estimated_energy_production_offset_hour': self.estimated_energy_production_offset_hour,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'SolarEstimationSensors':
        return cls(
            estimated_actual_production=data.get('estimated_actual_production', ''),
            estimated_energy_production_remaining_today=data.get('estimated_energy_production_remaining_today', ''),
            estimated_energy_production_today=data.get('estimated_energy_production_today', ''),
            estimated_energy_production_hour=data.get('estimated_energy_production_hour', ''),
            estimated_actual_production_offset_day=data.get('estimated_actual_production_offset_day', ''),
            estimated_energy_production_offset_day=data.get('estimated_energy_production_offset_day', ''),
            estimated_energy_production_offset_hour=data.get('estimated_energy_production_offset_hour', ''),
        )

    @property
    def has_any(self) -> bool:
        return bool(
            self.estimated_actual_production
            or self.estimated_energy_production_remaining_today
            or self.estimated_energy_production_today
            or self.estimated_energy_production_hour
            or self.estimated_actual_production_offset_day
            or self.estimated_energy_production_offset_day
            or self.estimated_energy_production_offset_hour
        )


@dataclass
class Solar:
    sensors: SolarSensors = field(default_factory=SolarSensors)
    estimation_sensors: SolarEstimationSensors = field(default_factory=SolarEstimationSensors)
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def is_configured(self) -> bool:
        return self.sensors.has_any

    def to_dict(self) -> Dict:
        return {
            'sensors': self.sensors.to_dict(),
            'estimation_sensors': self.estimation_sensors.to_dict(),
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
        estimation_data = data.get('estimation_sensors', {})

        return cls(
            sensors=SolarSensors.from_dict(sensors_data),
            estimation_sensors=SolarEstimationSensors.from_dict(estimation_data),
            last_updated=last_updated,
        )
