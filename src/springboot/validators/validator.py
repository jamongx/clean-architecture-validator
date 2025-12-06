# springboot/validators/validator.py
from typing import Dict, Any
from src.core.base import FrameworkValidator
from src.core.constants import Framework
from src.core.models import ValidationResult
from src.core.registry import validator_registry


@validator_registry.register(Framework.SPRINGBOOT)
class SpringBootValidator(FrameworkValidator):
    """Placeholder validator for Spring Boot projects."""

    @property
    def default_config(self) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "paths": {
                # Placeholder paths
                "controller": "src/main/java/**/controller/*.java",
                "service": "src/main/java/**/service/*.java",
                "repository": "src/main/java/**/repository/*.java",
            },
            "exclude": ["**/test/**", "**/target/**", "**/build/**"],
        }

    def validate(self) -> ValidationResult:
        """
        Run validation for Spring Boot projects.

        Note: Not yet implemented - returns empty result.
        """
        # Return empty result with perfect score (not implemented)
        return self._build_validation_result(
            violations=[],
            framework=Framework.SPRINGBOOT.value
        )