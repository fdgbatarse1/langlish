from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
import pandas as pd
import json
from typing import List, Dict
from collections import defaultdict
import logging

from src.services.s3_service import S3Service



default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 6, 25),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'conversation_evaluation_pipeline',
    default_args=default_args,
    description='Pull conversation data from S3, merge sessions, and evaluate',
    schedule_interval='@daily',
    catchup=False,
    tags=['nlp', 'evaluation', 's3'],
)

def pull_conversation(type):
    """
    Pull from S3
    """
    return S3Service.pull_conversations_from_s3(type)

def group_conversations_by_session(**context):
    """
    Group conversation data by session_id.
    """
    # Get data from previous task
    all_conversations = context['task_instance'].xcom_pull(task_ids='pull_s3_data')
    
    if not all_conversations:
        logging.warning("No conversation data received")
        return {}
    
    # Group by session_id
    sessions_grouped = defaultdict(list)
    
    for conversation in all_conversations:
        session_id = conversation.get('session_id')
        if session_id:
            sessions_grouped[session_id].append(conversation)
        else:
            logging.warning(f"Conversation missing session_id: {conversation}")
    
    logging.info(f"Grouped conversations into {len(sessions_grouped)} sessions")
    
    # Convert defaultdict to regular dict for serialization
    return dict(sessions_grouped)

def merge_sessions_data(**context):
    """
    Merge conversation turns by session_id into complete conversations.
    """
    from collections import defaultdict
    
    # Get grouped data from previous task
    sessions_grouped = context['task_instance'].xcom_pull(task_ids='group_by_session')
    
    if not sessions_grouped:
        logging.warning("No grouped session data received")
        return []
    
    def merge_sessions(session_data_list: List[Dict]) -> List[Dict]:
        """
        Merge conversation turns by session_id into a single conversation per session.
        """
        merged = defaultdict(lambda: {"session_id": "", "user": [], "assistant": []})

        for item in session_data_list:
            session_id = item["session_id"]
            merged[session_id]["session_id"] = session_id
            merged[session_id]["user"].append(item.get("student_message", ""))
            merged[session_id]["assistant"].append(item.get("model_response", ""))

        # Convert merged structure to list of dicts
        result = []
        for session_id, convo in merged.items():
            result.append({
                "session_id": session_id,
                "user": " ".join(convo["user"]),
                "assistant": " ".join(convo["assistant"])
            })

        return result
    
    # Process each session
    all_merged_sessions = []
    
    for session_id, session_conversations in sessions_grouped.items():
        try:
            # Merge this session's conversations
            merged_session = merge_sessions(session_conversations)
            all_merged_sessions.extend(merged_session)
            
        except Exception as e:
            logging.error(f"Error merging session {session_id}: {str(e)}")
            continue
    
    logging.info(f"Merged {len(all_merged_sessions)} complete sessions")
    
    return all_merged_sessions

def evaluate_sessions(**context):
    """
    Evaluate all merged sessions using the evaluation function.
    """
    # Get merged sessions from previous task
    merged_sessions = context['task_instance'].xcom_pull(task_ids='merge_sessions')
    
    if not merged_sessions:
        logging.warning("No merged sessions received")
        return []
    
    # You would import and use your actual evaluation function here
    # For now, I'll include a simplified version
    
    def mock_evaluate_session(session_data: Dict) -> Dict:
        """
        Mock evaluation function - replace with your actual evaluate_session function
        """
        return {
            "session_id": session_data["session_id"],
            "metrics": {
                "clarity_score": {"score": 4, "justification": "Mock evaluation"},
                "vocabulary_enrichment_score": {"score": 3, "justification": "Mock evaluation"},
                "language_accuracy_score": {"score": 5, "justification": "Mock evaluation"},
                "fluency_practice_score": {"score": 4, "justification": "Mock evaluation"},
            }
        }
    
    evaluation_results = []
    
    for session in merged_sessions:
        try:
            # Replace this with your actual evaluate_session function
            evaluation = mock_evaluate_session(session)
            evaluation_results.append(evaluation)
            
        except Exception as e:
            logging.error(f"Error evaluating session {session.get('session_id')}: {str(e)}")
            continue
    
    logging.info(f"Evaluated {len(evaluation_results)} sessions")
    
    return evaluation_results

def print_results(**context):
    """
    Just print the evaluation results to Airflow logs.
    """
    results = context['task_instance'].xcom_pull(task_ids='evaluate_sessions')

    if not results:
        logging.warning("No evaluation results to print.")
        return

    for result in results:
        logging.info(f"Evaluation result for session {result['session_id']}: {json.dumps(result, indent=2)}")


# Define tasks
pull_data_task = PythonOperator(
    task_id='pull_s3_data',
    python_callable=pull_conversation("streamline"),
    dag=dag,
)

group_sessions_task = PythonOperator(
    task_id='group_by_session',
    python_callable=group_conversations_by_session,
    dag=dag,
)

merge_sessions_task = PythonOperator(
    task_id='merge_sessions',
    python_callable=merge_sessions_data,
    dag=dag,
)

evaluate_sessions_task = PythonOperator(
    task_id='evaluate_sessions',
    python_callable=evaluate_sessions,
    dag=dag,
)

print_results_task = PythonOperator(
    task_id='save_results',
    python_callable=print_results,
    dag=dag,
)

# Set task dependencies
pull_data_task >> group_sessions_task >> merge_sessions_task >> evaluate_sessions_task >> print_results_task