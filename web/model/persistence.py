"""
GridMate - Persistence Layer
Defines abstract repository interface and concrete JSON implementation
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict


class Repository(ABC):
    """Abstract base class defining the persistence interface"""

    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """Load all data from storage"""
        pass

    @abstractmethod
    def save(self, data: Dict[str, Any]) -> None:
        """Save all data to storage"""
        pass

    @abstractmethod
    def exists(self) -> bool:
        """Check if storage exists"""
        pass


class JsonRepository(Repository):
    """JSON file-based persistence implementation"""

    def __init__(self, file_path: str = 'web/data/settings.json'):
        """
        Initialize JSON repository

        Args:
            file_path: Path to JSON file for storage
        """
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        """Load data from JSON file"""
        if not self.exists():
            return {}

        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f'Error loading data file: {e}')
            return {}

    def save(self, data: Dict[str, Any]) -> None:
        """Save data to JSON file"""
        try:
            with open(self.file_path, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f'Error saving data file: {e}')

    def exists(self) -> bool:
        """Check if JSON file exists"""
        return self.file_path.exists()
