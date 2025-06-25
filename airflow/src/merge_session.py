from collections import defaultdict
from typing import List, Dict

def merge_sessions(session_data_list: List[Dict]) -> List[Dict]:
    """
    Merge conversation turns by session_id into a single conversation per session.

    Parameters:
        session_data_list: List of dictionaries, each with 'session_id', 'student_message', and 'model_response'.

    Returns:
        List of dictionaries, one per session_id, with combined user and assistant texts.
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
