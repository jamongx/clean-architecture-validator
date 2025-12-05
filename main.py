# main_improved.py - Improved MCP server implementation
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Clean Architecture Validator")

# ============================================================================
# Validation Rules Definition (Extended)
# ============================================================================

RULES = {
    "FASTAPI": {
        "files": "**/*.py",
        "patterns": {
            "CRITICAL": {
                # Category 1: Basic Dict Returns
                "SERVICE_DICT_RETURN_BASIC": {
                    "regex": [
                        r"->\s*(typing\.)?Dict\[str,\s*Any\]",
                        r"->\s*dict\[str,\s*Any\]",  # Python 3.9+
                    ],
                    "layer": "services",
                    "msg": "Service returns Dict[str, Any]. Use Pydantic BaseModel instead.",
                    "auto_fix": True
                },
                "SERVICE_LIST_DICT_RETURN": {
                    "regex": [
                        r"->\s*List\s*\[\s*Dict\[",
                        r"->\s*list\s*\[\s*dict\[",
                    ],
                    "layer": "services",
                    "msg": "Service returns List[Dict]. Use List[BaseModel] instead.",
                    "auto_fix": True
                },
                # Category 2: Extended Dict Returns (NEW)
                "SERVICE_OPTIONAL_DICT": {
                    "regex": [
                        r"->\s*Optional\s*\[\s*Dict\[",
                        r"->\s*Dict\[.*\]\s*\|\s*None",  # Python 3.10+
                    ],
                    "layer": "services",
                    "msg": "Service returns Optional[Dict]. Use Optional[BaseModel] instead.",
                    "auto_fix": True
                },
                "SERVICE_UNION_DICT": {
                    "regex": [
                        r"->\s*Union\s*\[.*Dict\[",
                        r"->\s*\w+\s*\|\s*Dict\[",
                    ],
                    "layer": "services",
                    "msg": "Service returns Union with Dict. Use Union[BaseModel, ...] instead.",
                    "auto_fix": True
                },
                "SERVICE_NESTED_DICT": {
                    "regex": [
                        r"->\s*Tuple\s*\[.*Dict\[",
                        r"->\s*Result\s*\[.*Dict\[",
                    ],
                    "layer": "services",
                    "msg": "Service returns nested Dict in generic type. Use BaseModel instead.",
                    "auto_fix": True
                },
                # Category 3: Repository in API
                "API_REPO_IMPORT": {
                    "regex": [
                        r"from\s+.*repositories.*import",
                        r"from\s+.*repository.*import",
                    ],
                    "layer": "api",
                    "msg": "API imports Repository directly. Use Service injection via Depends().",
                    "auto_fix": True
                },
                "API_REPO_INSTANTIATION": {
                    "regex": [
                        r"\w*Repository\s*\(",
                    ],
                    "layer": "api",
                    "msg": "API instantiates Repository. Use Service injection instead.",
                    "auto_fix": True
                },
                "API_REPO_METHOD_CALL": {
                    "regex": [
                        r"repo\s*\.\s*\w+\s*\(",
                        r"repository\s*\.\s*\w+\s*\(",
                        r"\.get_by_\w+\s*\(",
                    ],
                    "layer": "api",
                    "msg": "API calls Repository method. Route should only call Service methods.",
                    "auto_fix": False  # Complex refactoring needed
                },
                # Category 4: Cross-Layer Imports
                "SERVICE_IMPORTS_API": {
                    "regex": [
                        r"from\s+.*\.api\.",
                        r"from\s+.*\.api\s+import",
                    ],
                    "layer": "services",
                    "msg": "Service imports from API layer. Violates dependency flow.",
                    "auto_fix": False
                },
                "REPO_IMPORTS_SERVICE": {
                    "regex": [
                        r"from\s+.*services.*import",
                        r"from\s+.*service.*import",
                    ],
                    "layer": "repositories",
                    "msg": "Repository imports Service. Violates dependency flow.",
                    "auto_fix": False
                },
                "REPO_IMPORTS_SCHEMA": {
                    "regex": [
                        r"from\s+.*schemas.*import.*Response",
                        r"from\s+.*schemas.*import.*Request",
                    ],
                    "layer": "repositories",
                    "msg": "Repository imports Pydantic schema. Repository should only use SQLAlchemy models.",
                    "auto_fix": False
                },
            },
            "WARNING": {
                # Any return type
                "SERVICE_ANY_RETURN": {
                    "regex": [
                        r"->\s*Any\s*:",
                        r"->\s*Any\s*$",
                    ],
                    "layer": "services",
                    "msg": "Service returns Any type. Specify concrete BaseModel type.",
                    "auto_fix": False
                },
                # Missing type hints
                "MISSING_RETURN_TYPE": {
                    "regex": [
                        r"async\s+def\s+\w+\s*\([^)]*\)\s*:",
                        r"def\s+(?!__)\w+\s*\([^)]*\)\s*:",  # Exclude __init__ etc
                    ],
                    "layer": "services",
                    "msg": "Method missing return type annotation.",
                    "auto_fix": False
                },
            },
            "INFO": {
                # Private method with Dict (allowed in some cases)
                "PRIVATE_METHOD_DICT": {
                    "regex": [
                        r"def\s+_\w+.*->\s*Dict\[",
                    ],
                    "layer": "services",
                    "msg": "Private method returns Dict. Consider using BaseModel for consistency.",
                    "auto_fix": False
                },
            }
        }
    }
}

