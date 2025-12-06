# src/core/registry.py
"""
Plugin registry for framework validators.

Allows dynamic registration and discovery of validators without
modifying main.py for each new framework.
"""
import logging
from typing import Dict, Type, Optional, List
from .base import FrameworkValidator
from .constants import Framework

logger = logging.getLogger(__name__)


class ValidatorRegistry:
    """
    Registry for framework validators.

    Usage:
        # Register a validator
        @validator_registry.register(Framework.FASTAPI)
        class FastApiValidator(FrameworkValidator):
            ...

        # Or register manually
        validator_registry.register(Framework.FASTAPI)(FastApiValidator)

        # Get a validator
        validator_class = validator_registry.get("fastapi")
        validator = validator_class(project_path, verbose)
    """

    def __init__(self):
        self._validators: Dict[str, Type[FrameworkValidator]] = {}

    def register(self, framework: Framework):
        """
        Decorator to register a validator class for a framework.

        Args:
            framework: Framework enum value

        Returns:
            Decorator function

        Example:
            @validator_registry.register(Framework.FASTAPI)
            class FastApiValidator(FrameworkValidator):
                ...
        """
        def decorator(validator_class: Type[FrameworkValidator]):
            framework_name = framework.value.lower()

            if framework_name in self._validators:
                logger.warning(
                    f"Overwriting existing validator for '{framework_name}': "
                    f"{self._validators[framework_name].__name__} -> {validator_class.__name__}"
                )

            self._validators[framework_name] = validator_class
            logger.debug(f"Registered validator: {framework_name} -> {validator_class.__name__}")

            return validator_class

        return decorator

    def get(self, framework: str) -> Optional[Type[FrameworkValidator]]:
        """
        Get validator class for a framework.

        Args:
            framework: Framework name (case-insensitive)

        Returns:
            Validator class or None if not found
        """
        return self._validators.get(framework.lower())

    def get_or_raise(self, framework: str) -> Type[FrameworkValidator]:
        """
        Get validator class for a framework, raising error if not found.

        Args:
            framework: Framework name (case-insensitive)

        Returns:
            Validator class

        Raises:
            ValueError: If framework is not registered
        """
        validator_class = self.get(framework)
        if validator_class is None:
            available = ", ".join(self.list_frameworks())
            raise ValueError(
                f"Unknown framework '{framework}'. Available: {available}"
            )
        return validator_class

    def list_frameworks(self) -> List[str]:
        """
        List all registered framework names.

        Returns:
            List of framework names
        """
        return list(self._validators.keys())

    def is_registered(self, framework: str) -> bool:
        """
        Check if a framework is registered.

        Args:
            framework: Framework name (case-insensitive)

        Returns:
            True if registered
        """
        return framework.lower() in self._validators

    def unregister(self, framework: str) -> bool:
        """
        Unregister a framework validator.

        Args:
            framework: Framework name (case-insensitive)

        Returns:
            True if was registered and removed, False otherwise
        """
        framework_lower = framework.lower()
        if framework_lower in self._validators:
            del self._validators[framework_lower]
            logger.debug(f"Unregistered validator: {framework_lower}")
            return True
        return False

    def clear(self):
        """Clear all registered validators."""
        self._validators.clear()
        logger.debug("Cleared all registered validators")


# Global registry instance
validator_registry = ValidatorRegistry()


def get_validator(
    framework: str,
    project_path: str,
    verbose: bool = False
) -> FrameworkValidator:
    """
    Convenience function to get and instantiate a validator.

    Args:
        framework: Framework name (e.g., "fastapi", "springboot", "react")
        project_path: Path to the project to validate
        verbose: Enable verbose output

    Returns:
        Instantiated validator

    Raises:
        ValueError: If framework is not registered
    """
    validator_class = validator_registry.get_or_raise(framework)
    return validator_class(project_path, verbose)
