import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import pandas as pd
import json
from typing import List, Dict
from collections import defaultdict
import logging

from src.services.s3_service import S3Service
from src.evaluate_response import evaluate_multiple_sessions

import mlflow
from src.mlflow_config import setup_mlflow

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
    schedule='@daily',
    catchup=False,
    tags=['nlp', 'evaluation', 's3'],
)

def pull_conversation(type):
    """
    Pull from S3
    """
    s3_service = S3Service() 
    return s3_service.pull_conversations_from_s3(type)

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
    setup_mlflow()

    merged_sessions = context['task_instance'].xcom_pull(task_ids='merge_sessions')
    if not merged_sessions:
        logging.warning("No merged sessions received")
        return []
    
    results = evaluate_multiple_sessions(merged_sessions)

    # Use a parent run for the entire evaluation batch
    parent_run_name = f"airflow_eval_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    with mlflow.start_run(run_name=parent_run_name):
        mlflow.log_param("num_sessions", len(merged_sessions))
        mlflow.log_param("evaluation_type", "streamline_conversations")

        for result in results:
            session_id = result["session_id"]

            # Find the corresponding session data for conversation history
            session_data = next((s for s in merged_sessions if s["session_id"] == session_id), {})
            session_config = get_session_config(session_id) 

            # Create a nested run for this session to keep prompt and evaluation separate
            with mlflow.start_run(run_name=f"session_{session_id}", nested=True):
                # Log prompt/config
                model_version = session_config.get("model_version", "gpt-4o")
                instructions = session_config.get("session", {}).get("instructions", "")
                
                # Register prompt in MLflow Prompt Registry
                prompt_name = "langlish-instruction-prompt"
                mlflow.genai.create_or_update_prompt(name=prompt_name, prompt=instructions)
                
                mlflow.log_param("model_version", model_version)
                mlflow.log_param("session_id", session_id)
                mlflow.log_text(instructions, "prompt.txt")
                mlflow.log_dict(session_config, "session_config.json")

                # Log conversation history
                if session_data:
                    conversation_data = {
                        "session_id": session_id,
                        "user_messages": session_data.get("user", ""),
                        "assistant_messages": session_data.get("assistant", ""),
                        "conversation_length": len(session_data.get("user", "").split()) + len(session_data.get("assistant", "").split())
                    }
                    mlflow.log_dict(conversation_data, f"conversations/{session_id}_conversation.json")
                    mlflow.log_param("conversation_length_words", conversation_data["conversation_length"])

                # Log evaluation metrics
                for metric_name, metric_details in result["metrics"].items():
                    score = metric_details.get("score")
                    if score is not None:
                        mlflow.log_metric(f"{metric_name}", score)
                
                # Log full results artifact
                mlflow.log_dict(result, f"results/{session_id}.json")

    return results

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

######mock###
def get_session_config(session_id):
    """
    Returns a mock session configuration dictionary
    similar to what your application uses to configure
    the OpenAI session or prompt instructions.
    """
    return {
        "session": {
            "modalities": ["audio", "text"],
            "voice": "alloy",
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {
                "model": "whisper-1"
            },
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500,
                "create_response": True,
            },
            "instructions": (
                "You are Langlish, a friendly and patient English learning "
                "assistant. You help students improve their English through "
                "conversation practice. Your role is to: help the user practice "
                "english conversation, correct grammar mistakes gently, suggest "
                "better vocabulary when appropriate, encourage the student, and "
                "adapt to the student's level."
            ),
        }
    }



# Define tasks
pull_data_task = PythonOperator(
    task_id='pull_s3_data',
    python_callable=lambda: pull_conversation(type="streamline"),
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
    task_id='print_results',
    python_callable=print_results,
    dag=dag,
)

# Set task dependencies
pull_data_task >> group_sessions_task >> merge_sessions_task >> evaluate_sessions_task >> print_results_task