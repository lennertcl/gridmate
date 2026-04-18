import calendar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


@dataclass
class DeviceDayEntry:
    device_id: str = ''
    num_cycles: int = 1
    hours_between_runs: float = 0.0
    earliest_start_time: str = ''
    latest_end_time: str = ''

    def to_dict(self) -> Dict:
        return {
            'device_id': self.device_id,
            'num_cycles': self.num_cycles,
            'hours_between_runs': self.hours_between_runs,
            'earliest_start_time': self.earliest_start_time,
            'latest_end_time': self.latest_end_time,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'DeviceDayEntry':
        num_cycles = int(data.get('num_cycles', data.get('num_runs', 1)))
        if 'enabled' in data and not data['enabled']:
            num_cycles = 0
        return cls(
            device_id=data.get('device_id', ''),
            num_cycles=num_cycles,
            hours_between_runs=float(data.get('hours_between_runs', 0.0)),
            earliest_start_time=data.get('earliest_start_time', ''),
            latest_end_time=data.get('latest_end_time', ''),
        )


@dataclass
class WeeklySchedule:
    days: Dict[str, List[DeviceDayEntry]] = field(default_factory=dict)

    def get_today(self) -> List[DeviceDayEntry]:
        day_name = calendar.day_name[datetime.now().weekday()].lower()
        return self.days.get(day_name, [])

    def get_day(self, day_name: str) -> List[DeviceDayEntry]:
        return self.days.get(day_name.lower(), [])

    def get_device_entry_for_today(self, device_id: str) -> Optional[DeviceDayEntry]:
        for entry in self.get_today():
            if entry.device_id == device_id:
                return entry
        return None

    def to_dict(self) -> Dict:
        return {day: [e.to_dict() for e in entries] for day, entries in self.days.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'WeeklySchedule':
        days = {}
        for day, entries in data.items():
            if day.lower() in WEEKDAYS:
                days[day.lower()] = [DeviceDayEntry.from_dict(e) for e in entries]
        return cls(days=days)


@dataclass
class DeferrableLoadConfig:
    device_id: str = ''
    enabled: bool = True
    nominal_power_w: float = 0.0
    operating_duration_hours: float = 0.0
    is_constant_power: bool = True
    is_continuous_operation: bool = False
    earliest_start_time: str = ''
    latest_end_time: str = ''
    startup_penalty: float = 0.0
    priority: int = 5

    def to_dict(self) -> Dict:
        return {
            'device_id': self.device_id,
            'enabled': self.enabled,
            'nominal_power_w': self.nominal_power_w,
            'operating_duration_hours': self.operating_duration_hours,
            'is_constant_power': self.is_constant_power,
            'is_continuous_operation': self.is_continuous_operation,
            'earliest_start_time': self.earliest_start_time,
            'latest_end_time': self.latest_end_time,
            'startup_penalty': self.startup_penalty,
            'priority': self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'DeferrableLoadConfig':
        return cls(
            device_id=data.get('device_id', ''),
            enabled=data.get('enabled', True),
            nominal_power_w=float(data.get('nominal_power_w', 0.0)),
            operating_duration_hours=float(data.get('operating_duration_hours', 0.0)),
            is_constant_power=data.get('is_constant_power', True),
            is_continuous_operation=data.get('is_continuous_operation', False),
            earliest_start_time=data.get('earliest_start_time', ''),
            latest_end_time=data.get('latest_end_time', ''),
            startup_penalty=float(data.get('startup_penalty', 0.0)),
            priority=int(data.get('priority', 5)),
        )

    @classmethod
    def from_device(cls, device) -> 'DeferrableLoadConfig':
        params = device.custom_parameters
        return cls(
            device_id=device.device_id,
            enabled=params.get('opt_enabled', True),
            nominal_power_w=float(params.get('opt_nominal_power', 0.0)),
            operating_duration_hours=float(params.get('opt_duration_hours', 0.0)),
            is_constant_power=params.get('opt_constant_power', True),
            is_continuous_operation=params.get('opt_continuous_operation', False),
            earliest_start_time=params.get('opt_earliest_start', ''),
            latest_end_time=params.get('opt_latest_end', ''),
            startup_penalty=float(params.get('opt_startup_penalty', 0.0)),
            priority=int(params.get('opt_priority', 5)),
        )


@dataclass
class BatteryOptimizationConfig:
    device_id: str = ''
    device_name: str = ''
    enabled: bool = False
    capacity_kwh: float = 0.0
    max_charge_power_kw: float = 0.0
    max_discharge_power_kw: float = 0.0
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    min_charge_level: int = 20
    max_charge_level: int = 80
    target_soc: int = 80

    def to_dict(self) -> Dict:
        return {
            'device_id': self.device_id,
            'device_name': self.device_name,
            'enabled': self.enabled,
            'capacity_kwh': self.capacity_kwh,
            'max_charge_power_kw': self.max_charge_power_kw,
            'max_discharge_power_kw': self.max_discharge_power_kw,
            'charge_efficiency': self.charge_efficiency,
            'discharge_efficiency': self.discharge_efficiency,
            'min_charge_level': self.min_charge_level,
            'max_charge_level': self.max_charge_level,
            'target_soc': self.target_soc,
        }

    @classmethod
    def from_device(cls, device) -> 'BatteryOptimizationConfig':
        params = device.custom_parameters
        return cls(
            device_id=device.device_id,
            device_name=device.name,
            enabled=params.get('opt_enabled', False),
            capacity_kwh=float(params.get('capacity_kwh', 0.0)),
            max_charge_power_kw=float(params.get('max_charge_power', 0.0)),
            max_discharge_power_kw=float(params.get('max_discharge_power', 0.0)),
            charge_efficiency=float(params.get('charge_efficiency', 0.95)),
            discharge_efficiency=float(params.get('discharge_efficiency', 0.95)),
            min_charge_level=int(params.get('min_charge_level', 20)),
            max_charge_level=int(params.get('max_charge_level', 80)),
            target_soc=int(params.get('target_soc', 80)),
        )


@dataclass
class LoadPowerScheduleBlock:
    start_time: str = '00:00'
    end_time: str = '23:59'
    power_w: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'start_time': self.start_time,
            'end_time': self.end_time,
            'power_w': self.power_w,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'LoadPowerScheduleBlock':
        return cls(
            start_time=data.get('start_time', '00:00'),
            end_time=data.get('end_time', '23:59'),
            power_w=float(data.get('power_w', 0.0)),
        )


@dataclass
class LoadPowerConfig:
    source_type: str = 'sensor'
    sensor_entity: str = ''
    schedule_blocks: List['LoadPowerScheduleBlock'] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'source_type': self.source_type,
            'sensor_entity': self.sensor_entity,
            'schedule_blocks': [b.to_dict() for b in self.schedule_blocks],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'LoadPowerConfig':
        blocks = [LoadPowerScheduleBlock.from_dict(b) for b in data.get('schedule_blocks', [])]
        return cls(
            source_type=data.get('source_type', 'sensor'),
            sensor_entity=data.get('sensor_entity', ''),
            schedule_blocks=blocks,
        )

    def build_forecast(self, time_step_minutes: int, horizon_hours: int) -> List[float]:
        if self.source_type != 'schedule' or not self.schedule_blocks:
            return []

        from datetime import timedelta

        num_steps = (horizon_hours * 60) // time_step_minutes
        now = datetime.now()
        forecast = []
        for i in range(num_steps):
            ts = now + timedelta(minutes=i * time_step_minutes)
            current_minutes = ts.hour * 60 + ts.minute
            power = 0.0
            for block in self.schedule_blocks:
                bh, bm = map(int, block.start_time.split(':'))
                eh, em = map(int, block.end_time.split(':'))
                block_start = bh * 60 + bm
                block_end = eh * 60 + em
                if block_start <= current_minutes <= block_end:
                    power = block.power_w
                    break
            forecast.append(power)
        return forecast


@dataclass
class OptimizationConfig:
    emhass_url: str = ''
    enabled: bool = False
    dayahead_schedule_time: str = '05:30'
    max_grid_import_w: int = 9000
    max_grid_export_w: int = 9000
    actuation_mode: str = 'manual'
    load_power_config: LoadPowerConfig = field(default_factory=LoadPowerConfig)
    weekly_schedule: WeeklySchedule = field(default_factory=WeeklySchedule)
    next_run_overrides: List[DeviceDayEntry] = field(default_factory=list)

    last_optimization_run: Optional[datetime] = None
    last_optimization_status: str = ''
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'emhass_url': self.emhass_url,
            'enabled': self.enabled,
            'dayahead_schedule_time': self.dayahead_schedule_time,
            'max_grid_import_w': self.max_grid_import_w,
            'max_grid_export_w': self.max_grid_export_w,
            'actuation_mode': self.actuation_mode,
            'load_power_config': self.load_power_config.to_dict(),
            'weekly_schedule': self.weekly_schedule.to_dict(),
            'next_run_overrides': [o.to_dict() for o in self.next_run_overrides],
            'last_optimization_run': self.last_optimization_run.isoformat()
            if isinstance(self.last_optimization_run, datetime)
            else self.last_optimization_run,
            'last_optimization_status': self.last_optimization_status,
            'last_updated': self.last_updated.isoformat()
            if isinstance(self.last_updated, datetime)
            else self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'OptimizationConfig':
        def _parse_dt(val):
            if isinstance(val, str):
                return datetime.fromisoformat(val)
            return val

        load_power_raw = data.get('load_power_config', {})
        if not load_power_raw and data.get('load_power_sensor'):
            load_power_raw = {
                'source_type': 'sensor',
                'sensor_entity': data['load_power_sensor'],
            }

        return cls(
            emhass_url=data.get('emhass_url', ''),
            enabled=data.get('enabled', False),
            dayahead_schedule_time=data.get('dayahead_schedule_time', '05:30'),
            max_grid_import_w=int(data.get('max_grid_import_w', 9000)),
            max_grid_export_w=int(data.get('max_grid_export_w', 9000)),
            actuation_mode=data.get('actuation_mode', 'manual'),
            load_power_config=LoadPowerConfig.from_dict(load_power_raw),
            weekly_schedule=WeeklySchedule.from_dict(data.get('weekly_schedule', {})),
            next_run_overrides=[DeviceDayEntry.from_dict(o) for o in data.get('next_run_overrides', [])],
            last_optimization_run=_parse_dt(data.get('last_optimization_run')),
            last_optimization_status=data.get('last_optimization_status', ''),
            last_updated=_parse_dt(data.get('last_updated')) or datetime.now(),
        )


@dataclass
class TimeseriesPoint:
    timestamp: datetime = field(default_factory=datetime.now)
    value: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'value': self.value,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'TimeseriesPoint':
        ts = data.get('timestamp')
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif ts is None:
            ts = datetime.now()
        return cls(timestamp=ts, value=float(data.get('value', 0.0)))

    def __repr__(self):
        return f'({self.timestamp.isoformat()}: {self.value})'


@dataclass
class ScheduleEntry:
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime = field(default_factory=datetime.now)
    power_w: float = 0.0
    is_active: bool = False

    def to_dict(self) -> Dict:
        return {
            'start_time': self.start_time.isoformat() if isinstance(self.start_time, datetime) else self.start_time,
            'end_time': self.end_time.isoformat() if isinstance(self.end_time, datetime) else self.end_time,
            'power_w': self.power_w,
            'is_active': self.is_active,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ScheduleEntry':
        def _parse_dt(val):
            if isinstance(val, str):
                return datetime.fromisoformat(val)
            return val or datetime.now()

        return cls(
            start_time=_parse_dt(data.get('start_time')),
            end_time=_parse_dt(data.get('end_time')),
            power_w=float(data.get('power_w', 0.0)),
            is_active=data.get('is_active', False),
        )


@dataclass
class DeviceSchedule:
    device_id: str = ''
    device_name: str = ''
    schedule_entries: List[ScheduleEntry] = field(default_factory=list)
    total_energy_kwh: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'device_id': self.device_id,
            'device_name': self.device_name,
            'schedule_entries': [e.to_dict() for e in self.schedule_entries],
            'total_energy_kwh': self.total_energy_kwh,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'DeviceSchedule':
        entries = [ScheduleEntry.from_dict(e) for e in data.get('schedule_entries', [])]
        return cls(
            device_id=data.get('device_id', ''),
            device_name=data.get('device_name', ''),
            schedule_entries=entries,
            total_energy_kwh=float(data.get('total_energy_kwh', 0.0)),
        )


@dataclass
class OptimizationResult:
    timestamp: datetime = field(default_factory=datetime.now)
    optimization_type: str = ''
    time_step_minutes: int = 30

    pv_forecast: List[TimeseriesPoint] = field(default_factory=list)
    load_forecast: List[TimeseriesPoint] = field(default_factory=list)
    grid_forecast: List[TimeseriesPoint] = field(default_factory=list)
    battery_soc_forecast: List[TimeseriesPoint] = field(default_factory=list)
    battery_power_forecast: List[TimeseriesPoint] = field(default_factory=list)
    load_cost_forecast: List[TimeseriesPoint] = field(default_factory=list)
    prod_price_forecast: List[TimeseriesPoint] = field(default_factory=list)

    device_schedules: Dict[str, DeviceSchedule] = field(default_factory=dict)
    device_power_forecasts: Dict[str, List[TimeseriesPoint]] = field(default_factory=dict)

    total_cost_eur: float = 0.0
    total_grid_import_kwh: float = 0.0
    total_grid_export_kwh: float = 0.0
    total_pv_production_kwh: float = 0.0
    total_self_consumption_kwh: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'optimization_type': self.optimization_type,
            'time_step_minutes': self.time_step_minutes,
            'pv_forecast': [p.to_dict() for p in self.pv_forecast],
            'load_forecast': [p.to_dict() for p in self.load_forecast],
            'grid_forecast': [p.to_dict() for p in self.grid_forecast],
            'battery_soc_forecast': [p.to_dict() for p in self.battery_soc_forecast],
            'battery_power_forecast': [p.to_dict() for p in self.battery_power_forecast],
            'load_cost_forecast': [p.to_dict() for p in self.load_cost_forecast],
            'prod_price_forecast': [p.to_dict() for p in self.prod_price_forecast],
            'device_schedules': {k: v.to_dict() for k, v in self.device_schedules.items()},
            'device_power_forecasts': {k: [p.to_dict() for p in v] for k, v in self.device_power_forecasts.items()},
            'total_cost_eur': self.total_cost_eur,
            'total_grid_import_kwh': self.total_grid_import_kwh,
            'total_grid_export_kwh': self.total_grid_export_kwh,
            'total_pv_production_kwh': self.total_pv_production_kwh,
            'total_self_consumption_kwh': self.total_self_consumption_kwh,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'OptimizationResult':
        ts = data.get('timestamp')
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif ts is None:
            ts = datetime.now()

        schedules = {}
        for device_id, sched_data in data.get('device_schedules', {}).items():
            schedules[device_id] = DeviceSchedule.from_dict(sched_data)

        device_power_forecasts = {}
        for device_id, points in data.get('device_power_forecasts', {}).items():
            device_power_forecasts[device_id] = [TimeseriesPoint.from_dict(p) for p in points]

        return cls(
            timestamp=ts,
            optimization_type=data.get('optimization_type', ''),
            time_step_minutes=int(data.get('time_step_minutes', 30)),
            pv_forecast=[TimeseriesPoint.from_dict(p) for p in data.get('pv_forecast', [])],
            load_forecast=[TimeseriesPoint.from_dict(p) for p in data.get('load_forecast', [])],
            grid_forecast=[TimeseriesPoint.from_dict(p) for p in data.get('grid_forecast', [])],
            battery_soc_forecast=[TimeseriesPoint.from_dict(p) for p in data.get('battery_soc_forecast', [])],
            battery_power_forecast=[TimeseriesPoint.from_dict(p) for p in data.get('battery_power_forecast', [])],
            load_cost_forecast=[TimeseriesPoint.from_dict(p) for p in data.get('load_cost_forecast', [])],
            prod_price_forecast=[TimeseriesPoint.from_dict(p) for p in data.get('prod_price_forecast', [])],
            device_schedules=schedules,
            device_power_forecasts=device_power_forecasts,
            total_cost_eur=float(data.get('total_cost_eur', 0.0)),
            total_grid_import_kwh=float(data.get('total_grid_import_kwh', 0.0)),
            total_grid_export_kwh=float(data.get('total_grid_export_kwh', 0.0)),
            total_pv_production_kwh=float(data.get('total_pv_production_kwh', 0.0)),
            total_self_consumption_kwh=float(data.get('total_self_consumption_kwh', 0.0)),
        )
