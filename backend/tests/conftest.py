import os
import sys
from unittest.mock import MagicMock
from typing import Any

# Set environment variable to disable MLflow tracking during tests
os.environ["MLFLOW_TRACKING_URI"] = "file:///tmp/mlruns"

# Mock heavy imports before they're loaded
sys.modules["mlflow"] = MagicMock()
sys.modules["boto3"] = MagicMock()
sys.modules["sentry_sdk"] = MagicMock()

# Ensure mlflow mock has necessary attributes
mlflow_mock: Any = sys.modules["mlflow"]
mlflow_mock.set_tracking_uri = MagicMock()
mlflow_mock.set_experiment = MagicMock()
mlflow_mock.start_run = MagicMock()
mlflow_mock.log_param = MagicMock()
mlflow_mock.end_run = MagicMock()
