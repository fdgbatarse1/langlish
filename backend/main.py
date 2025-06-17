from fastapi import FastAPI
from src.models.greeting import Greeting

app = FastAPI(
    title="Langlish",
    description="A voice-based English learning assistant",
)

@app.get("/", response_model=Greeting)
def read_root() -> Greeting:

    return Greeting(message="Hello world")