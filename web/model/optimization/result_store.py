import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from web.model.optimization.models import OptimizationResult

logger = logging.getLogger(__name__)


class OptimizationResultStore:
    def __init__(self, base_path: str = 'data'):
        self.base_path = Path(base_path)
        self.latest_file = self.base_path / 'optimization_latest.json'
        self.history_dir = self.base_path / 'optimization_history'

    def save_result(self, result: OptimizationResult) -> None:
        try:
            result_dict = result.to_dict()
            self._write_latest_result(result_dict)
            history_entries = self._load_history_entries(result.timestamp)
            history_entries.append(result_dict)
            self._write_history_entries(result.timestamp, history_entries)

        except IOError as e:
            logger.error(f'Failed to save optimization result: {e}')

    def update_latest_result(self, result: OptimizationResult) -> bool:
        result_dict = result.to_dict()

        try:
            self._write_latest_result(result_dict)
            history_entries = self._load_history_entries(result.timestamp)
            replaced = False

            for index in range(len(history_entries) - 1, -1, -1):
                if history_entries[index].get('timestamp') == result_dict.get('timestamp'):
                    history_entries[index] = result_dict
                    replaced = True
                    break

            if not replaced:
                history_entries.append(result_dict)

            self._write_history_entries(result.timestamp, history_entries)
            return True
        except IOError as e:
            logger.error(f'Failed to update latest optimization result: {e}')
            return False

    def get_latest_result(self) -> Optional[OptimizationResult]:
        if not self.latest_file.exists():
            return None
        try:
            with open(self.latest_file, 'r') as f:
                data = json.load(f)
            return OptimizationResult.from_dict(data)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f'Failed to load latest optimization result: {e}')
            return None

    def cleanup_history(self, retention_days: int = 7) -> None:
        if not self.history_dir.exists():
            return
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')

        for history_file in self.history_dir.glob('*.json'):
            if history_file.stem < cutoff_str:
                try:
                    history_file.unlink()
                except IOError:
                    pass

    def _write_latest_result(self, result_dict: dict) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)
        with open(self.latest_file, 'w') as f:
            json.dump(result_dict, f, indent=2)

    def _load_history_entries(self, timestamp: datetime) -> list:
        history_file = self._get_history_file(timestamp)
        if not history_file.exists():
            return []

        try:
            with open(history_file, 'r') as f:
                loaded_entries = json.load(f)
                return loaded_entries if isinstance(loaded_entries, list) else []
        except (json.JSONDecodeError, IOError):
            return []

    def _write_history_entries(self, timestamp: datetime, history_entries: list) -> None:
        self.history_dir.mkdir(parents=True, exist_ok=True)
        history_file = self._get_history_file(timestamp)
        with open(history_file, 'w') as f:
            json.dump(history_entries, f, indent=2)

    def _get_history_file(self, timestamp: datetime) -> Path:
        date_str = timestamp.strftime('%Y-%m-%d')
        return self.history_dir / f'{date_str}.json'
