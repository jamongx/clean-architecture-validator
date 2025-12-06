# fastapi/fixers/base.py
import abc
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from .backup import BackupManager

logger = logging.getLogger(__name__)


class BaseFixer(abc.ABC):
    """Abstract base class for fixing Clean Architecture violations."""

    def __init__(self, project_path: str, dry_run: bool = True, backup_manager: Optional['BackupManager'] = None):
        self.project_path = Path(project_path).resolve()
        self.dry_run = dry_run
        self.fixes_applied: List[Dict[str, Any]] = []
        self.backup_manager = backup_manager or BackupManager(str(self.project_path))

    @abc.abstractmethod
    def can_fix(self, violation: Dict[str, Any]) -> bool:
        """
        Determine if this fixer can handle the given violation.

        Args:
            violation: Violation dict with keys: severity, rule, layer, file, line, code, message

        Returns:
            True if this fixer can handle this violation type
        """
        pass

    @abc.abstractmethod
    def fix(self, violation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Apply fix for the given violation.

        Args:
            violation: Violation dict to fix

        Returns:
            Dict with fix details if successful, None if failed
            Format: {"file": str, "original": str, "fixed": str, "description": str}
        """
        pass

    def apply_fixes(self, violations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply fixes to all violations this fixer can handle.

        Args:
            violations: List of violations from validator

        Returns:
            List of applied fixes
        """
        applied = []
        for violation in violations:
            if self.can_fix(violation):
                fix_result = self.fix(violation)
                if fix_result:
                    applied.append(fix_result)
                    self.fixes_applied.append(fix_result)
        return applied

    def _read_file(self, file_path: str) -> Optional[str]:
        """Read file contents safely."""
        try:
            return Path(file_path).read_text()
        except Exception:
            return None

    def _write_file(self, file_path: str, content: str) -> bool:
        """Write file contents safely (respects dry_run and creates backup)."""
        if self.dry_run:
            return True  # Simulate success in dry run mode

        try:
            # Create backup before modifying
            backup_path = self.backup_manager.create_backup(file_path)
            if backup_path:
                logger.info(f"Backup created: {backup_path}")

            # Write new content
            Path(file_path).write_text(content)
            return True
        except PermissionError as e:
            logger.error(f"Permission denied writing to {file_path}: {e}")
            return False
        except OSError as e:
            logger.error(f"OS error writing to {file_path}: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error writing to {file_path}: {e}")
            return False
