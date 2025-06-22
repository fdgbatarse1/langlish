import sys
import os

print("Before append:", sys.path)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
print("After append:", sys.path)

try:
    from src.services.s3_service import S3Service
    print("Import successful!")
except ModuleNotFoundError as e:
    print("Import failed:", e)

try:
    from src.evaluate_response import evaluate_response
    print("Import successful!")
except ModuleNotFoundError as e:
    print("Import failed:", e)
