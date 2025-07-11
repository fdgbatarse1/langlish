from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.models.greeting_response import GreetingResponse
from src.routes.agent_streamline import agent_realtime_router
from src.routes.streamline import realtime_router
import sentry_sdk


sentry_sdk.init(
    dsn="https://598cb4d7cdd52621f2c4a1e86981802b@o4509557900509184.ingest.us.sentry.io/4509557948219392",
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
    # ACTIVATE TRACING
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    # ACTIVATE PROFILING
    # Set profile_session_sample_rate to 1.0 to profile 100%
    # of profile sessions.
    profile_session_sample_rate=1.0,
    # Set profile_lifecycle to "trace" to automatically
    # run the profiler on when there is an active transaction
    profile_lifecycle="trace",
)

app = FastAPI(
    title="Langlish - English Learning Voice Assistant",
    description="A voice-based English learning assistant using AI",
    version="1.0.0",
)

# Configure CORS
origins = [
    "http://localhost:5173",  # Frontend development server
    "http://localhost:3000",  # Alternative frontend port
    "http://127.0.0.1:5173",  # Alternative localhost
    "http://127.0.0.1:3000",  # Alternative localhost
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(realtime_router)
app.include_router(agent_realtime_router)


@app.get("/sentry-debug")
async def trigger_error():
    pass


@app.get("/", response_model=GreetingResponse)
def read_root() -> GreetingResponse:
    """Return a simple greeting message.

    Returns:
        GreetingResponse: A Pydantic model containing a greeting message.
    """
    return GreetingResponse(message="Hello, World!")
