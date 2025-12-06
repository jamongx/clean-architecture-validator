# fastapi/fixers/runner.py
from pathlib import Path
from typing import List, Dict, Any, Optional
from .base import BaseFixer
from .backup import BackupManager
from .dict_to_model import DictToModelFixer
from .import_cleanup import ImportCleanupFixer
from .repository_to_service import RepositoryToServiceFixer


class FixRunner:
    """Orchestrates multiple fixers to apply violations fixes."""

    def __init__(
        self,
        project_path: str,
        dry_run: bool = True,
        auto_generate_schema: bool = True,
        config: Optional[Dict[str, Any]] = None
    ):
        self.project_path = Path(project_path).resolve()
        self.dry_run = dry_run
        self.config = config or {}
        self.backup_manager = BackupManager(str(self.project_path))

        # Register all available fixers
        self.fixers: List[BaseFixer] = [
            DictToModelFixer(
                str(self.project_path),
                dry_run,
                auto_generate_schema=auto_generate_schema,
                config=self.config,
                backup_manager=self.backup_manager
            ),
            ImportCleanupFixer(
                str(self.project_path),
                dry_run,
                backup_manager=self.backup_manager
            ),
            RepositoryToServiceFixer(
                str(self.project_path),
                dry_run,
                backup_manager=self.backup_manager
            ),
        ]

    def run(self, violations: List[Dict[str, Any]], violation_types: Optional[List[str]] = None) -> str:
        """
        Apply fixes to violations.

        Args:
            violations: List of violations from validator
            violation_types: Optional list of specific violation types to fix

        Returns:
            Formatted report of fixes applied
        """
        # Filter violations if specific types requested
        if violation_types:
            violations = [v for v in violations if v.get("rule") in violation_types]

        # Filter only auto-fixable violations
        auto_fixable = [v for v in violations if v.get("auto_fix", False)]

        if not auto_fixable:
            return self._generate_report([], violations)

        # Apply fixes
        all_fixes = []
        for fixer in self.fixers:
            fixes = fixer.apply_fixes(auto_fixable)
            all_fixes.extend(fixes)

        return self._generate_report(all_fixes, violations)

    def _generate_report(self, fixes: List[Dict[str, Any]], violations: List[Dict[str, Any]]) -> str:
        """Generate a formatted report of applied fixes."""
        report = []

        mode = "DRY RUN" if self.dry_run else "LIVE MODE"
        report.append(f"🔧 Auto-fix Report ({mode})")
        report.append("━" * 60)
        report.append(f"\n📂 Project: {self.project_path}")

        if not violations:
            report.append("\n✅ No violations found!")
            return "\n".join(report)

        auto_fixable = [v for v in violations if v.get("auto_fix", False)]
        manual_required = [v for v in violations if not v.get("auto_fix", False)]

        report.append(f"\n📊 Summary:")
        report.append(f"  - Total Violations: {len(violations)}")
        report.append(f"  - Auto-fixable: {len(auto_fixable)}")
        report.append(f"  - Manual Review Required: {len(manual_required)}")
        report.append(f"  - Fixes Applied: {len(fixes)}")

        # Add backup info
        if not self.dry_run and self.backup_manager.backed_up_files:
            report.append(f"\n💾 Backups Created: {len(self.backup_manager.backed_up_files)}")
            report.append(f"   Location: {self.backup_manager.backup_dir / self.backup_manager.timestamp}")

        if fixes:
            report.append(f"\n✅ Applied Fixes ({len(fixes)}):")
            report.append("━" * 60)

            schema_files_created = []
            for i, fix in enumerate(fixes, 1):
                report.append(f"\n{i}. {fix['file']}:{fix['line']}")
                report.append(f"   Description: {fix['description']}")
                report.append(f"   Original:    {fix['original'][:80]}")
                report.append(f"   Fixed:       {fix['fixed'][:80]}")

                # Track schema files created
                if fix.get("schema_generated"):
                    schema_files_created.append(fix["schema_generated"])

                if fix.get("action_required"):
                    report.append(f"   ⚠️  Action Required: {fix['action_required']}")

            # Add schema files summary
            if schema_files_created:
                report.append(f"\n📄 Schema Files Generated ({len(schema_files_created)}):")
                for schema_file in schema_files_created:
                    report.append(f"   - {schema_file}")

        if manual_required:
            report.append(f"\n⚠️  Manual Review Required ({len(manual_required)}):")
            report.append("━" * 60)

            for i, v in enumerate(manual_required[:5], 1):  # Show first 5
                report.append(f"\n{i}. {v['file']}:{v['line']}")
                report.append(f"   Rule: {v['rule']}")
                report.append(f"   Message: {v['message']}")

            if len(manual_required) > 5:
                report.append(f"\n   ... and {len(manual_required) - 5} more")

        if self.dry_run:
            report.append("\n" + "━" * 60)
            report.append("💡 This was a DRY RUN. No files were modified.")
            report.append("   Run with dry_run=False to apply changes.")
        else:
            report.append("\n" + "━" * 60)
            report.append("✅ Changes have been applied to your files.")
            report.append("   Review the changes and test your application.")

        return "\n".join(report)
