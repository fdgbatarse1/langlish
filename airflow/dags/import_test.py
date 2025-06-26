#!/usr/bin/env python3
"""
Minimal DAG to test each function individually
"""

import faulthandler
import os
import sys

# Enable fault handler
os.environ['PYTHONFAULTHANDLER'] = 'true'
faulthandler.enable()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

print("Creating minimal test DAG...")

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 6, 25),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,  # No retries for testing
    'retry_delay': timedelta(minutes=1),
}

dag = DAG(
    'minimal_test_dag',
    default_args=default_args,
    description='Minimal test DAG to isolate segfault',
    schedule=None,  # Manual trigger only
    catchup=False,
    tags=['test'],
)

def test_basic_function():
    """Test basic Python functionality"""
    print("Testing basic function...")
    logging.info("Basic function executed successfully")
    return {"status": "success", "message": "Basic function works"}

def test_s3_import():
    """Test S3 service import only"""
    print("Testing S3 import...")
    try:
        from src.services.s3_service import S3Service
        logging.info("S3Service imported successfully")
        return {"status": "success", "message": "S3 import works"}
    except Exception as e:
        logging.error(f"S3 import failed: {e}")
        raise

def test_s3_instantiation():
    """Test S3 service instantiation"""
    print("Testing S3 instantiation...")
    try:
        from src.services.s3_service import S3Service
        s3_service = S3Service()
        logging.info("S3Service instantiated successfully")
        return {"status": "success", "message": "S3 instantiation works"}
    except Exception as e:
        logging.error(f"S3 instantiation failed: {e}")
        raise

def test_mlflow_import():
    """Test MLflow imports"""
    print("Testing MLflow import...")
    try:
        import mlflow
        from src.mlflow_config import setup_mlflow
        logging.info("MLflow imported successfully")
        return {"status": "success", "message": "MLflow import works"}
    except Exception as e:
        logging.error(f"MLflow import failed: {e}")
        raise

def test_mlflow_setup():
    """Test MLflow setup execution"""
    print("Testing MLflow setup...")
    try:
        from src.mlflow_config import setup_mlflow
        setup_mlflow()
        logging.info("MLflow setup completed successfully")
        return {"status": "success", "message": "MLflow setup works"}
    except Exception as e:
        logging.error(f"MLflow setup failed: {e}")
        raise

def test_evaluate_import():
    """Test evaluation function import"""
    print("Testing evaluation import...")
    try:
        from src.evaluate_response import evaluate_multiple_sessions
        logging.info("evaluate_multiple_sessions imported successfully")
        return {"status": "success", "message": "Evaluation import works"}
    except Exception as e:
        logging.error(f"Evaluation import failed: {e}")
        raise

def test_mock_data_processing():
    """Test data processing with mock data"""
    print("Testing mock data processing...")
    try:
        # Mock data similar to your real data
        mock_conversations = [
            {
                "session_id": "test_session_1",
                "student_message": "Hello, how are you?",
                "model_response": "I'm doing well, thank you!"
            },
            {
                "session_id": "test_session_1", 
                "student_message": "What's the weather like?",
                "model_response": "I don't have access to current weather data."
            }
        ]
        
        # Test grouping logic
        from collections import defaultdict
        sessions_grouped = defaultdict(list)
        
        for conversation in mock_conversations:
            session_id = conversation.get('session_id')
            if session_id:
                sessions_grouped[session_id].append(conversation)
        
        logging.info(f"Grouped {len(sessions_grouped)} sessions")
        return {"status": "success", "message": f"Mock processing works - {len(sessions_grouped)} sessions"}
        
    except Exception as e:
        logging.error(f"Mock data processing failed: {e}")
        raise

# Create tasks
basic_test = PythonOperator(
    task_id='test_basic',
    python_callable=test_basic_function,
    dag=dag,
)

s3_import_test = PythonOperator(
    task_id='test_s3_import',
    python_callable=test_s3_import,
    dag=dag,
)

s3_instantiation_test = PythonOperator(
    task_id='test_s3_instantiation',
    python_callable=test_s3_instantiation,
    dag=dag,
)

mlflow_import_test = PythonOperator(
    task_id='test_mlflow_import',
    python_callable=test_mlflow_import,
    dag=dag,
)

mlflow_setup_test = PythonOperator(
    task_id='test_mlflow_setup',
    python_callable=test_mlflow_setup,
    dag=dag,
)

evaluate_import_test = PythonOperator(
    task_id='test_evaluate_import',
    python_callable=test_evaluate_import,
    dag=dag,
)

mock_data_test = PythonOperator(
    task_id='test_mock_data',
    python_callable=test_mock_data_processing,
    dag=dag,
)

# Set dependencies - each task runs independently for easier debugging
# No dependencies so we can test each one individually

print("Minimal test DAG created successfully!")