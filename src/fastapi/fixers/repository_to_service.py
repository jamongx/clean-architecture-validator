# fastapi/fixers/repository_to_service.py
import re
from typing import Dict, Any, Optional
from .base import BaseFixer
from .import_manager import ImportManager


class RepositoryToServiceFixer(BaseFixer):
    """Fixer for refactoring Repository calls to use Service layer."""

    REPO_METHOD_RULES = [
        "API_REPO_METHOD_CALL",
    ]

    def can_fix(self, violation: Dict[str, Any]) -> bool:
        """Check if this is a Repository method call violation."""
        return violation.get("rule") in self.REPO_METHOD_RULES

    def fix(self, violation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Refactor Repository calls to use Service.

        Strategy:
        1. Identify repository method calls
        2. Replace with equivalent service method calls
        3. Add TODO comment for creating service method if needed
        """
        file_path = violation["file"]
        code_line = violation["code"]

        content = self._read_file(file_path)
        if not content:
            return None

        # Detect repository method pattern
        method_pattern = self._detect_repo_method(code_line)
        if not method_pattern:
            return None

        # Generate service equivalent
        service_replacement = self._generate_service_call(code_line, method_pattern)
        if not service_replacement:
            return None

        # Replace in content
        new_content = content.replace(code_line, service_replacement)

        # Add service import if needed
        import_mgr = ImportManager(file_path)
        import_mgr.content = new_content

        # Infer service name from file structure
        service_name = self._infer_service_name(file_path, method_pattern)
        if service_name:
            # Add placeholder import (user needs to adjust)
            new_content = import_mgr.content  # Use current content

        if self._write_file(file_path, new_content):
            return {
                "file": file_path,
                "line": violation["line"],
                "original": code_line,
                "fixed": service_replacement,
                "description": f"Replaced Repository call with Service call",
                "action_required": f"Ensure {service_name or 'Service'} is injected via Depends() and method exists"
            }

        return None

    def _detect_repo_method(self, code_line: str) -> Optional[Dict[str, str]]:
        """
        Detect repository method call pattern.

        Returns:
            Dict with 'object', 'method', 'args' if found
        """
        # Pattern: repo.get_by_id(user_id)
        # Pattern: repository.find_all()
        # Pattern: user_repo.create(user_data)

        patterns = [
            r'(\w*repo\w*)\.(\w+)\((.*)\)',  # repo.method(args)
            r'(\w*repository\w*)\.(\w+)\((.*)\)',  # repository.method(args)
        ]

        for pattern in patterns:
            match = re.search(pattern, code_line, re.IGNORECASE)
            if match:
                return {
                    "object": match.group(1),
                    "method": match.group(2),
                    "args": match.group(3)
                }

        return None

    def _generate_service_call(
        self,
        code_line: str,
        method_pattern: Dict[str, str]
    ) -> Optional[str]:
        """
        Generate service layer equivalent call.

        Args:
            code_line: Original code line
            method_pattern: Detected method pattern

        Returns:
            Replacement code with service call
        """
        obj_name = method_pattern["object"]
        method_name = method_pattern["method"]
        args = method_pattern["args"]

        # Replace repo object with service
        service_obj = obj_name.replace("repo", "service").replace("Repository", "Service")

        # Keep method name same (service should mirror repository interface)
        replacement = code_line.replace(
            f"{obj_name}.{method_name}({args})",
            f"{service_obj}.{method_name}({args})"
        )

        # Add TODO comment if not already present
        if "TODO" not in replacement and "//" not in replacement:
            replacement = f"{replacement}  # TODO: Ensure {service_obj}.{method_name}() exists in service layer"

        return replacement

    def _infer_service_name(
        self,
        file_path: str,
        method_pattern: Dict[str, str]
    ) -> Optional[str]:
        """
        Infer service name from repository object name.

        Examples:
            user_repo -> UserService
            product_repository -> ProductService
        """
        obj_name = method_pattern["object"]

        # Remove repo/repository suffix
        base_name = obj_name.replace("_repo", "").replace("_repository", "")
        base_name = base_name.replace("repo", "").replace("repository", "")

        # Convert to PascalCase
        parts = base_name.split('_')
        service_name = ''.join(word.capitalize() for word in parts if word)

        if service_name:
            return f"{service_name}Service"

        return "Service"
