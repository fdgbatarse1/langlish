import openai
import csv
from src.services.s3_service import s3_service

def run_gpt(prompt: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You are an expert grader."},
                  {"role": "user", "content": prompt}],
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
"""

    grading_prompt += """
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
        if "justification" in line.lower():
            parts = line.split(":")
            if len(parts) > 1:
                justification = parts[1].strip()

    return {
        "score": score,
        "justification": justification,
        "grading_prompt": grading_prompt,
        "grading_output": grading_output,
    }

def run_evaluation():
    conversations = [
        {
            "student_message": "I goed to the store yesterday.",
            "model_response": "Instead of 'goed', you should say 'went'. Good job!",
        },
        {
            "student_message": "She are happy.",
            "model_response": "Use 'is' instead of 'are'.",
        }
    ]

    results = []
    for convo in conversations:
        result = evaluate_response(
            convo["student_message"],
            convo["model_response"],
        )
        results.append({
            "student_message": convo["student_message"],
            "model_response": convo["model_response"],
            "score": result["score"],
            "justification": result["justification"]
        })

    csv_path = "/tmp/evaluation_results.csv"
    with open(csv_path, "w", newline="") as csvfile:
        fieldnames = ["student_message", "model_response", "score", "justification"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # Read CSV bytes and upload to S3
    with open(csv_path, "rb") as f:
        csv_bytes = f.read()

    s3_url = s3_service.upload_audio(
        audio_data=csv_bytes,
        file_name="evaluation_results.csv",
        content_type="text/csv",
        metadata={"type": "evaluation", "source": "auto-grader"}
    )

    print(f"✅ Uploaded to S3: {s3_url}")

