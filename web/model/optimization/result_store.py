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
            self.base_path.mkdir(parents=True, exist_ok=True)
            with open(self.latest_file, 'w') as f:
                json.dump(result.to_dict(), f, indent=2)

            self.history_dir.mkdir(parents=True, exist_ok=True)
            date_str = result.timestamp.strftime('%Y-%m-%d')
            history_file = self.history_dir / f'{date_str}.json'

            history_entries = []
            if history_file.exists():
                try:
                    with open(history_file, 'r') as f:
                        history_entries = json.load(f)
                except (json.JSONDecodeError, IOError):
                    history_entries = []

            history_entries.append(result.to_dict())

            with open(history_file, 'w') as f:
                json.dump(history_entries, f, indent=2)

        except IOError as e:
            logger.error(f'Failed to save optimization result: {e}')

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
