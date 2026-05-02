from datetime import datetime, time, timedelta
from typing import List, Tuple

from web.model.optimization.models import DeviceSchedule, OptimizationResult, ScheduleEntry, TimeseriesPoint
from web.model.optimization.result_store import OptimizationResultStore


class ManualScheduleError(ValueError):
    pass


class ManualScheduleService:
    def __init__(self, data_connector, result_store: OptimizationResultStore = None):
        self.data_connector = data_connector
        self.result_store = result_store or OptimizationResultStore()

    def update_device_window(
        self,
        device_id: str,
        window_index: int,
        start_time: str,
        end_time: str,
    ) -> OptimizationResult:
        result, schedule, timeline = self._load_context(device_id)

        if window_index < 0 or window_index >= len(schedule.schedule_entries):
            raise ManualScheduleError('Scheduled window does not exist')

        updated_entry = self._build_schedule_entry(
            start_time=start_time,
            end_time=end_time,
            horizon_points=timeline,
            time_step_minutes=result.time_step_minutes,
            power_w=schedule.schedule_entries[window_index].power_w,
        )

        entries = list(schedule.schedule_entries)
        entries[window_index] = updated_entry
        return self._apply_entries(result, schedule, timeline, entries)

    def add_device_window(self, device_id: str, start_time: str, end_time: str) -> OptimizationResult:
        result, schedule, timeline = self._load_context(device_id)
        power_w = self._resolve_default_power(device_id, schedule)

        new_entry = self._build_schedule_entry(
            start_time=start_time,
            end_time=end_time,
            horizon_points=timeline,
            time_step_minutes=result.time_step_minutes,
            power_w=power_w,
        )

        entries = list(schedule.schedule_entries)
        entries.append(new_entry)
        return self._apply_entries(result, schedule, timeline, entries)

    def delete_device_window(self, device_id: str, window_index: int) -> OptimizationResult:
        result, schedule, timeline = self._load_context(device_id)

        if window_index < 0 or window_index >= len(schedule.schedule_entries):
            raise ManualScheduleError('Scheduled window does not exist')

        entries = list(schedule.schedule_entries)
        del entries[window_index]
        return self._apply_entries(result, schedule, timeline, entries)

    def _load_context(self, device_id: str) -> Tuple[OptimizationResult, DeviceSchedule, List[TimeseriesPoint]]:
        result = self.result_store.get_latest_result()
        if result is None:
            raise ManualScheduleError('No optimization result available')

        device = self.data_connector.get_device(device_id)
        if device is None:
            raise ManualScheduleError('Device not found')

        if 'deferrable_load' not in device.get_all_type_ids():
            raise ManualScheduleError('Only deferrable load schedules can be edited from the dashboard')

        timeline = self._resolve_timeline(result, device_id)
        if not timeline:
            raise ManualScheduleError('No optimization timeline is available for this device')

        schedule = result.device_schedules.get(device_id)
        if schedule is None:
            schedule = DeviceSchedule(device_id=device_id, device_name=device.name)
            result.device_schedules[device_id] = schedule
        elif not schedule.device_name:
            schedule.device_name = device.name

        return result, schedule, timeline

    def _resolve_timeline(self, result: OptimizationResult, device_id: str) -> List[TimeseriesPoint]:
        candidate_series = [
            result.device_power_forecasts.get(device_id, []),
            result.load_forecast,
            result.grid_forecast,
            result.pv_forecast,
            result.battery_power_forecast,
        ]

        for series in candidate_series:
            if series:
                return [TimeseriesPoint(timestamp=point.timestamp, value=point.value) for point in series]

        return []

    def _resolve_default_power(self, device_id: str, schedule: DeviceSchedule) -> float:
        if schedule.schedule_entries:
            return schedule.schedule_entries[0].power_w

        device = self.data_connector.get_device(device_id)
        nominal_power_w = float(device.custom_parameters.get('opt_nominal_power', 0.0)) if device else 0.0
        if nominal_power_w <= 0:
            raise ManualScheduleError('Device has no nominal power configured for a new scheduled window')
        return nominal_power_w

    def _build_schedule_entry(
        self,
        start_time: str,
        end_time: str,
        horizon_points: List[TimeseriesPoint],
        time_step_minutes: int,
        power_w: float,
    ) -> ScheduleEntry:
        if not start_time or not end_time:
            raise ManualScheduleError('Start and end time are required')

        step_delta = timedelta(minutes=time_step_minutes)
        horizon_start = horizon_points[0].timestamp.replace(second=0, microsecond=0)
        horizon_end = horizon_points[-1].timestamp + step_delta

        start_dt = self._resolve_datetime(start_time, horizon_start, horizon_end)
        end_dt = self._resolve_datetime(end_time, horizon_start, horizon_end)

        if end_dt <= start_dt:
            raise ManualScheduleError('End time must be after start time')

        if not self._is_step_aligned(start_dt, time_step_minutes) or not self._is_step_aligned(
            end_dt, time_step_minutes
        ):
            raise ManualScheduleError(f'Times must align with the {time_step_minutes}-minute optimization step')

        if start_dt < horizon_start or end_dt > horizon_end:
            raise ManualScheduleError('Scheduled window must stay inside the current optimization horizon')

        return ScheduleEntry(
            start_time=start_dt,
            end_time=end_dt,
            power_w=power_w,
            is_active=True,
        )

    def _resolve_datetime(self, raw_time: str, horizon_start: datetime, horizon_end: datetime) -> datetime:
        parsed_time = self._parse_time(raw_time)
        candidate = datetime.combine(horizon_start.date(), parsed_time)

        if candidate < horizon_start and horizon_end.date() > horizon_start.date():
            candidate += timedelta(days=1)

        return candidate

    def _parse_time(self, raw_time: str) -> time:
        normalized = raw_time.strip()

        for fmt in ('%H:%M', '%H:%M:%S'):
            try:
                return datetime.strptime(normalized, fmt).time()
            except ValueError:
                continue

        raise ManualScheduleError('Invalid time format')

    def _is_step_aligned(self, value: datetime, time_step_minutes: int) -> bool:
        minutes_since_midnight = (value.hour * 60) + value.minute
        return value.second == 0 and value.microsecond == 0 and minutes_since_midnight % time_step_minutes == 0

    def _apply_entries(
        self,
        result: OptimizationResult,
        schedule: DeviceSchedule,
        timeline: List[TimeseriesPoint],
        entries: List[ScheduleEntry],
    ) -> OptimizationResult:
        normalized_entries = self._normalize_entries(entries)

        schedule.schedule_entries = normalized_entries
        schedule.total_energy_kwh = self._calculate_total_energy_kwh(normalized_entries)
        result.device_schedules[schedule.device_id] = schedule
        result.device_power_forecasts[schedule.device_id] = self._build_power_forecast(
            timeline=timeline,
            entries=normalized_entries,
        )

        return result

    def _normalize_entries(self, entries: List[ScheduleEntry]) -> List[ScheduleEntry]:
        active_entries = [entry for entry in entries if entry.is_active]
        active_entries.sort(key=lambda entry: entry.start_time)

        for index in range(len(active_entries) - 1):
            current_entry = active_entries[index]
            next_entry = active_entries[index + 1]
            if current_entry.end_time > next_entry.start_time:
                raise ManualScheduleError('Scheduled windows cannot overlap')

        return active_entries

    def _calculate_total_energy_kwh(self, entries: List[ScheduleEntry]) -> float:
        total_energy_kwh = 0.0

        for entry in entries:
            duration_hours = (entry.end_time - entry.start_time).total_seconds() / 3600
            total_energy_kwh += (entry.power_w / 1000.0) * duration_hours

        return total_energy_kwh

    def _build_power_forecast(
        self, timeline: List[TimeseriesPoint], entries: List[ScheduleEntry]
    ) -> List[TimeseriesPoint]:
        forecast = []

        for point in timeline:
            power_kw = 0.0

            for entry in entries:
                if entry.start_time <= point.timestamp < entry.end_time:
                    power_kw = entry.power_w / 1000.0
                    break

            forecast.append(TimeseriesPoint(timestamp=point.timestamp, value=power_kw))

        return forecast
