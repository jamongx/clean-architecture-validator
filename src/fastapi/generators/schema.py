# fastapi/generators/schema.py
from pathlib import Path
from typing import Dict, Optional


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
from typing import Optional, List, Dict, Any, Union
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
            p_out = Path(output_path)
            p_out.parent.mkdir(parents=True, exist_ok=True)
            p_out.write_text(schema_code)
            return f"✅ Schema generated at: {output_path}\n\n{schema_code}"
        except Exception as e:
            return f"❌ Error writing file: {e}\n\n{schema_code}"

    return schema_code
