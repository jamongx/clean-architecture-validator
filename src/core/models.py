# core/models.py
"""
Pydantic models for Clean Architecture validation results.
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Violation severity levels."""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class Violation(BaseModel):
    """Represents a single Clean Architecture violation."""

    severity: Severity = Field(description="Severity level of the violation")
    rule: str = Field(description="Rule identifier (e.g., 'SERVICE_DICT_RETURN_BASIC')")
    layer: str = Field(description="Architectural layer where violation occurred")
    file: str = Field(description="File path where violation was found")
    line: str = Field(description="Line number of the violation")
    code: str = Field(description="The actual code that violates the rule")
    message: str = Field(description="Human-readable explanation of the violation")
    auto_fix: bool = Field(default=False, description="Whether this violation can be auto-fixed")
    decorators: Optional[List[str]] = Field(default=None, description="Decorators on the function (for AST analysis)")

    model_config = {"use_enum_values": True}


class ScoreSummary(BaseModel):
    """Score breakdown by severity."""

    critical: int = Field(default=0, alias="CRITICAL")
    warning: int = Field(default=0, alias="WARNING")
    info: int = Field(default=0, alias="INFO")

    model_config = {"populate_by_name": True}


class ValidationResult(BaseModel):
    """Complete validation result with violations and score."""

    project_path: str = Field(description="Path to the validated project")
    framework: str = Field(description="Framework type (fastapi, springboot, react)")
    violations: List[Violation] = Field(default_factory=list, description="List of violations found")
    score: int = Field(ge=0, le=100, description="Architecture score (0-100)")
    grade: str = Field(description="Letter grade (A, B, C, F)")
    status: str = Field(description="Human-readable status message")
    counts: ScoreSummary = Field(description="Violation counts by severity")

    model_config = {"use_enum_values": True}

    @property
    def is_passing(self) -> bool:
        """Check if the validation passed (grade C or better)."""
        return self.grade in ("A", "B", "C")

    @property
    def has_critical(self) -> bool:
        """Check if there are any critical violations."""
        return self.counts.critical > 0

    @property
    def total_violations(self) -> int:
        """Get total number of violations."""
        return len(self.violations)

    def get_violations_by_severity(self, severity: Severity) -> List[Violation]:
        """Get violations filtered by severity."""
        return [v for v in self.violations if v.severity == severity]

    def get_violations_by_layer(self, layer: str) -> List[Violation]:
        """Get violations filtered by layer."""
        return [v for v in self.violations if v.layer == layer]

    def get_auto_fixable(self) -> List[Violation]:
        """Get violations that can be auto-fixed."""
        return [v for v in self.violations if v.auto_fix]

    def to_report(self, verbose: bool = False) -> str:
        """
        Generate a formatted string report.

        Args:
            verbose: Include detailed information if True

        Returns:
            Formatted report string
        """
        lines = [
            f"Clean Architecture Validation Results for {self.framework.upper()}",
            f"Project: {self.project_path}",
            "-" * 60,
        ]

        if not self.violations:
            lines.append("\nNo violations found! Excellent job!")
        else:
            for v in self.violations:
                icon = {"CRITICAL": "[X]", "WARNING": "[!]", "INFO": "[i]"}.get(v.severity, "[?]")
                lines.append(f"\n{icon} {v.severity} in {v.layer} layer ({v.rule})")
                lines.append(f"  File: {v.file}:{v.line}")
                lines.append(f"  Code: {v.code}")
                if verbose:
                    lines.append(f"  Suggestion: {v.message}")
                    if v.auto_fix:
                        lines.append(f"  Auto-fix: Available")

        lines.extend([
            "\n" + "-" * 60,
            "Summary",
            f"  - CRITICAL: {self.counts.critical}",
            f"  - WARNING: {self.counts.warning}",
            f"  - INFO: {self.counts.info}",
            f"\nArchitecture Score: {self.score}/100 (Grade {self.grade}) - {self.status}"
        ])

        return "\n".join(lines)


class FixResult(BaseModel):
    """Result of applying a single fix."""

    file: str = Field(description="File that was modified")
    line: str = Field(description="Line number that was fixed")
    original: str = Field(description="Original code")
    fixed: str = Field(description="Fixed code")
    description: str = Field(description="Description of the fix")
    action_required: Optional[str] = Field(default=None, description="Additional action needed")
    schema_generated: Optional[str] = Field(default=None, description="Path to generated schema file")


class FixReport(BaseModel):
    """Complete fix report."""

    project_path: str = Field(description="Path to the project")
    dry_run: bool = Field(description="Whether this was a dry run")
    total_violations: int = Field(description="Total number of violations")
    auto_fixable: int = Field(description="Number of auto-fixable violations")
    fixes_applied: List[FixResult] = Field(default_factory=list, description="List of applied fixes")
    manual_required: List[Violation] = Field(default_factory=list, description="Violations requiring manual review")
    backup_location: Optional[str] = Field(default=None, description="Backup directory path")

    def to_report(self) -> str:
        """Generate a formatted string report."""
        mode = "DRY RUN" if self.dry_run else "LIVE MODE"
        lines = [
            f"Auto-fix Report ({mode})",
            "-" * 60,
            f"\nProject: {self.project_path}",
            f"\nSummary:",
            f"  - Total Violations: {self.total_violations}",
            f"  - Auto-fixable: {self.auto_fixable}",
            f"  - Manual Review Required: {len(self.manual_required)}",
            f"  - Fixes Applied: {len(self.fixes_applied)}",
        ]

        if self.backup_location:
            lines.append(f"\nBackups Created: {self.backup_location}")

        if self.fixes_applied:
            lines.append(f"\nApplied Fixes ({len(self.fixes_applied)}):")
            lines.append("-" * 60)
            for i, fix in enumerate(self.fixes_applied, 1):
                lines.append(f"\n{i}. {fix.file}:{fix.line}")
                lines.append(f"   Description: {fix.description}")
                lines.append(f"   Original: {fix.original[:80]}")
                lines.append(f"   Fixed: {fix.fixed[:80]}")
                if fix.action_required:
                    lines.append(f"   Action Required: {fix.action_required}")

        if self.manual_required:
            lines.append(f"\nManual Review Required ({len(self.manual_required)}):")
            for i, v in enumerate(self.manual_required[:5], 1):
                lines.append(f"\n{i}. {v.file}:{v.line}")
                lines.append(f"   Rule: {v.rule}")
                lines.append(f"   Message: {v.message}")
            if len(self.manual_required) > 5:
                lines.append(f"\n   ... and {len(self.manual_required) - 5} more")

        if self.dry_run:
            lines.extend([
                "\n" + "-" * 60,
                "This was a DRY RUN. No files were modified.",
                "Run with dry_run=False to apply changes."
            ])

        return "\n".join(lines)
