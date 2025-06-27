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
# Use MLflow server for tracking
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")

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
            # Check for required environment variables
            self.aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
            self.aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
            self.bucket_name = os.environ.get("AWS_S3_BUCKET_NAME")
            
            if not self.aws_access_key or not self.aws_secret_key:
                raise ValueError(
                    "Missing AWS credentials. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables."
                )
            
            if not self.bucket_name:
                raise ValueError(
                    "Missing S3 bucket name. Please set AWS_S3_BUCKET_NAME environment variable."
                )
            
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=os.environ.get("AWS_S3_REGION", "us-east-1"),
            )
            
            logging.info(f"✅ S3 client initialized for bucket: {self.bucket_name}")
        except NoCredentialsError:
            logging.error("🔴 AWS credentials not found in environment")
            raise
        except ValueError as ve:
            logging.error(f"🔴 Configuration error: {ve}")
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
def evaluate_conversation_turn(turn_data: Dict) -> dict:
    """Evaluate a single conversation turn (one exchange between user and assistant)."""
    session_id = turn_data["session_id"]
    user_text = turn_data["user"]
    assistant_text = turn_data["assistant"]
    
    logging.info(f"Starting evaluation for session {session_id}")
    logging.info(f"User text: {len(user_text)} chars, Assistant text: {len(assistant_text)} chars")
    
    # Skip evaluation if either text is empty
    if not user_text.strip() or not assistant_text.strip():
        logging.warning(f"Skipping evaluation for session {session_id} - empty user or assistant text")
        return {
            "session_id": session_id,
            "metrics": {
                metric: {
                    "score": None,
                    "reasoning": "Empty conversation content"
                } for metric in metric_rubrics.keys()
            }
        }
    
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
"fluency_practice_score": """
Fluency Practice Score Rubric:
Score 1: No encouragement for continued practice. Conversation ends abruptly without follow-up questions or challenges.
Score 2: Minimal encouragement. Rarely asks follow-up questions or provides new challenges to keep user engaged.
Score 3: Some encouragement present. Occasionally asks questions or suggests new topics, but inconsistently throughout the session.
Score 4: Good encouragement. Regularly asks follow-up questions, introduces new challenges, and motivates continued practice.
Score 5: Excellent encouragement. Consistently asks engaging questions, provides progressive challenges, and actively motivates user to continue practicing with enthusiasm.
""",
    }
    
    results = {
        "session_id": session_id,
        "metrics": {}
    }
    
    # Get OpenAI API key from environment
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    
    if not openai.api_key:
        logging.error("OPENAI_API_KEY not set in environment variables")
        return {
            "session_id": session_id,
            "metrics": {
                metric: {
                    "score": None,
                    "reasoning": "OpenAI API key not configured"
                } for metric in metric_rubrics.keys()
            }
        }
    
    for metric_name, rubric in metric_rubrics.items():
        try:
            # Truncate very long conversations to avoid API limits
            max_chars = 4000  # Leave room for the rubric and instructions
            truncated_user = user_text[:max_chars] + "..." if len(user_text) > max_chars else user_text
            truncated_assistant = assistant_text[:max_chars] + "..." if len(assistant_text) > max_chars else assistant_text
            
            # Create evaluation prompt
            prompt = f"""
You are evaluating a conversation between an English learning assistant and a student.

{rubric}

User Messages:
{truncated_user}

Assistant Responses:
{truncated_assistant}

Provide your evaluation as a JSON object with:
- "score": integer from 1-5
- "reasoning": brief explanation for your score
"""
            
            # Call OpenAI API for evaluation
            logging.info(f"Calling OpenAI API for {metric_name}...")
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert at evaluating English learning conversations."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                timeout=60  # Add timeout
            )
            
            evaluation = json.loads(response.choices[0].message.content)
            results["metrics"][metric_name] = evaluation
            logging.info(f"Successfully evaluated {metric_name}: score={evaluation.get('score')}")
            
        except Exception as e:
            logging.error(f"Error evaluating {metric_name} for session {session_id}: {str(e)}")
            results["metrics"][metric_name] = {
                "score": None,
                "reasoning": f"Evaluation failed: {str(e)}"
            }
    
    return results

def evaluate_multiple_conversation_turns(conversation_turns: List[Dict]) -> List[Dict]:
    """Evaluate multiple conversation turns individually."""
    results = []
    
    for i, turn in enumerate(conversation_turns):
        logging.info(f"Evaluating conversation {i+1}/{len(conversation_turns)} from session: {turn['session_id']}")
        start_time = datetime.now()
        evaluation_result = evaluate_conversation_turn(turn)
        end_time = datetime.now()
        logging.info(f"Completed evaluation {i+1} in {(end_time - start_time).total_seconds():.2f} seconds")
        results.append(evaluation_result)
    
    logging.info(f"Completed all {len(conversation_turns)} evaluations")
    return results

# Task functions
def pull_conversation(**context):
    """Pull conversations from S3."""
    try:
        s3_service = S3Service() 
        conversations = s3_service.pull_conversations_from_s3(type="streamline")
        logging.info(f"Successfully pulled {len(conversations)} conversations from S3")
        return conversations
    except Exception as e:
        logging.error(f"Failed to pull conversations from S3: {str(e)}")
        return []

