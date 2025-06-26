FROM apache/airflow:3.0.2

USER root

# Install any system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install Python packages
RUN pip install --no-cache-dir \
    openai==1.35.3 \
    boto3==1.34.122 \
    mlflow==2.14.1 