# ============================================================================
# Configuration Management
# ============================================================================

def load_config(project_path: str) -> dict:
    """
    Load .clean-arch.json from project root or use defaults.

    Priority:
    1. .clean-arch.json in project root
    2. .clean-arch.json in src/
    3. Default paths
    """
    root = Path(project_path)

    # Check root directory
    config_file = root / ".clean-arch.json"
    if config_file.exists():
        try:
            with open(config_file) as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️  Warning: Invalid JSON in {config_file}, using defaults")

    # Check src/ directory
    src_config = root / "src" / ".clean-arch.json"
    if src_config.exists():
        try:
            with open(src_config) as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass

    # Default configuration
    return {
        "version": "1.0",
        "paths": {
            "api": "src/*/api/v*/*.py",
            "services": "src/*/services/*.py",
            "repositories": "src/*/repositories/*.py",
            "schemas": "src/*/schemas/*.py",
            "models": "src/*/models/*.py"
        },
        "exclude": [
            "**/tests/**",
            "**/__pycache__/**",
            "**/migrations/**",
            "**/.venv/**"
        ],
        "rules": {
            "enforceBaseModelReturns": True,
            "allowDictInPrivateMethods": False,
            "requireTypeHints": True
        }
    }

# ============================================================================
# ripgrep Utilities
# ============================================================================

def check_dependencies():
    """Check if ripgrep is installed"""
    if not shutil.which("rg"):
        raise RuntimeError(
            "❌ 'rg' (ripgrep) not found.\n"
            "Install: sudo apt install ripgrep (Ubuntu/Debian)\n"
            "        brew install ripgrep (macOS)"
        )

def run_rg(regex: str, path: str, glob: str = "**/*.py") -> List[Dict]:
    """
    Run ripgrep with pattern.

    Returns:
        List of matches with file, line, and code
    """
    cmd = [
        "rg", regex,
        "-g", glob,
        "-n",  # Line numbers
        "--no-heading",
        "--with-filename",
        path
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="ignore"
        )

        findings = []
        if result.stdout:
            for line in result.stdout.splitlines():
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    findings.append({
                        "file": parts[0].strip(),
                        "line": parts[1],
                        "code": parts[2].strip()
                    })

        return findings
    except Exception as e:
        return [{"error": str(e)}]

# ============================================================================
# Architecture Score Calculation
# ============================================================================

