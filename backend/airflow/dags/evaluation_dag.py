from airflow.models import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from evaluate_response import run_evaluation
from src.services.s3_service import s3_service
import csv

def print_results():
    s3_key = "evaluation_results.csv"
    file_bytes = s3_service.download_file(s3_key)
    if file_bytes:
        print(file_bytes.decode("utf-8"))
    else:
        print(f"Failed to read {s3_key} from S3")


default_args = {
    "start_date": datetime(2025, 6, 19),
    "catchup": False,
}

dag = DAG(
    dag_id="gpt_evaluation_dag",
    schedule=None,
    catchup=False,
    tags=["evaluation"]
)

task_eval = PythonOperator(
    task_id="run_evaluation",
    python_callable=run_evaluation,
    dag=dag
)

task_print = PythonOperator(
    task_id="print_results",
    python_callable=print_results,
    dag=dag
)

task_eval >> task_print
