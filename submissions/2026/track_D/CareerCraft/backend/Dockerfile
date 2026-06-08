FROM python:3.11-slim

# Prevent writing bytecode and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (build-essential for Python native extensions, curl for docker health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy python dependencies file
COPY backend/requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy FastAPI backend application code
COPY backend/app/ ./app

# Copy knowledge base documents for RAG populate
COPY docs/ ./docs

# Configure default runtime environment variables
ENV DOCS_DIR=/app/docs
ENV ENVIRONMENT=production

EXPOSE 8000

# Start FastAPI server using uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
