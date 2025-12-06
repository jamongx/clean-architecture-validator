# fastapi/fixers/backup.py
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

logger = logging.getLogger(__name__)


class BackupManager:
    """Manages file backups before applying fixes."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()
        self.backup_dir = self.project_path / ".clean-arch-backups"
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backed_up_files: Set[str] = set()

    def create_backup(self, file_path: str) -> Optional[str]:
        """
        Create a backup of the file before modification.

        Args:
            file_path: Absolute path to the file to backup

        Returns:
            Path to backup file if successful, None otherwise
        """
        file_path = Path(file_path).resolve()

        # Skip if already backed up in this session
        if str(file_path) in self.backed_up_files:
            return None

        if not file_path.exists():
            return None

        # Create backup directory structure
        try:
            # Get relative path from project root
            try:
                rel_path = file_path.relative_to(self.project_path)
            except ValueError:
                # File is outside project, use absolute path structure
                rel_path = Path(str(file_path).lstrip('/'))

            # Create timestamped backup path
            backup_path = self.backup_dir / self.timestamp / rel_path
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(file_path, backup_path)

            # Mark as backed up
            self.backed_up_files.add(str(file_path))

            return str(backup_path)

        except PermissionError as e:
            logger.error(f"Permission denied creating backup for {file_path}: {e}")
            return None
        except OSError as e:
            logger.error(f"OS error creating backup for {file_path}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error creating backup for {file_path}: {e}")
            return None

    def restore_backup(self, backup_path: str, original_path: str) -> bool:
        """
        Restore a file from backup.

        Args:
            backup_path: Path to backup file
            original_path: Path where to restore the file

        Returns:
            True if restored successfully
        """
        try:
            backup_file = Path(backup_path)
            original_file = Path(original_path)

            if not backup_file.exists():
                return False

            # Restore file
            original_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_file, original_file)

            return True

        except Exception:
            return False

    def list_backups(self) -> list:
        """List all backup sessions."""
        if not self.backup_dir.exists():
            return []

        sessions = []
        for session_dir in sorted(self.backup_dir.iterdir(), reverse=True):
            if session_dir.is_dir():
                files = list(session_dir.rglob("*"))
                files = [f for f in files if f.is_file()]
                sessions.append({
                    "timestamp": session_dir.name,
                    "path": str(session_dir),
                    "file_count": len(files)
                })

        return sessions

    def clean_old_backups(self, keep_latest: int = 5) -> int:
        """
        Remove old backup sessions, keeping only the latest N.

        Args:
            keep_latest: Number of latest backups to keep

        Returns:
            Number of backup sessions removed
        """
        if not self.backup_dir.exists():
            return 0

        sessions = sorted(self.backup_dir.iterdir(), reverse=True)
        removed = 0

        for session_dir in sessions[keep_latest:]:
            if session_dir.is_dir():
                try:
                    shutil.rmtree(session_dir)
                    removed += 1
                except Exception:
                    pass

        return removed
