# fastapi/fixers/import_cleanup.py
import re
from typing import Dict, Any, Optional
from .base import BaseFixer


class ImportCleanupFixer(BaseFixer):
    """Fixer for removing Repository imports from API layer."""

    IMPORT_CLEANUP_RULES = [
        "API_REPO_IMPORT",
        "API_REPO_INSTANTIATION",
    ]

    def can_fix(self, violation: Dict[str, Any]) -> bool:
        """Check if this is a Repository import violation."""
        return violation.get("rule") in self.IMPORT_CLEANUP_RULES

    def fix(self, violation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Remove Repository imports from API layer.

        Strategy:
        1. Remove import lines containing 'repository' or 'repositories'
        2. Add TODO comment to inject Service instead
        """
        file_path = violation["file"]
        code_line = violation["code"]
        rule = violation["rule"]

        content = self._read_file(file_path)
        if not content:
            return None

        lines = content.split('\n')
        original_line = code_line.strip()

        # Find and remove the import line
        new_lines = []
        removed_line = None
        line_number = int(violation.get("line", 0))

        for i, line in enumerate(lines, start=1):
            if i == line_number or original_line in line:
                # This is the line to remove
                removed_line = line
                # Add TODO comment
                new_lines.append(f"# TODO: Remove Repository dependency. Use Service injection via Depends()")
                continue
            new_lines.append(line)

        if not removed_line:
            return None

        new_content = '\n'.join(new_lines)

        if self._write_file(file_path, new_content):
            return {
                "file": file_path,
                "line": violation["line"],
                "original": removed_line,
                "fixed": "# TODO: Remove Repository dependency. Use Service injection via Depends()",
                "description": "Removed Repository import from API layer",
                "action_required": "Inject Service via Depends() instead of using Repository directly"
            }

        return None
