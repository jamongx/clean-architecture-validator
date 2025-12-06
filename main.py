# main.py - Clean Architecture Validator MCP Server
import logging
from typing import List, Dict, Optional
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from src.core import Framework, ValidationResult, validator_registry, get_validator
from src.fastapi import generate_schema, FixRunner

# Import validators to trigger registration via decorators
import src.fastapi.validators  # noqa: F401 - registers FastApiValidator
import src.springboot.validators  # noqa: F401 - registers SpringBootValidator
import src.react.validators  # noqa: F401 - registers ReactValidator

# Configure logging
logger = logging.getLogger(__name__)

# Initialize FastMCP Server
mcp = FastMCP("Clean Architecture Validator")

@mcp.tool()
def validate_architecture(
    project_path: str,
    tech_stack: str = "FASTAPI",
    verbose: bool = False
) -> str:
    """
    Validate Clean Architecture compliance in a project.

    Args:
        project_path: Absolute path to project root
        tech_stack: 'FASTAPI', 'SPRINGBOOT', or 'REACT'
        verbose: Include detailed explanations and fix suggestions

    Returns:
        Detailed validation report with architecture score
    """
    # Get the appropriate validator based on tech_stack
    framework = tech_stack.lower()

    if not validator_registry.is_registered(framework):
        available = ", ".join(validator_registry.list_frameworks())
        logger.warning(f"Unknown framework requested: {tech_stack}")
        return f"❌ Error: Unknown framework '{tech_stack}'. Available: {available}"

    try:
        validator = get_validator(framework, project_path, verbose)
        result: ValidationResult = validator.validate()

        # Return formatted report string for MCP tool output
        return result.to_report(verbose=verbose)

    except FileNotFoundError as e:
        logger.error(f"Project path not found: {project_path}")
        return f"❌ Error: Project path not found - {e}"
    except RuntimeError as e:
        logger.error(f"Runtime error during validation: {e}")
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception(f"Unexpected error during validation: {e}")
        return f"❌ Unexpected error: {str(e)}"

@mcp.tool()
def fix_violations(
    project_path: str,
    dry_run: bool = True,
    violation_types: Optional[List[str]] = None
) -> str:
    """
    Auto-fix Clean Architecture violations.

    Args:
        project_path: Absolute path to project root
        dry_run: If True, only show what would be fixed (default: True)
        violation_types: List of violation types to fix (None = all auto-fixable)

    Returns:
        Fix report showing changes made or planned
    """
    root = Path(project_path).resolve()
    if not root.exists():
        logger.error(f"Project path does not exist: {root}")
        return f"❌ Error: Path '{root}' does not exist."

    try:
        # Run validator to get violations (currently only FastAPI supported)
        validator = get_validator("fastapi", str(root), verbose=False)
        result = validator.validate()

        if not result.violations:
            logger.info(f"No violations found in {root}")
            return "✅ No violations found! Nothing to fix."

        # Convert Violation models back to dicts for fixer compatibility
        violations_dicts = [v.model_dump() for v in result.violations]

        # Run fixer with validator's config (for proper path resolution)
        fixer = FixRunner(str(root), dry_run=dry_run, config=validator.config)
        report = fixer.run(violations_dicts, violation_types)

        return report

    except FileNotFoundError as e:
        logger.error(f"File not found during fix: {e}")
        return f"❌ Error: File not found - {e}"
    except PermissionError as e:
        logger.error(f"Permission denied: {e}")
        return f"❌ Error: Permission denied - {e}"
    except RuntimeError as e:
        logger.error(f"Runtime error during fix: {e}")
        return f"❌ Error: {e}"
    except Exception as e:
        logger.exception(f"Unexpected error during fix: {e}")
        return f"❌ Unexpected error: {str(e)}"

@mcp.tool()
def generate_schema_tool(
    class_name: str,
    fields: Dict[str, str],
    output_path: Optional[str] = None
) -> str:
    """
    Generate Pydantic BaseModel schema.

    Args:
        class_name: Name of the response/request class
        fields: Dict mapping field names to types
        output_path: Where to save the schema (optional)

    Returns:
        Generated schema code
    """
    return generate_schema(class_name, fields, output_path)

if __name__ == "__main__":
    mcp.run()