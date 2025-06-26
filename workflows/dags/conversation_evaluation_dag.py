import sys
import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import json
from typing import List, Dict
from collections import defaultdict
import logging
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import openai
from decimal import Decimal
import mlflow

# MLflow tracking URI from environment
# Use file-based tracking for local development
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "file:///opt/airflow/mlruns")

# Default session configuration used in production
# This represents the actual configuration used by the Langlish assistant
DEFAULT_SESSION_CONFIG = {
    "model_version": "gpt-4o",
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

# Airflow DAG default arguments
default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'conversation_evaluation_pipeline_v2',
    default_args=default_args,
    description='Pull conversation data from S3, merge sessions, and evaluate - No mocks version',
    schedule='@daily',
    catchup=False,
    tags=['nlp', 'evaluation', 's3', 'production'],
)

# S3 Service implementation (embedded to avoid external dependencies)
class S3Service:
    """Service class for AWS S3 operations."""
    
    def __init__(self):
        """Initialize S3 client with credentials from environment."""
        try:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                region_name=os.environ.get("AWS_S3_REGION", "us-east-1"),
            )
            self.bucket_name = os.environ.get("AWS_S3_BUCKET_NAME")
            logging.info(f"✅ S3 client initialized for bucket: {self.bucket_name}")
        except NoCredentialsError:
            logging.error("🔴 AWS credentials not found in environment")
            raise
        except Exception as e:
            logging.error(f"🔴 Error initializing S3 client: {e}")
            raise
    
    def pull_conversations_from_s3(self, type):
        """Pull all conversation files from S3 bucket."""
        if not self.s3_client: 
            logging.error("S3 service not initialized")
            return []
        
        bucket_name = self.bucket_name 
        if type == "streamline":
            prefix = 'conversations_streamline/'
        elif type == "agent_streamline":
            prefix = 'conversations_agent_streamline/'
        else:
            logging.error(f"Unknown type: {type}")
            return []
        
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

            all_conversations = []

            for page in pages:
                if 'Contents' not in page:
                    continue
                for obj in page['Contents']:
                    obj_key = obj['Key']
                    if obj_key.endswith('/') or not (obj_key.endswith('.json') or obj_key.endswith('.jsonl')):
                        continue
                    try:
                        response_obj = self.s3_client.get_object(Bucket=bucket_name, Key=obj_key)
                        obj_content = response_obj['Body'].read().decode('utf-8')

                        if obj_key.endswith('.json'):
                            data = json.loads(obj_content)
                            all_conversations.extend(data if isinstance(data, list) else [data])
                        elif obj_key.endswith('.jsonl'):
                            for line in obj_content.strip().split('\n'):
                                if line.strip():
                                    all_conversations.append(json.loads(line))

                        logging.info(f"✅ Processed {obj_key}: total so far = {len(all_conversations)}")

                    except Exception as e:
                        logging.error(f"❌ Error processing {obj_key}: {str(e)}")
                        continue

            logging.info(f"🎉 Total conversations pulled: {len(all_conversations)}")
            return all_conversations
            
        except Exception as e:
            logging.error(f"Error listing S3 objects: {str(e)}")
            return []

# MLflow setup
def setup_mlflow():
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("ConversationEvaluation")

# Evaluation implementation
def evaluate_session(session_data: Dict) -> dict:
    """Evaluate an entire conversation session."""
    session_id = session_data["session_id"]
    user_text = session_data["user"]
    assistant_text = session_data["assistant"]
    
    metric_rubrics = {
        "clarity_score": """
Clarity Score Rubric:
Score 1: Very unclear. The explanations are confusing or incoherent throughout the conversation.
Score 2: Mostly unclear. Difficult to understand without rereading multiple parts.
Score 3: Fair clarity. Some exchanges are understandable, others unclear.
Score 4: Good clarity. Most explanations are understandable with minor issues.
Score 5: Excellent clarity. Very easy to understand throughout, well-structured conversation.
""",
        "vocabulary_enrichment_score": """
Vocabulary Enrichment Score Rubric:
Score 1: No new vocabulary introduced throughout the conversation.
Score 2: One or two new words introduced without explanation.
Score 3: Some new words introduced with limited examples or context.
Score 4: Several new words introduced with good examples and practice.
Score 5: Rich vocabulary introduced with clear, contextual examples and repeated practice opportunities.
""",
        "language_accuracy_score": """
Language Accuracy Score Rubric:
Score 1: Frequent grammar and vocabulary errors throughout, very hard to follow.
Score 2: Several errors that disrupt understanding across the conversation.
Score 3: Some grammar/vocab mistakes, but conversation is still clear overall.
Score 4: Minor issues, mostly correct usage throughout the session.
Score 5: Grammar and vocabulary are accurate and natural throughout the entire conversation.
""",
    }
    
    results = {
        "session_id": session_id,
        "metrics": {}
    }
    
    # Get OpenAI API key from environment
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    
    for metric_name, rubric in metric_rubrics.items():
        try:
            # Create evaluation prompt
            prompt = f"""
You are evaluating a conversation between an English learning assistant and a student.

{rubric}

User Messages:
{user_text}

Assistant Responses:
{assistant_text}

Provide your evaluation as a JSON object with:
- "score": integer from 1-5
- "reasoning": brief explanation for your score
"""
            
            # Call OpenAI API for evaluation
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert at evaluating English learning conversations."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            
            evaluation = json.loads(response.choices[0].message.content)
            results["metrics"][metric_name] = evaluation
            
        except Exception as e:
            logging.error(f"Error evaluating {metric_name} for session {session_id}: {str(e)}")
            results["metrics"][metric_name] = {
                "score": None,
                "reasoning": f"Evaluation failed: {str(e)}"
            }
    
    return results

