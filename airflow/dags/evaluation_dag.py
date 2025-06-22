from airflow.models import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from evaluate_response import evaluate_response
from src.services.s3_service import s3_service

def run_evaluation_task():
    # Example input
    student_message = "I don't speak English good."
    model_response = "That's okay! Let's improve together."

    result = evaluate_response(student_message, model_response)

    csv_line = f"{datetime.utcnow().isoformat()},{result['score']},{result['justification']}\n"

    s3_service.upload_text(
        text_data=csv_line,
        file_name="evaluation_results.csv",
        content_type="text/csv",
        metadata={"type": "evaluation"}
    )

def dummy_task():
    print("Hello from Airflow!")


def print_results():
    s3_key = "evaluation_results.csv"
    file_bytes = s3_service.download_file(s3_key)
    if file_bytes:
        print(file_bytes.decode("utf-8"))
    else:
        print(f"Failed to read {s3_key} from S3")


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

task_eval = PythonOperator(
    task_id="run_evaluation",
    python_callable=run_evaluation_task,
    dag=dag
)

task_print = PythonOperator(
    task_id="print_results",
    python_callable=print_results,
    dag=dag
)
task = PythonOperator(
    task_id="dummy_task",
    python_callable=dummy_task
)

task >> task_eval >> task_print
