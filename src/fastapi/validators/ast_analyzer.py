# fastapi/validators/ast_analyzer.py
"""
AST-based code analyzer for Python files.
Provides more accurate analysis than regex for complex patterns like:
- Multi-line function signatures
- Decorator-aware analysis
- Return type checking
"""
import ast
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.fastapi.constants import ROUTE_DECORATORS, API_ROUTER_NAMES

logger = logging.getLogger(__name__)


class ASTAnalyzer:
    """Analyzes Python files using Abstract Syntax Tree parsing."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()

    def analyze_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Analyze a single Python file for violations.

        Args:
            file_path: Path to the Python file

        Returns:
            List of violations found
        """
        violations = []

        try:
            source = Path(file_path).read_text(encoding='utf-8')
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            return violations
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return violations

        # Analyze the AST
        violations.extend(self._check_missing_return_types(tree, file_path, source))
        violations.extend(self._check_dict_return_types(tree, file_path, source))

        return violations

    def _check_missing_return_types(
        self,
        tree: ast.Module,
        file_path: str,
        source: str
    ) -> List[Dict[str, Any]]:
        """
        Check for functions missing return type annotations.

        Only checks:
        - Public functions (not starting with _)
        - Functions with route decorators (for API layer)
        - Service layer public methods
        """
        violations = []
        source_lines = source.splitlines()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Skip private/magic methods
            if node.name.startswith('_'):
                continue

            # Skip if has return type annotation
            if node.returns is not None:
                continue

            # Check if this is a relevant function
            is_route_handler = self._has_route_decorator(node)
            is_in_service = self._is_service_file(file_path)

            if not (is_route_handler or is_in_service):
                continue

            # Get the actual code line
            code_line = self._get_function_signature(node, source_lines)

            violations.append({
                "severity": "WARNING",
                "rule": "MISSING_RETURN_TYPE_AST",
                "layer": "services" if is_in_service else "api",
                "file": file_path,
                "line": str(node.lineno),
                "code": code_line,
                "message": f"Function '{node.name}' missing return type annotation.",
                "auto_fix": False,
                "decorators": self._get_decorator_names(node)
            })

        return violations

    def _check_dict_return_types(
        self,
        tree: ast.Module,
        file_path: str,
        source: str
    ) -> List[Dict[str, Any]]:
        """
        Check for functions returning Dict types instead of Pydantic models.
        Uses AST to accurately detect return type annotations.
        """
        violations = []
        source_lines = source.splitlines()

        if not self._is_service_file(file_path):
            return violations

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            if node.returns is None:
                continue

            # Check if return type contains Dict
            dict_info = self._check_for_dict_type(node.returns)
            if not dict_info:
                continue

            code_line = self._get_function_signature(node, source_lines)

            violations.append({
                "severity": "CRITICAL",
                "rule": f"SERVICE_{dict_info['type']}_AST",
                "layer": "services",
                "file": file_path,
                "line": str(node.lineno),
                "code": code_line,
                "message": f"Service returns {dict_info['description']}. Use Pydantic BaseModel instead.",
                "auto_fix": True,
                "return_type_node": dict_info
            })

        return violations

    def _has_route_decorator(self, node: ast.FunctionDef) -> bool:
        """Check if function has a FastAPI route decorator."""
        for decorator in node.decorator_list:
            decorator_name = self._get_decorator_name(decorator)
            if decorator_name:
                # Check for @router.get, @app.post, etc.
                parts = decorator_name.lower().split('.')
                if len(parts) >= 2:
                    if parts[0] in API_ROUTER_NAMES and parts[1] in ROUTE_DECORATORS:
                        return True
                # Check for direct @get, @post (less common)
                if parts[-1] in ROUTE_DECORATORS:
                    return True
        return False

    def _get_decorator_name(self, decorator: ast.expr) -> Optional[str]:
        """Extract decorator name from AST node."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            parts = []
            node = decorator
            while isinstance(node, ast.Attribute):
                parts.append(node.attr)
                node = node.value
            if isinstance(node, ast.Name):
                parts.append(node.id)
            return '.'.join(reversed(parts))
        elif isinstance(decorator, ast.Call):
            return self._get_decorator_name(decorator.func)
        return None

    def _get_decorator_names(self, node: ast.FunctionDef) -> List[str]:
        """Get all decorator names for a function."""
        names = []
        for decorator in node.decorator_list:
            name = self._get_decorator_name(decorator)
            if name:
                names.append(name)
        return names

    def _is_service_file(self, file_path: str) -> bool:
        """Check if file is in the services layer."""
        path_lower = file_path.lower()
        return '/services/' in path_lower or '/service/' in path_lower

    def _is_api_file(self, file_path: str) -> bool:
        """Check if file is in the API layer."""
        path_lower = file_path.lower()
        return '/api/' in path_lower or '/routes/' in path_lower or '/routers/' in path_lower

    def _get_function_signature(
        self,
        node: ast.FunctionDef,
        source_lines: List[str]
    ) -> str:
        """
        Extract the full function signature including multi-line signatures.
        """
        start_line = node.lineno - 1  # 0-indexed

        # Find the end of signature (the colon)
        signature_lines = []
        for i in range(start_line, min(start_line + 20, len(source_lines))):
            line = source_lines[i]
            signature_lines.append(line)
            if ':' in line and not line.strip().startswith('#'):
                # Check if this colon ends the signature
                # (not inside a type annotation like Dict[str, int])
                bracket_count = 0
                for char in ''.join(signature_lines):
                    if char in '([{':
                        bracket_count += 1
                    elif char in ')]}':
                        bracket_count -= 1

                if bracket_count == 0:
                    break

        signature = ' '.join(line.strip() for line in signature_lines)
        # Truncate if too long
        if len(signature) > 120:
            signature = signature[:117] + '...'
        return signature

    def _check_for_dict_type(self, return_node: ast.expr) -> Optional[Dict[str, Any]]:
        """
        Check if return type annotation contains Dict.

        Returns dict with type info if Dict found, None otherwise.
        """
        if return_node is None:
            return None

        # Direct Dict[str, Any] or dict[str, Any]
        if isinstance(return_node, ast.Subscript):
            type_name = self._get_type_name(return_node.value)
            if type_name and type_name.lower() == 'dict':
                return {
                    "type": "DICT_RETURN_BASIC",
                    "description": "Dict[str, Any]"
                }

        # Check for Optional[Dict[...]]
        if isinstance(return_node, ast.Subscript):
            type_name = self._get_type_name(return_node.value)
            if type_name == 'Optional':
                inner = return_node.slice
                if isinstance(inner, ast.Subscript):
                    inner_type = self._get_type_name(inner.value)
                    if inner_type and inner_type.lower() == 'dict':
                        return {
                            "type": "OPTIONAL_DICT",
                            "description": "Optional[Dict[...]]"
                        }

        # Check for List[Dict[...]]
        if isinstance(return_node, ast.Subscript):
            type_name = self._get_type_name(return_node.value)
            if type_name == 'List' or type_name == 'list':
                inner = return_node.slice
                if isinstance(inner, ast.Subscript):
                    inner_type = self._get_type_name(inner.value)
                    if inner_type and inner_type.lower() == 'dict':
                        return {
                            "type": "LIST_DICT_RETURN",
                            "description": "List[Dict[...]]"
                        }

        # Check for Union types containing Dict
        if isinstance(return_node, ast.Subscript):
            type_name = self._get_type_name(return_node.value)
            if type_name == 'Union':
                if isinstance(return_node.slice, ast.Tuple):
                    for elt in return_node.slice.elts:
                        if self._check_for_dict_type(elt):
                            return {
                                "type": "UNION_DICT",
                                "description": "Union[..., Dict[...]]"
                            }

        # Python 3.10+ union syntax: Dict[...] | None
        if isinstance(return_node, ast.BinOp) and isinstance(return_node.op, ast.BitOr):
            left_dict = self._check_for_dict_type(return_node.left)
            right_dict = self._check_for_dict_type(return_node.right)
            if left_dict or right_dict:
                return {
                    "type": "UNION_DICT",
                    "description": "Dict[...] | ..."
                }

        return None

    def _get_type_name(self, node: ast.expr) -> Optional[str]:
        """Extract type name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return None


