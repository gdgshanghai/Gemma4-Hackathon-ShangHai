# GemmaSlide Backend

FastAPI service to upload a `.pptx`, convert each slide to image, and extract slide element metadata and coordinates with `python-pptx`.

## Features

- Single sync API endpoint for `.pptx` upload
- Async background job API for multimodal script generation
- Per-slide PNG rendering via `pptxtoimages`
- Per-slide element extraction with `python-pptx`
- Stage-level SSE job status streaming (`queued`, `parsing`, `llm`, `assembling`, `done`, `error`)
- Returns 3 coordinate systems for each element:
  - EMU (native PPT unit)
  - Normalized coordinates (0-1)
  - Pixel coordinates mapped to rendered slide image
- Supports most shape categories (text, pictures, table, chart, group, line, connector, and more)

## System Prerequisites

Install these tools before running:

- LibreOffice (`soffice` in PATH)
- Poppler utils (`pdftoppm` in PATH)

Example on Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y libreoffice poppler-utils
```

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run worker (required for async job endpoints):

```bash
cd backend
celery -A app.celery_app.celery_app worker --loglevel INFO
```

Run Redis (required for job state + queue):

```bash
docker run --rm -p 6379:6379 redis:7-alpine
```

## Docker

### Compose

Run the production-style service:

```bash
docker compose up --build
```

Run the development service with source mounts and auto-reload:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Build image:

```bash
cd backend
docker build -t gemmaslide-backend:full-font .
```

Run container:

```bash
docker run --rm -p 8000:8000 \
  -e CORS_ALLOW_ORIGINS='*' \
  -e TEMP_ROOT=/tmp/gemmaslide \
  gemmaslide-backend:full-font
```

### Font Matching Notes

- The image includes broad open-source fonts (Noto + DejaVu + Liberation), which improves multilingual rendering and reduces missing glyphs.
- Exact text layout for proprietary fonts (for example Microsoft YaHei and SimSun) requires those exact font files to be available to LibreOffice.
- To use licensed fonts without baking them into the image, mount them at runtime. The container entrypoint refreshes font cache on startup.

Example with mounted private fonts:

```bash
docker run --rm -p 8000:8000 \
  -v /path/to/private-fonts:/usr/local/share/fonts/custom:ro \
  -e CORS_ALLOW_ORIGINS='*' \
  gemmaslide-backend:full-font
```

If you add or replace mounted fonts, restart the container so startup cache refresh can pick them up.

## API

### Health

- `GET /api/v1/health`

### Parse PPTX

- `POST /api/v1/debug/pptx/parse`
- Content type: `multipart/form-data`
- File field: `file`
- Query params:
  - `include_images_base64` (bool, default `true`)
  - `flatten_groups` (bool, default `true`)
  - `element_types` (repeatable string query, optional; filter by lowercased `shape_type_name`)

Example request:

```bash
curl -X POST "http://localhost:8000/api/v1/debug/pptx/parse?include_images_base64=true&flatten_groups=true" \
  -F "file=@/path/to/demo.pptx"
```

### Async Script Job

Submit a new job:

- `POST /api/v1/jobs/pptx-script`
- Content type: `multipart/form-data`
- File field: `file`
- Query params:
  - `include_images_base64` (bool, default `true`)
  - `flatten_groups` (bool, default `true`)
  - `element_types` (repeatable string query, optional)
  - `llm_model` (optional model override)

Example:

```bash
curl -X POST "http://localhost:8000/api/v1/jobs/pptx-script" \
  -F "file=@/path/to/demo.pptx"
```

Get job status:

- `GET /api/v1/jobs/{job_id}`

Stream stage updates (SSE):

- `GET /api/v1/jobs/{job_id}/events`

Get final result:

- `GET /api/v1/jobs/{job_id}/result`

The final response includes narrative segments with:

- `text`
- `visual_cue` (`action_type`, `target_id`, `timing`)
- `timing_placeholder`
- `estimated_start_seconds`
- `target_bbox_px` (resolved from canonical parsed element coordinates)

LLM environment settings:

- `LLM_ENDPOINT` (optional OpenAI-compatible base URL)
- `LLM_MODEL`
- `LLM_TEMPERATURE`
- `LLM_MAX_TOKENS`

## Response Notes

- `slides[].elements[]` contains parsed shape-level metadata.
- Each element includes:
  - `bbox_emu`
  - `bbox_norm`
  - `bbox_px` (null when slide image unavailable)
- `slides[].image.image_base64` is returned as `data:image/png;base64,...` when enabled.

## Limitations

- No OCR is performed. Text inside inserted image pixels is not recognized.
- Some complex Office object internals (certain SmartArt/chart internals) may not be fully exposed by `python-pptx` and are reported as best-effort shape metadata.
