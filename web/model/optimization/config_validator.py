from dataclasses import dataclass
from typing import Dict, List

from web.model.optimization.models import OptimizationConfig


@dataclass
class ConfigWarning:
    field: str = ''
    message: str = ''
    severity: str = 'warning'


class EmhassConfigValidator:
    def validate(self, gridmate_config: OptimizationConfig, emhass_config: Dict) -> List[ConfigWarning]:
        warnings = []

        deferrable_loads = gridmate_config.deferrable_loads if hasattr(gridmate_config, 'deferrable_loads') else []
        gm_loads = len(deferrable_loads)
        em_loads = emhass_config.get('number_of_deferrable_loads', 0)
        if gm_loads != em_loads:
            warnings.append(
                ConfigWarning(
                    field='number_of_deferrable_loads',
                    message=f'GridMate has {gm_loads} deferrable loads but EMHASS config has {em_loads}',
                    severity='error',
                )
            )

        return warnings
