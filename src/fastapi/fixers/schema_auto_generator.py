# fastapi/fixers/schema_auto_generator.py
import ast
import logging
import re
from pathlib import Path
from typing import Dict, Optional

from src.fastapi.constants import SQLALCHEMY_TO_PYTHON, EXCLUDED_METHOD_NAMES

logger = logging.getLogger(__name__)


class SchemaAutoGenerator:
    """Automatically generates Pydantic schema files based on function signatures."""

    # Default schemas directory patterns to try
    DEFAULT_SCHEMA_PATHS = [
        "src/schemas",
        "app/schemas",
        "schemas",
    ]

    def __init__(self, project_path: str, config: Optional[Dict] = None):
        self.project_path = Path(project_path).resolve()
        self.config = config or {}
        self.schemas_dir = self._resolve_schemas_dir()

    def _resolve_schemas_dir(self) -> Path:
        """
        Resolve the schemas directory from config or by detection.

        Priority:
        1. Config paths.schemas (if provided)
        2. Existing directory detection
        3. Default fallback
        """
        # 1. Try to get from config
        schemas_glob = self.config.get("paths", {}).get("schemas")
        if schemas_glob:
            schemas_dir = self._glob_to_directory(schemas_glob)
            if schemas_dir:
                logger.debug(f"Using schemas dir from config: {schemas_dir}")
                return schemas_dir

        # 2. Try to find existing schemas directory
        for path_pattern in self.DEFAULT_SCHEMA_PATHS:
            candidate = self.project_path / path_pattern
            if candidate.exists():
                logger.debug(f"Found existing schemas dir: {candidate}")
                return candidate

        # 3. Fallback to first default
        default_dir = self.project_path / self.DEFAULT_SCHEMA_PATHS[0]
        logger.debug(f"Using default schemas dir: {default_dir}")
        return default_dir

    def _glob_to_directory(self, glob_pattern: str) -> Optional[Path]:
        """
        Convert a glob pattern to a directory path.

        Examples:
            "src/*/schemas/*.py" -> "src/schemas" (first match)
            "app/schemas/**/*.py" -> "app/schemas"
        """
        # Remove file patterns
        parts = glob_pattern.replace("**", "").replace("*.py", "").split("/")
        parts = [p for p in parts if p and p != "*"]

        if not parts:
            return None

        # Try to find a matching directory
        # Handle patterns like "src/*/schemas" by trying common module names
        if "*" in glob_pattern:
            # Try to find first existing match
            from glob import glob
            pattern = str(self.project_path / glob_pattern.rsplit("/", 1)[0].replace("*", "*"))
            matches = glob(pattern)
            if matches:
                # Return first match that looks like a schemas directory
                for match in sorted(matches):
                    if "schema" in match.lower():
                        return Path(match)
                return Path(matches[0])

        # Direct path without wildcards
        candidate = self.project_path / "/".join(parts)
        return candidate

    def generate_schema_from_function(
        self,
        function_code: str,
        model_name: str,
        file_path: str
    ) -> Optional[str]:
        """
        Generate Pydantic schema by analyzing the function and related code.

        Args:
            function_code: The function definition code
            model_name: Name for the generated model (e.g., "UserResponse")
            file_path: Path to the file containing the function

        Returns:
            Path to generated schema file, or None if failed
        """
        # Try to infer fields from the function implementation
        fields = self._infer_fields_from_function(function_code, file_path)

        if not fields:
            # Fallback: create placeholder schema
            fields = {"id": "int", "data": "Any"}

        # Generate schema file
        schema_file = self._create_schema_file(model_name, fields)

        return schema_file

    def _infer_fields_from_function(
        self,
        function_code: str,
        file_path: str
    ) -> Dict[str, str]:
        """
        Attempt to infer schema fields from function implementation.

        Strategy:
        1. Look for dict construction: {"key": value, ...}
        2. Look for attribute access: obj.field_name
        3. Look for similar models in schemas/
        """
        fields = {}

        # Read the full file to get more context
        try:
            content = Path(file_path).read_text()
        except:
            content = function_code

        # Pattern 1: Find dict constructions like {"name": user.name, "email": user.email}
        dict_pattern = r'\{([^}]+)\}'
        dict_matches = re.findall(dict_pattern, function_code)

        for match in dict_matches:
            # Parse key-value pairs
            pairs = match.split(',')
            for pair in pairs:
                if ':' in pair:
                    key_part = pair.split(':')[0].strip()
                    # Extract key name (remove quotes)
                    key = key_part.strip('"\'')
                    if key and key.isidentifier():
                        # Default to Any, will be refined if we find type hints
                        fields[key] = "Any"

        # Pattern 2: Find attribute access patterns (obj.field_name)
        attr_pattern = r'(\w+)\.(\w+)'
        attr_matches = re.findall(attr_pattern, function_code)

        for obj_name, field_name in attr_matches:
            if field_name not in EXCLUDED_METHOD_NAMES:
                if field_name not in fields:
                    fields[field_name] = "Any"

        # Pattern 3: Look for type hints in related ORM models
        fields = self._refine_types_from_models(fields, content)

        return fields

    def _refine_types_from_models(
        self,
        fields: Dict[str, str],
        content: str
    ) -> Dict[str, str]:
        """Refine field types by looking at SQLAlchemy models in the code."""
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Look for model definitions
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name):
                                    field_name = target.id
                                    if field_name in fields:
                                        # Try to extract type from Column definition
                                        type_hint = self._extract_column_type(item.value)
                                        if type_hint:
                                            fields[field_name] = type_hint
        except:
            pass

        return fields

    def _extract_column_type(self, node: ast.expr) -> Optional[str]:
        """Extract Python type from SQLAlchemy Column definition."""
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "Column":
                if node.args:
                    first_arg = node.args[0]
                    if isinstance(first_arg, ast.Name):
                        return SQLALCHEMY_TO_PYTHON.get(first_arg.id, "Any")

        return None

    def _create_schema_file(
        self,
        model_name: str,
        fields: Dict[str, str]
    ) -> Optional[str]:
        """
        Create the actual schema file.

        Args:
            model_name: Name of the model class
            fields: Dict of field_name -> type_name

        Returns:
            Path to created file
        """
        # Ensure schemas directory exists
        self.schemas_dir.mkdir(parents=True, exist_ok=True)

        # Convert model name to filename (UserResponse -> user.py)
        filename = self._model_name_to_filename(model_name)
        schema_file = self.schemas_dir / filename

        # Check if file already exists
        if schema_file.exists():
            # Append to existing file instead of overwriting
            return self._append_to_schema_file(schema_file, model_name, fields)

        # Generate imports
        imports = set(["BaseModel"])
        for field_type in fields.values():
            if field_type == "datetime":
                imports.add("datetime")
            if "Optional" in field_type:
                imports.add("Optional")
            if "List" in field_type:
                imports.add("List")

        # Generate schema code
        schema_code = f'''# Auto-generated schema
from pydantic import BaseModel
from typing import Any, Optional, List
'''

        if "datetime" in imports:
            schema_code += "from datetime import datetime\n"

        schema_code += f'''

class {model_name}(BaseModel):
    """Auto-generated schema for {model_name}."""

'''

        for field_name, field_type in fields.items():
            schema_code += f"    {field_name}: {field_type}\n"

        schema_code += '''
    model_config = {"from_attributes": True}
'''

        # Write file
        try:
            schema_file.write_text(schema_code)
            logger.info(f"Schema file created: {schema_file}")
            return str(schema_file)
        except PermissionError as e:
            logger.error(f"Permission denied creating schema file {schema_file}: {e}")
            return None
        except OSError as e:
            logger.error(f"OS error creating schema file {schema_file}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error creating schema file {schema_file}: {e}")
            return None

    def _append_to_schema_file(
        self,
        schema_file: Path,
        model_name: str,
        fields: Dict[str, str]
    ) -> Optional[str]:
        """Append new model to existing schema file."""
        try:
            content = schema_file.read_text()

            # Check if model already exists
            if f"class {model_name}" in content:
                return str(schema_file)  # Already exists

            # Generate new model code
            model_code = f'''

class {model_name}(BaseModel):
    """Auto-generated schema for {model_name}."""

'''
            for field_name, field_type in fields.items():
                model_code += f"    {field_name}: {field_type}\n"

            model_code += '''
    model_config = {"from_attributes": True}
'''

            # Append to file
            schema_file.write_text(content + model_code)
            logger.info(f"Model {model_name} appended to schema file: {schema_file}")
            return str(schema_file)

        except PermissionError as e:
            logger.error(f"Permission denied appending to schema file {schema_file}: {e}")
            return None
        except OSError as e:
            logger.error(f"OS error appending to schema file {schema_file}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error appending to schema file {schema_file}: {e}")
            return None

    def _model_name_to_filename(self, model_name: str) -> str:
        """
        Convert model name to filename.

        Examples:
            UserResponse -> user.py
            ProductListResponse -> product.py
            OrderDetailResponse -> order.py
        """
        # Remove common suffixes
        base_name = model_name
        for suffix in ["Response", "Request", "Schema", "Model"]:
            if base_name.endswith(suffix):
                base_name = base_name[:-len(suffix)]
                break

        # Convert PascalCase to snake_case
        snake_case = re.sub(r'(?<!^)(?=[A-Z])', '_', base_name).lower()

        # Remove "list", "detail" etc. prefixes for grouping
        if snake_case.startswith("list_"):
            snake_case = snake_case[5:]
        if snake_case.startswith("detail_"):
            snake_case = snake_case[7:]

        return f"{snake_case}.py"
