# fastapi/fixers/dict_to_model.py
import re
from typing import Dict, Any, Optional
from .base import BaseFixer
from .import_manager import ImportManager
from .schema_auto_generator import SchemaAutoGenerator


class DictToModelFixer(BaseFixer):
    """Fixer for converting Dict return types to Pydantic BaseModel."""

    DICT_RETURN_RULES = [
        "SERVICE_DICT_RETURN_BASIC",
        "SERVICE_LIST_DICT_RETURN",
        "SERVICE_OPTIONAL_DICT",
        "SERVICE_UNION_DICT",
        "SERVICE_NESTED_DICT",
    ]

    def __init__(
        self,
        project_path: str,
        dry_run: bool = True,
        auto_generate_schema: bool = True,
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(project_path, dry_run, **kwargs)
        self.auto_generate_schema = auto_generate_schema
        self.config = config or {}
        self.schema_generator = SchemaAutoGenerator(project_path, config=self.config)

    def can_fix(self, violation: Dict[str, Any]) -> bool:
        """Check if this is a Dict return type violation."""
        return violation.get("rule") in self.DICT_RETURN_RULES

    def fix(self, violation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert Dict return type to BaseModel.

        Strategy:
        1. Extract function name from code
        2. Infer appropriate model name (e.g., get_user → UserResponse)
        3. Replace Dict with inferred model name
        4. Add TODO comment to create the actual model
        """
        file_path = violation["file"]
        code_line = violation["code"]
        rule = violation["rule"]

        content = self._read_file(file_path)
        if not content:
            return None

        # Infer model name from function
        model_name = self._infer_model_name(code_line, rule)
        if not model_name:
            return None

        # Generate replacement based on rule type
        replacement = self._generate_replacement(code_line, model_name, rule)
        if not replacement:
            return None

        # Apply the fix
        new_content = content.replace(code_line, replacement)

        # Add necessary imports automatically
        import_mgr = ImportManager(file_path)
        import_mgr.content = new_content

        # Add import for the schema model (assuming it's in schemas/)
        # Note: This adds a TODO-style import that user needs to update
        new_content = import_mgr.add_import("typing", ["Optional", "List", "Dict", "Any"])

        # Auto-generate schema file if enabled and not in dry-run
        schema_file = None
        if self.auto_generate_schema and not self.dry_run:
            # Extract full function code for better inference
            function_code = self._extract_function_code(content, code_line)
            schema_file = self.schema_generator.generate_schema_from_function(
                function_code,
                model_name,
                file_path
            )

        if self._write_file(file_path, new_content):
            result = {
                "file": file_path,
                "line": violation["line"],
                "original": code_line,
                "fixed": replacement,
                "description": f"Replaced Dict return type with {model_name}",
            }

            if schema_file:
                result["action_required"] = f"Schema {model_name} created at {schema_file}. Add: from schemas import {model_name}"
                result["schema_generated"] = schema_file
            else:
                result["action_required"] = f"Create {model_name} Pydantic model in schemas/ and add: from schemas import {model_name}"

            return result

        return None

    def _extract_function_code(self, content: str, function_signature: str) -> str:
        """Extract full function code including body."""
        lines = content.split('\n')
        function_lines = []
        in_function = False
        indent_level = None

        for line in lines:
            # Find function start
            if function_signature.strip() in line:
                in_function = True
                indent_level = len(line) - len(line.lstrip())
                function_lines.append(line)
                continue

            if in_function:
                current_indent = len(line) - len(line.lstrip())

                # End of function: dedent or new function/class
                if line.strip() and current_indent <= indent_level:
                    break

                function_lines.append(line)

        return '\n'.join(function_lines)

    def _infer_model_name(self, code_line: str, rule: str) -> Optional[str]:
        """
        Infer appropriate model name from function name.

        Examples:
            get_user() → UserResponse
            list_products() → ProductResponse (in List[ProductResponse])
            create_order() → OrderResponse
        """
        # Extract function name
        match = re.search(r'def\s+(\w+)\s*\(', code_line)
        if not match:
            return None

        func_name = match.group(1)

        # Remove common prefixes
        for prefix in ['get_', 'fetch_', 'retrieve_', 'list_', 'create_', 'update_', 'delete_']:
            if func_name.startswith(prefix):
                func_name = func_name[len(prefix):]
                break

        # Convert snake_case to PascalCase
        parts = func_name.split('_')
        model_base = ''.join(word.capitalize() for word in parts)

        # Add Response suffix
        return f"{model_base}Response"

    def _generate_replacement(self, code_line: str, model_name: str, rule: str) -> Optional[str]:
        """Generate the replacement code based on rule type."""

        if rule == "SERVICE_DICT_RETURN_BASIC":
            # Dict[str, Any] → ModelResponse
            replacement = re.sub(
                r'->\s*(typing\.)?Dict\[str,\s*Any\]',
                f'-> {model_name}',
                code_line
            )
            replacement = re.sub(
                r'->\s*dict\[str,\s*Any\]',
                f'-> {model_name}',
                replacement
            )

        elif rule == "SERVICE_LIST_DICT_RETURN":
            # List[Dict[...]] → List[ModelResponse]
            replacement = re.sub(
                r'->\s*List\s*\[\s*Dict\[',
                f'-> List[{model_name}',
                code_line
            )
            # Close the brackets properly
            replacement = re.sub(r'Dict\[[^\]]+\]', model_name, replacement)

        elif rule == "SERVICE_OPTIONAL_DICT":
            # Optional[Dict[...]] → Optional[ModelResponse]
            replacement = re.sub(
                r'->\s*Optional\s*\[\s*Dict\[[^\]]+\]\s*\]',
                f'-> Optional[{model_name}]',
                code_line
            )
            # Python 3.10+ style: Dict[...] | None → ModelResponse | None
            replacement = re.sub(
                r'->\s*Dict\[[^\]]+\]\s*\|\s*None',
                f'-> {model_name} | None',
                replacement
            )

        elif rule == "SERVICE_UNION_DICT":
            # Union[..., Dict[...]] → Union[..., ModelResponse]
            replacement = re.sub(
                r'Dict\[[^\]]+\]',
                model_name,
                code_line
            )

        elif rule == "SERVICE_NESTED_DICT":
            # Tuple[..., Dict[...]] or Result[..., Dict[...]]
            replacement = re.sub(
                r'Dict\[[^\]]+\]',
                model_name,
                code_line
            )

        else:
            return None

        # Add TODO comment if not already present
        if replacement != code_line and 'TODO' not in replacement:
            replacement = f"{replacement}  # TODO: Create {model_name} in schemas/"

        return replacement if replacement != code_line else None
