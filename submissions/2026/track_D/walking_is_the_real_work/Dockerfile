FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    GEMMA_DEVICE=auto

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential git \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

EXPOSE 8000

# When GEMMA_STUB=1 the container starts in seconds without weights.
# For real inference, mount a Gemma 4 4B Multimodal HF cache into /models:
#   docker run -e GEMMA_STUB=0 -v $HOME/.cache/huggingface:/models -p 8000:8000 walking_is_the_real_work
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
