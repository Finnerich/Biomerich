
import os

RELEASE = os.getenv("SOLRICH_RELEASE") == "1"


def feature_on(key: str) -> bool:
    
    return not RELEASE