def calculate_architecture_score(violations: List[Dict]) -> Dict:
    """
    Calculate architecture compliance score (0-100).

    Deductions:
    - CRITICAL: -10 points each
    - WARNING: -5 points each
    - INFO: -1 point each
    """
    score = 100
    critical_count = 0
    warning_count = 0
    info_count = 0

    for v in violations:
        severity = v.get("severity", "INFO")
        if severity == "CRITICAL":
            score -= 10
            critical_count += 1
        elif severity == "WARNING":
            score -= 5
            warning_count += 1
        elif severity == "INFO":
            score -= 1
            info_count += 1

    score = max(0, score)

    # Grade calculation
    if score >= 90:
        grade, status = "A", "Excellent ✨"
    elif score >= 80:
        grade, status = "B", "Good 👍"
    elif score >= 70:
        grade, status = "C", "Fair ⚠️"
    elif score >= 60:
        grade, status = "D", "Poor 🔧"
    else:
        grade, status = "F", "Failing ❌"

    return {
        "score": score,
        "grade": grade,
        "status": status,
        "critical": critical_count,
        "warning": warning_count,
        "info": info_count
    }

# ============================================================================
# Layer-by-Layer File Scanning
# ============================================================================

def scan_layers(project_path: str, config: dict) -> Dict[str, List[str]]:
    """
    Scan project for layer files.

    Returns:
        Dict mapping layer name to list of file paths
    """
    from glob import glob

    root = Path(project_path)
    paths = config.get("paths", {})
    exclude = config.get("exclude", [])

    layers = {}

    for layer_name, pattern in paths.items():
        # Convert pattern to glob-compatible format
        full_pattern = str(root / pattern)
        files = glob(full_pattern, recursive=True)

        # Apply exclusions
        filtered = []
        for f in files:
            excluded = False
            for ex in exclude:
                if ex.replace("**", "").replace("*", "") in f:
                    excluded = True
                    break
            if not excluded:
                filtered.append(f)

        layers[layer_name] = filtered

    return layers

# ============================================================================
# Validation Tools
# ============================================================================

