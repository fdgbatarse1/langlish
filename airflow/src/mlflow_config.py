
import mlflow

def setup_mlflow():
    mlflow.set_tracking_uri("file:./mlruns")
    mlflow.set_experiment("TestVersioning")
