from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def print_hello():
    return 'Hello World from Airflow!'

with DAG(
    'hello_world',
    default_args=default_args,
    description='A simple hello world DAG',
    schedule=timedelta(days=1),
    catchup=False,
) as dag:
    
    # Python operator
    hello_task = PythonOperator(
        task_id='print_hello',
        python_callable=print_hello,
    )
    
    # Bash operator
    date_task = BashOperator(
        task_id='print_date',
        bash_command='date',
    )
    
    # Set task dependencies
    hello_task >> date_task 