# core/base.py
import abc
import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from .constants import DEFAULT_SCORE_CONFIG
from .models import ValidationResult, Violation, ScoreSummary, Severity

logger = logging.getLogger(__name__)

class FrameworkValidator(abc.ABC):
    """Abstract base class for a framework-specific architecture validator."""

    def __init__(self, project_path: str, verbose: bool = False):
        self.project_path = Path(project_path).resolve()
        self.verbose = verbose
        if not self.project_path.exists():
            raise FileNotFoundError(f"❌ Error: Path '{self.project_path}' does not exist.")
        self.config = self._load_config()

    def _check_dependencies(self):
        """Check if required command-line tools are installed."""
        if not shutil.which("rg"):
            raise RuntimeError(
                "❌ 'rg' (ripgrep) not found.\n"
                "Install: sudo apt install ripgrep (Ubuntu/Debian) or brew install ripgrep (macOS)"
            )

    @property
    @abc.abstractmethod
    def default_config(self) -> Dict[str, Any]:
        """Return the default configuration for the specific framework."""
        pass

    def _load_config(self) -> dict:
        """Load .clean-arch.json from project root or use defaults."""
        config_file = self.project_path / ".clean-arch.json"

        # Start with default config
        config = self.default_config.copy()

        if config_file.exists():
            try:
                with open(config_file) as f:
                    user_config = json.load(f)
                    # Update config with user-provided values
                    for key in ["paths", "exclude", "score", "rules"]:
                        if key in user_config:
                            config[key] = user_config[key]
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in {config_file}, using defaults")

        # Ensure score config exists if not provided
        if "score" not in config:
            config["score"] = DEFAULT_SCORE_CONFIG

        return config

    def _run_rg(self, regex: str, glob: str) -> List[Dict]:
        """Run ripgrep and return structured findings."""
        cmd = ["rg", regex, "-g", glob, "-n", "--no-heading", "--with-filename", str(self.project_path)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
            findings = []
            if result.stdout:
                for line in result.stdout.splitlines():
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        findings.append({"file": parts[0].strip(), "line": parts[1], "code": parts[2].strip()})
            return findings
        except Exception as e:
            logger.error(f"Error running ripgrep: {e}")
            return []

    def _calculate_score(self, violations: List[Dict]) -> Dict:
        """Calculate architecture score based on violation severity from config."""
        score_config = self.config.get("score", DEFAULT_SCORE_CONFIG)
        initial_score = score_config.get("initial_score", 100)
        deductions = score_config.get("deductions", {})
        grades = score_config.get("grades", {})

        score = initial_score
        counts = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}

        for v in violations:
            severity = v.get("severity", "INFO")
            if severity in counts:
                counts[severity] += 1

            deduction = deductions.get(severity, 0)
            score -= deduction

        score = max(0, score)

        # Determine Grade
        if score >= grades.get("A", 90):
            grade, status = "A", "Excellent"
        elif score >= grades.get("B", 80):
            grade, status = "B", "Good"
        elif score >= grades.get("C", 70):
            grade, status = "C", "Fair"
        else:
            grade, status = "F", "Failing"

        return {"score": score, "grade": grade, "status": status, "counts": counts}

    def _build_validation_result(
        self,
        violations: List[Dict],
        framework: str
    ) -> ValidationResult:
        """
        Build a ValidationResult from raw violation dicts.

        Args:
            violations: List of violation dictionaries
            framework: Framework name (fastapi, springboot, react)

        Returns:
            Structured ValidationResult object
        """
        score_info = self._calculate_score(violations)

        # Convert dict violations to Violation models
        violation_models = []
        for v in violations:
            try:
                violation_models.append(Violation(
                    severity=Severity(v.get("severity", "INFO")),
                    rule=v.get("rule", "UNKNOWN"),
                    layer=v.get("layer", "unknown"),
                    file=v.get("file", ""),
                    line=str(v.get("line", "0")),
                    code=v.get("code", ""),
                    message=v.get("message", ""),
                    auto_fix=v.get("auto_fix", False),
                    decorators=v.get("decorators"),
                ))
            except Exception as e:
                logger.warning(f"Failed to convert violation to model: {e}")

        return ValidationResult(
            project_path=str(self.project_path),
            framework=framework,
            violations=violation_models,
            score=score_info["score"],
            grade=score_info["grade"],
            status=score_info["status"],
            counts=ScoreSummary(
                CRITICAL=score_info["counts"]["CRITICAL"],
                WARNING=score_info["counts"]["WARNING"],
                INFO=score_info["counts"]["INFO"],
            ),
        )

    @abc.abstractmethod
    def validate(self) -> ValidationResult:
        """Run all validation checks and return a structured result."""
        pass