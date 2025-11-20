import os
os.environ["ENVIRONMENT"] = "testing"
from src.app.core.config import config
print(f"Testing Database URL: {config.DATABASE_URL}")