class ServiceLayerAnalyzer(ASTAnalyzer):
    """Specialized analyzer for service layer files."""

    def analyze_services(self, services_glob: str) -> List[Dict[str, Any]]:
        """
        Analyze all service files matching the glob pattern.

        Args:
            services_glob: Glob pattern for service files

        Returns:
            List of all violations found
        """
        from glob import glob

        all_violations = []
        pattern = str(self.project_path / services_glob)

        for file_path in glob(pattern, recursive=True):
            if '__pycache__' in file_path or '.venv' in file_path:
                continue
            violations = self.analyze_file(file_path)
            all_violations.extend(violations)

        return all_violations


class APILayerAnalyzer(ASTAnalyzer):
    """Specialized analyzer for API layer files."""

    def analyze_api_routes(self, api_glob: str) -> List[Dict[str, Any]]:
        """
        Analyze all API route files matching the glob pattern.

        Args:
            api_glob: Glob pattern for API files

        Returns:
            List of all violations found
        """
        from glob import glob

        all_violations = []
        pattern = str(self.project_path / api_glob)

        for file_path in glob(pattern, recursive=True):
            if '__pycache__' in file_path or '.venv' in file_path:
                continue
            violations = self._analyze_api_file(file_path)
            all_violations.extend(violations)

        return all_violations

    def _analyze_api_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Analyze a single API file for route-specific violations."""
        violations = []

        try:
            source = Path(file_path).read_text(encoding='utf-8')
            tree = ast.parse(source, filename=file_path)
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return violations

        source_lines = source.splitlines()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Only check functions with route decorators
            if not self._has_route_decorator(node):
                continue

            # Check for missing return type
            if node.returns is None:
                code_line = self._get_function_signature(node, source_lines)
                decorators = self._get_decorator_names(node)

                violations.append({
                    "severity": "WARNING",
                    "rule": "API_MISSING_RETURN_TYPE_AST",
                    "layer": "api",
                    "file": file_path,
                    "line": str(node.lineno),
                    "code": code_line,
                    "message": f"API endpoint '{node.name}' missing return type annotation. "
                               f"Decorators: {', '.join(decorators)}",
                    "auto_fix": False,
                    "decorators": decorators
                })

        return violations
