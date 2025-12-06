# fastapi/constants.py
"""
Constants for FastAPI Clean Architecture validation.
"""
from typing import Dict, Set

# SQLAlchemy to Python type mappings
SQLALCHEMY_TO_PYTHON: Dict[str, str] = {
    # Integer types
    "Integer": "int",
    "BigInteger": "int",
    "SmallInteger": "int",

    # String types
    "String": "str",
    "Text": "str",
    "Unicode": "str",
    "UnicodeText": "str",
    "CHAR": "str",
    "VARCHAR": "str",

    # Boolean
    "Boolean": "bool",

    # Date/Time types
    "DateTime": "datetime",
    "Date": "date",
    "Time": "time",
    "Interval": "timedelta",

    # Numeric types
    "Float": "float",
    "Numeric": "float",
    "DECIMAL": "float",
    "REAL": "float",

    # JSON types
    "JSON": "dict",
    "JSONB": "dict",

    # Binary types
    "LargeBinary": "bytes",
    "BINARY": "bytes",
    "VARBINARY": "bytes",

    # Other types
    "Enum": "str",
    "UUID": "str",
    "ARRAY": "list",
}

# FastAPI/Starlette route decorator names
ROUTE_DECORATORS: Set[str] = {
    "get",
    "post",
    "put",
    "delete",
    "patch",
    "options",
    "head",
    "trace",
    "api_route",
    "route",
    "websocket",
}

# Common API router object names
API_ROUTER_NAMES: Set[str] = {
    "router",
    "app",
    "api_router",
    "api",
}

# Common method names to exclude from attribute detection
EXCLUDED_METHOD_NAMES: Set[str] = {
    "get",
    "set",
    "filter",
    "query",
    "first",
    "all",
    "one",
    "scalar",
    "execute",
    "commit",
    "rollback",
    "flush",
    "refresh",
    "delete",
    "add",
    "merge",
}
