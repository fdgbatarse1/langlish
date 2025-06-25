import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openai import OpenAI
from src.config import OPENAI_API_KEY
from typing import Dict, List

client = OpenAI(api_key=OPENAI_API_KEY)

def run_gpt(prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert grader."},
            {"role": "user", "content": prompt},
        ],
        temperature=0
    )
    return response.choices[0].message.content

def evaluate_session(session_data: Dict) -> dict:
    """
    Evaluate an entire conversation session.
    
    Parameters:
        session_data: Dictionary with 'session_id', 'user', and 'assistant' keys
                     where 'user' and 'assistant' contain the full conversation text
    
    Returns:
        Dictionary with evaluation results for each metric
    """
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
       "fluency_practice_score": """
Fluency Practice Score Rubric:
Score 1: No encouragement for continued practice. Conversation ends abruptly without follow-up questions or challenges.
Score 2: Minimal encouragement. Rarely asks follow-up questions or provides new challenges to keep user engaged.
Score 3: Some encouragement present. Occasionally asks questions or suggests new topics, but inconsistently throughout the session.
Score 4: Good encouragement. Regularly asks follow-up questions, introduces new challenges, and motivates continued practice.
Score 5: Excellent encouragement. Consistently asks engaging questions, provides progressive challenges, and actively motivates user to continue practicing with enthusiasm.
""",

    }

    result = {
        "session_id": session_id,
        "metrics": {}
    }
    
    for metric, rubric in metric_rubrics.items():
        grading_prompt = f"""
Evaluate the entire conversation session on the following metric: **{metric}**

Rubric:
{rubric}

Full User Conversation: {user_text}

Full Assistant Conversation: {assistant_text}

Please evaluate the ENTIRE conversation session, not just individual exchanges. Consider how well the assistant performed on this metric throughout the complete interaction.

Please provide:
- A score from 1 to 5
- A brief justification for the score based on the overall conversation
"""

        grading_output = run_gpt(grading_prompt)

        # Parse the score and justification
        score = None
        justification = ""
        lines = grading_output.split("\n")
        
        for i, line in enumerate(lines):
            if "score" in line.lower() and ":" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    try:
                        score_text = parts[1].strip()
                        # Extract just the number
                        score = int(''.join(filter(str.isdigit, score_text)))
                        if score < 1 or score > 5:
                            score = None
                    except:
                        pass
            elif "justification" in line.lower() and ":" in line:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    justification = parts[1].strip()
                    # If justification continues on next lines, capture them too
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip() and not any(keyword in lines[j].lower() for keyword in ["score", "rating"]):
                            justification += " " + lines[j].strip()
                        else:
                            break

        result["metrics"][metric] = {
            "score": score,
            "justification": justification,
            "grading_prompt": grading_prompt,
            "grading_output": grading_output,
        }

    return result

def evaluate_multiple_sessions(merged_sessions: List[Dict]) -> List[Dict]:
    """
    Evaluate multiple conversation sessions.
    
    Parameters:
        merged_sessions: List of session dictionaries from merge_sessions function
    
    Returns:
        List of evaluation results, one per session
    """
    results = []
    
    for session in merged_sessions:
        print(f"Evaluating session: {session['session_id']}")
        evaluation = evaluate_session(session)
        results.append(evaluation)
    
    return results

# Example usage:
if __name__ == "__main__":
    # Example session data (output from your merge_sessions function)
    sample_session = {
        "session_id": "7418bcec-10e5-43bf-bb23-ef82435973fd",
        "user": "Hello, hi I want to practice English What topics can we discuss?",
        "assistant": "Hi there! How are you today? Are you ready to practice some English? Great! We can discuss many topics like hobbies, travel, food, or daily activities. What interests you most?"
    }
    
    # Evaluate the session
    evaluation_result = evaluate_session(sample_session)
    print(f"Evaluation for session {evaluation_result['session_id']}:")
    for metric, details in evaluation_result['metrics'].items():
        print(f"{metric}: {details['score']} - {details['justification']}")