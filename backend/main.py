from fastapi import FastAPI
from src.models.greeting_response import GreetingResponse
from src.routes.streamline import realtime_router

from src.config import OPENAI_API_KEY

app = FastAPI(
    title="Langlish - English Learning Voice Assistant",
    description="A voice-based English learning assistant using AI",
    version="1.0.0",
)

app.include_router(realtime_router)

@app.get("/", response_model=GreetingResponse)
def read_root() -> GreetingResponse:
    """Return a simple greeting message.

    Returns:
        GreetingResponse: A Pydantic model containing a greeting message.
    """
    return GreetingResponse(message=f"{OPENAI_API_KEY}")
