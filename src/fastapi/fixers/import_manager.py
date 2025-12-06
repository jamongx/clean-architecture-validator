# fastapi/fixers/import_manager.py
import ast
from pathlib import Path
from typing import List, Set, Optional, Tuple


class ImportManager:
    """Manages automatic import addition and cleanup."""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.content = self.file_path.read_text() if self.file_path.exists() else ""
        self.tree: Optional[ast.Module] = None
        self.existing_imports: Set[Tuple[str, Optional[str]]] = set()

        if self.content:
            try:
                self.tree = ast.parse(self.content)
                self._analyze_imports()
            except SyntaxError:
                pass

    def _analyze_imports(self):
        """Analyze existing imports in the file."""
        if not self.tree:
            return

        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # ast.Import: import module [as alias]
                    self.existing_imports.add((alias.name, alias.asname))

            elif isinstance(node, ast.ImportFrom):
                # ast.ImportFrom: from module import name [as alias]
                module = node.module or ""
                for alias in node.names:
                    self.existing_imports.add((f"{module}.{alias.name}", alias.asname))

    def has_import(self, module: str, name: Optional[str] = None) -> bool:
        """
        Check if an import already exists.

        Args:
            module: Module name (e.g., "pydantic", "typing")
            name: Specific import name (e.g., "BaseModel", "List")

        Returns:
            True if import exists
        """
        if name:
            # Check: from module import name
            return (f"{module}.{name}", None) in self.existing_imports or \
                   (f"{module}.{name}", name) in self.existing_imports
        else:
            # Check: import module
            return (module, None) in self.existing_imports

    def add_import(self, module: str, names: List[str]) -> str:
        """
        Add import to file if not already present.

        Args:
            module: Module name (e.g., "pydantic")
            names: List of names to import (e.g., ["BaseModel", "Field"])

        Returns:
            Updated file content
        """
        # Filter out already imported names
        new_names = [name for name in names if not self.has_import(module, name)]

        if not new_names:
            return self.content  # All imports already exist

        # Create import statement
        import_line = f"from {module} import {', '.join(sorted(new_names))}\n"

        # Find insertion point (after existing imports)
        lines = self.content.split('\n')
        insert_pos = 0
        last_import_line = -1

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('import ') or stripped.startswith('from '):
                last_import_line = i
            elif stripped and not stripped.startswith('#') and last_import_line >= 0:
                # Found first non-import, non-comment line after imports
                insert_pos = last_import_line + 1
                break

        if insert_pos == 0 and last_import_line >= 0:
            insert_pos = last_import_line + 1
        elif insert_pos == 0:
            # No existing imports, insert after docstring or at start
            insert_pos = self._find_after_docstring(lines)

        # Insert import
        lines.insert(insert_pos, import_line.rstrip())

        return '\n'.join(lines)

    def _find_after_docstring(self, lines: List[str]) -> int:
        """Find position after module docstring."""
        in_docstring = False
        docstring_quote = None

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check for docstring start
            if not in_docstring:
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    docstring_quote = stripped[:3]
                    if stripped.endswith(docstring_quote) and len(stripped) > 6:
                        # Single-line docstring
                        return i + 1
                    in_docstring = True
            else:
                # In docstring, check for end
                if docstring_quote in stripped:
                    return i + 1

        return 0  # No docstring found

    def remove_import(self, module: str, name: str) -> str:
        """
        Remove specific import from file.

        Args:
            module: Module name
            name: Import name to remove

        Returns:
            Updated file content
        """
        lines = self.content.split('\n')
        new_lines = []

        for line in lines:
            stripped = line.strip()

            # Check if this is the import to remove
            if stripped.startswith(f"from {module} import"):
                # Parse import names
                import_part = stripped.replace(f"from {module} import ", "")
                names = [n.strip() for n in import_part.split(',')]

                # Remove the specific name
                names = [n for n in names if n != name]

                if names:
                    # Keep line with remaining imports
                    new_lines.append(f"from {module} import {', '.join(names)}")
                # else: skip line (completely removed)
            else:
                new_lines.append(line)

        return '\n'.join(new_lines)

    def add_pydantic_imports(self, model_names: List[str]) -> str:
        """
        Add Pydantic imports needed for BaseModel schemas.

        Args:
            model_names: List of model names being used

        Returns:
            Updated file content
        """
        # Always need BaseModel
        needed_imports = ["BaseModel"]

        # Check content for common type hints
        if "Optional[" in self.content or "| None" in self.content:
            needed_imports.append("Optional")
        if "List[" in self.content:
            needed_imports.append("List")
        if "Field(" in self.content:
            needed_imports.append("Field")

        self.content = self.add_import("pydantic", needed_imports)

        # Add typing imports if needed
        typing_imports = []
        if "Dict[" in self.content:
            typing_imports.append("Dict")
        if "Any" in self.content:
            typing_imports.append("Any")
        if "Union[" in self.content:
            typing_imports.append("Union")

        if typing_imports:
            self.content = self.add_import("typing", typing_imports)

        # Re-parse after modifications
        try:
            self.tree = ast.parse(self.content)
            self._analyze_imports()
        except SyntaxError:
            pass

        return self.content
