from enum import Enum

class Framework(str, Enum):
    FASTAPI = "fastapi"
    SPRINGBOOT = "springboot"
    REACT = "react"

DEFAULT_SCORE_CONFIG = {
    "initial_score": 100,
    "deductions": {
        "CRITICAL": 10,
        "WARNING": 5,
        "INFO": 1
    },
    "grades": {
        "A": 90,
        "B": 80,
        "C": 70
    }
}
