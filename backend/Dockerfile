FROM python:3.11

# Install ffmpeg for audio processing
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /code

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for better Docker cache utilization
COPY pyproject.toml /code/pyproject.toml
COPY uv.lock /code/uv.lock

# Copy the source directory (needed for setuptools to build the package)
COPY src /code/src
COPY README.md /code/README.md

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Copy the main application file
COPY main.py /code/

# Use CMD in exec form as recommended by the documentation
# Run with uv to ensure the virtual environment is activated
CMD ["uv", "run", "fastapi", "run", "main.py", "--port", "80"] 