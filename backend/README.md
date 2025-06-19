# Langlish - English Learning Voice Assistant Backend

## Description

Langlish is a voice-based English learning assistant powered by AI. This backend service provides the API infrastructure for the voice assistant application, built with FastAPI for high performance and modern Python features.

## Features

- FastAPI-based REST API
- Pydantic models for data validation
- Type hints and modern Python 3.11+ features
- Development tools integration (pytest, mypy, ruff)

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager (recommended) or pip

## Installation

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
├── models/              # Pydantic models
│   └── greeting_response.py
├── tests/               # Test files
├── pyproject.toml       # Project configuration and dependencies
├── uv.lock             # Locked dependencies (if using uv)
└── README.md           # This file
```

## License

This project is licensed under the terms specified in the LICENSE file in the root directory.
