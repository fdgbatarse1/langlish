from fastapi import FastAPI

from models.greeting_response import GreetingResponse

import uvicorn
from api.upload_audio import input_router

app = FastAPI(
    title="Langlish - English Learning Voice Assistant",
    description="A voice-based English learning assistant using AI",
    version="1.0.0",
)

app.include_router(input_router)

@app.get("/", response_model=GreetingResponse)
def read_root() -> GreetingResponse:
    """Return a simple greeting message.

    Returns:
        GreetingResponse: A Pydantic model containing a greeting message.
    """
    return GreetingResponse(message="Hello, World!")

