from airflow.models import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from evaluate_response import run_evaluation
import csv

def print_results():
    with open("/tmp/evaluation_results.csv", "r") as f:
        print(f.read())

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
