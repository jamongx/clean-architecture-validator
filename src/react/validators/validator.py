# react/validators/validator.py
from typing import Dict, Any
from src.core.base import FrameworkValidator
from src.core.constants import Framework
from src.core.models import ValidationResult
from src.core.registry import validator_registry


@validator_registry.register(Framework.REACT)
class ReactValidator(FrameworkValidator):
    """Placeholder validator for React projects."""

    @property
    def default_config(self) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "paths": {
                # Placeholder paths
                "components": "src/components/**/*.tsx",
                "hooks": "src/hooks/**/*.ts",
                "pages": "src/pages/**/*.tsx",
            },
            "exclude": ["**/node_modules/**", "**/dist/**", "**/*.test.tsx"],
        }

    def validate(self) -> ValidationResult:
        """
        Run validation for React projects.

        Note: Not yet implemented - returns empty result.
        """
        # Return empty result with perfect score (not implemented)
        return self._build_validation_result(
            violations=[],
            framework=Framework.REACT.value
        )