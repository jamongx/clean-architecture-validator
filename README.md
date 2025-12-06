# Clean Architecture Validator (MCP Server)

[](https://modelcontextprotocol.io)
[](https://python.org)
[](https://fastapi.tiangolo.com)

A **Model Context Protocol (MCP)** server that automatically validates **Clean Architecture** compliance in your projects.

Unlike generic linters, this tool works with **Claude** to enforce architectural rules (e.g., "Service layer must return Pydantic models, not Dicts"). It uses **`ripgrep` (rg)** for lightning-fast, rule-based static analysis, making it scalable for large codebases.

## 🚀 Features

  - **⚡️ High Performance:** Built on Rust-based `ripgrep` to scan thousands of files instantly.
  - **🛡️ Service Layer Validation:** Strictly enforces Pydantic `BaseModel` return types (blocks `Dict`, `Any`).
  - **🏗️ Dependency Enforcement:** Detects forbidden imports (e.g., API layer directly importing Repositories).
  - **🔌 Extensible Design:** Comes with **FastAPI** rules by default, and an **extensible plugin system** to easily add validators for **Spring Boot**, **React**, or other frameworks.
  - **📊 Detailed Reporting:** Generates structured ASCII reports with architectural grades (A-F).

## 🛠 Prerequisites

Ensure you have the following tools installed on your system (Linux/macOS):

  - **Python 3.12+**
  - **Poetry** (Dependency Manager)
  - **ripgrep** (Required for scanning)
  - **Claude Code** (CLI)

<!-- end list -->

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ripgrep
npm install -g @anthropic-ai/claude-code

# macOS
brew install ripgrep
npm install -g @anthropic-ai/claude-code
```

## 📦 Installation

To avoid dependency conflicts between `fastmcp` and `mcp[cli]`, please follow these specific steps:

### 1. Clone the repository

```bash
git clone git@github.com:jamongx/clean-architecture-validator.git
cd clean-architecture-validator
```

### 2. Configure Poetry

Create the virtual environment inside the project directory for easier management.

```bash
poetry config virtualenvs.in-project true
```

### 3. Install Dependencies

> **Important:** We explicitly define the Python version (`<4.0`) and `mcp` version (`<1.23`) to ensure compatibility with `fastmcp`.

```bash
# Initialize project with specific python constraint
poetry init -n --name "clean-arch-validator" --python ">=3.12,<4.0"

# Install dependencies (Preventing version conflict)
poetry add fastmcp "mcp[cli]<1.23"
```

## 🔌 Configuration (Claude CLI)

Register the MCP server to your Claude environment. Using `poetry run` allows execution without manually activating the virtual environment.

**Run the following command in your terminal:**

```bash
claude mcp add clean-arch-validator --scope user -- \
  poetry run --directory /path/to/clean-architecture-validator \
  python main.py
```

> ⚠️ **Note:** Replace `/path/to/clean-architecture-validator` with the **absolute path** to your cloned directory.

**Verify connection:**

```bash
claude mcp list
# Expected Output:
# clean-arch-validator: ... - ✓ Connected
```

## 📖 Usage

Start a session with Claude Code:

```bash
claude
```

### 1. Validate Architecture

**Example Prompt:**

> "Scan the architecture of my project at `/home/user/projects/my-fastapi-service` for `FASTAPI` compliance, with verbose output."

**Tool Call (internal):**

```python
validate_architecture(
    project_path="/home/user/projects/my-fastapi-service",
    tech_stack="FASTAPI",
    verbose=True
)
```

**Example Output:**

```text
✅ Clean Architecture Validation Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📂 Project: /home/user/projects/my-fastapi-service
⚙️  Config File: Using Defaults

📂 API Layer
├─ Files Scanned: 5
├─ Violations: 0
└─ Status: ✅ PASS

📂 SERVICES Layer
├─ Files Scanned: 12
├─ Violations: 1
│  🚫 CRITICAL: services/user_service.py:45
│     → def get_user(...) -> Dict[str, Any]:
│     💡 Service returns Dict[str, Any]. Use Pydantic BaseModel instead.
│     ✏️  Auto-fixable
│
└─ Status: ❌ FAIL

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Summary
├─ Total Files: 25
├─ Violations: 1
└─ Architecture Score: 90/100 (Grade A) - Excellent ✨
```

### 2. Fix Violations

**Example Prompt:**

> "Automatically fix all auto-fixable Clean Architecture violations in my project at `/home/user/projects/my-fastapi-service`. Perform a dry run first."

**Tool Call (internal):**

```python
fix_violations(
    project_path="/home/user/projects/my-fastapi-service",
    dry_run=True
)
```

**Example Output (Dry Run):**

```text
🔧 Auto-fix Report (DRY RUN)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📂 Project: /home/user/projects/my-fastapi-service

📊 Summary:
  - Total Violations: 1
  - Auto-fixable: 1
  - Manual Review Required: 0
  - Fixes Applied: 1

✅ Applied Fixes (1):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. services/user_service.py:45
   Description: Converted Dict return type to Pydantic BaseModel.
   Original:    def get_user(...) -> Dict[str, Any]:
   Fixed:       def get_user(...) -> User:
   ⚠️  Action Required: Generated new schema 'User' in schemas/user.py. Review and import.

📄 Schema Files Generated (1):
   - schemas/user.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 This was a DRY RUN. No files were modified.
   Run with dry_run=False to apply changes.
```

### 3. Generate Schema

**Example Prompt:**

> "Generate a Pydantic schema named `Product` with fields `name` (str), `price` (float), and `in_stock` (bool). Save it to `src/my_app/schemas/product.py`."

**Tool Call (internal):**

```python
generate_schema_tool(
    class_name="Product",
    fields={
        "name": "str",
        "price": "float",
        "in_stock": "bool"
    },
    output_path="src/my_app/schemas/product.py"
)
```

**Example Output:**

```python
# src/my_app/schemas/product.py
from pydantic import BaseModel

class Product(BaseModel):
    name: str
    price: float
    in_stock: bool
```

## ⚙️ Customization

The validator uses a plugin-based architecture. New frameworks or custom rules can be added without modifying `main.py`.

### Adding New Framework Validators

To add support for a new `TECH_STACK` (e.g., `DJANGO`):

1.  **Create a new validator module:**
    Create `src/django/validators/validator.py` (similar to `src/fastapi/validators/validator.py`).
    ```python
    # src/django/validators/validator.py
    from typing import Dict, Any
    from src.core.base import FrameworkValidator
    from src.core.constants import Framework
    from src.core.models import ValidationResult
    from src.core.registry import validator_registry

    @validator_registry.register(Framework.DJANGO) # Register with the registry
    class DjangoValidator(FrameworkValidator):
        # Implement default_config and validation logic here
        @property
        def default_config(self) -> Dict[str, Any]:
            return {
                "version": "1.0",
                "paths": {
                    "views": "src/*/views/*.py",
                    "models": "src/*/models/*.py",
                },
                "exclude": ["**/tests/**", "**/__pycache__/**"],
            }

        def validate(self) -> ValidationResult:
            # Implement your Django-specific validation logic
            # ...
            return self._build_validation_result(
                violations=[],
                framework=Framework.DJANGO.value
            )
    ```

2.  **Import the new validator:**
    Ensure the new validator module is imported in `main.py` to trigger its registration.
    ```python
    # main.py
    # ...
    import src.django.validators # noqa: F401 - registers DjangoValidator
    # ...
    ```

### Defining Custom Rules

Validation rules for each framework (e.g., FastAPI) are defined in a `rules.json` file located in `src/<framework>/rules/`.

**Example: `src/fastapi/rules/rules.json`**

```json
{
  "FASTAPI": {
    "patterns": {
      "CRITICAL": {
        "MISSING_RETURN_TYPE": {
          "layer": "services",
          "regex": ["def\s+\w+\(.*\)\s*->\s*(None|Dict|Any):"],
          "msg": "Service layer functions must have explicit Pydantic BaseModel return types.",
          "auto_fix": true
        }
      },
      "WARNING": {
        "FORBIDDEN_REPOSITORY_IMPORT": {
          "layer": "api",
          "regex": ["from\s+\S*\.repositories\.\S*\s+import"],
          "msg": "API layer should not directly import from the Repository layer.",
          "auto_fix": false
        }
      }
    }
  }
}
```

**Rule Structure:**
-   **`framework_name`**: (e.g., `"FASTAPI"`) Top-level key matching the `Framework` enum value (uppercase).
-   **`patterns`**: Contains rules categorized by `severity` (e.g., `"CRITICAL"`, `"WARNING"`).
-   **`rule_name`**: (e.g., `"MISSING_RETURN_TYPE"`) Unique name for the rule.
    -   **`layer`**: The architectural layer this rule applies to (e.g., `"services"`, `"api"`). These map to the `paths` defined in the validator's `default_config`.
    -   **`regex`**: A list of regular expressions. If any regex matches, the rule is violated.
    -   **`msg`**: The message to display when the rule is violated.
    -   **`auto_fix`**: (Optional) `true` if this violation can be automatically fixed by the tool.


## 📜 License

MIT License