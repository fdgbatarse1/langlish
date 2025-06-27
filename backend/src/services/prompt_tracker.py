import mlflow
from typing import Dict, Any


def log_prompt_version(
    session_config: Dict[str, Any], session_id: str, model_version: str = "gpt-4o"
) -> None:
    """
    Log session configuration and prompt instructions to MLflow for versioning.

        session_config: The dict containing OpenAI session config (modalities, instructions, etc.)
        session_id: Unique session ID
        model_version: LLM model version string
    """
    with mlflow.start_run(run_name=f"session_{session_id}"):
        mlflow.log_param("model_version", model_version)
        mlflow.log_param("session_id", session_id)

        # Log the prompt instructions
        instructions = session_config.get("session", {}).get("instructions", "")
        mlflow.log_text(instructions, "prompt.txt")

        # Log full session config JSON
        mlflow.log_dict(session_config, "session_config.json")
