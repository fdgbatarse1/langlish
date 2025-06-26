
import mlflow

def setup_mlflow():
    MLFLOW_TRACKING_URI = "http://localhost:5001"
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("TestVersioning")
