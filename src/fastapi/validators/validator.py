# fastapi/validators/validator.py
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from src.core.base import FrameworkValidator
from src.core.constants import Framework
from src.core.models import ValidationResult
from src.core.registry import validator_registry
from .ast_analyzer import ServiceLayerAnalyzer, APILayerAnalyzer

logger = logging.getLogger(__name__)


@validator_registry.register(Framework.FASTAPI)
class FastApiValidator(FrameworkValidator):
    """Validator for FastAPI projects based on Python."""

    def __init__(self, project_path: str, verbose: bool = False):
        super().__init__(project_path, verbose)
        self.violations: List[Dict[str, Any]] = []

    @property
    def default_config(self) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "paths": {
                "api": "src/*/api/v*/*.py",
                "services": "src/*/services/*.py",
                "repositories": "src/*/repositories/*.py",
                "schemas": "src/*/schemas/*.py",
                "models": "src/*/models/*.py"
            },
            "exclude": [
                "**/tests/**",
                "**/__pycache__/**",
                "**/migrations/**",
                "**/.venv/**"
            ],
        }

    def _load_rules(self) -> Dict:
        """Load validation rules from JSON file."""
        rules_path = Path(__file__).parent.parent / "rules" / "rules.json"
        if not rules_path.exists():
             return {}
        try:
            with open(rules_path) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading rules: {e}")
            return {}

    def validate(self) -> ValidationResult:
        """
        Run all validation checks and return a structured result.

        Returns:
            ValidationResult with violations, score, and grade
        """
        self._check_dependencies()

        all_rules = self._load_rules()
        # Keys in JSON are uppercase, e.g. "FASTAPI"
        ruleset = all_rules.get(Framework.FASTAPI.value.upper(), {})
        self.violations = []

        # 1. Regex-based validation (for simple patterns)
        self._run_regex_validation(ruleset)

        # 2. AST-based validation (for complex patterns)
        self._run_ast_validation()

        # Remove duplicates (same file:line might be caught by both methods)
        self._deduplicate_violations()

        # Build and return structured result
        return self._build_validation_result(
            violations=self.violations,
            framework=Framework.FASTAPI.value
        )

    def _run_regex_validation(self, ruleset: Dict) -> None:
        """Run regex-based validation using ripgrep."""
        # Skip AST-handled rules to avoid duplicates
        ast_handled_rules = {
            'MISSING_RETURN_TYPE',  # Now handled by AST
        }

        for severity, checks in ruleset.get("patterns", {}).items():
            for rule_name, rule in checks.items():
                # Skip rules that are better handled by AST
                if rule_name in ast_handled_rules:
                    logger.debug(f"Skipping regex rule {rule_name} (handled by AST)")
                    continue

                target_layer = rule["layer"]
                layer_path_pattern = self.config.get("paths", {}).get(target_layer)

                if not layer_path_pattern:
                    continue

                for regex in rule["regex"]:
                    matches = self._run_rg(regex, layer_path_pattern)
                    for match in matches:
                        self.violations.append({
                            "severity": severity, "rule": rule_name, "layer": target_layer,
                            "file": match["file"], "line": match["line"],
                            "code": match["code"], "message": rule["msg"],
                            "auto_fix": rule.get("auto_fix", False)
                        })

    def _run_ast_validation(self) -> None:
        """Run AST-based validation for complex patterns."""
        paths = self.config.get("paths", {})

        # Analyze service layer
        services_pattern = paths.get("services")
        if services_pattern:
            service_analyzer = ServiceLayerAnalyzer(str(self.project_path))
            service_violations = service_analyzer.analyze_services(services_pattern)
            self.violations.extend(service_violations)
            logger.debug(f"AST found {len(service_violations)} service layer violations")

        # Analyze API layer
        api_pattern = paths.get("api")
        if api_pattern:
            api_analyzer = APILayerAnalyzer(str(self.project_path))
            api_violations = api_analyzer.analyze_api_routes(api_pattern)
            self.violations.extend(api_violations)
            logger.debug(f"AST found {len(api_violations)} API layer violations")

    def _deduplicate_violations(self) -> None:
        """Remove duplicate violations (same file:line:rule pattern)."""
        seen = set()
        unique_violations = []

        for v in self.violations:
            # Create a unique key for each violation
            key = (v['file'], v['line'], v['rule'].replace('_AST', ''))
            if key not in seen:
                seen.add(key)
                unique_violations.append(v)

        removed_count = len(self.violations) - len(unique_violations)
        if removed_count > 0:
            logger.debug(f"Removed {removed_count} duplicate violations")

        self.violations = unique_violations

    def get_violations(self) -> List[Dict[str, Any]]:
        """
        Get the list of violations found during validation as dictionaries.

        Note: For structured Violation objects, use validate().violations instead.
        """
        return self.violations