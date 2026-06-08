from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from uuid import uuid4

from services.decision_service import DecisionService
from services.vision_service import VisionService
from services.speech_service import SpeechService
from services.php_bridge_service import PhpBridgeService

app = FastAPI(
    title="Gemma4 Elderly Care AI Backend",
    description="Multimodal AI backend for fall detection, speech recognition, and emergency decision making.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8080", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

vision_service = VisionService()
speech_service = SpeechService()
decision_service = DecisionService()
php_bridge_service = PhpBridgeService()
latest_vision_state: dict = {}
latest_speech_state: dict = {
    "transcript": "",
    "intent": "none",
}


class AnalyzeRequest(BaseModel):
    """Payload sent by PHP API for multimodal decision analysis."""

    state: dict = Field(default_factory=dict)


class VisionFrameRequest(BaseModel):
    """Demo payload for frame analysis. Replace frame_path with camera frame bytes in production."""

    frame_path: str | None = None


class BrowserFrameRequest(BaseModel):
    """Base64 browser camera frame sent by the dashboard."""

    image: str
    push_to_php: bool = True
    no_response_seconds: int = 0


class SpeechRequest(BaseModel):
    """Demo payload for audio transcription. Replace audio_path with stream chunks in production."""

    audio_path: str | None = None


class PipelineRequest(BaseModel):
    """Run one AI cycle and optionally push JSON result to PHP."""

    frame_path: str | None = None
    audio_path: str | None = None
    no_response_seconds: int = 0
    push_to_php: bool = True


@app.get("/health")
def health() -> dict:
    """Return backend health for integration checks."""
    return {
        "success": True,
        "service": "ai_backend",
        "status": "ok",
        "vision": vision_service.health(),
    }


@app.post("/vision/detect")
def detect_fall(payload: VisionFrameRequest) -> dict:
    """Run OpenCV + YOLO fall detection adapter."""
    result = vision_service.detect_fall(payload.frame_path)
    return {"success": True, "vision": result}


@app.post("/vision/frame")
def detect_browser_frame(payload: BrowserFrameRequest) -> dict:
    """Analyze one browser camera frame and optionally update the PHP dashboard."""
    global latest_vision_state
    inference_error = None
    try:
        vision = vision_service.detect_frame_data_url(payload.image)
    except Exception as exc:
        inference_error = str(exc)
        vision = vision_service.detect_fall(None)
        vision["error"] = inference_error

    latest_vision_state = vision
    state = {
        "vision": vision,
        "speech": latest_speech_state,
        "context": {
            "no_response_seconds": payload.no_response_seconds,
        },
        "intervention": {
            "active": vision["fall_detected"],
            "voice_prompt": "Are you okay? Please answer if you can hear me."
            if vision["fall_detected"]
            else "System is monitoring.",
        },
    }
    decision = decision_service.analyze(state)
    update_payload = {
        "source": "browser-camera-yolo",
        "pipeline_id": str(uuid4()),
        "vision": vision,
        "speech": latest_speech_state,
        "context": state["context"],
        "intervention": state["intervention"],
        "decision": decision,
        "emergency": {
            "triggered": decision["emergency_alert"],
            "countdown_seconds": 0 if decision["emergency_alert"] else 10,
            "contact_status": "Notifying family" if decision["emergency_alert"] else "Standby",
        },
    }

    php_response = None
    php_error = None
    if payload.push_to_php:
        try:
            php_response = php_bridge_service.post_ai_update(update_payload)
        except Exception as exc:
            php_error = str(exc)

    return {
        "success": True,
        "payload": update_payload,
        "php_response": php_response,
        "error": inference_error,
        "php_error": php_error,
    }


@app.post("/upload_video")
async def upload_video(file: UploadFile = File(...)) -> dict:
    """Analyze an uploaded video with YOLO and update the dashboard state."""
    suffix = Path(file.filename or "upload.mp4").suffix.lower()
    if suffix not in {".mp4", ".avi", ".mov", ".mkv", ".wmv"}:
        return {"success": False, "error": "Unsupported video format. Use mp4, avi, mov, mkv, or wmv."}

    upload_dir = Path(__file__).resolve().parent / "runtime" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    video_path = upload_dir / f"{uuid4()}{suffix}"
    video_path.write_bytes(await file.read())

    vision = vision_service.analyze_video(str(video_path), max_frames=80, frame_stride=5)
    state = {
        "vision": vision,
        "speech": {
            "transcript": "",
            "intent": "none",
        },
        "context": {
            "no_response_seconds": 0,
        },
        "intervention": {
            "active": vision["fall_detected"],
            "voice_prompt": "Are you okay? Please answer if you can hear me."
            if vision["fall_detected"]
            else "System is monitoring.",
        },
    }
    decision = decision_service.analyze(state)
    update_payload = {
        "source": "video-upload-yolo",
        "pipeline_id": str(uuid4()),
        "vision": vision,
        "speech": state["speech"],
        "context": state["context"],
        "intervention": state["intervention"],
        "decision": decision,
        "emergency": {
            "triggered": decision["emergency_alert"],
            "countdown_seconds": 0 if decision["emergency_alert"] else 10,
            "contact_status": "Notifying family" if decision["emergency_alert"] else "Standby",
        },
    }

    php_response = None
    try:
        php_response = php_bridge_service.post_ai_update(update_payload)
    except Exception:
        php_response = None

    return {
        "success": True,
        "data": {
            "video": {
                "filename": file.filename,
                "stored_path": str(video_path),
                "frames_processed": vision.get("frames_processed", 0),
            },
            "vision": vision,
            "decision": decision,
            "php_response": php_response,
        },
    }


@app.post("/speech/transcribe")
def transcribe(payload: SpeechRequest) -> dict:
    """Run Whisper speech recognition adapter."""
    result = speech_service.transcribe(payload.audio_path)
    return {"success": True, "speech": result}


@app.post("/speech/upload")
async def transcribe_upload(
    audio: UploadFile = File(...),
    push_to_php: bool = Form(True),
) -> dict:
    """Transcribe dashboard microphone audio and optionally update PHP state."""
    global latest_speech_state
    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(await audio.read())
        audio_path = temp_file.name

    speech = speech_service.transcribe(audio_path)
    latest_speech_state = speech
    state = {
        "vision": latest_vision_state,
        "speech": speech,
        "context": {
            "no_response_seconds": 0,
        },
        "intervention": {
            "active": bool(latest_vision_state.get("fall_detected")),
            "voice_prompt": "Voice reply received.",
        },
    }
    decision = decision_service.analyze(state)
    update_payload = {
        "source": "browser-microphone-whisper",
        "pipeline_id": str(uuid4()),
        "vision": latest_vision_state,
        "speech": speech,
        "context": state["context"],
        "intervention": state["intervention"],
        "decision": decision,
        "emergency": {
            "triggered": decision["emergency_alert"],
            "countdown_seconds": 0 if decision["emergency_alert"] else 10,
            "contact_status": "Notifying family" if decision["emergency_alert"] else "Standby",
        },
    }

    php_response = None
    error = None
    if push_to_php:
        try:
            php_response = php_bridge_service.post_ai_update(update_payload)
        except Exception as exc:
            error = str(exc)

    return {
        "success": error is None,
        "payload": update_payload,
        "php_response": php_response,
        "error": error,
    }


@app.post("/analyze")
def analyze(payload: AnalyzeRequest) -> dict:
    """Use Gemma4 decision adapter to evaluate whether emergency help is required."""
    decision = decision_service.analyze(payload.state)
    return {"success": True, "decision": decision}


@app.post("/pipeline/run")
def run_pipeline(payload: PipelineRequest) -> dict:
    """Run YOLO + Whisper + Gemma4 demo pipeline and POST JSON to PHP backend."""
    vision = vision_service.detect_fall(payload.frame_path)
    speech = speech_service.transcribe(payload.audio_path)
    state = {
        "vision": vision,
        "speech": speech,
        "context": {
            "no_response_seconds": payload.no_response_seconds,
        },
        "intervention": {
            "active": vision["fall_detected"],
            "voice_prompt": "Are you okay? Please answer if you can hear me."
            if vision["fall_detected"]
            else "System is monitoring.",
        },
    }
    decision = decision_service.analyze(state)
    update_payload = {
        "source": "python-ai-service",
        "pipeline_id": str(uuid4()),
        "vision": vision,
        "speech": speech,
        "context": state["context"],
        "intervention": state["intervention"],
        "decision": decision,
        "emergency": {
            "triggered": decision["emergency_alert"],
            "countdown_seconds": 0 if decision["emergency_alert"] else 10,
            "contact_status": "Notifying family" if decision["emergency_alert"] else "Standby",
        },
    }

    php_response = None
    error = None
    if payload.push_to_php:
        try:
            php_response = php_bridge_service.post_ai_update(update_payload)
        except Exception as exc:
            error = str(exc)

    return {
        "success": error is None,
        "payload": update_payload,
        "php_response": php_response,
        "error": error,
    }
