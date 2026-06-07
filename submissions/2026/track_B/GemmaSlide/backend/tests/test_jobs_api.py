from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.pptx import (
    JobStage,
    PptxScriptJobRecord,
    PptxScriptJobStatus,
    PresentationScriptResult,
    SlideScript,
)

client = TestClient(app)


def _status(job_id: str, stage: JobStage) -> PptxScriptJobStatus:
    now = datetime.now(tz=UTC)
    return PptxScriptJobStatus(
        job_id=job_id,
        request_id="req-1",
        status=stage,
        message="ok",
        progress_current=50,
        progress_total=100,
        created_at=now,
        updated_at=now,
        version=1,
    )


def test_submit_job_endpoint(monkeypatch) -> None:
    from app.api.v1.jobs import routes as job_routes

    called = {"delay": False}

    async def fake_save_upload(_):
        return "req-1", Path("/tmp/gemmaslide/req-1/demo.pptx")

    def fake_create_job(request_id: str):
        assert request_id == "req-1"
        return _status("job-1", JobStage.QUEUED)

    def fake_delay(**kwargs):
        called["delay"] = True
        assert kwargs["job_id"] == "job-1"

    monkeypatch.setattr(job_routes.FileService, "save_upload", fake_save_upload)
    monkeypatch.setattr(job_routes.JobStore, "create_job", fake_create_job)
    monkeypatch.setattr(job_routes.run_pptx_script_job, "delay", fake_delay)

    response = client.post(
        "/api/v1/jobs/pptx-script",
        files={
            "file": (
                "demo.pptx",
                b"fake-pptx",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "job-1"
    assert body["status"] == "queued"
    assert called["delay"] is True


def test_get_job_status_endpoint(monkeypatch) -> None:
    from app.api.v1.jobs import routes as job_routes

    record = PptxScriptJobRecord(status=_status("job-2", JobStage.PARSING), result=None)
    monkeypatch.setattr(job_routes.JobStore, "get_job", lambda _: record)

    response = client.get("/api/v1/jobs/job-2")
    assert response.status_code == 200
    assert response.json()["status"] == "parsing"


def test_get_job_result_endpoint(monkeypatch) -> None:
    from app.api.v1.jobs import routes as job_routes

    result = PresentationScriptResult(
        file_name="demo.pptx",
        total_slides=1,
        slides=[
            SlideScript(
                slide_index=1,
                narrative_segments=[],
                summary="",
                warnings=[],
                width_px=1280,
                height_px=720,
                image_base64="data:image/png;base64,ZmFrZQ==",
            )
        ],
    )
    record = PptxScriptJobRecord(status=_status("job-3", JobStage.DONE), result=result)
    monkeypatch.setattr(job_routes.JobStore, "get_job", lambda _: record)

    response = client.get("/api/v1/jobs/job-3/result")
    assert response.status_code == 200
    body = response.json()
    assert body["file_name"] == "demo.pptx"
    assert body["slides"][0]["width_px"] == 1280
    assert body["slides"][0]["height_px"] == 720
    assert body["slides"][0]["image_base64"] == "data:image/png;base64,ZmFrZQ=="
