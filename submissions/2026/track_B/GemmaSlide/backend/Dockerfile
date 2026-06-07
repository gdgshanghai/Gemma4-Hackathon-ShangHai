FROM python:3.13-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TEMP_ROOT=/tmp/gemmaslide

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    libreoffice-writer \
    libreoffice-impress \
    poppler-utils \
    fontconfig \
    fonts-noto-core \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    fonts-dejavu-core \
    fonts-liberation2 \
    tini \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY app /app/app
COPY tests /app/tests
COPY README.md /app/README.md
COPY docker/entrypoint.sh /app/docker/entrypoint.sh

RUN mkdir -p /usr/local/share/fonts/custom /tmp/gemmaslide \
    && fc-cache -f -v

RUN useradd --create-home --uid 10001 appuser \
    && chmod +x /app/docker/entrypoint.sh \
    && chown -R appuser:appuser /app /tmp/gemmaslide /usr/local/share/fonts/custom

USER appuser

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--", "/bin/sh", "/app/docker/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
