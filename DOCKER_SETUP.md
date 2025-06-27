# Docker Compose Setup Guide for Langlish

This guide explains how to run the merged docker-compose configuration that includes all four services: Backend, Frontend, MLflow (Lifecycle), and Airflow (Workflows).

## Prerequisites

- Docker and Docker Compose installed (Docker version 20.10+ recommended)
- At least 4GB of available RAM (6GB+ recommended for Airflow)
- FFmpeg installed on the host (for backend audio processing)

## Service Overview

| Service  | Port | Description                              |
| -------- | ---- | ---------------------------------------- |
| Backend  | 8000 | FastAPI application for voice processing |
| Frontend | 5173 | React development server                 |
| MLflow   | 5000 | Experiment tracking server               |
| Airflow  | 8080 | Workflow orchestration (API/UI)          |
| Flower   | 5555 | Celery monitoring (optional)             |

## Setup Instructions

### 1. Environment Configuration

Create a `.env` file in the project root:

```bash
# Airflow configuration (REQUIRED)
AIRFLOW_UID=50000

# Airflow default credentials (change in production)
_AIRFLOW_WWW_USER_USERNAME=admin
_AIRFLOW_WWW_USER_PASSWORD=admin
```

**Important**: On Linux, set `AIRFLOW_UID` to your actual user ID:

```bash
echo "AIRFLOW_UID=$(id -u)" >> .env
```

### 2. Backend Environment

Ensure your `backend/.env` file contains:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# AWS S3 Configuration (optional)
AWS_ACCESS_KEY_ID=your_aws_access_key_id_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key_here
AWS_S3_BUCKET_NAME=your_s3_bucket_name_here
AWS_S3_REGION=us-east-1

# MLflow tracking will automatically use http://mlflow:5000
```

### 3. Running the Services

Start all services:

```bash
docker compose up -d
```

Start specific services:

```bash
# Just backend and frontend
docker compose up backend frontend -d

# Add MLflow
docker compose up backend frontend mlflow -d

# Full stack with Airflow
docker compose up -d
```

### 4. Accessing the Services

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **Backend Docs**: http://localhost:8000/docs
- **MLflow UI**: http://localhost:5000
- **Airflow UI**: http://localhost:8080 (username: admin, password: admin)
- **Flower** (if enabled): http://localhost:5555

### 5. Service Dependencies

The services are configured with the following dependencies:

- Frontend → Backend
- Backend → MLflow
- Airflow services → PostgreSQL & Redis

## Development Workflow

### Frontend Development

The frontend uses hot-reload and connects to the backend via WebSocket. The environment variables `VITE_API_URL` and `VITE_WS_URL` are automatically configured to use the backend container.

### Backend Development

The backend source code is mounted as a volume, so changes are reflected immediately when using FastAPI's auto-reload feature.

### MLflow Tracking

The backend automatically tracks experiments to MLflow at `http://mlflow:5000`. View experiments in the MLflow UI.

### Airflow DAGs

Place your DAG files in `workflows/dags/`. They will be automatically picked up by Airflow.

## Troubleshooting

### Port Conflicts

If you encounter port conflicts, you can change them in `docker-compose.yml`:

```yaml
services:
  backend:
    ports:
      - "8001:80" # Change 8001 to your preferred port
```

### Airflow Issues

1. **Permission errors**: Ensure `AIRFLOW_UID` is set correctly
2. **Memory issues**: Airflow requires at least 4GB RAM
3. **First run**: The `airflow-init` service must complete successfully before other Airflow services start

### Frontend WebSocket Connection

If the frontend can't connect to the backend:

1. Check that the backend is running: `docker compose ps backend`
2. Verify the backend logs: `docker compose logs backend`
3. Ensure no firewall is blocking WebSocket connections

### MLflow Connection

If the backend can't connect to MLflow:

1. Check MLflow is running: `docker compose ps mlflow`
2. Verify MLflow logs: `docker compose logs mlflow`

## Stopping Services

Stop all services:

```bash
docker compose down
```

Stop and remove volumes (WARNING: This will delete all data):

```bash
docker compose down -v
```

## Production Considerations

1. **Security**:

   - Change all default passwords
   - Use secrets management for API keys
   - Enable HTTPS/WSS for external access

2. **Performance**:

   - Remove volume mounts for source code
   - Build optimized production images
   - Configure proper resource limits

3. **Persistence**:
   - Back up the MLflow data in `lifecycle/`
   - Back up Airflow PostgreSQL database
   - Consider using external databases for production

## Monitoring

View logs for all services:

```bash
docker compose logs -f
```

View logs for specific service:

```bash
docker compose logs -f backend
```

Check service health:

```bash
docker compose ps
```
