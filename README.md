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
  - **🔌 Extensible Design:** Comes with **FastAPI** rules by default; easily expandable to **Spring Boot** or **React**.
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

**Example Prompt:**

> "Scan the architecture of my project at `/home/user/projects/my-fastapi-service`."

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

## ⚙️ Customization

You can add custom rules for different tech stacks (like Spring Boot or React) by modifying the `RULES` dictionary in `main.py`.

```python
RULES = {
    "FASTAPI": { ... },
    "SPRING": {
        "files": "**/*.java",
        "patterns": {
             # Add Java patterns here
        }
    }
}
```

## 📜 License

MIT License