@mcp.tool()
def validate_architecture(
    project_path: str,
    tech_stack: str = "FASTAPI",
    verbose: bool = False
) -> str:
    """
    Validate Clean Architecture compliance in a FastAPI project.

    Args:
        project_path: Absolute path to project root
        tech_stack: 'FASTAPI', 'SPRING', or 'REACT' (currently FASTAPI only)
        verbose: Include detailed explanations and fix suggestions

    Returns:
        Detailed validation report with architecture score
    """
    root = Path(project_path).resolve()
    if not root.exists():
        return f"❌ Error: Path '{root}' does not exist."

    check_dependencies()

    # Load configuration
    config = load_config(str(root))

    # Get rules for tech stack
    stack_rules = RULES.get(tech_stack.upper())
    if not stack_rules:
        return f"❌ Error: Unknown tech stack '{tech_stack}'. Supported: {list(RULES.keys())}"

    # Scan layers
    layers = scan_layers(str(root), config)

    # Collect violations
    violations = []
    layer_stats = {}

    for severity_level, checks in stack_rules["patterns"].items():
        for rule_name, rule in checks.items():
            target_layer = rule.get("layer", "services")

            # Determine which files to scan
            if target_layer == "api":
                scan_files = layers.get("api", [])
            elif target_layer == "services":
                scan_files = layers.get("services", [])
            elif target_layer == "repositories":
                scan_files = layers.get("repositories", [])
            else:
                continue

            # Run each regex pattern
            for regex in rule["regex"]:
                # Search in layer-specific directories
                if target_layer in config.get("paths", {}):
                    search_pattern = config["paths"][target_layer]
                    matches = run_rg(regex, str(root), search_pattern)

                    for match in matches:
                        if "error" in match:
                            continue

                        violations.append({
                            "severity": severity_level,
                            "rule": rule_name,
                            "layer": target_layer,
                            "file": match["file"],
                            "line": match["line"],
                            "code": match["code"],
                            "message": rule["msg"],
                            "auto_fix": rule.get("auto_fix", False)
                        })

    # Calculate stats per layer
    for layer in ["api", "services", "repositories"]:
        layer_violations = [v for v in violations if v["layer"] == layer]
        layer_stats[layer] = {
            "files": len(layers.get(layer, [])),
            "violations": len(layer_violations),
            "critical": len([v for v in layer_violations if v["severity"] == "CRITICAL"])
        }

    # Calculate score
    score_info = calculate_architecture_score(violations)

    # Generate report
    report = []
    report.append(f"✅ Clean Architecture Validation Results")
    report.append("━" * 60)
    report.append(f"\n📂 Project: {root}")
    report.append(f"⚙️  Config File: {'Found' if (root / '.clean-arch.json').exists() else 'Using Defaults'}")
    report.append("")

    # Layer-by-layer report
    for layer in ["api", "services", "repositories"]:
        stats = layer_stats.get(layer, {"files": 0, "violations": 0})
        layer_violations = [v for v in violations if v["layer"] == layer]

        status_icon = "✅" if stats["violations"] == 0 else "❌"

        report.append(f"📂 {layer.upper()} Layer")
        report.append(f"├─ Files Scanned: {stats['files']}")
        report.append(f"├─ Violations: {stats['violations']}")

        if layer_violations:
            report.append("│")
            for v in layer_violations[:5]:  # Show first 5
                severity_icon = "🚫" if v["severity"] == "CRITICAL" else "⚠️" if v["severity"] == "WARNING" else "ℹ️"
                report.append(f"│  {severity_icon} {v['severity']}: {v['file']}:{v['line']}")
                report.append(f"│     → {v['code'][:80]}")
                report.append(f"│     💡 {v['message']}")
                if v.get("auto_fix"):
                    report.append(f"│     ✏️  Auto-fixable")
                report.append("│")

            if len(layer_violations) > 5:
                report.append(f"│  ... and {len(layer_violations) - 5} more")

        report.append(f"└─ Status: {status_icon} {'PASS' if stats['violations'] == 0 else 'FAIL'}")
        report.append("")

    # Summary
    report.append("━" * 60)
    report.append(f"\n📊 Summary")
    report.append(f"├─ Total Files: {sum(stats['files'] for stats in layer_stats.values())}")
    report.append(f"├─ Violations: {len(violations)}")
    report.append(f"│  ├─ CRITICAL: {score_info['critical']}")
    report.append(f"│  ├─ WARNING: {score_info['warning']}")
    report.append(f"│  └─ INFO: {score_info['info']}")
    report.append(f"│")
    report.append(f"└─ Architecture Score: {score_info['score']}/100 (Grade {score_info['grade']}) - {score_info['status']}")
    report.append("")

    # Auto-fix info
    auto_fixable = len([v for v in violations if v.get("auto_fix")])
    if auto_fixable > 0:
        report.append(f"🔧 Auto-fixable: {auto_fixable}")
        report.append(f"📝 Manual Review Required: {len(violations) - auto_fixable}")
        report.append("")
        report.append("💡 To run auto-fix: Use the fix_violations() tool")

    return "\n".join(report)

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
        return f"❌ Error: Path '{root}' does not exist."

    # TODO: Implement auto-fix logic
    # This would involve:
    # 1. Detecting violations (reuse validate_architecture logic)
    # 2. For each auto-fixable violation:
    #    a. Generate Pydantic schema if needed
    #    b. Transform code (Dict → BaseModel, etc.)
    #    c. Update imports
    # 3. Generate fix report

    return f"""
🔧 Auto-fix Feature (Coming Soon)

Current Status: dry_run={dry_run}
Project: {root}

The following features will be implemented:
1. Dict → BaseModel transformation
2. Automatic schema generation
3. Repository → Service refactoring
4. Import statement cleanup
5. Type hint addition

Note: Can be implemented using Claude Code's Edit tool.
"""

@mcp.tool()
def generate_schema(
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
    schema_code = f'''from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class {class_name}(BaseModel):
    """Auto-generated schema for {class_name}."""

'''

    for field_name, field_type in fields.items():
        schema_code += f"    {field_name}: {field_type}\n"

    schema_code += '''
    model_config = {"from_attributes": True}
'''

    if output_path:
        try:
            Path(output_path).write_text(schema_code)
            return f"✅ Schema generated at: {output_path}\n\n{schema_code}"
        except Exception as e:
            return f"❌ Error writing file: {e}\n\n{schema_code}"

    return schema_code

# ============================================================================
# MCP Server Execution
# ============================================================================

if __name__ == "__main__":
    mcp.run()
