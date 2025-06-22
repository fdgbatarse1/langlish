import openai
from src.config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def run_gpt(prompt: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert grader."},
            {"role": "user", "content": prompt},
        ],
        temperature=0
    )
    return response.choices[0].message.content


def evaluate_response(student_message: str, model_response: str) -> dict:
    score_rubric = """
Score 1: Response provides no educational value, no corrections or learning.
Score 2: Response provides minimal educational value.
Score 3: Response provides moderate educational value with some corrections.
Score 4: Response provides good educational value with clear corrections and explanations.
Score 5: Response provides excellent educational value with corrections, explanations, and additional learning tips.
"""

    grading_prompt = f"""
Evaluate the model response based on educational value using the rubric:

{score_rubric}

Student message: {student_message}
Model response: {model_response}

Please provide:
- A score from 1 to 5
- A brief justification of the score.
"""

    grading_output = run_gpt(grading_prompt)

    score = None
    justification = ""
    for line in grading_output.split("\n"):
        if line.lower().startswith("score"):
            parts = line.split(":")
            if len(parts) > 1:
                try:
                    score = int(parts[1].strip())
                except:
                    pass
        elif "justification" in line.lower():
            parts = line.split(":", 1)
            if len(parts) > 1:
                justification = parts[1].strip()

    return {
        "score": score,
        "justification": justification,
        "grading_prompt": grading_prompt,
        "grading_output": grading_output,
    }
