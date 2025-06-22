import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from airflow.models import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from src.evaluate_response import evaluate_response
from src.services.s3_service import s3_service


def run_evaluation_task():
    # Example input
    student_message = "I don't speak English good."
    model_response = "That's okay! Let's improve together."

    result = evaluate_response(student_message, model_response)

    csv_line = f"{datetime.utcnow().isoformat()},{result['score']},{result['justification']}\n"

    s3_service.upload_evaluation(
        evaluation_data=csv_line,
        file_name="evaluation_results.csv",
        content_type="text/csv",
        metadata={"type": "evaluation"}
    )

def dummy_task():
    print("Hello from Airflow!")


default_args = {
    "start_date": datetime(2025, 6, 22),
    "catchup": False,
}

dag = DAG(
    dag_id="evaluation_dag",
    default_args=default_args,
    schedule=None,
    catchup=False,
    tags=["evaluation"]
)


task_dummy = PythonOperator(
    task_id="dummy_task",
    python_callable=dummy_task,
    dag=dag  
)

task_eval = PythonOperator(
    task_id="run_evaluation",
    python_callable=run_evaluation_task,
    dag=dag
)


task_dummy >> task_eval