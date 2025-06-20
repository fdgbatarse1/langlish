# Langlish - Real-time English Teaching Voice Assistant

## Description

Langlish is a real-time English learning voice assistant that uses OpenAI's speech-to-speech technology to provide conversational English practice. Students can speak naturally and receive immediate feedback, corrections, and guidance from an AI English teacher through voice interaction.

## Features

- Real-time speech-to-speech communication
- OpenAI Real-time API integration
- Conversational English learning
- Grammar corrections and vocabulary help
- Natural voice interaction with audio processing
- Modern web interface with React and TypeScript
- FastAPI backend with WebSocket support
- **AWS S3 integration for audio storage** - Save and archive conversation audio files

## Prerequisites

- Python 3.11 or higher
- Node.js 18 or higher
- npm or pnpm package manager
- [uv](https://github.com/astral-sh/uv) package manager (recommended for backend)
- OpenAI API key with Real-time API access
- AWS account (optional, for audio storage)

## Installation

### Backend Setup

1. Navigate to the backend directory:

```bash
cd backend
```

2. Install uv if you haven't already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. Create virtual environment and install dependencies:

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

4. Set up environment variables:

```bash
# Create .env file from example
echo "OPENAI_API_KEY=your_openai_api_key_here" > .env

# For AWS S3 audio storage (optional):
echo "AWS_ACCESS_KEY_ID=your_aws_access_key_id_here" >> .env
echo "AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key_here" >> .env
echo "AWS_S3_BUCKET_NAME=your_s3_bucket_name_here" >> .env
echo "AWS_S3_REGION=us-east-1" >> .env
```

For detailed AWS S3 setup instructions, see [backend/AWS_S3_SETUP.md](backend/AWS_S3_SETUP.md).

### Frontend Setup

1. Navigate to the frontend directory:

```bash
cd frontend
```

2. Install dependencies:

```bash
npm install
# or
pnpm install
```

## Running the Application

### Development Mode

1. Start the backend server:

```bash
cd backend
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python -m uvicorn main:app --reload
```

2. In a new terminal, start the frontend:

```bash
cd frontend
npm run dev
# or
pnpm dev
```

3. Open your browser and navigate to `http://localhost:5173`

### Production Mode

See individual README files in `backend/` and `frontend/` directories for production deployment instructions.

## Usage

1. Click the blue microphone button to start recording
2. Speak in English - ask questions, practice conversation, or request help
3. Click the red button to stop recording
4. Listen to Langlish's response and continue the conversation

## Development

### Backend Development

```bash
cd backend
pytest                    # Run tests
mypy .                    # Type checking
ruff check .              # Linting
ruff format .             # Formatting
```

### Frontend Development

```bash
cd frontend
npm run test              # Run tests
npm run lint              # Linting
npm run type-check        # Type checking
npm run build             # Build for production
```

## Project Structure

```
langlish/
├── backend/              # FastAPI backend with WebSocket support
│   ├── main.py          # Application entry point
│   ├── src/             # Source code
│   └── tests/           # Backend tests
├── frontend/            # React frontend application
│   ├── src/             # React components and logic
│   ├── public/          # Static assets
│   └── dist/            # Build output
├── README.md            # This file
└── LICENSE              # Project license
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Run the development checks
6. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