def evaluate_multiple_sessions(merged_sessions: List[Dict]) -> List[Dict]:
    """Evaluate multiple conversation sessions."""
    results = []
    
    for session in merged_sessions:
        logging.info(f"Evaluating session: {session['session_id']}")
        evaluation_result = evaluate_session(session)
        results.append(evaluation_result)
    
    return results

# Task functions
def pull_conversation(**context):
    """Pull conversations from S3."""
    s3_service = S3Service() 
    return s3_service.pull_conversations_from_s3(type="streamline")

def group_conversations_by_session(**context):
    """Group conversation data by session_id."""
    all_conversations = context['task_instance'].xcom_pull(task_ids='pull_s3_data')
    
    if not all_conversations:
        logging.warning("No conversation data received")
        return {}
    
    sessions_grouped = defaultdict(list)
    
    for conversation in all_conversations:
        session_id = conversation.get('session_id')
        if session_id:
            sessions_grouped[session_id].append(conversation)
        else:
            logging.warning(f"Conversation missing session_id: {conversation}")
    
    logging.info(f"Grouped conversations into {len(sessions_grouped)} sessions")
    
    return dict(sessions_grouped)

def merge_sessions_data(**context):
    """Merge conversation turns by session_id into complete conversations."""
    sessions_grouped = context['task_instance'].xcom_pull(task_ids='group_by_session')
    
    if not sessions_grouped:
        logging.warning("No grouped session data received")
        return []
    
    def merge_sessions(session_data_list: List[Dict]) -> List[Dict]:
        """Merge conversation turns by session_id into a single conversation per session."""
        merged = defaultdict(lambda: {"session_id": "", "user": [], "assistant": []})

        for item in session_data_list:
            session_id = item["session_id"]
            merged[session_id]["session_id"] = session_id
            merged[session_id]["user"].append(item.get("student_message", ""))
            merged[session_id]["assistant"].append(item.get("model_response", ""))

        result = []
        for session_id, convo in merged.items():
            result.append({
                "session_id": session_id,
                "user": " ".join(convo["user"]),
                "assistant": " ".join(convo["assistant"])
            })

        return result
    
    all_merged_sessions = []
    
    for session_id, session_conversations in sessions_grouped.items():
        try:
            merged_session = merge_sessions(session_conversations)
            all_merged_sessions.extend(merged_session)
            
        except Exception as e:
            logging.error(f"Error merging session {session_id}: {str(e)}")
            continue
    
    logging.info(f"Merged {len(all_merged_sessions)} complete sessions")
    
    return all_merged_sessions

def evaluate_sessions(**context):
    """Evaluate sessions and log results to MLflow."""
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
            
            # Use default session configuration
            session_config = DEFAULT_SESSION_CONFIG

            # Create a nested run for this session
            with mlflow.start_run(run_name=f"session_{session_id}", nested=True):
                # Log configuration
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
    """Print the evaluation results to Airflow logs."""
    results = context['task_instance'].xcom_pull(task_ids='evaluate_sessions')

    if not results:
        logging.warning("No evaluation results to print.")
        return

    for result in results:
        logging.info(f"Evaluation result for session {result['session_id']}: {json.dumps(result, indent=2)}")

# Define tasks
pull_data_task = PythonOperator(
    task_id='pull_s3_data',
    python_callable=pull_conversation,
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