def group_conversations_by_session(**context):
    """Group conversation data by session_id."""
    all_conversations = context['task_instance'].xcom_pull(task_ids='pull_s3_data')
    
    if not all_conversations:
        logging.warning("No conversation data received")
        return {}
    
    # Debug: Print first conversation to see data structure
    if all_conversations:
        logging.info(f"Sample conversation data structure: {json.dumps(all_conversations[0], indent=2)}")
    
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
    """Merge conversation turns by session_id but create multiple conversation objects."""
    sessions_grouped = context['task_instance'].xcom_pull(task_ids='group_by_session')
    
    if not sessions_grouped:
        logging.warning("No grouped session data received")
        return []
    
    def process_session_conversations(session_data_list: List[Dict]) -> List[Dict]:
        """Process conversations for a session - concatenate if needed but keep as separate objects."""
        result = []
        
        for item in session_data_list:
            session_id = item["session_id"]
            
            # Each item from S3 is already a complete conversation
            # Just ensure it has the right structure
            conversation_obj = {
                "session_id": session_id,
                "user": item.get("user", "") or item.get("student_message", ""),
                "assistant": item.get("assistant", "") or item.get("model_response", "")
            }
            
            # Only add if both user and assistant have content
            if conversation_obj["user"] and conversation_obj["assistant"]:
                result.append(conversation_obj)
            
        return result
    
    all_conversations = []
    
    for session_id, session_conversations in sessions_grouped.items():
        try:
            logging.info(f"Processing session {session_id} with {len(session_conversations)} conversation(s)")
            
            processed_conversations = process_session_conversations(session_conversations)
            all_conversations.extend(processed_conversations)
            
        except Exception as e:
            logging.error(f"Error processing session {session_id}: {str(e)}")
            continue
    
    logging.info(f"Total conversations to evaluate: {len(all_conversations)}")
    
    # Debug: Print sample conversations
    if all_conversations:
        sample = all_conversations[0]
        logging.info(f"Sample conversation:")
        logging.info(f"  Session ID: {sample['session_id']}")
        logging.info(f"  User text length: {len(sample['user'])} chars")
        logging.info(f"  Assistant text length: {len(sample['assistant'])} chars")
        logging.info(f"  User preview: {sample['user'][:200]}..." if len(sample['user']) > 200 else f"  User: {sample['user']}")
        logging.info(f"  Assistant preview: {sample['assistant'][:200]}..." if len(sample['assistant']) > 200 else f"  Assistant: {sample['assistant']}")
    
    return all_conversations

def evaluate_sessions(**context):
    """Evaluate sessions and log results to MLflow."""
    setup_mlflow()

    merged_sessions = context['task_instance'].xcom_pull(task_ids='merge_sessions')
    if not merged_sessions:
        logging.warning("No merged sessions received")
        return []
    
    results = evaluate_multiple_conversation_turns(merged_sessions)

    # Use a parent run for the entire evaluation batch
    parent_run_name = f"airflow_eval_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    with mlflow.start_run(run_name=parent_run_name):
        mlflow.log_param("num_conversations", len(merged_sessions))
        mlflow.log_param("evaluation_type", "streamline_conversations")

        for idx, result in enumerate(results):
            session_id = result["session_id"]

            # Find the corresponding session data for conversation history
            session_data = next((s for s in merged_sessions if s["session_id"] == session_id and merged_sessions.index(s) == idx), {})
            
            # Use default session configuration
            session_config = DEFAULT_SESSION_CONFIG

            # Create a nested run for this conversation
            with mlflow.start_run(run_name=f"conversation_{idx+1}_session_{session_id}", nested=True):
                # Log configuration
                model_version = session_config.get("model_version", "gpt-4o")
                instructions = session_config.get("session", {}).get("instructions", "")
                
                mlflow.log_param("model_version", model_version)
                mlflow.log_param("session_id", session_id)
                mlflow.log_param("conversation_index", idx)
                mlflow.log_text(instructions, "prompt.txt")
                mlflow.log_dict(session_config, "session_config.json")

                # Log conversation history
                if session_data:
                    conversation_data = {
                        "session_id": session_id,
                        "conversation_index": idx,
                        "user_messages": session_data.get("user", ""),
                        "assistant_messages": session_data.get("assistant", ""),
                        "conversation_length": len(session_data.get("user", "").split()) + len(session_data.get("assistant", "").split())
                    }
                    mlflow.log_dict(conversation_data, f"conversation_{idx+1}.json")
                    mlflow.log_param("conversation_length_words", conversation_data["conversation_length"])

                # Log evaluation metrics
                for metric_name, metric_details in result["metrics"].items():
                    score = metric_details.get("score")
                    if score is not None:
                        mlflow.log_metric(f"{metric_name}", score)
                
                # Log full results artifact
                mlflow.log_dict(result, f"results_{idx+1}.json")

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
# 1. Pull data from S3
# 2. Group conversations by session_id 
# 3. Process all conversation turns (keeping them separate for individual evaluation)
# 4. Evaluate each conversation turn individually
# 5. Print results
pull_data_task >> group_sessions_task >> merge_sessions_task >> evaluate_sessions_task >> print_results_task 