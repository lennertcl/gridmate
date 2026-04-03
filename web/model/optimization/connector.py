from abc import ABC, abstractmethod
from typing import Optional

from web.model.optimization.models import OptimizationConfig, OptimizationResult


class OptimizerConnector(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def run_dayahead_optimization(self, config: OptimizationConfig) -> OptimizationResult:
        pass

    @abstractmethod
    def run_mpc_optimization(self, config: OptimizationConfig) -> OptimizationResult:
        pass

    @abstractmethod
    def get_latest_result(self) -> Optional[OptimizationResult]:
        pass
