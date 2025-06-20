# Langlish - English Learning Voice Assistant Backend

## Description

Langlish is a voice-based English learning assistant powered by AI. This backend service provides the API infrastructure for the voice assistant application, built with FastAPI for high performance and modern Python features.

## Features

- FastAPI-based REST API with WebSocket support
- Real-time audio streaming with OpenAI's Realtime API
- WebSocket endpoint for bidirectional audio communication
- Audio format conversion (WebM to PCM16)
- AWS S3 integration for audio storage and archiving
- Pydantic models for data validation
- Type hints and modern Python 3.11+ features
- Development tools integration (pytest, mypy, ruff)

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager (recommended) or pip
- OpenAI API key with Realtime API access
- AWS account and S3 bucket (optional, for audio storage)
- FFmpeg installed on your system (for audio format conversion)

## Installation

### Installing FFmpeg

FFmpeg is required for audio format conversion:

**Ubuntu/Debian:**

```bash
sudo apt update && sudo apt install ffmpeg
```

**macOS:**

```bash
brew install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html) or use Chocolatey:

```bash
choco install ffmpeg
```

### Using uv (Recommended)

1. Clone the repository and navigate to the backend directory:

```bash
cd backend
```

2. Install uv if you haven't already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. Create a virtual environment and install dependencies:

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

4. Install development dependencies:

```bash
uv pip install -e ".[dev]"
```

5. Set up environment variables:

```bash
# Create .env file with your credentials
cat > .env << EOF
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# AWS S3 Configuration (optional)
AWS_ACCESS_KEY_ID=your_aws_access_key_id_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key_here
AWS_S3_BUCKET_NAME=your_s3_bucket_name_here
AWS_S3_REGION=us-east-1
EOF
```

For detailed AWS S3 setup instructions, see [AWS_S3_SETUP.md](AWS_S3_SETUP.md).

### Using pip

1. Clone the repository and navigate to the backend directory:

```bash
cd backend
```

2. Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install the package and dependencies:

```bash
pip install -e .
```

4. Install development dependencies:

```bash
pip install -e ".[dev]"
```

## Running the Application

### Development Server

Run the FastAPI development server with auto-reload:

```bash
fastapi dev main.py
```

The API will be available at `http://localhost:8000`

### Production Server

For production deployment:

```bash
fastapi run main.py
```

## API Documentation

Once the server is running, you can access:

- Interactive API documentation (Swagger UI): `http://localhost:8000/docs`
- Alternative API documentation (ReDoc): `http://localhost:8000/redoc`
- OpenAPI schema: `http://localhost:8000/openapi.json`
- WebSocket endpoint: `ws://localhost:8000/streamline`

## WebSocket Audio Streaming

The `/streamline` WebSocket endpoint handles real-time audio communication:

1. Accepts WebM audio from the client
2. Converts to PCM16 format for OpenAI
3. Streams to OpenAI's Realtime API
4. Receives AI responses and forwards to client
5. Optionally saves audio files to AWS S3

## Audio Storage

When AWS S3 is configured, the application automatically:

- Saves user input audio as WebM files
- Saves assistant responses as WebM files (converted from PCM)
- Organizes files by session ID and timestamp
- Includes metadata for easy retrieval

## Development

### Running Tests

```bash
pytest
```

### Type Checking

```bash
mypy .
```

### Linting and Formatting

```bash
ruff check .
ruff format .
```

## Project Structure

```
backend/
├── main.py              # FastAPI application entry point
├── src/                 # Source code
│   ├── config.py        # Configuration and environment variables
│   ├── models/          # Pydantic models
│   │   └── greeting_response.py
│   ├── routes/          # API routes
│   │   └── streamline.py # WebSocket audio streaming endpoint
│   └── services/        # Business logic services
│       └── s3_service.py # AWS S3 operations
├── tests/               # Test files
├── pyproject.toml       # Project configuration and dependencies
├── uv.lock             # Locked dependencies (if using uv)
├── AWS_S3_SETUP.md     # AWS S3 setup guide
└── README.md           # This file
```

## License

This project is licensed under the terms specified in the LICENSE file in the root directory.
